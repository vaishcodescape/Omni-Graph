SET search_path TO omnigraph;



-- SCENARIO 1: Document Search & Discovery


-- Q1.1: Search for documents containing a specific keyword in title or content

SELECT
    d.document_id,
    d.title,
    d.source_type,
    d.sensitivity_level,
    LEFT(d.summary, 150) AS excerpt,
    u.full_name AS author,
    ts_rank(
        to_tsvector('english', d.title || ' ' || d.content),
        plainto_tsquery('english', 'deep learning')
    ) AS relevance_rank
FROM documents d
JOIN users u ON u.user_id = d.uploaded_by
WHERE to_tsvector('english', d.title || ' ' || d.content)
      @@ plainto_tsquery('english', 'deep learning')
  AND d.is_archived = FALSE
ORDER BY relevance_rank DESC
LIMIT 10;


-- Q1.2: List all documents tagged with a specific tag

SELECT
    d.document_id,
    d.title,
    d.source_type,
    d.sensitivity_level,
    LEFT(d.summary, 120) AS summary,
    u.full_name AS uploaded_by,
    dt.tagged_at
FROM document_tags dt
JOIN tags t ON t.tag_id = dt.tag_id
JOIN documents d ON d.document_id = dt.document_id
JOIN users u ON u.user_id = d.uploaded_by
WHERE LOWER(t.name) = LOWER('security')
  AND d.is_archived = FALSE
ORDER BY dt.tagged_at DESC;


-- Q1.3: Get all documents uploaded by a specific user

SELECT
    d.document_id,
    d.title,
    d.source_type,
    d.sensitivity_level,
    d.created_at,
    LEFT(d.summary, 100) AS summary
FROM documents d
JOIN users u ON u.user_id = d.uploaded_by
WHERE u.username = 'ben.okafor'
  AND d.is_archived = FALSE
ORDER BY d.created_at DESC;


-- Q1.4: Filter documents by their source type

SELECT
    d.document_id,
    d.title,
    d.sensitivity_level,
    d.created_at,
    u.full_name AS uploaded_by
FROM documents d
JOIN users u ON u.user_id = d.uploaded_by
WHERE d.source_type = 'research_paper'
  AND d.is_archived = FALSE
ORDER BY d.created_at DESC;


-- Q1.5: List all documents under a taxonomy branch including all sub-categories

