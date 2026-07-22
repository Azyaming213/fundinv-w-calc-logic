# ────────────────────────────────────────────────────────────
# Secrets Manager — DB credentials + application secrets
# ────────────────────────────────────────────────────────────

# ── Database credentials ────────────────────────────────────
resource "random_password" "db_password" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "db" {
  name                    = "${var.project_name}/db-${var.environment}"
  recovery_window_in_days = var.environment == "prod" ? 7 : 0

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    host     = aws_db_instance.main.address
    port     = aws_db_instance.main.port
    dbname   = var.db_name
    username = var.db_username
    password = random_password.db_password.result
    url      = "postgresql://${var.db_username}:${random_password.db_password.result}@${aws_db_instance.main.address}:${aws_db_instance.main.port}/${var.db_name}"
  })
}

# ── Application secrets ─────────────────────────────────────
resource "aws_secretsmanager_secret" "app" {
  name                    = "${var.project_name}/app-${var.environment}"
  recovery_window_in_days = var.environment == "prod" ? 7 : 0

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    SECRET_KEY            = var.app_secret_key
    JWT_ALGORITHM         = "HS256"
    JWT_EXPIRY_MINUTES    = "60"
    ENVIRONMENT           = var.environment
    FRONTEND_URL          = var.frontend_url
    STRIPE_SECRET_KEY     = var.stripe_secret_key
    STRIPE_WEBHOOK_SECRET = var.stripe_webhook_secret
    ALPACA_API_KEY        = var.alpaca_api_key
    ALPACA_SECRET_KEY     = var.alpaca_secret_key
    ALPACA_BASE_URL       = "https://paper-api.alpaca.markets"
    ALPACA_DATA_URL       = "https://data.alpaca.markets"
    SMTP_EMAIL            = var.smtp_email
    SMTP_PASSWORD         = var.smtp_password
    AUTO_MIGRATE          = "true"
  })
}
