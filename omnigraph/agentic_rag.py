"""Agentic RAG: LangGraph ReAct agent with OmniGraph tools as the core query path."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from .access_control_audit import AccessControlManager
from .graph_builder import KnowledgeGraphBuilder
from .ingestion_pipeline import DatabaseConnection, DocumentIngester, SUPPORTED_SOURCE_TYPES
from .semantic_query_engine import SemanticQueryEngine

ALLOWED_RELATION_TYPES = frozenset(
    {
        "works_for",
        "collaborates_with",
        "authored",
        "uses",
        "located_in",
        "part_of",
        "depends_on",
        "related_to",
        "manages",
        "developed_by",
        "competitor_of",
        "successor_of",
    }
)


def _format_docs(docs: List[Dict[str, Any]], max_chars: int = 3000) -> str:
    out: List[str] = []
    total = 0
    for d in docs:
        title = d.get("title", "")
        summary = (d.get("summary") or "")[:400]
        doc_id = d.get("document_id", "")
        line = f"[id={doc_id}] {title}\n  {summary}"
        if total + len(line) > max_chars:
            break
        out.append(line)
        total += len(line)
    return "\n\n".join(out) if out else "No documents found."


def _create_tools(
    query_engine: SemanticQueryEngine,
    access_manager: AccessControlManager,
    user_id: int,
    db: DatabaseConnection,
) -> List[Any]:
    @tool
    def hybrid_search(query: str, limit: int = 10) -> str:
        """Search the knowledge graph (full-text, semantic, and graph traversal). Use for finding documents relevant to a topic or question."""
        results = query_engine.search(query, strategy="hybrid", limit=limit)
        filtered = [
            r
            for r in results
            if r.get("document_id") is not None
            and access_manager.check_access(user_id, "document", r["document_id"], "read")
        ]
        return _format_docs(filtered)

    @tool
    def find_experts(concept: str, limit: int = 5) -> str:
        """Find users who are domain experts on a concept (by document contributions and relevance)."""
        experts = query_engine.find_experts(concept, limit=limit)
        if not experts:
            return "No experts found for that concept."
        lines = [f"- {e['full_name']} ({e.get('department', '')}): {e.get('expertise_score', 0):.1f}" for e in experts]
        return "\n".join(lines)

    @tool
    def get_entity_documents(entity_name: str, limit: int = 10) -> str:
        """List documents linked to a specific entity (person, org, technology)."""
        docs = query_engine.get_entity_documents(entity_name, limit=limit)
        filtered = [
            d
            for d in docs
            if d.get("document_id") is not None
            and access_manager.check_access(user_id, "document", d["document_id"], "read")
        ]
        return _format_docs(filtered)

    @tool
    def find_related_concepts(concept: str) -> str:
        """Get concepts related to a given concept via hierarchy and co-occurrence in documents."""
        related = query_engine.find_related_concepts(concept)
        if not related:
            return "No related concepts found."
        lines = [f"- {c['name']} [{c.get('domain', '')}] ({c.get('relationship_types', '')})" for c in related[:15]]
        return "\n".join(lines)

    @tool
    def get_document_content(document_id: int, max_chars: int = 4000) -> str:
        """Fetch the full text content of a document by ID. Use after search when you need to read the actual content. Requires read access."""
        if not access_manager.check_access(user_id, "document", document_id, "read"):
            return "Access denied to this document."
        try:
            with db.conn.cursor() as cur:
                cur.execute(
                    "SELECT title, content FROM omnigraph.documents WHERE document_id = %s",
                    (document_id,),
                )
                row = cur.fetchone()
            if not row:
                return "Document not found."
            title, content = row[0], (row[1] or "")[:max_chars]
            return f"Title: {title}\n\nContent:\n{content}"
        except Exception as e:
            return f"Error fetching document: {e}"

    ingester = DocumentIngester(db)
    graph = KnowledgeGraphBuilder(db)

    @tool
    def create_document(
        title: str,
        source_type: str,
        content: str,
        sensitivity_level: str = "internal",
        summary: Optional[str] = None,
    ) -> str:
        """Create a new document in the knowledge base. source_type must be one of the supported types (e.g. technical_doc, report). Requires write permission at the chosen sensitivity tier."""
        if source_type not in SUPPORTED_SOURCE_TYPES:
            return f"Invalid source_type. Use one of: {sorted(SUPPORTED_SOURCE_TYPES)}"
        if not access_manager.check_policy_at_sensitivity(
            user_id, "document", sensitivity_level, "write",
        ):
            return "Access denied: cannot create documents at this sensitivity level."
        doc_id = ingester.ingest_document(
            title=title,
            source_type=source_type,
            content=content,
            uploaded_by=user_id,
            sensitivity_level=sensitivity_level,
            summary=summary,
        )
        if doc_id is None:
            return "Failed to create document (ingestion error or duplicate handling failed)."
        access_manager.log_audit(
            user_id=user_id,
            action="create",
            resource_type="document",
            resource_id=doc_id,
            details=f"Agent created document: {title[:200]}",
        )
        return f"Created document_id={doc_id}"

    @tool
    def update_document(
        document_id: int,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        sensitivity_level: Optional[str] = None,
        content: Optional[str] = None,
    ) -> str:
        """Update an existing document (metadata and/or body). Requires write access; changing sensitivity requires write at the new tier."""
        if not access_manager.check_access(user_id, "document", document_id, "write"):
            return "Access denied: cannot update this document."
        if sensitivity_level is not None and not access_manager.check_policy_at_sensitivity(
            user_id, "document", sensitivity_level, "write",
        ):
            return "Access denied: cannot set document to this sensitivity level."
        result = ingester.update_document(
            document_id=document_id,
            changed_by=user_id,
            title=title,
            summary=summary,
            sensitivity_level=sensitivity_level,
            content=content,
            change_summary="Agent update",
        )
        if result is None:
            return "Update failed (document not found, archived, or no fields provided)."
        access_manager.log_audit(
            user_id=user_id,
            action="update",
            resource_type="document",
            resource_id=document_id,
            details="Agent updated document fields",
        )
        return f"Updated document_id={document_id}"

    @tool
    def archive_document(document_id: int) -> str:
        """Soft-delete (archive) a document. Requires delete permission on that document."""
        if not access_manager.check_access(user_id, "document", document_id, "delete"):
            return "Access denied: cannot archive this document."
        if not ingester.set_document_archived(document_id, True):
            return "Archive failed (document not found?)."
        access_manager.log_audit(
            user_id=user_id,
            action="delete",
            resource_type="document",
            resource_id=document_id,
            details="Agent archived document",
        )
        return f"Archived document_id={document_id}"

    @tool
    def restore_document(document_id: int) -> str:
        """Un-archive a document. Requires write permission."""
        if not access_manager.check_access(user_id, "document", document_id, "write"):
            return "Access denied: cannot restore this document."
        if not ingester.set_document_archived(document_id, False):
            return "Restore failed (document not found?)."
        access_manager.log_audit(
            user_id=user_id,
            action="update",
            resource_type="document",
            resource_id=document_id,
            details="Agent restored document from archive",
        )
        return f"Restored document_id={document_id}"

    @tool
    def create_entity(name: str, entity_type: str, description: Optional[str] = None) -> str:
        """Add a graph entity. entity_type: person, organization, technology, location, product, event, standard, other."""
        if not access_manager.check_policy_at_sensitivity(user_id, "entity", "public", "write"):
            return "Access denied: cannot create entities."
        eid = graph.add_entity_node(name=name, entity_type=entity_type, description=description)
        if eid is None:
            return "Failed to create entity."
        access_manager.log_audit(
            user_id=user_id,
            action="create",
            resource_type="entity",
            resource_id=eid,
            details=f"Agent created entity: {name}",
        )
        return f"Created entity_id={eid} (existing id returned if duplicate name+type)."

    @tool
    def update_entity(
        entity_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> str:
        """Update entity fields. Requires entity write permission."""
        if not access_manager.check_access(user_id, "entity", entity_id, "write"):
            return "Access denied: cannot update this entity."
        ok = graph.update_entity_node(entity_id, name=name, description=description, confidence=confidence)
        if not ok:
            return "Update failed (not found, no changes, or name conflict with another entity)."
        access_manager.log_audit(
            user_id=user_id,
            action="update",
            resource_type="entity",
            resource_id=entity_id,
            details="Agent updated entity",
        )
        return f"Updated entity_id={entity_id}"

    @tool
    def delete_entity(entity_id: int) -> str:
        """Remove an entity and its relationships (cascade). Requires entity delete permission."""
        if not access_manager.check_access(user_id, "entity", entity_id, "delete"):
            return "Access denied: cannot delete this entity."
        if not graph.remove_entity_node(entity_id):
            return "Delete failed (entity not found?)."
        access_manager.log_audit(
            user_id=user_id,
            action="delete",
            resource_type="entity",
            resource_id=entity_id,
            details="Agent deleted entity",
        )
        return f"Deleted entity_id={entity_id}"

    @tool
    def create_relationship(
        source_entity_id: int,
        target_entity_id: int,
        relation_type: str,
        strength: float = 1.0,
        description: Optional[str] = None,
        source_document_id: Optional[int] = None,
    ) -> str:
        """Create a typed edge between entities. relation_type must be a schema value: works_for, uses, depends_on, related_to, etc."""
        if relation_type not in ALLOWED_RELATION_TYPES:
            return f"Invalid relation_type. Use one of: {sorted(ALLOWED_RELATION_TYPES)}"
        if not access_manager.check_policy_at_sensitivity(user_id, "entity", "public", "write"):
            return "Access denied: cannot create relationships."
        if source_document_id is not None and not access_manager.check_access(
            user_id, "document", source_document_id, "read",
        ):
            return "Access denied: cannot attach relationship to this document (read)."
        rid = graph.add_relationship(
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relation_type=relation_type,
            strength=strength,
            description=description,
            source_document_id=source_document_id,
        )
        if rid is None:
            return "Failed to create relationship (invalid entities or self-loop)."
        access_manager.log_audit(
            user_id=user_id,
            action="create",
            resource_type="entity",
            resource_id=source_entity_id,
            details=f"Agent created relation_id={rid} {relation_type}",
        )
        return f"Created relation_id={rid}"

    @tool
    def delete_relationship(relation_id: int) -> str:
        """Delete a relationship by relation_id. Requires write permission on the source entity."""
        try:
            with db.conn.cursor() as cur:
                cur.execute(
                    "SELECT source_entity_id FROM omnigraph.relations WHERE relation_id = %s",
                    (relation_id,),
                )
                row = cur.fetchone()
        except Exception as e:
            return f"Error looking up relationship: {e}"
        if not row:
            return "Relationship not found."
        src = row[0]
        if not access_manager.check_access(user_id, "entity", src, "write"):
            return "Access denied: cannot delete this relationship."
        if not graph.remove_relationship(relation_id):
            return "Failed to delete relationship."
        access_manager.log_audit(
            user_id=user_id,
            action="delete",
            resource_type="entity",
            resource_id=src,
            details=f"Agent deleted relation_id={relation_id}",
        )
        return f"Deleted relation_id={relation_id}"

    @tool
    def link_document_to_entity(
        document_id: int,
        entity_id: int,
        relevance: float = 1.0,
        mention_count: int = 1,
    ) -> str:
        """Link a document to an entity (document_entities). Requires write on both document and entity."""
        if not access_manager.check_access(user_id, "document", document_id, "write"):
            return "Access denied: cannot modify this document."
        if not access_manager.check_access(user_id, "entity", entity_id, "write"):
            return "Access denied: cannot link to this entity."
        if not graph.map_document_entity(document_id, entity_id, relevance, mention_count):
            return "Failed to link document to entity."
        access_manager.log_audit(
            user_id=user_id,
            action="update",
            resource_type="document",
            resource_id=document_id,
            details=f"Agent linked entity_id={entity_id}",
        )
        return f"Linked document_id={document_id} to entity_id={entity_id}"

    return [
        hybrid_search,
        find_experts,
        get_entity_documents,
        find_related_concepts,
        get_document_content,
        create_document,
        update_document,
        archive_document,
        restore_document,
        create_entity,
        update_entity,
        delete_entity,
        create_relationship,
        delete_relationship,
        link_document_to_entity,
    ]


class OmniGraphAgent:
    """ReAct agent with OmniGraph tools; primary interface for querying the knowledge graph."""

    def __init__(self, db: DatabaseConnection, user_id: int, llm: Any) -> None:
        self.db = db
        self.user_id = user_id
        self.llm = llm
        self.access_manager = AccessControlManager(db)
        self.query_engine = SemanticQueryEngine(db, user_id=user_id)
        tools = _create_tools(self.query_engine, self.access_manager, user_id, db)
        self.app = create_react_agent(self.llm, tools)

    def run(self, question: str) -> Dict[str, Any]:
        """Run the agent on a single question; returns final state with messages and last answer."""
        from langchain_core.messages import HumanMessage  # noqa: PLC0415

        result = self.app.invoke({"messages": [HumanMessage(content=question)]})
        messages = result.get("messages", [])
        last = messages[-1] if messages else None
        answer = getattr(last, "content", str(last)) if last else ""
        return {"answer": answer, "messages": messages, "state": result}


def get_default_llm():
    """Return a default Groq chat model when GROQ_API_KEY is set; otherwise None."""
    if not os.getenv("GROQ_API_KEY"):
        return None
    try:
        from langchain_groq import ChatGroq

        return ChatGroq(model="llama3-70b-8192", temperature=0)
    except ImportError:
        return None


__all__ = ["OmniGraphAgent", "get_default_llm", "_create_tools", "_format_docs"]
