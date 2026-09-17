#!/usr/bin/env bash
set -Eeuo pipefail
exec "${BASELINE_PYTHON:-python3}" "$(dirname "$0")/validation_baseline.py" restore "$@"
