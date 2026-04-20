import logging
import re
from typing import Dict, List, Optional, Set

import psycopg2  # type: ignore[import-untyped]
from psycopg2.extras import execute_values

logger = logging.getLogger("omnigraph.extractor")

TECHNOLOGY_KEYWORDS = {
    "Kubernetes", "Docker", "TensorFlow", "PyTorch", "BERT", "GPT",
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Kafka", "Spark",
    "Hadoop", "AWS", "Azure", "GCP", "Istio", "ArgoCD", "Helm",
    "Terraform", "Ansible", "Jenkins", "GraphQL", "REST", "gRPC",
    "React", "Angular", "Vue", "Node.js", "Python", "Java", "Go",
    "Rust", "TypeScript", "JavaScript", "CUDA", "OpenAI", "LangChain",
    "Transformer", "LSTM", "CNN", "RNN", "GAN", "VAE", "GraphSAGE",
    "Prophet", "Airflow", "MLflow", "Kubeflow", "PagerDuty",
    "Federated Learning", "OAuth 2.0", "Zero Trust",
}

ORGANIZATION_KEYWORDS = {
    "Google", "Microsoft", "Amazon", "Meta", "Apple", "Netflix",
    "IBM", "Oracle", "SAP", "Salesforce", "VMware", "Red Hat",
    "Databricks", "Snowflake", "Confluent", "HashiCorp", "NVIDIA",
    "Intel", "AMD", "Qualcomm", "NIST", "IEEE", "ACM", "W3C",
}

STANDARD_KEYWORDS = {
    "GDPR", "CCPA", "HIPAA", "SOC2", "ISO 27001", "PCI DSS",
    "NIST 800-53", "OWASP", "CIS", "ITIL", "TOGAF", "COBIT",
}

CONCEPT_DOMAINS = {
    "machine learning": "AI", "deep learning": "AI",
    "natural language processing": "AI", "computer vision": "AI",
    "knowledge graph": "AI", "neural network": "AI", "transfer learning": "AI",
    "reinforcement learning": "AI", "cybersecurity": "Security", "zero trust": "Security",
    "encryption": "Security", "threat detection": "Security",
    "cloud computing": "Infrastructure", "containerization": "Infrastructure",
    "microservices": "Engineering", "api design": "Engineering",
    "devops": "Operations", "ci/cd": "Operations", "data governance": "Compliance",
    "compliance": "Compliance", "predictive analytics": "Analytics", "supply chain": "Business",
    "data pipeline": "Engineering", "graph neural network": "AI", "federated learning": "AI",
    "privacy": "Compliance",
}

_REL_PATTERNS_RAW = [
    (r"(\w[\w\s]*?)\s+(?:is developed by|was developed by|created by)\s+(\w[\w\s]*)", "developed_by"),
    (r"(\w[\w\s]*?)\s+(?:works for|employed at|works at)\s+(\w[\w\s]*)", "works_for"),
    (r"(\w[\w\s]*?)\s+(?:collaborates with|partners with)\s+(\w[\w\s]*)", "collaborates_with"),
    (r"(\w[\w\s]*?)\s+(?:depends on|requires|relies on)\s+(\w[\w\s]*)", "depends_on"),
    (r"(\w[\w\s]*?)\s+(?:is part of|belongs to)\s+(\w[\w\s]*)", "part_of"),
    (r"(\w[\w\s]*?)\s+(?:competes with|rivals)\s+(\w[\w\s]*)", "competitor_of"),
    (r"(\w[\w\s]*?)\s+(?:uses|utilizes|leverages|employs)\s+(\w[\w\s]*)", "uses"),
    (r"(\w[\w\s]*?)\s+(?:manages|oversees|leads)\s+(\w[\w\s]*)", "manages"),
    (r"(\w[\w\s]*?)\s+(?:is located in|based in|headquartered in)\s+(\w[\w\s]*)", "located_in"),
]
RELATIONSHIP_PATTERNS = [(re.compile(p, re.IGNORECASE), t) for p, t in _REL_PATTERNS_RAW]

PERSON_PATTERN = re.compile(
    r"\b((?:Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.)\s+[A-Z][a-z]+\s+[A-Z][a-z]+)\b"
)


