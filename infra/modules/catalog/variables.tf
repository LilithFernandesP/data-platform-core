variable "databases" {
  description = "lista de databases para criar no glue: nome => caminho no s3"
  type        = map(string)
}

