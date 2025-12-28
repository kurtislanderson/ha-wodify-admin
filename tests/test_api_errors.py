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
