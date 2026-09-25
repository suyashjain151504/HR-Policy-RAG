# Commands — Project Creation to Teardown (Floci-AWS)

Every command used to build this project locally, in order.
**Reference only.** A one-line comment sits above each command.

This is the Floci-AWS rewrite of the teacher GCP runbook
(`gcloud` / Vertex / Model Armor / Cloud Run / Google OAuth).
Emulator: **Floci AWS** on `http://localhost:4566`.
Not real AWS. Not Floci-GCP. Not real GCP.

Teacher Python entrypoints (`ingest.py`, `main.py`, `app.py`, …) are
kept. Cloud provisioning is replaced. Some app env keys change when
the Python is wired to S3 / llama.cpp / FastEmbed — those code changes
are not in this file.

## Values used throughout

```bash
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_DEFAULT_REGION=us-east-1
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test

AWS_REGION=us-east-1
S3_BUCKET_NAME=rag-hr-assistant-demo-hr-policies
QDRANT_COLLECTION_NAME=hr_policies
QDRANT_NOISY_COLLECTION_NAME=hr_policies_noisy_demo
ECS_CLUSTER=hr-rag
ECS_SERVICE=hr-rag-assistant
ECS_TASK_FAMILY=hr-rag-assistant
SECRET_NAME=streamlit-auth
APP_IMAGE=hr-rag-assistant:local
```

Dummy keys `test` / `test` are what Floci documents. They are not real
AWS credentials and must never be used against real AWS.

`LLM_BASE_URL`, `LLM_API_KEY` (dummy for the local OpenAI-compatible
server), `FALLBACK_LLM_BASE_URL`, `QDRANT_URL`, `QDRANT_API_KEY`, and
`LANGSMITH_API_KEY` stay in `.env`. They are not pasted into commands.

Dropped teacher secrets (not used in this runbook):
`GROQ_API_KEY`, `JINA_API_KEY`, `GCS_BUCKET_NAME`, Vertex project IDs,
Model Armor template IDs, Google OAuth client id/secret.

---

## Phase 0 — Prerequisites

Teacher: `gcloud auth login` + billing account list.

```bash
# Docker 20.10+ and Compose v2 (Floci install docs)
docker --version
docker compose version

# AWS CLI v2 — talks to Floci via AWS_ENDPOINT_URL
aws --version

# Pull the official Floci AWS image
docker pull floci/floci:latest
```

No Google account. No AWS account. No billing account.

Also needed on the machine (not Floci):
- `uv` for the Python env
- llama.cpp (or equivalent) serving your generator and judge
- Qdrant: local Docker *or* Qdrant Cloud free tier
- optional LangSmith free Developer key (no credit card)

---

## Phase 1 — Start Floci-AWS

Teacher: `gcloud projects create` + link billing + `gcloud config set project`.

There is no project and no billing on Floci. Starting the emulator *is*
the environment.

```bash
# Minimal compose snippet (from Floci quick start)
# services:
#   floci:
#     image: floci/floci:latest
#     ports:
#       - "4566:4566"
#     volumes:
#       - ./data/floci:/app/data
#       - /var/run/docker.sock:/var/run/docker.sock   # required if ECS tasks should really run
#     environment:
#       FLOCI_STORAGE_MODE: hybrid

docker compose up -d floci

# Point every AWS CLI / SDK call at the emulator (Floci AWS setup docs)
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_DEFAULT_REGION=us-east-1
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
```

Optional profile (same docs):

```
# ~/.aws/config
[profile floci]
region = us-east-1
output = json

# ~/.aws/credentials
[floci]
aws_access_key_id = test
aws_secret_access_key = test
```

```bash
export AWS_PROFILE=floci
```

Smoke test (Floci quick start):

