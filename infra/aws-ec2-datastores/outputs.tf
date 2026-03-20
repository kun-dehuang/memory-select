output "instance_id" {
  description = "EC2 instance ID for Neo4j and Qdrant."
  value       = aws_instance.datastores.id
}

output "private_ip" {
  description = "Private IP address of the EC2 instance."
  value       = aws_instance.datastores.private_ip
}

output "public_ip" {
  description = "Public IP address of the EC2 instance when enabled."
  value       = aws_instance.datastores.public_ip
}

output "neo4j_browser_url" {
  description = "Neo4j Browser URL."
  value       = "http://${aws_instance.datastores.private_ip}:${var.neo4j_http_port}"
}

output "neo4j_bolt_uri" {
  description = "Neo4j Bolt URI."
  value       = "bolt://${aws_instance.datastores.private_ip}:${var.neo4j_bolt_port}"
}

output "qdrant_http_url" {
  description = "Qdrant HTTP URL."
  value       = "http://${aws_instance.datastores.private_ip}:${var.qdrant_http_port}"
}

output "ssm_start_session_command" {
  description = "Helper command to start an SSM shell session."
  value       = "aws ssm start-session --region ${var.aws_region} --target ${aws_instance.datastores.id}"
}
