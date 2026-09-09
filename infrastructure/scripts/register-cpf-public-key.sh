#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/chatbot_cpf_stg_public.pem" >&2
  exit 1
fi

PUBLIC_KEY_PATH="$1"
EXPECTED_ACCOUNT_ID="796575284584"
AWS_REGION="ap-northeast-1"
STACK_NAME="ScholarshipChatbot-stg01-demo"
KID="cpf-chatbot-stg-202609"

actual_account_id="$(aws sts get-caller-identity --query Account --output text)"
if [[ "$actual_account_id" != "$EXPECTED_ACCOUNT_ID" ]]; then
  echo "ERROR: AWS account must be $EXPECTED_ACCOUNT_ID, but current account is $actual_account_id." >&2
  exit 1
fi

if [[ ! -f "$PUBLIC_KEY_PATH" ]]; then
  echo "ERROR: Public key file not found: $PUBLIC_KEY_PATH" >&2
  exit 1
fi
openssl pkey -pubin -in "$PUBLIC_KEY_PATH" -check -noout >/dev/null

secret_name="$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='CpfPublicKeysSecretName'].OutputValue | [0]" \
  --output text)"
if [[ -z "$secret_name" || "$secret_name" == "None" ]]; then
  echo "ERROR: CpfPublicKeysSecretName was not found in stack outputs." >&2
  exit 1
fi

payload_file="$(mktemp)"
trap 'rm -f "$payload_file"' EXIT
node -e 'const fs=require("fs"); const [keyPath,kid,out]=process.argv.slice(1); fs.writeFileSync(out, JSON.stringify({[kid]:fs.readFileSync(keyPath,"utf8")}));' "$PUBLIC_KEY_PATH" "$KID" "$payload_file"
aws secretsmanager put-secret-value \
  --secret-id "$secret_name" \
  --secret-string "file://$payload_file" \
  --region "$AWS_REGION" >/dev/null

cluster_name="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" --query "Stacks[0].Outputs[?OutputKey=='ClusterName'].OutputValue | [0]" --output text)"
backend_service_name="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" --query "Stacks[0].Outputs[?OutputKey=='BackendServiceName'].OutputValue | [0]" --output text)"
aws ecs update-service --cluster "$cluster_name" --service "$backend_service_name" --force-new-deployment --region "$AWS_REGION" >/dev/null
aws ecs wait services-stable --cluster "$cluster_name" --services "$backend_service_name" --region "$AWS_REGION"

echo "CPF public key registered and backend service restarted."
