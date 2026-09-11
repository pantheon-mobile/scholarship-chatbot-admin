#!/usr/bin/env bash
set -euo pipefail

EXPECTED_ACCOUNT_ID="796575284584"
AWS_REGION="ap-northeast-1"
export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"
STACK_NAME="ScholarshipChatbot-stg01-demo"
CONFIG_PATH="config/customer-validation.json"
LISTENER_ARN="arn:aws:elasticloadbalancing:ap-northeast-1:796575284584:listener/app/gakupita-stg-web-fargate-alb/ea893fe54fc88e36/ecef481f0bab2efd"

actual_account_id="$(aws sts get-caller-identity --query Account --output text)"
if [[ "$actual_account_id" != "$EXPECTED_ACCOUNT_ID" ]]; then
  echo "ERROR: AWS account must be $EXPECTED_ACCOUNT_ID, but current account is $actual_account_id." >&2
  exit 1
fi

# 初回構築時だけ、既存ALBの優先順位競合を事前確認します。既存スタックの
# 再デプロイ時は、そのスタック自身が1001/1002を使用しているため確認不要です。
if ! aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
  used_priorities="$(aws elbv2 describe-rules --listener-arn "$LISTENER_ARN" --region "$AWS_REGION" --query 'Rules[].Priority' --output text)"
  for priority in 1001 1002; do
    if [[ " $used_priorities " == *" $priority "* ]]; then
      echo "ERROR: ALB listener rule priority $priority is already in use." >&2
      exit 1
    fi
  done
fi

chat_model_arn="${CHAT_MODEL_ARN:-}"
if [[ -z "$chat_model_arn" ]]; then
  chat_model_arn="$(aws bedrock list-inference-profiles \
    --region "$AWS_REGION" \
    --type-equals SYSTEM_DEFINED \
    --query "inferenceProfileSummaries[?contains(inferenceProfileName, 'Claude Sonnet 4.6')].inferenceProfileArn | [0]" \
    --output text)"
fi
if [[ -z "$chat_model_arn" || "$chat_model_arn" == "None" ]]; then
  echo "ERROR: Claude Sonnet 4.6 inference profile was not found. Set CHAT_MODEL_ARN and retry." >&2
  exit 1
fi

npm ci
npm run build
npx cdk deploy "$STACK_NAME" \
  --context "config=$CONFIG_PATH" \
  --parameters "ChatModelArn=$chat_model_arn" \
  --parameters "CpfFacultyReturnUrl=https://cpf-stg01-demo.gakupita.com/faculty/" \
  --parameters "CpfStudentReturnUrl=" \
  --require-approval never

echo "Deployment completed. Configure DNS for ai-chatbot-stg01-demo.gakupita.com and register the CPF public key next."
