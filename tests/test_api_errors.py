"""Test API error scenarios."""

import re

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.wodify.api import ApiAuthError, ApiError


class TestAPIErrorHandling:
    """Test API error handling."""

    @pytest.mark.asyncio
    async def test_network_error(self, api_client):
        """Test network error handling."""
        with aioresponses() as mock:
            mock.get(
                re.compile(r"https://api\.wodify\.com/v1/programs\?.*"),
                exception=aiohttp.ClientError("Network error"),
            )

            with pytest.raises(ApiError, match="Request failed"):
                await api_client.get_programs()

    @pytest.mark.asyncio
    async def test_timeout_error(self, api_client):
        """Test timeout error handling."""
        with aioresponses() as mock:
            mock.get(
                re.compile(r"https://api\.wodify\.com/v1/programs\?.*"),
                exception=TimeoutError(),
            )

            with pytest.raises(ApiError, match="timeout"):
                await api_client.get_programs()

    @pytest.mark.asyncio
    async def test_invalid_json_response(self, api_client):
        """Test invalid JSON response handling."""
        with aioresponses() as mock:
            mock.get(
                re.compile(r"https://api\.wodify\.com/v1/programs\?.*"),
                body="not json",
                content_type="application/json",
            )

            with pytest.raises(ApiError, match="Failed to parse response"):
                await api_client.get_programs()

    @pytest.mark.asyncio
    async def test_empty_response(self, api_client):
        """Test empty response handling."""
        with aioresponses() as mock:
            mock.get(
                re.compile(r"https://api\.wodify\.com/v1/programs\?.*"),
                payload={
                    "programs": [],
                    "pagination": {"page": 1, "page_size": 100, "has_more": False},
                },
            )

            result = await api_client.get_programs()
            assert result == []

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, api_client):
        """Test rate limit error handling."""
        with aioresponses() as mock:
            mock.get(
                re.compile(r"https://api\.wodify\.com/v1/programs\?.*"),
                status=429,
                payload={"error": "Rate limit exceeded"},
            )

            with pytest.raises(ApiError, match="Rate limit"):
                await api_client.get_programs()

    @pytest.mark.asyncio
    async def test_server_error_codes(self, api_client):
        """Test various server error codes."""
        error_codes = [500, 502, 503, 504]

        for code in error_codes:
            with aioresponses() as mock:
                mock.get(
                    re.compile(r"https://api\.wodify\.com/v1/programs\?.*"),
                    status=code,
                    payload={"error": f"Server error {code}"},
                )

                with pytest.raises(ApiError):
                    await api_client.get_programs()

    @pytest.mark.asyncio
    async def test_forbidden_error(self, api_client):
        """Test forbidden (403) error handling."""
        with aioresponses() as mock:
            mock.get(
                re.compile(r"https://api\.wodify\.com/v1/programs\?.*"),
                status=403,
                payload={"error": "Forbidden"},
            )

            with pytest.raises(ApiAuthError, match="Forbidden"):
                await api_client.get_programs()

    @pytest.mark.asyncio
    async def test_not_found_error(self, api_client):
        """Test not found (404) error handling."""
        with aioresponses() as mock:
            mock.get(
                re.compile(r"https://api\.wodify\.com/v1/programs\?.*"),
                status=404,
                payload={"error": "Not found"},
            )

            with pytest.raises(ApiError, match="404"):
                await api_client.get_programs()


class TestHttp200ErrorBody:
    """Wodify reports some errors as HTTP 200 with an error body."""

    @pytest.mark.asyncio
    async def test_http_code_401_raises_auth_error(self, api_client):
        body = {
            "HTTPCode": 401,
            "UserMessage": "Unauthorized",
            "ErrorCode": "401",
            "MoreInfo": "Invalid api key.",
        }
        with aioresponses() as mock:
            mock.get(re.compile(r"https://api\.wodify\.com/v1/programs\?.*"), payload=body)
            with pytest.raises(ApiAuthError, match="Invalid api key.*401"):
                await api_client.get_programs()

    @pytest.mark.asyncio
    async def test_http_code_400_raises_api_error(self, api_client):
        body = {"HTTPCode": 400, "DeveloperMessage": "The 'q' URL parameter is missing."}
        with aioresponses() as mock:
            mock.get(re.compile(r"https://api\.wodify\.com/v1/programs\?.*"), payload=body)
            with pytest.raises(ApiError, match="'q' URL parameter.*400") as exc_info:
                await api_client.get_programs()
        assert not isinstance(exc_info.value, ApiAuthError)

    @pytest.mark.asyncio
    async def test_search_error_body_returns_no_classes(self, api_client):
        body = {"HTTPCode": 404, "UserMessage": "No classes found."}
        with aioresponses() as mock:
            mock.get(re.compile(r"https://api\.wodify\.com/v1/classes/search\?.*"), payload=body)
            assert await api_client.search_classes() == []

    @pytest.mark.asyncio
    async def test_search_auth_error_body_raises(self, api_client):
        body = {"HTTPCode": 401, "MoreInfo": "Invalid api key."}
        with aioresponses() as mock:
            mock.get(re.compile(r"https://api\.wodify\.com/v1/classes/search\?.*"), payload=body)
            with pytest.raises(ApiAuthError):
                await api_client.search_classes()

    @pytest.mark.asyncio
    async def test_dict_without_http_code_is_not_error(self, api_client):
        with aioresponses() as mock:
            mock.get(
                re.compile(r"https://api\.wodify\.com/v1/programs\?.*"),
                payload={"programs": [], "pagination": {"has_more": False}},
            )
            assert await api_client.get_programs() == []

    @pytest.mark.asyncio
    async def test_coordinator_auth_failed_on_200_body(self, hass, api_client):
        from homeassistant.exceptions import ConfigEntryAuthFailed

        from custom_components.wodify.coordinator import WodifyDataUpdateCoordinator

        coordinator = WodifyDataUpdateCoordinator(hass, api_client, [], [], 5)
        body = {"HTTPCode": 401, "MoreInfo": "Invalid api key."}
        with aioresponses() as mock:
            mock.get(re.compile(r"https://api\.wodify\.com/v1/classes/search.*"), payload=body)
            with pytest.raises(ConfigEntryAuthFailed):
                await coordinator._async_update_data()
