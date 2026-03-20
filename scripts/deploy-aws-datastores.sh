#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(cd "${SCRIPT_DIR}/../infra/aws-ec2-datastores" && pwd)"
TF_VARS_FILE="${TF_VARS_FILE:-${INFRA_DIR}/terraform.tfvars}"

if ! command -v terraform >/dev/null 2>&1; then
  echo "Missing required command: terraform" >&2
  exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "Missing required command: aws" >&2
  exit 1
fi

if [[ ! -f "${TF_VARS_FILE}" ]]; then
  echo "Missing tfvars file: ${TF_VARS_FILE}" >&2
  exit 1
fi

terraform -chdir="${INFRA_DIR}" init -input=false
terraform -chdir="${INFRA_DIR}" apply -input=false -var-file="${TF_VARS_FILE}"
