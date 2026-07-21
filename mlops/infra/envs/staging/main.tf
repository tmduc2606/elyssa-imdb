# Elyssa-IMDb | Staging Environment
module "networking" {
  source = "../../modules/networking"
  environment = "staging"
  vpc_cidr    = "10.1.0.0/16"
}

module "compute" {
  source = "../../modules/compute"
  environment = "staging"
  instance_type = "t3.large"
  desired_count = 2
  vpc_id        = module.networking.vpc_id
  subnet_ids    = module.networking.private_subnet_ids
}

module "storage" {
  source = "../../modules/storage"
  environment = "staging"
}

module "monitoring" {
  source = "../../modules/monitoring"
  environment = "staging"
}
