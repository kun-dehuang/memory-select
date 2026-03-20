variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "ap-southeast-1"
}

variable "project_name" {
  description = "Resource name prefix."
  type        = string
  default     = "memory-select-datastores"
}

variable "vpc_id" {
  description = "Target VPC for the EC2 instance."
  type        = string
  default     = "vpc-068084567e406f9f3"
}

variable "subnet_id" {
  description = "Subnet ID for the EC2 instance."
  type        = string
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to reach Neo4j and Qdrant."
  type        = list(string)
  default     = ["10.60.0.0/16"]
}

variable "additional_security_group_ids" {
  description = "Additional security groups to attach for manual rules."
  type        = list(string)
  default     = []
}

variable "instance_type" {
  description = "EC2 instance type."
  type        = string
  default     = "t3.large"
}

variable "ami_id" {
  description = "Pinned Amazon Linux 2023 AMI ID for the EC2 instance."
  type        = string
  default     = "ami-011d19742f14ff9b8"
}

variable "associate_public_ip_address" {
  description = "Whether to assign a public IP to the instance."
  type        = bool
  default     = false
}

variable "root_volume_size" {
  description = "Root EBS volume size in GiB."
  type        = number
  default     = 80
}

variable "neo4j_password" {
  description = "Neo4j password stored in SSM Parameter Store."
  type        = string
  sensitive   = true
}

variable "qdrant_api_key" {
  description = "Optional Qdrant API key stored in SSM Parameter Store."
  type        = string
  sensitive   = true
  default     = ""
}

variable "neo4j_http_port" {
  description = "Neo4j HTTP port."
  type        = number
  default     = 7474
}

variable "neo4j_bolt_port" {
  description = "Neo4j Bolt port."
  type        = number
  default     = 7687
}

variable "qdrant_http_port" {
  description = "Qdrant HTTP port."
  type        = number
  default     = 6333
}

variable "qdrant_grpc_port" {
  description = "Qdrant gRPC port."
  type        = number
  default     = 6334
}

variable "tags" {
  description = "Additional tags applied to all resources."
  type        = map(string)
  default     = {}
}
