"""Web geolocation helpers."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


REVERSE_GEOCODE_API = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "life-index-web-gui/1.0"


def parse_coordinate_location(value: str) -> tuple[float, float] | None:
    """Parse a `lat, lon` text value emitted by browser geolocation."""
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2:
        return None
    try:
        latitude = float(parts[0])
        longitude = float(parts[1])
    except ValueError:
        return None
    return latitude, longitude


def _normalize_address(address: dict[str, Any]) -> str:
    city = str(
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("county")
        or ""
    ).strip()
    state = str(address.get("state") or address.get("region") or "").strip()
    country = str(address.get("country") or "").strip()
    parts = [part for part in [city, state, country] if part]
    return ", ".join(parts)


def reverse_geocode_coordinates(latitude: float, longitude: float) -> dict[str, Any]:
    """Resolve browser coordinates to a human-readable location string."""
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
        return {"success": False, "location": None, "error": f"地点解析失败：{exc}"}
    except json.JSONDecodeError:
        return {
            "success": False,
            "location": None,
            "error": "地点解析失败：响应格式无效",
        }

    address = payload.get("address")
    if not isinstance(address, dict):
        return {"success": False, "location": None, "error": "地点解析失败"}

    location = _normalize_address(address)
    if not location:
        location = str(payload.get("display_name") or "").strip()
    if not location:
        return {"success": False, "location": None, "error": "地点解析失败"}

    return {"success": True, "location": location, "error": None}
