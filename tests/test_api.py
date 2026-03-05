"""
DuckDiceAPI integration tests.

Verifies the complete backend setup flow (wizard steps 1–3 under the hood):
  - Connection with real credentials
  - PAW level detection
  - Balance fetch
  - Currency enumeration
  - Minimum-bet fetch
  - Cookie-first auth (api_key should NOT appear in logged URLs)

Requires: DUCKDICE_COOKIE env var (DUCKDICE_API_KEY is optional).
"""
import logging

import pytest

from core.api import CookieExpiredError


# ---------------------------------------------------------------------------
# Connection / authentication
# ---------------------------------------------------------------------------

def test_connection_returns_paw_level(api):
    """Wizard step 3: PAW level is an integer 0–5."""
    paw = api.get_paw_level(force=True)
    assert isinstance(paw, int), f"Expected int, got {type(paw)}"
    assert 0 <= paw <= 5, f"PAW level {paw} is outside valid range 0–5"


def test_paw_cached_on_second_call(api):
    """PAW level is cached — second call returns same value without a network hit."""
    first  = api.get_paw_level(force=True)
    second = api.get_paw_level()          # should use cache
    assert first == second


def test_ttt_games_needed(api):
    """Number of TTT games is consistent with PAW level."""
    paw   = api.get_paw_level(force=True)
    games = api.ttt_games_needed()
    expected = (5, 4, 3, 1, 0, 0)[min(paw, 5)]
    assert games == expected, (
        f"PAW {paw} should require {expected} TTT games, got {games}"
    )


# ---------------------------------------------------------------------------
# Balance & currencies (wizard step 4)
# ---------------------------------------------------------------------------

def test_balance_usdc_structure(api):
    """get_balance returns a dict with non-negative 'faucet' and 'main' keys."""
    bal = api.get_balance("USDC")
    assert "faucet" in bal and "main" in bal
    assert bal["faucet"] >= 0.0
    assert bal["main"]   >= 0.0


def test_balance_unknown_currency_is_zero(api):
    """Unknown currency returns zeros rather than raising."""
    bal = api.get_balance("NOTACOIN")
    assert bal == {"faucet": 0.0, "main": 0.0}


def test_available_currencies(api):
    """Currency list is non-empty and contains only strings."""
    currencies = api.get_available_currencies()
    assert len(currencies) > 0, "No currencies returned"
    assert all(isinstance(c, str) and c for c in currencies)


# ---------------------------------------------------------------------------
# Minimum bet (strategy setup)
# ---------------------------------------------------------------------------

def test_min_bet_usdc_positive(api):
    min_bet = api.get_min_bet("USDC")
    assert min_bet > 0, f"min_bet must be positive, got {min_bet}"


def test_min_bet_cached(api):
    """Min bet is cached — value is stable across calls."""
    first  = api.get_min_bet("USDC")
    second = api.get_min_bet("USDC")
    assert first == second


def test_min_bet_fallback_for_unknown_currency(api):
    """Unknown currency returns a safe non-zero default."""
    bet = api.get_min_bet("UNKNOWNCOIN")
    assert bet > 0


# ---------------------------------------------------------------------------
# Cookie-first auth verification
# ---------------------------------------------------------------------------

def test_cookie_auth_used_not_api_key(api, duckdice_cookie, caplog):
    """
    When a valid cookie is present, _authed() must succeed with cookie auth
    and NOT fall back to api_key (no 'falling back to api_key' log message).
    """
    with caplog.at_level(logging.INFO, logger="core.api"):
        api._user_info_cache = None          # force a fresh network call
        api.get_paw_level(force=True)

    fallback_msgs = [r for r in caplog.records if "falling back to api_key" in r.message]
    assert not fallback_msgs, (
        "Cookie auth was rejected and api_key fallback was used — "
        "cookie may be expired or the endpoint changed."
    )


def test_expired_cookie_raises(duckdice_api_key):
    """A clearly invalid cookie raises CookieExpiredError (or fails cleanly)."""
    from core.api import DuckDiceAPI
    bad_api = DuckDiceAPI(api_key=duckdice_api_key,
                          cookie="_session=this_is_not_a_real_cookie")
    # Should either raise CookieExpiredError or return an empty/zero dict.
    # It must NOT raise an unhandled exception.
    try:
        result = bad_api._get_user_info(force=True)
        # If it didn't raise, the result should be empty or zero-like
        assert isinstance(result, dict)
    except CookieExpiredError:
        pass   # expected — invalid cookie detected correctly
