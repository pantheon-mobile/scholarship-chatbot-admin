#!/usr/bin/env bash
set -Eeuo pipefail

STACK_NAME="${1:?Usage: smoke-test.sh STACK_NAME [REPORT_FILE]}"
REPORT_FILE="${2:-smoke-test-report.md}"
REGION="${AWS_REGION:-ap-northeast-1}"
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

output() {
  aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue | [0]" --output text
}

APPLICATION_URL="$(output ApplicationUrl)"
CLUSTER_NAME="$(output ClusterName)"
FRONTEND_SERVICE="$(output FrontendServiceName)"
BACKEND_SERVICE="$(output BackendServiceName)"
KB_ID="$(output IntegratedKnowledgeBaseId)"

checks=()
check() {
  local label="$1"
  shift
  if "$@"; then checks+=("PASS|$label"); else checks+=("FAIL|$label"); return 1; fi
}

http_ok() { curl --fail --silent --show-error --retry 12 --retry-all-errors --retry-delay 10 "$1" >/dev/null; }
json_status_ok() { curl --fail --silent --show-error --retry 12 --retry-all-errors --retry-delay 10 "$1" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; }

overall=0
check "Frontend page" http_ok "$APPLICATION_URL/development/cpf" || overall=1
check "Backend health and database" json_status_ok "$APPLICATION_URL/api/v1/health" || overall=1
check "Frontend ECS service stable" aws ecs wait services-stable --region "$REGION" --cluster "$CLUSTER_NAME" --services "$FRONTEND_SERVICE" || overall=1
check "Backend ECS service stable" aws ecs wait services-stable --region "$REGION" --cluster "$CLUSTER_NAME" --services "$BACKEND_SERVICE" || overall=1
check "Integrated Knowledge Base available" test "$(aws bedrock-agent get-knowledge-base --region "$REGION" --knowledge-base-id "$KB_ID" --query 'knowledgeBase.status' --output text)" = "ACTIVE" || overall=1

TOKEN="$(curl --fail --silent --show-error -X POST "$APPLICATION_URL/api/v1/auth/development/token" \
  -H 'Content-Type: application/json' \
  -d '{"subject":"rehearsal-admin","display_name":"再現テスト管理者","role":"admin"}' | \
  python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')" || overall=1
if [[ -n "${TOKEN:-}" ]]; then
  check "Development CPF login" curl --fail --silent --show-error -c "$COOKIE_JAR" -X POST \
    "$APPLICATION_URL/api/v1/auth/development/cpf" -H 'Content-Type: application/json' \
    -d "{\"token\":\"$TOKEN\"}" -o /dev/null || overall=1
  check "Authenticated session" curl --fail --silent --show-error -b "$COOKIE_JAR" \
    "$APPLICATION_URL/api/v1/auth/session" -o /dev/null || overall=1
  check "Chat UI configuration" curl --fail --silent --show-error -b "$COOKIE_JAR" \
    "$APPLICATION_URL/api/v1/chat/config" -o /dev/null || overall=1
  check "Chat response pipeline" bash -c '
    response=$(curl --fail --silent --show-error -b "$1" -X POST "$2/api/v1/chat/messages" \
      -H "Content-Type: application/json" -d "{\"question\":\"登録資料に情報がない場合の動作確認です\"}") &&
    python3 -c '\''import json,sys; value=json.load(sys.stdin); assert isinstance(value.get("answer"),str) and value["answer"]'\'' <<<"$response"
  ' _ "$COOKIE_JAR" "$APPLICATION_URL" || overall=1
fi

if [[ -n "${SMOKE_TEST_WEBSITE_URL:-}" && -n "${TOKEN:-}" ]]; then
  WEBSITE_RESPONSE="$(curl --fail --silent --show-error -b "$COOKIE_JAR" \
    -X POST "$APPLICATION_URL/api/v1/data-sources/websites" -H 'Content-Type: application/json' \
    -d "{\"url\":\"$SMOKE_TEST_WEBSITE_URL\",\"title\":\"再現テスト\",\"priority\":\"MEDIUM\",\"answer_source_enabled\":true,\"reference_link_visible\":true}" \
  )" || overall=1
  WEBSITE_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"${WEBSITE_RESPONSE:-{}}" 2>/dev/null || true)"
  if [[ -n "$WEBSITE_ID" ]]; then checks+=("PASS|Register website data source"); else checks+=("FAIL|Register website data source"); overall=1; fi
  check "Start ingestion worker" curl --fail --silent --show-error -b "$COOKIE_JAR" \
    -X POST "$APPLICATION_URL/api/v1/data-sources/ingestion/run-now" -o /dev/null || overall=1
  if [[ -n "$WEBSITE_ID" ]]; then
    ingestion_status=""
    for _ in {1..90}; do
      ingestion_status="$(curl --fail --silent --show-error -b "$COOKIE_JAR" \
        "$APPLICATION_URL/api/v1/data-sources/$WEBSITE_ID" | \
        python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])' 2>/dev/null || true)"
      [[ "$ingestion_status" == "AVAILABLE" || "$ingestion_status" == "ERROR" ]] && break
      sleep 20
    done
    if [[ "$ingestion_status" == "AVAILABLE" ]]; then
      checks+=("PASS|Website conversion and Knowledge Base synchronization")
    else
      checks+=("FAIL|Website conversion and Knowledge Base synchronization ($ingestion_status)")
      overall=1
    fi
  fi
fi

{
  echo "# Pre-handoff rehearsal report"
  echo
  echo "- Stack: \`$STACK_NAME\`"
  echo "- Region: \`$REGION\`"
  echo "- Application: $APPLICATION_URL"
  echo "- Executed at: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  echo
  echo "| Result | Check |"
  echo "|---|---|"
  for item in "${checks[@]}"; do
    echo "| ${item%%|*} | ${item#*|} |"
  done
} > "$REPORT_FILE"

cat "$REPORT_FILE"
exit "$overall"
