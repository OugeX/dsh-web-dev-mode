#!/usr/bin/env python3
"""把两个市场 PR 的内容同步到本地最新状态。

用法：
    python scripts/sync-pr.py --check      # 只检查差异，不写入
    python scripts/sync-pr.py              # 执行同步
    python scripts/sync-pr.py --dry-run    # 同 --check，但打印具体要改的内容

环境变量：
    GH_TOKEN    必填，GitHub Personal Access Token（需 repo 权限）

做的事：
    1. 读本地 skills 目录，得到技能数 N
    2. PR #10150（awesome-dsh-plugin）：把条目描述里的技能数改成 N
    3. PR #1（awesome-dsh-presets）：同步 presets/web-dev/agent.cordis.yml
    4. PR #1：更新两个 README 清单行里的技能数

幂等：某处没有差异就跳过，不产生空提交。

退出码：
    0  全部已同步 / 同步成功
    1  需要同步但处于 --check 模式
    2  出错（token 缺失、接口失败等）
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

# ── 配置 ────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")
LOCAL_PRESET = os.path.expanduser("~/.dsh/.agent-presets/web-dev/agent.cordis.yml")

MARKET_REPO = "OugeX/awesome-dsh-plugin"
MARKET_BRANCH = "add-web-dev-mode"
MARKET_FILE = "data/plugins/OugeX__dsh-web-dev-mode.yml"

PRESET_REPO = "OugeX/awesome-dsh-presets"
PRESET_BRANCH = "add-web-dev-preset"
PRESET_FILE = "presets/web-dev/agent.cordis.yml"
README_FILES = ["README.zh.md", "README.md"]

# (匹配模式, 格式化函数)
# 中文统一不带空格（「23个配套技能」），英文统一一个空格（「23 companion skills」）
COUNT_PATTERNS = [
    (re.compile(r"\d+\s*个配套技能"), lambda n: f"{n}个配套技能"),
    (re.compile(r"\d+\s*个工程技能"), lambda n: f"{n}个工程技能"),
    (re.compile(r"\d+\s*个技能"),     lambda n: f"{n}个技能"),
    (re.compile(r"\d+\s+companion skills"), lambda n: f"{n} companion skills"),
]


# ── GitHub API ─────────────────────────────────────────────────
class GH:
    def __init__(self, token: str):
        self.token = token

    def _req(self, method: str, path: str, body: dict | None = None):
        req = urllib.request.Request(
            "https://api.github.com" + path,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "dsh-web-dev-mode-sync",
            },
            data=json.dumps(body).encode("utf-8") if body else None,
        )
        try:
            with urllib.request.urlopen(req) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {detail}") from None

    def get_file(self, repo: str, path: str, ref: str):
        d = self._req("GET", f"/repos/{repo}/contents/{path}?ref={ref}")
        return d["sha"], base64.b64decode(d["content"]).decode("utf-8")

    def put_file(self, repo: str, path: str, content: str, sha: str, branch: str, msg: str):
        return self._req("PUT", f"/repos/{repo}/contents/{path}", {
            "message": msg,
            "content": base64.b64encode(content.encode("utf-8")).decode(),
            "sha": sha,
            "branch": branch,
        })


# ── 工具 ───────────────────────────────────────────────────────
def local_skill_count() -> int:
    if not os.path.isdir(SKILLS_DIR):
        raise RuntimeError(f"找不到 skills 目录：{SKILLS_DIR}")
    n = sum(1 for d in os.listdir(SKILLS_DIR)
            if os.path.isfile(os.path.join(SKILLS_DIR, d, "SKILL.md")))
    if n == 0:
        raise RuntimeError("skills 目录下没有 SKILL.md")
    return n


def rewrite_counts(text: str, n: int) -> tuple[str, int]:
    """把所有「N 个…技能」改成期望值，返回 (新文本, 改动处数)。"""
    changed = 0
    for pat, fmt in COUNT_PATTERNS:
        def repl(m: re.Match, fmt=fmt) -> str:
            nonlocal changed
            new = fmt(n)
            if m.group(0) != new:
                changed += 1
            return new
        text = pat.sub(repl, text)
    return text, changed


def short_hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


# ── 主流程 ─────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="同步市场 PR 到本地最新状态")
    ap.add_argument("--check", action="store_true", help="只检查，不写入")
    ap.add_argument("--dry-run", action="store_true", help="打印要改的内容，不写入")
    args = ap.parse_args()
    check_only = args.check or args.dry_run

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("错误：需要 GH_TOKEN 环境变量", file=sys.stderr)
        print("      export GH_TOKEN=ghp_xxx", file=sys.stderr)
        return 2

    try:
        n = local_skill_count()
    except RuntimeError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2

    print(f"本地技能数：{n}")
    gh = GH(token)
    pending = 0
    done = 0

    # ── 1. 市场条目（PR #10150）──────────────────────────────
    print("\n[1/3] awesome-dsh-plugin 条目")
    try:
        sha, text = gh.get_file(MARKET_REPO, MARKET_FILE, MARKET_BRANCH)
        new_text, changed = rewrite_counts(text, n)
        if changed == 0:
            print("  ✓ 技能数已是最新")
        else:
            print(f"  需要改 {changed} 处技能数")
            if args.dry_run:
                for line in new_text.split("\n"):
                    if str(n) in line:
                        print(f"    → {line.strip()[:110]}")
            if check_only:
                pending += 1
            else:
                gh.put_file(MARKET_REPO, MARKET_FILE, new_text, sha, MARKET_BRANCH,
                            f"docs: 技能数同步为 {n}")
                print("  ✓ 已提交")
                done += 1
    except RuntimeError as e:
        print(f"  ✗ {e}", file=sys.stderr)
        return 2

    # ── 2. preset 文件（PR #1）───────────────────────────────
    print("\n[2/3] awesome-dsh-presets / agent.cordis.yml")
    if not os.path.isfile(LOCAL_PRESET):
        print(f"  跳过：本地 preset 不存在（{LOCAL_PRESET}）")
    else:
        local_text = open(LOCAL_PRESET, encoding="utf-8").read()
        try:
            sha, remote_text = gh.get_file(PRESET_REPO, PRESET_FILE, PRESET_BRANCH)
            if short_hash(local_text) == short_hash(remote_text):
                print("  ✓ 内容一致")
            else:
                print(f"  有差异（本地 {len(local_text)} 字符 / 远端 {len(remote_text)} 字符）")
                if check_only:
                    pending += 1
                else:
                    gh.put_file(PRESET_REPO, PRESET_FILE, local_text, sha, PRESET_BRANCH,
                                "sync: 同步最新 preset")
                    print("  ✓ 已同步")
                    done += 1
        except RuntimeError as e:
            print(f"  ✗ {e}", file=sys.stderr)
            return 2

    # ── 3. README 清单行（PR #1）─────────────────────────────
    print("\n[3/3] awesome-dsh-presets / README 清单行")
    for fname in README_FILES:
        try:
            sha, text = gh.get_file(PRESET_REPO, fname, PRESET_BRANCH)
            new_text, changed = rewrite_counts(text, n)
            if changed == 0:
                print(f"  ✓ {fname} 已是最新")
            else:
                print(f"  {fname} 需要改 {changed} 处")
                if check_only:
                    pending += 1
                else:
                    gh.put_file(PRESET_REPO, fname, new_text, sha, PRESET_BRANCH,
                                f"docs: {fname} 技能数同步为 {n}")
                    print(f"  ✓ {fname} 已更新")
                    done += 1
        except RuntimeError as e:
            print(f"  ✗ {fname}: {e}", file=sys.stderr)
            return 2

    # ── 汇总 ────────────────────────────────────────────────
    print()
    if check_only:
        if pending:
            print(f"⚠ 有 {pending} 处需要同步。去掉 --check 执行实际同步。")
            return 1
        print("✅ 全部已是最新。")
        return 0

    print(f"✅ 完成：{done} 处已同步。")
    if done:
        print("   PR 列表：")
        print(f"     https://github.com/awesome-dsh-plugin/awesome-dsh-plugin/pull/10150")
        print(f"     https://github.com/hackerFish/awesome-dsh-presets/pull/1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
