"""
FaucetPlay — DuckDice API Wrapper
Features:
  - Cookie-first auth: all endpoints try session-cookie before api_key fallback
  - Retry with exponential back-off on transient errors and 429 rate-limits
  - Cookie expiry detection (raises CookieExpiredError)
  - Dynamic per-currency minimum-bet fetch
  - PAW level fetch and cache
"""

from __future__ import annotations

import time
import logging
from typing import Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class CookieExpiredError(Exception):
    """Raised when DuckDice returns a session-expired / auth error."""


class RateLimitError(Exception):
    """Raised after all retry attempts are exhausted due to 429."""


# ---------------------------------------------------------------------------
# Retry / session helpers
# ---------------------------------------------------------------------------

def _build_session() -> requests.Session:
    """Create a requests Session with automatic retries on transient errors."""
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=1.5,         # 1.5s, 2.25s, 3.375s …
        status_forcelist={500, 502, 503, 504},
        allowed_methods={"GET", "POST"},
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# ---------------------------------------------------------------------------
# API class
# ---------------------------------------------------------------------------

class DuckDiceAPI:
    """DuckDice API wrapper with retry hardening."""

    BASE_URL = "https://duckdice.io"

    # How many times to retry a 429 before giving up
    RATE_LIMIT_RETRIES = 6
    RATE_LIMIT_BASE_WAIT = 5  # seconds

    def __init__(self, api_key: str = "", cookie: str = "", session=None):
        """
        Parameters
        ----------
        api_key  : DuckDice bot API key (optional — used as fallback auth)
        cookie   : Raw session cookie string (used when session=None)
        session  : Optional BrowserSession (from core.browser_session).
                   When provided, all HTTP calls go through Playwright's
                   APIRequestContext — cookie handling is automatic and
                   the session looks identical to a real browser.
        """
        self.api_key = api_key
        self.cookie  = cookie
        # Use the provided BrowserSession or fall back to requests.Session
        self._session = session if session is not None else _build_session()
        self._using_browser_session = session is not None

        # Caches
        self._paw_level: Optional[int] = None
        self._min_bets: Dict[str, float] = {}   # currency → min bet amount
        self._user_info_cache: Optional[dict] = None
        self._user_info_ts: float = 0.0

    # --- Request helpers ---------------------------------------------------

    def _browser_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Content-Type": "application/json",
            "Cookie": self.cookie,
            "Accept": "application/json",
        }

    def _get(self, url: str, **kwargs) -> requests.Response:
        return self._request("GET", url, **kwargs)

    def _post(self, url: str, **kwargs) -> requests.Response:
        return self._request("POST", url, **kwargs)

    def _authed(self, method: str, path: str, **kwargs) -> requests.Response:
        """
        Cookie-first authenticated request.

        When a BrowserSession is active, cookies are handled automatically by
        Playwright's cookie store — no manual Cookie header injection needed.

        Otherwise falls back to the manual cookie header → api_key chain.
        """
        base_url = f"{self.BASE_URL}{path}"

        if self._using_browser_session:
            # Playwright manages cookies; just fire the request.
            try:
                resp = self._request(method, base_url, **kwargs)
                if resp.status_code not in (401, 403):
                    return resp
                logger.info("Browser session auth rejected (HTTP %s) for %s",
                            resp.status_code, path)
            except CookieExpiredError:
                if not self.api_key:
                    raise
                logger.info("Browser session expired for %s — trying api_key", path)
            # Fall through to api_key if browser session auth failed
            if self.api_key:
                sep = "&" if "?" in path else "?"
                return self._request(method, f"{base_url}{sep}api_key={self.api_key}",
                                     **kwargs)
            return self._request(method, base_url, **kwargs)

        # ── requests.Session path: inject Cookie header manually ──────
        if self.cookie:
            cookie_kw = {**kwargs,
                         "headers": {**self._browser_headers(),
                                     **kwargs.get("headers", {})}}
            try:
                resp = self._request(method, base_url, **cookie_kw)
                if resp.status_code not in (401, 403):
                    return resp
                logger.info("Cookie auth rejected (HTTP %s) for %s — trying api_key",
                            resp.status_code, path)
            except CookieExpiredError:
                if not self.api_key:
                    raise
                logger.info("Cookie expired for %s — falling back to api_key", path)

        if self.api_key:
            sep = "&" if "?" in path else "?"
            return self._request(method,
                                 f"{base_url}{sep}api_key={self.api_key}", **kwargs)

        # No credentials available — bare request (will surface the auth error)
        return self._request(method, base_url, **kwargs)

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Perform a request with 429 back-off.
        Raises CookieExpiredError on auth failures.
        Raises RateLimitError if all rate-limit retries are exhausted.
        """
        kwargs.setdefault("timeout", 15)
        for attempt in range(self.RATE_LIMIT_RETRIES):
            resp = self._session.request(method, url, **kwargs)

            if resp.status_code == 429:
                wait = self.RATE_LIMIT_BASE_WAIT * (2 ** attempt)
                logger.warning("Rate limited (429). Waiting %ss (attempt %d/%d)",
                               wait, attempt + 1, self.RATE_LIMIT_RETRIES)
                time.sleep(wait)
                continue

            if resp.status_code in (401, 403):
                body = resp.text.lower()
                if any(k in body for k in ("expired", "invalid session",
                                           "unauthorized", "unauthenticated")):
                    raise CookieExpiredError(
                        "Session cookie has expired. Please update your cookie."
                    )

            return resp

        raise RateLimitError(
            f"Exhausted {self.RATE_LIMIT_RETRIES} retries due to rate limiting on {url}"
        )

    # --- User info (cached 60 s) -------------------------------------------

    def _get_user_info(self, force: bool = False) -> dict:
        now = time.time()
        if not force and self._user_info_cache and (now - self._user_info_ts) < 60:
            return self._user_info_cache
        resp = self._authed("GET", "/api/bot/user-info")
        if resp.status_code != 200:
            logger.error("user-info HTTP %s", resp.status_code)
            return self._user_info_cache or {}
        data = resp.json()
        self._user_info_cache = data
        self._user_info_ts = now
        return data

    # --- PAW level ---------------------------------------------------------

    def get_paw_level(self, force: bool = False) -> int:
        """
        Return the account's PAW level (0–5).
        Result is cached until force=True or a new session starts.
        """
        if self._paw_level is not None and not force:
            return self._paw_level
        data = self._get_user_info(force=force)
        # DuckDice returns paw level in user-info; field name may vary — try common keys
        level = (
            data.get('paw_level')
            or data.get('pawLevel')
            or data.get('level')
            or 0
        )
        self._paw_level = int(level)
        logger.info("PAW level: %d", self._paw_level)
        return self._paw_level

    # TTT games needed before a claim unlocks, indexed by PAW level 0-5
    TTT_GAMES_REQUIRED: Tuple[int, ...] = (5, 4, 3, 1, 0, 0)

    def ttt_games_needed(self) -> int:
        """Return how many Tic-Tac-Toe games must be won before claiming."""
        level = self.get_paw_level()
        return self.TTT_GAMES_REQUIRED[min(level, 5)]

    # --- Balances & currencies --------------------------------------------

    def get_available_currencies(self) -> List[str]:
        data = self._get_user_info()
        balances = data.get('balances', [])
        currencies = [b.get('currency') for b in balances if b.get('currency')]
        return sorted(set(currencies))

    def get_balance(self, currency: str) -> Dict[str, float]:
        data = self._get_user_info(force=True)
        for entry in data.get('balances', []):
            if entry.get('currency') == currency.upper():
                return {
                    "main":   float(entry.get('main', 0)),
                    "faucet": float(entry.get('faucet', 0)),
                }
        return {"main": 0.0, "faucet": 0.0}

    # --- Dynamic min-bet fetch --------------------------------------------

    def get_min_bet(self, currency: str) -> float:
        """
        Fetch and cache the minimum bet for a currency from the API.
        Falls back to a safe hardcoded default if the API doesn't return the value.
        """
        cur = currency.upper()
        if cur in self._min_bets:
            return self._min_bets[cur]

        SAFE_DEFAULTS = {
            "BTC": 0.00000001, "ETH": 0.000001, "USDC": 0.001,
            "LTC": 0.00001,    "DOGE": 0.01,    "TRX": 0.1,
            "SOL": 0.000001,   "XRP": 0.001,
        }

        try:
            resp = self._authed("GET", f"/bot-api/info?symbol={cur}")
            if resp.status_code == 200:
                data = resp.json()
                min_bet = (
                    data.get('min_bet')
                    or data.get('minBet')
                    or data.get('minimum_bet')
                )
                if min_bet:
                    self._min_bets[cur] = float(min_bet)
                    return self._min_bets[cur]
        except Exception as e:
            logger.warning("min-bet fetch failed for %s: %s", cur, e)

        fallback = SAFE_DEFAULTS.get(cur, 0.001)
        self._min_bets[cur] = fallback
        return fallback

    # --- Faucet claim (direct, PAW 4-5) -----------------------------------

    def claim_faucet(self, currency: str) -> bool:
        """
        Direct API faucet claim (PAW level 4–5).
        For PAW 0–3 use core.tictactoe.TicTacToeClaimEngine instead.
        Returns True on success, raises CookieExpiredError if session expired.
        """
        url = f"{self.BASE_URL}/api/faucet"
        resp = self._post(
            url,
            headers=self._browser_headers(),
            json={"symbol": currency.upper(), "results": []},
        )
        if resp.status_code == 200:
            # Refresh PAW level and user info after each successful claim
            self._paw_level = None
            self._user_info_cache = None
            return True
        logger.warning("claim_faucet HTTP %s: %s", resp.status_code, resp.text[:200])
        return False

    # --- Dice play ---------------------------------------------------------

    def play_dice(
        self,
        currency: str,
        amount: float,
        chance: float,
        is_high: bool = True,
        use_faucet: bool = True,
    ) -> Optional[Dict]:
        """Place a dice bet. Returns full API response dict or None on failure."""
        payload = {
            "symbol":  currency.upper(),
            "amount":  f"{amount:.9f}",
            "chance":  f"{chance:.2f}",
            "isHigh":  is_high,
            "faucet":  use_faucet,
        }
        resp = self._authed("POST", "/api/dice/play", json=payload)
        if resp.status_code != 200:
            logger.error("play_dice HTTP %s: %s", resp.status_code, resp.text[:300])
            return None
        return resp.json()

    # --- Cashout (faucet → main wallet) -----------------------------------

    # DuckDice cashout cooldown is per-account; the API returns the next
    # allowed cashout timestamp in the response body.  We track it locally.
    CASHOUT_DEFAULT_COOLDOWN = 3600   # 1 hour fallback if API doesn't tell us

    def cashout(self, currency: str, amount: float) -> Dict:
        """
        Transfer `amount` from faucet wallet to main wallet.

        Returns a dict with keys:
          success   bool   – True if transfer was accepted
          amount    float  – amount actually transferred
          cooldown  int    – seconds until next cashout is allowed (0 = no limit)
          message   str    – human-readable status

        Raises CookieExpiredError if the session is dead.
        """
        payload = {
            "symbol": currency.upper(),
            "amount": f"{amount:.9f}",
        }
        resp = self._authed("POST", "/api/bot/transfer", json=payload)

        # DuckDice may also expose this under /api/faucet/transfer — try both
        if resp.status_code == 404:
            resp = self._authed("POST", "/api/faucet/transfer", json=payload)

        if resp.status_code == 200:
            data = resp.json()
            # Invalidate balance cache so next get_balance() is fresh
            self._user_info_cache = None

            # Parse cooldown from response if provided
            cooldown = 0
            next_ts = (data.get("next_cashout_at")
                       or data.get("nextCashoutAt")
                       or data.get("cooldown"))
            if next_ts:
                try:
                    cooldown = max(0, int(float(next_ts)) - int(time.time()))
                except (ValueError, TypeError):
                    cooldown = 0

            transferred = float(
                data.get("amount") or data.get("transferred") or amount
            )
            logger.info("Cashout %s %s → main OK  (cooldown %ds)",
                        transferred, currency, cooldown)
            return {"success": True, "amount": transferred,
                    "cooldown": cooldown, "message": "Transfer successful"}

        if resp.status_code == 429:
            # Rate-limited or cooldown enforced by server
            try:
                body = resp.json()
                cooldown = int(body.get("retry_after")
                               or body.get("cooldown")
                               or self.CASHOUT_DEFAULT_COOLDOWN)
            except Exception:
                cooldown = self.CASHOUT_DEFAULT_COOLDOWN
            logger.warning("Cashout on cooldown for %ds", cooldown)
            return {"success": False, "amount": 0.0,
                    "cooldown": cooldown,
                    "message": f"Cashout cooldown active ({cooldown}s)"}

        logger.error("cashout HTTP %s: %s", resp.status_code, resp.text[:300])
        return {"success": False, "amount": 0.0, "cooldown": 0,
                "message": f"Cashout failed (HTTP {resp.status_code})"}

    # --- Chat ---------------------------------------------------------

    def send_chat_message(self, text: str) -> bool:
        """
        Post a message to the DuckDice public chat.
        Returns True on success, False on failure.
        """
        text = text.strip()
        if not text:
            return False
        try:
            resp = self._authed("POST", "/api/chat", json={"message": text})
            if resp.status_code in (200, 201):
                return True
            logger.warning("send_chat_message HTTP %s: %s",
                           resp.status_code, resp.text[:200])
            return False
        except Exception as exc:
            logger.warning("send_chat_message error: %s", exc)
            return False

    def get_cashout_cooldown(self, currency: str) -> int:
        """
        Check how many seconds remain before the next cashout is allowed.
        Returns 0 if a cashout can be made immediately.
        Probes the API with a zero-amount dry-run if supported, otherwise
        returns 0 (optimistic — the real cashout call will return cooldown info).
        """
        try:
            resp = self._authed("POST", "/api/bot/transfer",
                                json={"symbol": currency.upper(),
                                      "amount": "0", "dry_run": True})
            if resp.status_code == 429:
                body = resp.json()
                return int(body.get("retry_after") or body.get("cooldown") or 0)
            return 0
        except Exception:
            return 0   # assume available; real call will catch it
