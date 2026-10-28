#!/usr/bin/env python3
"""DSH Web Dev Mode - 设计规则检索

零依赖（仅标准库）。在 skill 目录下运行：

    python scripts/search.py "表单 错误" --domain ux
    python scripts/search.py "登录页 布局" --domain layout --context pc
    python scripts/search.py "SaaS 蓝" --domain color

域（--domain）：
    ux      UX 硬规则（Do/Don't + 正反例）
    layout  页面布局模式（admin / pc / mobile）
    color   配色方案
    type    字体配对
    style   视觉风格
    dial    三个调节参数的预设

退出码：0 找到结果；1 无结果（此时**不要编造**，如实告知）。
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

DOMAINS = {
    "ux": ("ux-rules.csv", "UX 硬规则"),
    "layout": ("page-layouts.csv", "页面布局模式"),
    "color": ("colors.csv", "配色方案"),
    "type": ("typography.csv", "字体配对"),
    "style": ("styles.csv", "视觉风格"),
    "dial": ("dials.csv", "调节参数预设"),
}

COLUMNS = {
    "ux": ["id", "category", "severity", "context", "issue", "do", "dont", "code_good", "code_bad"],
    "layout": ["id", "context", "page_type", "sections", "nav", "primary_cta", "density", "notes"],
    "color": ["id", "context", "product_type", "mood", "primary", "bg", "surface", "text", "notes"],
    "type": ["id", "context", "mood", "heading", "body", "sizes", "notes"],
    "style": ["id", "context", "style", "density", "radius", "shadow", "motion", "use_when", "avoid_when"],
    "dial": ["id", "context", "product_type", "variance", "motion", "density", "notes"],
}


def load(domain: str) -> list[dict]:
    fname, _ = DOMAINS[domain]
    path = os.path.join(DATA_DIR, fname)
    if not os.path.exists(path):
        print(f"错误：找不到数据文件 {path}", file=sys.stderr)
        sys.exit(2)
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def score(row: dict, terms: list[str]) -> int:
    """关键词命中数。id 命中权重更高。"""
    text = " ".join(str(v) for v in row.values()).lower()
    total = 0
    for t in terms:
        tl = t.lower()
        if tl in text:
            total += 3 if tl in str(row.get("id", "")).lower() or tl in str(row.get("issue", "")).lower() else 1
    return total


def render(domain: str, rows: list[dict]) -> None:
    for r in rows:
        print("─" * 72)
        if domain == "ux":
            print(f"[{r['severity']:8s}] {r['category']:14s} {r['issue']}")
            print(f"  场景: {r['context']}")
            print(f"  Do  : {r['do']}")
            print(f"  Don't: {r['dont']}")
            if r.get("code_good"):
                print(f"  ✓ {r['code_good']}")
            if r.get("code_bad"):
                print(f"  ✗ {r['code_bad']}")
        elif domain == "layout":
            print(f"[{r['context']:6s}] {r['page_type']}")
            print(f"  区块: {r['sections']}")
            print(f"  导航: {r['nav']}")
            print(f"  主CTA: {r['primary_cta']}")
            print(f"  密度: {r['density']}")
            print(f"  备注: {r['notes']}")
        elif domain == "color":
            print(f"[{r['context']:6s}] {r['product_type']} / {r['mood']}")
            print(f"  primary {r['primary']}  bg {r['bg']}  surface {r['surface']}  text {r['text']}")
            print(f"  备注: {r['notes']}")
        elif domain == "type":
            print(f"[{r['context']:6s}] {r['mood']}")
            print(f"  标题: {r['heading']}")
            print(f"  正文: {r['body']}")
            print(f"  字号: {r['sizes']}")
            print(f"  备注: {r['notes']}")
        elif domain == "style":
            print(f"[{r['context']:6s}] {r['style']}")
            print(f"  密度 {r['density']} / 圆角 {r['radius']} / 阴影 {r['shadow']} / 动效 {r['motion']}")
            print(f"  适用: {r['use_when']}")
            print(f"  避免: {r['avoid_when']}")
        elif domain == "dial":
            print(f"[{r['context']:6s}] {r['product_type']}")
            print(f"  variance {r['variance']} / motion {r['motion']} / density {r['density']}")
            print(f"  备注: {r['notes']}")


def main() -> int:
    ap = argparse.ArgumentParser(description="DSH Web Dev Mode 设计规则检索")
    ap.add_argument("query", nargs="*", help="关键词（2-5 个，一次一个主要意图）")
    ap.add_argument("--domain", "-d", choices=list(DOMAINS), help="规则域")
    ap.add_argument("--context", "-c", choices=["admin", "pc", "mobile", "all"], help="场景过滤")
    ap.add_argument("--limit", "-n", type=int, default=8, help="最多返回条数（默认 8）")
    ap.add_argument("--list-domains", action="store_true", help="列出所有域")
    args = ap.parse_args()

    if args.list_domains:
        for k, (fname, desc) in DOMAINS.items():
            rows = load(k)
            print(f"  {k:8s} {desc:12s} {len(rows):3d} 条  ({fname})")
        return 0

    if not args.query:
        ap.print_help()
        return 0

    # 支持 "表单 错误" 这种整串传参：按空白拆成多个词
    terms = []
    for q in args.query:
        terms.extend(q.split())
    terms = [t for t in terms if t]
    targets = [args.domain] if args.domain else list(DOMAINS)

    found_any = False
    for domain in targets:
        rows = load(domain)
        if args.context and args.context != "all" and "context" in (rows[0] if rows else {}):
            rows = [r for r in rows if r.get("context") in (args.context, "all")]

        scored = [(score(r, terms), r) for r in rows]
        scored = [(s, r) for s, r in scored if s > 0]
        scored.sort(key=lambda x: -x[0])
        top = [r for _, r in scored[: args.limit]]

        if not top:
            continue

        found_any = True
        fname, desc = DOMAINS[domain]
        print()
        print(f"══ {desc}（{domain}）命中 {len(top)} 条 ══")
        render(domain, top)

    print()
    if not found_any:
        print("⚠ 没有匹配结果。")
        print("  请：① 换更窄的关键词重试一次；② 或指定 --domain。")
        print("  仍然没有就如实说明「没有找到依据」，不要编造规则或数值。")
        return 1

    print("─" * 72)
    print("提示：结果只是建议。落地前确认它适配当前产品与场景。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
