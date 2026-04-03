#!/usr/bin/env python3
"""
文档同步检查脚本
检查文档中的内部链接和引用是否有效
检查版本号一致性（pyproject.toml vs bootstrap-manifest.json）
"""

import json
import os
import re
import sys
from pathlib import Path


def find_markdown_links(content: str, base_dir: Path) -> list:
    """
    查找 Markdown 内容中的内部链接
    返回: [(链接文本, 链接路径, 行号)]
    """
    links = []
    # 匹配 Markdown 链接: [text](./path) 或 [text](../path)
    link_pattern = r"\[([^\]]+)\]\((\.[^)]+)\)"

    for line_num, line in enumerate(content.split("\n"), 1):
        for match in re.finditer(link_pattern, line):
            text = match.group(1)
            path = match.group(2)
            links.append((text, path, line_num))

    return links


def extract_pyproject_version(pyproject_path: Path) -> str | None:
    """
    从 pyproject.toml 提取 version
    返回: 版本号字符串，如 "1.5.0"
    """
    if not pyproject_path.exists():
        return None

    content = pyproject_path.read_text(encoding="utf-8")
    # 匹配 version = "X.Y.Z" 格式
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if match:
        return match.group(1)
    return None


def extract_bootstrap_version(bootstrap_path: Path) -> str | None:
    """
    从 bootstrap-manifest.json 提取 repo_version
    返回: 版本号字符串，如 "1.5.0"
    """
    if not bootstrap_path.exists():
        return None

    content = bootstrap_path.read_text(encoding="utf-8")
    try:
        data = json.loads(content)
        return data.get("repo_version")
    except json.JSONDecodeError:
        return None


def check_link_validity(link_path: str, base_dir: Path, source_file: Path) -> tuple:
    """
    检查链接是否有效
    返回: (是否有效, 解析后的完整路径)
    """
    # 移除锚点（#section）
    path_without_anchor = link_path.split("#")[0]

    if not path_without_anchor:
        return True, None  # 纯锚点链接，始终有效

    # 解析相对路径
    if link_path.startswith("./") or link_path.startswith("../"):
        target = (source_file.parent / path_without_anchor).resolve()
    else:
        target = (base_dir / path_without_anchor).resolve()

    exists = target.exists()
    return exists, target


def check_documentation_sync():
    """主检查函数"""
    project_root = Path(__file__).parent.parent.parent
    docs_dir = project_root

    # 要检查的核心文档
    core_docs = [
        "SKILL.md",
        "AGENTS.md",
        "README.md",
        "docs/API.md",
        "docs/ARCHITECTURE.md",
        "tools/lib/AGENTS.md",
    ]

    errors = []
    warnings = []

    print("=" * 60)
    print("文档同步检查")
    print("=" * 60)

    for doc_rel_path in core_docs:
        doc_path = project_root / doc_rel_path

        if not doc_path.exists():
            errors.append(f"[ERROR] 文档不存在: {doc_rel_path}")
            continue

        print(f"\n[检查] {doc_rel_path}")

        content = doc_path.read_text(encoding="utf-8")
        links = find_markdown_links(content, project_root)

        if not links:
            print(f"   无内部链接")
            continue

        for text, link_path, line_num in links:
            is_valid, resolved_path = check_link_validity(
                link_path, project_root, doc_path
            )

            if is_valid:
                print(
                    f"   [OK] [{text}]({link_path}) -> {resolved_path and resolved_path.name or 'anchor'}"
                )
            else:
                errors.append(
                    f"[ERROR] {doc_rel_path}:{line_num} - 无效链接: [{text}]({link_path})"
                )
                print(f"   [FAIL] [{text}]({link_path}) - 未找到")

    # 检查 AGENTS.md 最后更新日期
    agents_md = project_root / "AGENTS.md"
    if agents_md.exists():
        content = agents_md.read_text(encoding="utf-8")
        # 兼容两种格式: "最后更新:" 和 "**最后更新**:"
        if "最后更新" in content:
            print(f"\n[OK] AGENTS.md 包含最后更新日期标记")
        else:
            warnings.append("[WARN] AGENTS.md 缺少最后更新日期标记")

    # 检查 tools/lib/AGENTS.md 最后更新日期
    lib_agents_md = project_root / "tools/lib/AGENTS.md"
    if lib_agents_md.exists():
        content = lib_agents_md.read_text(encoding="utf-8")
        # 兼容两种格式: "最后更新:" 和 "**最后更新**:"
        if "最后更新" in content:
            print(f"[OK] tools/lib/AGENTS.md 包含最后更新日期标记")
        else:
            warnings.append("[WARN] tools/lib/AGENTS.md 缺少最后更新日期标记")

    # 检查版本号一致性
    print(f"\n[检查] 版本号一致性")
    pyproject_path = project_root / "pyproject.toml"
    bootstrap_path = project_root / "bootstrap-manifest.json"

    pyproject_version = extract_pyproject_version(pyproject_path)
    bootstrap_version = extract_bootstrap_version(bootstrap_path)

    if pyproject_version and bootstrap_version:
        if pyproject_version == bootstrap_version:
            print(
                f"   [OK] pyproject.toml: {pyproject_version} == bootstrap-manifest.json: {bootstrap_version}"
            )
        else:
            errors.append(
                f"[ERROR] 版本号不一致: pyproject.toml={pyproject_version}, bootstrap-manifest.json={bootstrap_version}"
            )
            print(
                f"   [FAIL] pyproject.toml: {pyproject_version} != bootstrap-manifest.json: {bootstrap_version}"
            )
    elif pyproject_version:
        errors.append("[ERROR] bootstrap-manifest.json 缺少 repo_version 或解析失败")
        print(f"   [FAIL] bootstrap-manifest.json 缺少 repo_version")
    elif bootstrap_version:
        errors.append("[ERROR] pyproject.toml 缺少 version 或解析失败")
        print(f"   [FAIL] pyproject.toml 缺少 version")
    else:
        errors.append(
            "[ERROR] 无法从 pyproject.toml 和 bootstrap-manifest.json 提取版本号"
        )
        print(f"   [FAIL] 两个文件都无法提取版本号")

    # 汇总结果
    print("\n" + "=" * 60)
    print("检查结果汇总")
    print("=" * 60)

    if warnings:
        print(f"\n警告 ({len(warnings)}):")
        for warning in warnings:
            print(f"   {warning}")

    if errors:
        print(f"\n错误 ({len(errors)}):")
        for error in errors:
            print(f"   {error}")
        print(f"\n{'=' * 60}")
        print("检查失败 - 请修复上述错误")
        return 1

    print(f"\n所有检查通过！")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(check_documentation_sync())
