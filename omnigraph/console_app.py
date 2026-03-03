"""
OmniGraph: Enterprise AI Knowledge Graph Database System
========================================================
Module: Interactive Console Application

Menu-driven console application that provides interactive access to
the OmniGraph knowledge base. Supports searching, document management,
user administration, and audit reporting — all via prepared statements.

Author: OmniGraph Team
"""

import getpass
import logging
import sys
from datetime import datetime
from typing import Optional

import psycopg2

from .ingestion_pipeline import DatabaseConnection, DocumentIngester
from .entity_relation_extractor import EntityRelationExtractor
from .graph_builder import KnowledgeGraphBuilder
from .semantic_query_engine import SemanticQueryEngine
from .access_control_audit import AccessControlManager

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("omnigraph.console")

# ---------------------------------------------------------------------------
# Display Helpers
# ---------------------------------------------------------------------------
SEPARATOR = "═" * 70
THIN_SEP = "─" * 70


def clear_screen():
    """Print enough newlines to simulate a screen clear."""
    print("\n" * 2)


def print_header(title: str):
    """Print a formatted section header."""
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def print_table(headers: list, rows: list, widths: Optional[list] = None):
    """
    Print a formatted ASCII table.

    Parameters
    ----------
    headers : list of str
        Column headers.
    rows : list of list
        Table rows.
    widths : list of int, optional
        Column widths. Auto-computed if None.
    """
    if not rows:
        print("  (No results)")
        return

    if widths is None:
        widths = []
        for i, h in enumerate(headers):
            col_max = max(
                len(str(h)),
                max((len(str(r[i])) for r in rows if i < len(r)), default=0),
            )
            widths.append(min(col_max + 2, 50))

    # Header
    header_line = "  ".join(
        str(h).ljust(w) for h, w in zip(headers, widths)
    )
    print(f"  {header_line}")
    print(f"  {'  '.join('─' * w for w in widths)}")

    # Rows
    for row in rows:
        row_line = "  ".join(
            str(row[i] if i < len(row) else "").ljust(w)[:w]
            for i, w in enumerate(widths)
        )
        print(f"  {row_line}")


def prompt_int(message: str, default: Optional[int] = None) -> Optional[int]:
    """Prompt user for an integer input."""
    suffix = f" [{default}]" if default is not None else ""
    try:
        val = input(f"  {message}{suffix}: ").strip()
        if not val and default is not None:
            return default
        return int(val)
    except (ValueError, EOFError):
        return default


def prompt_str(message: str, default: str = "") -> str:
    """Prompt user for a string input."""
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"  {message}{suffix}: ").strip()
        return val if val else default
    except EOFError:
        return default


# ===========================================================================
# Console Application
# ===========================================================================

