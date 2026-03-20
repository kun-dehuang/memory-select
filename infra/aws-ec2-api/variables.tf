variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "ap-southeast-1"
}

variable "project_name" {
  description = "Resource name prefix."
  type        = string
  default     = "memory-select-api"
}

variable "vpc_id" {
  description = "Target VPC for the EC2 instance."
  type        = string
  default     = "vpc-068084567e406f9f3"
}

variable "subnet_id" {
  description = "Public subnet for the API instance."
  type        = string
  default     = "subnet-0c6cfe1e9fb812f48"
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to reach the public API."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "additional_security_group_ids" {
  description = "Additional security groups to attach for manual rules."
  type        = list(string)
  default     = []
}

variable "shared_vpc_endpoint_security_group_ids" {
  description = "Shared interface VPC endpoint security groups that must allow this API instance on port 443."
  type        = list(string)
  default     = ["sg-08af6d959c37e7aeb"]
}

variable "instance_type" {
  description = "EC2 instance type."
  type        = string
  default     = "t3.small"
}

variable "ami_id" {
  description = "Pinned Amazon Linux 2023 AMI ID for the EC2 instance."
  type        = string
  default     = "ami-011d19742f14ff9b8"
}

variable "associate_public_ip_address" {
  description = "Whether to assign a public IP to the instance."
  type        = bool
  default     = true
}

variable "allocate_eip" {
  description = "Whether to allocate an Elastic IP for the API instance."
  type        = bool
  default     = true
}

variable "app_port" {
  description = "Container and host port for the API."
  type        = number
  default     = 8000
}

variable "image_tag" {
  description = "Docker image tag to deploy."
  type        = string
  default     = "latest"
}

variable "gemini_api_key" {
  description = "Gemini API key stored in SSM Parameter Store."
  type        = string
  sensitive   = true
}

variable "mem0_qdrant_host" {
  description = "Qdrant host for mem0."
  type        = string
  default     = "10.60.1.57"
}

variable "mem0_qdrant_port" {
  description = "Qdrant port for mem0."
  type        = string
  default     = "6333"
}

variable "qdrant_https" {
  description = "Whether the Qdrant URL should be treated as HTTPS when using an API key."
  type        = bool
  default     = false
}

variable "mem0_neo4j_uri" {
  description = "Neo4j Bolt URI for mem0."
  type        = string
  default     = "bolt://10.60.1.57:7687"
}

variable "mem0_neo4j_user" {
  description = "Neo4j username for mem0."
  type        = string
  default     = "neo4j"
}

variable "neo4j_password_parameter_name" {
  description = "Existing SSM parameter name for the Neo4j password."
  type        = string
  default     = "/memory-select-datastores/neo4j_password"
}

variable "qdrant_api_key_parameter_name" {
  description = "Existing SSM parameter name for the Qdrant API key."
  type        = string
  default     = "/memory-select-datastores/qdrant_api_key"
}

variable "root_volume_size" {
  description = "Root EBS volume size in GiB."
  type        = number
  default     = 30
}

variable "log_retention_days" {
  description = "CloudWatch log retention for container logs."
  type        = number
  default     = 14
}

variable "tags" {
  description = "Additional tags applied to all resources."
  type        = map(string)
  default     = {}
}
