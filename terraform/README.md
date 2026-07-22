# FundInv Solo — Terraform Infrastructure

Production-ready AWS infrastructure for the FundInv investment platform.
Deploys a **highly-available**, **self-healing** architecture with automated
backups, secrets management, and a full CI/CD pipeline via GitHub Actions.

---

## Architecture Diagram

```
                                Internet
                                   │
                                   ▼
                    ┌──────────────────────────┐
                    │   Application Load        │
                    │   Balancer (ALB)          │
                    │   HTTP :80                │
                    │   us-east-1a + us-east-1b │
                    └────────────┬─────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
     ┌────────▼────────┐  ┌──────▼──────┐  ┌───────▼──────┐
     │  Public Subnet   │  │  Public      │  │  Public      │
     │  AZ-a            │  │  Subnet AZ-b │  │  Subnet ...  │
     └─────────────────┘  └──────────────┘  └──────────────┘
              │                  │
         ┌────▼──────────────────▼────┐
         │       NAT Gateway          │
         │       (AZ-a only)          │
         └────────────┬───────────────┘
                      │
    ┌─────────────────┼───────────────────┐
    │                 │                   │
┌───▼──────────┐  ┌───▼──────────┐       │
│ Private      │  │ Private      │       │
│ Subnet AZ-a  │  │ Subnet AZ-b  │       │
│              │  │              │       │
│ ┌──────────┐ │  │ ┌──────────┐ │       │
│ │ EC2 (ASG)│ │  │ │ EC2      │ │       │
│ │ ┌──────┐ │ │  │ │ (standby)│ │       │
│ │ │nginx │ │ │  │ └──────────┘ │       │
│ │ │ :80  │ │ │  │              │       │
│ │ ├──────┤ │ │  │              │       │
│ │ │/api/*│─┼──┼──► FastAPI    │       │
│ │ │/*    │─┼──┼──► Next.js    │       │
│ │ └──────┘ │ │  │              │       │
│ │ Images   │ │  │              │       │
│ │ pulled   │ │  │              │       │
│ │ from ECR │ │  │              │       │
│ └──────────┘ │  │              │       │
└──────────────┘  └──────────────┘       │
         │                 │              │
         │    ┌────────────┼──────────────┘
         │    │            │
    ┌────▼────▼────────────▼────┐
    │     Database Subnets      │
    │                            │
    │  ┌──────────────────────┐  │
    │  │   RDS PostgreSQL 16  │  │
    │  │   ┌───────┐ ┌──────┐ │  │
    │  │   │Primary│ │Standby│ │  │
    │  │   │AZ-a   │▸│AZ-b  │ │  │
    │  │   └───────┘ └──────┘ │  │
    │  │   Multi-AZ, Encrypted│  │
    │  └──────────────────────┘  │
    └────────────────────────────┘
         │                    │
    ┌────▼────┐    ┌─────▼──────┐    ┌──────────┐
    │ Secrets │    │    S3      │    │   ECR    │
    │ Manager │    │  ┌───────┐ │    │ ┌──────┐ │
    │ ┌─────┐ │    │  │State  │ │    │ │Backnd│ │
    │ │ DB  │ │    │  ├───────┤ │    │ ├──────┤ │
    │ │ App │ │    │  │Backups│ │    │ │Front │ │
    │ └─────┘ │    │  └───────┘ │    │ └──────┘ │
    └─────────┘    └─────────────┘    └──────────┘
```

## CI/CD Pipeline

```
 GitHub Push ──► security-scan ──► backend-build ──► deploy
                    │                  │                 │
                    │ gitleaks         │ docker build     │ ASG rolling
                    │ trivy config     │ trivy scan       │ instance refresh
                    │                  │ push to ECR      │
                    │                  │                  │
                    │              frontend-build         │
                    │                  │                  │
                    │                  │ docker build     │
                    │                  │ trivy scan       │
                    │                  │ push to ECR      │
                    │                  │                  │
                    └──────────────────┴──────────────────┘
```

