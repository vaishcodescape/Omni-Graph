# OmniGraph

**An enterprise-grade knowledge graph and agentic RAG platform built on PostgreSQL, pgvector, and Anthropic Claude.**

OmniGraph ingests organizational documents, extracts entities / concepts / relationships into a queryable graph, and exposes retrieval through a hybrid search engine (full-text + vector + graph traversal) fronted by an Anthropic tool-use agent. Designed around production concerns: RBAC, sensitivity tiers, audit trails, versioning, and deterministic deduplication.

---

## Highlights

- **Hybrid retrieval engine** — Postgres full-text search (`tsvector` + GIN), 1024-dim Voyage AI vector similarity, and graph traversal unified behind a single weighted ranker.
- **Agentic RAG** — Anthropic Claude agent with a native tool-use loop exposing five RBAC-gated retrieval tools (`hybrid_search`, `find_experts`, `get_entity_documents`, `find_related_concepts`, `get_document_content`).
- **Relational knowledge graph** — 19-table PostgreSQL schema modeling documents, entities, concepts, relations, taxonomies, and user/role access policies.
- **Deterministic ingestion** — Text normalization → SHA-256 deduplication → versioned writes → async embedding with UPSERT semantics on `(source_type, source_id, model_name)`.
- **Enterprise security model** — Role-based access control joined with per-row sensitivity levels (`public` / `internal` / `confidential` / `restricted`); every query is filtered post-retrieval and logged to audit tables.
- **Database-first design** — 6 stored procedures and 5 triggers enforce invariants (FTS refresh, timestamping, audit emission) in SQL rather than application code.

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Language | Python 3.10+ |
| Database | PostgreSQL 14+ |
| Vector store | `pgvector` (1024-dim, cosine) |
| Embeddings | Voyage AI — `voyage-3` |
| LLM Agent | Anthropic Claude (tool-use + streaming) |
| Driver | `psycopg2` |
| Interface | ANSI-rendered terminal console |

---

## Architecture at a Glance

```text
                ┌──────────────────────────────────────────────┐
                │            OmniGraph Console (TUI)           │
                └──────────────────────────────────────────────┘
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        ▼                            ▼                            ▼
┌───────────────┐          ┌──────────────────┐          ┌────────────────┐
│   Ingestion   │          │  Agentic RAG     │          │  Admin / Audit │
│   Pipeline    │          │  (Claude agent)  │          │                │
└───────┬───────┘          └─────────┬────────┘          └────────┬───────┘
        │                            │                            │
        ▼                            ▼                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│             Semantic Query Engine  +  Access Control Layer           │
│         (Full-Text  │  Vector Similarity  │  Graph Traversal)        │
└──────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│                 PostgreSQL  —  schema: omnigraph                     │
│   documents · entities · concepts · relations · embeddings · roles   │
│   access_policies · taxonomy · audit_logs · query_logs · + more      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow — From Raw Text to Graph

```text
raw text
  → normalize (strip control chars, collapse whitespace)
  → SHA-256 content hash → dedupe probe
      ├─ hit  → insert new row in document_versions
      └─ miss → insert into documents (FTS tsvector trigger fires)
              → Voyage AI embed → upsert into embeddings (pgvector)
              → extract:
                  ├─ keyword / regex NER  → entities + document_entities
                  ├─ concept dict scan    → concepts + document_concepts
                  └─ regex relation mine  → relations (entity → entity edges)
