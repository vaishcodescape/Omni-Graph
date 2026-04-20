from __future__ import annotations

import logging
import os
from typing import List

logger = logging.getLogger("omnigraph.embedder")

MODEL_NAME = "voyage-3"
EMBEDDING_DIM = 1024

_client = None


def _get_client():
    global _client
    if _client is None:
        try:
            import voyageai
        except ImportError as exc:
            raise ImportError(
                "voyageai is required for semantic search. "
                "Install it with: pip install voyageai"
            ) from exc
        api_key = os.getenv("VOYAGE_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "VOYAGE_API_KEY environment variable is not set. "
                "Get your key at https://www.voyageai.com/"
            )
        _client = voyageai.Client(api_key=api_key)
    return _client


def generate_embedding(text: str, input_type: str = "document") -> List[float]:
    client = _get_client()
    result = client.embed([text.strip()[:32000]], model=MODEL_NAME, input_type=input_type)
    return [round(float(v), 6) for v in result.embeddings[0]]
