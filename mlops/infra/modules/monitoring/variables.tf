variable "environment" {
  description = "Environment name"
  type        = string
}

variable "alerting_enabled" {
  description = "Enable CloudWatch alerting alarms"
  type        = bool
  default     = false
}
