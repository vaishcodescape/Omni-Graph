-- ============================================================================
-- OmniGraph: Enterprise AI Knowledge Graph Database System
-- Database Schema Definition (PostgreSQL)
-- ============================================================================
-- This DDL script creates the complete OmniGraph schema with:
--   - 18 tables normalized to BCNF
--   - Many-to-many relationship tables
--   - Hierarchical / self-referencing structures
--   - Composite keys, foreign keys, CHECK constraints
--   - Indexes for query performance
-- ============================================================================

-- Drop existing database objects if they exist
DROP SCHEMA IF EXISTS omnigraph CASCADE;
CREATE SCHEMA omnigraph;
SET search_path TO omnigraph;

-- ============================================================================
-- 1. ROLES
-- Stores system roles: Consumer, Contributor, Expert, Admin, Compliance
-- FD: role_id → role_name, description, permissions
-- ============================================================================
CREATE TABLE roles (
    role_id         SERIAL          PRIMARY KEY,
    role_name       VARCHAR(50)     NOT NULL UNIQUE,
    description     TEXT,
    permissions     TEXT[]          NOT NULL DEFAULT '{}',
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 2. USERS
-- System users with authentication and profile info
-- FD: user_id → username, email, full_name, ...
-- ============================================================================
CREATE TABLE users (
    user_id         SERIAL          PRIMARY KEY,
    username        VARCHAR(100)    NOT NULL UNIQUE,
    email           VARCHAR(255)    NOT NULL UNIQUE,
    full_name       VARCHAR(255)    NOT NULL,
    department      VARCHAR(150),
    title           VARCHAR(150),
    password_hash   VARCHAR(512)    NOT NULL,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login      TIMESTAMP
);

-- ============================================================================
-- 3. USER_ROLES  (Many-to-Many: users ↔ roles)
-- FD: (user_id, role_id) → assigned_at, assigned_by
-- ============================================================================
CREATE TABLE user_roles (
    user_id         INTEGER         NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role_id         INTEGER         NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
    assigned_at     TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    assigned_by     INTEGER         REFERENCES users(user_id),
    PRIMARY KEY (user_id, role_id)
);

-- ============================================================================
-- 4. ACCESS_POLICIES
-- Row-level access policies per role for document sensitivity levels
-- FD: policy_id → role_id, resource_type, sensitivity_level, ...
-- ============================================================================
CREATE TABLE access_policies (
    policy_id           SERIAL      PRIMARY KEY,
    role_id             INTEGER     NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
    resource_type       VARCHAR(50) NOT NULL CHECK (resource_type IN ('document', 'entity', 'concept', 'audit_log')),
    sensitivity_level   VARCHAR(30) NOT NULL CHECK (sensitivity_level IN ('public', 'internal', 'confidential', 'restricted')),
    can_read            BOOLEAN     NOT NULL DEFAULT FALSE,
    can_write           BOOLEAN     NOT NULL DEFAULT FALSE,
    can_delete          BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (role_id, resource_type, sensitivity_level)
);

-- ============================================================================
-- 5. TAXONOMY
-- Hierarchical taxonomy nodes (self-referencing tree)
-- FD: taxonomy_id → name, description, parent_id, level, domain
-- ============================================================================
CREATE TABLE taxonomy (
    taxonomy_id     SERIAL          PRIMARY KEY,
    name            VARCHAR(200)    NOT NULL,
    description     TEXT,
    parent_id       INTEGER         REFERENCES taxonomy(taxonomy_id) ON DELETE SET NULL,
    level           INTEGER         NOT NULL DEFAULT 0 CHECK (level >= 0),
    domain          VARCHAR(100),
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (name, parent_id)
);

CREATE INDEX idx_taxonomy_parent ON taxonomy(parent_id);
CREATE INDEX idx_taxonomy_domain ON taxonomy(domain);

-- ============================================================================
-- 6. DOCUMENTS
-- Core document records with metadata
-- FD: document_id → title, source_type, content, sensitivity_level, ...
-- ============================================================================
CREATE TABLE documents (
    document_id         SERIAL          PRIMARY KEY,
    title               VARCHAR(500)    NOT NULL,
    source_type         VARCHAR(50)     NOT NULL CHECK (source_type IN (
                            'report', 'research_paper', 'email', 'technical_doc',
                            'code_repository', 'project_artifact', 'presentation',
                            'support_ticket', 'log', 'other'
                        )),
    content             TEXT            NOT NULL,
    summary             TEXT,
    content_hash        VARCHAR(128)    NOT NULL,
    file_path           VARCHAR(1000),
    file_size_bytes     BIGINT          CHECK (file_size_bytes >= 0),
    mime_type           VARCHAR(100),
    language            VARCHAR(20)     DEFAULT 'en',
    sensitivity_level   VARCHAR(30)     NOT NULL DEFAULT 'internal'
                        CHECK (sensitivity_level IN ('public', 'internal', 'confidential', 'restricted')),
    taxonomy_id         INTEGER         REFERENCES taxonomy(taxonomy_id) ON DELETE SET NULL,
    uploaded_by         INTEGER         NOT NULL REFERENCES users(user_id),
    is_archived         BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_documents_source      ON documents(source_type);
CREATE INDEX idx_documents_sensitivity ON documents(sensitivity_level);
CREATE INDEX idx_documents_taxonomy    ON documents(taxonomy_id);
CREATE INDEX idx_documents_uploaded_by ON documents(uploaded_by);
CREATE INDEX idx_documents_hash        ON documents(content_hash);
CREATE INDEX idx_documents_created     ON documents(created_at);

-- Full-text search index
CREATE INDEX idx_documents_fts ON documents USING GIN (
    to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, ''))
);

