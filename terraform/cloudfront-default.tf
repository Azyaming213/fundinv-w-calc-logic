# CloudFront endpoint for demonstrations that do not use a purchased domain.
# The AWS-provided certificate supplies HTTPS on the generated cloudfront.net URL.
resource "aws_cloudfront_distribution" "default" {
  count = var.domain_name == "" && var.enable_default_cloudfront ? 1 : 0

  enabled             = true
  is_ipv6_enabled     = true
  price_class         = var.cloudfront_price_class
  comment             = "FundInv dev HTTPS distribution"
  default_root_object = ""
  http_version        = "http2and3"

  web_acl_id = var.enable_waf ? aws_wafv2_web_acl.main[0].arn : null

  origin {
    domain_name = aws_lb.app.dns_name
    origin_id   = "fundinv-alb"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }

    custom_header {
      name  = "X-FundInv-Forwarded-Proto"
      value = "https"
    }
  }

  default_cache_behavior {
    target_origin_id       = "fundinv-alb"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS", "PUT", "PATCH", "POST", "DELETE"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad" # Managed-CachingDisabled
    origin_request_policy_id = "216adef6-5c7f-47e4-b989-5492eafa07d3" # Managed-AllViewer
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = var.tags
}
