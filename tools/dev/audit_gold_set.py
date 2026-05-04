#!/usr/bin/env python3
"""Gold Set 审计专用工具 — 验证期望标题存在性和概念命中分布。

用法:
    python -m tools.dev.audit_gold_set --check-titles
    python -m tools.dev.audit_gold_set --check-concept "数字灵魂" --mode exact
    python -m tools.dev.audit_gold_set --check-concept "边缘计算" --mode keyword
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

GOLDEN_PATH = Path("tools/eval/golden_queries.yaml")
JOURNALS_DIR = Path.home() / "Documents" / "Life-Index" / "Journals"


def _load_journals() -> list[dict[str, Any]]:
    """加载所有日志的标题和正文。"""
    journals: list[dict[str, Any]] = []
    for md_file in JOURNALS_DIR.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            if not content.startswith("---"):
                continue
            end = content.find("---", 3)
            if end <= 0:
                continue
            meta = yaml.safe_load(content[3:end])
            title = str(meta.get("title", "")) if meta else ""
            body = content[end + 3 :]
            journals.append(
                {
                    "file": str(md_file.relative_to(JOURNALS_DIR)),
                    "title": title,
                    "body": body,
                    "full": title + "\n" + body,
                }
            )
        except Exception:
            continue
    return journals


def _load_golden() -> list[dict[str, Any]]:
    payload = yaml.safe_load(GOLDEN_PATH.read_text(encoding="utf-8"))
    return payload.get("queries", []) if isinstance(payload, dict) else []


def cmd_check_titles() -> None:
    """遍历全部 must_contain_title，输出不存在的列表。"""
    queries = _load_golden()
    journals = _load_journals()
    all_titles = {j["title"] for j in journals}

    ghosts: list[dict[str, Any]] = []
    for q in queries:
        qid = q.get("id", "")
        expected = q.get("expected", {})
        titles = expected.get("must_contain_title", []) if expected else []
        for t in titles:
            if t not in all_titles:
                ghosts.append(
                    {
                        "id": qid,
                        "query": q.get("query", ""),
                        "missing_title": t,
                        "category": q.get("category", ""),
                    }
                )

    # 汇总
    print("\n=== Gold Set 标题审计 ===")
    print(f"总查询数: {len(queries)}")
    print(f"日志总数: {len(journals)}")
    print(f"幻觉标题数（must_contain_title 不存在于任何日志）: {len(ghosts)}")
    if ghosts:
        print("\n详情:")
        for g in ghosts:
            print(f"  {g['id']} | {g['query']} | 缺失标题: \"{g['missing_title']}\"")
    else:
        print("\n✅ 所有 must_contain_title 均存在于日志中")

    # 同时输出 JSON 方便后续处理
    out = Path("tools/dev/audit_ghost_titles.json")
    out.write_text(json.dumps(ghosts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nJSON 输出: {out}")


def _normalize(text: str) -> str:
    """简单归一化：去空白、转小写。"""
    return text.lower().replace(" ", "").replace("\n", "")


def _tokenize(text: str) -> list[str]:
    """极简分词：中文按字，英文按空格。"""
    tokens: list[str] = []
    current_word = ""
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            if current_word:
                tokens.append(current_word.lower())
                current_word = ""
            tokens.append(ch)
        elif ch.isalnum():
            current_word += ch
        else:
            if current_word:
                tokens.append(current_word.lower())
                current_word = ""
    if current_word:
        tokens.append(current_word.lower())
    return tokens


def cmd_check_concept(query: str, mode: str) -> None:
    """对一条 query 的概念，输出三种匹配方式的命中分布。"""
    journals = _load_journals()
    print(f'\n=== 概念审计: "{query}" | mode={mode} ===')
    print(f"日志总数: {len(journals)}\n")

    if mode == "exact":
        hits = [j for j in journals if query in j["full"]]
        print(f"精确匹配命中: {len(hits)}")
        for j in hits:
            print(f"  - {j['title']}")
        if not hits:
            print("  (无命中)")

    elif mode == "keyword":
        tokens = _tokenize(query)
        print(f"分词结果: {tokens}\n")

        for tok in tokens:
            hits = [j for j in journals if tok in _normalize(j["full"])]
            print(f"关键词 '{tok}': 命中 {len(hits)} 篇")
            for j in hits[:3]:
                print(f"  - {j['title']}")
            if len(hits) > 3:
                print(f"  ... 还有 {len(hits) - 3} 篇")
            if not hits:
                print("  (无命中)")
            print()

    elif mode == "semantic":
        # 复用现有语义搜索基础设施
        try:
            from tools.search_journals.semantic import search_semantic

            results, _ = search_semantic(query, top_k=10)
            print("语义匹配 Top 10:")
            for r in results:
                score = r.get("score", 0)
                title = r.get("title", "N/A")
                print(f"  - {title} (score={score:.4f})")
            if not results:
                print("  (无命中)")
        except Exception as e:
            print(f"语义搜索失败: {e}")
            print("提示: 确保向量索引已构建 (life-index index --rebuild)")

    else:
        print(f"未知 mode: {mode}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gold Set 审计工具")
    parser.add_argument(
        "--check-titles", action="store_true", help="检查所有 must_contain_title 是否存在"
    )
    parser.add_argument(
        "--check-concept", type=str, default=None, help="检查某概念在日志中的命中分布"
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="exact",
        choices=["exact", "keyword", "semantic"],
        help="匹配模式",
    )
    args = parser.parse_args()

    if args.check_titles:
        cmd_check_titles()
    elif args.check_concept:
        cmd_check_concept(args.check_concept, args.mode)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
