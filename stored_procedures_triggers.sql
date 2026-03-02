-- ============================================================================
-- OmniGraph: Enterprise AI Knowledge Graph Database System
-- Stored Procedures & Triggers
-- ============================================================================
-- Run AFTER database_schema.sql and sample_data.sql
-- ============================================================================

SET search_path TO omnigraph;

-- ============================================================================
-- STORED PROCEDURE 1: sp_auto_extract_entities
-- Simulates automatic entity extraction when a new document is inserted.
-- Extracts technology and organization names from document content using
-- pattern matching against existing entities.
-- ============================================================================
CREATE OR REPLACE FUNCTION sp_auto_extract_entities(p_document_id INTEGER)
RETURNS INTEGER AS $$
DECLARE
    v_entity RECORD;
    v_content TEXT;
    v_count INTEGER := 0;
    v_mention_count INTEGER;
BEGIN
    -- Get document content
    SELECT content INTO v_content FROM documents WHERE document_id = p_document_id;

    IF v_content IS NULL THEN
        RAISE EXCEPTION 'Document % not found', p_document_id;
    END IF;

    -- Match existing entities against document content
    FOR v_entity IN
        SELECT entity_id, name
        FROM entities
        WHERE entity_type IN ('technology', 'organization', 'standard')
    LOOP
        -- Count occurrences (case-insensitive)
        SELECT (LENGTH(v_content) - LENGTH(REPLACE(LOWER(v_content), LOWER(v_entity.name), '')))
               / GREATEST(LENGTH(v_entity.name), 1)
        INTO v_mention_count;

        IF v_mention_count > 0 THEN
            INSERT INTO document_entities (document_id, entity_id, relevance, mention_count)
            VALUES (p_document_id, v_entity.entity_id,
                    LEAST(1.0, v_mention_count * 0.1)::NUMERIC(4,3),
                    v_mention_count)
            ON CONFLICT (document_id, entity_id) DO UPDATE
                SET mention_count = EXCLUDED.mention_count,
                    relevance = EXCLUDED.relevance;
            v_count := v_count + 1;
        END IF;
    END LOOP;

    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- STORED PROCEDURE 2: sp_enforce_access_control
-- Validates whether a user has permission to perform an action on a resource.
-- Returns TRUE if access is granted, FALSE otherwise.
-- ============================================================================
CREATE OR REPLACE FUNCTION sp_enforce_access_control(
    p_user_id       INTEGER,
    p_resource_type VARCHAR(50),
    p_resource_id   INTEGER,
    p_action        VARCHAR(20)    -- 'read', 'write', 'delete'
)
RETURNS BOOLEAN AS $$
DECLARE
    v_sensitivity VARCHAR(30);
    v_has_access  BOOLEAN := FALSE;
BEGIN
    -- Determine sensitivity level of the resource
    IF p_resource_type = 'document' THEN
        SELECT sensitivity_level INTO v_sensitivity
        FROM documents WHERE document_id = p_resource_id;
    ELSE
        v_sensitivity := 'public';  -- Default for non-document resources
    END IF;

    IF v_sensitivity IS NULL THEN
        RETURN FALSE;  -- Resource not found
    END IF;

    -- Check user's roles against access policies
    SELECT EXISTS (
        SELECT 1
        FROM user_roles ur
        JOIN access_policies ap ON ur.role_id = ap.role_id
        WHERE ur.user_id = p_user_id
          AND ap.resource_type = p_resource_type
          AND ap.sensitivity_level = v_sensitivity
          AND (
              (p_action = 'read'   AND ap.can_read = TRUE) OR
              (p_action = 'write'  AND ap.can_write = TRUE) OR
              (p_action = 'delete' AND ap.can_delete = TRUE)
          )
    ) INTO v_has_access;

    -- Log access attempt if denied
    IF NOT v_has_access THEN
        INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details)
        VALUES (p_user_id, 'access_denied', p_resource_type, p_resource_id,
                FORMAT('Denied %s access to %s #%s (sensitivity: %s)',
                       p_action, p_resource_type, p_resource_id, v_sensitivity));
    END IF;

    RETURN v_has_access;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- STORED PROCEDURE 3: sp_archive_old_versions
-- Archives document versions older than a specified number of days,
-- keeping only the N most recent versions per document.
-- ============================================================================
CREATE OR REPLACE FUNCTION sp_archive_old_versions(
    p_keep_versions INTEGER DEFAULT 3,
    p_older_than_days INTEGER DEFAULT 180
)
RETURNS INTEGER AS $$
DECLARE
    v_deleted INTEGER := 0;
BEGIN
    WITH ranked_versions AS (
        SELECT version_id, document_id, version_number,
               ROW_NUMBER() OVER (PARTITION BY document_id ORDER BY version_number DESC) AS rn
        FROM document_versions
        WHERE created_at < CURRENT_TIMESTAMP - (p_older_than_days || ' days')::INTERVAL
    )
    DELETE FROM document_versions
    WHERE version_id IN (
        SELECT version_id FROM ranked_versions WHERE rn > p_keep_versions
    );

    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- STORED PROCEDURE 4: sp_find_experts
