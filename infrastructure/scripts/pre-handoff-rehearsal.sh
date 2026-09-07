#!/usr/bin/env bash
set -Eeuo pipefail

CONFIG_FILE="${CONFIG_FILE:-config/rehearsal.json}"
CHAT_MODEL_ARN="${CHAT_MODEL_ARN:?Set CHAT_MODEL_ARN to the Claude Sonnet inference profile ARN}"
REGION="${AWS_REGION:-ap-northeast-1}"
DESTROY_AFTER_TEST="${DESTROY_AFTER_TEST:-false}"
REPORT_FILE="${REPORT_FILE:-pre-handoff-rehearsal-report.md}"

ENVIRONMENT_NAME="$(node -e 'const c=require("./'"$CONFIG_FILE"'"); process.stdout.write(c.environmentName)')"
STACK_NAME="ScholarshipChatbot-$ENVIRONMENT_NAME"
export AWS_REGION="$REGION"
export AWS_DEFAULT_REGION="$REGION"
export CDK_DEFAULT_REGION="$REGION"

npm ci
npm run build
npx cdk synth --context "config=$CONFIG_FILE"
npx cdk deploy "$STACK_NAME" --require-approval never --context "config=$CONFIG_FILE" \
  --parameters "ChatModelArn=$CHAT_MODEL_ARN" \
  --parameters "CpfFacultyReturnUrl=${CPF_FACULTY_RETURN_URL:-}" \
  --parameters "CpfStudentReturnUrl=${CPF_STUDENT_RETURN_URL:-}"

test_result=0
AWS_REGION="$REGION" ./scripts/smoke-test.sh "$STACK_NAME" "$REPORT_FILE" || test_result=$?

if [[ "$DESTROY_AFTER_TEST" == "true" ]]; then
  npx cdk destroy "$STACK_NAME" --force --context "config=$CONFIG_FILE"
fi

exit "$test_result"
