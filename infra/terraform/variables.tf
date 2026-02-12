variable "environment" {
  description = "Environment name (e.g. staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

# Domain and TLS
variable "domain_name" {
  description = "Domain for the ALB (e.g. api.example.com)"
  type        = string
}

variable "acm_certificate_arn" {
  description = "ARN of ACM certificate for HTTPS (must cover domain_name)"
  type        = string
}

# ECS
variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 1
}

variable "ecs_cpu" {
  description = "CPU units for Fargate task (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "ecs_memory_mb" {
  description = "Memory for Fargate task (MB)"
  type        = number
  default     = 1024
}

# RDS
variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "rds_allocated_storage_gb" {
  description = "RDS allocated storage (GB)"
  type        = number
  default     = 20
}

# S3
variable "s3_bucket_name" {
  description = "S3 bucket name for assets (must be globally unique)"
  type        = string
}

variable "s3_enable_kms" {
  description = "Use SSE-KMS for S3 bucket"
  type        = bool
  default     = false
}

# WAF (prod: set true; local has no ALB so no WAF)
variable "enable_waf" {
  description = "Attach WAF (rate-based + managed rules) to ALB"
  type        = bool
  default     = true
}

# Naming
variable "project_name" {
  description = "Project name used in resource names"
  type        = string
  default     = "data-viewer"
}
