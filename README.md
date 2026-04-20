# OmniGraph

Enterprise knowledge graph system that ingests organizational documents, extracts entities/concepts/relationships, and supports secure retrieval through full-text, semantic, and graph-based search. An agentic retrieval-augmented generation (RAG) workflow built with Voyage AI Embeddings sits on top of these primitives as the core query interface.

## Repository Layout

```text
Omni-Graph/
├── exec.py
├── requirements.txt
├── README.md
├── database-schema.jpeg
├── sql/
│   ├── schema.sql
│   ├── sample_data.sql
│   ├── procedures_triggers.sql
│   └── queries.sql
└── omnigraph/
    ├── __init__.py
    ├── ingestion_pipeline.py
    ├── entity_relation_extractor.py
    ├── graph_builder.py
    ├── semantic_query_engine.py
    ├── access_control_audit.py
    ├── console_app.py
    └── agentic_rag.py
```

## Prerequisites

- Python 3.14+
- PostgreSQL 14+
- `pip`

## Setup

1. Create and initialize the database.

```bash
createdb omnigraph
psql -d omnigraph -f sql/schema.sql
psql -d omnigraph -f sql/sample_data.sql
psql -d omnigraph -f sql/procedures_triggers.sql
```

2. Install Python dependencies.

```bash
python -m pip install -r requirements.txt
```

3. Run the console app.

```bash
python exec.py
```

## Login and Database Credentials

At startup, the console prompts for DB connection values and a username.

- DB defaults used by the app: `localhost:5432`, database `omnigraph`, user `postgres`
- DB password behavior:
  - If entered at prompt, that value is used
  - If left blank, the app falls back to `OMNIGRAPH_DB_PASSWORD` (or `postgres`)
- Supported env vars for `DatabaseConnection`:
  - `OMNIGRAPH_DB_USER`
  - `OMNIGRAPH_DB_PASSWORD`

Sample usernames (from `sql/sample_data.sql`):

- `albert.cheng`
- `chen.wei`
- `johnson.mark`
- `martinez.sofia`
- `okafor.emeka`
- `tanaka.yuki`
- `williams.alex`
- `kumar.rahul`
- `fischer.anna`
- `brown.david`

Note: console authentication currently validates active username only (no password verification in app logic).

## Database schema

All tables live in the PostgreSQL schema `omnigraph`. The full DDL (constraints, indexes, `CHECK` enums) is in [`sql/schema.sql`](sql/schema.sql).

### ER diagram (reference)

The diagram file must sit **next to this README** at the repository root as `database-schema.jpeg` so GitHub, GitLab, and local Markdown previews can resolve the path.

<p align="center">
  <img
    src="./database-schema.jpeg"
    alt="OmniGraph database schema ER diagram: omnigraph tables, keys, and relationships"
    width="920"
  />
</p>

### Tables (19)

| Table | Purpose |
|-------|---------|
| `roles` | Role definitions and permission arrays (`TEXT[]`). |
| `users` | User accounts and profile fields. |
| `user_roles` | Many-to-many assignment of roles to users. |
| `access_policies` | Per-role rules on `resource_type` × `sensitivity_level` (`can_read` / `can_write` / `can_delete`). |
| `taxonomy` | Hierarchical taxonomy nodes (`parent_id` self-reference, `level`, `domain`). |
| `documents` | Core documents: content, `content_hash`, `source_type`, `sensitivity_level`, `taxonomy_id`, `uploaded_by`, `is_archived`, FTS via GIN on title+content. |
| `document_versions` | Version history per document (`version_number`, content snapshot, `changed_by`). |
| `entities` | Graph nodes: `name`, `entity_type`, optional description/canonical metadata, `confidence`. |
| `concepts` | Topic nodes: `name`, `domain`, optional `taxonomy_id`, `relevance_score`. |
| `tags` | Tag dictionary for document classification. |
| `relations` | Directed edges between entities (`relation_type`, `strength`, optional `source_document_id`). |
| `document_entities` | Links documents to entities (`relevance`, `mention_count`, `first_occurrence`). |
| `document_tags` | Links documents to tags (`tagged_by`, `tagged_at`). |
| `concept_hierarchy` | Parent/child edges between concepts (`relationship_type`). |
| `entity_concepts` | Links entities to concepts (`relevance_score`). |
| `document_concepts` | Links documents to concepts (`relevance_score`, `extracted_by`: system/manual/ai). |
| `embeddings` | Vector storage per `source_type` (document/entity/concept) + `source_id` and `model_name` (`FLOAT[]`, unique per triple). |
| `query_logs` | Search/query telemetry (`query_type`, `results_count`, `execution_ms`). |
| `audit_logs` | Security audit events (`action`, `resource_type`, optional `resource_id`, `details`). |

### Relationships (summary)