```bash
aws s3 mb s3://floci-smoke --endpoint-url $AWS_ENDPOINT_URL
echo "ok" | aws s3 cp - s3://floci-smoke/hello.txt --endpoint-url $AWS_ENDPOINT_URL
aws s3 ls s3://floci-smoke --endpoint-url $AWS_ENDPOINT_URL
aws s3 rb s3://floci-smoke --force --endpoint-url $AWS_ENDPOINT_URL
```

---

## Phase 2 — Point local Python at Floci

Teacher: `gcloud auth application-default login` + set-quota-project.

```bash
# Same exports as Phase 1. boto3 must use endpoint_url=http://localhost:4566
# and dummy keys. Path-style S3: addressing_style = path / s3_use_path_style.
echo "$AWS_ENDPOINT_URL"
```

No ADC. No quota project. No Vertex.

---

## Phase 3 — “Enable APIs”

Teacher: enable `aiplatform.googleapis.com`, `storage.googleapis.com`,
`modelarmor.googleapis.com`.

**Drop.** Floci S3, Secrets Manager, ECS, CloudWatch Logs are on as soon
as the container is up. There is no `aws services enable`.

| Teacher API | This runbook |
|---|---|
| Vertex AI (`aiplatform`) | llama.cpp OpenAI-compatible server. Not Floci. |
| Cloud Storage | S3 on Floci (`:4566`) |
| Model Armor | In-process guardrail (Llama Guard / Presidio). No cloud command. |

---

## Phase 4 — Object store: create the bucket

Teacher: `gcloud storage buckets create gs://...`

```bash
aws s3 mb s3://$S3_BUCKET_NAME --endpoint-url $AWS_ENDPOINT_URL

aws s3api head-bucket --bucket $S3_BUCKET_NAME --endpoint-url $AWS_ENDPOINT_URL
```

`ingest.py` should push `data/` to `s3://$S3_BUCKET_NAME/raw/`, write
parsed files to `processed/`, then chunk + FastEmbed into Qdrant.
Until that code is switched from the GCS client to boto3, you can ingest
from local `data/` only.

---

## Phase 5 — Guardrail

Teacher: `gcloud model-armor templates create ...`

**No Floci command.** Do not create a Bedrock guardrail as a substitute.

Configure in `.env`:

```bash
GUARDRAIL_PROVIDER=llama_guard    # or none while wiring the pipeline
# GUARDRAIL_FAIL_OPEN_INPUT / GUARDRAIL_FAIL_OPEN_OUTPUT as needed
```

Input jailbreak + output scope/PII stay in-process, same place the
teacher called Model Armor.

---

## Phase 6 — Local Python environment

Unchanged idea. Env name can stay `genenv`.

```bash
uv venv genenv
source genenv/bin/activate          # Git Bash / macOS / Linux
# Windows Git Bash sometimes: source genenv/Scripts/activate
uv pip install -r requirements.txt
```

---

## Phase 7 — Configure `.env`

```bash
cp .env.example .env
```

Fill in (names you will actually use after the GCP→AWS code swap):

```
AWS_ENDPOINT_URL=http://localhost:4566
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_S3_BUCKET=$S3_BUCKET_NAME

QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION_NAME=hr_policies
QDRANT_NOISY_COLLECTION_NAME=hr_policies_noisy_demo

# FastEmbed — no Jina key
EMBEDDING_PROVIDER=fastembed

# Your local OpenAI-compatible endpoints (you pick the models)
LLM_BASE_URL=http://127.0.0.1:8080/v1
FALLBACK_LLM_BASE_URL=http://127.0.0.1:8081/v1
LLM_API_KEY=local

GUARDRAIL_PROVIDER=llama_guard

# LangSmith free Developer plan — do not add a credit card
# LANGSMITH_API_KEY=
# LANGSMITH_TRACING=false
```

Teacher keys that leave `.env`: `PROJECT_ID`, `LOCATION` as Vertex region,
`GCS_BUCKET_NAME`, `JINA_API_KEY`, `GROQ_API_KEY`,
`GUARDRAIL_PROVIDER=model_armor`, `MODEL_ARMOR_*`.

