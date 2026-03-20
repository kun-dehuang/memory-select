output "instance_id" {
  description = "EC2 instance ID for the Memory API."
  value       = aws_instance.app.id
}

output "private_ip" {
  description = "Private IP address of the EC2 instance."
  value       = aws_instance.app.private_ip
}

output "public_ip" {
  description = "Public IP address of the EC2 instance."
  value       = var.allocate_eip ? aws_eip.app[0].public_ip : aws_instance.app.public_ip
}

output "api_url" {
  description = "Public API URL."
  value       = "http://${var.allocate_eip ? aws_eip.app[0].public_ip : aws_instance.app.public_ip}:${var.app_port}"
}

output "ssm_start_session_command" {
  description = "Helper command to start an SSM shell session."
  value       = "aws ssm start-session --region ${var.aws_region} --target ${aws_instance.app.id}"
}

output "ecr_repository_url" {
  description = "ECR repository URL for Docker image pushes."
  value       = aws_ecr_repository.app.repository_url
}