WITH RECURSIVE taxonomy_tree AS (
    SELECT taxonomy_id, name, parent_id, level
    FROM taxonomy
    WHERE name = 'Technology'

    UNION ALL

    SELECT t.taxonomy_id, t.name, t.parent_id, t.level
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


-- Q1.6: Which documents have more than one saved version?

SELECT
    d.document_id,
    d.title,
    d.source_type,
    COUNT(dv.version_id) AS version_count,
    MAX(dv.version_number) AS latest_version,
    u.full_name AS uploaded_by
FROM documents d
JOIN users u ON u.user_id = d.uploaded_by
JOIN document_versions dv ON dv.document_id = d.document_id
GROUP BY d.document_id, d.title, d.source_type, u.full_name
HAVING COUNT(dv.version_id) > 1
ORDER BY version_count DESC;


-- Q1.7: Show recently updated documents along with their version count and last editor

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
WHERE d.is_archived = FALSE
ORDER BY d.updated_at DESC;


-- Q1.8: Which documents span multiple knowledge domains?

SELECT
    d.document_id,
    d.title,
    d.source_type,
    COUNT(DISTINCT c.domain) AS domains_spanned,
    STRING_AGG(DISTINCT c.domain, ', ' ORDER BY c.domain) AS domains,
    COUNT(DISTINCT c.concept_id) AS concept_count,
    ROUND(AVG(dc.relevance_score), 3) AS avg_relevance
FROM documents d
JOIN document_concepts dc ON dc.document_id = d.document_id
JOIN concepts c ON c.concept_id = dc.concept_id
WHERE c.domain IS NOT NULL
GROUP BY d.document_id, d.title, d.source_type
HAVING COUNT(DISTINCT c.domain) >= 2
ORDER BY domains_spanned DESC, concept_count DESC;


-- Q1.9: Which documents have the most entity mentions?

SELECT
    d.document_id,
    d.title,
    d.source_type,
    COUNT(DISTINCT de.entity_id) AS distinct_entities,
    SUM(de.mention_count) AS total_mentions,
    u.full_name AS uploaded_by
FROM documents d
JOIN users u ON u.user_id = d.uploaded_by
JOIN document_entities de ON de.document_id = d.document_id
WHERE d.is_archived = FALSE
GROUP BY d.document_id, d.title, d.source_type, u.full_name
ORDER BY total_mentions DESC;


-- Q1.10: Find documents that have no tags assigned to them

SELECT
    d.document_id,
    d.title,
    d.source_type,
    d.sensitivity_level,
    d.created_at,
    u.full_name AS uploaded_by
FROM documents d
JOIN users u ON u.user_id = d.uploaded_by
WHERE d.is_archived = FALSE
  AND NOT EXISTS (
      SELECT 1 FROM document_tags dt WHERE dt.document_id = d.document_id
  )
ORDER BY d.created_at DESC;


-- Q1.11: List every document with all its associated tags

SELECT
    d.document_id,
    d.title,
    d.source_type,
    d.sensitivity_level,
    STRING_AGG(t.name, ', ' ORDER BY t.name) AS tags,
    u.full_name AS uploaded_by
FROM documents d
JOIN users u ON u.user_id = d.uploaded_by
LEFT JOIN document_tags dt ON dt.document_id = d.document_id
LEFT JOIN tags t ON t.tag_id = dt.tag_id
WHERE d.is_archived = FALSE
GROUP BY d.document_id, d.title, d.source_type, d.sensitivity_level, u.full_name
ORDER BY d.document_id;


-- Q1.12: Get all documents related to a concept along with their tags

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
WHERE LOWER(c.name) = LOWER('Machine Learning')
  AND d.is_archived = FALSE
GROUP BY d.document_id, d.title, d.source_type, d.sensitivity_level, dc.relevance_score, u.full_name
ORDER BY dc.relevance_score DESC;



-- SCENARIO 2: Access Control & Security


-- Q2.1: Which documents is a specific user allowed to read based on their role?

SELECT
    d.document_id,
    d.title,
    d.source_type,
    d.sensitivity_level,
    d.created_at,
    u_author.full_name AS uploaded_by
FROM users u_target
JOIN user_roles ur ON ur.user_id = u_target.user_id
JOIN access_policies ap ON ap.role_id = ur.role_id
JOIN documents d ON d.sensitivity_level = ap.sensitivity_level
JOIN users u_author ON u_author.user_id = d.uploaded_by
WHERE u_target.username = 'grace.huang'
  AND ap.resource_type = 'document'
  AND ap.can_read = TRUE
  AND d.is_archived = FALSE
GROUP BY d.document_id, d.title, d.source_type, d.sensitivity_level, d.created_at, u_author.full_name
ORDER BY d.sensitivity_level, d.created_at DESC;


-- Q2.2: Show all access-denied events from the last 30 days

SELECT
    al.audit_id,
    al.created_at AS event_timestamp,
    u.username,
    u.full_name,
    u.department,
    al.resource_type,
    al.resource_id,
    COALESCE(d.title, '—') AS document_title,
    COALESCE(d.sensitivity_level, '—') AS doc_sensitivity,
    al.details,
    al.ip_address
FROM audit_logs al
JOIN users u ON u.user_id = al.user_id
LEFT JOIN documents d ON d.document_id = al.resource_id
                      AND al.resource_type = 'document'
WHERE al.action = 'access_denied'
  AND al.created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
ORDER BY al.created_at DESC;


-- Q2.3: Which users successfully accessed confidential or restricted documents?

SELECT
    al.audit_id,
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
  AND al.action = 'view'
  AND d.sensitivity_level IN ('confidential', 'restricted')
GROUP BY al.audit_id, al.created_at, u.full_name, u.department,
         al.action, d.title, d.sensitivity_level, al.details, al.ip_address
ORDER BY al.created_at DESC;


-- Q2.4: Which users hold more than one role?

SELECT
    u.user_id,
    u.full_name,
    u.department,
    u.title,
    COUNT(ur.role_id) AS role_count,
    STRING_AGG(r.role_name, ', ' ORDER BY r.role_name) AS assigned_roles
FROM users u
JOIN user_roles ur ON ur.user_id = u.user_id
JOIN roles r ON r.role_id = ur.role_id
GROUP BY u.user_id, u.full_name, u.department, u.title
HAVING COUNT(ur.role_id) > 1
ORDER BY role_count DESC;


-- Q2.5: What is the full read/write permission matrix across all roles and sensitivity levels?

SELECT
    r.role_name,
    BOOL_OR(CASE WHEN ap.sensitivity_level = 'public'       THEN ap.can_read  END) AS public_read,
    BOOL_OR(CASE WHEN ap.sensitivity_level = 'public'       THEN ap.can_write END) AS public_write,
    BOOL_OR(CASE WHEN ap.sensitivity_level = 'internal'     THEN ap.can_read  END) AS internal_read,
    BOOL_OR(CASE WHEN ap.sensitivity_level = 'internal'     THEN ap.can_write END) AS internal_write,
    BOOL_OR(CASE WHEN ap.sensitivity_level = 'confidential' THEN ap.can_read  END) AS confidential_read,
    BOOL_OR(CASE WHEN ap.sensitivity_level = 'confidential' THEN ap.can_write END) AS confidential_write,
    BOOL_OR(CASE WHEN ap.sensitivity_level = 'restricted'   THEN ap.can_read  END) AS restricted_read,
    BOOL_OR(CASE WHEN ap.sensitivity_level = 'restricted'   THEN ap.can_write END) AS restricted_write
FROM roles r
LEFT JOIN access_policies ap ON ap.role_id = r.role_id AND ap.resource_type = 'document'
GROUP BY r.role_id, r.role_name
ORDER BY r.role_name;


-- Q2.6: List all document export events recorded in the audit log

SELECT
    al.audit_id,
    al.created_at AS exported_at,
    u.full_name AS exported_by,
    u.department,
    d.title AS document_title,
    d.sensitivity_level,
    al.details,
    al.ip_address
FROM audit_logs al
JOIN users u ON u.user_id = al.user_id
JOIN documents d ON d.document_id = al.resource_id
WHERE al.action = 'export'
  AND al.resource_type = 'document'
ORDER BY al.created_at DESC;


-- Q2.7: Which users have the most activity recorded in the audit log?

SELECT
    u.user_id,
    u.full_name,
    u.department,
    COUNT(*) AS total_events,
    COUNT(*) FILTER (WHERE al.action = 'view')          AS views,
    COUNT(*) FILTER (WHERE al.action = 'create')        AS creates,
    COUNT(*) FILTER (WHERE al.action = 'export')        AS exports,
    COUNT(*) FILTER (WHERE al.action = 'access_denied') AS denied_attempts
FROM audit_logs al
JOIN users u ON u.user_id = al.user_id
GROUP BY u.user_id, u.full_name, u.department
ORDER BY total_events DESC;


-- Q2.8: List all users assigned the admin role

SELECT
    u.user_id,
    u.full_name,
    u.department,
    u.title,
    u.email,
    ur.assigned_at
FROM users u
JOIN user_roles ur ON ur.user_id = u.user_id
JOIN roles r ON r.role_id = ur.role_id
WHERE r.role_name = 'admin'
  AND u.is_active = TRUE
ORDER BY ur.assigned_at;


-- Q2.9: Which documents cannot be written to by any role?

SELECT
    d.document_id,
    d.title,
    d.sensitivity_level,
    d.source_type,
    u.full_name AS uploaded_by
FROM documents d
JOIN users u ON u.user_id = d.uploaded_by
WHERE d.is_archived = FALSE
  AND NOT EXISTS (
      SELECT 1
      FROM access_policies ap
      WHERE ap.sensitivity_level = d.sensitivity_level
        AND ap.resource_type = 'document'
        AND ap.can_write = TRUE
  )
ORDER BY d.sensitivity_level;


-- Q2.10: Show all login and logout events with timestamps and IP addresses

SELECT
    al.audit_id,
    al.created_at AS event_time,
    al.action,
    u.username,
    u.full_name,
    u.department,
    al.ip_address,
    al.details
FROM audit_logs al
JOIN users u ON u.user_id = al.user_id
WHERE al.action IN ('login', 'logout')
ORDER BY al.created_at DESC;


-- Q2.11: Which users attempted to access documents above their clearance level?

SELECT DISTINCT
    u.full_name,
    u.department,
    STRING_AGG(DISTINCT r.role_name, ', ') AS roles,
    d.title AS document_attempted,
    d.sensitivity_level,
    al.created_at AS attempted_at,
    al.ip_address
FROM audit_logs al
JOIN users u ON u.user_id = al.user_id
JOIN documents d ON d.document_id = al.resource_id
LEFT JOIN user_roles ur ON ur.user_id = u.user_id
LEFT JOIN roles r ON r.role_id = ur.role_id
WHERE al.action = 'access_denied'
  AND al.resource_type = 'document'
GROUP BY u.full_name, u.department, d.title, d.sensitivity_level, al.created_at, al.ip_address
ORDER BY al.created_at DESC;


-- Q2.12: How many documents exist per sensitivity level and which roles can read each level?

SELECT
    d.sensitivity_level,
    COUNT(DISTINCT d.document_id) AS document_count,
    STRING_AGG(DISTINCT r.role_name, ', ' ORDER BY r.role_name) AS roles_with_read_access
FROM documents d
LEFT JOIN access_policies ap ON ap.sensitivity_level = d.sensitivity_level
                             AND ap.resource_type = 'document'
                             AND ap.can_read = TRUE
LEFT JOIN roles r ON r.role_id = ap.role_id
GROUP BY d.sensitivity_level
ORDER BY document_count DESC;



-- SCENARIO 3: Knowledge Graph & Entity Relations


-- Q3.1: What entities were extracted from a specific document?

SELECT
    e.entity_id,
    e.name,
    e.entity_type,
    e.confidence AS extraction_confidence,
    de.relevance AS document_relevance,
    de.mention_count,
    de.first_occurrence AS first_char_position
FROM document_entities de
JOIN entities e ON e.entity_id = de.entity_id
WHERE de.document_id = 2
ORDER BY de.relevance DESC, de.mention_count DESC;


-- Q3.2: Find all entities reachable within 2 hops from a seed entity

WITH RECURSIVE entity_hops AS (

    SELECT
        r.target_entity_id AS entity_id,
        e.name,
        e.entity_type,
        r.relation_type,
        r.strength,
        1 AS depth,
        ARRAY[1, r.target_entity_id] AS visited
    FROM relations r
    JOIN entities e ON e.entity_id = r.target_entity_id
    WHERE r.source_entity_id = 1

    UNION ALL

    SELECT
        r.target_entity_id,
        e.name,
        e.entity_type,
        r.relation_type,
        r.strength,
        eh.depth + 1,
        eh.visited || r.target_entity_id
    FROM entity_hops eh
    JOIN relations r ON r.source_entity_id = eh.entity_id
    JOIN entities e ON e.entity_id = r.target_entity_id
    WHERE eh.depth < 2
      AND NOT (r.target_entity_id = ANY(eh.visited))

)
SELECT DISTINCT
    entity_id,
    name,
    entity_type,
    relation_type,
    strength,
    depth AS hops_from_seed
FROM entity_hops
ORDER BY depth ASC, strength DESC;


-- Q3.3: Which entities are most connected in the knowledge graph?

SELECT
    e.entity_id,
    e.name,
    e.entity_type,
    COUNT(DISTINCT r_out.relation_id) AS outgoing_relations,
    COUNT(DISTINCT r_in.relation_id)  AS incoming_relations,
    COUNT(DISTINCT r_out.relation_id) + COUNT(DISTINCT r_in.relation_id) AS total_connections
FROM entities e
LEFT JOIN relations r_out ON r_out.source_entity_id = e.entity_id
LEFT JOIN relations r_in  ON r_in.target_entity_id  = e.entity_id
GROUP BY e.entity_id, e.name, e.entity_type
ORDER BY total_connections DESC
LIMIT 10;


-- Q3.4: Which documents mention a specific entity?

SELECT
    d.document_id,
    d.title,
    d.source_type,
    d.sensitivity_level,
    de.relevance,
    de.mention_count,
    u.full_name AS uploaded_by
FROM document_entities de
JOIN documents d ON d.document_id = de.document_id
JOIN entities e ON e.entity_id = de.entity_id
JOIN users u ON u.user_id = d.uploaded_by
WHERE LOWER(e.name) = LOWER('Kubernetes')
  AND d.is_archived = FALSE
ORDER BY de.relevance DESC;


-- Q3.5: Which documents share a common entity?

SELECT
    de1.document_id AS doc_a,
    d1.title AS title_a,
    de2.document_id AS doc_b,
    d2.title AS title_b,
    e.name AS shared_entity,
    e.entity_type
FROM document_entities de1
JOIN document_entities de2 ON de1.entity_id = de2.entity_id
                           AND de2.document_id > de1.document_id
JOIN entities e ON e.entity_id = de1.entity_id
JOIN documents d1 ON d1.document_id = de1.document_id
JOIN documents d2 ON d2.document_id = de2.document_id
ORDER BY e.name, de1.document_id;


-- Q3.6: Which entities have no outgoing relations in the graph?

SELECT
    e.entity_id,
    e.name,
    e.entity_type,
    e.description,
    e.confidence
FROM entities e
WHERE NOT EXISTS (
    SELECT 1 FROM relations r WHERE r.source_entity_id = e.entity_id
)
ORDER BY e.entity_type, e.name;


-- Q3.7: Which entities are mentioned most frequently across all documents?

SELECT
    e.entity_id,
    e.name,
    e.entity_type,
    COUNT(DISTINCT de.document_id) AS documents_mentioned_in,
    SUM(de.mention_count) AS total_mentions,
    ROUND(AVG(de.relevance), 3) AS avg_relevance
FROM entities e
JOIN document_entities de ON de.entity_id = e.entity_id
GROUP BY e.entity_id, e.name, e.entity_type
ORDER BY total_mentions DESC;


-- Q3.8: What is the breakdown of entity types in the system?

SELECT
    entity_type,
    COUNT(*) AS total_entities,
    ROUND(AVG(confidence), 3) AS avg_confidence,
    ROUND(MIN(confidence), 3) AS min_confidence,
    ROUND(MAX(confidence), 3) AS max_confidence
FROM entities
GROUP BY entity_type
ORDER BY total_entities DESC;


-- Q3.9: Find all relations of a specific type across the knowledge graph

SELECT
    e_src.name AS source_entity,
    e_src.entity_type AS source_type,
    r.relation_type,
    r.strength,
    e_tgt.name AS target_entity,
    e_tgt.entity_type AS target_type,
    d.title AS source_document
FROM relations r
JOIN entities e_src ON e_src.entity_id = r.source_entity_id
JOIN entities e_tgt ON e_tgt.entity_id = r.target_entity_id
LEFT JOIN documents d ON d.document_id = r.source_document_id
WHERE r.relation_type = 'depends_on'
ORDER BY r.strength DESC;


-- Q3.10: Which entities are directly associated with a given concept?

SELECT
    e.entity_id,
    e.name,
    e.entity_type,
    ec.relevance_score,
    c.name AS concept,
    c.domain
FROM entity_concepts ec
JOIN entities e ON e.entity_id = ec.entity_id
JOIN concepts c ON c.concept_id = ec.concept_id
WHERE LOWER(c.name) = LOWER('Deep Learning')
ORDER BY ec.relevance_score DESC;


-- Q3.11: Find the shortest relationship path between two entities

WITH RECURSIVE paths AS (

    SELECT
        r.target_entity_id AS current_id,
        ARRAY[es.name, et.name]::TEXT[] AS path_names,
        ARRAY[r.relation_type]::TEXT[] AS path_relations,
        1 AS depth
    FROM relations r
    JOIN entities es ON es.entity_id = r.source_entity_id
    JOIN entities et ON et.entity_id = r.target_entity_id
    WHERE r.source_entity_id = 4

    UNION ALL

    SELECT
        r.target_entity_id,
        p.path_names || et.name::TEXT,
        p.path_relations || r.relation_type::TEXT,
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
WHERE current_id = 12
ORDER BY depth ASC
LIMIT 5;


-- Q3.12: For each entity, show all relation types it participates in (incoming + outgoing)

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



-- SCENARIO 4: Concept, Expertise & Analytics


-- Q4.1: Who are the top contributors for a given concept based on document uploads?

SELECT
    u.user_id,
    u.full_name,
    u.department,
    u.title,
    COUNT(DISTINCT d.document_id) AS documents_contributed,
    ROUND(AVG(dc.relevance_score)::NUMERIC, 3) AS avg_concept_relevance,
    ROUND(
        COUNT(DISTINCT d.document_id) * AVG(dc.relevance_score) * 10,
        2
    ) AS expertise_score
FROM users u
JOIN documents d ON d.uploaded_by = u.user_id
JOIN document_concepts dc ON dc.document_id = d.document_id
JOIN concepts c ON c.concept_id = dc.concept_id
WHERE LOWER(c.name) = LOWER('Deep Learning')
  AND u.is_active = TRUE
GROUP BY u.user_id, u.full_name, u.department, u.title
ORDER BY expertise_score DESC
LIMIT 5;


-- Q4.2: Get the full concept hierarchy tree starting from a root concept

WITH RECURSIVE concept_tree AS (

    SELECT
        c.concept_id,
        c.name,
        c.domain,
        NULL::VARCHAR(200) AS parent_name,
        0 AS depth
    FROM concepts c
    WHERE LOWER(c.name) = LOWER('Machine Learning')

    UNION ALL

    SELECT
        child.concept_id,
        child.name,
        child.domain,
        ct.name AS parent_name,
        ct.depth + 1
    FROM concept_tree ct
    JOIN concept_hierarchy ch ON ch.parent_concept_id = ct.concept_id
    JOIN concepts child ON child.concept_id = ch.child_concept_id
    WHERE ct.depth < 10

)
SELECT
    concept_id,
    REPEAT('    ', depth) || name AS indented_name,
    domain,
    parent_name,
    depth
FROM concept_tree
ORDER BY depth, name;


-- Q4.3: Which concept pairs co-occur most frequently in the same documents?

SELECT
    c1.name AS concept_a,
    c1.domain AS domain_a,
    c2.name AS concept_b,
    c2.domain AS domain_b,
    COUNT(DISTINCT dc1.document_id) AS shared_documents,
    ROUND(
        AVG((dc1.relevance_score + dc2.relevance_score) / 2.0)::NUMERIC,
        3
    ) AS avg_combined_relevance
FROM document_concepts dc1
JOIN document_concepts dc2 ON dc2.document_id = dc1.document_id
                           AND dc2.concept_id > dc1.concept_id
JOIN concepts c1 ON c1.concept_id = dc1.concept_id
JOIN concepts c2 ON c2.concept_id = dc2.concept_id
GROUP BY c1.concept_id, c1.name, c1.domain, c2.concept_id, c2.name, c2.domain
HAVING COUNT(DISTINCT dc1.document_id) > 0
ORDER BY shared_documents DESC, avg_combined_relevance DESC
LIMIT 15;


-- Q4.4: What are the average execution time and result counts for each query type?

SELECT
    query_type,
    COUNT(*) AS total_queries,
    ROUND(AVG(execution_ms)::NUMERIC, 1) AS avg_execution_ms,
    ROUND(MIN(execution_ms)::NUMERIC, 1) AS min_execution_ms,
    ROUND(MAX(execution_ms)::NUMERIC, 1) AS max_execution_ms,
    ROUND(AVG(results_count)::NUMERIC, 1) AS avg_results_returned,
    ROUND(STDDEV(execution_ms)::NUMERIC, 1) AS stddev_execution_ms
FROM query_logs
WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '90 days'
GROUP BY query_type
ORDER BY total_queries DESC;


-- Q4.5: Which concepts have the most document and entity associations?

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


-- Q4.6: Which taxonomy nodes have the most documents assigned to them?

SELECT
    t.taxonomy_id,
    t.name AS taxonomy_name,
    t.domain,
    t.level,
    COUNT(d.document_id) AS document_count
FROM taxonomy t
LEFT JOIN documents d ON d.taxonomy_id = t.taxonomy_id
                      AND d.is_archived = FALSE
GROUP BY t.taxonomy_id, t.name, t.domain, t.level
ORDER BY document_count DESC;


-- Q4.7: Rank users by total document contributions weighted by sensitivity level

SELECT
    u.full_name,
    u.department,
    COUNT(DISTINCT d.document_id) AS total_documents,
    COUNT(DISTINCT dc.concept_id) AS concepts_covered,
    SUM(CASE d.sensitivity_level
        WHEN 'restricted'   THEN 4
        WHEN 'confidential' THEN 3
        WHEN 'internal'     THEN 2
        WHEN 'public'       THEN 1
        ELSE 0
    END) AS weighted_sensitivity_score,
    RANK() OVER (ORDER BY COUNT(DISTINCT d.document_id) DESC) AS contribution_rank
FROM users u
JOIN documents d ON d.uploaded_by = u.user_id
LEFT JOIN document_concepts dc ON dc.document_id = d.document_id
WHERE d.is_archived = FALSE
GROUP BY u.user_id, u.full_name, u.department
ORDER BY total_documents DESC;


-- Q4.8: Which documents have no concept extracted from them?

SELECT
    d.document_id,
    d.title,
    d.source_type,
    d.sensitivity_level,
    d.created_at,
    u.full_name AS uploaded_by,
    LEFT(d.summary, 100) AS summary
FROM documents d
JOIN users u ON u.user_id = d.uploaded_by
WHERE d.is_archived = FALSE
  AND NOT EXISTS (
      SELECT 1 FROM document_concepts dc WHERE dc.document_id = d.document_id
  )
ORDER BY d.created_at DESC;


-- Q4.9: What are the most frequently searched query terms in the system?

SELECT
    query_text,
    query_type,
    COUNT(*) AS search_count,
    ROUND(AVG(results_count), 1) AS avg_results,
    ROUND(AVG(execution_ms), 1) AS avg_ms
FROM query_logs
GROUP BY query_text, query_type
ORDER BY search_count DESC
LIMIT 15;


-- Q4.10: How does average query response time compare across months?

SELECT
    DATE_TRUNC('month', created_at)::DATE AS month,
    query_type,
    COUNT(*) AS query_count,
    ROUND(AVG(execution_ms)::NUMERIC, 1) AS avg_ms,
    ROUND(MAX(execution_ms)::NUMERIC, 1) AS max_ms
FROM query_logs
GROUP BY DATE_TRUNC('month', created_at), query_type
ORDER BY month DESC, avg_ms DESC;


-- Q4.11: Which tags are most used and how are they spread across categories?

SELECT
    t.category,
    t.name AS tag_name,
    COUNT(dt.document_id) AS usage_count,
    RANK() OVER (PARTITION BY t.category ORDER BY COUNT(dt.document_id) DESC) AS rank_in_category
FROM tags t
LEFT JOIN document_tags dt ON dt.tag_id = t.tag_id
GROUP BY t.tag_id, t.category, t.name
ORDER BY t.category, usage_count DESC;


-- Q4.12: How does document creation volume trend over time by source type?

SELECT
    DATE_TRUNC('month', d.created_at)::DATE AS month,
    d.source_type,
    COUNT(*) AS documents_created,
    SUM(COUNT(*)) OVER (
        PARTITION BY d.source_type
        ORDER BY DATE_TRUNC('month', d.created_at)
    ) AS cumulative_count
FROM documents d
GROUP BY DATE_TRUNC('month', d.created_at), d.source_type
ORDER BY month DESC, documents_created DESC;



-- SCENARIO 5: Document Versioning & Content Lifecycle


-- Q5.1: Show the full version history for a specific document

SELECT
    dv.version_id,
    dv.version_number,
    dv.change_summary,
    dv.created_at AS versioned_at,
    u.full_name AS changed_by,
    LEFT(dv.content, 120) AS content_preview
FROM document_versions dv
JOIN users u ON u.user_id = dv.changed_by
WHERE dv.document_id = 3
ORDER BY dv.version_number ASC;


-- Q5.2: Which documents have never been updated since they were first uploaded?

SELECT
    d.document_id,
    d.title,
    d.source_type,
    d.sensitivity_level,
    d.created_at,
    u.full_name AS uploaded_by
FROM documents d
JOIN users u ON u.user_id = d.uploaded_by
WHERE d.is_archived = FALSE
  AND d.created_at = d.updated_at
ORDER BY d.created_at ASC;


-- Q5.3: Which user has made the most version changes across all documents?

SELECT
    u.user_id,
    u.full_name,
    u.department,
    COUNT(dv.version_id) AS total_version_changes,
    COUNT(DISTINCT dv.document_id) AS documents_edited
FROM document_versions dv
JOIN users u ON u.user_id = dv.changed_by
GROUP BY u.user_id, u.full_name, u.department
ORDER BY total_version_changes DESC;


-- Q5.4: Show the latest version content for each document that has version history

SELECT DISTINCT ON (dv.document_id)
    dv.document_id,
    d.title,
    dv.version_number AS latest_version,
    dv.change_summary,
    dv.created_at AS last_versioned_at,
    u.full_name AS last_editor,
    LEFT(dv.content, 150) AS latest_content_preview
FROM document_versions dv
JOIN documents d ON d.document_id = dv.document_id
JOIN users u ON u.user_id = dv.changed_by
ORDER BY dv.document_id, dv.version_number DESC;


-- Q5.5: How many versions does each document have on average, grouped by source type?

SELECT
    d.source_type,
    COUNT(DISTINCT d.document_id) AS total_documents,
    COUNT(dv.version_id) AS total_versions,
    ROUND(COUNT(dv.version_id)::NUMERIC / NULLIF(COUNT(DISTINCT d.document_id), 0), 2) AS avg_versions_per_doc,
    MAX(dv.version_number) AS max_versions_seen
FROM documents d
LEFT JOIN document_versions dv ON dv.document_id = d.document_id
GROUP BY d.source_type
ORDER BY avg_versions_per_doc DESC;


-- Q5.6: Find documents that have been edited more than once (multiple versions)

SELECT
    d.document_id,
    d.title,
    d.source_type,
    d.sensitivity_level,
    COUNT(dv.version_id) AS version_count,
    MIN(dv.created_at) AS first_edit,
    MAX(dv.created_at) AS latest_edit,
    u.full_name AS original_uploader
FROM documents d
JOIN users u ON u.user_id = d.uploaded_by
JOIN document_versions dv ON dv.document_id = d.document_id
GROUP BY d.document_id, d.title, d.source_type, d.sensitivity_level, u.full_name
HAVING COUNT(dv.version_id) > 1
ORDER BY version_count DESC;


-- Q5.7: Which documents have been archived and do they have any version history?

SELECT
    d.document_id,
    d.title,
    d.source_type,
    d.sensitivity_level,
    d.updated_at AS archived_around,
    u.full_name AS uploaded_by,
    COUNT(dv.version_id) AS version_count
FROM documents d
JOIN users u ON u.user_id = d.uploaded_by
LEFT JOIN document_versions dv ON dv.document_id = d.document_id
WHERE d.is_archived = TRUE
GROUP BY d.document_id, d.title, d.source_type, d.sensitivity_level, d.updated_at, u.full_name
ORDER BY d.updated_at DESC;


-- Q5.8: Show the full audit trail for a specific document (create, view, edit, export)

SELECT
    al.audit_id,
    al.created_at AS event_time,
    al.action,
    u.full_name AS performed_by,
    u.department,
    al.details,
    al.ip_address
FROM audit_logs al
JOIN users u ON u.user_id = al.user_id
WHERE al.resource_type = 'document'
  AND al.resource_id = 4
ORDER BY al.created_at ASC;


-- Q5.9: Which documents were created and then had at least one version saved within the same week?

SELECT
    d.document_id,
    d.title,
    d.source_type,
    d.created_at AS uploaded_at,
    MIN(dv.created_at) AS first_version_at,
    EXTRACT(EPOCH FROM (MIN(dv.created_at) - d.created_at)) / 3600 AS hours_until_first_edit
FROM documents d
JOIN document_versions dv ON dv.document_id = d.document_id
WHERE dv.created_at <= d.created_at + INTERVAL '7 days'
GROUP BY d.document_id, d.title, d.source_type, d.created_at
ORDER BY hours_until_first_edit ASC;


-- Q5.10: List all documents that have no version history at all

SELECT
    d.document_id,
    d.title,
    d.source_type,
    d.sensitivity_level,
    d.created_at,
    u.full_name AS uploaded_by
FROM documents d
JOIN users u ON u.user_id = d.uploaded_by
WHERE NOT EXISTS (
    SELECT 1 FROM document_versions dv WHERE dv.document_id = d.document_id
)
ORDER BY d.created_at DESC;


-- Q5.11: For each document, show how many distinct users have contributed versions

SELECT
    d.document_id,
    d.title,
    d.source_type,
    COUNT(dv.version_id) AS total_versions,
    COUNT(DISTINCT dv.changed_by) AS distinct_editors,
    STRING_AGG(DISTINCT u.full_name, ', ' ORDER BY u.full_name) AS editors
FROM documents d
JOIN document_versions dv ON dv.document_id = d.document_id
JOIN users u ON u.user_id = dv.changed_by
GROUP BY d.document_id, d.title, d.source_type
ORDER BY distinct_editors DESC, total_versions DESC;


-- Q5.12: Rank documents by how recently they were versioned or updated

SELECT
    d.document_id,
    d.title,
    d.source_type,
    d.sensitivity_level,
    d.updated_at,
    COALESCE(MAX(dv.created_at), d.updated_at) AS last_activity,
    COUNT(dv.version_id) AS version_count,
    RANK() OVER (ORDER BY COALESCE(MAX(dv.created_at), d.updated_at) DESC) AS activity_rank
FROM documents d
LEFT JOIN document_versions dv ON dv.document_id = d.document_id
WHERE d.is_archived = FALSE
GROUP BY d.document_id, d.title, d.source_type, d.sensitivity_level, d.updated_at
ORDER BY last_activity DESC;
