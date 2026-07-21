# Elyssa-IMDb | Monitoring Module

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "alerting_enabled" {
  description = "Enable alerting rules"
  type        = bool
  default     = false
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/elyssa-api-${var.environment}"
  retention_in_days = 90
}

resource "aws_cloudwatch_log_group" "airflow" {
  name              = "/ecs/elyssa-airflow-${var.environment}"
  retention_in_days = 90
}

resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  count               = var.alerting_enabled ? 1 : 0
  alarm_name          = "elyssa-${var.environment}-high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "ErrorRate"
  namespace           = "Elyssa"
  period              = 60
  statistic           = "Average"
  threshold           = 0.01
  alarm_description   = "API error rate > 1% for 5 minutes"
  alarm_actions       = []  # SNS topic ARN would go here
}
