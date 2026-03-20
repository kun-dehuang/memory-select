provider "aws" {
  region = var.aws_region
}

locals {
  common_tags              = merge(var.tags, { Project = var.project_name, ManagedBy = "terraform" })
  neo4j_password_parameter = "/${var.project_name}/neo4j_password"
  qdrant_api_key_parameter = "/${var.project_name}/qdrant_api_key"
  readable_qdrant_api_key  = var.qdrant_api_key != ""
  parameter_arns_for_instance = concat(
    [aws_ssm_parameter.neo4j_password.arn],
    local.readable_qdrant_api_key ? [aws_ssm_parameter.qdrant_api_key[0].arn] : []
  )
}

resource "aws_ssm_parameter" "neo4j_password" {
  name        = local.neo4j_password_parameter
  description = "Neo4j password for ${var.project_name}"
  type        = "SecureString"
  value       = var.neo4j_password
  tags        = local.common_tags
}

resource "aws_ssm_parameter" "qdrant_api_key" {
  count       = local.readable_qdrant_api_key ? 1 : 0
  name        = local.qdrant_api_key_parameter
  description = "Qdrant API key for ${var.project_name}"
  type        = "SecureString"
  value       = var.qdrant_api_key
  tags        = local.common_tags
}

resource "aws_iam_role" "app" {
  name = "${var.project_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.app.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "instance" {
  name = "${var.project_name}-ec2-inline"
  role = aws_iam_role.app.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadDatastoreSecrets"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter"
        ]
        Resource = local.parameter_arns_for_instance
      }
    ]
  })
}

resource "aws_iam_instance_profile" "app" {
  name = "${var.project_name}-instance-profile"
  role = aws_iam_role.app.name
  tags = local.common_tags
}

resource "aws_security_group" "app" {
  name        = "${var.project_name}-sg"
  description = "Allow VPC-internal access to Neo4j and Qdrant"
  vpc_id      = var.vpc_id

  ingress {
    description = "Neo4j HTTP"
    from_port   = var.neo4j_http_port
    to_port     = var.neo4j_http_port
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  ingress {
    description = "Neo4j Bolt"
    from_port   = var.neo4j_bolt_port
    to_port     = var.neo4j_bolt_port
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  ingress {
    description = "Qdrant HTTP"
    from_port   = var.qdrant_http_port
    to_port     = var.qdrant_http_port
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  ingress {
    description = "Qdrant gRPC"
    from_port   = var.qdrant_grpc_port
    to_port     = var.qdrant_grpc_port
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

resource "aws_instance" "datastores" {
  ami                         = var.ami_id
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = concat([aws_security_group.app.id], var.additional_security_group_ids)
  iam_instance_profile        = aws_iam_instance_profile.app.name
  associate_public_ip_address = var.associate_public_ip_address
  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    aws_region               = var.aws_region
    project_name             = var.project_name
    neo4j_http_port          = var.neo4j_http_port
    neo4j_bolt_port          = var.neo4j_bolt_port
    qdrant_http_port         = var.qdrant_http_port
    qdrant_grpc_port         = var.qdrant_grpc_port
    neo4j_password_parameter = aws_ssm_parameter.neo4j_password.name
    qdrant_api_key_parameter = local.readable_qdrant_api_key ? aws_ssm_parameter.qdrant_api_key[0].name : ""
  })

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  root_block_device {
    volume_size = var.root_volume_size
    encrypted   = true
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-ec2"
  })
}
