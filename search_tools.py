from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import urllib.parse
import urllib.request


SEARCH_URL = "https://html.duckduckgo.com/html/"


class DuckDuckGoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._capture: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        class_name = attrs_dict.get("class", "")
        if tag == "a" and "result__a" in class_name:
            self._current = {"title": "", "url": self._clean_url(attrs_dict.get("href", "")), "snippet": ""}
            self._capture = "title"
            self._parts = []
        elif self._current is not None and "result__snippet" in class_name:
            self._capture = "snippet"
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture == "title" and tag == "a" and self._current is not None:
            self._current["title"] = self._clean_text(" ".join(self._parts))
            if self._current["title"] and self._current["url"]:
                self.results.append(self._current)
            self._capture = None
            self._parts = []
        elif self._capture == "snippet" and tag in {"a", "div"} and self._current is not None:
            self._current["snippet"] = self._clean_text(" ".join(self._parts))
            self._capture = None
            self._parts = []

    @staticmethod
    def _clean_text(value: str) -> str:
        return " ".join(unescape(value).split())

    @staticmethod
    def _clean_url(value: str) -> str:
        value = unescape(value)
        parsed = urllib.parse.urlparse(value)
        query = urllib.parse.parse_qs(parsed.query)
        if "uddg" in query:
            return query["uddg"][0]
        return value


def search_web(query: str, max_results: int = 4) -> list[dict[str, str]]:
    query = query.strip()
    if not query:
        return []
    max_results = max(1, min(max_results, 8))
    data = urllib.parse.urlencode({"q": query}).encode("utf-8")
    request = urllib.request.Request(
        SEARCH_URL,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 Gemma4LocalWebUI/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        html = response.read().decode("utf-8", errors="replace")
    parser = DuckDuckGoParser()
    parser.feed(html)
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for result in parser.results:
        url = result.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(result)
        if len(deduped) >= max_results:
            break
    return deduped


def build_search_context(results: list[dict[str, str]]) -> str:
    if not results:
        return "Web search was requested, but no search results were found."
    lines = [
        "Web search results follow. Use them as current context. Cite source numbers when relying on them.",
        "Do not invent titles, names, dates, numbers, or list items that do not appear in the search result titles, snippets, or page text below.",
        "If the user asks for every item, a complete list, or all works but the page text is missing or incomplete, say that the complete list could not be confirmed from the retrieved text.",
    ]
    for index, result in enumerate(results, start=1):
        lines.append(
            f"[{index}] {result.get('title', '').strip()}\n"
            f"URL: {result.get('url', '').strip()}\n"
            f"Snippet: {result.get('snippet', '').strip()}"
        )
    return "\n\n".join(lines)
