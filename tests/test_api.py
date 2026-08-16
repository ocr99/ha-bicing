"""Tests for the Bicing API helpers."""

from custom_components.bicing.lib.bike_stations_api import BikeStationApi


def test_retry_after_is_parsed_and_sanitized() -> None:
    assert BikeStationApi._get_retry_after({"Retry-After": "10"}) == 10
    assert BikeStationApi._get_retry_after({"Retry-After": "999999"}) == 3600
    assert BikeStationApi._get_retry_after({"Retry-After": "invalid"}, default=30) == 30
    assert BikeStationApi._get_retry_after({}, default=30) == 30
