# Elyssa-IMDb | Terraform Backend Configuration
terraform {
  backend "s3" {
    bucket         = "elyssa-terraform-state"
    key            = "infra/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "elyssa-terraform-locks"
  }
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
