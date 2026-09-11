#!/usr/bin/env bash
set -Eeuo pipefail

EXPECTED_ACCOUNT_ID="180162572038"
AWS_REGION="ap-northeast-1"
STACK_NAME="ScholarshipChatbot-development"
CONFIG_PATH="config/development-ci.json"
export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"

actual_account_id="$(aws sts get-caller-identity --query Account --output text)"
if [[ "$actual_account_id" != "$EXPECTED_ACCOUNT_ID" ]]; then
  echo "ERROR: AWS account must be $EXPECTED_ACCOUNT_ID, but current account is $actual_account_id." >&2
  exit 1
fi

if ! aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$STACK_NAME" >/dev/null 2>&1; then
  echo "ERROR: Existing development stack $STACK_NAME was not found." >&2
  echo "Run the documented initial deployment before enabling continuous deployment." >&2
  exit 1
fi

stack_parameter() {
  aws cloudformation describe-stacks \
    --region "$AWS_REGION" \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Parameters[?ParameterKey=='$1'].ParameterValue | [0]" \
    --output text
}

required_parameters=(
  ChatModelArn ChatKnowledgeBaseId
  PDFKnowledgeBaseId PDFDataSourceId
  WEBKnowledgeBaseId WEBDataSourceId
  EXCELKnowledgeBaseId EXCELDataSourceId
  WORDKnowledgeBaseId WORDDataSourceId
  PPTKnowledgeBaseId PPTDataSourceId
)
deploy_parameters=()
for key in "${required_parameters[@]}"; do
  value="$(stack_parameter "$key")"
  if [[ -z "$value" || "$value" == "None" ]]; then
    echo "ERROR: CloudFormation parameter $key is not configured in $STACK_NAME." >&2
    exit 1
  fi
  deploy_parameters+=(--parameters "$key=$value")
done

# Older development stacks predate the explicit TEXT parameters. Plain text and
# CSV intentionally share the PDF Knowledge Base/Data Source in that layout.
text_knowledge_base_id="$(stack_parameter TEXTKnowledgeBaseId)"
text_data_source_id="$(stack_parameter TEXTDataSourceId)"
if [[ -z "$text_knowledge_base_id" || "$text_knowledge_base_id" == "None" ]]; then
  text_knowledge_base_id="$(stack_parameter PDFKnowledgeBaseId)"
fi
if [[ -z "$text_data_source_id" || "$text_data_source_id" == "None" ]]; then
  text_data_source_id="$(stack_parameter PDFDataSourceId)"
fi
deploy_parameters+=(
  --parameters "TEXTKnowledgeBaseId=$text_knowledge_base_id"
  --parameters "TEXTDataSourceId=$text_data_source_id"
)

for key in CpfFacultyReturnUrl CpfStudentReturnUrl; do
  value="$(stack_parameter "$key")"
  [[ "$value" == "None" ]] && value=""
  deploy_parameters+=(--parameters "$key=$value")
done

npm ci
npm run build
npx cdk deploy "$STACK_NAME" \
  --context "config=$CONFIG_PATH" \
  "${deploy_parameters[@]}" \
  --require-approval never
