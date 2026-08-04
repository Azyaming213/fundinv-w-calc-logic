# FundInv AWS Cloud Architecture Handoff

## Purpose

This document is intended for an experienced AWS/cloud engineer reviewing how
FundInv should be deployed. Please assess the existing infrastructure, choose
an appropriate production architecture, and identify changes required before a
client-facing deployment.

No credentials or secret values are included in this document.

## Application summary

FundInv is a role-based investment fund management portal with four user roles:

- Investor
- Fund Manager
- Operations
- Administrator

The main application components are:

| Component | Technology | Purpose |
|---|---|---|
| Frontend | Next.js 16, React 19 | Role-based client portal |
| Backend | FastAPI, Python 3.12 | Authentication, funds, payments, accounting and reporting APIs |
| Database | PostgreSQL 16 | Users, funds, positions, units, fund flows, valuations and audit records |
| Scheduler | APScheduler in `Server/scheduler_worker.py` | Reconciliation, reporting, snapshots and maintenance jobs |
| Container images | Docker | Separate frontend and backend images |
| Infrastructure | Terraform | Existing EC2, ALB, RDS, ECR, S3, IAM and Secrets Manager definitions |

External integrations are:

- Stripe test-mode payments and signed webhooks
- Alpaca paper-trading and market-data APIs
- SMTP email
- Demo PayNow fixed-amount QR workflow for demonstrations

The application generates portfolio PDFs dynamically. The authoritative
financial/accounting data is stored in PostgreSQL.

## Current application status

The Windows/local version is working and has been tested with:

- 26 backend tests
- Next.js production build
- Frontend lint
- Cross-role Playwright browser tests
- Manager fund creation using Alpaca asset search
- Operations fund approval
- Automatic investor visibility after approval
- Investor subscription and fixed-amount demo PayNow flow

The current source is on the GitHub `main` branch.

## Existing AWS implementation

The repository currently contains an EC2-based Terraform design:

```text
Internet
   |
Application Load Balancer
   |
EC2 Auto Scaling Group in private subnets
   |-- Nginx
   |-- Next.js container
   |-- FastAPI container
   |
RDS PostgreSQL in database subnets
```

Existing Terraform resources include:

- VPC across two Availability Zones
- Public, private application and database subnets
- Internet Gateway and one NAT Gateway
- Application Load Balancer
- EC2 launch template and Auto Scaling Group
- RDS PostgreSQL 16, Multi-AZ and encrypted storage
- ECR frontend and backend repositories
- Secrets Manager secrets
- S3 Terraform-state and database-backup buckets
- IAM instance role and policies
- Security groups

Important files:

- `terraform/README.md`
- `terraform/ec2.tf`
- `terraform/rds.tf`
- `terraform/vpc.tf`
- `terraform/security-groups.tf`
- `terraform/secrets-manager.tf`
- `terraform/templates/user-data.sh.tmpl`
- `.github/workflows/deploy.yml`

## Architecture decision required

Please recommend one of these approaches:

### Option A: Retain EC2 Auto Scaling

Continue using the existing Terraform structure and run the containers on EC2.
This requires less Terraform rewriting but leaves responsibility for OS,
Docker, bootstrap and instance lifecycle management with the project team.

### Option B: Move compute to ECS Fargate

Run three separate ECS services/tasks:

1. Next.js frontend service
2. FastAPI backend service
3. Singleton scheduler worker with desired count exactly `1`

The preferred preliminary option is ECS Fargate because the application is
already containerized, but the cloud engineer should decide based on cost,
expected traffic, operational skill and project requirements.

Please specifically advise whether the added complexity and monthly cost of
ECS is justified for this client/capstone deployment.

## Non-negotiable application requirements

The final architecture must preserve these properties:

1. Frontend and API must be presented under one HTTPS origin, preferably:

   ```text
   https://fundinv.example.com/       -> Next.js
   https://fundinv.example.com/api/*  -> FastAPI
   ```

   Authentication uses an HTTP-only cookie. Incorrect host, HTTPS, CORS or
   cookie settings will break authenticated requests.

2. Production configuration must include:

   ```env
   ENVIRONMENT=production
   COOKIE_SECURE=true
   FRONTEND_URL=https://fundinv.example.com
   CORS_ORIGINS=https://fundinv.example.com
   ENABLE_SCHEDULER=false
   ENABLE_AUTOMATED_TRADING=false
   ```

3. The scheduler must run in exactly one dedicated process. It must not run in
   every API replica.

