# ────────────────────────────────────────────────────────────
# VPC Endpoints — PrivateLink for AWS services
#   Eliminates NAT Gateway data transfer costs for AWS APIs.
#   EC2 instances reach these services within the AWS backbone.
# ────────────────────────────────────────────────────────────

resource "aws_security_group" "vpc_endpoints" {
  name        = "${var.project_name}-vpce-sg-${var.environment}"
  description = "VPC endpoints - allow HTTPS from EC2"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2.id, aws_security_group.backup.id]
    description     = "HTTPS from EC2 and backup Lambda"
  }

  tags = merge(var.tags, { Name = "${var.project_name}-vpce-sg" })
}

resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]

  tags = merge(var.tags, { Name = "${var.project_name}-vpce-secretsmanager" })
}

resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]

  tags = merge(var.tags, { Name = "${var.project_name}-vpce-ecr-api" })
}

resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]

  tags = merge(var.tags, { Name = "${var.project_name}-vpce-ecr-dkr" })
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = aws_route_table.private[*].id

  tags = merge(var.tags, { Name = "${var.project_name}-vpce-s3" })
}
