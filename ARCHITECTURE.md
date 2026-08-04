# FundInv AWS Architecture

## Overview

The application runs on EC2 instances in an Auto Scaling Group behind an Application Load Balancer, with PostgreSQL on RDS. All resources live in a dedicated VPC. When a custom domain is configured, CloudFront, ACM, Route53, and WAF are layered on top for CDN caching, TLS termination, and DDoS protection.

```
Internet ──► ALB (public subnets) ──► EC2 ASG (private subnets) ──► RDS (database subnets)
                  │                         │
                  └── S3 (ALB logs)         ├── Secrets Manager (DB creds, app secrets)
                                            ├── ECR (container images)
                                            ├── S3 (backups, app assets)
                                            └── Lambda (daily pg_dump) ──► S3 (backups)

[When domain is set]
Internet ──► CloudFront ──► WAF ──► ALB ──► ...
                  │
                  └── ACM (TLS cert) ──► Route53 (DNS)


[Backup flow]
CloudWatch Events (2AM UTC) ──► Lambda (VPC, private subnet) ──► RDS (pg_dump) ──► S3 (gzip)
                                   │
                                   └── Secrets Manager (DB creds)
```

## VPC (10.0.0.0/16)

6 subnets across 2 Availability Zones:

| Tier     | Subnets | CIDR offset | Purpose                          |
|----------|---------|-------------|----------------------------------|
| Public   | 2       | +0, +1      | ALB, NAT Gateways                |
| Private  | 2       | +10, +11    | EC2 instances (Auto Scaling)     |
| Database | 2       | +20, +21    | RDS PostgreSQL (Multi-AZ)        |

- Internet Gateway on public subnets, NAT Gateways (one per AZ) for private subnet egress
- VPC Endpoints (Interface) for Secrets Manager, ECR API, ECR DKR, SSM — keeps AWS API traffic inside the backbone
- VPC Endpoint (Gateway) for S3
- VPC Flow Logs to CloudWatch

## Compute

**EC2 Auto Scaling Group** (1–2 × t3.medium, Amazon Linux 2023):
- Launch Template with gp3 encrypted EBS root volume, IMDSv2 enforced
- IAM instance profile with access to: Secrets Manager, ECR, S3, CloudWatch Logs, SSM Session Manager
- CPU target tracking scaling at 70%

**Application Load Balancer** (internet-facing):
- HTTP listener on port 80 — forwards to target group in dev mode; blocks direct access when CloudFront is configured (requires `X-Origin-Verify` header)
- HTTPS listener on port 443 (only when domain is set)
- Health check: `GET /api/test` every 30s
- Access logs written to S3

## Database

**RDS PostgreSQL 16.4** (db.t3.small, Multi-AZ):
- 20 GB gp3 encrypted storage, auto-scales to 100 GB
- 7-day automated snapshots (AWS-managed, window 03:00–04:00 UTC)
- Final snapshot on deletion only when `deletion_protection` is enabled
- Custom parameter group (`postgres16` family)

**RDS Proxy** (optional, `enable_rds_proxy` flag): connection pooling, TLS termination, faster failover

## Backups

Two complementary mechanisms:

**1. RDS automated snapshots** — AWS-managed, 7-day retention, point-in-time recovery within the retention window. Good for disaster recovery within AWS.

**2. Lambda daily pg_dump** — portable SQL dump uploaded to S3:
- CloudWatch Events triggers a Lambda at 2 AM UTC every day (`cron(0 2 * * ? *)`)
- Lambda runs in private subnets, reaches RDS directly over the VPC
- Reads DB credentials from Secrets Manager
- Executes `pg_dump --no-owner --no-acl`, pipes through `gzip`, uploads to S3
- Stored at `s3://fundinv-backups-dev/backups/YYYY-MM-DD/HHMM/fundinv.sql.gz`
- S3 lifecycle: transitions to Infrequent Access after 30 days, expires after 90
- pg_dump binary is bundled as a Lambda layer (see `bin/build-pg-layer.sh`)

