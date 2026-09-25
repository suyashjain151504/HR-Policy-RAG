"""Read text documents out of Floci S3.

Binary files (.pdf / .docx / .pptx) are parsed in processor.py.
This module only loads text that is already text.
"""

import json

import boto3
from botocore.config import Config as BotoConfig
from langchain_core.documents import Document

from hr_assistant import config


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=config.AWS_ENDPOINT_URL,
        region_name=config.AWS_DEFAULT_REGION,
        aws_access_key_id=config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
        config=BotoConfig(s3={"addressing_style": "path"}),
    )


def extract_policy_category(text: str) -> str:
    """Read the category from the first few lines of a policy or noise file."""
    for line in text.splitlines()[:5]:
        stripped = line.strip().lower()
        if stripped.startswith("policy category:"):
            return line.split(":", 1)[1].strip()
        if stripped.startswith("category:"):
            return line.split(":", 1)[1].strip()
    return "Unknown"


def load_documents_from_s3(
    bucket_name: str = config.S3_BUCKET_NAME,
    prefix: str = config.S3_PREFIX,
) -> list[Document]:
    """Download every .txt under the raw prefix. One Document per file."""
    client = _s3_client()
    documents = []
    token = None
    while True:
        kwargs = {"Bucket": bucket_name, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        page = client.list_objects_v2(**kwargs)
        for obj in page.get("Contents") or []:
            key = obj["Key"]
            if not key.endswith(".txt"):
                continue
            body = client.get_object(Bucket=bucket_name, Key=key)["Body"].read()
            text = body.decode("utf-8")
            filename = key.rsplit("/", 1)[-1]
            documents.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": filename,
                        "policy_category": extract_policy_category(text),
                        "s3_path": f"s3://{bucket_name}/{key}",
                    },
                )
            )
        if not page.get("IsTruncated"):
            break
        token = page.get("NextContinuationToken")
    return documents


def load_processed_documents_from_s3(
    bucket_name: str = config.S3_BUCKET_NAME,
    prefixes: tuple[str, ...] = (
        config.PROCESSED_HR_PREFIX,
        config.PROCESSED_NOISE_PREFIX,
    ),
) -> list[Document]:
    """Download processed JSON from S3 and turn each record into a Document."""
    client = _s3_client()
    documents = []
    for prefix in prefixes:
        token = None
        while True:
            kwargs = {"Bucket": bucket_name, "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            page = client.list_objects_v2(**kwargs)
            for obj in page.get("Contents") or []:
                key = obj["Key"]
                if not key.endswith(".json"):
                    continue
                body = client.get_object(Bucket=bucket_name, Key=key)["Body"].read()
                record = json.loads(body.decode("utf-8"))
                documents.append(
                    Document(
                        page_content=record["text"],
                        metadata={
                            "source": record["source"],
                            "policy_category": record["policy_category"],
                            "s3_path": record.get("raw_s3_path", ""),
                        },
                    )
                )
            if not page.get("IsTruncated"):
                break
            token = page.get("NextContinuationToken")
    return documents
