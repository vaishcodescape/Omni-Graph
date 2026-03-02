-- ============================================================================
-- OmniGraph: Enterprise AI Knowledge Graph Database System
-- Advanced Query Set (15 Queries)
-- ============================================================================
-- Demonstrates: multi-table JOINs, aggregation, recursive CTEs,
-- window functions, subqueries, full-text search
-- ============================================================================

SET search_path TO omnigraph;

-- ============================================================================
-- QUERY 1: Find Experts on a Topic
-- Identifies users who have contributed documents related to a specific
-- concept, ranked by number of contributions and average relevance.
-- Demonstrates: Multi-table JOIN, GROUP BY, ORDER BY, aggregate functions
-- ============================================================================
SELECT
    u.full_name,
    u.department,
    u.title,
    COUNT(DISTINCT d.document_id) AS documents_contributed,
    ROUND(AVG(dc.relevance_score), 3) AS avg_concept_relevance,
    ROUND(COUNT(DISTINCT d.document_id) * AVG(dc.relevance_score) * 10, 2) AS expertise_score
FROM users u
JOIN documents d ON d.uploaded_by = u.user_id
JOIN document_concepts dc ON dc.document_id = d.document_id
JOIN concepts c ON c.concept_id = dc.concept_id
WHERE c.name = 'Deep Learning'
  AND u.is_active = TRUE
GROUP BY u.user_id, u.full_name, u.department, u.title
ORDER BY expertise_score DESC;

-- ============================================================================
-- QUERY 2: Retrieve Documents Related to a Concept (with Tags)
-- Finds all documents associated with a concept and their tags.
-- Demonstrates: Multi-table JOIN, STRING_AGG aggregation
-- ============================================================================
SELECT
    d.document_id,
    d.title,
    d.source_type,
    d.sensitivity_level,
    dc.relevance_score,
    u.full_name AS uploaded_by,
    STRING_AGG(DISTINCT t.name, ', ' ORDER BY t.name) AS tags
FROM documents d
JOIN document_concepts dc ON dc.document_id = d.document_id
JOIN concepts c ON c.concept_id = dc.concept_id
JOIN users u ON u.user_id = d.uploaded_by
LEFT JOIN document_tags dt ON dt.document_id = d.document_id
LEFT JOIN tags t ON t.tag_id = dt.tag_id
WHERE c.name = 'Machine Learning'
  AND d.is_archived = FALSE
GROUP BY d.document_id, d.title, d.source_type, d.sensitivity_level,
         dc.relevance_score, u.full_name
ORDER BY dc.relevance_score DESC;

-- ============================================================================
-- QUERY 3: Discover Related Entities Through Relationships
-- Given an entity, find all entities connected within 2 hops.
-- Demonstrates: Recursive CTE, self-referencing traversal, cycle prevention
-- ============================================================================
WITH RECURSIVE entity_network AS (
    -- Base: direct relationships from the source entity
    SELECT
        r.target_entity_id AS entity_id,
        e.name AS entity_name,
        e.entity_type,
        r.relation_type,
        r.strength,
        1 AS hop_distance,
        ARRAY[r.source_entity_id, r.target_entity_id] AS visited
    FROM relations r
    JOIN entities e ON e.entity_id = r.target_entity_id
    WHERE r.source_entity_id = (SELECT entity_id FROM entities WHERE name = 'Kubernetes' LIMIT 1)

    UNION ALL

    -- Recursive: follow outgoing edges
    SELECT
        r.target_entity_id,
        e.name,
        e.entity_type,
        r.relation_type,
        r.strength,
        en.hop_distance + 1,
        en.visited || r.target_entity_id
    FROM entity_network en
    JOIN relations r ON r.source_entity_id = en.entity_id
    JOIN entities e ON e.entity_id = r.target_entity_id
    WHERE en.hop_distance < 2
      AND NOT (r.target_entity_id = ANY(en.visited))
)
SELECT DISTINCT
    entity_name,
    entity_type,
    relation_type,
    strength,
    hop_distance
FROM entity_network
ORDER BY hop_distance, strength DESC;

