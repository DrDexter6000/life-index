#!/usr/bin/env python3
"""
Life Index - Query Weather Tool
查询指定日期和地点的天气信息 (使用 Open-Meteo API)

Usage:
    python -m tools.query_weather --location "Lagos" --date 2026-03-04
    python -m tools.query_weather --lat 6.5244 --lon 3.3792 --date 2026-03-04

Public API:
    from tools.query_weather import query_weather, geocode_location, reverse_geocode_location
    result = query_weather(latitude=6.52, longitude=3.38, date="2026-03-04")
    location = reverse_geocode_location(6.52, 3.38)
"""

import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from typing import Dict, Optional, Any

from ..lib.logger import get_logger
from ..lib.errors import ErrorCode, create_error_response

logger = get_logger(__name__)

# Open-Meteo API 端点
GEOCODING_API = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_API = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_API = "https://api.open-meteo.com/v1/forecast"

# Nominatim reverse geocoding API
REVERSE_GEOCODE_API = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "life-index/1.0"


def _geocode_single(location: str) -> Optional[Dict[str, Any]]:
    """执行单次地点 geocode 请求。"""
    try:
        params = urllib.parse.urlencode(
            {"name": location, "count": 5, "language": "en", "format": "json"}
        )
        url = f"{GEOCODING_API}?{params}"

        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        if not data.get("results"):
            logger.debug(f"No results found for location: {location}")
            return None

        # 返回第一个结果
        result = data["results"][0]
        loc_name = result.get("name")
        loc_lat = result.get("latitude")
        loc_lon = result.get("longitude")
        logger.debug(f"Geocoded location: {loc_name} ({loc_lat}, {loc_lon})")
        return {
            "name": result.get("name", ""),
            "latitude": result.get("latitude", 0),
            "longitude": result.get("longitude", 0),
            "country": result.get("country", ""),
            "admin1": result.get("admin1", ""),
        }

    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        json.JSONDecodeError,
        TimeoutError,
    ) as e:
        logger.error(f"Geocoding failed: {e}")
        # Return structured error response
        return create_error_response(
            ErrorCode.LOCATION_NOT_FOUND,
            f"无法找到地点：{location}",
            {"location": location, "error": str(e)},
            "请检查地点名称是否正确，或使用英文格式（如 'Beijing,China'）",
        )


def geocode_location(location: str) -> Optional[Dict[str, Any]]:
    """
    将地点名称转换为经纬度

    Returns:
        {
            "name": str,
            "latitude": float,
            "longitude": float,
            "country": str,
            "admin1": str (省份/州)
        }
    """
    parts = [part.strip() for part in location.split(",") if part.strip()]
    candidates = [", ".join(parts[index:]) for index in range(len(parts))]

    seen: set[str] = set()
    deduped_candidates: list[str] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped_candidates.append(candidate)

    for candidate in deduped_candidates:
        result = _geocode_single(candidate)
        if result:
            return result

    return None


def parse_coordinate_location(value: str) -> tuple[float, float] | None:
    """Parse a `lat, lon` text value to tuple.

    Handles:
    - "6.5244, 3.3792" (half-width comma)
    - "6.5244，3.3792" (full-width comma)

    Args:
        value: Coordinate string in "lat, lon" format

    Returns:
        (latitude, longitude) tuple or None if parsing fails
    """
    normalized = value.replace("，", ",")
    parts = [part.strip() for part in normalized.split(",")]
    if len(parts) != 2:
        return None
    try:
        latitude = float(parts[0])
        longitude = float(parts[1])
    except ValueError:
        return None
    return latitude, longitude


