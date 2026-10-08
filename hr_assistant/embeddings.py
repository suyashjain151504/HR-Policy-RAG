"""Turn text into vectors.

Set EMBEDDING_PROVIDER in .env:

  jina       Jina Embeddings API (JINA_API_KEY). Needs network.
  fastembed  Local ONNX via FastEmbed. No Jina key.
             Default model: BAAI/bge-small-en-v1.5 (384-dim, 512 token window).

Do not mix providers in one Qdrant collection. Different models produce
different vector sizes. After a switch run ingest with --force.

This module does not talk to S3. It only returns a LangChain Embeddings
object. Ingest and the retriever call embed_documents / embed_query on it.
"""

from langchain_community.embeddings import FastEmbedEmbeddings, JinaEmbeddings

from hr_assistant import config

_FASTEMBED_DEFAULT = "BAAI/bge-small-en-v1.5"


def get_jina_embeddings():
    """Jina REST embeddings. Reads JINA_API_KEY and EMBEDDING_MODEL_NAME."""
    if not config.JINA_API_KEY:
        raise ValueError("EMBEDDING_PROVIDER=jina requires JINA_API_KEY in .env")
    return JinaEmbeddings(
        jina_api_key=config.JINA_API_KEY,
        model_name=config.EMBEDDING_MODEL_NAME,
    )


def get_fastembed_embeddings():
    """Local FastEmbed. Optional FASTEMBED_EMBEDDING_MODEL overrides the default."""
    model_name = config.FASTEMBED_EMBEDDING_MODEL or _FASTEMBED_DEFAULT
    return FastEmbedEmbeddings(model_name=model_name)


def get_embeddings_model():
    """Return the embeddings client selected by EMBEDDING_PROVIDER."""
    provider = (config.EMBEDDING_PROVIDER or "jina").strip().lower()
    if provider == "jina":
        return get_jina_embeddings()
    if provider == "fastembed":
        return get_fastembed_embeddings()
    raise ValueError(
        f"Unknown EMBEDDING_PROVIDER={provider!r}. Use 'jina' or 'fastembed'."
    )