4. PostgreSQL must not be publicly accessible.

5. Application containers must be stateless. Persistent financial data belongs
   in PostgreSQL, not on EC2/ECS local storage.

6. Alembic migrations should run once as a controlled deployment step, not
   concurrently in every web replica.

7. Stripe webhook requests must reach the FastAPI service over public HTTPS.

8. FastAPI and the scheduler require outbound HTTPS access to Stripe, Alpaca
   and SMTP services.

9. All application secrets must come from Secrets Manager or another approved
   secret store. They must never be baked into images or committed to GitHub.

## Proposed starting autoscaling values

These are starting assumptions, not final capacity figures. Please validate
them with load testing and expected user numbers.

### If ECS Fargate is selected

| Service | Minimum | Desired | Maximum | Initial scaling signals |
|---|---:|---:|---:|---|
| Next.js | 2 | 2 | 6 | CPU 60%, memory 70%, ALB request count |
| FastAPI | 2 | 2 | 10 | CPU 60%, memory 70%, request count and p95 latency |
| Scheduler | 1 | 1 | 1 | Never autoscale |

Suggested behavior:

- Scale out after approximately three minutes over a threshold.
- Use a short scale-out cooldown of about 60 seconds.
- Scale in only after 10–15 minutes of stable low use.
- Use a longer scale-in cooldown of about 300 seconds.
- Never reduce production frontend or API services below two healthy tasks.

### If EC2 Auto Scaling is retained

The current Terraform values are `min=1`, `desired=1`, `max=2`, but no scaling
policy is defined. Please determine whether production should instead begin at:

```text
minimum = 2
desired = 2
maximum = 4 or 6
```

Please add target-tracking or step-scaling policies based on ALB request count,
CPU, memory and response latency.

## Database capacity questions

The existing Terraform uses RDS PostgreSQL 16 with Multi-AZ, encrypted gp3
storage, 20 GB initial storage and autoscaling to 100 GB.

Please advise on:

- Appropriate initial RDS instance class in `ap-southeast-1`
- Whether Multi-AZ is required for the demonstration or only production
- Whether RDS Proxy is needed when compute scales horizontally
- Connection-pool limits for FastAPI replicas and the scheduler
- Backup retention period
- Point-in-time recovery requirements
- Cross-region snapshot-copy requirements
- A tested database restore procedure
- Whether custom nightly `pg_dump` backups to S3 are necessary in addition to
  RDS automated backups

## Contingency and disaster-recovery requirements

Please validate or replace these preliminary targets:

| Failure | Proposed response | Preliminary target |
|---|---|---|
| Container or instance failure | ALB removes unhealthy target; ECS/ASG replaces it | RTO 1–5 minutes, RPO 0 |
| Availability Zone failure | Run compute in two AZs; RDS Multi-AZ failover | RTO under 5 minutes |
| Failed deployment | Automatic rollback to prior task definition/image | RTO under 10 minutes |
| Database instance failure | RDS automatic failover | RTO approximately 1–3 minutes |
| Data corruption/operator error | RDS point-in-time restore into a new instance | RPO around 5 minutes |
| Stripe or Alpaca outage | Retain pending state, retry idempotently and alert | No duplicate accounting |
| Scheduler failure | Restart singleton worker; idempotent jobs resume | Next retry/schedule cycle |
| Region failure | Rebuild using Terraform and secondary-region backups | RTO 1–4 hours |

Questions for the cloud engineer:

- Is one NAT Gateway acceptable for this project, or is one per AZ required?
- What RTO and RPO are realistic for the available budget?
- Should cross-region recovery be implemented or documented only?
- How often should restore drills be performed?
- Which CloudWatch alarms should page someone immediately?
- Should Stripe webhook processing be decoupled through SQS?
- Are additional rate limiting, WAF or DDoS protections required?

## Existing CI/CD pipeline

The repository has `.github/workflows/deploy.yml`. It currently:

- Runs Gitleaks
- Runs Trivy configuration scanning
- Builds frontend and backend images
- Scans images
- Pushes images to ECR
- Starts an EC2 Auto Scaling Group instance refresh

It is a scaffold and should not be treated as production-ready.

## Known CI/CD issues to resolve

1. Gitleaks uses `continue-on-error: true`, so detected secrets do not block the
   pipeline.
2. Trivy uses `exit-code: 0`, so high and critical findings do not block it.
3. Backend tests are not executed.
4. Frontend lint, production build verification and Playwright tests are not
   deployment gates.
