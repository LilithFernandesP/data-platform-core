locals {
  lake_bucket_name = "${var.prefix}-lake-${var.environment}"
}

module "lake" {
  source      = "./modules/lake"
  bucket_name = local.lake_bucket_name
}