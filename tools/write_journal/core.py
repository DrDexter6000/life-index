#!/usr/bin/env python3
"""
Life Index - Write Journal Tool - Core
核心协调模块
"""

from pathlib import Path
from typing import Any, Dict

# 导入配置
import sys

TOOLS_DIR = Path(__file__).parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

try:
    from lib.config import JOURNALS_DIR
except ImportError:
    # 回退到项目目录（用于开发测试）
    PROJECT_ROOT = Path(__file__).parent.parent
    JOURNALS_DIR = PROJECT_ROOT / "journals"

# 导入子模块
from .utils import get_year_month, generate_filename, get_next_sequence
from .frontmatter import format_frontmatter, format_content
from .attachments import extract_file_paths_from_content, process_attachments
from .weather import query_weather_for_location, normalize_location
from .index_updater import (
    update_topic_index,
    update_project_index,
    update_tag_indices,
    update_monthly_abstract,
)


def write_journal(data: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    """
    写入日志的主函数
    自动处理默认值和天气查询

    Returns:
        {
            "success": bool,
            "journal_path": str,
            "updated_indices": [str],
            "attachments_processed": [dict],
            "location_used": str,
            "weather_used": str,
            "weather_auto_filled": bool,
            "needs_confirmation": bool,
            "confirmation_message": str,
            "error": str (optional)
        }
    """
    result: Dict[str, Any] = {
        "success": False,
        "journal_path": None,
        "updated_indices": [],
        "attachments_processed": [],
        "location_used": "",
        "weather_used": "",
        "weather_auto_filled": False,
        "needs_confirmation": False,
        "confirmation_message": "",
        "error": None,
    }

    try:
        # 验证必需字段
        date_str = data.get("date")
        if not date_str:
            raise ValueError("缺少必需字段: date")

        # ===== 第一层：用户提及为准 =====
        # 如果用户提供了地点和天气，直接使用

        # ===== 第二层：自动填充 =====
        # 处理地点：如果未提供，使用默认值
        location = data.get("location", "").strip()
        if not location:
            location = "Chongqing, China"  # 默认地点
            result["location_used"] = location
            # 天气查询用同一格式
            location_for_weather = normalize_location("")
        else:
            # 规范化地点（处理城市级别输入）
            location_for_weather = normalize_location(location)
            result["location_used"] = location
        data["location"] = location

        # 处理天气：如果未提供，自动查询
        weather = data.get("weather", "").strip()
        if not weather:
            # 尝试获取天气（使用英文格式的地点）
            queried_weather = query_weather_for_location(location_for_weather, date_str)
            if queried_weather:
                weather = queried_weather
                result["weather_used"] = weather
                result["weather_auto_filled"] = True
            else:
                weather = ""
                result["weather_used"] = ""
        else:
            result["weather_used"] = weather

        data["weather"] = weather

        # 获取年月和序列号
        year, month = get_year_month(date_str)
        sequence = get_next_sequence(date_str)

        # 构建路径
        month_dir = JOURNALS_DIR / str(year) / f"{month:02d}"
        filename = generate_filename(date_str, sequence)
        journal_path = month_dir / filename

        # 从内容中自动检测文件路径
        content = data.get("content", "")
        auto_detected_paths = extract_file_paths_from_content(content)

        # 处理附件（显式附件 + 自动检测附件）
        attachments = data.get("attachments", [])
        processed_attachments = process_attachments(
            attachments, date_str, dry_run, auto_detected_paths
        )
        result["attachments_processed"] = processed_attachments

        # 更新数据中的附件信息（用于生成内容）
        data["attachments"] = processed_attachments

        # 生成内容
        frontmatter = format_frontmatter(data)
        content = format_content(data)
        full_content = f"{frontmatter}\n\n{content}"

        if dry_run:
            result["journal_path"] = str(journal_path)
            result["content_preview"] = full_content[:500]
            result["success"] = True
            return result

        # 创建目录并写入文件
        month_dir.mkdir(parents=True, exist_ok=True)
        with open(journal_path, "w", encoding="utf-8") as f:
            f.write(full_content)

        # 更新月度摘要（在写入文件后调用，确保包含当前日志）
        try:
            abstract_result = update_monthly_abstract(year, month, dry_run)
            result["monthly_abstract_updated"] = abstract_result
        except Exception as e:
            # 月度摘要更新失败不应影响主流程
            result["monthly_abstract_error"] = str(e)

        result["journal_path"] = str(journal_path)

        # 更新索引
        topic = data.get("topic")
        if topic:
            indices = update_topic_index(topic, journal_path, data)
            result["updated_indices"].extend([str(i) for i in indices])

        project = data.get("project")
        if project:
            idx = update_project_index(project, journal_path, data)
            if idx:
                result["updated_indices"].append(str(idx))

        tags = data.get("tags", [])
        if tags:
            indices = update_tag_indices(tags, journal_path, data)
            result["updated_indices"].extend([str(i) for i in indices])

        result["success"] = True

        # ===== 第三层：写入后确认 =====
        result["needs_confirmation"] = True
        result["confirmation_message"] = (
            f"日志已保存至：{journal_path}\n\n"
            f"当前记录信息：\n"
            f"- 地点：{location}\n"
            f"- 天气：{weather if weather else '（未获取）'}\n\n"
            f"请确认以上信息是否正确。如需修改，请告诉我新的地点或天气信息，"
            f"我将为您更新日志文件。"
        )

    except Exception as e:
        result["error"] = str(e)

    return result