**Restoring from a pg_dump backup:**
```bash
aws s3 cp s3://fundinv-backups-dev/backups/2026-01-01/0200/fundinv.sql.gz - | gunzip | \
  psql -h <rds-endpoint> -U yeaw_min -d fundinv
```

## Storage

| Bucket                     | Purpose                        | Lifecycle                          |
|----------------------------|--------------------------------|------------------------------------|
| `fundinv-backups-dev`      | pg_dump exports + Lambda layer zip | IA after 30d, expire after 90d     |
| `fundinv-assets-dev`       | Generated PDFs, user uploads   | IA after 90d, old versions 30d     |
| `fundinv-alb-logs-dev-*`   | ALB access logs                | Expire after 30d                   |

All buckets: SSE-AES256 encryption, versioning enabled, public access blocked.

**ECR** — two repositories (`fundinv-backend-dev`, `fundinv-frontend-dev`):
- Immutable tags, scan on push
- Lifecycle: keep last 5 images

## Secrets

**AWS Secrets Manager** — two secrets:
- `fundinv/db-dev` — RDS host, port, database name, username, password, full connection URL
- `fundinv/app-dev` — JWT signing key, Stripe keys, Alpaca API keys, SMTP credentials, feature flags

## Security

**Security Groups:**
- `alb-sg`: ingress from CloudFront managed prefix list (or `0.0.0.0/0` in dev mode) on ports 80/443; egress all
- `ec2-sg`: ingress from ALB on port 80; egress all
- `rds-sg`: ingress from EC2 on port 5432; default egress
- `vpce-sg`: ingress HTTPS from EC2

**WAF** (CloudFront-scoped, always us-east-1 regardless of `aws_region`, only when domain is set):
- AWS Managed Rules: CommonRuleSet, KnownBadInputs, IP Reputation
- Rate limit: 2000 requests per 5 minutes per IP
- Logs to CloudWatch

## Domain & CDN (only when `domain_name` is set)

- **ACM**: two certificates (us-east-1 for CloudFront per AWS requirement, regional for ALB), DNS-validated via Route53
- **CloudFront**: forwards all headers/cookies/query strings; `/api/*` disables caching; `/_next/static/*` uses managed caching policy; custom origin verify header prevents ALB bypass
- **Route53**: hosted zone with A/AAAA apex and `www` records pointing to CloudFront

## Monitoring

- CloudWatch Log Groups: application logs, VPC flow logs, WAF logs (30-day retention)
- SNS topic with email subscription for alarms
- Alarms: ALB 5XX, ALB response time (>5s), EC2 CPU (>80%), RDS CPU (>80%), RDS free storage (<20%), RDS connections (>80)
- CloudWatch Dashboard: ALB requests/errors, EC2 CPU, RDS CPU/connections/storage, CloudFront metrics (when domain is set)

## Variable Summary

| Variable               | Default        | Description                              |
|------------------------|----------------|------------------------------------------|
| `aws_region`           | `ap-southeast-1` | AWS region for all resources             |
| `environment`          | `dev`          | Environment name                         |
| `project_name`         | `fundinv`      | Prefix for all resource names            |
| `domain_name`          | `""`           | Custom domain (empty = dev mode)         |
| `ec2_instance_type`    | `t3.medium`    | EC2 instance size                        |
| `db_instance_class`    | `db.t3.small`  | RDS instance size                        |
| `enable_rds_proxy`     | `false`        | Enable RDS Proxy for connection pooling  |
| `enable_waf`           | `true`         | Enable WAF (requires domain)             |
| `deletion_protection`  | `false`        | Protect RDS from accidental deletion     |

## Terraform State

State is stored in S3 (`fundinv-terraform-state-dev`) with S3 native lock file. See `backend.conf`.
