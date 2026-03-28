import os
import re
import time

import requests
from dotenv import load_dotenv

from agent.models import ToolResult
from agent.tools.base import BaseTool

_BASE_URL = "https://api.stlouisfed.org/fred"
_MAX_RETRIES = 3
_BACKOFF_BASE = 0.5

# Pattern to detect a FRED series ID (uppercase letters, digits, underscores)
_SERIES_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,30}$")


class FredTool(BaseTool):
    @property
    def name(self) -> str:
        return "fred"

    @property
    def description(self) -> str:
        return "Fetch economic data series from the Federal Reserve Economic Data (FRED) API."

    def run(self, query: str, *, force_fail: bool = False) -> ToolResult:
        if force_fail:
            return ToolResult(
                tool_name=self.name,
                query=query,
                content="",
                sources=[],
                success=False,
                error="Synthetic failure triggered by force_fail=True",
            )

        load_dotenv()
        api_key = os.environ.get("FRED_API_KEY")
        if not api_key:
            return ToolResult(
                tool_name=self.name,
                query=query,
                content="",
                sources=[],
                success=False,
                error="FRED_API_KEY is not set. Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html",
            )

        # Decide operation: if query looks like a series ID, fetch observations directly
        stripped = query.strip()
        if _SERIES_ID_RE.match(stripped):
            return self._fetch_observations(stripped, api_key)
        return self._search_series(stripped, api_key)

    def _request_with_retry(self, url: str, params: dict[str, str]) -> requests.Response:
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = requests.get(url, params=params, timeout=10)
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_BACKOFF_BASE * (2**attempt))
        raise last_exc  # type: ignore[misc]

    def _search_series(self, query: str, api_key: str) -> ToolResult:
        resp = self._request_with_retry(
            f"{_BASE_URL}/series/search",
            params={
                "search_text": query,
                "api_key": api_key,
                "file_type": "json",
                "limit": "5",
            },
        )
        data = resp.json()
        series_list = data.get("seriess", [])
        if not series_list:
            return ToolResult(
                tool_name=self.name,
                query=query,
                content="",
                sources=[],
                success=False,
                error=f"No FRED series found for: {query}",
            )

        # Pick the first (most relevant) series and fetch its observations
        top = series_list[0]
        series_id: str = top["id"]
        return self._fetch_observations(series_id, api_key, series_meta=top)

    def _fetch_observations(
        self,
        series_id: str,
        api_key: str,
        series_meta: dict[str, str] | None = None,
    ) -> ToolResult:
        # If we don't have metadata yet, fetch series info first
        if series_meta is None:
            info_resp = self._request_with_retry(
                f"{_BASE_URL}/series",
                params={
                    "series_id": series_id,
                    "api_key": api_key,
                    "file_type": "json",
                },
            )
            info_data = info_resp.json()
            series_list = info_data.get("seriess", [])
            if not series_list:
                return ToolResult(
                    tool_name=self.name,
                    query=series_id,
                    content="",
                    sources=[],
                    success=False,
                    error=f"FRED series not found: {series_id}",
                )
            series_meta = series_list[0]

        obs_resp = self._request_with_retry(
            f"{_BASE_URL}/series/observations",
            params={
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": "12",
            },
        )
        obs_data = obs_resp.json()
        observations = obs_data.get("observations", [])

        title = series_meta.get("title", series_id)
        units = series_meta.get("units", "N/A")
        frequency = series_meta.get("frequency", "N/A")

        # Build a readable table of observations
        lines = [
            f"# {title}",
            f"**Series ID:** {series_id}",
            f"**Units:** {units}",
            f"**Frequency:** {frequency}",
            "",
            "| Date       | Value |",
            "|------------|-------|",
        ]
        for obs in observations:
            date = obs.get("date", "")
            value = obs.get("value", ".")
            lines.append(f"| {date} | {value} |")

        source_url = f"https://fred.stlouisfed.org/series/{series_id}"
        return ToolResult(
            tool_name=self.name,
            query=series_id,
            content="\n".join(lines),
            sources=[source_url],
            success=True,
        )
