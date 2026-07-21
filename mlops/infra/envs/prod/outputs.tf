output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "api_endpoint" {
  description = "API endpoint URL"
  value       = "https://${module.compute.api_dns_name}"
}

output "mlflow_endpoint" {
  description = "MLflow tracking URL"
  value       = "https://${module.compute.mlflow_dns_name}"
}

output "grafana_endpoint" {
  description = "Grafana dashboard URL"
  value       = "https://${module.monitoring.grafana_dns_name}"
}

output "backup_bucket" {
  description = "S3 backup bucket name"
  value       = module.storage.backup_bucket_name
}
