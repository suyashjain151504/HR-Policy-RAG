"""The one place documents get loaded into Qdrant.

Orchestrates document_loader, processor, splitter, embeddings, vector_store.

    local data/ files
        -> S3  raw/hr-policies/   +  raw/other-data/    (upload)
        -> S3  processed/...      (pdf/docx/pptx parsed to JSON, once)
        -> chunk -> embed -> Qdrant collections

Idempotent by default: a Qdrant collection that already has points in it is
left alone. Pass force=True to rebuild it from scratch. ingest.py is
the runnable entry point; the app never ingests — it connects to what this
built.
"""

import glob
import logging
import os

import boto3
from botocore.config import Config as BotoConfig

from hr_assistant import config
from hr_assistant.document_loader import (
    load_documents_from_s3,
    load_processed_documents_from_s3,
)
from hr_assistant.processor import process_raw_to_json
from hr_assistant.splitter import split_into_chunks
from hr_assistant.vector_store import build_vector_store, collection_exists

logger = logging.getLogger(__name__)

_LOCAL_HR_GLOB = os.path.join("data", "*.txt")
_LOCAL_NOISE_GLOB = os.path.join("data", "noise", "*")


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=config.AWS_ENDPOINT_URL,
        region_name=config.AWS_DEFAULT_REGION,
        aws_access_key_id=config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
        config=BotoConfig(s3={"addressing_style": "path"}),
    )


def upload_corpus_to_s3() -> None:
    """Push the local data/ files to the S3 raw zone. Overwrites — cheap
    and keeps the bucket in sync with the repo."""
    client = _s3_client()
    bucket = config.S3_BUCKET_NAME

    pairs = [
        (_LOCAL_HR_GLOB, config.S3_PREFIX),
        (_LOCAL_NOISE_GLOB, config.NOISE_S3_PREFIX),
    ]
    for local_glob, prefix in pairs:
        files = [f for f in glob.glob(local_glob) if os.path.isfile(f)]
        for path in files:
            key = f"{prefix}{os.path.basename(path)}"
            with open(path, "rb") as handle:
                client.put_object(Bucket=bucket, Key=key, Body=handle.read())
        logger.info(
            "Uploaded %d file(s) -> s3://%s/%s",
            len(files),
            bucket,
            prefix,
        )


def ingest_hr_policies(force: bool = False) -> None:
    """The clean HR-only collection the app connects to."""
    name = config.QDRANT_COLLECTION_NAME
    if collection_exists(name) and not force:
        logger.info(
            "Collection '%s' already populated — skipping (use --force to rebuild).",
            name,
        )
        return

    documents = load_documents_from_s3()
    chunks = split_into_chunks(documents)
    build_vector_store(chunks, hybrid=True, collection_name=name)
    logger.info(
        "Ingested %d HR document(s) -> %d chunk(s) into '%s'.",
        len(documents),
        len(chunks),
        name,
    )


def ingest_noisy_corpus(force: bool = False) -> None:
    """The mixed HR + noise collection — built alongside the clean one so a
    later stage can test retrieval against real cross-domain noise.

    Raw pdf/docx/pptx are parsed into the processed JSON zone first —
    always on force=True, otherwise only when that zone is still empty."""
    name = config.QDRANT_NOISY_COLLECTION_NAME
    if collection_exists(name) and not force:
        logger.info(
            "Collection '%s' already populated — skipping (use --force to rebuild).",
            name,
        )
        return

    if force:
        logger.info("Parsing raw files into the processed/ zone...")
        process_raw_to_json()

    documents = load_processed_documents_from_s3()
    if not documents:
        logger.info("Processed zone is empty — parsing raw files...")
        process_raw_to_json()
        documents = load_processed_documents_from_s3()

    if not documents:
        raise RuntimeError(
            "Still no processed documents after parsing — check the S3 raw zone."
        )

    chunks = split_into_chunks(documents)
    build_vector_store(chunks, hybrid=True, collection_name=name)
    logger.info(
        "Ingested %d document(s) (HR + noise) -> %d chunk(s) into '%s'.",
        len(documents),
        len(chunks),
        name,
    )


def run_ingestion(
    force: bool = False,
    hr: bool = True,
    noisy: bool = True,
    upload: bool = True,
) -> None:
    config.check_api_keys()
    if upload:
        upload_corpus_to_s3()
    if hr:
        ingest_hr_policies(force=force)
    if noisy:
        ingest_noisy_corpus(force=force)
