output "cloudwatch_log_group_api" {
  description = "CloudWatch log group for API"
  value       = aws_cloudwatch_log_group.api.name
}

output "cloudwatch_log_group_airflow" {
  description = "CloudWatch log group for Airflow"
  value       = aws_cloudwatch_log_group.airflow.name
}

output "grafana_dns_name" {
  description = "Grafana DNS name"
  value       = "elyssa-grafana-${var.environment}"
}
