"""
Shared fixtures for FaucetPlay integration tests.

Required environment variables / GitHub secrets:
  DUCKDICE_COOKIE   — session cookie (primary auth)
  DUCKDICE_API_KEY  — API key (optional fallback)
"""
import os
import time

import pytest


# ---------------------------------------------------------------------------
# Credential fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def duckdice_cookie():
    """Real DuckDice session cookie. Skips if not provided."""
    cookie = os.environ.get("DUCKDICE_COOKIE", "").strip()
    if not cookie:
        pytest.skip("DUCKDICE_COOKIE is not set — skipping integration tests")
    return cookie


@pytest.fixture(scope="session")
def duckdice_api_key():
    return os.environ.get("DUCKDICE_API_KEY", "").strip()


@pytest.fixture(scope="session")
def api(duckdice_cookie, duckdice_api_key):
    from core.api import DuckDiceAPI
    return DuckDiceAPI(api_key=duckdice_api_key, cookie=duckdice_cookie)


# ---------------------------------------------------------------------------
# GUI fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def tk_root():
    """Session-scoped CustomTkinter root window. Skips if no display."""
    try:
        import customtkinter as ctk
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        root = ctk.CTk()
        root.withdraw()
    except Exception as exc:
        pytest.skip(f"GUI display not available: {exc}")
    yield root
    try:
        root.destroy()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Helpers available to all test modules
# ---------------------------------------------------------------------------

def pump(root, seconds: float = 0.1):
    """Drive the tkinter event loop for `seconds` without blocking the thread."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        root.update()
        time.sleep(0.02)


def wait_for(root, condition_fn, timeout: float = 15.0, poll: float = 0.1) -> bool:
    """Pump the event loop until condition_fn() returns True or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        root.update()
        if condition_fn():
            return True
        time.sleep(poll)
    return False
