# ────────────────────────────────────────────────────────────
# EC2 — Launch Template, Auto Scaling Group, Application Load Balancer
# ────────────────────────────────────────────────────────────

# ── Launch Template ─────────────────────────────────────────
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
    environment    = var.environment
    project_name   = var.project_name
    db_secret_arn  = aws_secretsmanager_secret.db.arn
    app_secret_arn = aws_secretsmanager_secret.app.arn
    aws_region     = var.aws_region
    backups_bucket = aws_s3_bucket.backups.bucket
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

# ── Auto Scaling Group ──────────────────────────────────────
resource "aws_autoscaling_group" "app" {
  name                = "${var.project_name}-asg-${var.environment}"
  vpc_zone_identifier = aws_subnet.private[*].id
  min_size            = var.ec2_min_size
  max_size            = var.ec2_max_size
  desired_capacity    = var.ec2_desired_size
  health_check_type   = "ELB"
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

# ── Application Load Balancer ───────────────────────────────
resource "aws_lb" "app" {
  name               = "${var.project_name}-alb-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  tags = merge(var.tags, { Name = "${var.project_name}-alb" })
}

# ── Target Group ────────────────────────────────────────────
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

# ── ALB Listener — HTTP on port 80 ──────────────────────────
resource "aws_lb_listener" "app" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}