# Regex and keyword-based entity, concept, and relationship extraction.
class EntityRelationExtractor:

    def __init__(self, db_connection):
        self.db = db_connection

    def extract_entities(self, text: str) -> List[Dict]:
        entities = []
        entities.extend(self._match_keywords(text, TECHNOLOGY_KEYWORDS, "technology"))
        entities.extend(self._match_keywords(text, ORGANIZATION_KEYWORDS, "organization"))
        entities.extend(self._match_keywords(text, STANDARD_KEYWORDS, "standard"))
        entities.extend(self._extract_persons(text))
        logger.info("Extracted %d entities from text.", len(entities))
        return entities

    def extract_concepts(self, text: str) -> List[Dict]:
        text_lower = text.lower()
        concepts = []
        for concept, domain in CONCEPT_DOMAINS.items():
            count = text_lower.count(concept)
            if count > 0:
                relevance = min(1.0, count * 0.15)
                concepts.append({
                    "name": concept.title(),
                    "domain": domain,
                    "relevance_score": round(relevance, 3),
                    "mention_count": count,
                })
        concepts.sort(key=lambda c: c["relevance_score"], reverse=True)
        logger.info("Extracted %d concepts from text.", len(concepts))
        return concepts

    def extract_relationships(self, text: str, entities: List[Dict]) -> List[Dict]:
        entity_names = {e["name"] for e in entities}
        relationships = []

        for pattern, rel_type in RELATIONSHIP_PATTERNS:
            for match in pattern.finditer(text):
                source = match.group(1).strip()
                target = match.group(2).strip()
                source_match = self._fuzzy_match(source, entity_names)
                target_match = self._fuzzy_match(target, entity_names)
                if source_match and target_match and source_match != target_match:
                    relationships.append({
                        "source": source_match,
                        "target": target_match,
                        "relation_type": rel_type,
                        "strength": 0.750,
                    })

        seen = set()
        unique = []
        for rel in relationships:
            key = (rel["source"], rel["target"], rel["relation_type"])
            if key not in seen:
                seen.add(key)
                unique.append(rel)
        logger.info("Extracted %d relationships from text.", len(unique))
        return unique

    def process_document(self, document_id: int) -> Dict:
        with self.db.conn.cursor() as cur:
            cur.execute(
                "SELECT content FROM omnigraph.documents WHERE document_id = %s",
                (document_id,),
            )
            row = cur.fetchone()
        if not row:
            logger.error("Document %d not found.", document_id)
            return {"entities": [], "concepts": [], "relationships": []}

        content = row[0]
        entities = self.extract_entities(content)
        concepts = self.extract_concepts(content)
        relationships = self.extract_relationships(content, entities)

        self._store_entities(entities, document_id)
        self._store_concepts(concepts, document_id)
        self._store_relationships(relationships, document_id)

        logger.info(
            "Processed document %d: %d entities, %d concepts, %d relationships.",
            document_id, len(entities), len(concepts), len(relationships),
        )
        return {
            "entities": entities,
            "concepts": concepts,
            "relationships": relationships,
        }

    def _store_entities(self, entities: List[Dict], document_id: int) -> None:
        if not entities:
            return
        entity_ids = []
        with self.db.conn.cursor() as cur:
            for entity in entities:
                try:
                    cur.execute(
                        """
                        INSERT INTO omnigraph.entities (name, entity_type, confidence)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (name, entity_type) DO UPDATE
                            SET confidence = GREATEST(entities.confidence, EXCLUDED.confidence)
                        RETURNING entity_id
                        """,
                        (entity["name"], entity["entity_type"], entity["confidence"]),
                    )
                    entity_ids.append((cur.fetchone()[0], entity))
                except psycopg2.Error as exc:
                    logger.warning("Entity storage error: %s", exc)
                    continue

            if entity_ids:
                link_rows = [
                    (document_id, eid, ent["confidence"], ent["mention_count"])
                    for eid, ent in entity_ids
                ]
                execute_values(
                    cur,
                    """
                    INSERT INTO omnigraph.document_entities
                        (document_id, entity_id, relevance, mention_count)
                    VALUES %s
                    ON CONFLICT (document_id, entity_id) DO UPDATE
                        SET mention_count = EXCLUDED.mention_count,
                            relevance = EXCLUDED.relevance
                    """,
                    link_rows,
                )
        try:
            self.db.conn.commit()
        except psycopg2.Error:
            self.db.conn.rollback()

    def _store_concepts(self, concepts: List[Dict], document_id: int) -> None:
        with self.db.conn.cursor() as cur:
            for concept in concepts:
                try:
                    cur.execute(
                        """
                        INSERT INTO omnigraph.concepts (name, domain)
                        VALUES (%s, %s)
                        ON CONFLICT (name) DO NOTHING
                        RETURNING concept_id
                        """,
                        (concept["name"], concept["domain"]),
                    )
                    row = cur.fetchone()
                    if row is None:
                        cur.execute(
                            "SELECT concept_id FROM omnigraph.concepts WHERE name = %s",
                            (concept["name"],),
                        )
                        row = cur.fetchone()
                    if row:
                        cur.execute(
                            """
                            INSERT INTO omnigraph.document_concepts
                                (document_id, concept_id, relevance_score, extracted_by)
                            VALUES (%s, %s, %s, 'system')
                            ON CONFLICT (document_id, concept_id) DO UPDATE
                                SET relevance_score = EXCLUDED.relevance_score
                            """,
                            (document_id, row[0], concept["relevance_score"]),
                        )
                except psycopg2.Error as exc:
                    logger.warning("Concept storage error: %s", exc)
                    continue
        try:
            self.db.conn.commit()
        except psycopg2.Error:
            self.db.conn.rollback()

    def _store_relationships(
        self, relationships: List[Dict], document_id: int,
    ) -> None:
        if not relationships:
            return
        name_to_id: Dict[str, int] = {}
        with self.db.conn.cursor() as cur:
            names = set()
            for rel in relationships:
                names.add(rel["source"])
                names.add(rel["target"])
            for name in names:
                cur.execute(
                    "SELECT entity_id FROM omnigraph.entities WHERE name = %s LIMIT 1",
                    (name,),
                )
                row = cur.fetchone()
                if row:
                    name_to_id[name] = row[0]

            for rel in relationships:
                source_id = name_to_id.get(rel["source"])
                target_id = name_to_id.get(rel["target"])
                if not source_id or not target_id or source_id == target_id:
                    continue
                try:
                    cur.execute(
                        """
                        INSERT INTO omnigraph.relations
                            (source_entity_id, target_entity_id, relation_type,
                             strength, source_document_id)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (source_id, target_id, rel["relation_type"],
                         rel["strength"], document_id),
                    )
                except psycopg2.Error as exc:
                    logger.warning("Relationship storage error: %s", exc)
                    continue
        try:
            self.db.conn.commit()
        except psycopg2.Error:
            self.db.conn.rollback()

    @staticmethod
    def _match_keywords(
        text: str, keywords: Set[str], entity_type: str,
    ) -> List[Dict]:
        if not text or not keywords:
            return []

        sorted_keywords = sorted(keywords, key=len, reverse=True)
        pattern = re.compile(
            "|".join(re.escape(k) for k in sorted_keywords),
            re.IGNORECASE,
        )

        match_positions: Dict[str, List[int]] = {}
        for m in pattern.finditer(text):
            matched_text = m.group(0)
            canonical = next(
                (k for k in keywords if k.lower() == matched_text.lower()),
                matched_text,
            )
            match_positions.setdefault(canonical, []).append(m.start())

        results: List[Dict] = []
        for keyword, positions in match_positions.items():
            count = len(positions)
            confidence = min(0.995, 0.700 + count * 0.05)
            results.append({
                "name": keyword,
                "entity_type": entity_type,
                "confidence": round(confidence, 3),
                "mention_count": count,
                "positions": positions,
            })
        return results

    @staticmethod
    def _extract_persons(text: str) -> List[Dict]:
        persons = []
        seen = {}
        for match in PERSON_PATTERN.finditer(text):
            name = match.group(1).strip()
            positions = seen.setdefault(name, [])
            positions.append(match.start())

        for name, positions in seen.items():
            count = len(positions)
            persons.append({
                "name": name,
                "entity_type": "person",
                "confidence": round(min(0.900, 0.600 + count * 0.1), 3),
                "mention_count": count,
                "positions": positions,
            })
        return persons

    @staticmethod
    def _fuzzy_match(candidate: str, known_names: Set[str]) -> Optional[str]:
        candidate_lower = candidate.lower().strip()
        if not candidate_lower or not known_names:
            return None

        lower_map = {name.lower(): name for name in known_names}
        if candidate_lower in lower_map:
            return lower_map[candidate_lower]

        for lower_name, original in lower_map.items():
            if lower_name in candidate_lower or candidate_lower in lower_name:
                return original
        return None

    @staticmethod
    def classify_entity(name: str) -> str:
        if name in TECHNOLOGY_KEYWORDS:
            return "technology"
        if name in ORGANIZATION_KEYWORDS:
            return "organization"
        if name in STANDARD_KEYWORDS:
            return "standard"
        return "other"


if __name__ == "__main__":
    sample_text = """
    Google has developed TensorFlow and BERT for machine learning and
    natural language processing research. Kubernetes, originally created
    by Google, depends on Docker for container orchestration. Microsoft
    Azure competes with AWS in cloud computing. The system uses OAuth 2.0
    for authentication and follows GDPR compliance standards.
    Dr. Sarah Lin leads the NLP research division.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    extractor = EntityRelationExtractor(db_connection=None)

    print("=== Entity Extraction ===")
    entities = extractor.extract_entities(sample_text)
    for e in entities:
        print(f"  [{e['entity_type']}] {e['name']} "
              f"(confidence={e['confidence']}, mentions={e['mention_count']})")

    print("\n=== Concept Extraction ===")
    concepts = extractor.extract_concepts(sample_text)
    for c in concepts:
        print(f"  [{c['domain']}] {c['name']} "
              f"(relevance={c['relevance_score']}, mentions={c['mention_count']})")

    print("\n=== Relationship Extraction ===")
    rels = extractor.extract_relationships(sample_text, entities)
    for r in rels:
        print(f"  {r['source']} --[{r['relation_type']}]--> {r['target']} "
              f"(strength={r['strength']})")
