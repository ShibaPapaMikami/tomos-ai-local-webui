import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from search_tools import DuckDuckGoParser, build_search_context


def test_duckduckgo_parser_extracts_result() -> None:
    parser = DuckDuckGoParser()
    parser.feed(
        """
        <a class="result__a" href="/l/?uddg=https%3A%2F%2Fexample.com%2Fpage&amp;rut=abc">
          Example &amp; Title
        </a>
        <div class="result__snippet">Example snippet &amp; details</div>
        """
    )
    assert parser.results == [
        {
            "title": "Example & Title",
            "url": "https://example.com/page",
            "snippet": "Example snippet & details",
        }
    ]


def test_build_search_context() -> None:
    context = build_search_context(
        [
            {
                "title": "Example",
                "url": "https://example.com/",
                "snippet": "Current fact",
            }
        ]
    )
    assert "Web search results follow" in context
    assert "[1] Example" in context
    assert "URL: https://example.com/" in context
    assert "Snippet: Current fact" in context


if __name__ == "__main__":
    test_duckduckgo_parser_extracts_result()
    test_build_search_context()
    print("search tools tests passed")
