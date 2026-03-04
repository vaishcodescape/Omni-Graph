"""Retrieval-augmented generation (RAG) over OmniGraph using LangGraph."""

from __future__ import annotations

from typing import Dict, List, TypedDict
from langgraph.graph import StateGraph, END

from .access_control_audit import AccessControlManager
from .ingestion_pipeline import DatabaseConnection
from .semantic_query_engine import SemanticQueryEngine


class RAGState(TypedDict):
    """State for the RAG workflow (question, retrieved docs, answer)."""

    question: str
    retrieved: List[Dict]
    answer: str


class OmniGraphRAG:
    """LangGraph-based RAG orchestrator for OmniGraph."""

    def __init__(self, db: DatabaseConnection, user_id: int, llm) -> None:
        self.db = db
        self.user_id = user_id
        self.llm = llm

        self.access_manager = AccessControlManager(self.db)
        self.query_engine = SemanticQueryEngine(self.db, user_id=self.user_id)

        self.app = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(RAGState)
        workflow.add_node("retrieve", self._retrieve)
        workflow.add_node("generate", self._generate)
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)
        return workflow.compile()

    def _retrieve(self, state: RAGState) -> RAGState:
        """Retrieve relevant documents from OmniGraph for the given question."""
        question = state["question"]
        results = self.query_engine.search(
            question,
            strategy="hybrid",
            limit=10,
        )

        filtered: List[Dict] = []
        for r in results:
            doc_id = r.get("document_id")
            if doc_id is None:
                continue
            if not self.access_manager.check_access(
                self.user_id,
                "document",
                doc_id,
                "read",
            ):
                continue
            filtered.append(r)

        return {
            "question": question,
            "retrieved": filtered,
            "answer": state.get("answer", ""),
        }

    def _generate(self, state: RAGState) -> RAGState:
        """Call the LLM with the question and retrieved documents."""
        question = state["question"]
        docs = state["retrieved"]

        context_snippets: List[str] = []
        
        for d in docs:
            title = d.get("title", "")
            summary = d.get("summary") or ""
            sensitivity = d.get("sensitivity_level", "")
            context_snippets.append(
                f"Title: {title}\n"
                f"Sensitivity: {sensitivity}\n"
                f"Summary: {summary}\n"
            )

        context_block = "\n\n".join(context_snippets) if context_snippets else "No documents were retrieved."

        prompt = (
            "You are an assistant answering questions using an internal knowledge graph.\n\n"
            "Context documents:\n"
            f"{context_block}\n\n"
            "Instructions:\n"
            "- Use only the information in the context when possible.\n"
            "- If the answer is not clearly supported, say that the context is insufficient.\n"
            "- Keep the answer concise but specific.\n\n"
            f"Question: {question}\n"
            "Answer:"
        )

        llm_result = self.llm.invoke(prompt)
        if hasattr(llm_result, "content"):
            answer_text = getattr(llm_result, "content")
        else:
            answer_text = str(llm_result)

        return {
            "question": question,
            "retrieved": docs,
            "answer": answer_text,
        }

    def run(self, question: str) -> RAGState:
        """Run the RAG workflow for a single question."""
        initial_state: RAGState = {"question": question, "retrieved": [], "answer": ""}
        return self.app.invoke(initial_state)


__all__ = ["RAGState", "OmniGraphRAG"]

