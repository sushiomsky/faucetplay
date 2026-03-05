"""
ChatBot unit tests.

Tests message database functionality.
"""
from unittest.mock import Mock
from collections import deque

import pytest

from core.chat_bot import ChatBot


@pytest.fixture
def mock_api():
    """Create a mock DuckDiceAPI."""
    return Mock()


@pytest.fixture
def mock_config():
    """Create a mock BotConfig."""
    cfg = Mock()
    cfg.get = Mock(side_effect=lambda k, default=None: {
        "chat_enabled": True,
        "chat_dry_run": True,
        "chat_min_interval": 30,
        "chat_max_interval": 300,
        "chat_rest_periods": [],
    }.get(k, default))
    return cfg


@pytest.fixture
def chat_bot(mock_api, mock_config):
    """Create a ChatBot instance for testing."""
    log_callback = Mock()
    bot = ChatBot(api=mock_api, config=mock_config, log_callback=log_callback)
    return bot


def test_chat_bot_init(chat_bot):
    """ChatBot initializes correctly."""
    assert chat_bot is not None
    assert chat_bot.dry_run is True


def test_dry_run_mode_default(chat_bot):
    """Dry-run mode is enabled by default."""
    assert chat_bot.dry_run is True


def test_dry_run_can_be_set(chat_bot):
    """Dry-run property can be set."""
    chat_bot.dry_run = False
    assert chat_bot.dry_run is False
    
    chat_bot.dry_run = True
    assert chat_bot.dry_run is True


def test_recent_log_is_deque(chat_bot):
    """recent_log is a deque containing activity."""
    assert isinstance(chat_bot.recent_log, deque)