-- ============================================================================
-- 7. DOCUMENT_VERSIONS
-- Version history for documents
-- FD: version_id → document_id, version_number, content, changed_by, ...
-- ============================================================================
CREATE TABLE document_versions (
    version_id      SERIAL          PRIMARY KEY,
    document_id     INTEGER         NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    version_number  INTEGER         NOT NULL CHECK (version_number > 0),
    content         TEXT            NOT NULL,
    content_hash    VARCHAR(128)    NOT NULL,
    change_summary  TEXT,
    changed_by      INTEGER         NOT NULL REFERENCES users(user_id),
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_id, version_number)
);

CREATE INDEX idx_docversions_document ON document_versions(document_id);

-- ============================================================================
-- 8. ENTITIES
-- Named entities extracted from documents (people, orgs, tech, locations)
-- FD: entity_id → name, entity_type, description, ...
-- ============================================================================
CREATE TABLE entities (
    entity_id       SERIAL          PRIMARY KEY,
    name            VARCHAR(300)    NOT NULL,
    entity_type     VARCHAR(50)     NOT NULL CHECK (entity_type IN (
                        'person', 'organization', 'technology', 'location',
                        'product', 'event', 'standard', 'other'
                    )),
    description     TEXT,
    canonical_name  VARCHAR(300),
    source_url      VARCHAR(1000),
    confidence      NUMERIC(4,3)    CHECK (confidence >= 0 AND confidence <= 1),
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (name, entity_type)
);

CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entities_name ON entities(name);

