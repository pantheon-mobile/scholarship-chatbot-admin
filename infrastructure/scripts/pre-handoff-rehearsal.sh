#!/usr/bin/env bash
set -Eeuo pipefail

CONFIG_FILE="${CONFIG_FILE:-config/rehearsal.json}"
CHAT_MODEL_ARN="${CHAT_MODEL_ARN:?Set CHAT_MODEL_ARN to the Claude Sonnet inference profile ARN}"
REGION="${AWS_REGION:-ap-northeast-1}"
DESTROY_AFTER_TEST="${DESTROY_AFTER_TEST:-false}"
REPORT_FILE="${REPORT_FILE:-pre-handoff-rehearsal-report.md}"

ENVIRONMENT_NAME="$(node -e 'const fs=require("fs"); const c=JSON.parse(fs.readFileSync(process.argv[1],"utf8")); process.stdout.write(c.environmentName)' "$CONFIG_FILE")"
if [[ ! "$ENVIRONMENT_NAME" =~ ^rehearsal-[a-z0-9][a-z0-9-]{0,30}$ ]]; then
  echo "Use a new environment name beginning with rehearsal-" >&2
  exit 1
fi
STACK_NAME="ScholarshipChatbot-$ENVIRONMENT_NAME"
export AWS_REGION="$REGION"
export AWS_DEFAULT_REGION="$REGION"
export CDK_DEFAULT_REGION="$REGION"

# List must succeed; do not mistake expired credentials/AccessDenied for absence.
existing="$(aws cloudformation list-stacks --region "$REGION" --output json)"
collision="$(STACK_TO_CREATE="$STACK_NAME" python3 -c 'import json,os,sys; entries=json.load(sys.stdin)["StackSummaries"]; print("yes" if any(s["StackName"]==os.environ["STACK_TO_CREATE"] and s["StackStatus"]!="DELETE_COMPLETE" for s in entries) else "no")' <<< "$existing")"
if [[ "$collision" == "yes" ]]; then
  echo "Refusing to overwrite an existing stack: $STACK_NAME" >&2
  exit 1
fi

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