-- ============================================================================
-- QUERY 4: List Documents by Taxonomy Hierarchy (Recursive CTE)
-- Traverses the taxonomy tree and lists all documents under a taxonomy
-- branch including all sub-categories.
-- Demonstrates: Recursive CTE on self-referencing table, LEFT JOIN
-- ============================================================================
WITH RECURSIVE taxonomy_tree AS (
    -- Base: root taxonomy node
    SELECT taxonomy_id, name, parent_id, level, domain
    FROM taxonomy
    WHERE name = 'Technology'

    UNION ALL

    -- Children
    SELECT t.taxonomy_id, t.name, t.parent_id, t.level, t.domain
    FROM taxonomy t
    JOIN taxonomy_tree tt ON t.parent_id = tt.taxonomy_id
)
SELECT
    tt.name AS taxonomy_category,
    tt.level AS taxonomy_level,
    d.document_id,
    d.title,
    d.source_type,
    d.sensitivity_level,
    d.created_at
FROM taxonomy_tree tt
LEFT JOIN documents d ON d.taxonomy_id = tt.taxonomy_id
ORDER BY tt.level, tt.name, d.created_at DESC;

-- ============================================================================
-- QUERY 5: Identify Most Referenced Concepts
-- Ranks concepts by how many documents reference them and how many
-- entities are associated with them.
-- Demonstrates: LEFT JOIN, GROUP BY, COALESCE, multiple aggregations
-- ============================================================================
SELECT
    c.name AS concept_name,
    c.domain,
    COUNT(DISTINCT dc.document_id) AS document_count,
    COUNT(DISTINCT ec.entity_id) AS entity_count,
    c.relevance_score,
    RANK() OVER (ORDER BY COUNT(DISTINCT dc.document_id) DESC) AS popularity_rank
FROM concepts c
LEFT JOIN document_concepts dc ON dc.concept_id = c.concept_id
LEFT JOIN entity_concepts ec ON ec.concept_id = c.concept_id
GROUP BY c.concept_id, c.name, c.domain, c.relevance_score
ORDER BY document_count DESC, entity_count DESC;

-- ============================================================================
-- QUERY 6: Detect Sensitive Document Access History
-- Lists all access events for confidential and restricted documents,
-- showing who accessed what and when.
-- Demonstrates: Multi-table JOIN, IN subquery, date filtering
-- ============================================================================
SELECT
    al.created_at AS access_time,
    u.full_name AS accessed_by,
    u.department,
    STRING_AGG(DISTINCT r.role_name, ', ') AS user_roles,
    al.action,
    d.title AS document_title,
    d.sensitivity_level,
    al.details,
    al.ip_address
FROM audit_logs al
JOIN users u ON u.user_id = al.user_id
JOIN documents d ON d.document_id = al.resource_id
LEFT JOIN user_roles ur ON ur.user_id = al.user_id
LEFT JOIN roles r ON r.role_id = ur.role_id
WHERE al.resource_type = 'document'
  AND d.sensitivity_level IN ('confidential', 'restricted')
  AND al.action IN ('view', 'export', 'update')
GROUP BY al.audit_id, al.created_at, u.full_name, u.department,
         al.action, d.title, d.sensitivity_level, al.details, al.ip_address
ORDER BY al.created_at DESC;

-- ============================================================================
-- QUERY 7: Knowledge Usage Trends by Year
-- Analyzes document creation and query patterns over time.
-- Demonstrates: DATE_TRUNC, GROUP BY with date functions, window functions
-- ============================================================================
SELECT
    DATE_TRUNC('month', d.created_at)::DATE AS month,
    d.source_type,
    COUNT(*) AS documents_created,
    SUM(COUNT(*)) OVER (
        PARTITION BY d.source_type
        ORDER BY DATE_TRUNC('month', d.created_at)
    ) AS cumulative_count,
    ROUND(AVG(d.file_size_bytes) / 1000000.0, 2) AS avg_size_mb
FROM documents d
GROUP BY DATE_TRUNC('month', d.created_at), d.source_type
ORDER BY month DESC, documents_created DESC;

-- ============================================================================
-- QUERY 8: Shortest Relationship Path Between Entities (Recursive CTE)
-- Finds the shortest path between two entities through the relationship
-- graph using breadth-first search.
-- Demonstrates: Recursive CTE with path tracking, array operations
-- ============================================================================
WITH RECURSIVE paths AS (
    -- Base: start from source entity (TensorFlow, id=5)
    SELECT
        r.target_entity_id AS current_id,
        ARRAY[es.name, et.name] AS path_names,
        ARRAY[r.relation_type] AS path_relations,
        1 AS depth
    FROM relations r
    JOIN entities es ON es.entity_id = r.source_entity_id
    JOIN entities et ON et.entity_id = r.target_entity_id
    WHERE r.source_entity_id = 5  -- TensorFlow

    UNION ALL

    -- Recursive step
    SELECT
        r.target_entity_id,
        p.path_names || et.name,
        p.path_relations || r.relation_type,
        p.depth + 1
    FROM paths p
    JOIN relations r ON r.source_entity_id = p.current_id
    JOIN entities et ON et.entity_id = r.target_entity_id
    WHERE p.depth < 5
      AND NOT (et.name = ANY(p.path_names))
)
SELECT
    depth AS path_length,
    path_names,
    path_relations
