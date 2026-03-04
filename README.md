# OmniGraph

Enterprise knowledge graph system that ingests organizational documents, extracts entities/concepts/relationships, and supports secure retrieval through full-text, semantic, and graph-based search.

## What This Project Includes

- PostgreSQL schema with 19 tables (BCNF-oriented design), indexes, constraints, stored procedures, and triggers
- Python package for ingestion, extraction, graph operations, search, RBAC, and audit
- Interactive console application for search, document management, and admin/audit workflows
- Optional LangGraph-based RAG workflow on top of the same retrieval and access-control layers

## Repository Layout

```text
Omni-Graph/
├── exec.py
├── requirements.txt
├── README.md
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
    └── rag_workflow.py
```

## Prerequisites

- Python 3.10+
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

- `agarwal.priya`
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

### 6. Optional RAG Workflow (`omnigraph/rag_workflow.py`)

- LangGraph state workflow: retrieve -> generate
- Reuses `SemanticQueryEngine` and `AccessControlManager`
- Accepts a LangChain-compatible LLM (`llm.invoke(...)`)

## Console Menu Overview

Main menus in `omnigraph/console_app.py`:

1. `Search & Discover`
- Full-text search
- Hybrid/semantic search
- Find experts
- Explore related concepts
- Entity-based document lookup
- Entity neighborhood view

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
