# OmniGraph — Enterprise AI Knowledge Graph

**An AI-powered knowledge intelligence system** that turns unstructured organizational data (reports, emails, code, research) into a queryable semantic graph with RBAC, full-text search, and audit trails.

---

## Overview

- **Target roles**: Backend Engineer · Data/Platform Engineer · ML / Search Engineer
- **Project type**: End-to-end, single-repo system (schema design → backend modules → CLI)
- **Time-saver**: If you only have 2–3 minutes, skim:
  - **Highlights** (next section)
  - **Tech stack**
  - **Project structure** (to see code organization)

---

## Highlights

- **Production-style database design**: 19-table PostgreSQL schema in BCNF with 6 stored procedures, 5 triggers, recursive CTEs, full-text search, and embeddings.
- **Modular Python backend**: Separate modules for ingestion, entity/relationship extraction, graph building, semantic query, and RBAC/audit.
- **Security-first querying**: Every DB call uses parameterized queries via `psycopg2` and is governed by role-based access control with full audit logging.
- **Search & semantics**: Hybrid search that combines full-text, vector similarity, and graph traversal to surface relevant documents and domain experts.

---

## Quick start

```bash
# 1. Create database and load schema
createdb omnigraph
psql -d omnigraph -f sql/schema.sql
psql -d omnigraph -f sql/procedures_triggers.sql
psql -d omnigraph -f sql/sample_data.sql

# 2. Install Python deps and run console
pip install -r requirements.txt
python run.py
```

Default demo user: **priya.sharma**

---

## Tech stack

| Layer      | Technology                  |
|-----------|-----------------------------|
| **Database**  | PostgreSQL 14+              |
| **Backend**   | Python 3.8+                 |
| **DB driver** | psycopg2                    |
| **Search**    | PostgreSQL Full-Text Search |
| **Auth**      | RBAC + audit logs           |

---

## Project structure

```
Omni-Graph/
├── run.py                 # Entry point: run the console app
├── requirements.txt       # Python dependencies
├── README.md
├── sql/                   # Database
│   ├── schema.sql         # 19-table schema
│   ├── procedures_triggers.sql
│   ├── sample_data.sql
│   └── queries.sql        # 15+ advanced SQL examples
└── omnigraph/             # Python package
    ├── __init__.py
    ├── console_app.py     # Interactive CLI
    ├── ingestion_pipeline.py
    ├── entity_relation_extractor.py
    ├── graph_builder.py
    ├── semantic_query_engine.py
    └── access_control_audit.py
```

**Good entry points to review**

- **Database**: `sql/schema.sql`, `sql/procedures_triggers.sql`, `sql/queries.sql`
- **Backend**: `omnigraph/semantic_query_engine.py`, `omnigraph/graph_builder.py`
- **Security**: `omnigraph/access_control_audit.py`, `omnigraph/console_app.py` (prepared statements)

---

## What it does

| Area | Features |
|------|----------|
| **Ingestion** | Document ingest, text normalization, SHA-256 dedup, chunking, versioning |
| **Extraction** | NER (entities), concept tagging, relationship extraction, DB persistence |
| **Graph** | Entity/concept nodes, typed relations, taxonomy, concept hierarchy, graph stats |
| **Search** | Full-text, vector similarity, graph traversal, expert finding, hybrid ranking |
| **Security** | RBAC, permission checks, query + audit logging, sensitive-access reports |

---

## Architecture (high level)

```
┌─────────────────────────────────────────────────────┐
│  Console CLI (Search · Manage Documents · Admin)    │
├─────────────────────────────────────────────────────┤
│  Ingestion → Extraction → Graph Builder → Query     │
│  Access Control & Audit (RBAC, logging)             │
├─────────────────────────────────────────────────────┤
│  PostgreSQL: 19 tables, FTS, embeddings, triggers   │
└─────────────────────────────────────────────────────┘
```

See the diagram in `omnigraph-architecture.drawio` for a visual.

---

## Database at a glance

- **Core**: `users`, `roles`, `user_roles`, `access_policies`, `documents`, `document_versions`, `tags`, `document_tags`
- **Knowledge graph**: `entities`, `relations`, `concepts`, `concept_hierarchy`, `taxonomy`
- **Mappings**: `document_entities`, `document_concepts`, `entity_concepts`, `embeddings`
- **Audit**: `query_logs`, `audit_logs`

Schema is normalized to **BCNF**. SQL files include constraints, indexes, stored procedures, and triggers for realistic behavior (versioning, taxonomy maintenance, audit logging, etc.).

---

## Usage (console)

1. **Search**: Full-text search, hybrid/semantic search, find experts, related concepts, entity neighborhoods.
2. **Manage**: Add/update documents, tag documents, view details, list recent, run entity extraction.
3. **Admin**: Graph stats, taxonomy tree, concept hierarchy, audit trail, sensitive access report, query analytics, role management, read-only custom SQL.

All DB access uses **parameterized queries** (psycopg2 `%s`) to prevent SQL injection.

---

## Skills demonstrated

- **Databases**: Schema design, normalization (BCNF), stored procedures, triggers, recursive CTEs, full-text search.
- **Python**: Modular design, type hints, logging, CLI UX, context managers, defensive error handling.
- **Security**: RBAC, audit trails, least-privilege access patterns, prepared statements.
- **NLP / knowledge**: Entity/concept extraction, relationship extraction, semantic search, graph traversal.

---

## License

[MIT](LICENSE)
