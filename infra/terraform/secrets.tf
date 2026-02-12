# Secrets Manager: placeholder secrets. Set values outside Terraform (Console, CLI, or CI).
# No plaintext secrets in state; task definition references ARNs.

resource "aws_secretsmanager_secret" "app" {
  name        = "${local.name}/app"
  description = "App secrets: DATABASE_URL, secret_key (JWT). Set value via Console/CLI."
  # Optional: recovery_window_in_days = 7
}

# Placeholder value only to create the key; replace with real secret JSON after creation.
resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    DATABASE_URL = "postgresql+asyncpg://REPLACE_USER:REPLACE_PASSWORD@REPLACE_RDS_ENDPOINT:5432/viewer"
    secret_key   = "REPLACE_WITH_JWT_SECRET"
  })
  lifecycle {
    ignore_changes = [secret_string]
  }
}
