output "bucket_name" {
  description = "Nome do bucket do data lake."
  value       = aws_s3_bucket.lake.bucket
}

output "bucket_arn" {
  description = "ARN do bucket, usado nas policies de IAM."
  value       = aws_s3_bucket.lake.arn
}