-- ============================================================================
-- 9. CONCEPTS
-- Knowledge concepts / topics
-- FD: concept_id → name, domain, description, ...
-- ============================================================================
CREATE TABLE concepts (
    concept_id      SERIAL          PRIMARY KEY,
    name            VARCHAR(200)    NOT NULL UNIQUE,
    domain          VARCHAR(100),
    description     TEXT,
    taxonomy_id     INTEGER         REFERENCES taxonomy(taxonomy_id) ON DELETE SET NULL,
    relevance_score NUMERIC(5,3)    DEFAULT 0.0 CHECK (relevance_score >= 0),
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_concepts_domain   ON concepts(domain);
CREATE INDEX idx_concepts_taxonomy ON concepts(taxonomy_id);

-- ============================================================================
-- 10. TAGS
-- Classification tags for documents
-- FD: tag_id → name, category
-- ============================================================================
CREATE TABLE tags (
    tag_id          SERIAL          PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL UNIQUE,
    category        VARCHAR(100),
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 11. RELATIONS
-- Typed relationships between entities
-- FD: relation_id → source_entity_id, target_entity_id, relation_type, ...
-- ============================================================================
CREATE TABLE relations (
    relation_id         SERIAL          PRIMARY KEY,
    source_entity_id    INTEGER         NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    target_entity_id    INTEGER         NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    relation_type       VARCHAR(100)    NOT NULL CHECK (relation_type IN (
                            'works_for', 'collaborates_with', 'authored', 'uses',
                            'located_in', 'part_of', 'depends_on', 'related_to',
                            'manages', 'developed_by', 'competitor_of', 'successor_of'
                        )),
    strength            NUMERIC(4,3)    DEFAULT 1.0 CHECK (strength >= 0 AND strength <= 1),
    description         TEXT,
    source_document_id  INTEGER         REFERENCES documents(document_id) ON DELETE SET NULL,
    created_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (source_entity_id != target_entity_id)
);

CREATE INDEX idx_relations_source ON relations(source_entity_id);
CREATE INDEX idx_relations_target ON relations(target_entity_id);
CREATE INDEX idx_relations_type   ON relations(relation_type);

-- ============================================================================
-- 12. DOCUMENT_ENTITIES  (Many-to-Many: documents ↔ entities)
-- FD: (document_id, entity_id) → relevance, mention_count, first_occurrence
-- ============================================================================
CREATE TABLE document_entities (
    document_id         INTEGER     NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    entity_id           INTEGER     NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    relevance           NUMERIC(4,3)    DEFAULT 1.0 CHECK (relevance >= 0 AND relevance <= 1),
    mention_count       INTEGER     NOT NULL DEFAULT 1 CHECK (mention_count > 0),
    first_occurrence    INTEGER     CHECK (first_occurrence >= 0),
    PRIMARY KEY (document_id, entity_id)
);

-- ============================================================================
-- 13. DOCUMENT_TAGS  (Many-to-Many: documents ↔ tags)
-- FD: (document_id, tag_id) → tagged_by, tagged_at
-- ============================================================================
CREATE TABLE document_tags (
    document_id     INTEGER     NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    tag_id          INTEGER     NOT NULL REFERENCES tags(tag_id) ON DELETE CASCADE,
    tagged_by       INTEGER     REFERENCES users(user_id),
    tagged_at       TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (document_id, tag_id)
);

-- ============================================================================
-- 14. CONCEPT_HIERARCHY  (Many-to-Many self-referencing: concept ↔ concept)
-- Parent-child concept graph supporting DAG structures
-- FD: (parent_concept_id, child_concept_id) → relationship_type
-- ============================================================================
CREATE TABLE concept_hierarchy (
    parent_concept_id   INTEGER     NOT NULL REFERENCES concepts(concept_id) ON DELETE CASCADE,
    child_concept_id    INTEGER     NOT NULL REFERENCES concepts(concept_id) ON DELETE CASCADE,
    relationship_type   VARCHAR(50) NOT NULL DEFAULT 'is_parent_of'
                        CHECK (relationship_type IN ('is_parent_of', 'is_specialization_of', 'is_prerequisite_of')),
    created_at          TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (parent_concept_id, child_concept_id),
    CHECK (parent_concept_id != child_concept_id)
);

-- ============================================================================
-- 15. ENTITY_CONCEPTS  (Many-to-Many: entities ↔ concepts)
-- FD: (entity_id, concept_id) → relevance_score
-- ============================================================================
CREATE TABLE entity_concepts (
    entity_id       INTEGER         NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    concept_id      INTEGER         NOT NULL REFERENCES concepts(concept_id) ON DELETE CASCADE,
    relevance_score NUMERIC(4,3)    DEFAULT 1.0 CHECK (relevance_score >= 0 AND relevance_score <= 1),
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (entity_id, concept_id)
);

-- ============================================================================
-- 16. DOCUMENT_CONCEPTS  (Many-to-Many: documents ↔ concepts)
-- FD: (document_id, concept_id) → relevance_score, extracted_by
-- ============================================================================
CREATE TABLE document_concepts (
    document_id     INTEGER         NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    concept_id      INTEGER         NOT NULL REFERENCES concepts(concept_id) ON DELETE CASCADE,
    relevance_score NUMERIC(4,3)    DEFAULT 1.0 CHECK (relevance_score >= 0 AND relevance_score <= 1),
    extracted_by    VARCHAR(50)     DEFAULT 'system' CHECK (extracted_by IN ('system', 'manual', 'ai')),
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (document_id, concept_id)
);

-- ============================================================================
-- 17. EMBEDDINGS
-- Vector embeddings for semantic similarity search
-- FD: embedding_id → source_type, source_id, model_name, vector, ...
-- ============================================================================
CREATE TABLE embeddings (
    embedding_id    SERIAL          PRIMARY KEY,
    source_type     VARCHAR(30)     NOT NULL CHECK (source_type IN ('document', 'entity', 'concept')),
    source_id       INTEGER         NOT NULL,
    model_name      VARCHAR(100)    NOT NULL DEFAULT 'text-embedding-ada-002',
    vector          FLOAT[]         NOT NULL,
    dimensions      INTEGER         NOT NULL CHECK (dimensions > 0),
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_type, source_id, model_name)
);

CREATE INDEX idx_embeddings_source ON embeddings(source_type, source_id);

-- ============================================================================
-- 18. QUERY_LOGS
-- Audit trail for all user queries
-- FD: log_id → user_id, query_text, query_type, results_count, ...
-- ============================================================================
CREATE TABLE query_logs (
    log_id          SERIAL          PRIMARY KEY,
    user_id         INTEGER         NOT NULL REFERENCES users(user_id),
    query_text      TEXT            NOT NULL,
    query_type      VARCHAR(50)     NOT NULL CHECK (query_type IN (
                        'keyword_search', 'semantic_search', 'graph_traversal',
                        'analytics', 'admin', 'export'
                    )),
    results_count   INTEGER         DEFAULT 0 CHECK (results_count >= 0),
    execution_ms    INTEGER         CHECK (execution_ms >= 0),
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_querylogs_user    ON query_logs(user_id);
CREATE INDEX idx_querylogs_created ON query_logs(created_at);

-- ============================================================================
-- 19. AUDIT_LOGS
-- Sensitive-access audit trail
-- FD: audit_id → user_id, action, resource_type, resource_id, ...
-- ============================================================================
CREATE TABLE audit_logs (
    audit_id        SERIAL          PRIMARY KEY,
    user_id         INTEGER         NOT NULL REFERENCES users(user_id),
    action          VARCHAR(50)     NOT NULL CHECK (action IN (
                        'view', 'create', 'update', 'delete', 'export',
                        'access_denied', 'login', 'logout'
                    )),
    resource_type   VARCHAR(50)     NOT NULL CHECK (resource_type IN (
                        'document', 'entity', 'concept', 'user', 'role', 'policy', 'system'
                    )),
    resource_id     INTEGER,
    details         TEXT,
    ip_address      VARCHAR(45),
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_auditlogs_user     ON audit_logs(user_id);
CREATE INDEX idx_auditlogs_action   ON audit_logs(action);
CREATE INDEX idx_auditlogs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_auditlogs_created  ON audit_logs(created_at);

-- ============================================================================
-- END OF SCHEMA
-- Total: 19 tables, 6 junction/relationship tables, 25+ indexes
-- All tables normalized to BCNF (see README for proofs)
-- ============================================================================
