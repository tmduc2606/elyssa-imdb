# Elyssa-IMDb | Production Environment
module "networking" {
  source = "../../modules/networking"
  environment = "prod"
  vpc_cidr    = "10.2.0.0/16"
}

module "compute" {
  source = "../../modules/compute"
  environment = "prod"
  instance_type = "t3.xlarge"
  desired_count = 3
  vpc_id        = module.networking.vpc_id
  subnet_ids    = module.networking.private_subnet_ids
}

module "storage" {
  source = "../../modules/storage"
  environment = "prod"
  lifecycle_rules_enabled = true
}

module "monitoring" {
  source = "../../modules/monitoring"
  environment = "prod"
  alerting_enabled = true
}
