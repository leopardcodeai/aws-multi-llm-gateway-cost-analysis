terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    bucket = "llm-gateway-terraform-state"
    key    = "prod/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  default = "us-east-1"
}

variable "environment" {
  default = "prod"
}

variable "openai_api_key" {
  type      = string
  sensitive = true
}

locals {
  name_prefix = "llm-gateway-${var.environment}"
  tags = {
    Project     = "llm-gateway"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_bedrock_model_invocation_role" "gateway" {
  name = "${local.name_prefix}-bedrock-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "bedrock.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "bedrock_models" {
  role = aws_iam_role.gateway.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ]
      Resource = [
        "arn:aws:bedrock:${var.aws_region}::foundation-model/anthropic.claude-3*",
        "arn:aws:bedrock:${var.aws_region}::foundation-model/meta.llama3*",
        "arn:aws:bedrock:${var.aws_region}::foundation-model/meta.llama4*",
      ]
    }]
  })
}

resource "aws_iam_role" "gateway" {
  name = "${local.name_prefix}-gateway-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_dynamodb_table" "tenants" {
  name           = "${local.name_prefix}-tenants"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "tenant_id"
  attribute {
    name = "tenant_id"
    type = "S"
  }
  attribute {
    name = "api_key_hash"
    type = "S"
  }
  global_secondary_index {
    name            = "api_key_hash-index"
    hash_key        = "api_key_hash"
    projection_type = "ALL"
  }
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
  tags = local.tags
}

resource "aws_secretsmanager_secret" "openai_key" {
  name = "${local.name_prefix}/openai-api-key"
  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "openai_key" {
  secret_id = aws_secretsmanager_secret.openai_key.id
  secret_string = var.openai_api_key
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${local.name_prefix}-cache"
  engine               = "redis"
  engine_version       = "7.1"
  node_type            = "cache.t3.micro"
  number_cache_clusters = 2
  port                 = 6379
  parameter_group_name = "default.redis7"
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token_enabled = true
  auth_token = var.redis_auth_token
  tags = local.tags
}

resource "aws_ecs_cluster" "gateway" {
  name = "${local.name_prefix}-cluster"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  tags = local.tags
}

resource "aws_ecs_task_definition" "gateway" {
  family = "${local.name_prefix}-gateway"
  network_mode = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu    = "1024"
  memory = "2048"
  execution_role_arn = aws_iam_role.gateway.arn
  task_role_arn = aws_iam_role.gateway.arn

  container_definitions = jsonencode([{
    name = "gateway"
    image = "${aws_ecr_repository.gateway.repository_url}:latest"
    portMappings = [
      { containerPort = 8000, protocol = "tcp" },
      { containerPort = 9090, protocol = "tcp" }
    ]
    environment = [
      { name = "AWS_REGION", value = var.aws_region },
      { name = "REDIS_HOST", value = aws_elasticache_replication_group.redis.primary_endpoint_address },
      { name = "REDIS_PORT", value = "6379" },
      { name = "REDIS_PASSWORD", value = var.redis_auth_token },
      { name = "DYNAMODB_TABLE", value = aws_dynamodb_table.tenants.name },
      { name = "LOG_LEVEL", value = "INFO" }
    ]
    secrets = [
      { name = "OPENAI_API_KEY", valueFrom = aws_secretsmanager_secret.openai_key.arn }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group" = aws_cloudwatch_log_group.gateway.name
        "awslogs-region" = var.aws_region
        "awslogs-stream-prefix" = "gateway"
      }
    }
    healthCheck = {
      command = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval = 30
      timeout = 5
      retries = 3
      startPeriod = 60
    }
  })
}

resource "aws_ecr_repository" "gateway" {
  name = "${local.name_prefix}-gateway"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
  tags = local.tags
}

resource "aws_cloudwatch_log_group" "gateway" {
  name = "/ecs/${local.name_prefix}-gateway"
  retention_in_days = 30
  tags = local.tags
}

resource "aws_lb" "gateway" {
  name = "${local.name_prefix}-alb"
  internal = false
  load_balancer_type = "application"
  security_groups = [aws_security_group.alb.id]
  subnets = var.public_subnet_ids
  enable_deletion_protection = false
  tags = local.tags
}

resource "aws_lb_target_group" "gateway" {
  name = "${local.name_prefix}-tg"
  port = 8000
  protocol = "HTTP"
  target_type = "ip"
  vpc_id = var.vpc_id
  health_check {
    path = "/health"
    interval = 30
    timeout = 5
    healthy_threshold = 2
    unhealthy_threshold = 3
  }
  tags = local.tags
}

resource "aws_lb_listener" "gateway" {
  load_balancer_arn = aws_lb.gateway.arn
  port = 80
  protocol = "HTTP"
  default_action {
    type = "forward"
    target_group_arn = aws_lb_target_group.gateway.arn
  }
}

resource "aws_security_group" "alb" {
  name = "${local.name_prefix}-alb-sg"
  vpc_id = var.vpc_id
  ingress {
    from_port = 80
    to_port = 80
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port = 443
    to_port = 443
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}

resource "aws_security_group" "ecs" {
  name = "${local.name_prefix}-ecs-sg"
  vpc_id = var.vpc_id
  ingress {
    from_port = 8000
    to_port = 8000
    protocol = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  ingress {
    from_port = 9090
    to_port = 9090
    protocol = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}

resource "aws_ecs_service" "gateway" {
  name = "${local.name_prefix}-gateway"
  cluster = aws_ecs_cluster.gateway.id
  task_definition = aws_ecs_task_definition.gateway.arn
  desired_count = 2
  launch_type = "FARGATE"
  network_configuration {
    subnets = var.private_subnet_ids
    security_groups = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.gateway.arn
    container_name = "gateway"
    container_port = 8000
  }
  deployment_controller {
    type = "ECS"
  }
  deployment_circuit_breaker {
    enable = true
    rollback = true
  }
  tags = local.tags
}

variable "vpc_id" {}
variable "public_subnet_ids" {
  type = list(string)
}
variable "private_subnet_ids" {
  type = list(string)
}
variable "redis_auth_token" {
  type      = string
  sensitive = true
}

output "alb_dns_name" {
  value = aws_lb.gateway.dns_name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.gateway.repository_url
}