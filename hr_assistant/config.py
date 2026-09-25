"""01 · config — every setting, read from .env. Everything imports this.

config.py holds values only (keys, URLs, model ids, sizes). The
system-prompt text lives next door in prompts.py (02).
"""

import os
from dotenv import load_dotenv

load_dotenv()

## FLOCI-AWS (not GCP)

AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "test")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "test")

## ENV VAR / SECRETS

JINA_API_KEY = os.getenv("JINA_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

## OBJECT STORAGE — Floci S3 (teacher used GCS)

S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET") or os.getenv("S3_BUCKET_NAME")
# Keep the old name so any leftover GCS_* reads do not crash during the port.
GCS_BUCKET_NAME = S3_BUCKET_NAME

# Raw zone — original files, untouched. Ingestion uploads the local data/
# tree here: HR policies under S3_PREFIX, the non-HR noise docs under
# NOISE_S3_PREFIX.
S3_PREFIX = "raw/hr-policies/"
NOISE_S3_PREFIX = "raw/other-data/"
GCS_PREFIX = S3_PREFIX
NOISE_GCS_PREFIX = NOISE_S3_PREFIX

# Processed zone — one JSON record per raw file (parsed text + metadata),
# written by processor.py (05). Ingestion reads ONLY from here, so
# PDFs/DOCX/PPTX are parsed once, not on every rebuild.
PROCESSED_HR_PREFIX = "processed/hr-policies/"
PROCESSED_NOISE_PREFIX = "processed/other-data/"

## QDRANT — Qdrant Cloud cluster URL + key, not the cluster display name

QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "hr_policies")

# A second collection holding HR docs + non-HR noise together. `ingest.py`
# builds it alongside the clean one; the app connects to the clean
# collection. The noisy collection is where a later stage tests retrieval
# against real cross-domain noise.
QDRANT_NOISY_COLLECTION_NAME = os.getenv(
    "QDRANT_NOISY_COLLECTION_NAME", "hr_policies_noisy_demo"
)

## PROVIDERS
# jina      = teacher path (Jina Embeddings + Rerank API)
# fastembed = local ONNX (FastEmbed embed + MiniLM rerank)
# Mixing providers in one collection needs `python ingest.py --force`.

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "jina")
RERANKER_PROVIDER = os.getenv("RERANKER_PROVIDER", "jina")

## MODELS
# All three are env-overridable so a model swap needs no code change.

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://127.0.0.1:8080/v1")
FALLBACK_LLM_BASE_URL = os.getenv("FALLBACK_LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "local")
LITELLM_URL = os.getenv("LITELLM_URL", "http://127.0.0.1:4000")

# Id your local llama.cpp / LiteLLM server expects. Not Vertex Gemini.
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "")

# Fallback when llama.cpp is down. Groq Cloud (console.groq.com), not xAI Grok.
# LiteLLM model id: groq/<id-from-console>
FALLBACK_LLM_PROVIDER = os.getenv("FALLBACK_LLM_PROVIDER", "groq")
FALLBACK_MODEL_NAME = os.getenv("FALLBACK_MODEL_NAME", "groq/openai/gpt-oss-20b")

# Teacher Jina defaults. Used when EMBEDDING_PROVIDER=jina.
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "jina-embeddings-v2-base-en")
RERANKER_MODEL_NAME = os.getenv("RERANKER_MODEL_NAME", "jina-reranker-v2-base-multilingual")

# Local FastEmbed stack. Used when PROVIDER=fastembed.
FASTEMBED_EMBEDDING_MODEL = os.getenv("FASTEMBED_EMBEDDING_MODEL", "")
FASTEMBED_RERANKER_MODEL = os.getenv(
    "FASTEMBED_RERANKER_MODEL", "Xenova/ms-marco-MiniLM-L-6-v2"
)

## GUARDRAILS / AUTH (not Model Armor, not Google OAuth)

GUARDRAIL_PROVIDER = os.getenv("GUARDRAIL_PROVIDER", "llama_guard")
AUTH_MODE = os.getenv("AUTH_MODE", "jwt")

## CHUNK / TEXT SPLITTING

CHUNK_SIZE = 500
CHUNK_OVERLAP = 60

## RETRIEVAL RESULTS

# Broad questions ("list all maternity leave provisions") need enough
# chunks in context to answer in full; at CHUNK_SIZE=500 a single
# multi-section policy doc is often 4-5 chunks, so a small top_k can't
# return the whole thing no matter how the prompt is worded.
TOP_K_RESULTS = 5
RERANK_CANDIDATE_K = 12  # wider shortlist retrieved before re-ranking

## LANGSMITH — request tracing (env-var based; langchain auto-traces)

LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "false")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "hr-policy-assistant")


def check_api_keys() -> None:
    """Stop early with a clear message if a required key/config is missing."""
    required = [
        ("QDRANT_URL", QDRANT_URL),
        ("QDRANT_API_KEY", QDRANT_API_KEY),
        ("AWS_S3_BUCKET", S3_BUCKET_NAME),
    ]
    if EMBEDDING_PROVIDER == "jina" or RERANKER_PROVIDER == "jina":
        required.append(("JINA_API_KEY", JINA_API_KEY))
    missing = [name for name, value in required if not value]
    if missing:
        raise ValueError(f"Missing required .env values: {', '.join(missing)}")
