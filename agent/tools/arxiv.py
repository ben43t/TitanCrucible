import time
import xml.etree.ElementTree as ET

import requests

from agent.models import ToolResult
from agent.tools.base import BaseTool

_API_URL = "http://export.arxiv.org/api/query"
_ATOM_NS = "{http://www.w3.org/2005/Atom}"
_MAX_RETRIES = 3
_BACKOFF_BASE = 0.5
_MAX_RESULTS = 3


class ArxivTool(BaseTool):
    @property
    def name(self) -> str:
        return "arxiv"

    @property
    def description(self) -> str:
        return "Search arXiv for academic papers and research."

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

        resp = self._request_with_retry(
            _API_URL,
            params={
                "search_query": f"all:{query}",
                "start": "0",
                "max_results": str(_MAX_RESULTS),
                "sortBy": "relevance",
                "sortOrder": "descending",
            },
        )

        return self._parse_response(query, resp.text)

    def _request_with_retry(self, url: str, params: dict[str, str] | None = None) -> requests.Response:
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

    def _parse_response(self, query: str, xml_text: str) -> ToolResult:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return ToolResult(
                tool_name=self.name,
                query=query,
                content="",
                sources=[],
                success=False,
                error="Malformed XML response from arXiv API",
            )

        entries = root.findall(f"{_ATOM_NS}entry")
        if not entries:
            return ToolResult(
                tool_name=self.name,
                query=query,
                content="",
                sources=[],
                success=False,
                error=f"No arXiv papers found for: {query}",
            )

        sections: list[str] = []
        sources: list[str] = []

        for entry in entries:
            title = (entry.findtext(f"{_ATOM_NS}title") or "").strip().replace("\n", " ")
            abstract = (entry.findtext(f"{_ATOM_NS}summary") or "").strip().replace("\n", " ")
            published = (entry.findtext(f"{_ATOM_NS}published") or "")[:10]

            authors: list[str] = []
            for author_el in entry.findall(f"{_ATOM_NS}author"):
                author_name = author_el.findtext(f"{_ATOM_NS}name")
                if author_name:
                    authors.append(author_name.strip())

            paper_url = ""
            for link in entry.findall(f"{_ATOM_NS}link"):
                if link.get("rel") == "alternate":
                    paper_url = link.get("href", "")
                    break

            sections.append(
                f"## {title}\n"
                f"**Authors:** {', '.join(authors)}\n"
                f"**Published:** {published}\n\n"
                f"{abstract}"
            )
            if paper_url:
                sources.append(paper_url)

        return ToolResult(
            tool_name=self.name,
            query=query,
            content="\n\n---\n\n".join(sections),
            sources=sources,
            success=True,
        )
