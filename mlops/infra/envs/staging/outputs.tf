output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "api_endpoint" {
  description = "API endpoint URL"
  value       = "http://${module.compute.api_dns_name}:8000"
}

output "mlflow_endpoint" {
  description = "MLflow tracking URL"
  value       = "http://${module.compute.mlflow_dns_name}:5000"
}

output "grafana_endpoint" {
  description = "Grafana dashboard URL"
  value       = "http://${module.monitoring.grafana_dns_name}:3000"
}
