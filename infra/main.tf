locals {
  lake_bucket_name = "${var.prefix}-lake-${var.environment}"

  domains = ["cinema"]
  layers  = ["bronze", "silver", "gold"]

  glue_databases = {
    for pair in setproduct(local.domains, local.layers) :
    "${pair[0]}_${pair[1]}_${var.environment}" => "s3://${module.lake.bucket_name}/${pair[1]}/${pair[0]}/"
  }
}

module "lake" {
  source      = "./modules/lake"
  bucket_name = local.lake_bucket_name
}

module "catalog" {
  source    = "./modules/catalog"
  databases = local.glue_databases
}