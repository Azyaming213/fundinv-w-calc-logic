# ────────────────────────────────────────────────────────────
# IAM — EC2 instance role for Secrets Manager + S3 + CloudWatch
# ────────────────────────────────────────────────────────────

# ── Trust policy (EC2 service) ──────────────────────────────
data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2" {
  name               = "${var.project_name}-ec2-role-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json

  tags = var.tags
}

# ── Secrets Manager read access ─────────────────────────────
data "aws_iam_policy_document" "secrets_read" {
  statement {
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = [
      aws_secretsmanager_secret.db.arn,
      aws_secretsmanager_secret.app.arn,
    ]
  }
}

resource "aws_iam_policy" "secrets_read" {
  name   = "${var.project_name}-secrets-read-${var.environment}"
  policy = data.aws_iam_policy_document.secrets_read.json
}

resource "aws_iam_role_policy_attachment" "secrets_read" {
  role       = aws_iam_role.ec2.name
  policy_arn = aws_iam_policy.secrets_read.arn
}

# ── S3 backup access ────────────────────────────────────────
data "aws_iam_policy_document" "s3_backup" {
  statement {
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.backups.arn,
      "${aws_s3_bucket.backups.arn}/*",
    ]
  }
}

resource "aws_iam_policy" "s3_backup" {
  name   = "${var.project_name}-s3-backup-${var.environment}"
  policy = data.aws_iam_policy_document.s3_backup.json
}

resource "aws_iam_role_policy_attachment" "s3_backup" {
  role       = aws_iam_role.ec2.name
  policy_arn = aws_iam_policy.s3_backup.arn
}

# ── ECR pull access ─────────────────────────────────────────
data "aws_iam_policy_document" "ecr_pull" {
  statement {
    sid    = "GetAuthorizationToken"
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "PullImages"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
    ]
    resources = [
      aws_ecr_repository.backend.arn,
      aws_ecr_repository.frontend.arn,
    ]
  }
}

resource "aws_iam_policy" "ecr_pull" {
  name   = "${var.project_name}-ecr-pull-${var.environment}"
  policy = data.aws_iam_policy_document.ecr_pull.json
}

resource "aws_iam_role_policy_attachment" "ecr_pull" {
  role       = aws_iam_role.ec2.name
  policy_arn = aws_iam_policy.ecr_pull.arn
}

# ── CloudWatch Logs (managed policy) ────────────────────────
resource "aws_iam_role_policy_attachment" "cloudwatch_logs" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
}

# ── Instance Profile ────────────────────────────────────────
resource "aws_iam_instance_profile" "ec2" {
  name = "${var.project_name}-ec2-profile-${var.environment}"
  role = aws_iam_role.ec2.name
}

# ── DynamoDB — Terraform state lock ─────────────────────────
resource "aws_dynamodb_table" "terraform_lock" {
  name         = "fundinv-terraform-lock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = var.tags
}
