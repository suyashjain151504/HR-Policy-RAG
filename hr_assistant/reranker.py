"""Re-rank retrieved candidates with a cross-encoder.

Retrieval is fast but rough. The reranker reads the question and each
candidate chunk together and re-scores the shortlist.

RERANKER_PROVIDER in .env picks the scorer:

  jina       Jina Rerank API (RERANKER_MODEL_NAME, JINA_API_KEY). REST.
  fastembed  Local ONNX cross-encoder. Default Xenova/ms-marco-MiniLM-L-6-v2.
             No Jina call. First run downloads the model (~80MB).

Both return the same thing: the top_n Documents, best first.
"""

import requests
from fastembed.rerank.cross_encoder import TextCrossEncoder

from hr_assistant import config

JINA_RERANK_URL = "https://api.jina.ai/v1/rerank"
_FASTEMBED_RERANKER = None


def _jina_rerank(query: str, candidates: list, top_n: int) -> list:
    """Jina scores query+chunk pairs and returns indexes into candidates."""
    if not config.JINA_API_KEY:
        raise ValueError("RERANKER_PROVIDER=jina requires JINA_API_KEY in .env")

    response = requests.post(
        JINA_RERANK_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.JINA_API_KEY}",
        },
        json={
            "model": config.RERANKER_MODEL_NAME,
            "query": query,
            "top_n": top_n,
            "documents": [c.page_content for c in candidates],
            "return_documents": False,
        },
        timeout=30,
    )
    response.raise_for_status()

    # each result carries an "index" back into the original candidates list
    ranked = response.json()["results"]
    return [candidates[r["index"]] for r in ranked]


def _fastembed_reranker() -> TextCrossEncoder:
    """One local cross-encoder for the process. Loaded on first rerank."""
    global _FASTEMBED_RERANKER
    if _FASTEMBED_RERANKER is None:
        _FASTEMBED_RERANKER = TextCrossEncoder(
            model_name=config.FASTEMBED_RERANKER_MODEL
        )
    return _FASTEMBED_RERANKER


def _fastembed_rerank(query: str, candidates: list, top_n: int) -> list:
    """Score every candidate locally, then keep the highest scores.

    rerank() returns one float per document, same order as candidates.
    It does not return indexes, so we sort here.
    """
    scores = list(
        _fastembed_reranker().rerank(
            query,
            [c.page_content for c in candidates],
        )
    )
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return [candidates[i] for i in order[:top_n]]


def rerank(
    query: str,
    candidates: list,
    top_n: int = config.TOP_K_RESULTS,
) -> list:
    """Re-rank `candidates` (a wide shortlist — see RERANK_CANDIDATE_K) and
    return the top `top_n` Documents, best first."""
    if not candidates:
        return []

    provider = (config.RERANKER_PROVIDER or "jina").strip().lower()
    if provider == "jina":
        return _jina_rerank(query, candidates, top_n)
    if provider == "fastembed":
        return _fastembed_rerank(query, candidates, top_n)
    raise ValueError(
        f"Unknown RERANKER_PROVIDER={provider!r}. Use 'jina' or 'fastembed'."
    )
