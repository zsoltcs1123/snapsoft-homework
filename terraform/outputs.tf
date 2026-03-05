output "landing_bucket_name" {
  description = "Name of the landing zone S3 bucket"
  value       = aws_s3_bucket.landing.id
}

output "curated_bucket_name" {
  description = "Name of the curated zone S3 bucket"
  value       = aws_s3_bucket.curated.id
}

output "lambda_function_name" {
  description = "Name of the preprocessing Lambda function"
  value       = aws_lambda_function.preprocess.function_name
}

output "lambda_function_arn" {
  description = "ARN of the preprocessing Lambda function"
  value       = aws_lambda_function.preprocess.arn
}
