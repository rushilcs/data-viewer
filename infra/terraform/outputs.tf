output "alb_dns_name" {
  description = "ALB DNS name (point CNAME domain_name to this)"
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "ALB zone id for Route53 alias"
  value       = aws_lb.main.zone_id
}

output "ecr_repository_url" {
  description = "ECR repository URL for backend image"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "ECS service name"
  value       = aws_ecs_service.backend.name
}

output "rds_endpoint" {
  description = "RDS instance endpoint (no port)"
  value       = aws_db_instance.main.address
}

output "rds_port" {
  description = "RDS port"
  value       = aws_db_instance.main.port
}

output "app_secret_arn" {
  description = "Secrets Manager secret ARN for DATABASE_URL and secret_key"
  value       = aws_secretsmanager_secret.app.arn
}

output "s3_bucket_name" {
  description = "S3 bucket for assets"
  value       = aws_s3_bucket.assets.id
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group for ECS"
  value       = aws_cloudwatch_log_group.ecs.name
}
