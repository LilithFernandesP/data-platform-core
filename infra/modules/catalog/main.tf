resource "aws_glue_catalog_database" "databases" {
  for_each = var.databases

  name         = each.key
  description  = "gerenciado pelo data-platform-core"
  location_uri = each.value
}