# AWS API Deployment

The API-only `memory-select` service is deployed separately from the Neo4j/Qdrant datastore host.

Files:

- [`Dockerfile`](/Users/myles/Projects/Pupixel/memory-select/Dockerfile)
- [`infra/aws-ec2-api/main.tf`](/Users/myles/Projects/Pupixel/memory-select/infra/aws-ec2-api/main.tf)
- [`infra/aws-ec2-api/user_data.sh.tftpl`](/Users/myles/Projects/Pupixel/memory-select/infra/aws-ec2-api/user_data.sh.tftpl)
- [`scripts/release-aws-api.sh`](/Users/myles/Projects/Pupixel/memory-select/scripts/release-aws-api.sh)

Default deployment shape:

- Public EC2 in `subnet-0c6cfe1e9fb812f48`
- Elastic IP attached by Terraform
- API exposed on port `8000`
- App connects privately to:
  - Qdrant `10.60.1.57:6333`
  - Neo4j `bolt://10.60.1.57:7687`
