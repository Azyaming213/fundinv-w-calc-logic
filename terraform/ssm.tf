# ────────────────────────────────────────────────────────────
# SSM Session Manager — secure instance access without SSH
#   VPC endpoints allow EC2 to reach SSM APIs privately.
#   IAM policy allows Session Manager connections.
# ────────────────────────────────────────────────────────────

resource "aws_vpc_endpoint" "ssm" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.ssm"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]

  tags = merge(var.tags, { Name = "${var.project_name}-vpce-ssm" })
}

resource "aws_vpc_endpoint" "ssmmessages" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.ssmmessages"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]

  tags = merge(var.tags, { Name = "${var.project_name}-vpce-ssmmessages" })
}

resource "aws_vpc_endpoint" "ec2messages" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.ec2messages"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]

  tags = merge(var.tags, { Name = "${var.project_name}-vpce-ec2messages" })
}

data "aws_iam_policy_document" "ssm_session" {
  statement {
    actions = [
      "ssmmessages:CreateControlChannel",
      "ssmmessages:CreateDataChannel",
      "ssmmessages:OpenControlChannel",
      "ssmmessages:OpenDataChannel",
      "ssm:UpdateInstanceInformation",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "ssm_session" {
  name   = "${var.project_name}-ssm-session-${var.environment}"
  policy = data.aws_iam_policy_document.ssm_session.json
}

resource "aws_iam_role_policy_attachment" "ssm_session" {
  role       = aws_iam_role.ec2.name
  policy_arn = aws_iam_policy.ssm_session.arn
}

resource "aws_iam_role_policy_attachment" "ssm_managed" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
