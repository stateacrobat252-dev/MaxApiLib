import pytest
from src.maxbot_easy.exceptions import MaxBotEasyError, MaxBotEasyAPIError, MaxBotEasyNetworkError

def test_max_bot_easy_error():
    with pytest.raises(MaxBotEasyError) as excinfo:
        raise MaxBotEasyError("Test message")
    assert "Test message" in str(excinfo.value)

def test_max_bot_easy_api_error():
    with pytest.raises(MaxBotEasyAPIError) as excinfo:
        raise MaxBotEasyAPIError("API error")
    assert "API error" in str(excinfo.value)

def test_max_bot_easy_network_error():
    with pytest.raises(MaxBotEasyNetworkError) as excinfo:
        raise MaxBotEasyNetworkError("Network error")
    assert "Network error" in str(excinfo.value)
