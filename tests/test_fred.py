import requests
import pytest

from agent.tools.fred import FredTool


@pytest.fixture
def tool() -> FredTool:
    return FredTool()


def _mock_response(mocker, json_data):
    resp = mocker.Mock()
    resp.json.return_value = json_data
    resp.raise_for_status = mocker.Mock()
    return resp


class TestFredToolSuccess:
    def test_search_and_fetch_observations(self, tool: FredTool, mocker) -> None:
        mocker.patch.dict("os.environ", {"FRED_API_KEY": "test-key"})

        search_resp = _mock_response(mocker, {
            "seriess": [
                {
                    "id": "UNRATE",
                    "title": "Unemployment Rate",
                    "units": "Percent",
                    "frequency": "Monthly",
                }
            ],
        })
        obs_resp = _mock_response(mocker, {
            "observations": [
                {"date": "2024-06-01", "value": "4.1"},
                {"date": "2024-05-01", "value": "4.0"},
            ],
        })

        mocker.patch(
            "agent.tools.fred.requests.get",
            side_effect=[search_resp, obs_resp],
        )

        result = tool.run("unemployment rate")

        assert result.success is True
        assert result.tool_name == "fred"
        assert "Unemployment Rate" in result.content
        assert "UNRATE" in result.content
        assert "4.1" in result.content
        assert "4.0" in result.content
        assert "Percent" in result.content
        assert result.sources == ["https://fred.stlouisfed.org/series/UNRATE"]

    def test_direct_series_id_fetch(self, tool: FredTool, mocker) -> None:
        mocker.patch.dict("os.environ", {"FRED_API_KEY": "test-key"})

        info_resp = _mock_response(mocker, {
            "seriess": [
                {
                    "id": "GDP",
                    "title": "Gross Domestic Product",
                    "units": "Billions of Dollars",
                    "frequency": "Quarterly",
                }
            ],
        })
        obs_resp = _mock_response(mocker, {
            "observations": [
                {"date": "2024-04-01", "value": "28000.5"},
            ],
        })

        mocker.patch(
            "agent.tools.fred.requests.get",
            side_effect=[info_resp, obs_resp],
        )

        result = tool.run("GDP")

        assert result.success is True
        assert "Gross Domestic Product" in result.content
        assert "28000.5" in result.content
        assert result.sources == ["https://fred.stlouisfed.org/series/GDP"]


class TestFredToolMissingKey:
    def test_missing_api_key(self, tool: FredTool, mocker) -> None:
        mocker.patch("agent.tools.fred.load_dotenv")
        mocker.patch.dict("os.environ", {}, clear=True)

        result = tool.run("unemployment")

        assert result.success is False
        assert "FRED_API_KEY" in result.error


class TestFredToolNotFound:
    def test_series_not_found_via_search(self, tool: FredTool, mocker) -> None:
        mocker.patch.dict("os.environ", {"FRED_API_KEY": "test-key"})

        search_resp = _mock_response(mocker, {"seriess": []})
        mocker.patch("agent.tools.fred.requests.get", return_value=search_resp)

        result = tool.run("xyznonexistent123series")

        assert result.success is False
        assert "No FRED series found" in result.error

    def test_series_id_not_found(self, tool: FredTool, mocker) -> None:
        mocker.patch.dict("os.environ", {"FRED_API_KEY": "test-key"})

        info_resp = _mock_response(mocker, {"seriess": []})
        mocker.patch("agent.tools.fred.requests.get", return_value=info_resp)

        result = tool.run("ZZZZNOTREAL")

        assert result.success is False
        assert "FRED series not found" in result.error


class TestFredToolNetworkError:
    def test_network_failure_exhausts_retries(self, tool: FredTool, mocker) -> None:
        mocker.patch.dict("os.environ", {"FRED_API_KEY": "test-key"})
        mocker.patch("agent.tools.fred.time.sleep")
        mocker.patch(
            "agent.tools.fred.requests.get",
            side_effect=requests.ConnectionError("Network unreachable"),
        )

        with pytest.raises(requests.ConnectionError):
            tool.run("unemployment")


class TestFredToolForceFail:
    def test_force_fail(self, tool: FredTool) -> None:
        result = tool.run("anything", force_fail=True)

        assert result.success is False
        assert "force_fail" in result.error.lower()
