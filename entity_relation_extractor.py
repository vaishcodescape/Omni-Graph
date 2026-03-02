"""
OmniGraph: Enterprise AI Knowledge Graph Database System
========================================================
Module: Entity & Relationship Extractor

Extracts named entities, concepts, and relationships from document text.
Uses pattern-based NER (regex + keyword dictionaries) for portability
without heavy ML framework dependencies.

Author: OmniGraph Team
"""

import logging
import re
from collections import Counter
from typing import Dict, List, Optional, Set, Tuple

import psycopg2

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("omnigraph.extractor")

# ---------------------------------------------------------------------------
# Entity Type Dictionaries
# ---------------------------------------------------------------------------
# These keyword lists serve as a lightweight NER approach.
# In production you would replace this with spaCy / Hugging Face models.

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

# Concept domain mapping
CONCEPT_DOMAINS = {
    "machine learning":     "AI",
    "deep learning":        "AI",
    "natural language processing": "AI",
    "computer vision":      "AI",
    "knowledge graph":      "AI",
    "neural network":       "AI",
    "transfer learning":    "AI",
    "reinforcement learning": "AI",
    "cybersecurity":        "Security",
    "zero trust":           "Security",
    "encryption":           "Security",
    "threat detection":     "Security",
    "cloud computing":      "Infrastructure",
    "containerization":     "Infrastructure",
    "microservices":        "Engineering",
    "api design":           "Engineering",
    "devops":               "Operations",
    "ci/cd":                "Operations",
    "data governance":      "Compliance",
    "compliance":           "Compliance",
    "predictive analytics": "Analytics",
    "supply chain":         "Business",
    "data pipeline":        "Engineering",
    "graph neural network": "AI",
    "federated learning":   "AI",
    "privacy":              "Compliance",
}

