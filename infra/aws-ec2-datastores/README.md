# AWS EC2 Datastores

This stack creates a single EC2 instance in `ap-southeast-1` and runs:

- `Neo4j` on ports `7474` and `7687`
- `Qdrant` on ports `6333` and `6334`

The host is intended to live inside the VPC and be accessed over private networking or AWS Systems Manager.

## What Terraform manages

- 1 EC2 instance with Docker
- 1 security group scoped to the CIDRs in `allowed_cidr_blocks`
- 1 IAM role and instance profile for Systems Manager and Parameter Store reads
- 1 SSM SecureString parameter for the Neo4j password
- 0 or 1 SSM SecureString parameter for the Qdrant API key

## Quick start

1. Copy `terraform.tfvars.example` to `terraform.tfvars`.
2. Set `subnet_id` and the datastore secrets.
3. Run:

```bash
cd /Users/myles/Projects/Pupixel/memory-select/infra/aws-ec2-datastores
terraform init
terraform apply
```

## Outputs to wire into `memory-select`

- `MEM0_QDRANT_HOST=<private_ip>`
- `MEM0_QDRANT_PORT=6333`
- `QDRANT_API_KEY=<same value as qdrant_api_key>` if you enabled it
- `MEM0_NEO4J_URI=bolt://<private_ip>:7687`
- `MEM0_NEO4J_USER=neo4j`
- `MEM0_NEO4J_PASSWORD=<same value as neo4j_password>`

## Notes

- Persistence lives on the instance root EBS volume, so avoid replacing the instance casually.
- Default ingress is limited to `10.60.0.0/16`.
- The instance is private by default. Use `aws ssm start-session` for shell access.
