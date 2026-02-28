"""
FaucetPlay — Playwright-Based HTTP Session

BrowserSession is a drop-in replacement for requests.Session that routes every
API call through Playwright's APIRequestContext.  This means:

  • Requests look identical to those made by a real browser (TLS fingerprint,
    Accept-Language, Cookie handling, automatic Set-Cookie tracking).
  • Cookies are persisted in a JSON storage_state file between runs — no need
    to paste a fresh cookie string after every session expiry.
  • When the user logs in via the Auto-Extract wizard step, their full browser
    session (all cookies + local-storage) is captured and reused automatically.

Usage
─────
    session = BrowserSession(cookie="…")
    session.start()
    api = DuckDiceAPI(api_key="", cookie="", session=session)
    # … use api normally …
    session.save_state()
    session.stop()

Or as a context manager:
    with BrowserSession.from_cookie("…") as session:
        api = DuckDiceAPI(session=session)
        …
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_BASE_URL    = "https://duckdice.io"
_USER_AGENT  = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_DEFAULT_STATE = Path.home() / ".faucetplay_bot" / "browser_state.json"


# ─────────────────────────────────────────────────────────────────
# Response adapter
# ─────────────────────────────────────────────────────────────────

class _PWResponse:
    """Wraps playwright.APIResponse to expose a requests.Response-compatible API."""

    def __init__(self, pw_resp) -> None:
        self._resp       = pw_resp
        self.status_code = pw_resp.status
        self._body: Optional[bytes] = None

    def _get_body(self) -> bytes:
        if self._body is None:
            self._body = self._resp.body()
        return self._body

    @property
    def text(self) -> str:
        return self._get_body().decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self._get_body())


# ─────────────────────────────────────────────────────────────────
# BrowserSession
# ─────────────────────────────────────────────────────────────────

class BrowserSession:
    """
    Playwright APIRequestContext wrapped as a requests.Session-compatible object.

    Lifecycle
    ─────────
    Call start() before use and stop() when done (or use as a context manager).
    save_state() writes the current cookie jar to disk so the next session can
    pick up right where this one left off.
    """

    def __init__(
        self,
        state_file: Optional[Path] = None,
        cookie:     str            = "",
    ) -> None:
        self._state_file  = Path(state_file) if state_file else _DEFAULT_STATE
        self._cookie_str  = cookie
        self._pw          = None
        self._context     = None

    # ── factory helpers ────────────────────────────────────────────

    @classmethod
    def from_cookie(cls, cookie: str, state_file: Optional[Path] = None) -> "BrowserSession":
        return cls(state_file=state_file, cookie=cookie)

    @classmethod
    def from_state_file(cls, state_file: Optional[Path] = None) -> "BrowserSession":
        return cls(state_file=state_file)

    # ── context manager ────────────────────────────────────────────

    def __enter__(self) -> "BrowserSession":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.save_state()
        self.stop()

    # ── lifecycle ──────────────────────────────────────────────────

    def start(self) -> None:
        """Start the Playwright runtime and open an APIRequestContext."""
        if self._context:
            return   # already running

        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()

        extra_headers: Dict[str, str] = {
            "User-Agent":       _USER_AGENT,
            "Accept":           "application/json, text/plain, */*",
            "Accept-Language":  "en-US,en;q=0.9",
        }

        init_kw: Dict[str, Any] = {
            "base_url":          _BASE_URL,
            "extra_http_headers": extra_headers,
            "ignore_https_errors": False,
        }

        # Prefer persisted state file; fall back to cookie string injection
        if self._state_file.exists():
            init_kw["storage_state"] = str(self._state_file)
            logger.info("BrowserSession: loaded state from %s", self._state_file)
        elif self._cookie_str:
            init_kw["storage_state"] = _cookie_str_to_state(self._cookie_str)
            logger.info("BrowserSession: initialised from cookie string")

        self._context = self._pw.request.new_context(**init_kw)

    def stop(self) -> None:
        """Dispose the Playwright context and stop the runtime."""
        if self._context:
            try:
                self._context.dispose()
            except Exception:
                pass
            self._context = None
        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass
            self._pw = None

    def save_state(self) -> None:
        """Persist the current cookie jar to the state file."""
        if not self._context:
            return
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._context.storage_state(path=str(self._state_file))
            logger.info("BrowserSession: state saved to %s", self._state_file)
        except Exception as exc:
            logger.warning("BrowserSession: could not save state: %s", exc)

    # ── HTTP requests ──────────────────────────────────────────────

    def request(self, method: str, url: str, **kwargs) -> _PWResponse:
        """
        Compatible with requests.Session.request().

        Supports kwargs:
          headers (dict), json (any), data (str|bytes), timeout (seconds → ms)
        """
        if not self._context:
            raise RuntimeError("BrowserSession not started — call start() first")

        fetch_kw: Dict[str, Any] = {}

        if "headers" in kwargs:
            fetch_kw["headers"] = kwargs["headers"]
        if "json" in kwargs:
            fetch_kw["data"] = json.dumps(kwargs["json"])
            fetch_kw.setdefault("headers", {})
            fetch_kw["headers"]["Content-Type"] = "application/json"
        elif "data" in kwargs:
            fetch_kw["data"] = kwargs["data"]

        # requests uses seconds; Playwright uses ms
        fetch_kw["timeout"] = kwargs.get("timeout", 15) * 1000

        try:
            pw_resp = self._context.fetch(url, method=method, **fetch_kw)
        except Exception as exc:
            # Wrap Playwright timeouts/network errors to match requests contract
            raise ConnectionError(f"BrowserSession request failed: {exc}") from exc

        return _PWResponse(pw_resp)

    # ── requests.Session compatibility stubs ───────────────────────

    def mount(self, *args, **kwargs) -> None:
        """No-op — adapter mounts are irrelevant for Playwright sessions."""

    # ── cookie helpers ─────────────────────────────────────────────

    def get_cookie_string(self) -> str:
        """Return the current session cookies as a raw Cookie header string."""
        if not self._context:
            return self._cookie_str
        try:
            state = self._context.storage_state()
            cookies = state.get("cookies", [])
            return "; ".join(
                f"{c['name']}={c['value']}"
                for c in cookies
                if "duckdice" in c.get("domain", "")
            )
        except Exception:
            return self._cookie_str

    @property
    def active(self) -> bool:
        return self._context is not None


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _cookie_str_to_state(cookie_str: str) -> Dict[str, Any]:
    """Convert a raw 'name=value; name2=value2' cookie string to Playwright storage_state."""
    cookies = []
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        name, _, value = part.partition("=")
        name  = name.strip()
        value = value.strip()
        if name:
            cookies.append({
                "name":     name,
                "value":    value,
                "domain":   "duckdice.io",
                "path":     "/",
                "httpOnly": False,
                "secure":   True,
                "sameSite": "Lax",
            })
    return {"cookies": cookies, "origins": []}


def state_file_exists() -> bool:
    return _DEFAULT_STATE.exists()


def delete_state_file() -> None:
    """Remove persisted browser state (forces re-login on next Auto-Extract)."""
    if _DEFAULT_STATE.exists():
        _DEFAULT_STATE.unlink()
        logger.info("BrowserSession: state file deleted")
