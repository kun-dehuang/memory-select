# AWS Neo4j + Qdrant Deployment

`memory-select` already expects Neo4j and Qdrant through environment variables. This deployment adds a simple AWS-hosted option based on one EC2 instance running both containers.

## Files

- [`infra/aws-ec2-datastores/main.tf`](/Users/myles/Projects/Pupixel/memory-select/infra/aws-ec2-datastores/main.tf)
- [`infra/aws-ec2-datastores/user_data.sh.tftpl`](/Users/myles/Projects/Pupixel/memory-select/infra/aws-ec2-datastores/user_data.sh.tftpl)
- [`infra/aws-ec2-datastores/terraform.tfvars.example`](/Users/myles/Projects/Pupixel/memory-select/infra/aws-ec2-datastores/terraform.tfvars.example)
- [`scripts/deploy-aws-datastores.sh`](/Users/myles/Projects/Pupixel/memory-select/scripts/deploy-aws-datastores.sh)

## Deploy

1. Copy `infra/aws-ec2-datastores/terraform.tfvars.example` to `terraform.tfvars`.
2. Fill in:
   - `subnet_id`
   - `neo4j_password`
   - optionally `qdrant_api_key`
3. Run:

```bash
cd /Users/myles/Projects/Pupixel/memory-select
./scripts/deploy-aws-datastores.sh
```

## App configuration

After `terraform apply`, take the instance private IP and set:

```bash
MEM0_QDRANT_HOST=<private_ip>
MEM0_QDRANT_PORT=6333
MEM0_NEO4J_URI=bolt://<private_ip>:7687
MEM0_NEO4J_USER=neo4j
MEM0_NEO4J_PASSWORD=<neo4j_password>
QDRANT_API_KEY=<qdrant_api_key if enabled>
```

## Access model

- Neo4j Browser: `http://<private_ip>:7474`
- Neo4j Bolt: `bolt://<private_ip>:7687`
- Qdrant REST: `http://<private_ip>:6333`
- Qdrant gRPC: `http://<private_ip>:6334`
- Shell access: `aws ssm start-session --target <instance_id>`

## Scope

- Included: one EC2 host, Docker bootstrap, SSM-stored credentials, private-network access
- Not included: backups, multi-AZ failover, load balancers, public HTTPS, automated snapshots
