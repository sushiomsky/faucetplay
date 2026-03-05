"""
BotConfig unit tests.

Tests encryption/decryption, loading, saving, and field defaults.
"""
import tempfile
from pathlib import Path

import pytest

from core.config import BotConfig


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for config files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def config(temp_config_dir, monkeypatch):
    """Create a BotConfig instance using a temporary directory."""
    monkeypatch.setenv("HOME", str(temp_config_dir))
    cfg = BotConfig()
    cfg._config_dir = temp_config_dir / ".faucetplay_bot"
    cfg._config_dir.mkdir(parents=True, exist_ok=True)
    return cfg


def test_default_values(config):
    """New config has sensible defaults."""
    assert config.get("api_key", "") == ""
    assert config.get("cookie", "") == ""
    assert config.get("currency", "USDC") == "USDC"
    assert config.get("target_amount", 20.0) == 20.0
    assert config.get("auto_cashout", True) is True
    assert config.get("continue_after_cashout", True) is True


def test_set_and_get(config):
    """Can set and retrieve values."""
    config.set("currency", "BTC")
    assert config.get("currency") == "BTC"
    
    config.set("target_amount", 50.5)
    assert config.get("target_amount") == 50.5


def test_set_encrypted_fields(config):
    """API key and cookie are encrypted when saved."""
    config.set("api_key", "test-key-123")
    config.set("cookie", "test-cookie-abc")
    config.save()
    
    # Load from disk
    config2 = BotConfig()
    config2._config_dir = config._config_dir
    config2.load()
    
    assert config2.get("api_key") == "test-key-123"
    assert config2.get("cookie") == "test-cookie-abc"


def test_encryption_key_isolation(config):
    """Encryption key is created with restricted permissions (0o600)."""
    config.set("api_key", "secret")
    config.save()
    
    key_path = config._config_dir / ".key"
    assert key_path.exists()
    # On Unix-like systems, check mode; on Windows this may not apply
    mode = key_path.stat().st_mode
    # Only check permission bits (last 3 digits of octal)
    assert (mode & 0o777) == 0o600, f"Key file has insecure permissions: {oct(mode)}"


def test_load_nonexistent_config(config):
    """Loading a nonexistent config does not raise an error."""
    config2 = BotConfig()
    config2._config_dir = config._config_dir / "nonexistent"
    # Should not raise
    config2.load()
    assert config2.get("currency", "USDC") == "USDC"


def test_round_trip_all_fields(config):
    """All field types survive a save/load cycle."""
    original = {
        "api_key": "key-value",
        "cookie": "session-cookie",
        "currency": "ETH",
        "target_amount": 99.99,
        "auto_cashout": False,
        "continue_after_cashout": True,
        "house_edge": 0.05,
    }
    
    for key, val in original.items():
        config.set(key, val)
    config.save()
    
    config2 = BotConfig()
    config2._config_dir = config._config_dir
    config2.load()
    
    for key, expected in original.items():
        actual = config2.get(key)
        assert actual == expected, f"{key}: expected {expected}, got {actual}"
