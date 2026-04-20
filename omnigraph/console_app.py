import logging
import re
from getpass import getpass
from typing import Dict, List, Optional, Tuple

import psycopg2  # type: ignore[import-untyped]

from .access_control_audit import AccessControlManager
from .agentic_rag import get_anthropic_agent
from .entity_relation_extractor import EntityRelationExtractor
from .graph_builder import KnowledgeGraphBuilder
from .ingestion_pipeline import DatabaseConnection, DocumentIngester
from .semantic_query_engine import SemanticQueryEngine

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("omnigraph.console")

SEPARATOR = "=" * 70
THIN_SEP = "-" * 70


def print_header(title: str) -> None:
    print(f"\n{SEPARATOR}\n  {title}\n{SEPARATOR}")


def print_table(headers: list, rows: list, widths: Optional[list] = None) -> None:
    if not rows:
        print("  (No results)")
        return

    widths = widths or [
        min(
            max(len(str(h)), max((len(str(r[i])) for r in rows if i < len(r)), default=0)) + 2,
            50,
        )
        for i, h in enumerate(headers)
    ]
    print("  " + "  ".join(str(h).ljust(w) for h, w in zip(headers, widths)))
    print("  " + "  ".join("-" * w for w in widths))
    for row in rows:
        print("  " + "  ".join(str(row[i] if i < len(row) else "").ljust(w)[:w] for i, w in enumerate(widths)))


def prompt_int(message: str, default: Optional[int] = None) -> Optional[int]:
    suffix = f" [{default}]" if default is not None else ""
    try:
        value = input(f"  {message}{suffix}: ").strip()
        return default if not value and default is not None else int(value)
    except (EOFError, ValueError):
        return default


def prompt_str(message: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"  {message}{suffix}: ").strip()
        return value or default
    except EOFError:
        return default