```

Every stage is idempotent: hash-based dedup on write, `ON CONFLICT` upserts on graph edges, and stable embedding keys `(source_type, source_id, model_name)`.

---

## Core Modules

| Module | Responsibility |
| --- | --- |
| [`ingestion_pipeline.py`](omnigraph/ingestion_pipeline.py) | Normalization, SHA-256 dedup, versioning, batch ingest, embedding persistence |
| [`entity_relation_extractor.py`](omnigraph/entity_relation_extractor.py) | Pattern-based NER (technology / organization / standard / person), concept extraction with domain tagging, relation mining via 9 regex patterns |
| [`graph_builder.py`](omnigraph/graph_builder.py) | Entity / relation CRUD, taxonomy trees, concept hierarchies, neighborhood exploration, graph statistics |
| [`semantic_query_engine.py`](omnigraph/semantic_query_engine.py) | Full-text, vector, graph, and hybrid search strategies with weighted ranking |
| [`access_control_audit.py`](omnigraph/access_control_audit.py) | RBAC enforcement, sensitivity checks, query + audit logging, analytics |
| [`agentic_rag.py`](omnigraph/agentic_rag.py) | Anthropic tool-use agent; orchestrates retrieval tools with RBAC filtering |
| [`embedder.py`](omnigraph/embedder.py) | Thin Voyage AI client wrapper |
| [`console_app.py`](omnigraph/console_app.py) | ANSI terminal UI with three functional menus |

---

## Database Schema — 19 Tables

All objects live in schema `omnigraph`. Full DDL (constraints, indexes, `CHECK` enums) in [`sql/schema.sql`](sql/schema.sql).

<p align="center">
  <img
    src="./database-schema.jpeg"
    alt="OmniGraph database schema ER diagram"
    width="920"
  />
</p>

**Identity & Access**: `roles` · `users` · `user_roles` · `access_policies`
**Content**: `documents` · `document_versions` · `taxonomy` · `tags` · `document_tags`
**Knowledge Graph**: `entities` · `relations` · `concepts` · `concept_hierarchy` · `entity_concepts` · `document_entities` · `document_concepts`
**Semantic Layer**: `embeddings` (vector storage indexed by `source_type` + `source_id`)
**Observability**: `query_logs` · `audit_logs`

Key design decisions:

- **Polymorphic embeddings** — One `embeddings` table spans documents, entities, and concepts via `(source_type, source_id)`, enabling semantic search across all graph nodes uniformly.
- **Directed relations** — `relations(source_entity_id, target_entity_id, relation_type, strength, source_document_id)` preserves provenance back to the document that generated each edge.
- **Row-level sensitivity** — `documents.sensitivity_level` is the final authority; every retrieval is re-checked against `access_policies` at read time, not just at write time.

---

## Retrieval Strategies

| Strategy | Mechanism | When to use |
| --- | --- | --- |
| `fulltext` | PostgreSQL `tsvector` / `tsquery` over `title + content`, GIN-indexed | Exact keyword matches, acronyms |
| `semantic` | Voyage `voyage-3` query embedding → pgvector nearest neighbor | Natural-language intent, paraphrases |
| `graph` | Traverse `document_entities → entities → relations → entities → document_entities` | "What else is connected to X?" |
| `hybrid` (default) | All three, blended with weights `{fulltext: 1.0, semantic: 1.2, graph: 0.8}` | Most production queries |

Every result is post-filtered through `AccessControlManager.check_access` before returning to the caller or agent.

---

## Quick Start

```bash
# 1. Initialize the database
createdb omnigraph
psql -d omnigraph -f sql/schema.sql
psql -d omnigraph -f sql/sample_data.sql
psql -d omnigraph -f sql/procedures_triggers.sql

# 2. Install dependencies
python -m pip install -r requirements.txt

# 3. Set credentials
export VOYAGE_API_KEY=...
export ANTHROPIC_API_KEY=...
export OMNIGRAPH_DB_USER=postgres
export OMNIGRAPH_DB_PASSWORD=postgres

# 4. Launch the console
python exec.py
```

---

## Programmatic Usage

```python
from omnigraph import DatabaseConnection, DocumentIngester, SemanticQueryEngine

db = DatabaseConnection(host="localhost", dbname="omnigraph")
db.connect()

