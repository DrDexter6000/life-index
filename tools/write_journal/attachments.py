#!/usr/bin/env python3
"""
Life Index - Write Journal Tool - Attachments
附件处理模块
"""

import os
import re
import shutil
import asyncio
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ..lib.paths import get_attachments_dir
from ..lib.logger import get_logger
from ..lib.url_download import download_url

from .utils import get_year_month, convert_path_for_platform

logger = get_logger(__name__)


def _get_attachment_metadata(file_path: str) -> dict[str, Any]:
    content_type, _ = mimetypes.guess_type(file_path)
    size: int | None = None
    try:
        size = os.path.getsize(file_path)
    except OSError:
        size = None

    return {"content_type": content_type, "size": size}


async def download_attachment_from_url(
    url: str, target_dir: Path, date_str: str, timeout: float = 30.0
) -> dict[str, Any]:
    return await download_url(url, target_dir, date_str=date_str, timeout=timeout)


def looks_like_file_path(path: str) -> bool:
    """
    判断路径是否看起来像文件路径（有扩展名）
    """
    if not path:
        return False

    # 检查是否有文件扩展名
    name = os.path.basename(path)
    if "." in name:
        ext = name.split(".")[-1].lower()
        # 常见文件扩展名
        valid_exts = {
            "txt",
            "md",
            "doc",
            "docx",
            "pdf",
            "xls",
            "xlsx",
            "ppt",
            "pptx",
            "jpg",
            "jpeg",
            "png",
            "gif",
            "bmp",
            "svg",
            "webp",
            "ico",
            "mp4",
            "avi",
            "mov",
            "mkv",
            "flv",
            "wmv",
            "mp3",
            "wav",
            "flac",
            "aac",
            "ogg",
            "zip",
            "rar",
            "7z",
            "tar",
            "gz",
            "py",
            "js",
            "ts",
            "html",
            "css",
            "json",
            "xml",
            "yaml",
            "yml",
            "exe",
            "msi",
            "dmg",
            "pkg",
            "deb",
            "rpm",
            "psd",
            "ai",
            "sketch",
            "fig",
            "db",
            "sqlite",
            "db3",
        }
        if ext in valid_exts:
            return True

    return False


def extract_file_paths_from_content(content: str) -> List[str]:
    """
    从内容中提取本地文件路径

    支持的格式：
    - Windows 绝对路径: C:\\Users\\...\\file.txt, C:/Users/.../file.txt
    - 网络路径: \\\\server\\share\\file.txt
    - UNC 路径: //server/share/file.txt

    Returns:
        文件路径列表（去重）
    """
    if not content:
        return []

    paths = []

    # 匹配 Windows 绝对路径 (C:\... 或 C:/...)
    # 使用更严格的模式：必须以盘符开头，后跟反斜杠或斜杠，然后是路径组件
    # 路径组件不能包含非法字符 :*?"<>|
    # FIX: 允许文件名中包含空格（中文文件名常见），但扩展名部分不允许空格
    windows_pattern = r'[A-Za-z]:[\\/](?:[^\\/:*?"<>|\r\n]*[\\/])*[^\\/:*?"<>|\r\n]*\.[\w]+'
    for match in re.finditer(windows_pattern, content):
        path = match.group(0)
        # 验证是否是有效文件路径（有扩展名）
        if looks_like_file_path(path):
            paths.append(path)

    # 匹配 UNC 路径 (\\server\share\... 或 //server/share/...)
    # FIX: 允许文件名中包含空格（中文文件名常见），但扩展名部分不允许空格
    unc_pattern = (
        r'(?:\\\\|//)[^\\/:*?"<>|\r\n]+(?:[\\/][^\\/:*?"<>|\r\n]+)*'
        r'[\\/][^\\/:*?"<>|\r\n]*\.[\w]+'
    )
    for match in re.finditer(unc_pattern, content):
        path = match.group(0)
        if looks_like_file_path(path):
            paths.append(path)

    # 匹配 Unix/Linux/macOS 绝对路径 (/tmp/.../file.txt)
    unix_pattern = r"/(?:[^/\s\r\n]+/)*[^/\s\r\n]+\.[\w]+"
    for match in re.finditer(unix_pattern, content):
        start = match.start()
        if start >= 2 and re.match(r"[A-Za-z]:", content[start - 2 : start]):
            continue
        if start >= 3 and content[start - 3 : start] == "://":
            continue
        path = match.group(0)
        if looks_like_file_path(path):
            paths.append(path)

    # 去重并保持顺序
    seen = set()
    unique_paths = []
    for p in paths:
        normalized = os.path.normpath(p).lower()
        if normalized not in seen:
            seen.add(normalized)
            unique_paths.append(p)

    return unique_paths


