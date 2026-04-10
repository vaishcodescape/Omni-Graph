"""Agentic RAG: Anthropic SDK-powered agent with OmniGraph tools."""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, NamedTuple, Optional

import anthropic

from .access_control_audit import AccessControlManager
from .entity_relation_extractor import EntityRelationExtractor
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


def _format_docs(docs: List[Dict[str, Any]], max_chars: int = 4000) -> str:
    out: List[str] = []
    total = 0
    for d in docs:
        title = d.get("title", "Untitled")
        summary = (d.get("summary") or "")[:600]
        doc_id = d.get("document_id", "")
        hint = f"  (call get_document_content({doc_id}) for full text)" if doc_id else ""
        line = f"[doc_id={doc_id}] {title}\n  {summary}{hint}"
        if total + len(line) > max_chars:
            break
        out.append(line)
        total += len(line)
    return "\n\n".join(out) if out else "No documents found."


class _OmniTool(NamedTuple):
    """Pairs an Anthropic tool schema with its implementation function."""
    schema: Dict[str, Any]
    fn: Callable


def _create_tools(
    query_engine: SemanticQueryEngine,
    access_manager: AccessControlManager,
    user_id: int,
    db: DatabaseConnection,
) -> List[_OmniTool]:

    def hybrid_search(query: str, limit: int = 10) -> str:
        results = query_engine.search(query, strategy="hybrid", limit=limit)
        filtered = [
            r for r in results
            if r.get("document_id") is not None
            and access_manager.check_access(user_id, "document", r["document_id"], "read")
        ]
        return _format_docs(filtered)

    def find_experts(concept: str, limit: int = 5) -> str:
        experts = query_engine.find_experts(concept, limit=limit)
        if not experts:
            return "No experts found for that concept."
        lines = [
            f"- {e['full_name']} ({e.get('department', '')}): {e.get('expertise_score', 0):.1f}"
            for e in experts
        ]
        return "\n".join(lines)

    def get_entity_documents(entity_name: str, limit: int = 10) -> str:
        docs = query_engine.get_entity_documents(entity_name, limit=limit)
        filtered = [
            d for d in docs
            if d.get("document_id") is not None
            and access_manager.check_access(user_id, "document", d["document_id"], "read")
        ]
        return _format_docs(filtered)

    def find_related_concepts(concept: str) -> str:
        related = query_engine.find_related_concepts(concept)
        if not related:
            return "No related concepts found."
        lines = [
            f"- {c['name']} [{c.get('domain', '')}] ({c.get('relationship_types', '')})"
            for c in related[:15]
        ]
        return "\n".join(lines)

    def get_document_content(document_id: int, max_chars: int = 4000) -> str:
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
    extractor = EntityRelationExtractor(db)
    graph = KnowledgeGraphBuilder(db)

    def create_document(
        title: str,
        source_type: str,
        content: str,
        sensitivity_level: str = "internal",
        summary: Optional[str] = None,
    ) -> str:
        if source_type not in SUPPORTED_SOURCE_TYPES:
            return f"Invalid source_type. Use one of: {sorted(SUPPORTED_SOURCE_TYPES)}"
        if not access_manager.check_policy_at_sensitivity(user_id, "document", sensitivity_level, "write"):
            return "Access denied: cannot create documents at this sensitivity level."
        doc_id = ingester.ingest_document(
            title=title, source_type=source_type, content=content,
            uploaded_by=user_id, sensitivity_level=sensitivity_level, summary=summary,
        )
        if doc_id is None:
            return "Failed to create document."
        extractor.process_document(doc_id)
        access_manager.log_audit(
            user_id=user_id, action="create", resource_type="document",
            resource_id=doc_id, details=f"Agent created document: {title[:200]}",
        )
        return f"Created document_id={doc_id}"

    def update_document(
        document_id: int,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        sensitivity_level: Optional[str] = None,
        content: Optional[str] = None,
    ) -> str:
        if not access_manager.check_access(user_id, "document", document_id, "write"):
            return "Access denied: cannot update this document."
        if sensitivity_level is not None and not access_manager.check_policy_at_sensitivity(
            user_id, "document", sensitivity_level, "write"
        ):
            return "Access denied: cannot set document to this sensitivity level."
        result = ingester.update_document(
            document_id=document_id, changed_by=user_id, title=title,
            summary=summary, sensitivity_level=sensitivity_level,
            content=content, change_summary="Agent update",
        )
        if result is None:
            return "Update failed (document not found, archived, or no fields provided)."
        access_manager.log_audit(
            user_id=user_id, action="update", resource_type="document",
            resource_id=document_id, details="Agent updated document fields",
        )
        return f"Updated document_id={document_id}"

    def archive_document(document_id: int) -> str:
        if not access_manager.check_access(user_id, "document", document_id, "delete"):
            return "Access denied: cannot archive this document."
        if not ingester.set_document_archived(document_id, True):
            return "Archive failed (document not found?)."
        access_manager.log_audit(
            user_id=user_id, action="delete", resource_type="document",
            resource_id=document_id, details="Agent archived document",
        )
        return f"Archived document_id={document_id}"

    def restore_document(document_id: int) -> str:
        if not access_manager.check_access(user_id, "document", document_id, "write"):
            return "Access denied: cannot restore this document."
        if not ingester.set_document_archived(document_id, False):
            return "Restore failed (document not found?)."
        access_manager.log_audit(
            user_id=user_id, action="update", resource_type="document",
            resource_id=document_id, details="Agent restored document from archive",
        )
        return f"Restored document_id={document_id}"

    def create_entity(name: str, entity_type: str, description: Optional[str] = None) -> str:
        if not access_manager.check_policy_at_sensitivity(user_id, "entity", "public", "write"):
            return "Access denied: cannot create entities."
        eid = graph.add_entity_node(name=name, entity_type=entity_type, description=description)
        if eid is None:
            return "Failed to create entity."
        access_manager.log_audit(
            user_id=user_id, action="create", resource_type="entity",
            resource_id=eid, details=f"Agent created entity: {name}",
        )
        return f"Created entity_id={eid} (existing id returned if duplicate name+type)."

    def update_entity(
        entity_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> str:
        if not access_manager.check_access(user_id, "entity", entity_id, "write"):
            return "Access denied: cannot update this entity."
        ok = graph.update_entity_node(entity_id, name=name, description=description, confidence=confidence)
        if not ok:
            return "Update failed (not found, no changes, or name conflict)."
        access_manager.log_audit(
            user_id=user_id, action="update", resource_type="entity",
            resource_id=entity_id, details="Agent updated entity",
        )
        return f"Updated entity_id={entity_id}"

    def delete_entity(entity_id: int) -> str:
        if not access_manager.check_access(user_id, "entity", entity_id, "delete"):
            return "Access denied: cannot delete this entity."
        if not graph.remove_entity_node(entity_id):
            return "Delete failed (entity not found?)."
        access_manager.log_audit(
            user_id=user_id, action="delete", resource_type="entity",
            resource_id=entity_id, details="Agent deleted entity",
        )
        return f"Deleted entity_id={entity_id}"

    def create_relationship(
        source_entity_id: int,
        target_entity_id: int,
        relation_type: str,
        strength: float = 1.0,
        description: Optional[str] = None,
        source_document_id: Optional[int] = None,
    ) -> str:
        if relation_type not in ALLOWED_RELATION_TYPES:
            return f"Invalid relation_type. Use one of: {sorted(ALLOWED_RELATION_TYPES)}"
        if not access_manager.check_policy_at_sensitivity(user_id, "entity", "public", "write"):
            return "Access denied: cannot create relationships."
        if source_document_id is not None and not access_manager.check_access(
            user_id, "document", source_document_id, "read"
        ):
            return "Access denied: cannot attach relationship to this document."
        rid = graph.add_relationship(
            source_entity_id=source_entity_id, target_entity_id=target_entity_id,
            relation_type=relation_type, strength=strength,
            description=description, source_document_id=source_document_id,
        )
        if rid is None:
            return "Failed to create relationship (invalid entities or self-loop)."
        access_manager.log_audit(
            user_id=user_id, action="create", resource_type="entity",
            resource_id=source_entity_id,
            details=f"Agent created relation_id={rid} {relation_type}",
        )
        return f"Created relation_id={rid}"

    def delete_relationship(relation_id: int) -> str:
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
            user_id=user_id, action="delete", resource_type="entity",
            resource_id=src, details=f"Agent deleted relation_id={relation_id}",
        )
        return f"Deleted relation_id={relation_id}"

    def link_document_to_entity(
        document_id: int,
        entity_id: int,
        relevance: float = 1.0,
        mention_count: int = 1,
    ) -> str:
        if not access_manager.check_access(user_id, "document", document_id, "write"):
            return "Access denied: cannot modify this document."
        if not access_manager.check_access(user_id, "entity", entity_id, "write"):
            return "Access denied: cannot link to this entity."
        if not graph.map_document_entity(document_id, entity_id, relevance, mention_count):
            return "Failed to link document to entity."
        access_manager.log_audit(
            user_id=user_id, action="update", resource_type="document",
            resource_id=document_id, details=f"Agent linked entity_id={entity_id}",
        )
        return f"Linked document_id={document_id} to entity_id={entity_id}"

    return [
        _OmniTool(
            schema={
                "name": "hybrid_search",
                "description": "Search the knowledge graph using full-text, semantic, and graph traversal. Use for finding documents relevant to a topic or question.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "description": "Maximum number of results (default 10)"},
                    },
                    "required": ["query"],
                },
            },
            fn=hybrid_search,
        ),
        _OmniTool(
            schema={
                "name": "find_experts",
                "description": "Find users who are domain experts on a concept, ranked by document contributions and relevance.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "concept": {"type": "string", "description": "Concept or topic name"},
                        "limit": {"type": "integer", "description": "Maximum number of experts to return (default 5)"},
                    },
                    "required": ["concept"],
                },
            },
            fn=find_experts,
        ),
        _OmniTool(
            schema={
                "name": "get_entity_documents",
                "description": "List documents linked to a specific entity (person, org, technology).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "entity_name": {"type": "string", "description": "Entity name to look up"},
                        "limit": {"type": "integer", "description": "Maximum results (default 10)"},
                    },
                    "required": ["entity_name"],
                },
            },
            fn=get_entity_documents,
        ),
        _OmniTool(
            schema={
                "name": "find_related_concepts",
                "description": "Get concepts related to a given concept via hierarchy and co-occurrence in documents.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "concept": {"type": "string", "description": "Concept name"},
                    },
                    "required": ["concept"],
                },
            },
            fn=find_related_concepts,
        ),
        _OmniTool(
            schema={
                "name": "get_document_content",
                "description": "Fetch the full text content of a document by ID. Use after search when you need to read the actual content. Requires read access.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "integer", "description": "Document ID"},
                        "max_chars": {"type": "integer", "description": "Maximum characters to return (default 4000)"},
                    },
                    "required": ["document_id"],
                },
            },
            fn=get_document_content,
        ),
        _OmniTool(
            schema={
                "name": "create_document",
                "description": "Create a new document in the knowledge base. Requires write permission at the chosen sensitivity tier.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Document title"},
                        "source_type": {"type": "string", "description": "Document type (e.g. technical_doc, report)"},
                        "content": {"type": "string", "description": "Document body text"},
                        "sensitivity_level": {"type": "string", "description": "Sensitivity tier (default: internal)"},
                        "summary": {"type": "string", "description": "Short summary (optional)"},
                    },
                    "required": ["title", "source_type", "content"],
                },
            },
            fn=create_document,
        ),
        _OmniTool(
            schema={
                "name": "update_document",
                "description": "Update an existing document's metadata or body. Requires write access.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "integer", "description": "Document ID to update"},
                        "title": {"type": "string", "description": "New title (optional)"},
                        "summary": {"type": "string", "description": "New summary (optional)"},
                        "sensitivity_level": {"type": "string", "description": "New sensitivity level (optional)"},
                        "content": {"type": "string", "description": "New body text (optional)"},
                    },
                    "required": ["document_id"],
                },
            },
            fn=update_document,
        ),
        _OmniTool(
            schema={
                "name": "archive_document",
                "description": "Soft-delete (archive) a document. Requires delete permission.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "integer", "description": "Document ID to archive"},
                    },
                    "required": ["document_id"],
                },
            },
            fn=archive_document,
        ),
        _OmniTool(
            schema={
                "name": "restore_document",
                "description": "Un-archive a document. Requires write permission.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "integer", "description": "Document ID to restore"},
                    },
                    "required": ["document_id"],
                },
            },
            fn=restore_document,
        ),
        _OmniTool(
            schema={
                "name": "create_entity",
                "description": "Add a graph entity. entity_type: person, organization, technology, location, product, event, standard, other.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Entity name"},
                        "entity_type": {"type": "string", "description": "Entity type (person, organization, technology, etc.)"},
                        "description": {"type": "string", "description": "Optional description"},
                    },
                    "required": ["name", "entity_type"],
                },
            },
            fn=create_entity,
        ),
        _OmniTool(
            schema={
                "name": "update_entity",
                "description": "Update entity fields. Requires entity write permission.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "integer", "description": "Entity ID to update"},
                        "name": {"type": "string", "description": "New name (optional)"},
                        "description": {"type": "string", "description": "New description (optional)"},
                        "confidence": {"type": "number", "description": "Confidence score 0-1 (optional)"},
                    },
                    "required": ["entity_id"],
                },
            },
            fn=update_entity,
        ),
        _OmniTool(
            schema={
                "name": "delete_entity",
                "description": "Remove an entity and its relationships. Requires entity delete permission.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "integer", "description": "Entity ID to delete"},
                    },
                    "required": ["entity_id"],
                },
            },
            fn=delete_entity,
        ),
        _OmniTool(
            schema={
                "name": "create_relationship",
                "description": "Create a typed edge between entities. relation_type must be one of the allowed schema values.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "source_entity_id": {"type": "integer", "description": "Source entity ID"},
                        "target_entity_id": {"type": "integer", "description": "Target entity ID"},
                        "relation_type": {
                            "type": "string",
                            "description": f"Relationship type. One of: {sorted(ALLOWED_RELATION_TYPES)}",
                        },
                        "strength": {"type": "number", "description": "Relationship strength 0-1 (default 1.0)"},
                        "description": {"type": "string", "description": "Optional description"},
                        "source_document_id": {"type": "integer", "description": "Document that evidences this relationship (optional)"},
                    },
                    "required": ["source_entity_id", "target_entity_id", "relation_type"],
                },
            },
            fn=create_relationship,
        ),
        _OmniTool(
            schema={
                "name": "delete_relationship",
                "description": "Delete a relationship by relation_id. Requires write permission on the source entity.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "relation_id": {"type": "integer", "description": "Relation ID to delete"},
                    },
                    "required": ["relation_id"],
                },
            },
            fn=delete_relationship,
        ),
        _OmniTool(
            schema={
                "name": "link_document_to_entity",
                "description": "Link a document to an entity. Requires write on both the document and the entity.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "integer", "description": "Document ID"},
                        "entity_id": {"type": "integer", "description": "Entity ID"},
                        "relevance": {"type": "number", "description": "Relevance score 0-1 (default 1.0)"},
                        "mention_count": {"type": "integer", "description": "Number of mentions (default 1)"},
                    },
                    "required": ["document_id", "entity_id"],
                },
            },
            fn=link_document_to_entity,
        ),
    ]


