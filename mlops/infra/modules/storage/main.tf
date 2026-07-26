# Elyssa-IMDb | Storage Module

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "lifecycle_rules_enabled" {
  description = "Enable S3 lifecycle rules"
  type        = bool
  default     = false
}

resource "aws_s3_bucket" "gold_marts" {
  bucket = "elyssa-${var.environment}-gold-marts"
  force_destroy = var.environment == "dev"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "gold_marts" {
  bucket = aws_s3_bucket.gold_marts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "gold_marts" {
  bucket = aws_s3_bucket.gold_marts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "gold_marts" {
  count  = var.lifecycle_rules_enabled ? 1 : 0
  bucket = aws_s3_bucket.gold_marts.id
  rule {
    id     = "expire-old-data"
    status = "Enabled"
    expiration {
      days = 90
    }
  }
}

resource "aws_s3_bucket_public_access_block" "gold_marts" {
  bucket = aws_s3_bucket.gold_marts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket" "mlflow_artifacts" {
  bucket = "elyssa-${var.environment}-mlflow-artifacts"
  force_destroy = var.environment == "dev"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "mlflow_artifacts" {
  bucket = aws_s3_bucket.mlflow_artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "mlflow_artifacts" {
  bucket = aws_s3_bucket.mlflow_artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket" "backups" {
  bucket = "elyssa-${var.environment}-backups"
  force_destroy = false
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id
  rule {
    id     = "transition-to-glacier"
    status = "Enabled"
    transition {
      days          = 30
      storage_class = "GLACIER"
    }
    expiration {
      days = 365
    }
  }
}
