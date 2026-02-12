resource "aws_db_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.private[*].id
}

resource "random_password" "rds" {
  length  = 24
  special = true
}

resource "aws_db_instance" "main" {
  identifier     = local.name
  engine         = "postgres"
  engine_version = "15"
  instance_class = var.rds_instance_class
  allocated_storage = var.rds_allocated_storage_gb

  db_name  = "viewer"
  username = "viewer"
  password = random_password.rds.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  multi_az              = var.environment == "prod"

  storage_encrypted = true
  skip_final_snapshot = var.environment != "prod"
  final_snapshot_identifier = var.environment == "prod" ? "${local.name}-final" : null
}

# Output connection info so you can set Secrets Manager DATABASE_URL (no password in output by default; use -json and jq if needed)
# Format: postgresql+asyncpg://viewer:PASSWORD@ENDPOINT:5432/viewer?sslmode=require
