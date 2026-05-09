"""
Terraform - Main AWS Infrastructure Configuration
Provisions ECR, ECS, RDS, S3, SQS, and networking
"""

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  # Uncomment for remote state management
  # backend "s3" {
  #   bucket         = "rag-terraform-state"
  #   key            = "prod/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "Agentic-RAG"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# VPC and Networking
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  version = "5.1.2"

  name = "${var.project_name}-vpc"
  cidr = "10.0.0.0/16"

  azs             = data.aws_availability_zones.available.names
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway = true
  enable_vpn_gateway = false
  enable_dns_hostnames = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

# Security Groups
resource "aws_security_group" "ecs_tasks" {
  name        = "${var.project_name}-ecs-tasks"
  description = "Allow inbound traffic for ECS tasks"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 8000
    to_port     = 8099
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "rag" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 30
}

# ECR Repositories for each service
locals {
  services = [
    "document-ingestion",
    "document-parsing",
    "embedding-service",
    "retrieval-service",
    "agent-orchestration",
    "query-processing",
    "evaluation-service",
  ]
}

resource "aws_ecr_repository" "services" {
  for_each = toset(local.services)

  name                 = "${var.project_name}/${each.value}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${var.project_name}-${each.value}"
  }
}

# RDS for MongoDB (using DocumentDB for production)
resource "aws_docdb_cluster" "rag" {
  cluster_identifier      = "${var.project_name}-cluster"
  engine                  = "docdb"
  master_username         = var.db_username
  master_password         = random_password.db_password.result
  backup_retention_period = 5
  preferred_backup_window = "07:00-09:00"
  skip_final_snapshot     = var.environment != "production"

  db_subnet_group_name            = aws_docdb_subnet_group.rag.name
  db_cluster_parameter_group_name = aws_docdb_cluster_parameter_group.rag.name
  vpc_security_group_ids          = [aws_security_group.docdb.id]

  enabled_cloudwatch_logs_exports = ["audit", "error", "general", "slowlog"]

  tags = {
    Name = "${var.project_name}-docdb"
  }
}

resource "aws_docdb_cluster_instance" "rag" {
  count              = 2
  cluster_identifier = aws_docdb_cluster.rag.id
  instance_class     = "db.t3.small"
  engine              = "docdb"

  tags = {
    Name = "${var.project_name}-docdb-instance-${count.index + 1}"
  }
}

resource "aws_docdb_subnet_group" "rag" {
  name       = "${var.project_name}-docdb-subnet"
  subnet_ids = module.vpc.private_subnets

  tags = {
    Name = "${var.project_name}-docdb-subnet-group"
  }
}

resource "aws_docdb_cluster_parameter_group" "rag" {
  family = "docdb4.0"
  name   = "${var.project_name}-docdb-params"

  tags = {
    Name = "${var.project_name}-docdb-params"
  }
}

resource "aws_security_group" "docdb" {
  name        = "${var.project_name}-docdb"
  description = "Security group for DocumentDB"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 27017
    to_port         = 27017
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ElastiCache for Redis
resource "aws_elasticache_cluster" "rag" {
  cluster_id           = "${var.project_name}-redis"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  engine_version       = "7.0"
  port                 = 6379
  security_group_ids   = [aws_security_group.redis.id]
  subnet_group_name    = aws_elasticache_subnet_group.rag.name

  tags = {
    Name = "${var.project_name}-redis"
  }
}

resource "aws_elasticache_subnet_group" "rag" {
  name       = "${var.project_name}-redis-subnet"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "redis" {
  name        = "${var.project_name}-redis"
  description = "Security group for Redis"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# S3 Bucket for documents
resource "aws_s3_bucket" "documents" {
  bucket = "${var.project_name}-documents-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.project_name}-documents"
  }
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_encryption" "documents" {
  bucket = aws_s3_bucket.documents.id

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }
}

# SQS Queue for document processing
resource "aws_sqs_queue" "documents" {
  name                      = "${var.project_name}-documents"
  delay_seconds             = 0
  max_message_size          = 262144
  message_retention_seconds = 1209600  # 14 days
  receive_wait_time_seconds = 20
  visibility_timeout_seconds = 300

  tags = {
    Name = "${var.project_name}-sqs"
  }
}

resource "aws_sqs_queue_policy" "documents_s3_events" {
  queue_url = aws_sqs_queue.documents.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowS3DocumentCreatedEvents"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.documents.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_s3_bucket.documents.arn
          }
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}

resource "aws_s3_bucket_notification" "documents" {
  bucket = aws_s3_bucket.documents.id

  queue {
    queue_arn     = aws_sqs_queue.documents.arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "documents/"
  }

  depends_on = [aws_sqs_queue_policy.documents_s3_events]
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# Random password for database
resource "random_password" "db_password" {
  length  = 32
  special = true
}

# Outputs
output "vpc_id" {
  value = module.vpc.vpc_id
}

output "docdb_cluster_endpoint" {
  value = aws_docdb_cluster.rag.endpoint
}

output "redis_endpoint" {
  value = aws_elasticache_cluster.rag.cache_nodes[0].address
}

output "s3_bucket_name" {
  value = aws_s3_bucket.documents.bucket
}

output "sqs_queue_url" {
  value = aws_sqs_queue.documents.url
}
