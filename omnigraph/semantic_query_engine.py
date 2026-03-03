"""
OmniGraph: Enterprise AI Knowledge Graph Database System
========================================================
Module: Semantic Query Engine

Provides intelligent querying over the knowledge graph including
full-text search, vector similarity search, graph traversal,
relevance ranking, and composite multi-strategy queries.

Query Pipeline:
    user query → semantic parsing → vector similarity → graph traversal
    → ranking → filtered results

Author: OmniGraph Team
"""

import logging
import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import psycopg2

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("omnigraph.query_engine")


class SemanticQueryEngine:
    """
    Semantic query engine for the OmniGraph knowledge base.

    Capabilities:
    - Full-text search via PostgreSQL tsvector/tsquery
    - Vector similarity search (cosine similarity on embeddings)
    - Graph traversal (entity neighborhoods, relationship paths)
    - Multi-table join queries
    - Relevance ranking and result fusion
    - Query logging for audit
    """

    def __init__(self, db_connection, user_id: Optional[int] = None):
        """
        Parameters
        ----------
        db_connection : DatabaseConnection
            Active database connection.
        user_id : int, optional
            Current user ID for query logging.
        """
        self.db = db_connection
        self.user_id = user_id

    # ------------------------------------------------------------------
    # Main Search API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        strategy: str = "hybrid",
        limit: int = 10,
        sensitivity_filter: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Execute a search query using the specified strategy.

        Parameters
        ----------
        query : str
            User search query.
        strategy : str
            Search strategy: 'fulltext', 'semantic', 'graph', or 'hybrid'.
        limit : int
            Maximum results to return.
        sensitivity_filter : list of str, optional
            Filter by sensitivity levels (e.g., ['public', 'internal']).

        Returns
        -------
        list of dict
            Ranked search results.
        """
        start_time = time.time()
        results = []

        parsed = self.parse_query(query)

        if strategy == "fulltext":
            results = self.fulltext_search(query, limit, sensitivity_filter)
        elif strategy == "semantic":
            results = self.vector_similarity_search(query, limit)
        elif strategy == "graph":
            results = self.graph_traverse(parsed, limit)
        elif strategy == "hybrid":
            results = self._hybrid_search(query, parsed, limit, sensitivity_filter)
        else:
            logger.warning("Unknown strategy '%s', defaulting to hybrid.", strategy)
            results = self._hybrid_search(query, parsed, limit, sensitivity_filter)

        # Rank results
        results = self.rank_results(results)

        # Log query
        elapsed_ms = int((time.time() - start_time) * 1000)
        self._log_query(query, strategy, len(results), elapsed_ms)

        logger.info(
            "Search '%s' (%s): %d results in %dms.",
            query, strategy, len(results), elapsed_ms,
        )
        return results[:limit]

    # ------------------------------------------------------------------
    # Full-Text Search
    # ------------------------------------------------------------------

    def fulltext_search(
        self,
        query: str,
        limit: int = 10,
        sensitivity_filter: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Perform full-text search using PostgreSQL tsvector/tsquery.

        Parameters
        ----------
        query : str
            Search query (natural language).
        limit : int
            Max results.
        sensitivity_filter : list of str, optional
            Allowed sensitivity levels.

        Returns
        -------
        list of dict
            Matching documents with relevance scores.
        """
        cur = self.db.conn.cursor()
        try:
            sensitivity_clause = ""
            params: list = [query, query, limit]

            if sensitivity_filter:
                sensitivity_clause = "AND d.sensitivity_level = ANY(%s)"
                params = [query, query, sensitivity_filter, limit]

            sql = f"""
                SELECT
                    d.document_id,
                    d.title,
                    d.source_type,
                    d.sensitivity_level,
                    ts_rank(
                        to_tsvector('english', d.title || ' ' || d.content),
                        plainto_tsquery('english', %s)
                    ) AS search_rank,
                    LEFT(d.summary, 200) AS summary,
                    u.full_name AS author,
                    d.created_at
                FROM omnigraph.documents d
                JOIN omnigraph.users u ON u.user_id = d.uploaded_by
                WHERE to_tsvector('english', d.title || ' ' || d.content)
                      @@ plainto_tsquery('english', %s)
                  AND d.is_archived = FALSE
                  {sensitivity_clause}
                ORDER BY search_rank DESC
                LIMIT %s
            """
            cur.execute(sql, params)

            columns = ["document_id", "title", "source_type", "sensitivity_level",
                        "score", "summary", "author", "created_at"]
            results = []
            for row in cur.fetchall():
                result = dict(zip(columns, row))
                result["search_type"] = "fulltext"
                result["score"] = float(result["score"]) if result["score"] else 0.0
                results.append(result)

            return results

        except psycopg2.Error as exc:
            logger.error("Full-text search failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Vector Similarity Search
    # ------------------------------------------------------------------

    def vector_similarity_search(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict]:
        """
        Search using cosine similarity on stored embeddings.

        Since we store embeddings as FLOAT arrays (not using pgvector),
        this computes cosine similarity in SQL using array operations.

        Parameters
        ----------
        query : str
            Search query.
        limit : int
            Max results.

        Returns
        -------
        list of dict
            Documents ranked by vector similarity.
        """
        # Generate a simple query embedding (hash-based for demonstration)
        query_vector = self._generate_query_embedding(query)

        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                WITH query_vec AS (
                    SELECT %s::FLOAT[] AS vec
                ),
                similarities AS (
                    SELECT
                        e.source_id AS document_id,
                        e.vector,
                        -- Cosine similarity: dot(a,b) / (|a| * |b|)
                        (
                            SELECT SUM(a * b)
                            FROM UNNEST(e.vector, (SELECT vec FROM query_vec)) AS t(a, b)
                        ) / NULLIF(
                            SQRT(
                                (SELECT SUM(a * a) FROM UNNEST(e.vector) AS t(a))
                            ) * SQRT(
                                (SELECT SUM(b * b) FROM UNNEST((SELECT vec FROM query_vec)) AS t(b))
                            ), 0
                        ) AS cosine_similarity
                    FROM omnigraph.embeddings e
                    WHERE e.source_type = 'document'
                )
                SELECT
                    d.document_id,
                    d.title,
                    d.source_type,
                    d.sensitivity_level,
                    s.cosine_similarity AS score,
                    LEFT(d.summary, 200) AS summary,
                    u.full_name AS author,
                    d.created_at
                FROM similarities s
                JOIN omnigraph.documents d ON d.document_id = s.document_id
                JOIN omnigraph.users u ON u.user_id = d.uploaded_by
                WHERE s.cosine_similarity IS NOT NULL
                  AND d.is_archived = FALSE
                ORDER BY s.cosine_similarity DESC
                LIMIT %s
                """,
                (query_vector, limit),
            )

            columns = ["document_id", "title", "source_type", "sensitivity_level",
                        "score", "summary", "author", "created_at"]
            results = []
            for row in cur.fetchall():
                result = dict(zip(columns, row))
                result["search_type"] = "semantic"
                result["score"] = float(result["score"]) if result["score"] else 0.0
                results.append(result)

            return results

        except psycopg2.Error as exc:
            logger.error("Vector similarity search failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Graph Traversal
    # ------------------------------------------------------------------

    def graph_traverse(
        self,
        parsed_query: Dict,
        limit: int = 10,
    ) -> List[Dict]:
        """
        Traverse the knowledge graph to find related documents.

        Uses entity and concept associations to discover relevant documents
        through multi-hop relationships.

        Parameters
        ----------
        parsed_query : dict
            Parsed query with extracted terms and entities.
        limit : int
            Max results.

        Returns
        -------
        list of dict
            Documents found through graph traversal.
        """
        terms = parsed_query.get("terms", [])
        if not terms:
            return []

        cur = self.db.conn.cursor()
        try:
            # Find entities matching query terms
            term_pattern = "|".join(re.escape(t) for t in terms)
            cur.execute(
                """
                WITH matched_entities AS (
                    SELECT entity_id, name, entity_type
                    FROM omnigraph.entities
                    WHERE name ~* %s
                ),
                related_docs AS (
                    -- Direct document-entity links
                    SELECT
                        de.document_id,
                        de.relevance AS score,
                        'direct_entity_link' AS traversal_type
                    FROM matched_entities me
                    JOIN omnigraph.document_entities de ON de.entity_id = me.entity_id

                    UNION ALL

                    -- Documents via entity relationships (1 hop)
                    SELECT
                        de.document_id,
                        de.relevance * r.strength AS score,
                        'relationship_hop' AS traversal_type
                    FROM matched_entities me
                    JOIN omnigraph.relations r ON r.source_entity_id = me.entity_id
                    JOIN omnigraph.document_entities de ON de.entity_id = r.target_entity_id
                )
                SELECT
                    d.document_id,
                    d.title,
                    d.source_type,
                    d.sensitivity_level,
                    MAX(rd.score) AS score,
                    LEFT(d.summary, 200) AS summary,
                    u.full_name AS author,
                    d.created_at
                FROM related_docs rd
                JOIN omnigraph.documents d ON d.document_id = rd.document_id
                JOIN omnigraph.users u ON u.user_id = d.uploaded_by
                WHERE d.is_archived = FALSE
                GROUP BY d.document_id, d.title, d.source_type,
                         d.sensitivity_level, d.summary, u.full_name, d.created_at
                ORDER BY score DESC
                LIMIT %s
                """,
                (term_pattern, limit),
            )

            columns = ["document_id", "title", "source_type", "sensitivity_level",
                        "score", "summary", "author", "created_at"]
            results = []
            for row in cur.fetchall():
                result = dict(zip(columns, row))
                result["search_type"] = "graph"
                result["score"] = float(result["score"]) if result["score"] else 0.0
                results.append(result)

            return results

        except psycopg2.Error as exc:
            logger.error("Graph traversal failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Specialized Queries
    # ------------------------------------------------------------------

    def find_experts(self, concept_name: str, limit: int = 5) -> List[Dict]:
        """Find domain experts for a given concept."""
        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                SELECT
                    u.user_id,
                    u.full_name,
                    u.department,
                    u.title,
                    COUNT(DISTINCT d.document_id) AS doc_count,
                    ROUND(AVG(dc.relevance_score), 3) AS avg_relevance,
                    ROUND(COUNT(DISTINCT d.document_id)
                          * AVG(dc.relevance_score) * 10, 2) AS expertise_score
                FROM omnigraph.users u
                JOIN omnigraph.documents d ON d.uploaded_by = u.user_id
                JOIN omnigraph.document_concepts dc ON dc.document_id = d.document_id
                JOIN omnigraph.concepts c ON c.concept_id = dc.concept_id
                WHERE LOWER(c.name) = LOWER(%s)
                  AND u.is_active = TRUE
                GROUP BY u.user_id, u.full_name, u.department, u.title
                ORDER BY expertise_score DESC
                LIMIT %s
                """,
                (concept_name, limit),
            )

            columns = ["user_id", "full_name", "department", "title",
                        "doc_count", "avg_relevance", "expertise_score"]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

        except psycopg2.Error as exc:
            logger.error("Expert search failed: %s", exc)
            return []

    def find_related_concepts(self, concept_name: str) -> List[Dict]:
        """Find concepts related to the given concept through hierarchy and co-occurrence."""
        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                WITH target_concept AS (
                    SELECT concept_id FROM omnigraph.concepts
                    WHERE LOWER(name) = LOWER(%s) LIMIT 1
                ),
                -- Concepts from hierarchy
                hierarchy_related AS (
                    SELECT child_concept_id AS related_id, 'child' AS relation
                    FROM omnigraph.concept_hierarchy ch, target_concept tc
                    WHERE ch.parent_concept_id = tc.concept_id
                    UNION ALL
                    SELECT parent_concept_id, 'parent'
                    FROM omnigraph.concept_hierarchy ch, target_concept tc
                    WHERE ch.child_concept_id = tc.concept_id
                ),
                -- Concepts co-occurring in documents
                cooccurring AS (
                    SELECT dc2.concept_id AS related_id, 'co_occurrence' AS relation
                    FROM target_concept tc
                    JOIN omnigraph.document_concepts dc1 ON dc1.concept_id = tc.concept_id
                    JOIN omnigraph.document_concepts dc2
                        ON dc2.document_id = dc1.document_id
                        AND dc2.concept_id != tc.concept_id
                ),
                all_related AS (
                    SELECT related_id, relation FROM hierarchy_related
                    UNION ALL
                    SELECT related_id, relation FROM cooccurring
                )
                SELECT
                    c.name,
                    c.domain,
                    STRING_AGG(DISTINCT ar.relation, ', ') AS relationship_types,
                    COUNT(*) AS connection_strength
                FROM all_related ar
                JOIN omnigraph.concepts c ON c.concept_id = ar.related_id
                GROUP BY c.concept_id, c.name, c.domain
                ORDER BY connection_strength DESC
                """,
                (concept_name,),
            )

            columns = ["name", "domain", "relationship_types", "connection_strength"]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

        except psycopg2.Error as exc:
            logger.error("Related concepts search failed: %s", exc)
            return []

    def get_entity_documents(
        self,
        entity_name: str,
        limit: int = 10,
    ) -> List[Dict]:
        """Retrieve all documents associated with a specific entity."""
        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                SELECT
                    d.document_id,
                    d.title,
                    d.source_type,
                    de.relevance,
                    de.mention_count,
                    u.full_name AS author,
                    d.created_at
                FROM omnigraph.entities e
                JOIN omnigraph.document_entities de ON de.entity_id = e.entity_id
                JOIN omnigraph.documents d ON d.document_id = de.document_id
                JOIN omnigraph.users u ON u.user_id = d.uploaded_by
                WHERE LOWER(e.name) = LOWER(%s)
                  AND d.is_archived = FALSE
                ORDER BY de.relevance DESC
                LIMIT %s
                """,
                (entity_name, limit),
            )

            columns = ["document_id", "title", "source_type", "relevance",
                        "mention_count", "author", "created_at"]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

        except psycopg2.Error as exc:
            logger.error("Entity document search failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Query Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_query(query: str) -> Dict:
        """
        Parse a natural language query into structured components.

        Extracts search terms, potential entity references, and query intent.

        Parameters
        ----------
        query : str
            Raw user query.

        Returns
        -------
        dict
            {terms, entities_mentioned, intent, original_query}.
        """
        # Tokenize and clean
        stop_words = {
            "the", "a", "an", "in", "on", "at", "to", "for", "of",
            "and", "or", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did",
            "will", "would", "could", "should", "may", "might",
            "shall", "can", "with", "by", "from", "that", "this",
            "these", "those", "it", "its", "my", "your", "our",
            "find", "search", "show", "get", "list", "what",
            "how", "who", "where", "when", "which",
        }

        words = re.findall(r"\b\w+\b", query.lower())
        terms = [w for w in words if w not in stop_words and len(w) > 2]

        # Detect intent
        intent = "search"
        if any(w in query.lower() for w in ["expert", "who knows", "specialist"]):
            intent = "find_expert"
        elif any(w in query.lower() for w in ["related", "similar", "like"]):
            intent = "find_related"
        elif any(w in query.lower() for w in ["path", "connection", "between"]):
            intent = "find_path"
        elif any(w in query.lower() for w in ["trend", "history", "over time"]):
            intent = "analytics"

        return {
            "terms": terms,
            "intent": intent,
            "original_query": query,
        }

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    @staticmethod
    def rank_results(results: List[Dict]) -> List[Dict]:
        """
        Rank and deduplicate results from multiple search strategies.

        Combines scores from different search types with weighted fusion.
        """
        # Aggregate scores per document
        doc_scores: Dict[int, Dict] = {}

        weights = {
            "fulltext": 1.0,
            "semantic": 1.2,
            "graph": 0.8,
        }

        for result in results:
            doc_id = result.get("document_id")
            if doc_id is None:
                continue

            search_type = result.get("search_type", "fulltext")
            weight = weights.get(search_type, 1.0)
            weighted_score = result.get("score", 0.0) * weight

            if doc_id in doc_scores:
                doc_scores[doc_id]["score"] += weighted_score
                doc_scores[doc_id]["sources"].add(search_type)
            else:
                doc_scores[doc_id] = {
                    **result,
                    "score": weighted_score,
                    "sources": {search_type},
                }

        # Convert sources set to list and sort
        ranked = list(doc_scores.values())
        for r in ranked:
            r["sources"] = list(r.get("sources", []))
        ranked.sort(key=lambda x: x.get("score", 0), reverse=True)

        return ranked

    # ------------------------------------------------------------------
    # Hybrid Search
    # ------------------------------------------------------------------

    def _hybrid_search(
        self,
        query: str,
        parsed: Dict,
        limit: int,
        sensitivity_filter: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Combine fulltext, semantic, and graph search results."""
        all_results = []

        # Full-text search
        ft_results = self.fulltext_search(query, limit, sensitivity_filter)
        all_results.extend(ft_results)

        # Vector similarity
        vs_results = self.vector_similarity_search(query, limit)
        all_results.extend(vs_results)

        # Graph traversal
        gt_results = self.graph_traverse(parsed, limit)
        all_results.extend(gt_results)

        return all_results

    # ------------------------------------------------------------------
    # Query Logging
    # ------------------------------------------------------------------

    def _log_query(
        self,
        query_text: str,
        query_type: str,
        results_count: int,
        execution_ms: int,
    ) -> None:
        """Log the query for audit purposes."""
        if self.user_id is None:
            return

        # Map strategy to allowed query_type enum
        type_map = {
            "fulltext": "keyword_search",
            "semantic": "semantic_search",
            "graph": "graph_traversal",
            "hybrid": "semantic_search",
        }
        db_query_type = type_map.get(query_type, "keyword_search")

        try:
            cur = self.db.conn.cursor()
            cur.execute(
                """
                INSERT INTO omnigraph.query_logs
                    (user_id, query_text, query_type, results_count, execution_ms)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (self.user_id, query_text, db_query_type, results_count, execution_ms),
            )
            self.db.conn.commit()
        except psycopg2.Error as exc:
            logger.warning("Failed to log query: %s", exc)
            try:
                self.db.conn.rollback()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Embedding Generation (simplified)
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_query_embedding(query: str, dimensions: int = 8) -> List[float]:
        """
        Generate a simple deterministic embedding for a query string.

        In production, this would call an embedding API (e.g., OpenAI).
        Here we use a hash-based approach for demonstration.
        """
        import hashlib

        query_hash = hashlib.sha256(query.lower().encode()).hexdigest()
        vector = []
        for i in range(dimensions):
            hex_chunk = query_hash[i * 4:(i + 1) * 4]
            value = (int(hex_chunk, 16) / 65535.0) * 2 - 1  # normalize to [-1, 1]
            vector.append(round(value, 4))

        # Normalize to unit vector
        magnitude = math.sqrt(sum(v * v for v in vector))
        if magnitude > 0:
            vector = [round(v / magnitude, 4) for v in vector]

        return vector


# ---------------------------------------------------------------------------
# Module Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from ingestion_pipeline import DatabaseConnection

    db = DatabaseConnection()
    db.connect()

    engine = SemanticQueryEngine(db, user_id=8)

    # Full-text search
    print("=== Full-Text Search: 'machine learning' ===")
    results = engine.search("machine learning neural network", strategy="fulltext")
    for r in results:
        print(f"  [{r['score']:.3f}] {r['title']}")

    # Find experts
    print("\n=== Find Experts: 'Deep Learning' ===")
    experts = engine.find_experts("Deep Learning")
    for e in experts:
        print(f"  {e['full_name']} ({e['department']}) - "
              f"score={e['expertise_score']}")

    # Related concepts
    print("\n=== Related Concepts: 'Machine Learning' ===")
    related = engine.find_related_concepts("Machine Learning")
    for c in related:
        print(f"  {c['name']} [{c['domain']}] via {c['relationship_types']}")

    # Hybrid search
    print("\n=== Hybrid Search: 'kubernetes cloud deployment' ===")
    results = engine.search("kubernetes cloud deployment", strategy="hybrid")
    for r in results:
        print(f"  [{r['score']:.3f}] {r['title']} (via {r.get('sources', [])})")

    db.disconnect()