# Ingest — handles normalization, dedup, embedding, and versioning
ingester = DocumentIngester(db)
doc_id = ingester.ingest_document(
    title="Container Orchestration Primer",
    source_type="technical_doc",
    content="Kubernetes orchestrates Docker containers across clusters...",
    uploaded_by=1,
    sensitivity_level="internal",
)

# Retrieve — hybrid strategy, RBAC-filtered
engine = SemanticQueryEngine(db, user_id=1)
results = engine.search("container orchestration", strategy="hybrid", limit=5)
```

---

## Console Capabilities

**Search & Discover**
Ask (Agent) · Full-text search · Hybrid / semantic search · Find experts · Explore related concepts · Entity-based document lookup · Entity neighborhood view · Entity path lookup

**Manage Documents**
Add · Update metadata · Tag · View detail · List recent · Run extraction

**Administration & Audit**
Graph stats · Structure views · Audit trail · Sensitive-access report · Query analytics · Role assignment / revocation · Read-only SQL sandbox (SELECT / CTE with safety checks)

### Sample agent queries

```text
What documents explain Kubernetes deployment?
Who are the experts on Deep Learning?
What concepts are related to Machine Learning?
Which documents mention PostgreSQL?
```

---

## Engineering Practices Demonstrated

- **Separation of concerns** — Retrieval, access control, and orchestration are distinct modules; the agent composes them rather than reimplementing them.
- **SQL-as-contract** — Invariants (timestamping, FTS maintenance, audit emission) are enforced by triggers and stored procedures, not ad-hoc application code.
- **Idempotent writes** — Hash dedup, `ON CONFLICT` upserts, and stable embedding keys make the pipeline safe to re-run.
- **Graceful degradation** — Embedding failures are logged but do not roll back document writes; FTS and graph retrieval remain functional.
- **Provenance** — Every extracted relation stores `source_document_id`, making the graph auditable back to source text.
- **Observability by default** — `query_logs` captures latency and result counts per strategy; `audit_logs` captures every sensitive access.

---

## Repository Layout

```text
Omni-Graph/
├── exec.py                              # Entrypoint
├── requirements.txt
├── database-schema.jpeg                 # ER diagram
├── sql/
│   ├── schema.sql                       # 19 tables, constraints, indexes
│   ├── sample_data.sql                  # Seed roles / users / documents
│   ├── procedures_triggers.sql          # 6 procs + 5 triggers
│   ├── retrieval.sql                    # Advanced retrieval queries
│   └── queries.sql                      # Recursive CTEs, window functions, FTS examples
└── omnigraph/
    ├── ingestion_pipeline.py
    ├── entity_relation_extractor.py
    ├── graph_builder.py
    ├── semantic_query_engine.py
    ├── access_control_audit.py
    ├── agentic_rag.py
    ├── embedder.py
    └── console_app.py
```

---

## Configuration Reference

| Env var | Purpose |
| --- | --- |
| `OMNIGRAPH_DB_USER` | PostgreSQL user (default `postgres`) |
| `OMNIGRAPH_DB_PASSWORD` | PostgreSQL password |
| `VOYAGE_API_KEY` | Required for embedding + semantic search |
| `ANTHROPIC_API_KEY` | Required for the agentic RAG loop |

Sample usernames seeded by `sample_data.sql`: `agarwal.priya`, `chen.wei`, `johnson.mark`, `martinez.sofia`, `okafor.emeka`, `tanaka.yuki`, `williams.alex`, `kumar.rahul`, `fischer.anna`, `brown.david`.

---

## Notes

- Initialization order is significant: `schema.sql` → `sample_data.sql` → `procedures_triggers.sql`.
- Some admin views require the `view_graph` permission, which is not in the seed role arrays by default:

```sql
UPDATE omnigraph.roles
SET permissions = array_append(permissions, 'view_graph')
WHERE role_name = 'admin'
  AND NOT ('view_graph' = ANY(permissions));
```

---

## License

MIT — see [LICENSE](LICENSE).
