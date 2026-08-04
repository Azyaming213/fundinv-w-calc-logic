# ────────────────────────────────────────────────────────────
# Outputs — values printed after terraform apply
# ────────────────────────────────────────────────────────────

output "domain_name" {
  description = "Application domain name (empty if not configured)"
  value       = var.domain_name
}

output "url" {
  description = "Full application URL"
  value = var.domain_name != "" ? "https://${var.domain_name}" : (
    var.enable_default_cloudfront ? "https://${aws_cloudfront_distribution.default[0].domain_name}" : "http://${aws_lb.app.dns_name}"
  )
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain name"
  value = var.domain_name != "" ? aws_cloudfront_distribution.main[0].domain_name : (
    var.enable_default_cloudfront ? aws_cloudfront_distribution.default[0].domain_name : null
  )
}

output "cloudfront_id" {
  description = "CloudFront distribution ID"
  value = var.domain_name != "" ? aws_cloudfront_distribution.main[0].id : (
    var.enable_default_cloudfront ? aws_cloudfront_distribution.default[0].id : null
  )
}

output "alb_dns_name" {
  description = "ALB DNS name"
  value       = aws_lb.app.dns_name
}

output "alb_arn_suffix" {
  description = "ALB ARN suffix"
  value       = aws_lb.app.arn_suffix
}

output "rds_endpoint" {
  description = "RDS endpoint (internal only)"
  value       = aws_db_instance.main.address
}

output "rds_port" {
  description = "RDS port"
  value       = aws_db_instance.main.port
}

output "rds_proxy_endpoint" {
  description = "RDS Proxy endpoint (use this instead of RDS endpoint when proxy is enabled)"
  value       = var.enable_rds_proxy ? aws_db_proxy.main[0].endpoint : null
}

output "db_identifier" {
  description = "RDS instance identifier"
  value       = aws_db_instance.main.identifier
}

output "db_secret_arn" {
  description = "Secrets Manager ARN for database credentials"
  value       = aws_secretsmanager_secret.db.arn
}

output "app_secret_arn" {
  description = "Secrets Manager ARN for application secrets"
  value       = aws_secretsmanager_secret.app.arn
}

output "backups_bucket" {
  description = "S3 bucket for database backups"
  value       = aws_s3_bucket.backups.bucket
}

output "app_assets_bucket" {
  description = "S3 bucket for application assets (PDFs, uploads)"
  value       = aws_s3_bucket.app_assets.bucket
}

output "ec2_instance_profile_name" {
  description = "EC2 instance profile name"
  value       = aws_iam_instance_profile.ec2.name
}

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "Private subnet IDs (EC2 instances)"
  value       = aws_subnet.private[*].id
}

output "ecr_backend_repo_url" {
  description = "ECR repository URL for the backend image"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_backend_repo_name" {
  description = "ECR repository name for the backend image"
  value       = aws_ecr_repository.backend.name
}

output "ecr_frontend_repo_url" {
  description = "ECR repository URL for the frontend image"
  value       = aws_ecr_repository.frontend.repository_url
}

output "ecr_frontend_repo_name" {
  description = "ECR repository name for the frontend image"
  value       = aws_ecr_repository.frontend.name
}

output "route53_zone_id" {
  description = "Route53 hosted zone ID"
  value       = var.domain_name != "" ? aws_route53_zone.main[0].zone_id : null
}

output "route53_name_servers" {
  description = "Route53 name servers (update your domain registrar with these)"
  value       = var.domain_name != "" ? aws_route53_zone.main[0].name_servers : null
}

output "sns_topic_arn" {
  description = "SNS topic ARN for CloudWatch alarms"
  value       = aws_sns_topic.alarms.arn
}

output "cloudwatch_dashboard_name" {
  description = "CloudWatch dashboard name"
  value       = aws_cloudwatch_dashboard.main.dashboard_name
}