def _strip_cjk_spaces(path_str: str) -> str:
    """
    移除中英文/中文与数字之间被错误插入的空格。

    某些 LLM（如 qwen 系列）在生成 JSON 参数时，会自动在中英文之间
    添加空格（中文排版习惯），导致文件名被修改。

    例如: "Opus 审计报告.txt" → "Opus审计报告.txt"

    仅处理文件名部分（最后一个路径组件），不修改目录路径。
    """
    # 分离目录和文件名
    dir_part = os.path.dirname(path_str)
    filename = os.path.basename(path_str)

    if not filename:
        return path_str

    # 移除英文/数字与中文之间的空格（双向）
    # ASCII字符(含标点) + 空格 + CJK字符
    filename = re.sub(r"([\x00-\x7F])\s+([\u4e00-\u9fff])", r"\1\2", filename)
    # CJK字符 + 空格 + ASCII字符(含标点)
    filename = re.sub(r"([\u4e00-\u9fff])\s+([\x00-\x7F])", r"\1\2", filename)

    if dir_part:
        return os.path.join(dir_part, filename)
    return filename


def _resolve_attachment_path(source_path: str, converted_path: str) -> Optional[str]:
    """
    多策略附件路径解析：精确匹配 → 跨平台转换 → 中英文空格容错。

    Args:
        source_path: 原始路径
        converted_path: 跨平台转换后的路径

    Returns:
        可访问的文件路径，或 None（所有策略都失败）
    """
    # 策略1：原始路径精确匹配
    if os.path.exists(source_path):
        return source_path

    # 策略2：跨平台转换路径
    if converted_path != source_path and os.path.exists(converted_path):
        return converted_path

    # 策略3：中英文空格容错（去掉 LLM 错误插入的空格后重试）
    stripped_source = _strip_cjk_spaces(source_path)
    if stripped_source != source_path and os.path.exists(stripped_source):
        logger.info(f"空格容错命中: [{source_path}] → [{stripped_source}]")
        return stripped_source

    # 策略3b：对跨平台转换后的路径也做空格容错
    if converted_path != source_path:
        stripped_converted = _strip_cjk_spaces(converted_path)
        if stripped_converted != converted_path and os.path.exists(stripped_converted):
            logger.info(f"空格容错命中(跨平台): [{converted_path}] → [{stripped_converted}]")
            return stripped_converted

    return None


