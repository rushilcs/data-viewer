# Deploy to AWS ECS (Fargate)

Production-style deployment using Terraform (IaC) and GitHub Actions. Local development is unchanged (uvicorn + docker-compose Postgres).

## Prerequisites

- **AWS account** and credentials (for Terraform and CI/CD).
- **Terraform** >= 1.5 (and `terraform` on PATH).
- **Domain and TLS**: a domain (e.g. `api.staging.example.com`) and an **ACM certificate** in the same region as the deployment. Request the cert in ACM (e.g. DNS validation), then use its ARN in Terraform.
- **GitHub repo** with Actions enabled; you will add secrets for AWS and optional base URLs for smoke tests.

## 1. Apply Terraform

### Backend (state)

Use local state for a first run, or configure S3 backend:

```bash
cd infra/terraform
terraform init
# Optional: terraform init -backend-config=backend.hcl
```

Example `backend.hcl`:

```hcl
bucket         = "your-tf-state-bucket"
key            = "data-viewer/staging/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "terraform-lock"  # optional, for locking
```

### Variables

Copy the example and set required variables (no secrets in this file):

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: environment, domain_name, acm_certificate_arn, s3_bucket_name, etc.
```

Required:

- `environment` — e.g. `staging` or `prod`
- `domain_name` — hostname for the API (e.g. `api.staging.example.com`)
- `acm_certificate_arn` — ARN of ACM certificate covering `domain_name`
- `s3_bucket_name` — globally unique S3 bucket name for assets

### Plan and apply

```bash
terraform plan -out=tfplan
terraform apply tfplan
```

Note outputs: `ecr_repository_url`, `rds_endpoint`, `app_secret_arn`, `alb_dns_name`, `s3_bucket_name`, etc.

## 2. Set secrets

Terraform creates a Secrets Manager secret with placeholder values. Replace them with real values (no secrets in Terraform state).

### Option A: AWS Console

1. Open **Secrets Manager** → secret named `data-viewer-<env>/app`.
2. **Retrieve secret value** → **Edit**.
3. Set JSON, e.g.:

```json
{
  "DATABASE_URL": "postgresql+asyncpg://viewer:YOUR_RDS_PASSWORD@RDS_ENDPOINT:5432/viewer?sslmode=require",
  "secret_key": "your-long-random-jwt-secret"
}
```

Use the RDS endpoint and password from Terraform (password is in state if you used `random_password`; otherwise set it manually and store in the secret). Build `DATABASE_URL` as:

`postgresql+asyncpg://viewer:PASSWORD@RDS_ENDPOINT:5432/viewer?sslmode=require`

### Option B: AWS CLI

```bash
aws secretsmanager put-secret-value \
  --secret-id "data-viewer-staging/app" \
  --secret-string '{"DATABASE_URL":"postgresql+asyncpg://viewer:PASSWORD@xxx.rds.amazonaws.com:5432/viewer?sslmode=require","secret_key":"your-jwt-secret"}'
```

Never commit secrets. Terraform uses `lifecycle { ignore_changes = [secret_string] }` so it will not overwrite the value you set.

## 3. DNS

Point your domain to the ALB:

- **CNAME**: `api.staging.example.com` → value of Terraform output `alb_dns_name`.
- Or create a Route 53 alias (A record) to the ALB using `alb_dns_name` and `alb_zone_id`.

## 4. Deploy staging (GitHub Actions)

### Repo secrets

In GitHub: **Settings → Secrets and variables → Actions**, add:

- `AWS_ACCESS_KEY_ID` — IAM user with permissions to ECR, ECS, and (for migrations) same VPC/security as ECS tasks.
- `AWS_SECRET_ACCESS_KEY`
- Optional: `STAGING_BASE_URL` — e.g. `https://api.staging.example.com` for the smoke test (otherwise smoke step is skipped).

### Staging deploy trigger

- **Push to `main`** runs the **Deploy Staging** workflow:
  1. Build backend Docker image and push to ECR.
  2. Update ECS service (force new deployment).
  3. Run migrations as a one-off ECS task (`alembic upgrade head`).
  4. Smoke test `/healthz` if `STAGING_BASE_URL` is set.

Ensure ECR repository name and ECS cluster/service names in the workflow match your Terraform outputs (e.g. `data-viewer-staging`, cluster `data-viewer-staging`, service `data-viewer-staging`). Adjust `.github/workflows/deploy-staging.yml` env if you use different names.

## 5. Deploy production (tag)

- **Tag** `v*` (e.g. `v1.0.0`) runs the **Deploy Production** workflow (build → push ECR → update ECS → migrations → smoke).
- Add `PROD_BASE_URL` secret if you want production smoke tests.

## 6. Run migrations manually

If you need to run migrations without a full deploy:

```bash
# Get task definition, subnets, and security groups from ECS service
aws ecs run-task \
  --cluster data-viewer-staging \
  --task-definition data-viewer-staging \
  --launch-type FARGate \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=DISABLED}" \
  --overrides '{"containerOverrides":[{"name":"backend","command":["alembic","upgrade","head"]}]}'
```

Then check the task exit code in the ECS console.

## 7. Health and readiness

- **`/healthz`** — liveness (no auth, no DB). Used by ALB target group health checks.
- **`/readyz`** — readiness (light DB check). Returns 503 if DB is unreachable.
- **`/health`** — legacy endpoint; same as `/healthz` for compatibility.

## Summary

| Item | Description |
|------|-------------|
| **Local dev** | Unchanged: `make run`, `make up`, no Docker image required. |
| **Terraform** | VPC, ALB, ECS Fargate, RDS, S3, Secrets Manager placeholder, CloudWatch logs. |
| **Secrets** | Set real values in Secrets Manager after apply; no secrets in Terraform state. |
| **CI/CD** | Staging on push to `main`; prod on tag `v*`. Build → ECR → ECS update → migrations → optional smoke. |