### Pipeline Stages

| Stage | Tool | What it does |
|-------|------|--------------|
| **Secret scanning** | Gitleaks | Scans repo for hardcoded API keys, tokens, passwords |
| **Config scanning** | Trivy | Scans Dockerfiles, terraform for misconfigurations |
| **Backend build** | Docker | Builds Python/FastAPI image from `Dockerfile.backend` |
| **Backend scan** | Trivy | Vulnerability scan on built image (HIGH + CRITICAL) |
| **Frontend build** | Docker | Builds Next.js image from `Dockerfile.frontend` |
| **Frontend scan** | Trivy | Vulnerability scan on built image (HIGH + CRITICAL) |
| **Deploy** | AWS CLI | Triggers ASG rolling instance refresh → pulls new images |

### Required GitHub Secrets

Set these in **Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | IAM user access key with ECR push + ASG permissions |
| `AWS_SECRET_ACCESS_KEY` | Corresponding secret key |
| `AWS_ACCOUNT_ID` | Your 12-digit AWS account ID |

---

## Network Architecture

```
VPC: 10.0.0.0/16
├── Public Subnets (ALB + NAT)
│   ├── 10.0.0.0/24   — AZ-a
│   └── 10.0.1.0/24   — AZ-b
├── Private Subnets (EC2)
│   ├── 10.0.10.0/24  — AZ-a
│   └── 10.0.11.0/24  — AZ-b
└── Database Subnets (RDS)
    ├── 10.0.20.0/24  — AZ-a
    └── 10.0.21.0/24  — AZ-b
```

### Routing

| Subnet Tier | Route to Internet | How |
|-------------|-------------------|-----|
| Public | ✅ Direct | Internet Gateway |
| Private | ✅ Via NAT | NAT Gateway → IGW |
| Database | ✅ Via NAT (egress only) | NAT Gateway → IGW |

**No inbound internet** to EC2 or RDS. The ALB is the only internet-facing component.

---

## Components

### Compute — EC2 Auto Scaling Group

| Setting | Value | Reason |
|---------|-------|--------|
| AMI | Amazon Linux 2023 | Lightweight, fast boot, `dnf` package manager |
| Instance type | `t3.medium` | 2 vCPU, 4 GB — enough for FastAPI + Next.js + nginx |
| Min/Max/Desired | 1 / 2 / 1 | Cost-efficient; scales to 2 under load or on AZ failure |
| Root volume | 30 GB gp3, encrypted | Application + Docker images + logs |
| Health check | ELB `/api/test` | Replaces instance if backend fails |

Each instance runs **three Docker containers** (images pulled from ECR at boot):

| Container | Source | Port | Purpose |
|-----------|--------|------|---------|
| `nginx` | Docker Hub (nginx:alpine) | **80** (host) | Reverse proxy: `/api/*` → backend, `/*` → frontend |
| `fundinv-backend` | ECR (built by CI) | 8000 (localhost) | FastAPI API server |
| `fundinv-frontend` | ECR (built by CI) | 3000 (localhost) | Next.js 16 frontend |

### Database — RDS PostgreSQL 16

| Setting | Value |
|---------|-------|
| Instance | `db.t3.small` |
| Multi-AZ | ✅ — synchronous standby in AZ-b |
| Storage | 20 GB gp3, auto-scale to 100 GB |
| Encryption | AES-256 at rest |
| Backups | 7-day retention, daily automated snapshots |
| Max connections | 100 |
| Extended library | `pg_stat_statements` |

### Container Registry — ECR

| Repository | Image mutability | Scanning |
|------------|-----------------|----------|
| `fundinv-backend-{env}` | Immutable | Scan on push |
| `fundinv-frontend-{env}` | Immutable | Scan on push |

Lifecycle policy: **retain last 5 images**, expire older ones automatically.

### Load Balancer — ALB

