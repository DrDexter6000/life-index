#!/usr/bin/env python3
"""
Life Index - Write Journal Tool - Weather
天气查询模块
"""

import json
import subprocess
import sys
from pathlib import Path

# 导入配置
import sys

TOOLS_DIR = Path(__file__).parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def normalize_location(location: str) -> str:
    """
    规范化地点名称，处理城市级别输入
    例如："重庆" -> "Chongqing, China"（返回英文格式以便天气查询）
    """
    if not location:
        return "Chongqing, China"

    location = location.strip()

    # 中文城市名到英文的映射（用于天气查询）
    chinese_to_english = {
        "重庆": "Chongqing, China",
        "北京": "Beijing, China",
        "上海": "Shanghai, China",
        "广州": "Guangzhou, China",
        "深圳": "Shenzhen, China",
        "成都": "Chengdu, China",
        "杭州": "Hangzhou, China",
        "武汉": "Wuhan, China",
        "西安": "Xi'an, China",
        "南京": "Nanjing, China",
        "重庆，中国": "Chongqing, China",
        "北京，中国": "Beijing, China",
        "上海，中国": "Shanghai, China",
        "广州，中国": "Guangzhou, China",
        "深圳，中国": "Shenzhen, China",
        "成都，中国": "Chengdu, China",
        "杭州，中国": "Hangzhou, China",
        "武汉，中国": "Wuhan, China",
        "西安，中国": "Xi'an, China",
        "南京，中国": "Nanjing, China",
    }

    # 如果已经是中文城市名，直接返回英文格式
    if location in chinese_to_english:
        return chinese_to_english[location]

    # 如果包含逗号，检查是否是中文格式
    if "，" in location:
        city = location.split("，")[0].strip()
        if city in chinese_to_english:
            return chinese_to_english[city]
        return location.replace("，", ", ")

    # 如果已经是英文格式（包含逗号），直接返回
    if "," in location:
        return location

    # 其他中文城市名（不在映射表中），默认添加 China
    if any("\u4e00" <= char <= "\u9fff" for char in location):
        return f"{location}, China"

    return location


def query_weather_for_location(location: str, date_str: str = "") -> str:
    """
    调用 query_weather.py 工具获取天气信息

    Args:
        location: 地点名称
        date_str: 日期字符串（可选，用于历史天气查询）

    Returns:
        天气描述字符串（包含温度），失败返回空字符串
    """
    try:
        cmd = [
            sys.executable,
            str(TOOLS_DIR / "query_weather.py"),
            "--location",
            location,
        ]
        if date_str:
            cmd.extend(["--date", date_str[:10]])

        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", timeout=15
        )

        if proc.returncode == 0:
            output = json.loads(proc.stdout)
            # 提取天气描述（处理嵌套结构）
            if isinstance(output, dict):
                weather_data = output.get("weather", {})
                if isinstance(weather_data, dict):
                    # 构建完整天气描述：描述 + 温度
                    description = weather_data.get("description", "")
                    simple = weather_data.get("simple", "")
                    temp_max = weather_data.get("temperature_max")
                    temp_min = weather_data.get("temperature_min")

                    # 组装天气描述
                    parts = []
                    if description:
                        parts.append(description)
                    elif simple:
                        parts.append(simple)

                    # 添加温度信息
                    if temp_max is not None and temp_min is not None:
                        parts.append(f"{temp_max}°C/{temp_min}°C")
                    elif temp_max is not None:
                        parts.append(f"{temp_max}°C")

                    return " ".join(parts) if parts else ""
                elif isinstance(weather_data, str):
                    return weather_data
                elif "description" in output:
                    return output["description"]
        return ""
    except (KeyError, ValueError, TypeError):
        return ""
        return ""
