#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
INFRA_DIR="${APP_DIR}/infra/aws-ec2-api"

AWS_REGION="${AWS_REGION:-ap-southeast-1}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
PROJECT_NAME="${PROJECT_NAME:-memory-select-api}"
REPOSITORY_NAME="${REPOSITORY_NAME:-${PROJECT_NAME}}"
TF_VARS_FILE="${TF_VARS_FILE:-${INFRA_DIR}/terraform.tfvars}"
APP_SERVICE_NAME="${PROJECT_NAME}"

for required_cmd in aws docker terraform; do
  if ! command -v "${required_cmd}" >/dev/null 2>&1; then
    echo "Missing required command: ${required_cmd}" >&2
    exit 1
  fi
done

if [[ -z "${GEMINI_API_KEY:-}" && -f "${APP_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${APP_DIR}/.env"
  set +a
fi

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  echo "GEMINI_API_KEY is required" >&2
  exit 1
fi

export AWS_REGION AWS_DEFAULT_REGION TF_IN_AUTOMATION=1

if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]]; then
  AWS_CREDENTIALS="$(
    aws configure export-credentials --format env-no-export 2>/dev/null || true
  )"
  if [[ -n "${AWS_CREDENTIALS}" ]]; then
    eval "$(printf '%s\n' "${AWS_CREDENTIALS}" | sed 's/^/export /')"
  fi
fi

terraform -chdir="${INFRA_DIR}" init -input=false

terraform_apply() {
  local -a cmd=(terraform -chdir="${INFRA_DIR}" apply -input=false -auto-approve)
  if [[ -f "${TF_VARS_FILE}" ]]; then
    cmd+=(-var-file="${TF_VARS_FILE}")
  fi
  cmd+=("$@")
  "${cmd[@]}"
}

terraform_output() {
  terraform -chdir="${INFRA_DIR}" output -raw "$1" 2>/dev/null || true
}

wait_for_ssm_online() {
  local instance_id="$1"

  for _ in $(seq 1 60); do
    if aws ssm describe-instance-information \
      --region "${AWS_REGION}" \
      --filters "Key=InstanceIds,Values=${instance_id}" \
      --query 'InstanceInformationList[0].PingStatus' \
      --output text 2>/dev/null | grep -q '^Online$'; then
      return 0
    fi
    sleep 10
  done

  return 1
}

wait_for_bootstrap_ready() {
  local instance_id="$1"
  local command_id=""

  command_id="$(
    aws ssm send-command \
      --region "${AWS_REGION}" \
      --instance-ids "${instance_id}" \
      --document-name "AWS-RunShellScript" \
      --comment "Wait for cloud-init bootstrap" \
      --parameters '{"commands":["cloud-init status --wait"]}' \
      --query "Command.CommandId" \
      --output text
  )"

  aws ssm wait command-executed \
    --region "${AWS_REGION}" \
    --command-id "${command_id}" \
    --instance-id "${instance_id}"
}

run_deploy_command() {
  local instance_id="$1"
  local image_tag="$2"
  local command_id=""
  local status=""
  local invocation=""

  command_id="$(
    aws ssm send-command \
      --region "${AWS_REGION}" \
      --instance-ids "${instance_id}" \
      --document-name "AWS-RunShellScript" \
      --comment "Deploy ${REPOSITORY_NAME}:${image_tag}" \
      --parameters "{\"commands\":[\"sudo /opt/${APP_SERVICE_NAME}/bin/deploy.sh ${image_tag}\"]}" \
      --query "Command.CommandId" \
      --output text
  )"

  aws ssm wait command-executed \
    --region "${AWS_REGION}" \
    --command-id "${command_id}" \
    --instance-id "${instance_id}" >/dev/null 2>&1

  invocation="$(
    aws ssm get-command-invocation \
      --region "${AWS_REGION}" \
      --command-id "${command_id}" \
      --instance-id "${instance_id}" \
      --query "{Status:Status,StandardOutputContent:StandardOutputContent,StandardErrorContent:StandardErrorContent}"
  )"

  status="$(
    aws ssm get-command-invocation \
      --region "${AWS_REGION}" \
      --command-id "${command_id}" \
      --instance-id "${instance_id}" \
      --query "Status" \
      --output text
  )"

  printf '%s\n' "${invocation}"

  if [[ "${status}" != "Success" ]]; then
    return 1
  fi
}

wait_for_service_script() {
  local instance_id="$1"
  local command_id=""
  local status=""

  command_id="$(
    aws ssm send-command \
      --region "${AWS_REGION}" \
      --instance-ids "${instance_id}" \
      --document-name "AWS-RunShellScript" \
      --comment "Wait for deploy script" \
      --parameters "{\"commands\":[\"for i in $(seq 1 60); do if [ -x /opt/${APP_SERVICE_NAME}/bin/deploy.sh ]; then exit 0; fi; sleep 5; done; exit 1\"]}" \
      --query "Command.CommandId" \
      --output text
  )"

  aws ssm wait command-executed \
    --region "${AWS_REGION}" \
    --command-id "${command_id}" \
    --instance-id "${instance_id}" >/dev/null 2>&1

  status="$(
    aws ssm get-command-invocation \
      --region "${AWS_REGION}" \
      --command-id "${command_id}" \
      --instance-id "${instance_id}" \
      --query "Status" \
      --output text
  )"

  [[ "${status}" == "Success" ]]
}

if ! aws ecr describe-repositories --region "${AWS_REGION}" --repository-names "${REPOSITORY_NAME}" >/dev/null 2>&1; then
  terraform_apply \
    -var="aws_region=${AWS_REGION}" \
    -var="project_name=${PROJECT_NAME}" \
    -var="gemini_api_key=${GEMINI_API_KEY}" \
    -var="image_tag=${IMAGE_TAG}" \
    -target=aws_ecr_repository.app
fi

ECR_REPOSITORY_URL="$(terraform_output ecr_repository_url)"
if [[ -z "${ECR_REPOSITORY_URL}" ]]; then
  ACCOUNT_ID="$(aws sts get-caller-identity --query 'Account' --output text)"
  ECR_REPOSITORY_URL="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPOSITORY_NAME}"
fi

IMAGE_URI="${ECR_REPOSITORY_URL}:${IMAGE_TAG}"

aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "$(printf '%s' "${ECR_REPOSITORY_URL}" | cut -d/ -f1)"
docker buildx build --platform linux/amd64 --load -t "${IMAGE_URI}" "${APP_DIR}"
docker push "${IMAGE_URI}"

terraform_apply \
  -var="aws_region=${AWS_REGION}" \
  -var="project_name=${PROJECT_NAME}" \
  -var="gemini_api_key=${GEMINI_API_KEY}" \
  -var="image_tag=${IMAGE_TAG}"

INSTANCE_ID="$(terraform_output instance_id)"
API_URL="$(terraform_output api_url)"

if [[ -z "${INSTANCE_ID}" ]]; then
  echo "Failed to determine instance_id from Terraform outputs" >&2
  exit 1
fi

wait_for_ssm_online "${INSTANCE_ID}"
wait_for_service_script "${INSTANCE_ID}"
wait_for_bootstrap_ready "${INSTANCE_ID}"
run_deploy_command "${INSTANCE_ID}" "${IMAGE_TAG}"

echo
echo "Memory API deployed"
echo "  instance_id: ${INSTANCE_ID}"
echo "  image_uri:   ${IMAGE_URI}"
echo "  api_url:     ${API_URL}"
