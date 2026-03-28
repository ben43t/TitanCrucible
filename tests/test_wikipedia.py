import requests
import pytest

from agent.tools.wikipedia import WikipediaTool


@pytest.fixture
def tool() -> WikipediaTool:
    return WikipediaTool()


class TestWikipediaToolSuccess:
    def test_successful_fetch(self, tool: WikipediaTool, mocker) -> None:
        search_response = mocker.Mock()
        search_response.json.return_value = {
            "pages": [{"title": "Federal Reserve"}],
        }
        search_response.raise_for_status = mocker.Mock()

        summary_response = mocker.Mock()
        summary_response.json.return_value = {
            "title": "Federal Reserve",
            "type": "standard",
            "extract": "The Federal Reserve System is the central banking system of the United States.",
            "content_urls": {
                "desktop": {
                    "page": "https://en.wikipedia.org/wiki/Federal_Reserve",
                },
            },
        }
        summary_response.raise_for_status = mocker.Mock()

        mocker.patch(
            "agent.tools.wikipedia.requests.get",
            side_effect=[search_response, summary_response],
        )

        result = tool.run("Federal Reserve")

        assert result.success is True
        assert result.tool_name == "wikipedia"
        assert "Federal Reserve" in result.content
        assert "central banking system" in result.content
        assert result.sources == ["https://en.wikipedia.org/wiki/Federal_Reserve"]
        assert result.error is None


class TestWikipediaToolNotFound:
    def test_article_not_found(self, tool: WikipediaTool, mocker) -> None:
        search_response = mocker.Mock()
        search_response.json.return_value = {"pages": []}
        search_response.raise_for_status = mocker.Mock()

        mocker.patch(
            "agent.tools.wikipedia.requests.get",
            return_value=search_response,
        )

        result = tool.run("xyznonexistentarticle123")

        assert result.success is False
        assert "No Wikipedia article found" in result.error

    def test_disambiguation_page(self, tool: WikipediaTool, mocker) -> None:
        search_response = mocker.Mock()
        search_response.json.return_value = {"pages": [{"title": "Bank"}]}
        search_response.raise_for_status = mocker.Mock()

        summary_response = mocker.Mock()
        summary_response.json.return_value = {
            "type": "disambiguation",
            "content_urls": {
                "desktop": {"page": "https://en.wikipedia.org/wiki/Bank_(disambiguation)"},
            },
        }
        summary_response.raise_for_status = mocker.Mock()

        mocker.patch(
            "agent.tools.wikipedia.requests.get",
            side_effect=[search_response, summary_response],
        )

        result = tool.run("Bank")

        assert result.success is False
        assert "disambiguation" in result.error.lower()


class TestWikipediaToolNetworkError:
    def test_network_failure_exhausts_retries(self, tool: WikipediaTool, mocker) -> None:
        mocker.patch("agent.tools.wikipedia.time.sleep")
        mocker.patch(
            "agent.tools.wikipedia.requests.get",
            side_effect=requests.ConnectionError("Network unreachable"),
        )

        with pytest.raises(requests.ConnectionError):
            tool.run("anything")

    def test_retries_then_succeeds(self, tool: WikipediaTool, mocker) -> None:
        mocker.patch("agent.tools.wikipedia.time.sleep")

        search_ok = mocker.Mock()
        search_ok.json.return_value = {"pages": [{"title": "Test"}]}
        search_ok.raise_for_status = mocker.Mock()

        summary_ok = mocker.Mock()
        summary_ok.json.return_value = {
            "type": "standard",
            "extract": "A test.",
            "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Test"}},
        }
        summary_ok.raise_for_status = mocker.Mock()

        mocker.patch(
            "agent.tools.wikipedia.requests.get",
            side_effect=[
                requests.ConnectionError("fail 1"),
                search_ok,
                summary_ok,
            ],
        )

        result = tool.run("test")

        assert result.success is True


class TestWikipediaToolForceFail:
    def test_force_fail(self, tool: WikipediaTool) -> None:
        result = tool.run("anything", force_fail=True)

        assert result.success is False
        assert "force_fail" in result.error.lower()
