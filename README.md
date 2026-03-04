# OmniGraph — Enterprise AI Knowledge Graph

**An AI-powered knowledge intelligence system** that turns unstructured organizational data (reports, emails, code, research) into a queryable semantic graph with role-based access control (RBAC), full-text search, and audit trails.

---

## Highlights

- **Production-style database design**: 19-table PostgreSQL schema in Boyce–Codd normal form (BCNF) with 6 stored procedures, 5 triggers, recursive common table expressions (CTEs), full-text search, and embeddings.
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

Default demo user: **admin**

---

## Tech stack

| Layer      | Technology                  |
|-----------|-----------------------------|
| **Database**  | PostgreSQL 14+              |
| **Backend**   | Python 3.8+                 |
| **DB driver** | psycopg2                    |
| **Search**    | PostgreSQL Full-Text Search |
| **Auth**      | Role-based access control (RBAC) + audit logs |
| **RAG / LLM** | LangGraph + LangChain-compatible chat models  |

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
| **Security** | Role-based access control (RBAC), permission checks, query + audit logging, sensitive-access reports |

---

## Implementation details (Python modules)

- **`omnigraph/ingestion_pipeline.py`**  
  - `DatabaseConnection`: Thin psycopg2 wrapper that reads credentials from `OMNIGRAPH_DB_USER` / `OMNIGRAPH_DB_PASSWORD` when not passed explicitly, with lazy reconnection.  
  - `DocumentIngester`: Implements document ingest (normalize → hash → dedup → insert), batch ingestion, and document versioning; each method manages its own transaction boundary and rolls back on failure.

- **`omnigraph/entity_relation_extractor.py`**  
  - `EntityRelationExtractor`: Pattern-based NER and relation extraction using keyword dictionaries, compiled relationship regexes, and a person-name pattern.  
  - Optimized implementations: single-pass keyword matching over all keywords, batched person extraction without repeated `text.count`, and a small fuzzy-matching helper for mapping relationship spans back to known entities.  
  - Persists entities, concepts, and relationships into `entities`, `concepts`, `document_entities`, `document_concepts`, and `relations` via best-effort, per-stage transactions.

- **`omnigraph/graph_builder.py`**  
  - `KnowledgeGraphBuilder`: Programmatic graph management — add/remove entities, add relationships, attach entities to documents, add taxonomy nodes and concept hierarchy links.  
  - Read operations: recursive CTEs for taxonomy and concept hierarchy, neighborhood queries, duplicate detection, and aggregate graph statistics.  
  - Each mutating method wraps its own commit/rollback so calls are atomic at the operation level.

- **`omnigraph/semantic_query_engine.py`**  
  - `SemanticQueryEngine`: Unified search layer with full-text (`tsvector`/`tsquery`), vector similarity (hash-based demo embeddings), graph traversal, and hybrid search.  
  - `search()`: Parses query intent, delegates to the appropriate strategy, then deduplicates and re-ranks results with per-source weights. Hybrid search fetches more candidates per modality and then applies a global limit.  
  - `graph_traverse()`: Uses entity/relationship hops to find related documents, with guardrails on regex construction to avoid pathological patterns.

- **`omnigraph/access_control_audit.py`**  
  - `AccessControlManager`: Central RBAC layer that evaluates per-resource access policies based on roles and sensitivity level, logs query and audit events, and exposes helpers for user roles, access matrix, and analytics.  
  - All permission checks and audit logging for the console and search engine go through this module.

- **`omnigraph/console_app.py`**  
  - `OmniGraphConsole`: Menu-driven CLI that wires together ingestion, extraction, graph building, semantic query, and access control.  
  - Enforces access control on document reads/writes and graph introspection, and restricts the custom SQL console to admin users with defense-in-depth checks (SELECT/CTE-only, keyword filters, query/audit logging).  
  - Provides the primary user experience for search, document management, audit viewing, and role management.

- **`omnigraph/__init__.py`**  
  - Package facade that exports the main building blocks (`DatabaseConnection`, `DocumentIngester`, `EntityRelationExtractor`, `KnowledgeGraphBuilder`, `SemanticQueryEngine`, `AccessControlManager`) for direct library-style use.

- **`omnigraph/rag_workflow.py`**  
  - `OmniGraphRAG`: A LangGraph-based retrieval-augmented generation (RAG) workflow that:
    - Uses `SemanticQueryEngine` to perform hybrid retrieval (full-text + semantic + graph).
    - Applies `AccessControlManager` checks to filter out documents the user cannot read.
    - Calls a provided LangChain-compatible chat model to generate answers using retrieved context.  
  - **Recruiter lens**: Shows how I would integrate an existing search/graph stack into an LLM orchestration framework (LangGraph), keeping the model layer pluggable and respecting existing security constraints.

---

## Architecture (high level)

```
┌─────────────────────────────────────────────────────┐
│  Console CLI (Search · Manage Documents · Admin)    │
├─────────────────────────────────────────────────────┤
│  Ingestion → Extraction → Graph Builder → Query     │
│  Access Control & Audit (role-based access control, logging) │
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

Schema is normalized to **Boyce–Codd normal form (BCNF)**. SQL files include constraints, indexes, stored procedures, and triggers for realistic behavior (versioning, taxonomy maintenance, audit logging, etc.).

---

## Usage (console)

1. **Search**: Full-text search, hybrid/semantic search, find experts, related concepts, entity neighborhoods.
2. **Manage**: Add/update documents, tag documents, view details, list recent, run entity extraction.
3. **Admin**: Graph stats, taxonomy tree, concept hierarchy, audit trail, sensitive access report, query analytics, role management, read-only custom SQL.

All DB access uses **parameterized queries** (psycopg2 `%s`) to prevent SQL injection.

---

## Skills demonstrated

- **Databases**: Schema design, normalization (Boyce–Codd normal form, BCNF), stored procedures, triggers, recursive common table expressions (CTEs), full-text search.
- **Python**: Modular design, type hints, logging, command-line interface (CLI) user experience (UX), context managers, defensive error handling.
- **Security**: Role-based access control (RBAC), audit trails, least-privilege access patterns, prepared statements.
- **Natural language processing (NLP) / knowledge**: Entity/concept extraction, relationship extraction, semantic search, graph traversal.

---

## License

[MIT](LICENSE)
