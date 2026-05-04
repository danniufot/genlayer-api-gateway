"""
Tests for ApiGateway Intelligent Contract
==========================================
Run with:  genlayer test
Or:        pytest tests/test_api_gateway.py  (with genlayer-test installed)
"""

import pytest
from genlayer.test import ContractRunner, mock_get_webpage


CONTRACT_PATH = "contracts/api_gateway.py"

OWNER   = "0xOwner000000000000000000000000000000000001"
CALLER  = "0xCaller00000000000000000000000000000000002"
HACKER  = "0xHacker00000000000000000000000000000000003"

WEATHER_RESP = '{"weather":[{"description":"clear sky"}],"main":{"temp":22.5},"name":"Lagos"}'
PRICE_RESP   = '{"bitcoin":{"usd":62350.12}}'


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def runner():
    r = ContractRunner(CONTRACT_PATH, constructor_args=[OWNER])
    return r


@pytest.fixture
def configured_runner(runner):
    """Runner with weather + coingecko services registered and CALLER approved."""
    runner.call_write(
        "register_service",
        args=["weather", "https://api.openweathermap.org/data/2.5", "FAKE_KEY_123", 100],
        sender=OWNER,
    )
    runner.call_write(
        "register_service",
        args=["coingecko", "https://api.coingecko.com/api/v3", "", 200],
        sender=OWNER,
    )
    runner.call_write("approve_caller", args=[CALLER], sender=OWNER)
    return runner


# ── owner guard tests ─────────────────────────────────────────────────────────

def test_only_owner_can_register(runner):
    with pytest.raises(Exception, match="not the owner"):
        runner.call_write(
            "register_service",
            args=["weather", "https://example.com", "key", 50],
            sender=HACKER,
        )


def test_only_owner_can_approve(runner):
    with pytest.raises(Exception, match="not the owner"):
        runner.call_write("approve_caller", args=[CALLER], sender=HACKER)


# ── registration tests ────────────────────────────────────────────────────────

def test_register_service(configured_runner):
    info = configured_runner.call_view("get_service_info", args=["weather"])
    assert info["enabled"] is True
    assert info["daily_limit"] == 100
    assert "openweathermap" in info["base_url"]


def test_list_services(configured_runner):
    services = configured_runner.call_view("list_services")
    assert "weather" in services
    assert "coingecko" in services


def test_api_key_not_exposed_in_view(configured_runner):
    """The API key must never appear in view method output."""
    info = configured_runner.call_view("get_service_info", args=["weather"])
    info_str = str(info)
    assert "FAKE_KEY_123" not in info_str


def test_disable_enable_service(configured_runner):
    configured_runner.call_write("disable_service", args=["weather"], sender=OWNER)
    info = configured_runner.call_view("get_service_info", args=["weather"])
    assert info["enabled"] is False

    configured_runner.call_write("enable_service", args=["weather"], sender=OWNER)
    info = configured_runner.call_view("get_service_info", args=["weather"])
    assert info["enabled"] is True


# ── caller approval tests ─────────────────────────────────────────────────────

def test_approved_caller(configured_runner):
    assert configured_runner.call_view("is_caller_approved", args=[CALLER]) is True


def test_unapproved_caller_blocked(configured_runner):
    with pytest.raises(Exception, match="not approved"):
        with mock_get_webpage(WEATHER_RESP):
            configured_runner.call_write(
                "fetch_weather", args=["Lagos"], sender=HACKER
            )


# ── weather fetch tests ───────────────────────────────────────────────────────

def test_fetch_weather_success(configured_runner):
    with mock_get_webpage(WEATHER_RESP):
        result = configured_runner.call_write(
            "fetch_weather", args=["Lagos"], sender=CALLER
        )
    assert result["success"] is True
    assert "temp" in result["data"]
    assert result["service"] == "weather"


def test_fetch_weather_increments_counter(configured_runner):
    with mock_get_webpage(WEATHER_RESP):
        configured_runner.call_write("fetch_weather", args=["Lagos"], sender=CALLER)

    info = configured_runner.call_view("get_service_info", args=["weather"])
    assert info["calls_today"] == 1

    count = configured_runner.call_view("get_call_count", args=[CALLER])
    assert count == 1


# ── crypto price tests ────────────────────────────────────────────────────────

def test_fetch_crypto_price(configured_runner):
    with mock_get_webpage(PRICE_RESP):
        result = configured_runner.call_write(
            "fetch_crypto_price", args=["bitcoin"], sender=CALLER
        )
    assert result["success"] is True
    assert "62350" in result["data"]


# ── rate-limit test ───────────────────────────────────────────────────────────

def test_daily_rate_limit(runner):
    """Register a service with limit=2 and verify the 3rd call is blocked."""
    runner.call_write(
        "register_service",
        args=["tiny", "https://example.com/api", "", 2],
        sender=OWNER,
    )
    runner.call_write("approve_caller", args=[CALLER], sender=OWNER)

    with mock_get_webpage('{"ok":true}'):
        runner.call_write("fetch_custom", args=["tiny", "/data"], sender=CALLER)
        runner.call_write("fetch_custom", args=["tiny", "/data"], sender=CALLER)
        result = runner.call_write("fetch_custom", args=["tiny", "/data"], sender=CALLER)

    assert result["success"] is False
    assert "rate limit" in result["data"].lower()


def test_reset_daily_counts(runner):
    runner.call_write(
        "register_service",
        args=["tiny", "https://example.com/api", "", 1],
        sender=OWNER,
    )
    runner.call_write("approve_caller", args=[CALLER], sender=OWNER)

    with mock_get_webpage('{"ok":true}'):
        runner.call_write("fetch_custom", args=["tiny", "/data"], sender=CALLER)

    runner.call_write("reset_daily_counts", sender=OWNER)
    info = runner.call_view("get_service_info", args=["tiny"])
    assert info["calls_today"] == 0


# ── disabled service test ─────────────────────────────────────────────────────

def test_disabled_service_returns_error(configured_runner):
    configured_runner.call_write("disable_service", args=["weather"], sender=OWNER)
    with mock_get_webpage(WEATHER_RESP):
        result = configured_runner.call_write(
            "fetch_weather", args=["Lagos"], sender=CALLER
        )
    assert result["success"] is False
    assert "disabled" in result["data"].lower()


# ── unknown service test ──────────────────────────────────────────────────────

def test_unknown_service_returns_error(configured_runner):
    result = configured_runner.call_write(
        "fetch_custom", args=["nonexistent", "/foo"], sender=CALLER
    )
    assert result["success"] is False
    assert "Unknown service" in result["data"]