- **Users ↔ roles**: `user_roles`.
- **Documents**: belong to `taxonomy`, uploaded by `users`; versions in `document_versions`; linked to `entities`, `tags`, and `concepts` via junction tables.
- **Graph**: `entities` connected by `relations`; `concepts` structured by `concept_hierarchy`; `entity_concepts` and `document_concepts` attach concepts to entities and documents.
- **Semantic search**: `embeddings` rows reference logical sources by `(source_type, source_id)`.
- **Governance**: `access_policies` drives RBAC checks; `query_logs` and `audit_logs` support observability.

## Core Capabilities

### 1. Ingestion (`omnigraph/ingestion_pipeline.py`)

- Text normalization
- SHA-256 deduplication via `content_hash`
- Document insert + metadata handling
- Version creation for duplicate content or updates
- Batch ingestion helpers

### 2. Entity/Concept/Relation Extraction (`omnigraph/entity_relation_extractor.py`)

- Pattern/keyword-based NER
- Concept extraction with domain tagging and relevance scores
- Regex relationship extraction (e.g., `works_for`, `depends_on`, `uses`)
- Persistence into entity/concept/relation mapping tables

### 3. Graph Management (`omnigraph/graph_builder.py`)

- Entity node and relation creation/removal
- Taxonomy tree operations
- Concept hierarchy operations
- Neighborhood exploration and graph statistics

### 4. Retrieval (`omnigraph/semantic_query_engine.py`)

- Full-text search (PostgreSQL `tsvector` / `tsquery`)
- Vector similarity search over stored embeddings (`FLOAT[]`)
- Graph traversal search through entity links/relations
- Hybrid ranking across retrieval modes
- Expert lookup and related-concept discovery

### 5. Security and Audit (`omnigraph/access_control_audit.py`)

- Role-based access control (RBAC)
- Sensitivity-aware permission checks
- Query logging (`query_logs`)
- Audit logging (`audit_logs`)
- Reports for sensitive access and query analytics

### 6. Agentic RAG — Core Retrieval Path (`omnigraph/agentic_rag.py`)

- **Anthropic SDK agent** with native tool-use loop and streaming as the primary way to query the knowledge graph.
- **Retrieval-only tools**: `hybrid_search`, `find_experts`, `get_entity_documents`, `find_related_concepts`, and `get_document_content` (all respect RBAC).
- Console **Search & Discover** leads with **Ask (Agent)**; set `ANTHROPIC_API_KEY` to use.

## Console Menu Overview

Main menus in `omnigraph/console_app.py`:

1. `Search & Discover`
- **Ask (Agent)** — natural-language retrieval over the graph (agentic RAG)
- Full-text search
- Hybrid/semantic search
- Find experts
- Explore related concepts
- Entity-based document lookup
- Entity neighborhood view
- Entity path lookup

Agent question examples:

```text
What documents explain Kubernetes deployment?
Who are the experts on Deep Learning?
What concepts are related to Machine Learning?
Which documents mention PostgreSQL?
```

Entity neighborhood and path lookup accept entity names as well as numeric IDs. If a name matches multiple entities, the console shows candidates and asks which ID to use.

2. `Manage Documents`
- Add document
- Update document metadata
- Tag document
- View document detail
- List recent documents
- Run extraction on a document

3. `Administration & Audit`
- Graph stats and structure views
- Audit trail and sensitive access report
- Query analytics
- Role assignment/revocation
- Custom read-only SQL (SELECT/CTE with safety checks)

## SQL Assets

- `sql/schema.sql`: full schema and indexes
- `sql/sample_data.sql`: demo roles/users/documents/entities/concepts/etc.
- `sql/procedures_triggers.sql`: 6 stored procedures + 5 triggers
- `sql/queries.sql`: advanced SQL examples (joins, recursive CTEs, window functions, full-text)

## Important Notes

- Run order matters: `schema.sql` -> `sample_data.sql` -> `procedures_triggers.sql`.
- The README in older revisions referenced `run.py`; current entrypoint is `exec.py`.
- Some admin console features require permissions like `view_graph`, but sample role permission arrays do not include `view_graph` by default. If needed, update role permissions in `omnigraph.roles.permissions`.

Example fix:

```sql
UPDATE omnigraph.roles
SET permissions = array_append(permissions, 'view_graph')
WHERE role_name = 'admin'
  AND NOT ('view_graph' = ANY(permissions));
```

## Minimal Programmatic Usage

```python
from omnigraph import DatabaseConnection, DocumentIngester, SemanticQueryEngine

# Connect
db = DatabaseConnection(host="localhost", port=5432, dbname="omnigraph", user="postgres", password="postgres")
db.connect()

# Ingest
ingester = DocumentIngester(db)
document_id = ingester.ingest_document(
    title="My Document",
    source_type="technical_doc",
    content="Kubernetes uses containers and works with Docker.",
    uploaded_by=1,
    sensitivity_level="internal",
)

# Search
engine = SemanticQueryEngine(db, user_id=1)
results = engine.search("Kubernetes Docker", strategy="hybrid", limit=5)

print(document_id, len(results))
db.disconnect()
```

## License

MIT License. See [LICENSE](LICENSE).
