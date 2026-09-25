# HR Policy RAG — Floci-AWS Terraform
#
# Matches the teacher GCP footprint, not the research-agent stack this file
# was referenced from:
#   GCS bucket          → 1 S3 bucket
#   Secret Manager      → 1 Secrets Manager secret
#   1 Cloud Run service → 1 ECS cluster + 1 ECS service + 1 task definition
#
# The task definition has TWO containers (same service, not a second service):
#   app      Streamlit / FastAPI image
#   litellm  sidecar gateway on :4000, talks to llama.cpp on the host
#
# FastEmbed stays inside the app image. Red-team stays a local script.
# No PyRIT service, no ALB pair, no RDS, no Redis, no EventBridge, no ASG.
#
# Floci must be up BEFORE terraform init (state lives in Floci S3 + DynamoDB).
# Compose for the emulator (Docker Desktop / Windows):
#
#   services:
#     floci:
#       image: floci/floci:latest
#       ports: ["4566:4566"]
#       volumes:
#         - ./data/floci:/app/data
#         - /var/run/docker.sock:/var/run/docker.sock
#       environment:
#         FLOCI_STORAGE_MODE: hybrid
#         FLOCI_SERVICES_ECS_PUBLISH_AWSVPC_PORTS_TO_HOST: "true"
#
# Bootstrap state (once, PowerShell):
#   $env:AWS_ENDPOINT_URL="http://localhost:4566"
#   $env:AWS_DEFAULT_REGION="us-east-1"
#   $env:AWS_ACCESS_KEY_ID="test"
#   $env:AWS_SECRET_ACCESS_KEY="test"
#   aws s3 mb s3://hr-rag-tfstate --endpoint-url $env:AWS_ENDPOINT_URL
#   aws dynamodb create-table --table-name hr-rag-tf-locks `
#     --attribute-definitions AttributeName=LockID,AttributeType=S `
#     --key-schema AttributeName=LockID,KeyType=HASH `
#     --billing-mode PAY_PER_REQUEST `
#     --endpoint-url $env:AWS_ENDPOINT_URL

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  backend "s3" {
    bucket                      = "hr-rag-tfstate"
    key                         = "terraform.tfstate"
    region                      = "us-east-1"
    dynamodb_table              = "hr-rag-tf-locks"
    encrypt                     = true
    access_key                  = "test"
    secret_key                  = "test"
    endpoint                    = "http://localhost:4566"
    dynamodb_endpoint           = "http://localhost:4566"
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    use_path_style              = true
  }
}

# Every service used below MUST appear here. A missing key hits real AWS.
provider "aws" {
  region                      = var.aws_region
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  s3_use_path_style           = true

  endpoints {
    dynamodb       = "http://localhost:4566"
    ec2            = "http://localhost:4566"
    ecs            = "http://localhost:4566"
    iam            = "http://localhost:4566"
    logs           = "http://localhost:4566"
    s3             = "http://localhost:4566"
    secretsmanager = "http://localhost:4566"
    sts            = "http://localhost:4566"
  }
}

# ─── Variables ───────────────────────────────────────────────────────────────

variable "aws_region" {
  default = "us-east-1"
}

variable "project" {
  default = "hr-rag-assistant"
}

variable "policy_bucket_name" {
  default = "rag-hr-assistant-demo-hr-policies"
}

variable "app_image" {
  description = "Local image tag. Build with: docker build -t hr-rag-assistant:local ."
  default     = "hr-rag-assistant:local"
}

variable "litellm_image" {
  default = "ghcr.io/berriai/litellm:main-latest"
}

variable "app_cpu" {
  default = "512"
}

variable "app_memory" {
  default = "1024"
}

variable "app_port" {
  description = "Streamlit default"
  default     = 8501
}

variable "llm_base_url" {
  description = "Generator OpenAI-compatible URL as seen FROM the LiteLLM container"
  default     = "http://host.docker.internal:8080/v1"
}

variable "fallback_llm_base_url" {
  description = "Judge / fallback URL as seen FROM the LiteLLM container"
  default     = "http://host.docker.internal:8081/v1"
}

variable "qdrant_url" {
  default = "http://host.docker.internal:6333"
}

variable "qdrant_api_key" {
  default   = ""
  sensitive = true
}

variable "langsmith_api_key" {
  default   = ""
  sensitive = true
}

# ─── Data ─────────────────────────────────────────────────────────────────────

data "aws_availability_zones" "available" {}