5. AWS authentication uses permanent access keys instead of GitHub OIDC.
6. Images are pushed using `latest`, but the ECR repositories are immutable.
   A second push of the same tag can fail.
7. The deploy command uses `MinHealthyPercentage: 0`, which permits complete
   application downtime during an instance refresh.
8. There is no automatic rollback based on ALB or CloudWatch alarms.
9. The workflow deploys an ASG named `fundinv-asg-dev` from a GitHub environment
   named `production`.
10. Terraform changes are path-ignored instead of being planned and reviewed.
11. Alembic migration execution is not separated from application startup.

## Desired CI/CD design

### Pull requests

The pull-request workflow should block merging unless all required checks pass:

1. Secret scanning
2. Backend tests
3. Frontend lint
4. Next.js production build
5. Playwright tests
6. Dependency and container vulnerability scanning
7. Terraform formatting, validation and security scanning
8. Terraform plan for infrastructure changes

### Merge to `main`

The deployment workflow should:

1. Authenticate to AWS using GitHub OIDC.
2. Build each image once.
3. Tag each image with the Git commit SHA or image digest.
4. Scan and push immutable images to ECR.
5. Deploy to a staging environment.
6. Run Alembic as one controlled task.
7. Run staging smoke tests.
8. Require approval for the GitHub production environment.
9. Deploy using a safe rolling, canary or blue/green strategy.
10. Monitor ALB health, HTTP 5xx rate and latency.
11. Automatically roll back if health checks or alarms fail.
12. Run post-deployment smoke tests.

## Monitoring requirements

Please define CloudWatch dashboards, alarms and retention for at least:

- ALB HTTP 4xx and 5xx counts
- ALB target response time and unhealthy-host count
- FastAPI CPU, memory, restarts and request latency
- Next.js CPU, memory and restarts
- Scheduler heartbeat and failed jobs
- RDS CPU, storage, connections, latency and failovers
- NAT Gateway errors
- Stripe webhook failures
- Alpaca API failures and reconciliation discrepancies
- Application authentication failures and suspicious activity

Financial audit records must remain in PostgreSQL even if operational logs are
expired from CloudWatch.

## Security review questions

Please review:

- ACM HTTPS and HTTP-to-HTTPS redirection
- Route 53 configuration
- WAF requirements
- Security-group least privilege
- IAM task/instance-role least privilege
- Replacement of `CloudWatchLogsFullAccess` with a narrower policy
- Secrets Manager access and rotation
- RDS encryption and deletion protection
- S3 encryption, public-access blocks and retention
- ECR image scanning and lifecycle policy
- GitHub branch protection and environment approvals
- Whether Singapore data-residency requirements require `ap-southeast-1`
- Whether AWS SES should replace Gmail SMTP

## Information still needed from the client

Capacity and cost cannot be finalized without:

- Expected number of registered users
- Peak concurrent users
- Expected requests per second
- Expected number of funds and daily fund flows
- Required uptime or service-level objective
- Acceptable monthly AWS budget
- Required RTO and RPO
- Data-retention requirements
- Data-residency or regulatory requirements
- Whether this is a demonstration, pilot or real-money production system
- Whether Stripe remains in test mode and Alpaca remains paper-only

## Requested output from the cloud engineer

Please provide:

1. Final recommended architecture and diagram
2. EC2 versus ECS Fargate decision with reasons
3. Estimated monthly cost for development and production
4. Terraform changes required
5. Autoscaling policies and initial capacity
6. Backup, restore and disaster-recovery runbook
7. CI/CD pipeline design and rollback procedure
8. Security findings and remediation priorities
9. Monitoring dashboard and alarm list
10. A staged implementation plan with acceptance criteria

## Deployment acceptance criteria

The AWS deployment should not be considered complete until:

- HTTPS works using the final domain.
- Authentication cookies work across frontend and API requests.
- RDS has no public route or public endpoint access.
- Secrets are not present in GitHub, images or Terraform state in plaintext.
- Frontend and API health checks pass across two Availability Zones.
- Exactly one scheduler worker is running.
- Alembic reports the expected head revision.
- Manager creation, Operations approval and Investor visibility work.
- Demo PayNow or configured Stripe test payments complete correctly.
- Database backup and restore have been tested.
- A failed deployment automatically rolls back.
- CloudWatch alarms have been tested.
- CI/CD prevents a failing test or critical security finding from reaching
  production.
