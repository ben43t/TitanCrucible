import time

import requests

from agent.models import ToolResult
from agent.tools.base import BaseTool

_SEARCH_URL = "https://en.wikipedia.org/w/rest.php/v1/search/page"
_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"
_MAX_RETRIES = 3
_BACKOFF_BASE = 0.5
_HEADERS = {"User-Agent": "TitanCrucible/0.1 (research-agent; educational project)"}


class WikipediaTool(BaseTool):
    @property
    def name(self) -> str:
        return "wikipedia"

    @property
    def description(self) -> str:
        return "Search Wikipedia for general knowledge, definitions, and background information."

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

        title = self._search(query)
        if title is None:
            return ToolResult(
                tool_name=self.name,
                query=query,
                content="",
                sources=[],
                success=False,
                error=f"No Wikipedia article found for: {query}",
            )

        return self._fetch_summary(query, title)

    def _request_with_retry(self, url: str, params: dict[str, str] | None = None) -> requests.Response:
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = requests.get(url, params=params, headers=_HEADERS, timeout=10)
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_BACKOFF_BASE * (2**attempt))
        raise last_exc  # type: ignore[misc]

    def _search(self, query: str) -> str | None:
        resp = self._request_with_retry(_SEARCH_URL, params={"q": query, "limit": "1"})
        data = resp.json()
        pages = data.get("pages", [])
        if not pages:
            return None
        return pages[0].get("title")

    def _fetch_summary(self, query: str, title: str) -> ToolResult:
        encoded_title = title.replace(" ", "_")
        resp = self._request_with_retry(f"{_SUMMARY_URL}/{encoded_title}")
        data = resp.json()

        # Handle disambiguation pages
        if data.get("type") == "disambiguation":
            return ToolResult(
                tool_name=self.name,
                query=query,
                content=f"'{title}' is a disambiguation page. Try a more specific query.",
                sources=[data.get("content_urls", {}).get("desktop", {}).get("page", "")],
                success=False,
                error="Disambiguation page returned",
            )

        extract = data.get("extract", "")
        page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")

        return ToolResult(
            tool_name=self.name,
            query=query,
            content=f"# {title}\n\n{extract}",
            sources=[page_url] if page_url else [],
            success=True,
        )