# ─── Minimal VPC (Fargate awsvpc needs a real subnet on Floci) ────────────────

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${var.project}-vpc" }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.0.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.project}-public" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.project}-igw" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "ecs_tasks" {
  name   = "${var.project}-ecs-tasks"
  vpc_id = aws_vpc.main.id

  ingress {
    description = "Streamlit"
    from_port   = var.app_port
    to_port     = var.app_port
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "LiteLLM sidecar (same-task localhost also works)"
    from_port   = 4000
    to_port     = 4000
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ─── S3 — teacher GCS bucket ─────────────────────────────────────────────────

resource "aws_s3_bucket" "policies" {
  bucket        = var.policy_bucket_name
  force_destroy = true
  tags          = { Name = "${var.project}-policies" }
}

# ─── Secret — teacher streamlit-auth (JWT, not Google OAuth) ─────────────────

resource "random_password" "cookie_secret" {
  length  = 48
  special = false
}

resource "aws_secretsmanager_secret" "app" {
  name = "${var.project}/config"
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    AWS_ENDPOINT_URL       = "http://host.docker.internal:4566"
    AWS_DEFAULT_REGION     = var.aws_region
    AWS_ACCESS_KEY_ID      = "test"
    AWS_SECRET_ACCESS_KEY  = "test"
    AWS_S3_BUCKET          = var.policy_bucket_name
    QDRANT_URL             = var.qdrant_url
    QDRANT_API_KEY         = var.qdrant_api_key
    QDRANT_COLLECTION_NAME = "hr_policies"
    EMBEDDING_PROVIDER     = "fastembed"
    GUARDRAIL_PROVIDER     = "llama_guard"
    AUTH_MODE              = "jwt"
    COOKIE_SECRET          = random_password.cookie_secret.result
    LITELLM_URL            = "http://127.0.0.1:4000"
    LLM_BASE_URL           = var.llm_base_url
    FALLBACK_LLM_BASE_URL  = var.fallback_llm_base_url
    LLM_API_KEY            = "local"
    LANGSMITH_TRACING      = "false"
    LANGSMITH_API_KEY      = var.langsmith_api_key
  })
}

# ─── IAM ──────────────────────────────────────────────────────────────────────

resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.project}-ecs-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_basic" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "${var.project}-execution-secrets"
  role = aws_iam_role.ecs_task_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = aws_secretsmanager_secret.app.arn
    }]
  })
}

resource "aws_iam_role" "ecs_task" {
  name = "${var.project}-ecs-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task_policy" {
  name = "${var.project}-task-policy"
  role = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.app.arn
      },
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.policies.arn,
          "${aws_s3_bucket.policies.arn}/*",
        ]
      }
    ]
  })
}

# ─── Logs ─────────────────────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.project}-app"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_group" "litellm" {
  name              = "/ecs/${var.project}-litellm"
  retention_in_days = 7
}

# ─── ECS — one cluster, one service, two containers in one task ───────────────

resource "aws_ecs_cluster" "main" {
  name = "${var.project}-cluster"
}

resource "aws_ecs_task_definition" "app" {
  family                   = "${var.project}-app"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.app_cpu
  memory                   = var.app_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "app"
      image     = var.app_image
      essential = true
      portMappings = [{
        containerPort = var.app_port
        hostPort      = var.app_port
        protocol      = "tcp"
      }]
      environment = [
        { name = "AWS_ENDPOINT_URL", value = "http://host.docker.internal:4566" },
        { name = "AWS_DEFAULT_REGION", value = var.aws_region },
        { name = "AWS_ACCESS_KEY_ID", value = "test" },
        { name = "AWS_SECRET_ACCESS_KEY", value = "test" },
        { name = "AWS_S3_BUCKET", value = var.policy_bucket_name },
        { name = "LITELLM_URL", value = "http://127.0.0.1:4000" },
        { name = "EMBEDDING_PROVIDER", value = "fastembed" },
        { name = "GUARDRAIL_PROVIDER", value = "llama_guard" },
        { name = "AUTH_MODE", value = "jwt" },
        { name = "QDRANT_URL", value = var.qdrant_url },
      ]
      dependsOn = [{ containerName = "litellm", condition = "START" }]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.app.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "app"
        }
      }
    },
    {
      name      = "litellm"
      image     = var.litellm_image
      essential = true
      portMappings = [{
        containerPort = 4000
        protocol      = "tcp"
      }]
      environment = [
        { name = "OPENAI_API_BASE", value = var.llm_base_url },
        { name = "OPENAI_API_KEY", value = "local" },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.litellm.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "litellm"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "app" {
  name            = "${var.project}-app"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.public.id]
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }
}

# ─── Outputs ──────────────────────────────────────────────────────────────────

output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "service_name" {
  value = aws_ecs_service.app.name
}

output "policy_bucket" {
  value = aws_s3_bucket.policies.bucket
}

output "secret_name" {
  value = aws_secretsmanager_secret.app.name
}

output "app_url_if_ports_published" {
  value = "http://localhost:${var.app_port}"
}
