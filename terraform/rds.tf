# ────────────────────────────────────────────────────────────
# RDS — PostgreSQL 16.4, Multi-AZ, encrypted storage
# ────────────────────────────────────────────────────────────

# ── Parameter Group ─────────────────────────────────────────
resource "aws_db_parameter_group" "main" {
  name   = "${var.project_name}-pg16-${var.environment}"
  family = "postgres16"

  tags = var.tags
}

# ── RDS Instance ────────────────────────────────────────────
resource "aws_db_instance" "main" {
  identifier = "${var.project_name}-db-${var.environment}"

  engine         = "postgres"
  engine_version = "16.4"
  instance_class = var.db_instance_class

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db_password.result
  port     = 5432

  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true

  # High availability
  multi_az               = true
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  parameter_group_name = aws_db_parameter_group.main.name

  # Backups
  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:00-sun:05:00"
  copy_tags_to_snapshot   = true

  auto_minor_version_upgrade = true
  deletion_protection        = var.db_deletion_protection
  skip_final_snapshot        = var.db_deletion_protection ? false : true
  final_snapshot_identifier  = var.db_deletion_protection ? "${var.project_name}-db-final-${var.environment}" : null

  publicly_accessible = false

  tags = merge(var.tags, { Name = "${var.project_name}-rds" })
}
