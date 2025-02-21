from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from ..api_utils import APIMixin


# Mock requests.get
@pytest.fixture
def mock_requests_get():
    with patch("requests.get") as mock_get:
        yield mock_get


@pytest.fixture
def apimixin():
    urls = "http://example.com,http://example2.com"
    health_check_path = "/health"
    apimixin = APIMixin(urls, health_check_path)
    yield apimixin
    # Ensure the executor is properly shut down after tests
    apimixin._heartbeat_executor.shutdown(wait=False)


def test_apimixin_initialization(apimixin):
    """Test APIMixin initialization with various parameters."""
    assert apimixin._remote_urls == ["http://example.com", "http://example2.com"]
    assert apimixin._health_check_path == "/health"
    assert apimixin._health_check_interval_secs == 5
    assert apimixin._health_check_timeout_secs == 30
    assert apimixin._choice_type == "latest_first"
    assert isinstance(apimixin._heartbeat_executor, ThreadPoolExecutor)


def test_health_check(apimixin, mock_requests_get):
    """Test the _check_health method."""
    url = "http://example.com"

    # Mocking a successful response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_requests_get.return_value = mock_response

    is_healthy, checked_url = apimixin._check_health(url)
    assert is_healthy
    assert checked_url == url

    # Mocking a failed response
    mock_requests_get.side_effect = Exception("Connection error")
    is_healthy, checked_url = apimixin._check_health(url)
    assert not is_healthy
    assert checked_url == url


def test_check_and_update_health(apimixin, mock_requests_get):
    """Test the _check_and_update_health method."""
    apimixin._heartbeat_map = {
        "http://example.com": datetime.now() - timedelta(seconds=3),
        "http://example2.com": datetime.now() - timedelta(seconds=10),
    }

    # Mocking responses
    def side_effect(url, timeout):
        mock_response = MagicMock()
        if url == "http://example.com/health":
            mock_response.status_code = 200
        elif url == "http://example2.com/health":
            mock_response.status_code = 500
        return mock_response

    mock_requests_get.side_effect = side_effect

    health_urls = apimixin._check_and_update_health()
    assert "http://example.com" in health_urls
    assert "http://example2.com" not in health_urls


@pytest.mark.asyncio
async def test_select_url(apimixin, mock_requests_get):
    """Test the async select_url method."""
    apimixin._health_urls = ["http://example.com"]

    selected_url = await apimixin.select_url()
    assert selected_url == "http://example.com"

    # Test with no healthy URLs
    apimixin._health_urls = []
    selected_url = await apimixin.select_url(max_wait_health_timeout_secs=1)
    assert selected_url in ["http://example.com", "http://example2.com"]


def test_sync_select_url(apimixin, mock_requests_get):
    """Test the synchronous sync_select_url method."""
    apimixin._health_urls = ["http://example.com"]

    selected_url = apimixin.sync_select_url()
    assert selected_url == "http://example.com"

    # Test with no healthy URLs
    apimixin._health_urls = []
    selected_url = apimixin.sync_select_url(max_wait_health_timeout_secs=1)
    assert selected_url in ["http://example.com", "http://example2.com"]
