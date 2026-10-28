#!/usr/bin/env bash
# DSH Web Dev Mode · 一键安装（Linux / macOS / Git Bash on Windows）
set -euo pipefail

DSH_HOME="${DSH_HOME:-$HOME/.dsh}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "▶ 安装目标：$DSH_HOME"

if [ ! -d "$DSH_HOME" ]; then
  echo "❌ 找不到 $DSH_HOME"
  echo "   请先安装 DSH 并至少运行一次，或用 DSH_HOME=/your/path bash install.sh 指定"
  exit 1
fi

mkdir -p "$DSH_HOME/.agent-presets" "$DSH_HOME/skills"

# ── 1. preset（含备份）────────────────────────────────────────────
PRESET_DST="$DSH_HOME/.agent-presets/web-dev"
if [ -d "$PRESET_DST" ]; then
  BAK="$PRESET_DST.bak.$(date +%s)"
  mv "$PRESET_DST" "$BAK"
  echo "  已备份原 preset → $BAK"
fi
cp -r "$SRC/presets/web-dev" "$PRESET_DST"
echo "▶ preset 已安装"

# ── 2. skills ────────────────────────────────────────────────────
count=0
for d in "$SRC"/skills/*/; do
  [ -f "$d/SKILL.md" ] || continue
  name="$(basename "$d")"
  rm -rf "$DSH_HOME/skills/$name"
  cp -r "$d" "$DSH_HOME/skills/$name"
  count=$((count+1))
done
echo "▶ skills 已安装：$count 个"

# ── 3. 安装后校验 ────────────────────────────────────────────────
echo "▶ 校验"
fail=0

if grep -q "id: persona" "$PRESET_DST/agent.cordis.yml" && \
   grep -q "Web开发模式" "$PRESET_DST/preset.yml"; then
  echo "   ✓ preset 结构正常"
else
  echo "   ✗ preset 结构异常"; fail=1
fi

ok=0
for d in "$SRC"/skills/*/; do
  name="$(basename "$d")"
  f="$DSH_HOME/skills/$name/SKILL.md"
  if [ -f "$f" ] && head -1 "$f" | grep -q '^---$' && grep -q "^name: $name$" "$f"; then
    ok=$((ok+1))
  else
    echo "   ✗ $name 异常"; fail=1
  fi
done
echo "   ✓ skills frontmatter 合格：$ok/$count"

if [ "$fail" -ne 0 ]; then
  echo
  echo "⚠ 校验有失败项，请检查上面的输出"
  exit 1
fi

# ── 4. 提示 ──────────────────────────────────────────────────────
echo
echo "✅ 安装完成"
echo
echo "下一步："
echo "  1. 刷新 DSH 页面            （preset 与 skills 都是热加载；看不到再重启进程）"
echo "  2. 模式下拉里选择「Web开发模式」"
echo "  3. 设为默认（可选）：编辑 $DSH_HOME/settings.yaml"
echo "       agent-presets:"
echo "         default: web-dev"
echo
echo "验证：重启后新开对话，说「新建一个后台管理系统」，"
echo "      应先输出一行「技能计划：...」，再问 5 个澄清问题。"
