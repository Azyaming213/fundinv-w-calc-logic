# ────────────────────────────────────────────────────────────
# Outputs — values printed after terraform apply
# ────────────────────────────────────────────────────────────

output "alb_dns_name" {
  description = "ALB DNS name — access the application here"
  value       = "http://${aws_lb.app.dns_name}"
}

output "alb_dns_name_full" {
  description = "Full ALB DNS name"
  value       = aws_lb.app.dns_name
}

output "rds_endpoint" {
  description = "RDS endpoint (internal only)"
  value       = aws_db_instance.main.address
}

output "rds_port" {
  description = "RDS port"
  value       = aws_db_instance.main.port
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
