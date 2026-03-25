from web.services.geolocation import _normalize_address


def test_normalize_address_prefers_city_and_country_without_state() -> None:
    result = _normalize_address(
        {
            "city": "Lagos",
            "state": "Lagos State",
            "country": "Nigeria",
        }
    )

    assert result == "Lagos, Nigeria"
