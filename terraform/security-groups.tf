# ────────────────────────────────────────────────────────────
# Security Groups
# ────────────────────────────────────────────────────────────

data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

# ── ALB — allows HTTP from CloudFront (or internet when no domain) ──
resource "aws_security_group" "alb" {
  name        = "${var.project_name}-alb-sg-${var.environment}"
  description = "ALB security group"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    cidr_blocks     = var.domain_name != "" ? null : ["0.0.0.0/0"]
    prefix_list_ids = var.domain_name != "" ? [data.aws_ec2_managed_prefix_list.cloudfront.id] : null
    description     = "HTTP"
  }

  ingress {
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    cidr_blocks     = var.domain_name != "" ? null : ["0.0.0.0/0"]
    prefix_list_ids = var.domain_name != "" ? [data.aws_ec2_managed_prefix_list.cloudfront.id] : null
    description     = "HTTPS"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "${var.project_name}-alb-sg" })
}

# ── EC2 — allows HTTP from ALB ──────────────────────────────
resource "aws_security_group" "ec2" {
  name        = "${var.project_name}-ec2-sg-${var.environment}"
  description = "EC2 security group"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
    description     = "HTTP from ALB"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Outbound - Alpaca, Stripe, SMTP, Yahoo, Secrets Manager, S3"
  }

  tags = merge(var.tags, { Name = "${var.project_name}-ec2-sg" })
}

# ── RDS — PostgreSQL from EC2 only ──────────────────────────
resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds-sg-${var.environment}"
  description = "RDS security group"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2.id]
    description     = "PostgreSQL from EC2"
  }

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.backup.id]
    description     = "PostgreSQL from backup Lambda"
  }

  tags = merge(var.tags, { Name = "${var.project_name}-rds-sg" })
}
