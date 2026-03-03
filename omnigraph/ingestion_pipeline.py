"""
OmniGraph: Enterprise AI Knowledge Graph Database System
========================================================
Module: Data Ingestion Pipeline

Handles ingestion of documents from heterogeneous sources into the
OmniGraph knowledge base. Supports batch processing, text normalization,
content deduplication, document chunking, and automated version tracking.

Author: OmniGraph Team
"""

import hashlib
import logging
import re
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("omnigraph.ingestion")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SUPPORTED_SOURCE_TYPES = {
    "report", "research_paper", "email", "technical_doc",
    "code_repository", "project_artifact", "presentation",
    "support_ticket", "log", "other",
}

SENSITIVITY_LEVELS = {"public", "internal", "confidential", "restricted"}

DEFAULT_CHUNK_SIZE = 2000  # characters per chunk
DEFAULT_CHUNK_OVERLAP = 200  # overlap between chunks


class DatabaseConnection:
    """Manages PostgreSQL connection lifecycle."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        dbname: str = "omnigraph",
        user: str = "postgres",
        password: str = "postgres",
    ):
        self.connection_params = {
            "host": host,
            "port": port,
            "dbname": dbname,
            "user": user,
            "password": password,
        }
        self._conn = None

    def connect(self):
        """Establish database connection."""
        try:
            self._conn = psycopg2.connect(**self.connection_params)
            self._conn.autocommit = False
            logger.info("Database connection established.")
        except psycopg2.Error as exc:
            logger.error("Failed to connect to database: %s", exc)
            raise

    def disconnect(self):
        """Close database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
            logger.info("Database connection closed.")

    @property
    def conn(self):
        """Return active connection, reconnecting if necessary."""
        if self._conn is None or self._conn.closed:
            self.connect()
        return self._conn