# Relationship patterns (regex-based)
RELATIONSHIP_PATTERNS = [
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


class EntityRelationExtractor:
    """
    Extracts entities, concepts, and relationships from document text.

    Methods
    -------
    extract_entities(text) -> list of dict
        Identify named entities in text.
    extract_concepts(text) -> list of dict
        Identify domain concepts in text.
    extract_relationships(text, entities) -> list of dict
        Identify typed relationships between entities.
    process_document(document_id) -> dict
        Full extraction pipeline for a stored document.
    """

    def __init__(self, db_connection):
        """
        Parameters
        ----------
        db_connection : DatabaseConnection
            Active database connection instance.
        """
        self.db = db_connection

    # ------------------------------------------------------------------
    # Entity Extraction
    # ------------------------------------------------------------------

    def extract_entities(self, text: str) -> List[Dict]:
        """
        Extract named entities from text using keyword matching.

        Parameters
        ----------
        text : str
            Document content.

        Returns
        -------
        list of dict
            Each dict: {name, entity_type, confidence, mention_count, positions}.
        """
        entities = []

        # Technology entities
        entities.extend(
            self._match_keywords(text, TECHNOLOGY_KEYWORDS, "technology")
        )
        # Organization entities
        entities.extend(
            self._match_keywords(text, ORGANIZATION_KEYWORDS, "organization")
        )
        # Standard entities
        entities.extend(
            self._match_keywords(text, STANDARD_KEYWORDS, "standard")
        )
        # Person entities (pattern-based)
        entities.extend(self._extract_persons(text))

        logger.info("Extracted %d entities from text.", len(entities))
        return entities

    def extract_concepts(self, text: str) -> List[Dict]:
        """
        Identify domain concepts mentioned in the text.

        Parameters
        ----------
        text : str
            Document content.

        Returns
        -------
        list of dict
            Each dict: {name, domain, relevance_score, mention_count}.
        """
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

        # Sort by relevance descending
        concepts.sort(key=lambda c: c["relevance_score"], reverse=True)
        logger.info("Extracted %d concepts from text.", len(concepts))
        return concepts

    def extract_relationships(
        self,
        text: str,
        entities: List[Dict],
    ) -> List[Dict]:
        """
        Extract typed relationships between entities from text.

        Parameters
        ----------
        text : str
            Document content.
        entities : list of dict
            Previously extracted entities.

        Returns
        -------
        list of dict
            Each dict: {source, target, relation_type, strength}.
        """
        relationships = []
        entity_names = {e["name"] for e in entities}

        for pattern, rel_type in RELATIONSHIP_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                source = match.group(1).strip()
                target = match.group(2).strip()

                # Validate that at least one entity is known
                source_match = self._fuzzy_match(source, entity_names)
                target_match = self._fuzzy_match(target, entity_names)

                if source_match and target_match and source_match != target_match:
                    relationships.append({
                        "source": source_match,
                        "target": target_match,
                        "relation_type": rel_type,
                        "strength": 0.750,
                    })

        # Deduplicate
        seen = set()
        unique = []
        for rel in relationships:
            key = (rel["source"], rel["target"], rel["relation_type"])
            if key not in seen:
                seen.add(key)
                unique.append(rel)

        logger.info("Extracted %d relationships from text.", len(unique))
        return unique

    # ------------------------------------------------------------------
    # Full Pipeline
    # ------------------------------------------------------------------

    def process_document(self, document_id: int) -> Dict:
        """
        Run the full extraction pipeline on a stored document.

        Parameters
        ----------
        document_id : int
            ID of the document to process.

        Returns
        -------
        dict
            {entities: [...], concepts: [...], relationships: [...]}.
        """
        # Fetch document content
        cur = self.db.conn.cursor()
        cur.execute(
            "SELECT content FROM omnigraph.documents WHERE document_id = %s",
            (document_id,),
        )
        row = cur.fetchone()
        if not row:
            logger.error("Document %d not found.", document_id)
            return {"entities": [], "concepts": [], "relationships": []}

        content = row[0]

        # Extract
        entities = self.extract_entities(content)
        concepts = self.extract_concepts(content)
        relationships = self.extract_relationships(content, entities)

        # Persist entities
        self._store_entities(entities, document_id)
        # Persist concepts
        self._store_concepts(concepts, document_id)
        # Persist relationships
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

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _store_entities(self, entities: List[Dict], document_id: int) -> None:
        """Store extracted entities and link them to the document."""
        cur = self.db.conn.cursor()
        for entity in entities:
            try:
                # Upsert entity
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
                entity_id = cur.fetchone()[0]

                # Link to document
                cur.execute(
                    """
                    INSERT INTO omnigraph.document_entities
                        (document_id, entity_id, relevance, mention_count)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (document_id, entity_id) DO UPDATE
                        SET mention_count = EXCLUDED.mention_count,
                            relevance = EXCLUDED.relevance
                    """,
                    (
                        document_id, entity_id,
                        entity["confidence"],
                        entity["mention_count"],
                    ),
                )
            except psycopg2.Error as exc:
                logger.warning("Entity storage error: %s", exc)
                self.db.conn.rollback()
                continue

        try:
            self.db.conn.commit()
        except psycopg2.Error:
            self.db.conn.rollback()

    def _store_concepts(self, concepts: List[Dict], document_id: int) -> None:
        """Store extracted concepts and link them to the document."""
        cur = self.db.conn.cursor()
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
                    concept_id = row[0]
                    cur.execute(
                        """
                        INSERT INTO omnigraph.document_concepts
                            (document_id, concept_id, relevance_score, extracted_by)
                        VALUES (%s, %s, %s, 'system')
                        ON CONFLICT (document_id, concept_id) DO UPDATE
                            SET relevance_score = EXCLUDED.relevance_score
                        """,
                        (document_id, concept_id, concept["relevance_score"]),
                    )
            except psycopg2.Error as exc:
                logger.warning("Concept storage error: %s", exc)
                self.db.conn.rollback()
                continue

        try:
            self.db.conn.commit()
        except psycopg2.Error:
            self.db.conn.rollback()

    def _store_relationships(
        self, relationships: List[Dict], document_id: int,
    ) -> None:
        """Store extracted relationships."""
        cur = self.db.conn.cursor()
        for rel in relationships:
            try:
                # Look up entity IDs
                cur.execute(
                    "SELECT entity_id FROM omnigraph.entities WHERE name = %s LIMIT 1",
                    (rel["source"],),
                )
                source_row = cur.fetchone()

                cur.execute(
                    "SELECT entity_id FROM omnigraph.entities WHERE name = %s LIMIT 1",
                    (rel["target"],),
                )
                target_row = cur.fetchone()

                if source_row and target_row:
                    source_id = source_row[0]
                    target_id = target_row[0]
                    if source_id != target_id:
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
                self.db.conn.rollback()
                continue

        try:
            self.db.conn.commit()
        except psycopg2.Error:
            self.db.conn.rollback()

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _match_keywords(
        text: str,
        keywords: Set[str],
        entity_type: str,
    ) -> List[Dict]:
        """Match keyword-based entities in text."""
        results = []
        for keyword in keywords:
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            matches = pattern.findall(text)
            if matches:
                positions = [m.start() for m in pattern.finditer(text)]
                confidence = min(0.995, 0.700 + len(matches) * 0.05)
                results.append({
                    "name": keyword,
                    "entity_type": entity_type,
                    "confidence": round(confidence, 3),
                    "mention_count": len(matches),
                    "positions": positions,
                })
        return results

    @staticmethod
    def _extract_persons(text: str) -> List[Dict]:
        """
        Extract person names using common name patterns.

        Matches patterns like: Dr. FirstName LastName, Prof. FirstName LastName,
        or capitalized two-word sequences that look like names.
        """
        patterns = [
            r"\b((?:Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.)\s+[A-Z][a-z]+\s+[A-Z][a-z]+)\b",
        ]
        persons = []
        seen = set()

        for pat in patterns:
            for match in re.finditer(pat, text):
                name = match.group(1).strip()
                if name not in seen:
                    seen.add(name)
                    count = text.count(name)
                    persons.append({
                        "name": name,
                        "entity_type": "person",
                        "confidence": round(min(0.900, 0.600 + count * 0.1), 3),
                        "mention_count": count,
                        "positions": [match.start()],
                    })

        return persons

    @staticmethod
    def _fuzzy_match(candidate: str, known_names: Set[str]) -> Optional[str]:
        """Case-insensitive match of candidate against known entity names."""
        candidate_lower = candidate.lower().strip()
        for name in known_names:
            if name.lower() == candidate_lower:
                return name
        # Partial match
        for name in known_names:
            if name.lower() in candidate_lower or candidate_lower in name.lower():
                return name
        return None

    # ------------------------------------------------------------------
    # Classification Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def classify_entity(name: str) -> str:
        """
        Classify an entity name into a type based on keyword dictionaries.

        Parameters
        ----------
        name : str
            Entity name to classify.

        Returns
        -------
        str
            One of: 'technology', 'organization', 'standard', 'other'.
        """
        if name in TECHNOLOGY_KEYWORDS:
            return "technology"
        if name in ORGANIZATION_KEYWORDS:
            return "organization"
        if name in STANDARD_KEYWORDS:
            return "standard"
        return "other"


# ---------------------------------------------------------------------------
# Module Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    sample_text = """
    Google has developed TensorFlow and BERT for machine learning and
    natural language processing research. Kubernetes, originally created
    by Google, depends on Docker for container orchestration. Microsoft
    Azure competes with AWS in cloud computing. The system uses OAuth 2.0
    for authentication and follows GDPR compliance standards.
    Dr. Sarah Lin leads the NLP research division.
    """

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