def process_attachments(
    attachments: Sequence[Dict[str, str] | str],
    date_str: str,
    dry_run: bool = False,
    auto_detected_paths: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    处理附件复制

    Args:
        attachments: 附件列表，每项包含 source_path 和可选的 description
        date_str: 日期字符串，用于确定附件存储路径
        dry_run: 是否为模拟运行
        auto_detected_paths: 从内容中自动检测到的文件路径

    Returns:
        处理后的附件列表，包含 filename 和 description
    """
    processed = []
    year, month = get_year_month(date_str)
    att_dir = get_attachments_dir() / str(year) / f"{month:02d}"

    # 合并显式附件和自动检测的附件
    all_attachments = []

    # 添加显式附件
    if attachments:
        for att in attachments:
            if isinstance(att, dict):
                all_attachments.append(att)
            elif isinstance(att, str):
                all_attachments.append({"source_path": att, "description": ""})

    # 添加自动检测的附件（去重）
    existing_paths = {os.path.normpath(a.get("source_path", "")).lower() for a in all_attachments}
    if auto_detected_paths:
        for path in auto_detected_paths:
            normalized = os.path.normpath(path).lower()
            if normalized not in existing_paths:
                all_attachments.append(
                    {"source_path": path, "description": "", "auto_detected": "true"}
                )
                existing_paths.add(normalized)

    if not all_attachments:
        return []

    for idx, att in enumerate(all_attachments):
        source_path = att.get("source_path", "")
        source_url = att.get("source_url", "")
        description = att.get("description", "")
        auto_detected = att.get("auto_detected", False)
        download_result: dict[str, Any] = {}

        if source_url:
            download_result = asyncio.run(
                download_attachment_from_url(source_url, att_dir, date_str)
            )
            if not download_result.get("success"):
                processed.append(
                    {
                        "filename": f"[下载失败: {source_url}]",
                        "description": description,
                        "error": str(download_result.get("error") or "下载失败"),
                        "auto_detected": auto_detected,
                        "error_code": download_result.get("error_code"),
                    }
                )
                continue

            source_path = str(download_result.get("path", ""))

        input_content_type = att.get("content_type")
        input_size = att.get("size")

        if not source_path:
            continue

        # 安全检查：防止路径遍历攻击
        # NOTE: 当前实现允许访问任何可读文件。如需限制访问范围，
        # 请使用 lib.config.get_safe_path() 验证路径是否在允许的目录内。
        # 例如：限制只能访问用户文档目录下的文件
        # from lib.config import get_safe_path, USER_DATA_DIR
        # safe_path = get_safe_path(source_path, USER_DATA_DIR)
        # if safe_path is None:
        #     processed.append({"filename": f"[访问被拒绝: {source_path}]", ...})
        #     continue

        # 诊断日志：记录工具实际收到的原始路径
        logger.debug(f"附件原始路径: [{source_path}]")

        # 尝试跨平台路径转换
        converted_path = convert_path_for_platform(source_path)

        # 路径查找：精确匹配 → 跨平台转换 → 中英文空格容错
        resolved_path = _resolve_attachment_path(source_path, converted_path)

        if resolved_path is None:
            logger.warning(f"附件未找到: [{source_path}]")
            processed.append(
                {
                    "filename": f"[未找到: {source_path}]",
                    "description": description,
                    "error": "源文件不存在",
                    "auto_detected": auto_detected,
                    "converted_path": converted_path if converted_path != source_path else None,
                }
            )
            continue

        if resolved_path != source_path:
            logger.info(f"附件路径已修正: [{source_path}] → [{resolved_path}]")
        source_path = resolved_path

        # 跳过目录
        if os.path.isdir(source_path):
            continue

        # 生成目标文件名（处理重名）
        source_name = Path(source_path).name
        base_name = Path(source_name).stem
        ext = Path(source_name).suffix

        if dry_run:
            target_name = source_name
        else:
            # 检查是否已存在同名文件
            target_name = source_name
            counter = 1
            while (att_dir / target_name).exists():
                target_name = f"{base_name}_{counter:03d}{ext}"
                counter += 1

            # 复制文件
            att_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(source_path, att_dir / target_name)

        # 生成相对路径 (../../../Attachments/YYYY/MM/filename)
        rel_path = f"../../../attachments/{year}/{month:02d}/{target_name}"
        metadata = _get_attachment_metadata(source_path)
        if input_content_type is not None:
            metadata["content_type"] = str(input_content_type)
        if input_size is not None:
            metadata["size"] = int(input_size)
        if source_url and download_result.get("content_type") is not None:
            metadata["content_type"] = str(download_result.get("content_type"))
        download_size = download_result.get("size") if source_url else None
        if download_size is not None and not isinstance(download_size, bool):
            if isinstance(download_size, (int, float)):
                metadata["size"] = int(download_size)
            elif isinstance(download_size, str):
                metadata["size"] = int(download_size)

        processed_entry = {
            "filename": target_name,
            "rel_path": rel_path,
            "description": description,
            "original_name": source_name,
            "auto_detected": auto_detected,
            "content_type": metadata.get("content_type"),
            "size": metadata.get("size"),
        }
        if source_url:
            processed_entry["source_url"] = source_url

        processed.append(processed_entry)

    return processed
