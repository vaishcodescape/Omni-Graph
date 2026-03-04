"""Agentic RAG: LangGraph ReAct agent with OmniGraph tools as the core query path."""

from __future__ import annotations

import os
from typing import Any, Dict, List

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from .access_control_audit import AccessControlManager
from .ingestion_pipeline import DatabaseConnection
from .semantic_query_engine import SemanticQueryEngine


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

    return [hybrid_search, find_experts, get_entity_documents, find_related_concepts, get_document_content]


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
