# OmniGraph — Enterprise AI Knowledge Graph Database System

> An AI-powered knowledge intelligence system that models, organizes, and retrieves
> structured insights from unstructured organizational data.

---

## Table of Contents

1. [Project Overview](#project-overview)  
2. [Architecture](#architecture)  
3. [Database Schema](#database-schema)  
4. [ER Diagram](#er-diagram)  
5. [Normalization](#normalization)  
6. [SQL Components](#sql-components)  
7. [Python Modules](#python-modules)  
8. [Console Application](#console-application)  
9. [Setup & Installation](#setup--installation)  
10. [Usage Guide](#usage-guide)  
11. [File Structure](#file-structure)

---

## Project Overview

OmniGraph is an enterprise-grade knowledge graph database system designed to:

- **Ingest** documents from diverse sources (reports, emails, code, research papers)
- **Extract** entities, concepts, and relationships using NLP/NER pipelines
- **Build** a semantic knowledge graph linking documents, entities, and concepts
- **Query** the knowledge base via full-text, semantic, and graph traversal
- **Secure** data access with role-based access control (RBAC)
- **Audit** all queries and access events for compliance

### Technology Stack

| Layer          | Technology                   |
|----------------|------------------------------|
| Database       | PostgreSQL 14+               |
| Backend        | Python 3.8+                  |
| DB Connector   | psycopg2                     |
| Search         | PostgreSQL Full-Text Search   |
| Auth           | RBAC with policies           |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Console Application                 │
│              (console_app.py — CLI UI)               │
├─────────┬───────────┬─────────────┬─────────────────┤
│ Search  │  Manage   │    Admin    │      Audit       │
│ Module  │  Module   │   Module    │     Module       │
├─────────┴───────────┴─────────────┴─────────────────┤
│                   Python Modules                     │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │  Ingestion  │ │  Extraction  │ │    Graph     │  │
│  │  Pipeline   │ │  (NER/RE)    │ │   Builder    │  │
│  └─────────────┘ └──────────────┘ └──────────────┘  │
│  ┌─────────────┐ ┌──────────────┐                   │
│  │  Semantic   │ │   Access     │                   │
│  │  Query Eng. │ │   Control    │                   │
│  └─────────────┘ └──────────────┘                   │
├─────────────────────────────────────────────────────┤
│                 PostgreSQL Database                   │
│  19 Tables · 6 Stored Procedures · 5 Triggers        │
│  Full-Text Search · Embeddings · Audit Logs          │
└─────────────────────────────────────────────────────┘
```

---

## Database Schema

The database uses the `omnigraph` schema and contains **19 tables** organized into 4 groups:

### Core Tables

| Table | Purpose |
|-------|---------|
| `users` | System users with department affiliation |
| `roles` | Role definitions with permission arrays |
| `user_roles` | Many-to-many user-role assignments |
| `access_policies` | RBAC policies per role/resource/sensitivity |
| `documents` | Document storage with metadata and sensitivity |
| `document_versions` | Version history of document content |
| `tags` | Tag definitions |
| `document_tags` | Many-to-many document-tag links |

### Knowledge Graph Tables

| Table | Purpose |
|-------|---------|
| `entities` | Named entities (person, org, technology, etc.) |
| `relations` | Typed relationships between entities |
| `concepts` | Domain concepts (ML, NLP, DevOps, etc.) |
| `concept_hierarchy` | Parent-child concept DAG |
| `taxonomy` | Hierarchical classification tree |

### Mapping Tables

| Table | Purpose |
|-------|---------|
| `document_entities` | Document ↔ Entity links with relevance |
| `document_concepts` | Document ↔ Concept links with scores |
| `entity_concepts` | Entity ↔ Concept associations |
| `embeddings` | Vector embeddings for semantic search |

### Audit Tables

| Table | Purpose |
|-------|---------|
| `query_logs` | Query execution history |
| `audit_logs` | Comprehensive audit trail |

---

## ER Diagram

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│    users     │       │    roles     │       │access_policies│
│──────────────│       │──────────────│       │──────────────│
│ user_id (PK) │───┐   │ role_id (PK) │───┬───│ policy_id(PK)│
│ username     │   │   │ role_name    │   │   │ role_id (FK) │
│ full_name    │   │   │ permissions[]│   │   │ resource_type│
│ department   │   │   └──────────────┘   │   │ can_read     │
│ is_active    │   │                      │   │ can_write    │
└──────────────┘   │   ┌──────────────┐   │   │ can_delete   │
       │           ├───│  user_roles  │───┘   └──────────────┘
       │           │   │──────────────│
       │           │   │ user_id (FK) │
       │           │   │ role_id (FK) │
       │           │   │ assigned_by  │
       │           │   └──────────────┘
       │           │
       │  uploaded_by   ┌──────────────────┐
       ├───────────────→│   documents      │
       │                │──────────────────│
       │                │ document_id (PK) │
       │                │ title            │
       │                │ content          │
       │                │ source_type      │
       │                │ sensitivity_level│
       │                │ tsvector (FTS)   │
       │                └──────────────────┘
       │                   │          │            │
       │    ┌──────────────┤          │            │
       │    │              │          │            │
       │    ▼              ▼          ▼            ▼
 ┌───────────────┐ ┌────────────┐ ┌──────────┐ ┌──────────────┐
 │ doc_versions  │ │ doc_tags   │ │doc_entities│ │doc_concepts │
 │───────────────│ │────────────│ │──────────│ │──────────────│
 │ version_id(PK)│ │doc_id (FK) │ │doc_id(FK)│ │doc_id (FK)  │
 │ doc_id (FK)   │ │tag_id (FK) │ │ent_id(FK)│ │concept_id(FK)│
 │ version_num   │ │tagged_by   │ │relevance │ │relevance_score│
 │ content       │ └────────────┘ └──────────┘ └──────────────┘
 └───────────────┘       │              │              │
                         │              │              │
                    ┌────┘              │              │
                    ▼                   ▼              ▼
              ┌──────────┐     ┌──────────────┐  ┌──────────────┐
              │   tags   │     │   entities   │  │   concepts   │
              │──────────│     │──────────────│  │──────────────│
              │tag_id(PK)│     │entity_id(PK) │  │concept_id(PK)│
              │ name     │     │ name         │  │ name         │
              └──────────┘     │ entity_type  │  │ domain       │
                               │ confidence   │  │ relevance    │
                               └──────────────┘  └──────────────┘
                                  │      ▲              │
                                  │      │              │
                         ┌────────┘      │         ┌────┘
                         ▼               │         ▼
                   ┌──────────────┐      │   ┌────────────────┐
                   │  relations   │      │   │concept_hierarchy│
                   │──────────────│      │   │────────────────│
                   │relation_id(PK)│     │   │parent_id (FK)  │
                   │source_ent(FK)│──────┘   │child_id (FK)   │
                   │target_ent(FK)│          │relationship    │
                   │relation_type │          └────────────────┘
                   │ strength     │
                   └──────────────┘    ┌──────────────┐
                                       │  taxonomy    │
                   ┌──────────────┐    │──────────────│
                   │entity_concepts│   │taxonomy_id(PK)│
                   │──────────────│    │ name         │
                   │entity_id(FK) │    │ parent_id(FK)│──→ self
                   │concept_id(FK)│    │ level        │
                   └──────────────┘    │ domain       │
                                       └──────────────┘
    ┌──────────────┐   ┌──────────────┐
    │  query_logs  │   │  audit_logs  │   ┌──────────────┐
    │──────────────│   │──────────────│   │  embeddings  │
    │ log_id (PK)  │   │audit_id (PK) │   │──────────────│
    │ user_id (FK) │   │ user_id (FK) │   │embedding_id  │
    │ query_text   │   │ action       │   │ source_type  │
    │ query_type   │   │ resource_type│   │ source_id    │
    │ results_count│   │ details      │   │ vector[]     │
    │ execution_ms │   │ ip_address   │   │ model_name   │
    └──────────────┘   └──────────────┘   └──────────────┘
```

### Relationship Summary

| Relationship | Type | Constraint |
|-------------|------|------------|
| users → documents | 1:N | `uploaded_by` FK |
| users ↔ roles | M:N | via `user_roles` |
| roles → access_policies | 1:N | `role_id` FK |
| documents → document_versions | 1:N | `document_id` FK |
| documents ↔ tags | M:N | via `document_tags` |
| documents ↔ entities | M:N | via `document_entities` |
| documents ↔ concepts | M:N | via `document_concepts` |
| entities → entities | M:N | via `relations` (self-join) |
| entities ↔ concepts | M:N | via `entity_concepts` |
| concepts → concepts | M:N | via `concept_hierarchy` (DAG) |
| taxonomy → taxonomy | Self-referential | `parent_id` FK |

---

## Normalization

### Normalization to BCNF — Proof

All 19 tables are normalized to **Boyce-Codd Normal Form (BCNF)**.

#### 1NF Compliance
- All columns contain atomic values (no repeating groups or nested structures)
- The only array type is `permissions[]` in `roles`, which stores a list of atomic strings and is treated as a single attribute
- Every table has a defined primary key

#### 2NF Compliance
- All non-key attributes are fully functionally dependent on the **entire** primary key
- Composite-key tables (`document_entities`, `document_tags`, `user_roles`, etc.) have no partial dependencies — every non-key column depends on the full composite key

#### 3NF Compliance
- No transitive dependencies exist. For example:
  - `documents.uploaded_by` references `users`, but user details (name, department) live in `users`, not duplicated in `documents`
  - `relations.source_entity_id` and `target_entity_id` reference `entities` — entity attributes are not duplicated in `relations`

#### BCNF Compliance
- For every functional dependency X → Y in every table, X is a superkey
- No non-trivial FDs exist where the determinant is not a candidate key
- Example analysis for key tables:

| Table | Candidate Key | All FDs | BCNF? |
|-------|--------------|---------|-------|
| `users` | `{user_id}`, `{username}`, `{email}` | `user_id → all`, `username → all`, `email → all` | ✓ |
| `documents` | `{document_id}` | `document_id → all` | ✓ |
| `entities` | `{entity_id}` | `entity_id → all` | ✓ |
| `document_entities` | `{document_id, entity_id}` | `{doc_id, ent_id} → relevance, mention_count` | ✓ |
| `user_roles` | `{user_id, role_id}` | `{user_id, role_id} → assigned_at, assigned_by` | ✓ |
| `relations` | `{relation_id}` | `relation_id → all` | ✓ |
| `taxonomy` | `{taxonomy_id}` | `taxonomy_id → all` | ✓ |

**All determinants in all FDs are superkeys → BCNF is satisfied.**

---

## SQL Components

### Stored Procedures (6)

| Procedure | Purpose |
|-----------|---------|
| `sp_auto_extract_entities` | Simulates entity extraction on new documents |
| `sp_enforce_access_control` | Validates RBAC permissions for resource actions |
| `sp_archive_old_versions` | Archives old document versions beyond retention limit |
| `sp_find_experts` | Identifies domain experts by document contribution |
| `sp_shortest_path` | BFS shortest path between entities via recursive CTE |
| `sp_concept_network` | Recursive traversal of concept hierarchy |

### Triggers (5)

| Trigger | Event | Purpose |
|---------|-------|---------|
| `trg_audit_sensitive_access` | After SELECT on docs | Logs access to sensitive documents |
| `trg_version_on_update` | Before UPDATE on docs | Auto-creates version snapshot |
| `trg_maintain_taxonomy` | Before INSERT/UPDATE on taxonomy | Computes level, prevents cycles |
| `trg_update_concept_relevance` | After INSERT on doc_concepts | Updates concept relevance scores |
| `trg_log_user_creation` | After INSERT on users | Audit logs new user creation |

### Advanced Queries (15 + 1 Bonus)

The `queries.sql` file demonstrates:
- Multi-table JOINs (3+ tables)
- Aggregation with GROUP BY / HAVING
- Recursive CTEs (entity paths, taxonomy traversal)
- Window functions (RANK, ROW_NUMBER, LAG)
- Self-joins (entity relationships)
- Correlated subqueries
- Full-text search with `ts_rank`
- CASE-based pivots
- Anti-join patterns (LEFT JOIN ... IS NULL)

---

## Python Modules

### 1. `ingestion_pipeline.py`
```
DatabaseConnection → DocumentIngester
                     ├── ingest_document()      — single doc with validation
                     ├── batch_ingest()          — bulk ingestion
                     ├── normalize_text()        — text normalization
                     ├── _compute_hash()         — SHA-256 deduplication
                     ├── chunk_document()        — text chunking
                     └── create_version()        — version management
```

### 2. `entity_relation_extractor.py`
```
EntityRelationExtractor
├── extract_entities()        — keyword/regex NER
├── extract_concepts()        — domain concept identification
├── extract_relationships()   — typed relationship extraction
├── persist_entities()        — save to DB with ON CONFLICT
├── persist_concepts()        — save concepts
├── persist_relationships()   — save relationships
└── process_document()        — full pipeline for one document
```

### 3. `graph_builder.py`
```
KnowledgeGraphBuilder
├── add_entity_node()            — create with dedup
├── remove_entity_node()         — cascading delete
├── add_relationship()           — typed edge creation
├── map_document_entity()        — doc-entity mapping
├── add_taxonomy_node()          — taxonomy management
├── get_taxonomy_tree()          — recursive CTE traversal
├── add_concept_link()           — concept hierarchy DAG
├── get_concept_hierarchy()      — recursive CTE traversal
├── get_entity_neighborhood()    — N-hop graph traversal
├── detect_duplicate_nodes()     — duplicate detection
├── get_graph_stats()            — summary statistics
└── build_graph()                — full construction pipeline
```

### 4. `semantic_query_engine.py`
```
SemanticQueryEngine
├── search()                    — main search API
├── fulltext_search()           — PostgreSQL tsvector/tsquery
├── vector_similarity_search()  — cosine similarity on embeddings
├── graph_traverse()            — multi-hop graph search
├── find_experts()              — domain expert identification
├── find_related_concepts()     — concept co-occurrence analysis
├── get_entity_documents()      — entity-document lookup
├── parse_query()               — NL query parsing
├── rank_results()              — weighted score fusion
└── _hybrid_search()            — combined strategy
```

### 5. `access_control_audit.py`
```
AccessControlManager
├── check_access()               — RBAC permission check
├── validate_permission()        — role-based permission validation
├── get_user_roles()             — user role retrieval
├── get_user_access_matrix()     — full access matrix
├── log_query()                  — query audit logging
├── log_audit()                  — general audit logging
├── get_audit_trail()            — filtered audit retrieval
├── get_sensitive_access_report()— compliance reporting
├── get_query_analytics()        — usage analytics
├── assign_role()                — role assignment
└── revoke_role()                — role revocation
```

---

## Console Application

`console_app.py` provides an interactive menu-driven interface:

```
OmniGraph Console
├── [1] Search & Discover
│   ├── Full-text Search
│   ├── Hybrid/Semantic Search
│   ├── Find Domain Experts
│   ├── Explore Related Concepts
│   ├── Entity Document Lookup
│   └── View Entity Neighborhood
├── [2] Manage Documents
│   ├── Add New Document         (INSERT with prepared stmt)
│   ├── Update Document Metadata (UPDATE with prepared stmt)
│   ├── Tag a Document           (INSERT with ON CONFLICT)
│   ├── View Document Details    (SELECT with prepared stmt)
│   ├── List Recent Documents
│   └── Extract Entities
├── [3] Administration & Audit
│   ├── Graph Statistics
│   ├── Taxonomy Tree
│   ├── Concept Hierarchy
│   ├── Audit Trail
│   ├── Sensitive Access Report
│   ├── Query Analytics
│   ├── User Role Management
│   └── Custom SQL Query (read-only)
└── [0] Exit
```

All database operations use **prepared statements** (`%s` parameterization via psycopg2) to prevent SQL injection.

---

## Setup & Installation

### Prerequisites
- PostgreSQL 14 or later
- Python 3.8+
- `psycopg2` library

### Step 1: Create Database
```bash
createdb omnigraph
```

### Step 2: Initialize Schema
```bash
psql -d omnigraph -f database_schema.sql
psql -d omnigraph -f stored_procedures_triggers.sql
psql -d omnigraph -f sample_data.sql
```

### Step 3: Install Python Dependencies
```bash
pip install psycopg2-binary
```

### Step 4: Run Console Application
```bash
python console_app.py
```

### Step 5: Run Advanced Queries
```bash
psql -d omnigraph -f queries.sql
```

---

## Usage Guide

### Searching Documents
```
1. Launch console_app.py
2. Log in (try username: priya.sharma)
3. Select [1] Search & Discover
4. Select [1] Full-text Search
5. Enter query: "machine learning neural network"
```

### Adding a Document
```
1. Select [2] Manage Documents
2. Select [1] Add New Document
3. Enter title, type, content, sensitivity
4. Document is auto-ingested with deduplication
```

### Viewing Audit Logs
```
1. Select [3] Administration & Audit
2. Select [4] View Audit Trail
3. Requires 'view_audit' permission (admin/compliance roles)
```

---

## File Structure

```
Omni-Graph/
├── database_schema.sql           ← 19-table PostgreSQL schema
├── sample_data.sql               ← Realistic seed data
├── stored_procedures_triggers.sql← 6 procedures + 5 triggers
├── queries.sql                   ← 15+ advanced SQL queries
├── ingestion_pipeline.py         ← Document ingestion module
├── entity_relation_extractor.py  ← NER & relationship extraction
├── graph_builder.py              ← Knowledge graph construction
├── semantic_query_engine.py      ← Multi-strategy query engine
├── access_control_audit.py       ← RBAC & audit module
├── console_app.py                ← Interactive CLI application
└── README.md                     ← This documentation
```

---

> **OmniGraph** — Turning unstructured knowledge into actionable intelligence.