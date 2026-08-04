# ── AWS ──
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-southeast-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name prefix for all resources"
  type        = string
  default     = "fundinv"
}

variable "key_name" {
  description = "SSH key pair name for EC2 instances"
  type        = string
}

# ── Networking ──
variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

# ── RDS ──
variable "db_name" {
  description = "Database name"
  type        = string
  default     = "fundinv"
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "yeaw_min"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.small"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
  default     = 5
}

variable "db_deletion_protection" {
  description = "Enable RDS deletion protection (set true for production)"
  type        = bool
  default     = false
}

# ── EC2 ──
variable "ec2_instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.medium"
}

variable "ec2_min_size" {
  description = "Auto Scaling Group minimum instances"
  type        = number
  default     = 1
}

variable "ec2_max_size" {
  description = "Auto Scaling Group maximum instances"
  type        = number
  default     = 2
}

variable "ec2_desired_size" {
  description = "Auto Scaling Group desired instances"
  type        = number
  default     = 1
}

# ── Application secrets ──
variable "app_secret_key" {
  description = "JWT signing secret (64+ characters)"
  type        = string
  sensitive   = true
}

variable "stripe_secret_key" {
  description = "Stripe secret key (sk_...)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "stripe_webhook_secret" {
  description = "Stripe webhook signing secret (whsec_...)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "alpaca_api_key" {
  description = "Alpaca Markets API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "alpaca_secret_key" {
  description = "Alpaca Markets secret key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "smtp_email" {
  description = "SMTP sender email address"
  type        = string
  default     = ""
}

variable "smtp_password" {
  description = "SMTP app password"
  type        = string
  sensitive   = true
  default     = ""
}

variable "frontend_url" {
  description = "Frontend URL for CORS origins and email links"
  type        = string
  default     = ""
}

# ── Domain ──
variable "domain_name" {
  description = "Root domain name for the application (e.g. fundinv.com). Leave empty to skip CloudFront/ACM/Route53."
  type        = string
  default     = ""
}

variable "enable_default_cloudfront" {
  description = "Create an HTTPS CloudFront endpoint using the AWS-provided cloudfront.net certificate when no custom domain is configured."
  type        = bool
  default     = false
}

# ── Monitoring ──
variable "alarm_email" {
  description = "Email address for CloudWatch alarm notifications"
  type        = string
  default     = ""
}

variable "cloudfront_price_class" {
  description = "CloudFront distribution price class"
  type        = string
  default     = "PriceClass_100"
}

# ── WAF ──
variable "enable_waf" {
  description = "Enable WAF Web ACL attached to CloudFront"
  type        = bool
  default     = true
}

# ── RDS Proxy ──
variable "enable_rds_proxy" {
  description = "Enable RDS Proxy for connection pooling (recommended for production)"
  type        = bool
  default     = false
}

# ── CloudWatch ──
variable "cloudwatch_log_retention_days" {
  description = "CloudWatch log group retention in days"
  type        = number
  default     = 30
}

# ── Tags ──
variable "tags" {
  description = "Common resource tags"
  type        = map(string)
  default = {
    Project   = "fundinv"
    ManagedBy = "terraform"
  }
}