def reverse_geocode_location(latitude: float, longitude: float) -> Dict[str, Any]:
    """Resolve coordinates to a human-readable location string.

    Uses Nominatim OpenStreetMap API for reverse geocoding.

    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate

    Returns:
        {
            "success": bool,
            "location": str | None,  # e.g., "Lagos, Nigeria"
            "error": str | None,
            "address": dict | None,  # Full address details
        }

    Example:
        >>> result = reverse_geocode_location(6.5244, 3.3792)
        >>> result["location"]
        'Lagos, Nigeria'
    """
    params = urllib.parse.urlencode(
        {
            "lat": latitude,
            "lon": longitude,
            "format": "jsonv2",
            "addressdetails": 1,
            "accept-language": "en",
        }
    )
    request = urllib.request.Request(
        f"{REVERSE_GEOCODE_API}?{params}",
        headers={"User-Agent": USER_AGENT},
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        logger.warning(f"Reverse geocoding failed: {exc}")
        return {
            "success": False,
            "location": None,
            "error": f"地点解析失败：{exc}",
            "address": None,
        }
    except json.JSONDecodeError:
        return {
            "success": False,
            "location": None,
            "error": "地点解析失败：响应格式无效",
            "address": None,
        }

    address = payload.get("address")
    if not isinstance(address, dict):
        return {
            "success": False,
            "location": None,
            "error": "地点解析失败",
            "address": None,
        }

    # Extract city and country
    city = str(
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("state")
        or ""
    ).strip()
    country = str(address.get("country") or "").strip()
    parts = [part for part in [city, country] if part]
    location = ", ".join(parts)

    if not location:
        location = str(payload.get("display_name") or "").strip()

    if not location:
        return {
            "success": False,
            "location": None,
            "error": "地点解析失败",
            "address": None,
        }

    logger.debug(f"Reverse geocoded ({latitude}, {longitude}) -> {location}")
    return {
        "success": True,
        "location": location,
        "error": None,
        "address": address,
    }


def get_weather_code_description(code: int) -> str:
    """将 WMO Weather interpretation codes 转换为描述"""
    codes = {
        0: "Clear sky (晴朗)",
        1: "Mainly clear (大部晴朗)",
        2: "Partly cloudy (多云)",
        3: "Overcast (阴天)",
        45: "Fog (雾)",
        48: "Depositing rime fog (雾凇)",
        51: "Light drizzle (毛毛雨)",
        53: "Moderate drizzle (中雨)",
        55: "Dense drizzle (大雨)",
        61: "Slight rain (小雨)",
        63: "Moderate rain (中雨)",
        65: "Heavy rain (大雨)",
        71: "Slight snow (小雪)",
        73: "Moderate snow (中雪)",
        75: "Heavy snow (大雪)",
        77: "Snow grains (雪粒)",
        80: "Slight rain showers (阵雨)",
        81: "Moderate rain showers (中阵雨)",
        82: "Violent rain showers (强阵雨)",
        85: "Slight snow showers (阵雪)",
        86: "Heavy snow showers (强阵雪)",
        95: "Thunderstorm (雷雨)",
        96: "Thunderstorm with slight hail (雷雨伴小冰雹)",
        99: "Thunderstorm with heavy hail (雷雨伴大冰雹)",
    }
    return codes.get(code, f"Unknown weather code: {code}")


def simplify_weather(description: str) -> str:
    """简化天气描述为常用词汇"""
    description_lower = description.lower()

    if any(word in description_lower for word in ["clear", "sunny"]):
        return "晴天"
    elif any(word in description_lower for word in ["partly cloudy", "cloudy"]):
        return "多云"
    elif any(word in description_lower for word in ["overcast"]):
        return "阴天"
    elif any(word in description_lower for word in ["rain", "drizzle", "shower"]):
        return "雨天"
    elif any(word in description_lower for word in ["snow"]):
        return "雪天"
    elif any(word in description_lower for word in ["fog", "mist"]):
        return "雾天"
    elif any(word in description_lower for word in ["thunder"]):
        return "雷雨"
    else:
        return "未知"


def query_weather(
    latitude: float, longitude: float, date: str, timezone: str = "auto"
) -> Dict[str, Any]:
    """
    查询指定坐标和日期的天气

    Args:
        latitude: 纬度
        longitude: 经度
        date: 日期 (YYYY-MM-DD)
        timezone: 时区

    Returns:
        {
            "success": bool,
            "date": str,
            "location": {"lat": float, "lon": float},
            "weather": {
                "code": int,
                "description": str,
                "simple": str,
                "temperature_max": float,
                "temperature_min": float,
                "precipitation": float
            },
            "error": str (optional)
        }
    """
    result = {
        "success": False,
        "date": date,
        "location": {"lat": latitude, "lon": longitude},
        "weather": {},
        "error": None,
    }

    try:
        # 判断是历史数据还是未来预报
        query_date = datetime.strptime(date, "%Y-%m-%d").date()
        today = datetime.now().date()

        # Open-Meteo archive API 支持到昨天，今天及以后用 forecast
        if query_date < today:
            api_url = WEATHER_API
        else:
            api_url = FORECAST_API

        params = urllib.parse.urlencode(
            {
                "latitude": latitude,
                "longitude": longitude,
                "start_date": date,
                "end_date": date,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": timezone,
            }
        )

        url = f"{api_url}?{params}"

        with urllib.request.urlopen(url, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        daily = data.get("daily", {})

        if not daily or not daily.get("weather_code"):
            logger.warning(
                f"No weather data available for {date} at ({latitude}, {longitude})"
            )
            result["error"] = "No weather data available for this date"
            return result

        weather_code = daily["weather_code"][0]
        description = get_weather_code_description(weather_code)
        logger.info(f"Weather retrieved for {date}: {description}")

        result["weather"] = {
            "code": weather_code,
            "description": description,
            "simple": simplify_weather(description),
            "temperature_max": daily.get("temperature_2m_max", [None])[0],
            "temperature_min": daily.get("temperature_2m_min", [None])[0],
            "precipitation": daily.get("precipitation_sum", [None])[0],
        }
        result["success"] = True

    except urllib.error.HTTPError as e:
        logger.error(f"Weather API error: {e.code} - {e.reason}")
        return create_error_response(
            ErrorCode.WEATHER_API_FAILED,
            f"天气API错误：{e.code} - {e.reason}",
            {"date": date, "lat": latitude, "lon": longitude},
            "请稍后重试，或手动输入天气信息",
        )
    except urllib.error.URLError as e:
        logger.error(f"Weather network error: {e.reason}")
        return create_error_response(
            ErrorCode.WEATHER_TIMEOUT,
            f"网络错误：{e.reason}",
            {"date": date, "lat": latitude, "lon": longitude},
            "请检查网络连接，或手动输入天气信息",
        )
    except TimeoutError as e:
        logger.error(f"Weather timeout error: {e}")
        return create_error_response(
            ErrorCode.WEATHER_TIMEOUT,
            f"网络错误：{e}",
            {"date": date, "lat": latitude, "lon": longitude},
            "请检查网络连接，或手动输入天气信息",
        )
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error(f"Weather data parsing error: {e}")
        return create_error_response(
            ErrorCode.WEATHER_PARSE_ERROR,
            f"天气数据解析错误：{e}",
            {"date": date, "lat": latitude, "lon": longitude},
            "请手动输入天气信息",
        )

    return result


__all__ = [
    "query_weather",
    "geocode_location",
    "reverse_geocode_location",
    "parse_coordinate_location",
    "get_weather_code_description",
    "simplify_weather",
    "main",
]


def main() -> None:
    """Package-surface compatibility wrapper for CLI entrypoint."""
    from .__main__ import main as cli_main

    cli_main()
