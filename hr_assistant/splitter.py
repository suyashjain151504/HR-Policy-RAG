"""Chop each document into small, searchable, overlapping chunks."""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from hr_assistant import config

# CHUNK_SIZE / CHUNK_OVERLAP in config.py are CHARACTERS, not tokens.
#
# Jina embeddings-v2-base-en: 8192 token window. 500 chars is fine.
#
# FastEmbed default BAAI/bge-small-en-v1.5: 512 token window.
# English is roughly 4 characters per token, so 500 chars ≈ 125 tokens.
# That is well under 512. Do not drop to 370 unless you change embedder
# to sentence-transformers/all-MiniLM-L6-v2 (256 token window).
#
# FastEmbed reranker Xenova/ms-marco-MiniLM-L-6-v2: 512 tokens for
# query + chunk together. 500-char chunks + a short query still fit.
#
# Switching EMBEDDING_PROVIDER does not require a splitter change.
# Re-ingest if you change the embedding model (vector size changes).


def split_into_chunks(documents):
    """Split documents into overlapping chunks. Metadata carries over."""
    chunk_size = config.CHUNK_SIZE
    chunk_overlap = config.CHUNK_OVERLAP

    # If you later embed with all-MiniLM-L6-v2 (256 tokens), uncomment:
    # if getattr(config, "EMBEDDING_PROVIDER", "") == "fastembed" and (
    #     getattr(config, "FASTEMBED_EMBEDDING_MODEL", "")
    #     == "sentence-transformers/all-MiniLM-L6-v2"
    # ):
    #     chunk_size, chunk_overlap = 400, 50

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return text_splitter.split_documents(documents)
