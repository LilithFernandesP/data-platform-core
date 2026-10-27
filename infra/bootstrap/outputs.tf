output "state_bucket_name" {
  description = "Bucket do estado remoto de todos os ambientes."
  value       = aws_s3_bucket.state.bucket
}

output "backend_hcl" {
  description = "Conteúdo para infra/envs/<env>/backend.hcl."
  value       = <<-EOT
    bucket = "${aws_s3_bucket.state.bucket}"
    region = "${var.aws_region}"
  EOT
}
