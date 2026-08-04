# ────────────────────────────────────────────────────────────
# RDS Proxy — Connection pooling for multi-instance scenarios
#   Reduces connection overhead, improves failover speed, and
#   enforces TLS between application and database.
# ────────────────────────────────────────────────────────────

data "aws_iam_policy_document" "rds_proxy_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["rds.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "rds_proxy" {
  count = var.enable_rds_proxy ? 1 : 0

  name               = "${var.project_name}-rds-proxy-role-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.rds_proxy_assume.json

  tags = var.tags
}

data "aws_iam_policy_document" "rds_proxy_secrets" {
  statement {
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      aws_secretsmanager_secret.db.arn,
    ]
  }
}

resource "aws_iam_policy" "rds_proxy_secrets" {
  count = var.enable_rds_proxy ? 1 : 0

  name   = "${var.project_name}-rds-proxy-secrets-${var.environment}"
  policy = data.aws_iam_policy_document.rds_proxy_secrets.json
}

resource "aws_iam_role_policy_attachment" "rds_proxy_secrets" {
  count = var.enable_rds_proxy ? 1 : 0

  role       = aws_iam_role.rds_proxy[0].name
  policy_arn = aws_iam_policy.rds_proxy_secrets[0].arn
}

resource "aws_db_proxy" "main" {
  count = var.enable_rds_proxy ? 1 : 0

  name                   = "${var.project_name}-proxy-${var.environment}"
  debug_logging          = false
  engine_family          = "POSTGRESQL"
  idle_client_timeout    = 1800
  require_tls            = true
  role_arn               = aws_iam_role.rds_proxy[0].arn
  vpc_security_group_ids = [aws_security_group.rds.id]
  vpc_subnet_ids         = aws_subnet.database[*].id

  auth {
    auth_scheme = "SECRETS"
    iam_auth    = "DISABLED"
    secret_arn  = aws_secretsmanager_secret.db.arn
  }

  tags = var.tags
}

resource "aws_db_proxy_default_target_group" "main" {
  count = var.enable_rds_proxy ? 1 : 0

  db_proxy_name = aws_db_proxy.main[0].name

  connection_pool_config {
    connection_borrow_timeout    = 120
    max_connections_percent      = 50
    max_idle_connections_percent = 25
    session_pinning_filters = [
      "EXCLUDE_VARIABLE_SETS",
    ]
  }
}

resource "aws_db_proxy_target" "main" {
  count = var.enable_rds_proxy ? 1 : 0

  db_proxy_name          = aws_db_proxy.main[0].name
  db_instance_identifier = aws_db_instance.main.identifier
  target_group_name      = aws_db_proxy_default_target_group.main[0].name
}
