provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

locals {
  common_tags                  = merge(var.tags, { Project = var.project_name, ManagedBy = "terraform" })
  log_group_name               = "/ec2/${var.project_name}"
  ecr_registry                 = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"
  image_uri                    = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
  gemini_parameter_name        = "/${var.project_name}/GEMINI_API_KEY"
  neo4j_password_parameter_arn = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/${trimprefix(var.neo4j_password_parameter_name, "/")}"
  qdrant_api_key_parameter_arn = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/${trimprefix(var.qdrant_api_key_parameter_name, "/")}"
}

resource "aws_ecr_repository" "app" {
  name                 = var.project_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "app" {
  name              = local.log_group_name
  retention_in_days = var.log_retention_days
  tags              = local.common_tags
}

resource "aws_ssm_parameter" "gemini_api_key" {
  name        = local.gemini_parameter_name
  description = "Gemini API key for ${var.project_name}"
  type        = "SecureString"
  value       = var.gemini_api_key
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

resource "aws_iam_role_policy" "app" {
  name = "${var.project_name}-ec2-inline"
  role = aws_iam_role.app.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadAppSecrets"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter"
        ]
        Resource = [
          aws_ssm_parameter.gemini_api_key.arn,
          local.neo4j_password_parameter_arn,
          local.qdrant_api_key_parameter_arn
        ]
      },
      {
        Sid    = "PullFromEcr"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      },
      {
        Sid    = "WriteAppLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "${aws_cloudwatch_log_group.app.arn}:*"
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
  description = "Allow public access to ${var.project_name}"
  vpc_id      = var.vpc_id

  ingress {
    description = "Memory API"
    from_port   = var.app_port
    to_port     = var.app_port
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

resource "aws_security_group_rule" "allow_app_to_shared_vpc_endpoints" {
  for_each = toset(var.shared_vpc_endpoint_security_group_ids)

  type                     = "ingress"
  description              = "Allow ${var.project_name} to reach shared VPC endpoints over HTTPS"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  security_group_id        = each.value
  source_security_group_id = aws_security_group.app.id
}

resource "aws_instance" "app" {
  ami                         = var.ami_id
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = concat([aws_security_group.app.id], var.additional_security_group_ids)
  iam_instance_profile        = aws_iam_instance_profile.app.name
  associate_public_ip_address = var.associate_public_ip_address
  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    aws_region               = var.aws_region
    app_port                 = var.app_port
    project_name             = var.project_name
    ecr_registry             = local.ecr_registry
    ecr_repository_url       = aws_ecr_repository.app.repository_url
    gemini_parameter         = aws_ssm_parameter.gemini_api_key.name
    neo4j_password_parameter = var.neo4j_password_parameter_name
    qdrant_api_key_parameter = var.qdrant_api_key_parameter_name
    image_tag                = var.image_tag
    log_group_name           = aws_cloudwatch_log_group.app.name
    mem0_qdrant_host         = var.mem0_qdrant_host
    mem0_qdrant_port         = var.mem0_qdrant_port
    qdrant_https             = tostring(var.qdrant_https)
    mem0_neo4j_uri           = var.mem0_neo4j_uri
    mem0_neo4j_user          = var.mem0_neo4j_user
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

resource "aws_eip" "app" {
  count    = var.allocate_eip ? 1 : 0
  domain   = "vpc"
  instance = aws_instance.app.id

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-eip"
  })
}