FROM paths
WHERE current_id = 4  -- Kubernetes
ORDER BY depth ASC
LIMIT 5;

-- ============================================================================
-- QUERY 9: Top Contributors by Document Count and Impact
-- Ranks users by their contributions, weighted by document sensitivity
-- and concept associations.
-- Demonstrates: CASE expression, multiple JOINs, window function (RANK)
-- ============================================================================
SELECT
    u.full_name,
    u.department,
    COUNT(DISTINCT d.document_id) AS total_documents,
    COUNT(DISTINCT dc.concept_id) AS concepts_covered,
    SUM(CASE d.sensitivity_level
        WHEN 'restricted' THEN 4
        WHEN 'confidential' THEN 3
        WHEN 'internal' THEN 2
        WHEN 'public' THEN 1
    END) AS weighted_sensitivity_score,
    RANK() OVER (ORDER BY COUNT(DISTINCT d.document_id) DESC) AS contribution_rank
FROM users u
JOIN documents d ON d.uploaded_by = u.user_id
LEFT JOIN document_concepts dc ON dc.document_id = d.document_id
WHERE d.is_archived = FALSE
GROUP BY u.user_id, u.full_name, u.department
ORDER BY total_documents DESC;

-- ============================================================================
-- QUERY 10: Concept Co-occurrence Analysis
-- Finds pairs of concepts that frequently appear together in documents.
-- Demonstrates: Self-join, GROUP BY with HAVING, combinatorial analysis
-- ============================================================================
SELECT
    c1.name AS concept_1,
    c2.name AS concept_2,
    COUNT(DISTINCT dc1.document_id) AS co_occurrence_count,
    ROUND(AVG(dc1.relevance_score + dc2.relevance_score) / 2, 3) AS avg_combined_relevance
FROM document_concepts dc1
JOIN document_concepts dc2 ON dc1.document_id = dc2.document_id
    AND dc1.concept_id < dc2.concept_id  -- Avoid duplicates and self-pairs
JOIN concepts c1 ON c1.concept_id = dc1.concept_id
JOIN concepts c2 ON c2.concept_id = dc2.concept_id
GROUP BY c1.name, c2.name
HAVING COUNT(DISTINCT dc1.document_id) >= 1
ORDER BY co_occurrence_count DESC, avg_combined_relevance DESC
LIMIT 15;

-- ============================================================================
-- QUERY 11: Orphaned Entities (No Document Links)
-- Identifies entities that exist in the system but are not linked to any
-- document, potentially indicating stale or unused knowledge nodes.
-- Demonstrates: LEFT JOIN with NULL check (anti-join pattern)
-- ============================================================================
SELECT
    e.entity_id,
    e.name,
    e.entity_type,
    e.description,
    e.confidence,
    e.created_at
FROM entities e
LEFT JOIN document_entities de ON de.entity_id = e.entity_id
WHERE de.document_id IS NULL
ORDER BY e.created_at DESC;

-- ============================================================================
-- QUERY 12: Role-Based Document Access Matrix
-- Creates a cross-tabulation of roles and the sensitivity levels they
-- can access, showing the effective permission matrix.
-- Demonstrates: CASE aggregation (pivot), BOOL_OR, GROUP BY
-- ============================================================================
SELECT
    r.role_name,
    BOOL_OR(CASE WHEN ap.sensitivity_level = 'public'       THEN ap.can_read END) AS public_read,
    BOOL_OR(CASE WHEN ap.sensitivity_level = 'public'       THEN ap.can_write END) AS public_write,
    BOOL_OR(CASE WHEN ap.sensitivity_level = 'internal'     THEN ap.can_read END) AS internal_read,
    BOOL_OR(CASE WHEN ap.sensitivity_level = 'internal'     THEN ap.can_write END) AS internal_write,
    BOOL_OR(CASE WHEN ap.sensitivity_level = 'confidential' THEN ap.can_read END) AS confidential_read,
    BOOL_OR(CASE WHEN ap.sensitivity_level = 'confidential' THEN ap.can_write END) AS confidential_write,
    BOOL_OR(CASE WHEN ap.sensitivity_level = 'restricted'   THEN ap.can_read END) AS restricted_read,
    BOOL_OR(CASE WHEN ap.sensitivity_level = 'restricted'   THEN ap.can_write END) AS restricted_write