class AnthropicOmniGraphAgent:
    """OmniGraph agent driven by the Anthropic SDK (native tool-use loop, streaming)."""

    _SYSTEM = """\
You are OmniGraph Assistant, an AI that answers questions from an enterprise knowledge graph.

## RAG Workflow — follow this order for every factual question:
1. **Search first**: call `hybrid_search` with the user's topic/question to find candidate documents.
2. **Read before answering**: for each promising result, call `get_document_content(doc_id)` to fetch the full text. Do not answer from titles or summaries alone.
3. **Cite sources**: every factual claim in your answer must include a `[doc_id=X]` citation referencing the document you read.
4. **Explore the graph**: use `find_related_concepts`, `get_entity_documents`, or `find_experts` when the user's question involves entities, relationships, or expertise.
5. **Manage knowledge**: use create/update/archive tools only when the user explicitly asks to modify content. Always verify access before writing.

## Output format:
- Lead with a direct answer to the question.
- Follow with supporting details and `[doc_id=X]` citations.
- If no relevant documents were found after searching, say so clearly rather than guessing.
- Keep responses concise unless the user asks for depth.
"""

    def __init__(
        self,
        db: DatabaseConnection,
        user_id: int,
        model: str = "claude-opus-4-6",
    ) -> None:
        self.db = db
        self.user_id = user_id
        self.model = model
        self.client = anthropic.Anthropic()
        self.access_manager = AccessControlManager(db)
        self.query_engine = SemanticQueryEngine(db, user_id=user_id)
        tools = _create_tools(self.query_engine, self.access_manager, user_id, db)
        self._tool_map: Dict[str, Callable] = {t.schema["name"]: t.fn for t in tools}
        self._anthropic_tools: List[Dict[str, Any]] = [t.schema for t in tools]

    def run(self, question: str) -> Dict[str, Any]:
        """Run the agentic tool loop and return {"answer": str, "messages": list}."""
        messages: List[Dict[str, Any]] = [{"role": "user", "content": question}]

        while True:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=16000,
                system=self._SYSTEM,
                tools=self._anthropic_tools,
                thinking={"type": "adaptive"},
                messages=messages,
            ) as stream:
                response = stream.get_final_message()

            # Preserve full content (including thinking blocks) for subsequent turns.
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                answer = next((b.text for b in response.content if b.type == "text"), "")
                return {"answer": answer, "messages": messages}

            if response.stop_reason != "tool_use":
                break

            tool_results: List[Dict[str, Any]] = []
            for block in response.content:
                if block.type == "tool_use":
                    fn = self._tool_map.get(block.name)
                    if fn is not None:
                        try:
                            result = fn(**block.input)
                        except Exception as exc:
                            result = f"Tool error: {exc}"
                    else:
                        result = f"Unknown tool: {block.name}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })
            messages.append({"role": "user", "content": tool_results})

        answer = next((b.text for b in response.content if b.type == "text"), "")
        return {"answer": answer, "messages": messages}


def get_anthropic_agent(
    db: DatabaseConnection,
    user_id: int,
    model: str = "claude-opus-4-6",
) -> Optional[AnthropicOmniGraphAgent]:
    """Return an AnthropicOmniGraphAgent when ANTHROPIC_API_KEY is set; otherwise None."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    return AnthropicOmniGraphAgent(db, user_id, model=model)


__all__ = ["AnthropicOmniGraphAgent", "get_anthropic_agent", "_create_tools", "_format_docs"]
