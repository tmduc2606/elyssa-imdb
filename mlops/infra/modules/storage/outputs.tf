output "gold_marts_bucket" {
  description = "S3 bucket for Gold marts"
  value       = aws_s3_bucket.gold_marts.id
}

output "mlflow_artifacts_bucket" {
  description = "S3 bucket for MLflow artifacts"
  value       = aws_s3_bucket.mlflow_artifacts.id
}

output "backup_bucket_name" {
  description = "S3 bucket for backups"
  value       = aws_s3_bucket.backups.id
}