If the current teacher code still *requires* those names to boot, keep
the old names as unused placeholders until the code is patched. Do not
point them at real GCP.

---

## Phase 8 — Ingest the corpus into Qdrant

Same commands. Storage backend behind `ingest.py` must become S3-on-Floci
or local disk.

```bash
# local data/ -> S3 raw/ -> S3 processed/ -> Qdrant (both collections)
python ingest.py

# python ingest.py --force
# python ingest.py --hr-only
```

---

## Phase 9 — Run it locally

Same as teacher. No `gcloud auth` needed for Compose.

```bash
python main.py
streamlit run app.py
python demo_reliability.py

# LangSmith experiment — only if LANGSMITH_API_KEY is set.
# Teacher also required GROQ_API_KEY; point evaluate.py at the local
# judge endpoint instead, or skip this until that patch exists.
python evaluate.py

python -m hr_assistant.tracing
python redteam_test.py
```

```bash
docker compose run --rm ingest
docker compose up                  # app at http://localhost:8501
docker compose run --rm eval
```

Start llama.cpp (your models, your ports) *before* the app. This file
does not name models.

---

## Phase 10 — Deploy the container on Floci ECS

Teacher: enable Run/Build/Artifact Registry, bind Vertex/GCS/Armor IAM,
`gcloud run deploy --source .`

Floci has no `gcloud run` and no Cloud Build `--source`. Documented
stand-in is: build the image locally, then ECS (Floci ECS docs; tasks
run as real Docker containers unless `FLOCI_SERVICES_ECS_MOCK=true`).

```bash
docker build -t $APP_IMAGE .

aws ecs create-cluster --cluster-name $ECS_CLUSTER \
  --endpoint-url $AWS_ENDPOINT_URL

aws ecs register-task-definition \
  --family $ECS_TASK_FAMILY \
  --container-definitions "[
    {
      \"name\": \"app\",
      \"image\": \"${APP_IMAGE}\",
      \"cpu\": 256,
      \"memory\": 512,
      \"essential\": true,
      \"portMappings\": [{\"containerPort\": 8501, \"protocol\": \"tcp\"}]
    }
  ]" \
  --requires-compatibilities FARGATE \
  --cpu 256 --memory 512 \
  --network-mode awsvpc \
  --endpoint-url $AWS_ENDPOINT_URL

aws ecs create-service \
  --cluster $ECS_CLUSTER \
  --service-name $ECS_SERVICE \
  --task-definition $ECS_TASK_FAMILY \
  --desired-count 1 \
  --launch-type FARGATE \
  --endpoint-url $AWS_ENDPOINT_URL

aws ecs list-tasks --cluster $ECS_CLUSTER --endpoint-url $AWS_ENDPOINT_URL
```

If ECS + Docker socket is more pain than it is worth for Streamlit, skip
this phase and use Phase 9 `docker compose up`. Same container, less
theatre.

Do not grant `roles/aiplatform.user` or `roles/modelarmor.user`. Those
GCP roles do not exist here and the app must not call those APIs.

---

## Phase 11 — Auth secret (no Google OAuth)

Teacher: Secret Manager + OAuth consent screen + `secrets.toml` with
`[auth.google]` + Cloud Run `--set-secrets`.

Floci Secrets Manager is real-enough (CreateSecret / GetSecretValue /
DeleteSecret). Google accounts login is not. Use JWT or a static API key.

```bash
COOKIE_SECRET=$(openssl rand -hex 32)

cat > secrets.toml <<EOF
[auth]
cookie_secret = "$COOKIE_SECRET"

[auth.local]
mode = "jwt"
EOF

aws secretsmanager create-secret \
  --name $SECRET_NAME \
  --secret-string file://secrets.toml \
  --endpoint-url $AWS_ENDPOINT_URL

rm secrets.toml

aws secretsmanager get-secret-value \
  --secret-id $SECRET_NAME \
  --endpoint-url $AWS_ENDPOINT_URL
```

