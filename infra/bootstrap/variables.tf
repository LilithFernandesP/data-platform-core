variable "prefix" {
  description = "Prefixo global dos recursos (ex.: iniciais + projeto). Compõe nomes de bucket, que são únicos no mundo."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,20}[a-z0-9]$", var.prefix))
    error_message = "Use 3 a 22 caracteres: minúsculas, dígitos e hífen, sem hífen nas pontas."
  }
}

variable "aws_region" {
  description = "Região AWS da plataforma."
  type        = string
  default     = "us-east-2"
}

variable "noncurrent_version_retention_days" {
  description = "Dias que versões antigas do estado ficam guardadas antes de expirar."
  type        = number
  default     = 90
}
