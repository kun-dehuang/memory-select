# AWS EC2 API Deployment

This stack deploys the API-only `memory-select` service as a Docker container on one EC2 instance in `ap-southeast-1`.

## What gets created

- 1 ECR repository
- 1 EC2 instance
- 1 Elastic IP by default
- 1 security group exposing `8000/tcp`
- 1 SSM SecureString parameter for `GEMINI_API_KEY`
- 1 CloudWatch log group

The instance reads the Neo4j and Qdrant secrets from the existing datastore parameters:

- `/memory-select-datastores/neo4j_password`
- `/memory-select-datastores/qdrant_api_key`

## Quick start

```bash
cd /Users/myles/Projects/Pupixel/memory-select
GEMINI_API_KEY=... ./scripts/release-aws-api.sh
```