class OmniGraphConsole:
    """Prompt-first console for OmniGraph."""

    def __init__(self):
        self.db = None
        self.ingester = None
        self.extractor = None
        self.graph_builder = None
        self.query_engine = None
        self.access_manager = None
        self.agent = None
        self.current_user_id = None
        self.current_username = None

    def connect(
        self,
        host: str = "localhost",
        port: int = 5432,
        dbname: str = "omnigraph",
        user: str = "postgres",
        password: Optional[str] = None,
    ) -> None:
        self.db = DatabaseConnection(host, port, dbname, user, password)
        self.db.connect()
        self.ingester = DocumentIngester(self.db)
        self.extractor = EntityRelationExtractor(self.db)
        self.graph_builder = KnowledgeGraphBuilder(self.db)
        self.access_manager = AccessControlManager(self.db)

    def authenticate(self) -> bool:
        print_header("OmniGraph Login")
        username = prompt_str("Username")
        if not username:
            return False

        with self.db.conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, full_name
                FROM omnigraph.users
                WHERE username = %s AND is_active = TRUE
                """,
                (username,),
            )
            row = cur.fetchone()

        if not row:
            print("\n  User not found or inactive.\n")
            return False

        self.current_user_id, self.current_username = row
        self.query_engine = SemanticQueryEngine(self.db, user_id=self.current_user_id)
        self.access_manager.log_audit(
            user_id=self.current_user_id,
            action="login",
            resource_type="system",
            details=f"Console login: {username}",
        )
        print(f"\n  Welcome, {self.current_username}.\n")
        return True

    def run(self) -> None:
        print_header("OmniGraph")
        print("  Prompt-based knowledge graph assistant\n")

        host = prompt_str("Database host", "localhost")
        port = prompt_int("Database port", 5432)
        dbname = prompt_str("Database name", "omnigraph")
        db_user = prompt_str("Database user", "postgres")
        try:
            db_pass = getpass("  Database password (leave blank to use environment): ") or None
        except (EOFError, KeyboardInterrupt):
            db_pass = None

        try:
            self.connect(host, port, dbname, db_user, db_pass)
        except Exception as exc:
            print(f"\n  Connection failed: {exc}")
            return

        if not self.authenticate():
            print("  Exiting.\n")
            return

        self._prompt_loop()
        self.access_manager.log_audit(
            user_id=self.current_user_id,
            action="logout",
            resource_type="system",
            details="Console logout",
        )
        self.db.disconnect()
        print("\n  Goodbye.\n")

    def _prompt_loop(self) -> None:
        self._help()
        while True:
            try:
                text = input("\nOmniGraph> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not text:
                continue
            if text.lower() in {"exit", "quit", "q"}:
                break
            self._handle_prompt(text)

    def _handle_prompt(self, text: str) -> None:
        q = text.lower()
        try:
            if q in {"help", "?"}:
                self._help()
            elif "add document" in q or "new document" in q:
                self._add_document()
            elif "profile" in q or "who am i" in q or "permissions" in q:
                self._profile()
            elif "recent" in q or "list documents" in q:
                self._recent_documents()
            elif "search" in q or "find documents" in q or "documents about" in q:
                self._search_documents(self._topic(text, ("search documents", "find documents", "documents about", "search")) or text)
            elif "expert" in q or "who knows" in q or "specialist" in q:
                self._experts(self._topic(text, ("who knows", "experts", "expert", "specialist")))
            elif "related" in q or "similar" in q:
                self._related_concepts(self._topic(text, ("related to", "related", "similar to", "similar")))
            elif "documents for" in q or "documents linked to" in q or "entity documents" in q:
                self._entity_documents(self._topic(text, ("documents for", "documents linked to", "entity documents")))
            elif "neighborhood" in q or "neighbours" in q or "neighbors" in q:
                self._entity_neighborhood(self._topic(text, ("neighborhood of", "neighborhood", "neighbors of", "neighbours of")))
            elif "path" in q or "connection between" in q:
                source, target = self._path_terms(text)
                self._entity_path(source, target)
            else:
                self._ask_or_search(text)
        except Exception as exc:
            logger.exception("Prompt failed")
            print(f"  Error: {exc}")

    def _help(self) -> None:
        print_header("Ask OmniGraph")
        print("  Ask in natural language. Examples:")
        print("    search documents about Kubernetes security")
        print("    who are the experts in machine learning?")
        print("    related concepts to vector databases")
        print("    documents for entity OpenAI")
        print("    neighborhood of Kubernetes")
        print("    path between Kubernetes and Docker")
        print("    recent documents")
        print("    add document")
        print("    profile")
        print("    exit")

    def _ask_or_search(self, question: str) -> None:
        if self.agent is None:
            self.agent = get_anthropic_agent(self.db, self.current_user_id)
        if self.agent is not None:
            result = self.agent.run(question)
            print(f"\n  {result.get('answer', '').strip()}\n")
            self._audit("view", "system", details=f"Agent question: {question[:80]}")
            return
        self._search_documents(question)

    def _search_documents(self, query: str) -> None:
        print_header("Documents")
        results = self.query_engine.search(query, strategy="hybrid", limit=10)
        results = self._filter_readable(results)
        rows = [
            [
                r["document_id"],
                r["title"][:38],
                r["source_type"],
                f"{r['score']:.3f}",
                ", ".join(r.get("sources", [])),
            ]
            for r in results
        ]
        print_table(["ID", "Title", "Type", "Score", "Sources"], rows, [6, 40, 16, 8, 24])

    def _experts(self, concept: str) -> None:
        concept = concept or prompt_str("Concept")
        if not concept:
            return
        print_header(f"Experts: {concept}")
        rows = [
            [e["full_name"], e["department"], e["title"][:25], e["doc_count"], f"{e['expertise_score']:.1f}"]
            for e in self.query_engine.find_experts(concept)
        ]
        print_table(["Name", "Department", "Title", "Docs", "Score"], rows, [22, 16, 27, 6, 8])

    def _related_concepts(self, concept: str) -> None:
        concept = concept or prompt_str("Concept")
        if not concept:
            return
        print_header(f"Related Concepts: {concept}")
        rows = [
            [c["name"], c["domain"], c["relationship_types"], c["connection_strength"]]
            for c in self.query_engine.find_related_concepts(concept)
        ]
        print_table(["Concept", "Domain", "Relation", "Strength"], rows, [28, 16, 25, 10])

    def _entity_documents(self, entity: str) -> None:
        entity = entity or prompt_str("Entity")
        if not entity:
            return
        print_header(f"Documents For: {entity}")
        docs = self._filter_readable(self.query_engine.get_entity_documents(entity))
        rows = [
            [d["document_id"], d["title"][:40], d["source_type"], f"{d['relevance']:.3f}", d["mention_count"]]
            for d in docs
        ]
        print_table(["ID", "Title", "Type", "Relevance", "Mentions"], rows, [6, 42, 16, 10, 10])

    def _entity_neighborhood(self, entity: str) -> None:
        if not self._require_permission("view_graph"):
            return
        entity_id = self._resolve_entity_id(entity or prompt_str("Entity name or ID"))
        if entity_id is None:
            return
        depth = prompt_int("Max depth", 2)
        print_header("Entity Neighborhood")
        rows = [
            [n["entity_id"], n["name"], n["entity_type"], n["relation_type"], f"{n['strength']:.3f}", n["depth"]]
            for n in self.graph_builder.get_entity_neighborhood(entity_id, depth)
        ]
        print_table(["ID", "Name", "Type", "Relation", "Strength", "Depth"], rows, [6, 22, 14, 18, 10, 6])

    def _entity_path(self, source: str = "", target: str = "") -> None:
        source_id = self._resolve_entity_id(source or prompt_str("Source entity name or ID"))
        target_id = self._resolve_entity_id(target or prompt_str("Target entity name or ID"))
        if source_id is None or target_id is None:
            return
        max_depth = prompt_int("Max depth", 6)
        print_header("Entity Path")
        with self.db.conn.cursor() as cur:
            cur.execute("SELECT * FROM omnigraph.sp_shortest_path(%s, %s, %s)", (source_id, target_id, max_depth))
            rows = cur.fetchall()
        if not rows:
            print(f"  No path found between entity #{source_id} and #{target_id}.")
            return
        for i, row in enumerate(rows):
            print(f"\n  Path {i + 1} (length={row[0]}):")
            print(f"    Entities:  {' -> '.join(row[1])}")
            print(f"    Relations: {' -> '.join(row[2])}")

    def _recent_documents(self) -> None:
        print_header("Recent Documents")
        limit = prompt_int("Number of documents", 10)
        with self.db.conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.document_id, d.title, d.source_type, d.sensitivity_level,
                       u.full_name, d.created_at::DATE
                FROM omnigraph.documents d
                JOIN omnigraph.users u ON u.user_id = d.uploaded_by
                WHERE d.is_archived = FALSE
                ORDER BY d.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = [
                r for r in cur.fetchall()
                if self.access_manager.check_access(self.current_user_id, "document", r[0], "read")
            ]
        print_table(
            ["ID", "Title", "Type", "Sensitivity", "Author", "Date"],
            [[r[0], str(r[1])[:35], r[2], r[3], r[4], str(r[5])] for r in rows],
            [6, 37, 16, 14, 20, 12],
        )

    def _add_document(self) -> None:
        print_header("Add Document")
        title = prompt_str("Title")
        if not title:
            return
        source_type = prompt_str("Source type", "technical_doc")
        sensitivity = prompt_str("Sensitivity", "internal")
        summary = prompt_str("Summary (optional)")
        content = prompt_str("Content")
        if not content:
            print("  Content is required.")
            return

        doc_id = self.ingester.ingest_document(
            title=title,
            source_type=source_type,
            content=content,
            uploaded_by=self.current_user_id,
            sensitivity_level=sensitivity,
            summary=summary or None,
        )
        if not doc_id:
            print("  Failed to create document.")
            return

        result = self.extractor.process_document(doc_id)
        print(
            f"  Document created (ID: {doc_id}). "
            f"Extracted {len(result['entities'])} entities, "
            f"{len(result['concepts'])} concepts, "
            f"{len(result['relationships'])} relationships."
        )
        self._audit("create", "document", doc_id, f"Created document: {title}")

    def _profile(self) -> None:
        print_header("Profile")
        with self.db.conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, username, email, full_name, department, title
                FROM omnigraph.users
                WHERE user_id = %s
                """,
                (self.current_user_id,),
            )
            user = cur.fetchone()
        if user:
            labels = ["User ID", "Username", "Email", "Full Name", "Department", "Title"]
            for label, value in zip(labels, user):
                print(f"  {label}: {value}")

        roles = self.access_manager.get_user_roles(self.current_user_id)
        if roles:
            print("\n  Roles:")
            for role in roles:
                perms = ", ".join(role["permissions"]) if role["permissions"] else "none"
                print(f"    {role['role_name']}: {perms}")

    def _resolve_entity_id(self, value: str) -> Optional[int]:
        value = value.strip()
        if not value:
            return None
        if value.isdigit():
            return int(value)

        matches = self._find_entity_candidates(value)
        if not matches:
            print(f"  No entity found for '{value}'.")
            return None
        exact = [m for m in matches if m["name"].lower() == value.lower()]
        if len(exact) == 1:
            return exact[0]["entity_id"]

        print(f"\n  Matching entities for '{value}':")
        print_table(
            ["ID", "Name", "Type", "Confidence", "Docs"],
            [
                [m["entity_id"], m["name"][:32], m["entity_type"], f"{m['confidence']:.3f}", m["doc_count"]]
                for m in matches
            ],
            [6, 34, 16, 12, 6],
        )
        return prompt_int("Use entity ID")

    def _find_entity_candidates(self, term: str, limit: int = 10) -> List[Dict]:
        try:
            with self.db.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.entity_id, e.name, e.entity_type, e.confidence,
                           (SELECT COUNT(*) FROM omnigraph.document_entities de WHERE de.entity_id = e.entity_id) AS doc_count
                    FROM omnigraph.entities e
                    WHERE LOWER(e.name) = LOWER(%s) OR e.name ILIKE %s OR e.description ILIKE %s
                    ORDER BY CASE WHEN LOWER(e.name) = LOWER(%s) THEN 0 ELSE 1 END, doc_count DESC, e.name
                    LIMIT %s
                    """,
                    (term, f"%{term}%", f"%{term}%", term, limit),
                )
                columns = ["entity_id", "name", "entity_type", "confidence", "doc_count"]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
        except psycopg2.Error as exc:
            print(f"  Entity lookup error: {exc}")
            return []

    def _filter_readable(self, rows: List[Dict]) -> List[Dict]:
        return [
            row for row in rows
            if row.get("document_id") is not None
            and self.access_manager.check_access(self.current_user_id, "document", row["document_id"], "read")
        ]

    def _require_permission(self, permission: str) -> bool:
        if self.access_manager.validate_permission(self.current_user_id, permission):
            return True
        print(f"  Access denied. Requires '{permission}' permission.")
        return False

    def _audit(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        details: str = "",
    ) -> None:
        self.access_manager.log_audit(
            user_id=self.current_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
        )

    @staticmethod
    def _topic(text: str, markers: Tuple[str, ...]) -> str:
        lowered = text.lower()
        for marker in markers:
            idx = lowered.find(marker)
            if idx >= 0:
                topic = text[idx + len(marker):].strip(" ?:.-")
                prefixes = (
                    "are", "is", "the", "a", "an", "to", "of", "about", "in",
                    "on", "for", "entity", "concept", "concepts",
                )
                changed = True
                while changed:
                    changed = False
                    for prefix in prefixes:
                        prefix_text = f"{prefix} "
                        if topic.lower().startswith(prefix_text):
                            topic = topic[len(prefix_text):].strip(" ?:.-")
                            changed = True
                return topic
        return ""

    @staticmethod
    def _path_terms(text: str) -> Tuple[str, str]:
        match = re.search(r"(?:path|connection)\s+between\s+(.+?)\s+and\s+(.+)", text, re.I)
        if match:
            return match.group(1).strip(" ?:.-"), match.group(2).strip(" ?:.-")
        return "", ""


if __name__ == "__main__":
    console = OmniGraphConsole()
    try:
        console.run()
    except KeyboardInterrupt:
        print("\n\n  Interrupted. Goodbye.\n")
    except Exception as exc:
        print(f"\n  Fatal error: {exc}")
        logger.exception("Fatal error in console application")