-- Finds domain experts for a given concept by analyzing document contributions
-- and entity associations. Returns users ranked by expertise score.
-- ============================================================================
CREATE OR REPLACE FUNCTION sp_find_experts(p_concept_name VARCHAR(200))
RETURNS TABLE (
    user_id     INTEGER,
    full_name   VARCHAR(255),
    department  VARCHAR(150),
    doc_count   BIGINT,
    avg_relevance NUMERIC,
    expertise_score NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        u.user_id,
        u.full_name,
        u.department,
        COUNT(DISTINCT d.document_id) AS doc_count,
        ROUND(AVG(dc.relevance_score), 3) AS avg_relevance,
        ROUND(COUNT(DISTINCT d.document_id) * AVG(dc.relevance_score) * 10, 2) AS expertise_score
    FROM users u
    JOIN documents d ON d.uploaded_by = u.user_id
    JOIN document_concepts dc ON dc.document_id = d.document_id
    JOIN concepts c ON c.concept_id = dc.concept_id
    WHERE LOWER(c.name) = LOWER(p_concept_name)
      AND u.is_active = TRUE
    GROUP BY u.user_id, u.full_name, u.department
    ORDER BY expertise_score DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- STORED PROCEDURE 5: sp_shortest_path
-- Finds the shortest relationship path between two entities using BFS
-- via recursive CTE. Returns the path as an array of entity names.
-- ============================================================================
CREATE OR REPLACE FUNCTION sp_shortest_path(
    p_source_entity_id INTEGER,
    p_target_entity_id INTEGER,
    p_max_depth INTEGER DEFAULT 6
)
RETURNS TABLE (
    path_length INTEGER,
    path_entities TEXT[],
    path_relations TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE entity_path AS (
        -- Base case: start from source entity
        SELECT
            r.target_entity_id AS current_id,
            1 AS depth,
            ARRAY[es.name, et.name] AS entities,
            ARRAY[r.relation_type] AS relations
        FROM relations r
        JOIN entities es ON es.entity_id = r.source_entity_id
        JOIN entities et ON et.entity_id = r.target_entity_id
        WHERE r.source_entity_id = p_source_entity_id

        UNION ALL

        -- Recursive case: traverse relationships
        SELECT
            r.target_entity_id,
            ep.depth + 1,
            ep.entities || et.name,
            ep.relations || r.relation_type
        FROM entity_path ep
        JOIN relations r ON r.source_entity_id = ep.current_id
        JOIN entities et ON et.entity_id = r.target_entity_id
        WHERE ep.depth < p_max_depth
          AND NOT (et.name = ANY(ep.entities))  -- Prevent cycles
    )
    SELECT
        ep.depth AS path_length,
        ep.entities AS path_entities,
        ep.relations AS path_relations
    FROM entity_path ep
    WHERE ep.current_id = p_target_entity_id
    ORDER BY ep.depth
    LIMIT 5;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- STORED PROCEDURE 6: sp_concept_network
-- Returns the full concept hierarchy network for a given root concept,
-- using recursive traversal of the concept_hierarchy table.
-- ============================================================================
CREATE OR REPLACE FUNCTION sp_concept_network(p_root_concept_name VARCHAR(200))
RETURNS TABLE (
    depth       INTEGER,
    concept_name VARCHAR(200),
    parent_name  VARCHAR(200),
    relationship VARCHAR(50),
    doc_count    BIGINT
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE concept_tree AS (
        -- Base: root concept
        SELECT
            c.concept_id,
            c.name AS concept_name,
            NULL::VARCHAR(200) AS parent_name,
            NULL::VARCHAR(50) AS relationship_type,
            0 AS depth
        FROM concepts c
        WHERE LOWER(c.name) = LOWER(p_root_concept_name)

        UNION ALL

        -- Children
        SELECT
            child.concept_id,
            child.name,
            ct.concept_name,
            ch.relationship_type,
            ct.depth + 1
        FROM concept_tree ct
        JOIN concept_hierarchy ch ON ch.parent_concept_id = ct.concept_id
        JOIN concepts child ON child.concept_id = ch.child_concept_id
        WHERE ct.depth < 10
    )
    SELECT
        ct.depth,
        ct.concept_name,
        ct.parent_name,
        ct.relationship_type,
        COUNT(dc.document_id) AS doc_count
    FROM concept_tree ct
    LEFT JOIN document_concepts dc ON dc.concept_id = ct.concept_id
    GROUP BY ct.depth, ct.concept_name, ct.parent_name, ct.relationship_type
    ORDER BY ct.depth, ct.concept_name;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TRIGGER 1: trg_audit_sensitive_access
-- Automatically logs an audit entry when a restricted or confidential
-- document is accessed (simulated via SELECT tracked in query_logs).
-- This trigger fires on INSERT to query_logs.
-- ============================================================================
CREATE OR REPLACE FUNCTION fn_audit_sensitive_access()
RETURNS TRIGGER AS $$
DECLARE
    v_doc RECORD;
BEGIN
    -- Check if the query references a sensitive document
    FOR v_doc IN
        SELECT document_id, title, sensitivity_level
        FROM documents
        WHERE sensitivity_level IN ('confidential', 'restricted')
          AND (LOWER(NEW.query_text) LIKE '%' || LOWER(title) || '%'
               OR NEW.query_text LIKE '%document_id = ' || document_id || '%')
    LOOP
        INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details)
        VALUES (NEW.user_id, 'view', 'document', v_doc.document_id,
                FORMAT('Sensitive document accessed via query: %s (sensitivity: %s)',
                       v_doc.title, v_doc.sensitivity_level));
    END LOOP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_sensitive_access
    AFTER INSERT ON query_logs
    FOR EACH ROW
    EXECUTE FUNCTION fn_audit_sensitive_access();

-- ============================================================================
-- TRIGGER 2: trg_version_on_update
-- Automatically creates a version record whenever a document's content
-- is updated, preserving the previous version.
-- ============================================================================
CREATE OR REPLACE FUNCTION fn_version_on_update()
RETURNS TRIGGER AS $$
DECLARE
    v_next_version INTEGER;
BEGIN
    IF OLD.content IS DISTINCT FROM NEW.content THEN
        -- Determine next version number
        SELECT COALESCE(MAX(version_number), 0) + 1
        INTO v_next_version
        FROM document_versions
        WHERE document_id = NEW.document_id;

        -- Store previous content as a version
        INSERT INTO document_versions (document_id, version_number, content, content_hash, change_summary, changed_by)
        VALUES (
            NEW.document_id,
            v_next_version,
            OLD.content,
            OLD.content_hash,
            'Auto-versioned on content update',
            NEW.uploaded_by
        );

        -- Update the timestamp
        NEW.updated_at := CURRENT_TIMESTAMP;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_version_on_update
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION fn_version_on_update();

-- ============================================================================
-- TRIGGER 3: trg_maintain_taxonomy
-- Ensures taxonomy consistency: prevents circular references and
-- automatically computes the level field based on parent.
-- ============================================================================
CREATE OR REPLACE FUNCTION fn_maintain_taxonomy()
RETURNS TRIGGER AS $$
DECLARE
    v_parent_level INTEGER;
    v_current_id INTEGER;
    v_check_id INTEGER;
BEGIN
    IF NEW.parent_id IS NOT NULL THEN
        -- Check for circular reference
        v_check_id := NEW.parent_id;
        WHILE v_check_id IS NOT NULL LOOP
            IF v_check_id = NEW.taxonomy_id THEN
                RAISE EXCEPTION 'Circular reference detected in taxonomy: node % cannot be its own ancestor', NEW.taxonomy_id;
            END IF;
            SELECT parent_id INTO v_check_id FROM taxonomy WHERE taxonomy_id = v_check_id;
        END LOOP;

        -- Auto-compute level from parent
        SELECT level INTO v_parent_level FROM taxonomy WHERE taxonomy_id = NEW.parent_id;
        IF v_parent_level IS NOT NULL THEN
            NEW.level := v_parent_level + 1;
        END IF;
    ELSE
        NEW.level := 0;  -- Root node
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_maintain_taxonomy
    BEFORE INSERT OR UPDATE ON taxonomy
    FOR EACH ROW
    EXECUTE FUNCTION fn_maintain_taxonomy();

-- ============================================================================
-- TRIGGER 4: trg_update_concept_relevance
-- Updates the relevance score of a concept whenever a new document-concept
-- link is created, based on the total number of document associations.
-- ============================================================================
CREATE OR REPLACE FUNCTION fn_update_concept_relevance()
RETURNS TRIGGER AS $$
DECLARE
    v_new_score NUMERIC(5,3);
BEGIN
    SELECT COUNT(*) * 0.5 INTO v_new_score
    FROM document_concepts
    WHERE concept_id = NEW.concept_id;

    UPDATE concepts
    SET relevance_score = LEAST(v_new_score, 10.0)
    WHERE concept_id = NEW.concept_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_concept_relevance
    AFTER INSERT ON document_concepts
    FOR EACH ROW
    EXECUTE FUNCTION fn_update_concept_relevance();

-- ============================================================================
-- TRIGGER 5: trg_log_user_creation
-- Automatically creates an audit log entry when a new user is created.
-- ============================================================================
CREATE OR REPLACE FUNCTION fn_log_user_creation()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details)
    VALUES (NEW.user_id, 'create', 'user', NEW.user_id,
            FORMAT('New user created: %s (%s)', NEW.full_name, NEW.email));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_log_user_creation
    AFTER INSERT ON users
    FOR EACH ROW
    EXECUTE FUNCTION fn_log_user_creation();

-- ============================================================================
-- END OF STORED PROCEDURES & TRIGGERS
-- ============================================================================