| Setting | Value |
|---------|-------|
| Type | Application, internet-facing |
| Protocol | HTTP :80 |
| AZs | Both public subnets |
| Target group | EC2 instances, port 80 |
| Health check | `GET /api/test` every 30s |

### Secrets — AWS Secrets Manager

| Secret | Contents |
|--------|----------|
| `fundinv/db-{env}` | `host`, `port`, `dbname`, `username`, `password`, `url` |
| `fundinv/app-{env}` | `SECRET_KEY`, Stripe keys, Alpaca keys, SMTP credentials |

EC2 instances fetch secrets at boot. Recovery window: **7 days** for prod, **0** for dev.

### Storage — S3

| Bucket | Purpose | Lifecycle |
|--------|---------|-----------|
| `fundinv-terraform-state-{env}` | Terraform remote state | Versioned, never expires |
| `fundinv-backups-{env}` | Nightly `pg_dump` backups | IA after 30d, delete after 90d |

---

## Reliability & Redundancy

### Failure Scenarios

| Scenario | Impact | Recovery |
|----------|--------|----------|
| **EC2 instance fails** | ALB health check fails → ASG replaces instance | ~2-3 min (boot + secret fetch + ECR pull) |
| **AZ-a outage** | EC2 in AZ-a lost; RDS primary lost | ASG launches in AZ-b; RDS fails over to standby in AZ-b (~60s) |
| **RDS primary fails** | DB unavailable momentarily | Automatic Multi-AZ failover to standby (~60-120s) |
| **ALB node fails** | Traffic routed to healthy ALB node | AWS auto-heals ALB nodes |
| **NAT Gateway fails** | EC2 loses outbound internet (Alpaca, Stripe, SMTP) | Single NAT is a SPOF; add second NAT in AZ-b for production |
| **Application bug** | Instance unhealthy → ASG replaces | Rollback by reverting commit → CI rebuilds → redeploy |

---

## Deployment

### Prerequisites

1. **AWS CLI** configured (`aws configure`)
2. **Terraform** >= 1.5.0 installed
3. **SSH key pair** created in your AWS region
4. **GitHub repo** with Actions enabled and secrets configured
5. Valid **Stripe**, **Alpaca**, and **SMTP** credentials (or leave blank)

### Manual Image Build (first time, before CI)

```bash
# Backend
docker build -f terraform/templates/Dockerfile.backend \
  -t fundinv-backend-dev:latest .

# Frontend
docker build -f terraform/templates/Dockerfile.frontend \
  -t fundinv-frontend-dev:latest .

# Login to ECR (after terraform creates the repos)
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Tag and push
export ECR=<account-id>.dkr.ecr.us-east-1.amazonaws.com
docker tag fundinv-backend-dev:latest  $ECR/fundinv-backend-dev:latest
docker tag fundinv-frontend-dev:latest $ECR/fundinv-frontend-dev:latest
docker push $ECR/fundinv-backend-dev:latest
docker push $ECR/fundinv-frontend-dev:latest
```

### Terraform Setup

```bash
cd terraform

# 1. Copy backend config
cp backend.conf.example backend.conf
# Edit with your bucket name if needed

# 2. Initialize
terraform init -backend-config=backend.conf

# 3. Copy and edit variables
cp terraform.tfvars.example terraform.tfvars

# 4. Plan
terraform plan

# 5. Apply
terraform apply
```

### Post-Deploy Setup

```bash
# Run DB schema init (one-time)
aws ssm start-session --target <instance-id> --document-name AWS-StartInteractiveCommand \
  --parameters '{"command":["sudo", "PGPASSWORD=...", "psql", "-h", "<rds-host>", "-U", "fundinv_admin", "-d", "fundinv", "-f", "/path/to/init_schema.sql"]}'

# Seed data
# Same as above, pointing to v0.0.1_seed_data.sql
```

> If `AUTO_MIGRATE=true` is set (default), the backend runs Alembic migrations on startup automatically.

