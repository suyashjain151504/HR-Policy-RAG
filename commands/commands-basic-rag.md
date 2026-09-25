# Commands — `basic-rag` branch (Floci-AWS)

Stage 1 of 3. Plain RAG only: retrieval → hybrid search → re-rank →
agent → cited answer.

**No** Model Armor, **no** OAuth, **no** Cloud Run / ECS, **no** LiteLLM
router, **no** eval/red-team. Those live in the full
`commands_all_phases.md`.

This is the Floci-AWS rewrite of the teacher `basic-rag` GCP runbook.
Emulator: **Floci AWS** on `http://localhost:4566`.
Not real AWS. Not Floci-GCP. Not real GCP.

---

## Values used on this branch

```bash
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_DEFAULT_REGION=us-east-1
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test

AWS_REGION=us-east-1
S3_BUCKET_NAME=rag-hr-assistant-demo-hr-policies
QDRANT_COLLECTION_NAME=hr_policies
QDRANT_NOISY_COLLECTION_NAME=hr_policies_noisy_demo
```

Dummy keys `test` / `test` are Floci’s documented credentials. Never use
them against real AWS.

`QDRANT_URL` / `QDRANT_API_KEY` stay in `.env`.
Dropped teacher values: `PROJECT_ID`, `PROJECT_NUMBER`,
`BILLING_ACCOUNT_ID`, `JINA_API_KEY`, Vertex region as `LOCATION`.

---

## 1. Start Floci-AWS (replaces GCP project + billing)

Teacher: `gcloud auth login`, create project, link billing, set project.

```bash
docker --version
docker compose version
aws --version
docker pull floci/floci:latest

docker compose up -d floci

export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_DEFAULT_REGION=us-east-1
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
```

No Google login. No billing account. No `gcloud projects create`.

---

## 2. Point local credentials at Floci

Teacher: `gcloud auth application-default login` + quota project.

```bash
echo "$AWS_ENDPOINT_URL"
# boto3 in ingest.py must use this endpoint and the dummy keys
```

---

## 3. “Enable APIs”

Teacher: `gcloud services enable aiplatform.googleapis.com storage.googleapis.com`.

**Drop.** S3 is available as soon as Floci is up.

- Vertex / Gemini (`aiplatform`) → your local llama.cpp endpoint (wired
  later; this branch can still run retrieval-only while that lands).
- Cloud Storage → S3 on Floci.

---

## 4. Create the object-store bucket

Teacher: `gcloud storage buckets create gs://$GCS_BUCKET_NAME`.

```bash
aws s3 mb s3://$S3_BUCKET_NAME --endpoint-url $AWS_ENDPOINT_URL

aws s3api head-bucket --bucket $S3_BUCKET_NAME --endpoint-url $AWS_ENDPOINT_URL
```

`ingest.py` should upload `data/` into this bucket. Until the GCS client
is swapped for boto3, ingest from local `data/`.

---

## 5. Python environment

```bash
uv venv hrrenv
source hrrenv/bin/activate          # Git Bash / macOS / Linux
# Windows Git Bash sometimes: source hrrenv/Scripts/activate
uv pip install -r requirements.txt
```

---

## 6. `.env`

```bash
cp .env.example .env
```

Fill in:

```
AWS_ENDPOINT_URL=http://localhost:4566
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_S3_BUCKET=rag-hr-assistant-demo-hr-policies

QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION_NAME=hr_policies
QDRANT_NOISY_COLLECTION_NAME=hr_policies_noisy_demo

EMBEDDING_PROVIDER=fastembed

LLM_BASE_URL=http://127.0.0.1:8080/v1
LLM_API_KEY=local
```

No `JINA_API_KEY`. No `PROJECT_ID` / Vertex `LOCATION` unless the current
teacher `config.py` still refuses to boot without them — then leave dummy
strings and patch config next.

---

## 7. Ingest the corpus into Qdrant

```bash
# local data/ -> S3 raw/ -> S3 processed/ -> chunk -> FastEmbed -> Qdrant
# Builds BOTH collections (hr_policies + hr_policies_noisy_demo).
python ingest.py

python ingest.py --force
python ingest.py --hr-only
python ingest.py --noisy-only
```

---

## 8. Run it

```bash
python main.py                    # CLI demo
streamlit run app.py              # http://localhost:8501
langgraph dev                     # LangGraph Studio
python -m hr_assistant.tracing    # only if LANGSMITH_TRACING=true
```

Start your local LLM server before the agent if this branch already
calls a generator.

---

## Cost note

Floci-AWS, FastEmbed, local Qdrant, local LLM: ₹0.
Teacher note about Vertex Gemini Flash + Jina pay-per-call does not apply.

---

## If something breaks

Most common on this branch:
- Floci not running → `docker compose up -d floci` and re-export the four AWS vars
- Bucket missing → Phase 4
- Qdrant collection missing → `python ingest.py`
- App still importing `google.cloud.storage` → S3 client not patched yet; ingest from disk
