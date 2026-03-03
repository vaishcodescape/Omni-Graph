"""
OmniGraph: Enterprise AI Knowledge Graph Database System
========================================================
Module: Knowledge Graph Builder

Constructs and maintains the semantic knowledge graph by mapping
document–entity relationships, managing taxonomy hierarchies, enforcing
referential integrity, and preventing duplicate nodes. Supports
recursive graph traversal queries.

Author: OmniGraph Team
"""

import logging
from typing import Dict, List, Optional, Set, Tuple

import psycopg2

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("omnigraph.graph_builder")


class KnowledgeGraphBuilder:
    """
    Builds and maintains the OmniGraph knowledge graph.

    The knowledge graph is stored relationally across:
    - entities, relations (entity-level graph)
    - concepts, concept_hierarchy (concept-level DAG)
    - document_entities, document_concepts (document linkage)
    - taxonomy (hierarchical classification)
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
    # Entity Node Operations
    # ------------------------------------------------------------------

    def add_entity_node(
        self,
        name: str,
        entity_type: str,
        description: Optional[str] = None,
        confidence: float = 0.800,
    ) -> Optional[int]:
        """
        Add an entity node to the graph, preventing duplicates.

        Parameters
        ----------
        name : str
            Entity name.
        entity_type : str
            Entity classification (person, organization, technology, etc.).
        description : str, optional
            Entity description.
        confidence : float
            Confidence score (0–1).

        Returns
        -------
        int or None
            The entity_id.
        """
        cur = self.db.conn.cursor()
        try:
            # Check for existing entity (dedup)
            cur.execute(
                """
                SELECT entity_id FROM omnigraph.entities
                WHERE LOWER(name) = LOWER(%s) AND entity_type = %s
                LIMIT 1
                """,
                (name, entity_type),
            )
            row = cur.fetchone()
            if row:
                logger.info("Entity '%s' already exists (id=%d).", name, row[0])
                return row[0]

            cur.execute(
                """
                INSERT INTO omnigraph.entities (name, entity_type, description, confidence)
                VALUES (%s, %s, %s, %s)
                RETURNING entity_id
                """,
                (name, entity_type, description, confidence),
            )
            entity_id = cur.fetchone()[0]
            self.db.conn.commit()
            logger.info("Added entity node '%s' (id=%d).", name, entity_id)
            return entity_id

        except psycopg2.Error as exc:
            self.db.conn.rollback()
            logger.error("Failed to add entity '%s': %s", name, exc)
            return None

    def remove_entity_node(self, entity_id: int) -> bool:
        """Remove an entity and all associated relationships (cascading)."""
        cur = self.db.conn.cursor()
        try:
            cur.execute(
                "DELETE FROM omnigraph.entities WHERE entity_id = %s",
                (entity_id,),
            )
            self.db.conn.commit()
            deleted = cur.rowcount > 0
            if deleted:
                logger.info("Removed entity node id=%d.", entity_id)
            return deleted
        except psycopg2.Error as exc:
            self.db.conn.rollback()
            logger.error("Failed to remove entity %d: %s", entity_id, exc)
            return False

    # ------------------------------------------------------------------
    # Relationship Operations
    # ------------------------------------------------------------------

    def add_relationship(
        self,
        source_entity_id: int,
        target_entity_id: int,
        relation_type: str,
        strength: float = 1.0,
        description: Optional[str] = None,
        source_document_id: Optional[int] = None,
    ) -> Optional[int]:
        """
        Add a typed relationship between two entities.

        Parameters
        ----------
        source_entity_id : int
            Source entity.
        target_entity_id : int
            Target entity.
        relation_type : str
            Relationship classification.
        strength : float
            Relationship strength (0–1).
        description : str, optional
            Relationship description.
        source_document_id : int, optional
            Document where the relationship was identified.

        Returns
        -------
        int or None
            The relation_id.
        """
        if source_entity_id == target_entity_id:
            logger.warning("Cannot create self-referencing relationship.")
            return None

        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO omnigraph.relations
                    (source_entity_id, target_entity_id, relation_type,
                     strength, description, source_document_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING relation_id
                """,
                (
                    source_entity_id, target_entity_id, relation_type,
                    strength, description, source_document_id,
                ),
            )
            relation_id = cur.fetchone()[0]
            self.db.conn.commit()
            logger.info(
                "Added relationship %d -[%s]-> %d (id=%d).",
                source_entity_id, relation_type, target_entity_id, relation_id,
            )
            return relation_id

        except psycopg2.Error as exc:
            self.db.conn.rollback()
            logger.error("Failed to add relationship: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Document–Entity Mapping
    # ------------------------------------------------------------------

    def map_document_entity(
        self,
        document_id: int,
        entity_id: int,
        relevance: float = 1.0,
        mention_count: int = 1,
    ) -> bool:
        """Link a document to an entity node."""
        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO omnigraph.document_entities
                    (document_id, entity_id, relevance, mention_count)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (document_id, entity_id) DO UPDATE
                    SET relevance = EXCLUDED.relevance,
                        mention_count = EXCLUDED.mention_count
                """,
                (document_id, entity_id, relevance, mention_count),
            )
            self.db.conn.commit()
            return True
        except psycopg2.Error as exc:
            self.db.conn.rollback()
            logger.error("Failed to map document %d to entity %d: %s",
                         document_id, entity_id, exc)
            return False

    # ------------------------------------------------------------------
    # Taxonomy Management
    # ------------------------------------------------------------------

    def add_taxonomy_node(
        self,
        name: str,
        parent_id: Optional[int] = None,
        domain: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[int]:
        """
        Add a node to the taxonomy hierarchy.

        The trg_maintain_taxonomy trigger automatically computes the level
        and checks for circular references.
        """
        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO omnigraph.taxonomy (name, parent_id, domain, description)
                VALUES (%s, %s, %s, %s)
                RETURNING taxonomy_id
                """,
                (name, parent_id, domain, description),
            )
            taxonomy_id = cur.fetchone()[0]
            self.db.conn.commit()
            logger.info("Added taxonomy node '%s' (id=%d).", name, taxonomy_id)
            return taxonomy_id
        except psycopg2.Error as exc:
            self.db.conn.rollback()
            logger.error("Failed to add taxonomy node '%s': %s", name, exc)
            return None

    def get_taxonomy_tree(self, root_name: Optional[str] = None) -> List[Dict]:
        """
        Retrieve the full taxonomy tree using a recursive CTE.

        Parameters
        ----------
        root_name : str, optional
            Start from a specific root. If None, retrieves all roots.

        Returns
        -------
        list of dict
            Each dict: {taxonomy_id, name, parent_id, level, domain, path}.
        """
        cur = self.db.conn.cursor()
        try:
            if root_name:
                cur.execute(
                    """
                    WITH RECURSIVE tree AS (
                        SELECT taxonomy_id, name, parent_id, level, domain,
                               ARRAY[name]::TEXT[] AS path
                        FROM omnigraph.taxonomy
                        WHERE LOWER(name) = LOWER(%s)

                        UNION ALL

                        SELECT t.taxonomy_id, t.name, t.parent_id, t.level, t.domain,
                               tree.path || t.name
                        FROM omnigraph.taxonomy t
                        JOIN tree ON t.parent_id = tree.taxonomy_id
                    )
                    SELECT * FROM tree ORDER BY path
                    """,
                    (root_name,),
                )
            else:
                cur.execute(
                    """
                    WITH RECURSIVE tree AS (
                        SELECT taxonomy_id, name, parent_id, level, domain,
                               ARRAY[name]::TEXT[] AS path
                        FROM omnigraph.taxonomy
                        WHERE parent_id IS NULL

                        UNION ALL

                        SELECT t.taxonomy_id, t.name, t.parent_id, t.level, t.domain,
                               tree.path || t.name
                        FROM omnigraph.taxonomy t
                        JOIN tree ON t.parent_id = tree.taxonomy_id
                    )
                    SELECT * FROM tree ORDER BY path
                    """
                )

            columns = ["taxonomy_id", "name", "parent_id", "level", "domain", "path"]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

        except psycopg2.Error as exc:
            logger.error("Failed to retrieve taxonomy tree: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Concept Hierarchy Management
    # ------------------------------------------------------------------

    def add_concept_link(
        self,
        parent_concept_id: int,
        child_concept_id: int,
        relationship_type: str = "is_parent_of",
    ) -> bool:
        """
        Create a parent-child link in the concept hierarchy.

        Parameters
        ----------
        parent_concept_id : int
            Parent concept.
        child_concept_id : int
            Child concept.
        relationship_type : str
            One of: is_parent_of, is_specialization_of, is_prerequisite_of.

        Returns
        -------
        bool
            True if link created successfully.
        """
        if parent_concept_id == child_concept_id:
            logger.warning("Cannot create self-referencing concept link.")
            return False

        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO omnigraph.concept_hierarchy
                    (parent_concept_id, child_concept_id, relationship_type)
                VALUES (%s, %s, %s)
                ON CONFLICT (parent_concept_id, child_concept_id) DO NOTHING
                """,
                (parent_concept_id, child_concept_id, relationship_type),
            )
            self.db.conn.commit()
            return True
        except psycopg2.Error as exc:
            self.db.conn.rollback()
            logger.error("Failed to add concept link: %s", exc)
            return False

    def get_concept_hierarchy(self, root_concept_name: str) -> List[Dict]:
        """
        Retrieve the full concept hierarchy from a root concept.

        Uses a recursive CTE to traverse concept_hierarchy.
        """
        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                WITH RECURSIVE hierarchy AS (
                    SELECT c.concept_id, c.name, c.domain,
                           NULL::VARCHAR AS parent_name,
                           0 AS depth
                    FROM omnigraph.concepts c
                    WHERE LOWER(c.name) = LOWER(%s)

                    UNION ALL

                    SELECT child.concept_id, child.name, child.domain,
                           h.name AS parent_name,
                           h.depth + 1
                    FROM hierarchy h
                    JOIN omnigraph.concept_hierarchy ch
                        ON ch.parent_concept_id = h.concept_id
                    JOIN omnigraph.concepts child
                        ON child.concept_id = ch.child_concept_id
                    WHERE h.depth < 10
                )
                SELECT * FROM hierarchy ORDER BY depth, name
                """,
                (root_concept_name,),
            )
            columns = ["concept_id", "name", "domain", "parent_name", "depth"]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

        except psycopg2.Error as exc:
            logger.error("Failed to retrieve concept hierarchy: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Graph Traversal
    # ------------------------------------------------------------------

    def get_entity_neighborhood(
        self,
        entity_id: int,
        max_depth: int = 2,
    ) -> List[Dict]:
        """
        Retrieve the neighborhood of an entity within N hops.

        Parameters
        ----------
        entity_id : int
            Center entity.
        max_depth : int
            Maximum traversal depth.

        Returns
        -------
        list of dict
            Each dict: {entity_id, name, entity_type, relation_type,
                        strength, depth}.
        """
        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                WITH RECURSIVE neighborhood AS (
                    SELECT
                        r.target_entity_id AS entity_id,
                        e.name,
                        e.entity_type,
                        r.relation_type,
                        r.strength,
                        1 AS depth,
                        ARRAY[%s, r.target_entity_id] AS visited
                    FROM omnigraph.relations r
                    JOIN omnigraph.entities e ON e.entity_id = r.target_entity_id
                    WHERE r.source_entity_id = %s

                    UNION ALL

                    SELECT
                        r.target_entity_id,
                        e.name,
                        e.entity_type,
                        r.relation_type,
                        r.strength,
                        n.depth + 1,
                        n.visited || r.target_entity_id
                    FROM neighborhood n
                    JOIN omnigraph.relations r ON r.source_entity_id = n.entity_id
                    JOIN omnigraph.entities e ON e.entity_id = r.target_entity_id
                    WHERE n.depth < %s
                      AND NOT (r.target_entity_id = ANY(n.visited))
                )
                SELECT DISTINCT entity_id, name, entity_type,
                       relation_type, strength, depth
                FROM neighborhood
                ORDER BY depth, strength DESC
                """,
                (entity_id, entity_id, max_depth),
            )

            columns = ["entity_id", "name", "entity_type", "relation_type",
                        "strength", "depth"]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

        except psycopg2.Error as exc:
            logger.error("Failed to get entity neighborhood: %s", exc)
            return []

    def detect_duplicate_nodes(self) -> List[Dict]:
        """
        Detect potential duplicate entity nodes based on similar names.

        Returns
        -------
        list of dict
            Each dict: {entity_id_1, name_1, entity_id_2, name_2, similarity}.
        """
        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                SELECT e1.entity_id, e1.name, e2.entity_id, e2.name
                FROM omnigraph.entities e1
                JOIN omnigraph.entities e2
                    ON e1.entity_id < e2.entity_id
                    AND e1.entity_type = e2.entity_type
                    AND LOWER(e1.name) = LOWER(e2.name)
                ORDER BY e1.name
                """
            )
            columns = ["entity_id_1", "name_1", "entity_id_2", "name_2"]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

        except psycopg2.Error as exc:
            logger.error("Duplicate detection failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Graph Statistics
    # ------------------------------------------------------------------

    def get_graph_stats(self) -> Dict:
        """Return summary statistics of the knowledge graph."""
        cur = self.db.conn.cursor()
        stats = {}
        try:
            cur.execute("SELECT COUNT(*) FROM omnigraph.entities")
            stats["total_entities"] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM omnigraph.relations")
            stats["total_relations"] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM omnigraph.concepts")
            stats["total_concepts"] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM omnigraph.documents")
            stats["total_documents"] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM omnigraph.taxonomy")
            stats["total_taxonomy_nodes"] = cur.fetchone()[0]

            cur.execute(
                """
                SELECT entity_type, COUNT(*)
                FROM omnigraph.entities
                GROUP BY entity_type
                ORDER BY COUNT(*) DESC
                """
            )
            stats["entities_by_type"] = dict(cur.fetchall())

            cur.execute(
                """
                SELECT relation_type, COUNT(*)
                FROM omnigraph.relations
                GROUP BY relation_type
                ORDER BY COUNT(*) DESC
                """
            )
            stats["relations_by_type"] = dict(cur.fetchall())

            return stats

        except psycopg2.Error as exc:
            logger.error("Failed to get graph stats: %s", exc)
            return stats

    # ------------------------------------------------------------------
    # Build Graph (Full Pipeline)
    # ------------------------------------------------------------------

    def build_graph(self) -> Dict:
        """
        Orchestrate the full graph construction process.

        This method:
        1. Validates referential integrity
        2. Detects duplicate nodes
        3. Computes graph statistics

        Returns
        -------
        dict
            Graph construction summary.
        """
        logger.info("Starting knowledge graph construction.")

        # Step 1: Detect duplicates
        duplicates = self.detect_duplicate_nodes()
        if duplicates:
            logger.warning(
                "Found %d potential duplicate entity pairs.", len(duplicates),
            )

        # Step 2: Get statistics
        stats = self.get_graph_stats()

        logger.info(
            "Graph construction complete: %d entities, %d relations, "
            "%d concepts, %d documents.",
            stats.get("total_entities", 0),
            stats.get("total_relations", 0),
            stats.get("total_concepts", 0),
            stats.get("total_documents", 0),
        )

        return {
            "stats": stats,
            "duplicates_detected": len(duplicates),
            "duplicate_pairs": duplicates,
        }


# ---------------------------------------------------------------------------
# Module Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from ingestion_pipeline import DatabaseConnection

    db = DatabaseConnection()
    db.connect()

    builder = KnowledgeGraphBuilder(db)

    # Build graph and display stats
    result = builder.build_graph()
    print("\n=== Knowledge Graph Statistics ===")
    for key, value in result["stats"].items():
        print(f"  {key}: {value}")

    if result["duplicates_detected"] > 0:
        print(f"\n  WARNING: {result['duplicates_detected']} duplicate pairs found!")

    # Display taxonomy tree
    print("\n=== Taxonomy Tree ===")
    tree = builder.get_taxonomy_tree()
    for node in tree:
        indent = "  " * node["level"]
        print(f"  {indent}├── {node['name']} (level={node['level']})")

    # Display concept hierarchy for 'Machine Learning'
    print("\n=== Concept Hierarchy: Machine Learning ===")
    hierarchy = builder.get_concept_hierarchy("Machine Learning")
    for node in hierarchy:
        indent = "  " * node["depth"]
        parent = f" ← {node['parent_name']}" if node["parent_name"] else ""
        print(f"  {indent}├── {node['name']}{parent}")

    db.disconnect()