class DocumentIngester:
    """
    Ingests documents into the OmniGraph knowledge base.

    Responsibilities:
    - Ingest single or batch documents
    - Normalize and clean text content
    - Detect and prevent duplicates via content hashing
    - Chunk large documents for downstream processing
    - Maintain version history on re-ingestion
    """

    def __init__(self, db: DatabaseConnection):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest_document(
        self,
        title: str,
        source_type: str,
        content: str,
        uploaded_by: int,
        sensitivity_level: str = "internal",
        taxonomy_id: Optional[int] = None,
        file_path: Optional[str] = None,
        mime_type: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> Optional[int]:
        """
        Ingest a single document into the knowledge base.

        Parameters
        ----------
        title : str
            Document title.
        source_type : str
            One of the SUPPORTED_SOURCE_TYPES.
        content : str
            Full text content of the document.
        uploaded_by : int
            User ID of the uploader.
        sensitivity_level : str
            Sensitivity classification (default: 'internal').
        taxonomy_id : int, optional
            Associated taxonomy node.
        file_path : str, optional
            Original file path.
        mime_type : str, optional
            MIME type of the original file.
        summary : str, optional
            Brief summary of the document.

        Returns
        -------
        int or None
            The document_id of the inserted document, or None on failure.
        """
        # Validate inputs
        self._validate_source_type(source_type)
        self._validate_sensitivity(sensitivity_level)

        # Normalize content
        normalized = self.normalize_text(content)
        content_hash = self._compute_hash(normalized)

        # Duplicate detection
        existing_id = self._find_duplicate(content_hash)
        if existing_id is not None:
            logger.warning(
                "Duplicate detected for '%s' (matches document_id=%d). "
                "Creating new version instead.",
                title, existing_id,
            )
            self.create_version(existing_id, normalized, content_hash, uploaded_by)
            return existing_id

        # Insert document
        file_size = len(normalized.encode("utf-8"))
        try:
            cur = self.db.conn.cursor()
            cur.execute(
                """
                INSERT INTO omnigraph.documents
                    (title, source_type, content, summary, content_hash,
                     file_path, file_size_bytes, mime_type, sensitivity_level,
                     taxonomy_id, uploaded_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING document_id
                """,
                (
                    title, source_type, normalized, summary, content_hash,
                    file_path, file_size, mime_type, sensitivity_level,
                    taxonomy_id, uploaded_by,
                ),
            )
            document_id = cur.fetchone()[0]
            self.db.conn.commit()
            logger.info("Ingested document '%s' (id=%d).", title, document_id)
            return document_id

        except psycopg2.Error as exc:
            self.db.conn.rollback()
            logger.error("Failed to ingest document '%s': %s", title, exc)
            return None

    def ingest_batch(
        self,
        documents: List[Dict],
    ) -> Tuple[int, int]:
        """
        Ingest a batch of documents.

        Parameters
        ----------
        documents : list of dict
            Each dict must contain at minimum: title, source_type, content,
            uploaded_by. Optional keys: sensitivity_level, taxonomy_id,
            file_path, mime_type, summary.

        Returns
        -------
        tuple of (int, int)
            (success_count, failure_count)
        """
        success = 0
        failure = 0

        logger.info("Starting batch ingestion of %d documents.", len(documents))

        for idx, doc in enumerate(documents, start=1):
            try:
                result = self.ingest_document(
                    title=doc["title"],
                    source_type=doc["source_type"],
                    content=doc["content"],
                    uploaded_by=doc["uploaded_by"],
                    sensitivity_level=doc.get("sensitivity_level", "internal"),
                    taxonomy_id=doc.get("taxonomy_id"),
                    file_path=doc.get("file_path"),
                    mime_type=doc.get("mime_type"),
                    summary=doc.get("summary"),
                )
                if result is not None:
                    success += 1
                else:
                    failure += 1
            except Exception as exc:
                logger.error("Batch item %d failed: %s", idx, exc)
                failure += 1

        logger.info(
            "Batch ingestion complete: %d succeeded, %d failed.",
            success, failure,
        )
        return success, failure

    # ------------------------------------------------------------------
    # Text Processing
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalize raw text content.

        - Strip leading/trailing whitespace
        - Collapse multiple whitespace into single spaces
        - Remove control characters (except newlines)
        - Normalize Unicode whitespace
        """
        if not text:
            return ""
        # Remove control characters except newlines and tabs
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        # Normalize whitespace
        text = re.sub(r"[ \t]+", " ", text)
        # Collapse multiple blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def chunk_document(
        content: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> List[Dict]:
        """
        Split a document into overlapping chunks for downstream processing.

        Parameters
        ----------
        content : str
            Full document text.
        chunk_size : int
            Maximum characters per chunk.
        overlap : int
            Number of overlapping characters between consecutive chunks.

        Returns
        -------
        list of dict
            Each dict has keys: chunk_index, start_pos, end_pos, text.
        """
        chunks = []
        start = 0
        index = 0

        while start < len(content):
            end = min(start + chunk_size, len(content))
            chunks.append({
                "chunk_index": index,
                "start_pos": start,
                "end_pos": end,
                "text": content[start:end],
            })
            if end >= len(content):
                break
            start = end - overlap
            index += 1

        logger.debug("Document chunked into %d segments.", len(chunks))
        return chunks

    # ------------------------------------------------------------------
    # Version Management
    # ------------------------------------------------------------------

    def create_version(
        self,
        document_id: int,
        new_content: str,
        content_hash: str,
        changed_by: int,
        change_summary: Optional[str] = None,
    ) -> Optional[int]:
        """
        Create a new version for an existing document.

        Parameters
        ----------
        document_id : int
            The document to version.
        new_content : str
            Updated content.
        content_hash : str
            Hash of the new content.
        changed_by : int
            User ID making the change.
        change_summary : str, optional
            Description of changes.

        Returns
        -------
        int or None
            The version_id, or None on failure.
        """
        try:
            cur = self.db.conn.cursor()

            # Determine next version number
            cur.execute(
                """
                SELECT COALESCE(MAX(version_number), 0) + 1
                FROM omnigraph.document_versions
                WHERE document_id = %s
                """,
                (document_id,),
            )
            next_version = cur.fetchone()[0]

            # Insert version record
            cur.execute(
                """
                INSERT INTO omnigraph.document_versions
                    (document_id, version_number, content, content_hash,
                     change_summary, changed_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING version_id
                """,
                (
                    document_id, next_version, new_content, content_hash,
                    change_summary or f"Version {next_version}", changed_by,
                ),
            )
            version_id = cur.fetchone()[0]
            self.db.conn.commit()

            logger.info(
                "Created version %d for document %d (version_id=%d).",
                next_version, document_id, version_id,
            )
            return version_id

        except psycopg2.Error as exc:
            self.db.conn.rollback()
            logger.error("Failed to create version for document %d: %s", document_id, exc)
            return None

    # ------------------------------------------------------------------
    # Metadata Extraction
    # ------------------------------------------------------------------

    @staticmethod
    def extract_metadata(file_path: str) -> Dict:
        """
        Extract basic metadata from a file path.

        Returns
        -------
        dict
            Keys: filename, extension, size_bytes, mime_type (guessed).
        """
        import mimetypes

        filename = os.path.basename(file_path)
        extension = os.path.splitext(filename)[1].lower()
        mime_guess, _ = mimetypes.guess_type(file_path)

        size_bytes = 0
        if os.path.exists(file_path):
            size_bytes = os.path.getsize(file_path)

        return {
            "filename": filename,
            "extension": extension,
            "size_bytes": size_bytes,
            "mime_type": mime_guess or "application/octet-stream",
        }

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_hash(content: str) -> str:
        """Compute SHA-256 hash of content for deduplication."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _find_duplicate(self, content_hash: str) -> Optional[int]:
        """Check if a document with the same content hash already exists."""
        try:
            cur = self.db.conn.cursor()
            cur.execute(
                "SELECT document_id FROM omnigraph.documents WHERE content_hash = %s LIMIT 1",
                (content_hash,),
            )
            row = cur.fetchone()
            return row[0] if row else None
        except psycopg2.Error as exc:
            logger.error("Duplicate check failed: %s", exc)
            return None

    @staticmethod
    def _validate_source_type(source_type: str) -> None:
        """Validate source type against allowed values."""
        if source_type not in SUPPORTED_SOURCE_TYPES:
            raise ValueError(
                f"Invalid source_type '{source_type}'. "
                f"Must be one of: {SUPPORTED_SOURCE_TYPES}"
            )

    @staticmethod
    def _validate_sensitivity(level: str) -> None:
        """Validate sensitivity level against allowed values."""
        if level not in SENSITIVITY_LEVELS:
            raise ValueError(
                f"Invalid sensitivity_level '{level}'. "
                f"Must be one of: {SENSITIVITY_LEVELS}"
            )


# ---------------------------------------------------------------------------
# Module Entry Point (for testing / standalone usage)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    db = DatabaseConnection()
    db.connect()

    ingester = DocumentIngester(db)

    # Example: single document ingestion
    doc_id = ingester.ingest_document(
        title="Test Document - Ingestion Pipeline Validation",
        source_type="technical_doc",
        content=(
            "This is a test document created by the ingestion pipeline. "
            "It validates that the pipeline correctly normalizes text, "
            "computes content hashes, and stores documents in PostgreSQL."
        ),
        uploaded_by=1,
        sensitivity_level="internal",
        summary="Pipeline validation test document.",
    )

    if doc_id:
        print(f"SUCCESS: Document ingested with id={doc_id}")

        # Example: chunking
        chunks = ingester.chunk_document(
            "A" * 5000, chunk_size=2000, overlap=200,
        )
        print(f"Document chunked into {len(chunks)} segments.")
    else:
        print("FAILED: Document ingestion returned None.")

    db.disconnect()
