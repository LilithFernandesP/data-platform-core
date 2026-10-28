output "database_names" {
  description = "Nomes dos databases criados"
  value       = keys(var.databases)
}