class OmniGraphConsole:
    """
    Interactive console application for OmniGraph.

    Provides menu-driven access for:
    - Search: documents, experts, concepts
    - Manage: add/update documents, manage tags
    - Admin: users, roles, audit logs, graph stats
    """

    def __init__(self):
        self.db = None
        self.ingester = None
        self.extractor = None
        self.graph_builder = None
        self.query_engine = None
        self.access_manager = None
        self.current_user_id = None
        self.current_username = None

    # ------------------------------------------------------------------
    # Connection & Setup
    # ------------------------------------------------------------------

    def connect(
        self,
        host: str = "localhost",
        port: int = 5432,
        dbname: str = "omnigraph",
        user: str = "postgres",
        password: str = "postgres",
    ):
        """Establish database connection and initialize modules."""
        self.db = DatabaseConnection(host, port, dbname, user, password)
        self.db.connect()
        self.ingester = DocumentIngester(self.db)
        self.extractor = EntityRelationExtractor(self.db)
        self.graph_builder = KnowledgeGraphBuilder(self.db)
        self.access_manager = AccessControlManager(self.db)

    def authenticate(self) -> bool:
        """Simple authentication against the users table."""
        print_header("OmniGraph — Login")
        username = prompt_str("Username")
        if not username:
            return False

        cur = self.db.conn.cursor()
        cur.execute(
            """
            SELECT user_id, full_name FROM omnigraph.users
            WHERE username = %s AND is_active = TRUE
            """,
            (username,),
        )
        row = cur.fetchone()
        if row:
            self.current_user_id = row[0]
            self.current_username = row[1]
            self.query_engine = SemanticQueryEngine(
                self.db, user_id=self.current_user_id,
            )
            # Log login
            self.access_manager.log_audit(
                user_id=self.current_user_id,
                action="login",
                resource_type="system",
                details=f"Console login: {username}",
            )
            print(f"\n  Welcome, {self.current_username}!\n")
            return True
        else:
            print("\n  ✗ User not found or inactive.\n")
            return False

    # ------------------------------------------------------------------
    # Main Menu
    # ------------------------------------------------------------------

    def run(self):
        """Main application loop."""
        print_header("OmniGraph — Enterprise Knowledge Graph")
        print("  An AI-powered knowledge intelligence system\n")

        # Connection setup
        host = prompt_str("Database host", "localhost")
        port = prompt_int("Database port", 5432)
        dbname = prompt_str("Database name", "omnigraph")
        db_user = prompt_str("Database user", "postgres")
        db_pass = prompt_str("Database password", "postgres")

        try:
            self.connect(host, port, dbname, db_user, db_pass)
        except Exception as exc:
            print(f"\n  ✗ Connection failed: {exc}")
            return

        # Authenticate
        if not self.authenticate():
            print("  Exiting.\n")
            return

        # Main menu loop
        while True:
            self._print_main_menu()
            choice = prompt_str("Select option")

            if choice == "1":
                self._search_menu()
            elif choice == "2":
                self._manage_menu()
            elif choice == "3":
                self._admin_menu()
            elif choice == "0" or choice.lower() in ("q", "quit", "exit"):
                self.access_manager.log_audit(
                    user_id=self.current_user_id,
                    action="logout",
                    resource_type="system",
                    details="Console logout",
                )
                print("\n  Goodbye!\n")
                break
            else:
                print("  Invalid option. Please try again.")

        self.db.disconnect()

    def _print_main_menu(self):
        """Display main menu."""
        print(f"\n{THIN_SEP}")
        print(f"  Logged in as: {self.current_username}")
        print(THIN_SEP)
        print("  [1] Search & Discover")
        print("  [2] Manage Documents")
        print("  [3] Administration & Audit")
        print("  [0] Exit")
        print(THIN_SEP)

    # ------------------------------------------------------------------
    # 1. Search & Discover Menu
    # ------------------------------------------------------------------

    def _search_menu(self):
        """Search and discovery sub-menu."""
        while True:
            print_header("Search & Discover")
            print("  [1] Search Documents (Full-text)")
            print("  [2] Search Documents (Hybrid/Semantic)")
            print("  [3] Find Domain Experts")
            print("  [4] Explore Related Concepts")
            print("  [5] Entity Document Lookup")
            print("  [6] View Entity Neighborhood")
            print("  [0] Back")
            print(THIN_SEP)

            choice = prompt_str("Select option")

            if choice == "1":
                self._fulltext_search()
            elif choice == "2":
                self._hybrid_search()
            elif choice == "3":
                self._find_experts()
            elif choice == "4":
                self._related_concepts()
            elif choice == "5":
                self._entity_documents()
            elif choice == "6":
                self._entity_neighborhood()
            elif choice == "0":
                break

    def _fulltext_search(self):
        """Execute full-text search."""
        print_header("Full-Text Search")
        query = prompt_str("Search query")
        if not query:
            return

        results = self.query_engine.search(query, strategy="fulltext", limit=10)

        if results:
            headers = ["ID", "Title", "Type", "Score", "Author"]
            rows = [
                [
                    r["document_id"],
                    r["title"][:40],
                    r["source_type"],
                    f"{r['score']:.3f}",
                    r.get("author", ""),
                ]
                for r in results
            ]
            print_table(headers, rows, [6, 42, 16, 8, 20])
        else:
            print("  No results found.")

    def _hybrid_search(self):
        """Execute hybrid (fulltext + semantic + graph) search."""
        print_header("Hybrid Search")
        query = prompt_str("Search query")
        if not query:
            return

        results = self.query_engine.search(query, strategy="hybrid", limit=10)

        if results:
            headers = ["ID", "Title", "Type", "Score", "Sources"]
            rows = [
                [
                    r["document_id"],
                    r["title"][:35],
                    r["source_type"],
                    f"{r['score']:.3f}",
                    ", ".join(r.get("sources", [])),
                ]
                for r in results
            ]
            print_table(headers, rows, [6, 37, 16, 8, 25])
        else:
            print("  No results found.")

    def _find_experts(self):
        """Find domain experts by concept."""
        print_header("Find Domain Experts")
        concept = prompt_str("Concept name (e.g., Deep Learning)")
        if not concept:
            return

        experts = self.query_engine.find_experts(concept)

        if experts:
            headers = ["Name", "Department", "Title", "Docs", "Score"]
            rows = [
                [
                    e["full_name"],
                    e["department"],
                    e["title"][:25],
                    e["doc_count"],
                    f"{e['expertise_score']:.1f}",
                ]
                for e in experts
            ]
            print_table(headers, rows, [22, 16, 27, 6, 8])
        else:
            print(f"  No experts found for '{concept}'.")

    def _related_concepts(self):
        """Explore concepts related to a given concept."""
        print_header("Related Concepts")
        concept = prompt_str("Concept name (e.g., Machine Learning)")
        if not concept:
            return

        related = self.query_engine.find_related_concepts(concept)

        if related:
            headers = ["Concept", "Domain", "Relation", "Strength"]
            rows = [
                [
                    c["name"],
                    c["domain"],
                    c["relationship_types"],
                    c["connection_strength"],
                ]
                for c in related
            ]
            print_table(headers, rows, [28, 16, 25, 10])
        else:
            print(f"  No related concepts found for '{concept}'.")

    def _entity_documents(self):
        """Retrieve documents linked to an entity."""
        print_header("Entity Document Lookup")
        entity = prompt_str("Entity name (e.g., Kubernetes)")
        if not entity:
            return

        docs = self.query_engine.get_entity_documents(entity)

        if docs:
            headers = ["ID", "Title", "Type", "Relevance", "Mentions"]
            rows = [
                [
                    d["document_id"],
                    d["title"][:40],
                    d["source_type"],
                    f"{d['relevance']:.3f}",
                    d["mention_count"],
                ]
                for d in docs
            ]
            print_table(headers, rows, [6, 42, 16, 10, 10])
        else:
            print(f"  No documents found for entity '{entity}'.")

    def _entity_neighborhood(self):
        """View entity neighborhood graph."""
        print_header("Entity Neighborhood")
        entity_id = prompt_int("Entity ID")
        if entity_id is None:
            return
        depth = prompt_int("Max depth", 2)

        neighbors = self.graph_builder.get_entity_neighborhood(entity_id, depth)

        if neighbors:
            headers = ["ID", "Name", "Type", "Relation", "Strength", "Depth"]
            rows = [
                [
                    n["entity_id"],
                    n["name"],
                    n["entity_type"],
                    n["relation_type"],
                    f"{n['strength']:.3f}",
                    n["depth"],
                ]
                for n in neighbors
            ]
            print_table(headers, rows, [6, 22, 14, 18, 10, 6])
        else:
            print(f"  No neighbors found for entity #{entity_id}.")

    # ------------------------------------------------------------------
    # 2. Manage Documents Menu
    # ------------------------------------------------------------------

    def _manage_menu(self):
        """Document management sub-menu."""
        while True:
            print_header("Manage Documents")
            print("  [1] Add New Document")
            print("  [2] Update Document Metadata")
            print("  [3] Tag a Document")
            print("  [4] View Document Details")
            print("  [5] List Recent Documents")
            print("  [6] Extract Entities from Document")
            print("  [0] Back")
            print(THIN_SEP)

            choice = prompt_str("Select option")

            if choice == "1":
                self._add_document()
            elif choice == "2":
                self._update_document()
            elif choice == "3":
                self._tag_document()
            elif choice == "4":
                self._view_document()
            elif choice == "5":
                self._list_documents()
            elif choice == "6":
                self._extract_entities()
            elif choice == "0":
                break

    def _add_document(self):
        """Add a new document (INSERT with prepared statement)."""
        print_header("Add New Document")

        title = prompt_str("Title")
        if not title:
            return

        print("  Source types: report, research_paper, email, technical_doc,")
        print("    code_repository, project_artifact, presentation,")
        print("    support_ticket, log, other")
        source_type = prompt_str("Source type", "technical_doc")

        content = prompt_str("Content (paste text)")
        if not content:
            print("  Content is required.")
            return

        print("  Sensitivity: public, internal, confidential, restricted")
        sensitivity = prompt_str("Sensitivity level", "internal")

        summary = prompt_str("Summary (optional)")

        doc_id = self.ingester.ingest_document(
            title=title,
            source_type=source_type,
            content=content,
            uploaded_by=self.current_user_id,
            sensitivity_level=sensitivity,
            summary=summary if summary else None,
        )

        if doc_id:
            print(f"\n  ✓ Document created successfully (ID: {doc_id})")
            self.access_manager.log_audit(
                user_id=self.current_user_id,
                action="create",
                resource_type="document",
                resource_id=doc_id,
                details=f"Created document: {title}",
            )
        else:
            print("\n  ✗ Failed to create document.")

    def _update_document(self):
        """Update document metadata (UPDATE with prepared statement)."""
        print_header("Update Document Metadata")

        doc_id = prompt_int("Document ID")
        if doc_id is None:
            return

        # Check access
        if not self.access_manager.check_access(
            self.current_user_id, "document", doc_id, "write",
        ):
            print("  ✗ Access denied.")
            return

        print("  Leave blank to keep current value.")
        new_title = prompt_str("New title")
        new_summary = prompt_str("New summary")
        new_sensitivity = prompt_str("New sensitivity level")

        # Build UPDATE dynamically using prepared statement
        updates = []
        params = []
        if new_title:
            updates.append("title = %s")
            params.append(new_title)
        if new_summary:
            updates.append("summary = %s")
            params.append(new_summary)
        if new_sensitivity:
            updates.append("sensitivity_level = %s")
            params.append(new_sensitivity)

        if not updates:
            print("  No changes specified.")
            return

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(doc_id)

        cur = self.db.conn.cursor()
        try:
            cur.execute(
                f"UPDATE omnigraph.documents SET {', '.join(updates)} "
                f"WHERE document_id = %s",
                params,
            )
            self.db.conn.commit()

            if cur.rowcount > 0:
                print(f"\n  ✓ Document #{doc_id} updated successfully.")
                self.access_manager.log_audit(
                    user_id=self.current_user_id,
                    action="update",
                    resource_type="document",
                    resource_id=doc_id,
                    details=f"Updated metadata for document #{doc_id}",
                )
            else:
                print(f"\n  ✗ Document #{doc_id} not found.")
        except psycopg2.Error as exc:
            self.db.conn.rollback()
            print(f"\n  ✗ Update failed: {exc}")

    def _tag_document(self):
        """Add a tag to a document."""
        print_header("Tag a Document")

        doc_id = prompt_int("Document ID")
        if doc_id is None:
            return
        tag_name = prompt_str("Tag name")
        if not tag_name:
            return

        cur = self.db.conn.cursor()
        try:
            # Get or create tag
            cur.execute(
                """
                INSERT INTO omnigraph.tags (name)
                VALUES (%s)
                ON CONFLICT (name) DO NOTHING
                RETURNING tag_id
                """,
                (tag_name.lower(),),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    "SELECT tag_id FROM omnigraph.tags WHERE name = %s",
                    (tag_name.lower(),),
                )
                row = cur.fetchone()
            tag_id = row[0]

            # Link tag to document
            cur.execute(
                """
                INSERT INTO omnigraph.document_tags (document_id, tag_id, tagged_by)
                VALUES (%s, %s, %s)
                ON CONFLICT (document_id, tag_id) DO NOTHING
                """,
                (doc_id, tag_id, self.current_user_id),
            )
            self.db.conn.commit()
            print(f"\n  ✓ Tag '{tag_name}' added to document #{doc_id}.")
        except psycopg2.Error as exc:
            self.db.conn.rollback()
            print(f"\n  ✗ Tagging failed: {exc}")

    def _view_document(self):
        """View detailed document information (SELECT with prepared statement)."""
        print_header("Document Details")

        doc_id = prompt_int("Document ID")
        if doc_id is None:
            return

        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                SELECT d.document_id, d.title, d.source_type,
                       d.sensitivity_level, d.created_at, d.updated_at,
                       u.full_name AS author, d.file_size_bytes,
                       LEFT(d.summary, 300) AS summary,
                       LEFT(d.content, 500) AS content_preview
                FROM omnigraph.documents d
                JOIN omnigraph.users u ON u.user_id = d.uploaded_by
                WHERE d.document_id = %s
                """,
                (doc_id,),
            )
            row = cur.fetchone()
            if not row:
                print(f"  Document #{doc_id} not found.")
                return

            print(f"\n  ID:           {row[0]}")
            print(f"  Title:        {row[1]}")
            print(f"  Type:         {row[2]}")
            print(f"  Sensitivity:  {row[3]}")
            print(f"  Created:      {row[4]}")
            print(f"  Updated:      {row[5]}")
            print(f"  Author:       {row[6]}")
            print(f"  Size:         {row[7]:,} bytes" if row[7] else "  Size:         N/A")
            if row[8]:
                print(f"  Summary:      {row[8]}")
            print(f"\n  Content Preview:\n  {row[9]}...")

            # Tags
            cur.execute(
                """
                SELECT t.name FROM omnigraph.document_tags dt
                JOIN omnigraph.tags t ON t.tag_id = dt.tag_id
                WHERE dt.document_id = %s ORDER BY t.name
                """,
                (doc_id,),
            )
            tags = [r[0] for r in cur.fetchall()]
            if tags:
                print(f"\n  Tags: {', '.join(tags)}")

            # Linked entities
            cur.execute(
                """
                SELECT e.name, e.entity_type, de.mention_count
                FROM omnigraph.document_entities de
                JOIN omnigraph.entities e ON e.entity_id = de.entity_id
                WHERE de.document_id = %s
                ORDER BY de.relevance DESC LIMIT 10
                """,
                (doc_id,),
            )
            entities = cur.fetchall()
            if entities:
                print("\n  Linked Entities:")
                for ent in entities:
                    print(f"    [{ent[1]}] {ent[0]} ({ent[2]} mentions)")

        except psycopg2.Error as exc:
            print(f"  ✗ Error: {exc}")

    def _list_documents(self):
        """List recent documents."""
        print_header("Recent Documents")
        limit = prompt_int("Number of documents", 15)

        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                SELECT d.document_id, d.title, d.source_type,
                       d.sensitivity_level, u.full_name, d.created_at::DATE
                FROM omnigraph.documents d
                JOIN omnigraph.users u ON u.user_id = d.uploaded_by
                WHERE d.is_archived = FALSE
                ORDER BY d.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
            headers = ["ID", "Title", "Type", "Sensitivity", "Author", "Date"]
            display_rows = [
                [r[0], str(r[1])[:35], r[2], r[3], r[4], str(r[5])]
                for r in rows
            ]
            print_table(headers, display_rows, [6, 37, 16, 14, 20, 12])

        except psycopg2.Error as exc:
            print(f"  ✗ Error: {exc}")

    def _extract_entities(self):
        """Run entity extraction on a document."""
        print_header("Entity Extraction")

        doc_id = prompt_int("Document ID")
        if doc_id is None:
            return

        print("  Running extraction pipeline...")
        result = self.extractor.process_document(doc_id)

        print(f"\n  Entities found:       {len(result['entities'])}")
        print(f"  Concepts identified:  {len(result['concepts'])}")
        print(f"  Relationships found:  {len(result['relationships'])}")

        if result["entities"]:
            print("\n  Top Entities:")
            for e in result["entities"][:10]:
                print(f"    [{e['entity_type']}] {e['name']} "
                      f"(confidence={e['confidence']})")

    # ------------------------------------------------------------------
    # 3. Administration & Audit Menu
    # ------------------------------------------------------------------

    def _admin_menu(self):
        """Administration and audit sub-menu."""
        while True:
            print_header("Administration & Audit")
            print("  [1] View Graph Statistics")
            print("  [2] View Taxonomy Tree")
            print("  [3] View Concept Hierarchy")
            print("  [4] View Audit Trail")
            print("  [5] Sensitive Access Report")
            print("  [6] Query Analytics")
            print("  [7] User Role Management")
            print("  [8] Run Custom SQL Query")
            print("  [0] Back")
            print(THIN_SEP)

            choice = prompt_str("Select option")

            if choice == "1":
                self._graph_stats()
            elif choice == "2":
                self._taxonomy_tree()
            elif choice == "3":
                self._concept_hierarchy()
            elif choice == "4":
                self._audit_trail()
            elif choice == "5":
                self._sensitive_report()
            elif choice == "6":
                self._query_analytics()
            elif choice == "7":
                self._role_management()
            elif choice == "8":
                self._custom_query()
            elif choice == "0":
                break

    def _graph_stats(self):
        """Display knowledge graph statistics."""
        print_header("Knowledge Graph Statistics")

        stats = self.graph_builder.get_graph_stats()

        print(f"  Total Documents:      {stats.get('total_documents', 0)}")
        print(f"  Total Entities:       {stats.get('total_entities', 0)}")
        print(f"  Total Relations:      {stats.get('total_relations', 0)}")
        print(f"  Total Concepts:       {stats.get('total_concepts', 0)}")
        print(f"  Total Taxonomy Nodes: {stats.get('total_taxonomy_nodes', 0)}")

        entities_by_type = stats.get("entities_by_type", {})
        if entities_by_type:
            print("\n  Entities by Type:")
            for etype, count in entities_by_type.items():
                print(f"    {etype}: {count}")

        relations_by_type = stats.get("relations_by_type", {})
        if relations_by_type:
            print("\n  Relations by Type:")
            for rtype, count in relations_by_type.items():
                print(f"    {rtype}: {count}")

    def _taxonomy_tree(self):
        """Display taxonomy hierarchy."""
        print_header("Taxonomy Tree")
        root = prompt_str("Root node name (blank for all)")

        tree = self.graph_builder.get_taxonomy_tree(root if root else None)

        for node in tree:
            indent = "  " * node["level"]
            print(f"  {indent}├── {node['name']} "
                  f"[{node.get('domain', '')}] (id={node['taxonomy_id']})")

    def _concept_hierarchy(self):
        """Display concept hierarchy."""
        print_header("Concept Hierarchy")
        root = prompt_str("Root concept (e.g., Machine Learning)")
        if not root:
            return

        hierarchy = self.graph_builder.get_concept_hierarchy(root)

        for node in hierarchy:
            indent = "  " * node["depth"]
            parent = f" ← {node['parent_name']}" if node["parent_name"] else ""
            print(f"  {indent}├── {node['name']} [{node['domain']}]{parent}")

    def _audit_trail(self):
        """View audit log entries."""
        print_header("Audit Trail")

        # Permission check
        if not self.access_manager.validate_permission(
            self.current_user_id, "view_audit",
        ):
            print("  ✗ Access denied. Requires 'view_audit' permission.")
            return

        days = prompt_int("Look back days", 30)
        limit = prompt_int("Max results", 20)

        trail = self.access_manager.get_audit_trail(days=days, limit=limit)

        if trail:
            headers = ["Time", "User", "Action", "Resource", "Details"]
            rows = [
                [
                    str(e["timestamp"])[:19],
                    e["user"],
                    e["action"],
                    f"{e['resource_type']}#{e.get('resource_id', '')}",
                    str(e.get("details", ""))[:30],
                ]
                for e in trail
            ]
            print_table(headers, rows, [20, 18, 14, 16, 32])
        else:
            print("  No audit entries found.")

    def _sensitive_report(self):
        """Generate sensitive document access report."""
        print_header("Sensitive Document Access Report")

        if not self.access_manager.validate_permission(
            self.current_user_id, "view_audit",
        ):
            print("  ✗ Access denied. Requires 'view_audit' permission.")
            return

        days = prompt_int("Look back days", 30)
        report = self.access_manager.get_sensitive_access_report(days)

        if report:
            headers = ["Time", "User", "Action", "Document", "Sensitivity"]
            rows = [
                [
                    str(e["timestamp"])[:19],
                    e["user"],
                    e["action"],
                    str(e.get("document", ""))[:30],
                    e["sensitivity"],
                ]
                for e in report
            ]
            print_table(headers, rows, [20, 18, 10, 32, 14])
        else:
            print("  No sensitive access events found.")

    def _query_analytics(self):
        """Display query usage analytics."""
        print_header("Query Analytics")

        days = prompt_int("Analysis period (days)", 30)
        analytics = self.access_manager.get_query_analytics(days)

        if analytics.get("by_type"):
            print("\n  Query Type Breakdown:")
            headers = ["Type", "Count", "Avg Time (ms)", "Avg Results"]
            rows = [
                [
                    q["query_type"],
                    q["count"],
                    f"{q['avg_execution_ms']:.0f}",
                    f"{q['avg_results']:.0f}",
                ]
                for q in analytics["by_type"]
            ]
            print_table(headers, rows, [20, 8, 16, 14])

        if analytics.get("top_users"):
            print("\n  Top Users by Query Count:")
            for u in analytics["top_users"]:
                print(f"    {u['user']}: {u['query_count']} queries")

    def _role_management(self):
        """View and manage user roles."""
        print_header("User Role Management")

        if not self.access_manager.validate_permission(
            self.current_user_id, "manage_users",
        ):
            print("  ✗ Access denied. Requires 'manage_users' permission.")
            return

        print("  [1] View user roles")
        print("  [2] Assign role to user")
        print("  [3] Revoke role from user")
        choice = prompt_str("Select")

        if choice == "1":
            user_id = prompt_int("User ID")
            if user_id is None:
                return
            roles = self.access_manager.get_user_roles(user_id)
            if roles:
                for r in roles:
                    print(f"    {r['role_name']}: {r['permissions']}")
            else:
                print("    No roles assigned.")

        elif choice == "2":
            user_id = prompt_int("User ID")
            role_id = prompt_int("Role ID (1=admin, 2=contributor, 3=consumer, 4=expert, 5=compliance)")
            if user_id and role_id:
                success = self.access_manager.assign_role(
                    user_id, role_id, self.current_user_id,
                )
                print("  ✓ Role assigned." if success else "  ✗ Failed.")

        elif choice == "3":
            user_id = prompt_int("User ID")
            role_id = prompt_int("Role ID")
            if user_id and role_id:
                success = self.access_manager.revoke_role(
                    user_id, role_id, self.current_user_id,
                )
                print("  ✓ Role revoked." if success else "  ✗ Failed.")

    def _custom_query(self):
        """Execute a custom SQL SELECT query (read-only)."""
        print_header("Custom SQL Query")
        print("  Enter a SELECT query (read-only). Type 'done' on a new line to execute.")

        lines = []
        while True:
            line = prompt_str(">")
            if line.lower() == "done":
                break
            lines.append(line)

        query = " ".join(lines).strip()
        if not query:
            return

        # Safety: only allow SELECT
        if not query.upper().startswith("SELECT"):
            print("  ✗ Only SELECT queries are allowed.")
            return

        cur = self.db.conn.cursor()
        try:
            cur.execute(query)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchall()

            if columns and rows:
                display_rows = [
                    [str(v)[:40] for v in row]
                    for row in rows[:50]
                ]
                print_table(columns, display_rows)
                print(f"\n  ({len(rows)} rows returned)")
            else:
                print("  Query returned no results.")

        except psycopg2.Error as exc:
            print(f"  ✗ Query error: {exc}")
            try:
                self.db.conn.rollback()
            except Exception:
                pass


# ===========================================================================
# Entry Point
# ===========================================================================
if __name__ == "__main__":
    console = OmniGraphConsole()
    try:
        console.run()
    except KeyboardInterrupt:
        print("\n\n  Interrupted. Goodbye!\n")
    except Exception as exc:
        print(f"\n  Fatal error: {exc}")
        logger.exception("Fatal error in console application")