Allow-list (if you still want one) is an env var, not Google Test users:

```bash
ALLOWED_EMPLOYEE_EMAILS="you@example.com"
```

Mounting that secret into an ECS task is app-compose work (`secrets.toml`
path). There is no `gcloud run --set-secrets` flag on Floci.

---

## Phase 12 — LLM routing and fallback

Teacher: in-process LiteLLM, Vertex Gemini primary, Groq fallback,
`GROQ_API_KEY` on Cloud Run.

Keep LiteLLM in-process. Change the two backends in config, not with a
deploy flag:

```
LLM_BASE_URL=http://<generator-host>:8080/v1
FALLBACK_LLM_BASE_URL=http://<judge-or-fallback-host>:8081/v1
```

No second “LLM gateway” service. Teacher already dropped that pattern
after Cloud Run IAM ate the Bearer token.

---

## Phase 13 — Post-deploy verification

```bash
python evaluate.py
python redteam_test.py
```

Smoke the UI: normal HR question (cited answer), repeat (cache hit),
“ignore all previous instructions” (input blocked), off-topic finance
(refusal).

Logs — teacher used `gcloud run services logs read`. Floci CloudWatch
Logs exists; `aws logs tail` is not in their examples. Documented shape:

```bash
aws logs filter-log-events \
  --log-group-name /app/backend \
  --filter-pattern "ERROR" \
  --endpoint-url $AWS_ENDPOINT_URL
```

Until the app actually writes to that group, use:

```bash
docker logs -f floci
docker compose logs -f
```

---

## Phase 14 — Teardown

Nothing here bills a cloud account. Still tear down so the next run is clean.

```bash
# 1. ECS service + cluster
aws ecs delete-service \
  --cluster $ECS_CLUSTER \
  --service $ECS_SERVICE \
  --force \
  --endpoint-url $AWS_ENDPOINT_URL

aws ecs delete-cluster --cluster $ECS_CLUSTER --endpoint-url $AWS_ENDPOINT_URL

# 2. Secret (recovery window is Floci’s documented delete shape)
aws secretsmanager delete-secret \
  --secret-id $SECRET_NAME \
  --recovery-window-in-days 7 \
  --endpoint-url $AWS_ENDPOINT_URL

# 3. Qdrant collections (Qdrant is not Floci)
python -c "
from qdrant_client import QdrantClient
from hr_assistant import config
client = QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY)
client.delete_collection(config.QDRANT_COLLECTION_NAME)
client.delete_collection(config.QDRANT_NOISY_COLLECTION_NAME)
"

# 4. No Model Armor template to delete

# 5. Bucket
aws s3 rb s3://$S3_BUCKET_NAME --force --endpoint-url $AWS_ENDPOINT_URL

# 6. Stop emulator + local app
docker compose down -v

# 7. No gcloud projects delete

# 8. Local cleanup
rm -rf genenv
rm -f .env
```

---

## Cost note

Floci-AWS: ₹0.
llama.cpp on your laptop / Mac Mini: ₹0.
FastEmbed: ₹0.
Local Qdrant Docker: ₹0. Qdrant Cloud free tier: ₹0 if you stay in quota.
LangSmith Developer: ₹0 if you do **not** add a card (5k traces/month).

Teacher cost note mentioned Gemini Flash, Jina, Model Armor, Groq, GCS.
Those are out of this runbook.

---

## Model / embedding migration

Teacher switched Gemini model IDs with `LLM_MODEL_NAME` and warned that
changing `EMBEDDING_MODEL_NAME` needs `python ingest.py --force`.

Same rule here: change the llama.cpp process or FastEmbed model name in
`.env`. If the embedding dimension changes, rebuild both Qdrant
collections with `--force`.
