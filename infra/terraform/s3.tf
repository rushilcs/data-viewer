resource "aws_s3_bucket" "assets" {
  bucket = var.s3_bucket_name
}

resource "aws_s3_bucket_public_access_block" "assets" {
  bucket = aws_s3_bucket.assets.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "assets" {
  bucket = aws_s3_bucket.assets.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "assets_aes" {
  count  = var.s3_enable_kms ? 0 : 1
  bucket = aws_s3_bucket.assets.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "assets_kms" {
  count  = var.s3_enable_kms ? 1 : 0
  bucket = aws_s3_bucket.assets.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3[0].arn
    }
  }
}

resource "aws_kms_key" "s3" {
  count = var.s3_enable_kms ? 1 : 0
  description = "KMS key for ${local.name} S3 bucket"
  deletion_window_in_days = 7
}

resource "aws_kms_alias" "s3" {
  count = var.s3_enable_kms ? 1 : 0
  name          = "alias/${local.name}-s3"
  target_key_id = aws_kms_key.s3[0].key_id
}
