variable "environment" {
  description = "Environment name"
  type        = string
}

variable "lifecycle_rules_enabled" {
  description = "Enable S3 lifecycle rules for data expiration"
  type        = bool
  default     = false
}
