# Elyssa-IMDb | Dev Environment
module "networking" {
  source = "../../modules/networking"
  environment = "dev"
  vpc_cidr    = "10.0.0.0/16"
}

module "compute" {
  source = "../../modules/compute"
  environment = "dev"
  instance_type = "t3.medium"
  desired_count = 1
  vpc_id        = module.networking.vpc_id
  subnet_ids    = module.networking.public_subnet_ids
}

module "storage" {
  source = "../../modules/storage"
  environment = "dev"
}