---

## File Structure

```
terra form/
├── main.tf                  # Provider config, data sources (no hardcoded backend)
├── backend.conf.example     # Template for -backend-config init
├── variables.tf             # All input variables with types/descriptions
├── outputs.tf               # ALB DNS, RDS endpoint, ECR URLs, secret ARNs
├── vpc.tf                   # VPC, 6 subnets, NAT, IGW, route tables
├── security-groups.tf       # ALB SG, EC2 SG, RDS SG
├── iam.tf                   # EC2 role, instance profile, Secrets/S3/ECR policies
├── secrets-manager.tf       # DB secrets + app secrets
├── rds.tf                   # RDS PostgreSQL 16, Multi-AZ
├── s3.tf                    # State bucket + backups bucket
├── ecr.tf                   # ECR repos + lifecycle policy
├── ec2.tf                   # Launch template, ASG, ALB, target group, listener
├── terraform.tfvars.example # Example variable values
├── templates/
│   ├── user-data.sh.tmpl    # EC2 bootstrap (ECR pull, nginx, cron backup)
│   ├── Dockerfile.backend   # Production FastAPI image
│   └── Dockerfile.frontend  # Production Next.js image
└── README.md                # This file

.github/
├── workflows/
│   └── deploy.yml           # CI/CD: lint → build → scan → push → deploy
└── .gitleaks.toml           # Secret scanning allowlist
```

---

## Resource Summary

| Service | Resources | Count |
|---------|-----------|-------|
| **VPC** | VPC, IGW, NAT GW, EIP, 6 subnets, 3 route tables, 6 associations, DB subnet group | 19 |
| **EC2** | Launch template, ASG | 2 |
| **ALB** | ALB, target group, listener | 3 |
| **RDS** | DB instance, parameter group | 2 |
| **ECR** | 2 repos, 2 lifecycle policies | 4 |
| **S3** | 2 buckets, versioning ×2, encryption ×2, public access block ×2, lifecycle | 9 |
| **Secrets** | 2 secrets, 2 versions, random password | 5 |
| **IAM** | Role, 3 custom policies, 4 attachments, instance profile, DynamoDB table | 10 |
| **Total** | | **~54 resources** |

---

## Cost Estimate (us-east-1, monthly)

| Resource | Spec | Est. Cost |
|----------|------|-----------|
| EC2 (t3.medium) | 1 instance, 24/7 | ~$30 |
| RDS (db.t3.small, Multi-AZ) | 2 instances, 20 GB | ~$70 |
| ALB | 1 ALB + LCU | ~$20 |
| NAT Gateway | 1 NAT + data | ~$35 |
| ECR | 2 repos, <1 GB storage | ~$1 |
| S3 | <1 GB storage | ~$1 |
| Secrets Manager | 2 secrets | ~$1 |
| DynamoDB | On-demand | ~$0 |
| **Total** | | **~$158/mo** |

> **Cost-saving tips**: Use `db.t3.micro` + single-AZ for dev (~$15/mo for RDS). Remove NAT Gateway and use VPC endpoints for dev (~-$35/mo). Set ASG min=0 for off-hours.

---

## Security Notes

- **Secret scanning** (Gitleaks) runs on every push to catch accidental credential leaks
- **Image scanning** (Trivy) runs on every build — HIGH/CRITICAL CVEs are flagged
- **ECR images** are immutable (tags cannot be overwritten)
- **SSH (port 22)** is open to `0.0.0.0/0` — restrict to your IP or use **SSM Session Manager** for production
- **ALB is HTTP-only** (no SSL). Add an **ACM certificate** and HTTPS listener after you set up a domain
- **Secrets are encrypted** at rest in Secrets Manager and fetched only at boot time
- **RDS** is encrypted, in private subnets, accessible only from EC2
- **S3 buckets** block all public access, enforce encryption, and are versioned
- **IMDSv2** is required (`http_tokens = "required"`) to prevent SSRF
