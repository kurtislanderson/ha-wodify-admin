"""Asynchronous client for the Wodify public API used by the integration."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp

from .const import API_BASE_URL, API_RATE_LIMIT_CALLS, API_TIMEOUT
from .models import WodifyClass

_LOGGER = logging.getLogger(__name__)

# Maximum page size supported by the API
API_MAX_PAGE_SIZE = 100


class ApiError(Exception):
    """Raised when the Wodify API returns an unexpected response."""


class ApiAuthError(ApiError):
    """Raised when authentication with the Wodify API fails."""


class WodifyAPI:
    """Small async API wrapper used by the tests and coordinator."""

    _DEFAULT_DEBOUNCE = max(0.1, 60 / API_RATE_LIMIT_CALLS)
    _MAX_RETRIES = 3
    _BACKOFF_START = 0.5

    def __init__(
        self,
        api_key: str,
        session: aiohttp.ClientSession,
        hass=None,
    ) -> None:
        """Initialise the client."""
        self.api_key = api_key
        self.base_url = API_BASE_URL
        self._session = session
        self._hass = hass
        self._last_request_time = 0.0
        self._request_lock = asyncio.Lock()

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------
    async def get_class(self, class_id: str | int) -> dict[str, Any] | None:
        """Fetch a single class by ID with full details including coaches.

        Returns None if the class is not found.
        """
        try:
            return await self._make_request(f"classes/{class_id}")
        except ApiError as err:
            if "404" in str(err):
                return None
            raise

    async def get_programs(self) -> list[dict[str, Any]]:
        """Return the list of programs available for the account.

        Handles both legacy list response and new paginated format.
        """
        return await self._get_all_pages("programs", "programs")

    async def search_classes(
        self,
        *,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        location_names: Iterable[str] | None = None,
        program_names: Iterable[str] | None = None,
    ) -> list[WodifyClass]:
        """Search for classes using the /classes/search endpoint.

        Uses the Wodify search query syntax: field|operator|value
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=1)
        if end_date is None:
            end_date = datetime.now(UTC) + timedelta(days=7)

        # Build search query using Wodify's pipe syntax
        # Format: field|operator|value (no quotes around datetime values)
        start_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        query = f"start_date_time|gte|{start_str};start_date_time|lte|{end_str}"

        # Use _search_classes_paginated to handle the special q parameter
        raw_classes = await self._search_classes_paginated(query)

        classes: list[WodifyClass] = []
        for item in raw_classes:
            try:
                wc = WodifyClass.from_api_response(item)
                # Apply location/program filters client-side
                if location_names and wc.location_name not in location_names:
                    continue
                if program_names and wc.program_name not in program_names:
                    continue
                classes.append(wc)
            except ValueError as err:
                _LOGGER.debug("Skipping invalid class payload: %s", err)

        # Sort chronologically
        classes.sort(key=lambda c: c.start_time)
        return classes

    # ------------------------------------------------------------------
    # Search helper for /classes/search endpoint
    # ------------------------------------------------------------------
    async def _search_classes_paginated(
        self,
        query: str,
    ) -> list[dict[str, Any]]:
        """Fetch all pages from the /classes/search endpoint.

        This method builds the URL manually to avoid double-encoding the query.
        """
        from urllib.parse import quote

        all_items: list[dict[str, Any]] = []
        page = 1
        max_pages = 100

        encoded_query = quote(query)

        while page <= max_pages:
            # Build URL manually to control encoding
            # Note: /classes/search doesn't support sort parameter
            url = (
                f"{self.base_url}/classes/search"
                f"?q={encoded_query}"
                f"&page={page}"
                f"&page_size={API_MAX_PAGE_SIZE}"
            )

            await self._apply_rate_limit()
            payload = await self._execute_request(url)

            if not isinstance(payload, dict):
                break

            if "APIError" in payload or "HTTPCode" in payload:
                error_msg = payload.get("UserMessage", payload.get("DeveloperMessage", "Unknown error"))
                _LOGGER.warning("Search API error: %s", error_msg)
                break

            items = payload.get("classes", [])
            if isinstance(items, list):
                all_items.extend(items)

            pagination = payload.get("pagination", {})
            if not pagination.get("has_more", False):
                break

            page += 1

        return all_items

    # ------------------------------------------------------------------
    # Pagination helper
    # ------------------------------------------------------------------
    async def _get_all_pages(
        self,
        endpoint: str,
        data_key: str,
        extra_params: dict[str, Any] | None = None,
        max_pages: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch all pages of a paginated endpoint.

        Handles both:
        - Legacy format: returns list directly
        - New format: returns {"<data_key>": [...], "pagination": {...}}

        Args:
            endpoint: API endpoint to call
            data_key: Key in response dict containing the data list
            extra_params: Additional query parameters
            max_pages: Maximum number of pages to fetch (safety limit)
        """
        all_items: list[dict[str, Any]] = []
        page = 1

        while page <= max_pages:
            params: dict[str, Any] = {
                "page": page,
                "page_size": API_MAX_PAGE_SIZE,
            }
            if extra_params:
                params.update(extra_params)

            payload = await self._make_request(endpoint, params=params)

            # Handle legacy list response format
            if isinstance(payload, list):
                all_items.extend(payload)
                break

            # Handle dictionary response with data key
            if not isinstance(payload, dict):
                _LOGGER.warning("Unexpected response type from %s: %s", endpoint, type(payload))
                break

            # Check for API error in response
            if "APIError" in payload:
                error_msg = payload["APIError"].get("ErrorMessage", "Unknown error")
                raise ApiError(f"API error: {error_msg}")

            # Extract items from response
            items = payload.get(data_key, [])
            if isinstance(items, list):
                all_items.extend(items)
            elif items is not None:
                _LOGGER.debug("Unexpected data format in %s: %s", data_key, type(items))

            # Check pagination for more pages
            pagination = payload.get("pagination", {})
            has_more = pagination.get("has_more", False)
            if not has_more:
                break

            page += 1

        if page > max_pages:
            _LOGGER.warning("Pagination safety limit reached for %s", endpoint)

        return all_items

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _make_request(
        self, endpoint: str, *, params: dict[str, Any] | None = None
    ) -> Any:
        """Rate limit and execute a request with retry logic."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        attempt = 0
        backoff = self._BACKOFF_START
        while True:
            attempt += 1
            await self._apply_rate_limit()
            try:
                return await self._execute_request(url, params=params)
            except ApiAuthError:
                raise
            except ApiError:
                raise
            except aiohttp.ClientError as err:
                if attempt >= self._MAX_RETRIES:
                    raise ApiError(f"Request failed: {err}") from err
                sleep_for = backoff + random.uniform(0, backoff / 2)
                _LOGGER.debug(
                    "Retrying request to %s after error: %s (attempt %s)",
                    url,
                    err,
                    attempt,
                )
                await asyncio.sleep(sleep_for)
                backoff *= 2

    async def _apply_rate_limit(self) -> None:
        """Ensure subsequent requests are slightly delayed (simple debouncer)."""
        async with self._request_lock:
            if self._hass and hasattr(self._hass, "loop"):
                loop = self._hass.loop
            else:
                loop = asyncio.get_event_loop()
            now = loop.time()
            elapsed = now - self._last_request_time
            if elapsed < self._DEFAULT_DEBOUNCE:
                await asyncio.sleep(self._DEFAULT_DEBOUNCE - elapsed)
                now = loop.time()
            self._last_request_time = now

    async def _execute_request(
        self, url: str, *, params: dict[str, Any] | None = None
    ) -> Any:
        """Perform the HTTP request and return decoded JSON."""
        headers = {"x-api-key": self.api_key}
        try:
            async with self._session.get(
                url,
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=API_TIMEOUT),
            ) as resp:
                if resp.status == 401:
                    raise ApiAuthError("Unauthorized - invalid API key")
                if resp.status == 403:
                    raise ApiAuthError("Forbidden - API key not authorized")
                if resp.status == 429:
                    raise ApiError("Rate limit exceeded")
                if resp.status >= 400:
                    text = await resp.text()
                    raise ApiError(f"Error {resp.status}: {text}")
                try:
                    return await resp.json()
                except aiohttp.ContentTypeError as err:
                    raise ApiError(f"Failed to parse response: {err}") from err
                except ValueError as err:
                    raise ApiError(f"Failed to parse response: {err}") from err
        except TimeoutError as err:
            raise ApiError(f"Request timeout after {API_TIMEOUT} seconds") from err


__all__ = ["ApiAuthError", "ApiError", "WodifyAPI"]
