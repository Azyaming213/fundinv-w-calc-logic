locals {
  backup_name = "${var.project_name}-backup-${var.environment}"
}

resource "aws_cloudwatch_log_group" "backup" {
  name              = "/aws/lambda/${local.backup_name}"
  retention_in_days = 30
}

resource "aws_security_group" "backup" {
  name        = "${var.project_name}-backup-lambda-sg-${var.environment}"
  description = "Backup Lambda - outbound to RDS and VPC endpoints"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Secrets Manager + S3 (via endpoints)"
  }

  egress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "RDS PostgreSQL"
  }

  tags = var.tags
}

data "aws_iam_policy_document" "backup_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "backup" {
  name               = "${local.backup_name}-role"
  assume_role_policy = data.aws_iam_policy_document.backup_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "backup" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.db.arn]
  }
  statement {
    actions = ["s3:PutObject", "s3:GetObject"]
    resources = [
      aws_s3_bucket.backups.arn,
      "${aws_s3_bucket.backups.arn}/*",
    ]
  }
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.backup.arn}:*"]
  }
  statement {
    actions = [
      "ec2:CreateNetworkInterface",
      "ec2:DescribeNetworkInterfaces",
      "ec2:DeleteNetworkInterface",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "backup" {
  name   = "${local.backup_name}-policy"
  policy = data.aws_iam_policy_document.backup.json
}

resource "aws_iam_role_policy_attachment" "backup" {
  role       = aws_iam_role.backup.name
  policy_arn = aws_iam_policy.backup.arn
}

data "archive_file" "backup" {
  type        = "zip"
  output_path = "${path.module}/.terraform/backup_lambda_${var.environment}.zip"

  source {
    content  = file("${path.module}/backup_handler.py")
    filename = "index.py"
  }
}

resource "aws_lambda_function" "backup" {
  function_name = local.backup_name
  role          = aws_iam_role.backup.arn
  runtime       = "python3.12"
  handler       = "index.handler"
  timeout       = 300
  memory_size   = 256

  filename         = data.archive_file.backup.output_path
  source_code_hash = data.archive_file.backup.output_base64sha256

  layers = [aws_lambda_layer_version.pg_dump.arn]

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.backup.id]
  }

  environment {
    variables = {
      DB_SECRET_ARN  = aws_secretsmanager_secret.db.arn
      BACKUPS_BUCKET = aws_s3_bucket.backups.bucket
    }
  }

  depends_on = [aws_iam_role_policy_attachment.backup]

  tags = var.tags
}

resource "aws_lambda_layer_version" "pg_dump" {
  layer_name          = "${var.project_name}-pgdump-${var.environment}"
  s3_bucket           = aws_s3_bucket.backups.bucket
  s3_key              = "layers/pg_dump_layer.zip"
  compatible_runtimes = ["python3.12"]
}

resource "aws_cloudwatch_event_rule" "backup" {
  name                = "${local.backup_name}-cron"
  schedule_expression = "cron(0 2 * * ? *)"
  description         = "Daily pg_dump at 2 AM UTC"
  tags                = var.tags
}

resource "aws_cloudwatch_event_target" "backup" {
  rule      = aws_cloudwatch_event_rule.backup.name
  target_id = "lambda"
  arn       = aws_lambda_function.backup.arn
}

resource "aws_lambda_permission" "backup" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.backup.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.backup.arn
}
