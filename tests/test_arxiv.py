import requests
import pytest

from agent.tools.arxiv import ArxivTool

_SAMPLE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Machine Learning for Credit Risk</title>
    <summary>We propose a novel approach to credit risk assessment using deep learning.</summary>
    <published>2024-06-15T00:00:00Z</published>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <link rel="alternate" href="https://arxiv.org/abs/2406.12345"/>
  </entry>
  <entry>
    <title>Neural Networks in Finance</title>
    <summary>A survey of neural network applications in financial risk modeling.</summary>
    <published>2024-03-01T00:00:00Z</published>
    <author><name>Carol Lee</name></author>
    <link rel="alternate" href="https://arxiv.org/abs/2403.67890"/>
  </entry>
</feed>
"""

_EMPTY_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
</feed>
"""


@pytest.fixture
def tool() -> ArxivTool:
    return ArxivTool()


class TestArxivToolSuccess:
    def test_successful_fetch_multiple_results(self, tool: ArxivTool, mocker) -> None:
        resp = mocker.Mock()
        resp.text = _SAMPLE_XML
        resp.raise_for_status = mocker.Mock()

        mocker.patch("agent.tools.arxiv.requests.get", return_value=resp)

        result = tool.run("credit risk machine learning")

        assert result.success is True
        assert result.tool_name == "arxiv"
        assert "Machine Learning for Credit Risk" in result.content
        assert "Neural Networks in Finance" in result.content
        assert "Alice Smith" in result.content
        assert "Bob Jones" in result.content
        assert "2024-06-15" in result.content
        assert result.sources == [
            "https://arxiv.org/abs/2406.12345",
            "https://arxiv.org/abs/2403.67890",
        ]
        assert result.error is None


class TestArxivToolNoResults:
    def test_no_results_found(self, tool: ArxivTool, mocker) -> None:
        resp = mocker.Mock()
        resp.text = _EMPTY_XML
        resp.raise_for_status = mocker.Mock()

        mocker.patch("agent.tools.arxiv.requests.get", return_value=resp)

        result = tool.run("xyznonexistent123")

        assert result.success is False
        assert result.tool_name == "arxiv"
        assert result.content == ""
        assert result.sources == []
        assert "No arXiv papers found" in result.error

    def test_malformed_xml(self, tool: ArxivTool, mocker) -> None:
        resp = mocker.Mock()
        resp.text = "this is not xml at all <><<<"
        resp.raise_for_status = mocker.Mock()

        mocker.patch("agent.tools.arxiv.requests.get", return_value=resp)

        result = tool.run("anything")

        assert result.success is False
        assert result.tool_name == "arxiv"
        assert result.content == ""
        assert result.sources == []
        assert "Malformed XML" in result.error


class TestArxivToolNetworkError:
    def test_network_failure_exhausts_retries(self, tool: ArxivTool, mocker) -> None:
        mocker.patch("agent.tools.arxiv.time.sleep")
        mocker.patch(
            "agent.tools.arxiv.requests.get",
            side_effect=requests.ConnectionError("Network unreachable"),
        )

        with pytest.raises(requests.ConnectionError):
            tool.run("anything")


class TestArxivToolForceFail:
    def test_force_fail(self, tool: ArxivTool) -> None:
        result = tool.run("anything", force_fail=True)

        assert result.success is False
        assert "force_fail" in result.error.lower()
