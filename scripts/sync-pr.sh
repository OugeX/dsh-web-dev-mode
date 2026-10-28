#!/usr/bin/env bash
# 同步市场 PR 的包装脚本（调用同目录的 sync-pr.py）
#
#   ./scripts/sync-pr.sh --check    检查差异
#   ./scripts/sync-pr.sh            执行同步
#
# 需要 GH_TOKEN 环境变量。
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done

if [ -z "$PY" ]; then
  echo "错误：找不到 python（试过 python3 / python / py）" >&2
  exit 2
fi

exec "$PY" "$DIR/sync-pr.py" "$@"
