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

resource "aws_s3_bucket" "mlflow_artifacts" {
  bucket = "elyssa-${var.environment}-mlflow-artifacts"
  force_destroy = var.environment == "dev"
}

resource "aws_s3_bucket" "backups" {
  bucket = "elyssa-${var.environment}-backups"
  force_destroy = false
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
