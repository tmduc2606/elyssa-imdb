output "cluster_id" {
  description = "ECS cluster ID"
  value       = aws_ecs_cluster.elyssa.id
}

output "api_dns_name" {
  description = "API service DNS name"
  value       = aws_ecs_service.api.name
}

output "mlflow_dns_name" {
  description = "MLflow service DNS name"
  value       = "elyssa-mlflow-${var.environment}"
}

output "security_group_id" {
  description = "API security group ID"
  value       = aws_security_group.api.id
}