FROM roles r
LEFT JOIN access_policies ap ON ap.role_id = r.role_id AND ap.resource_type = 'document'
GROUP BY r.role_id, r.role_name
ORDER BY r.role_name;

-- ============================================================================
-- QUERY 13: Entity Relationship Network Analysis
-- Analyzes the relationship graph to find the most connected entities
-- (highest degree centrality).
-- Demonstrates: UNION ALL for bidirectional edges, GROUP BY, HAVING
-- ============================================================================
WITH all_connections AS (
    SELECT source_entity_id AS entity_id, relation_type FROM relations
    UNION ALL
    SELECT target_entity_id AS entity_id, relation_type FROM relations
)
SELECT
    e.name,
    e.entity_type,
    COUNT(*) AS total_connections,
    COUNT(DISTINCT ac.relation_type) AS distinct_relation_types,
    STRING_AGG(DISTINCT ac.relation_type, ', ' ORDER BY ac.relation_type) AS relation_types
FROM all_connections ac
JOIN entities e ON e.entity_id = ac.entity_id
GROUP BY e.entity_id, e.name, e.entity_type
HAVING COUNT(*) > 1
ORDER BY total_connections DESC;

-- ============================================================================
-- QUERY 14: Recently Updated Documents with Version History
-- Shows documents updated in the last 90 days along with their version
-- count and last editor.
-- Demonstrates: Correlated subquery, lateral join pattern, date arithmetic
-- ============================================================================
SELECT
    d.document_id,
    d.title,
    d.source_type,
    d.updated_at,
    d.sensitivity_level,
    (SELECT COUNT(*) FROM document_versions dv WHERE dv.document_id = d.document_id) AS version_count,
    (SELECT u2.full_name
     FROM document_versions dv2
     JOIN users u2 ON u2.user_id = dv2.changed_by
     WHERE dv2.document_id = d.document_id
     ORDER BY dv2.version_number DESC LIMIT 1) AS last_editor,
    u.full_name AS original_uploader
FROM documents d
JOIN users u ON u.user_id = d.uploaded_by
WHERE d.updated_at >= CURRENT_TIMESTAMP - INTERVAL '90 days'
ORDER BY d.updated_at DESC;

-- ============================================================================
-- QUERY 15: Cross-Domain Knowledge Bridges
-- Identifies documents and entities that span multiple knowledge domains,
-- acting as bridges between different areas of expertise.
-- Demonstrates: GROUP BY with HAVING, COUNT(DISTINCT), multiple JOINs
-- ============================================================================
SELECT
    d.document_id,
    d.title,
    d.source_type,
    COUNT(DISTINCT c.domain) AS domains_spanned,
    STRING_AGG(DISTINCT c.domain, ', ' ORDER BY c.domain) AS domains,
    COUNT(DISTINCT c.concept_id) AS concept_count,
    STRING_AGG(DISTINCT c.name, ', ' ORDER BY c.name) AS concepts,
    ROUND(AVG(dc.relevance_score), 3) AS avg_relevance
FROM documents d
JOIN document_concepts dc ON dc.document_id = d.document_id
JOIN concepts c ON c.concept_id = dc.concept_id
WHERE c.domain IS NOT NULL
GROUP BY d.document_id, d.title, d.source_type
HAVING COUNT(DISTINCT c.domain) >= 2
ORDER BY domains_spanned DESC, concept_count DESC;

-- ============================================================================
-- BONUS QUERY: Full-Text Search with Ranking
-- Performs a PostgreSQL full-text search on document content with relevance
-- ranking using ts_rank.
-- Demonstrates: tsvector, tsquery, ts_rank, full-text search
-- ============================================================================
SELECT
    d.document_id,
    d.title,
    d.source_type,
    d.sensitivity_level,
    ts_rank(
        to_tsvector('english', d.title || ' ' || d.content),
        plainto_tsquery('english', 'machine learning neural network')
    ) AS search_rank,
    LEFT(d.summary, 120) || '...' AS summary_preview
FROM documents d
WHERE to_tsvector('english', d.title || ' ' || d.content)
      @@ plainto_tsquery('english', 'machine learning neural network')
ORDER BY search_rank DESC
LIMIT 10;

-- ============================================================================
-- END OF QUERY SET
-- ============================================================================
