resource "aws_launch_template" "app" {
  name          = "${var.project_name}-lt-${var.environment}"
  image_id      = data.aws_ami.amazon_linux_2023.id
  instance_type = var.ec2_instance_type
  key_name      = var.key_name

  iam_instance_profile {
    name = aws_iam_instance_profile.ec2.name
  }

  vpc_security_group_ids = [aws_security_group.ec2.id]

  user_data = base64encode(templatefile("${path.module}/templates/user-data.sh.tmpl", {
    account_id     = data.aws_caller_identity.current.account_id
    aws_region     = var.aws_region
    project_name   = var.project_name
    environment    = var.environment
    db_secret_arn  = aws_secretsmanager_secret.db.arn
    app_secret_arn = aws_secretsmanager_secret.app.arn
    backups_bucket = aws_s3_bucket.backups.bucket
    assets_bucket  = aws_s3_bucket.app_assets.bucket
  }))

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = 30
      volume_type           = "gp3"
      delete_on_termination = true
      encrypted             = true
    }
  }

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  tag_specifications {
    resource_type = "instance"
    tags = merge(var.tags, {
      Name = "${var.project_name}-ec2-${var.environment}"
    })
  }

  tags = var.tags
}

resource "aws_autoscaling_group" "app" {
  name                      = "${var.project_name}-asg-${var.environment}"
  vpc_zone_identifier       = aws_subnet.private[*].id
  min_size                  = var.ec2_min_size
  max_size                  = var.ec2_max_size
  desired_capacity          = var.ec2_desired_size
  health_check_type         = "ELB"
  health_check_grace_period = 900

  launch_template {
    id      = aws_launch_template.app.id
    version = "$Latest"
  }

  target_group_arns = [aws_lb_target_group.app.arn]

  tag {
    key                 = "Name"
    value               = "${var.project_name}-ec2-${var.environment}"
    propagate_at_launch = true
  }
}

resource "aws_lb" "app" {
  name               = "${var.project_name}-alb-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.bucket
    enabled = true
    prefix  = "alb-logs"
  }

  tags = merge(var.tags, { Name = "${var.project_name}-alb" })
}

resource "aws_lb_target_group" "app" {
  name     = "${var.project_name}-tg-${var.environment}"
  port     = 80
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id

  health_check {
    path                = "/api/test"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200-399"
  }

  tags = var.tags
}

resource "aws_lb_listener" "app_http" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = var.domain_name != "" ? "fixed-response" : "forward"

    dynamic "forward" {
      for_each = var.domain_name == "" ? [1] : []
      content {
        target_group {
          arn = aws_lb_target_group.app.arn
        }
      }
    }

    dynamic "fixed_response" {
      for_each = var.domain_name != "" ? [1] : []
      content {
        content_type = "text/plain"
        message_body = "Direct access not allowed"
        status_code  = "403"
      }
    }
  }
}

resource "aws_lb_listener_rule" "cloudfront_verify" {
  count        = var.domain_name != "" ? 1 : 0
  listener_arn = aws_lb_listener.app_http.arn
  priority     = 1

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }

  condition {
    http_header {
      http_header_name = "X-Origin-Verify"
      values           = [random_password.origin_verify[0].result]
    }
  }
}

resource "aws_lb_listener" "app_https" {
  count             = var.domain_name != "" ? 1 : 0
  load_balancer_arn = aws_lb.app.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.alb[0].certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

resource "aws_autoscaling_policy" "cpu_target_tracking" {
  name                      = "${var.project_name}-cpu-scaling-${var.environment}"
  autoscaling_group_name    = aws_autoscaling_group.app.name
  policy_type               = "TargetTrackingScaling"
  estimated_instance_warmup = 300

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
    target_value = 70.0
  }
}
