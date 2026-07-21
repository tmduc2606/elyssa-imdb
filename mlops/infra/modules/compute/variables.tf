variable "environment" {
  description = "Environment name (dev/staging/prod)"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type for ECS tasks"
  type        = string
}

variable "desired_count" {
  description = "Desired number of ECS task replicas"
  type        = number
}

variable "vpc_id" {
  description = "VPC ID for security groups"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for ECS service deployment"
  type        = list(string)
}
