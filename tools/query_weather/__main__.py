#!/usr/bin/env python3
"""
Life Index - Query Weather Tool - CLI Entry Point
查询指定日期和地点的天气信息 (使用 Open-Meteo API)
"""

import argparse
import json
import sys
from datetime import datetime

import tools.query_weather as _qw
from ..lib.config import ensure_dirs
from ..lib.errors import ErrorCode, create_error_response


def _emit_json(payload: dict) -> None:
    """Print JSON safely across Windows console encodings."""
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        fallback_text = json.dumps(payload, ensure_ascii=True, indent=2)
        print(fallback_text)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Life Index - Query Weather Tool (Open-Meteo)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m tools.query_weather --location "Lagos"
    python -m tools.query_weather --location "Beijing,China" --date 2026-03-04
    python -m tools.query_weather --lat 6.5244 --lon 3.3792 --date 2026-03-04
    python -m tools.query_weather --location "Paris" --format simple
        """,
    )

    parser.add_argument("--location", help='地点名称 (如 "Lagos", "Beijing,China")')

    parser.add_argument("--lat", type=float, help="纬度")

    parser.add_argument("--lon", type=float, help="经度")

    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="日期 (YYYY-MM-DD), 默认今天",
    )

    parser.add_argument(
        "--format", choices=["detailed", "simple"], default="detailed", help="输出格式"
    )

    parser.add_argument("--timezone", default="auto", help="时区 (默认 auto)")

    args = parser.parse_args()
    ensure_dirs()

    # 验证参数
    if not args.location and (args.lat is None or args.lon is None):
        _emit_json(
            create_error_response(
                ErrorCode.INVALID_INPUT,
                "必须提供 --location 或 --lat/--lon",
            )
        )
        sys.exit(1)

    # 获取坐标（通过模块引用以允许测试中的 monkey-patching）
    if args.location:
        geo_result = _qw.geocode_location(args.location)
        if geo_result is None:
            _emit_json(
                create_error_response(
                    ErrorCode.LOCATION_NOT_FOUND,
                    f"无法找到地点: {args.location}",
                    details={"location": args.location},
                )
            )
            sys.exit(1)
        if "error" in geo_result:
            _emit_json(
                create_error_response(
                    ErrorCode.WEATHER_API_FAILED,
                    f"地理编码错误: {geo_result['error']}",
                    details={
                        "location": args.location,
                        "geo_error": geo_result["error"],
                    },
                )
            )
            sys.exit(1)

        latitude = geo_result["latitude"]
        longitude = geo_result["longitude"]
        location_name = f"{geo_result['name']}, {geo_result.get('admin1', '')}, {geo_result['country']}".strip(
            ", "
        )
    else:
        latitude = args.lat
        longitude = args.lon
        location_name = f"{latitude}, {longitude}"

    # 查询天气（通过模块引用）
    result = _qw.query_weather(latitude, longitude, args.date, args.timezone)
    result["location_name"] = location_name

    # 格式化输出
    if args.format == "simple" and result["success"]:
        simple_output = {
            "success": True,
            "location": location_name,
            "date": args.date,
            "weather": result["weather"].get("simple", "未知"),
            "temp_high": result["weather"].get("temperature_max"),
            "temp_low": result["weather"].get("temperature_min"),
        }
        print(json.dumps(simple_output, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
