#!/usr/bin/env python3
"""
Life Index - Write Journal Tool - Index Updater
索引更新模块
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..lib.config import JOURNALS_DIR, BY_TOPIC_DIR, USER_DATA_DIR, get_index_prefixes

# Define write_journal directory for subprocess calls
WRITE_JOURNAL_DIR = Path(__file__).parent


def update_topic_index(topic: Any, journal_path: Path, data: Dict[str, Any]) -> List[Path]:
    """更新主题索引文件 - 支持单个主题或主题列表"""
    if not topic:
        return []

    # 统一处理为列表
    if isinstance(topic, str):
        topics = [topic]
    elif isinstance(topic, list):
        topics = topic
    else:
        return []

    # 获取可配置的前缀
    prefixes = get_index_prefixes()
    topic_prefix = prefixes.get("topic", "主题_")

    date_str = data.get("date", "")[:10]
    title = data.get("title", "无标题")
    rel_path = os.path.relpath(journal_path, JOURNALS_DIR.parent).replace("\\", "/")

    entry = f"- [{date_str}] [{title}]({rel_path})"

    updated = []
    for t in topics:
        if not t:
            continue
        BY_TOPIC_DIR.mkdir(parents=True, exist_ok=True)
        index_file = BY_TOPIC_DIR / f"{topic_prefix}{t}.md"

        if index_file.exists():
            content = index_file.read_text(encoding="utf-8")
            if entry not in content:
                with open(index_file, "a", encoding="utf-8") as f:
                    f.write(entry + "\n")
        else:
            with open(index_file, "w", encoding="utf-8") as f:
                f.write(f"# 主题: {t}\n\n")
                f.write(entry + "\n")

        updated.append(index_file)

    return updated


def update_project_index(project: str, journal_path: Path, data: Dict[str, Any]) -> Optional[Path]:
    """更新项目索引文件"""
    if not project:
        return None

    # 获取可配置的前缀
    prefixes = get_index_prefixes()
    project_prefix = prefixes.get("project", "项目_")

    BY_TOPIC_DIR.mkdir(parents=True, exist_ok=True)
    index_file = BY_TOPIC_DIR / f"{project_prefix}{project}.md"

    date_str = data.get("date", "")[:10]
    title = data.get("title", "无标题")
    rel_path = os.path.relpath(journal_path, JOURNALS_DIR.parent).replace("\\", "/")

    entry = f"- [{date_str}] [{title}]({rel_path})"

    if index_file.exists():
        content = index_file.read_text(encoding="utf-8")
        if entry not in content:
            with open(index_file, "a", encoding="utf-8") as f:
                f.write(entry + "\n")
    else:
        with open(index_file, "w", encoding="utf-8") as f:
            f.write(f"# 项目: {project}\n\n")
            f.write(entry + "\n")

    return index_file


def update_tag_indices(tags: List[str], journal_path: Path, data: Dict[str, Any]) -> List[Path]:
    """更新标签索引文件"""
    updated = []

    # 获取可配置的前缀
    prefixes = get_index_prefixes()
    tag_prefix = prefixes.get("tag", "标签_")

    for tag in tags:
        if not tag:
            continue

        BY_TOPIC_DIR.mkdir(parents=True, exist_ok=True)
        index_file = BY_TOPIC_DIR / f"{tag_prefix}{tag}.md"

        date_str = data.get("date", "")[:10]
        title = data.get("title", "无标题")
        rel_path = os.path.relpath(journal_path, JOURNALS_DIR.parent).replace("\\", "/")

        entry = f"- [{date_str}] [{title}]({rel_path})"

        if index_file.exists():
            content = index_file.read_text(encoding="utf-8")
            if entry not in content:
                with open(index_file, "a", encoding="utf-8") as f:
                    f.write(entry + "\n")
        else:
            with open(index_file, "w", encoding="utf-8") as f:
                f.write(f"# 标签: {tag}\n\n")
                f.write(entry + "\n")

        updated.append(index_file)

    return updated


def update_monthly_abstract(year: int, month: int, dry_run: bool = False) -> Dict[str, Any]:
    """
    更新月度摘要文件（调用 generate_abstract.py 工具）

    Args:
        year: 年份
        month: 月份
        dry_run: 是否为模拟运行

    Returns:
        {
            "abstract_path": str,
            "journal_count": int,
            "updated": bool
        }
    """
    result = {"abstract_path": None, "journal_count": 0, "updated": False}

    month_str = f"{year}-{month:02d}"
    abstract_path = (
        JOURNALS_DIR / str(year) / f"{month:02d}" / f"monthly_report_{year}-{month:02d}.md"
    )

    # 构建命令
    cmd = [
        sys.executable,
        "-m",
        "tools.generate_abstract",
        "--month",
        month_str,
        "--json",
    ]
    if dry_run:
        cmd.append("--dry-run")

    try:
        # 调用 generate_abstract 模块
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

        if proc.returncode == 0 and proc.stdout:
            try:
                output = json.loads(proc.stdout)
                if output and len(output) > 0:
                    data = output[0]
                    result["abstract_path"] = data.get("abstract_path")
                    result["journal_count"] = data.get("journal_count", 0)
                    result["updated"] = data.get("updated", False)
            except json.JSONDecodeError as e:
                result["error"] = f"Invalid JSON output: {e}"
        else:
            result["error"] = proc.stderr or f"Command failed with return code {proc.returncode}"

    except subprocess.TimeoutExpired:
        result["error"] = "Command timed out after 30 seconds"
    except (OSError, IOError, RuntimeError) as e:
        result["error"] = str(e)

    return result


def update_vector_index(journal_path: Path, data: Dict[str, Any]) -> bool:
    """
    写入后同步更新向量索引（Write-Through）

    Args:
        journal_path: 日志文件路径
        data: 日志数据（包含 title, content, abstract, tags, topic 等）

    Returns:
        True 如果更新成功，False 如果失败（不影响主流程）
    """
    try:
        from ..lib.vector_index_simple import get_model, get_index
        from ..lib.config import USER_DATA_DIR

        model = get_model()
        if not model.load():
            return False

        # 构建要嵌入的文本（与 semantic_search.py 的 parse_journal_for_vec 保持一致）
        # 顺序：标题 + 正文前1000字 + 标签 + 主题
        text_parts = []

        title = data.get("title", "")
        if title:
            text_parts.append(title)

        content = data.get("content", "")
        if content:
            # 限制正文长度，与 parse_journal_for_vec 保持一致
            text_parts.append(content[:1000])

        tags = data.get("tags", [])
        if tags:
            if isinstance(tags, list):
                text_parts.extend(tags)
            else:
                text_parts.append(tags)

        topic = data.get("topic")
        if topic:
            if isinstance(topic, list):
                text_parts.extend(topic)
            else:
                text_parts.append(topic)

        embed_text = " ".join(text_parts).strip()
        if not embed_text:
            return False

        # 生成嵌入向量
        embeddings = model.encode([embed_text])
        if not embeddings:
            return False

        # 计算相对路径
        try:
            rel_path = str(journal_path.relative_to(USER_DATA_DIR)).replace("\\", "/")
        except ValueError:
            rel_path = str(journal_path).replace("\\", "/")

        # 更新索引
        index = get_index()
        date_str = str(data.get("date", ""))[:10]

        # 计算文件哈希用于后续增量更新检测
        import hashlib

        try:
            file_content = journal_path.read_bytes()
            file_hash = hashlib.md5(file_content).hexdigest()[:16]
        except Exception:
            file_hash = ""

        index.add(rel_path, embeddings[0], date_str, file_hash)
        index.commit()

        return True

    except (ImportError, OSError, IOError, RuntimeError) as e:
        # 向量索引更新失败不应阻塞日志写入
        # 日志会在下次 cron 全量重建时补上
        print(f"Warning: Failed to update vector index: {e}")
        return False
