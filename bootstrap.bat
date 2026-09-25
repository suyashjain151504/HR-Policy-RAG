@echo off
setlocal

REM Bootstrap Terraform remote state ON FLOCI (fake AWS), not real Amazon.
REM Requires: Docker Desktop running + Floci container on port 4566.
REM   docker compose up -d floci

set REGION=us-east-1
set BUCKET=hr-rag-tfstate
set TABLE=hr-rag-tf-locks
set ENDPOINT=http://localhost:4566

set AWS_ENDPOINT_URL=%ENDPOINT%
set AWS_DEFAULT_REGION=%REGION%
set AWS_ACCESS_KEY_ID=test
set AWS_SECRET_ACCESS_KEY=test

echo Using Floci endpoint: %ENDPOINT%
echo Creating S3 bucket: %BUCKET% in region: %REGION%

aws s3api create-bucket --bucket %BUCKET% --region %REGION% --endpoint-url %ENDPOINT%
if %errorlevel% equ 0 (
    echo Bucket created.
) else (
    echo Bucket create returned an error — if it already exists, continuing.
)

echo Enabling versioning...
aws s3api put-bucket-versioning --bucket %BUCKET% --versioning-configuration Status=Enabled --endpoint-url %ENDPOINT%

echo Blocking public access...
aws s3api put-public-access-block --bucket %BUCKET% --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true --endpoint-url %ENDPOINT%

echo Enabling server-side encryption...
aws s3api put-bucket-encryption --bucket %BUCKET% --server-side-encryption-configuration "{\"Rules\":[{\"ApplyServerSideEncryptionByDefault\":{\"SSEAlgorithm\":\"AES256\"}}]}" --endpoint-url %ENDPOINT%

echo Creating DynamoDB table for state locking: %TABLE%
aws dynamodb create-table --table-name %TABLE% --attribute-definitions AttributeName=LockID,AttributeType=S --key-schema AttributeName=LockID,KeyType=HASH --billing-mode PAY_PER_REQUEST --region %REGION% --endpoint-url %ENDPOINT%
if %errorlevel% equ 0 (
    echo DynamoDB table created.
) else (
    echo DynamoDB create returned an error — if it already exists, continuing.
)

echo.
echo Bootstrap complete (Floci / localhost).
echo   S3 bucket  : %BUCKET%
echo   DynamoDB   : %TABLE%
echo   Endpoint   : %ENDPOINT%
echo.
echo Next: cd terraform
echo       terraform init
echo       terraform apply
echo.
echo If a command hit real AWS, you forgot --endpoint-url.

endlocal
