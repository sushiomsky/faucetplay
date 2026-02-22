"""
FaucetPlay — Bot Engine
Drives the claim → bet → repeat cycle for a single Account.
PAW-aware: routes low-PAW accounts through the TicTacToe engine.
All API requests go through the account's NetworkProfile (proxy/VPN).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Callable, Optional

from .accounts import Account
from .api import DuckDiceAPI, CookieExpiredError, RateLimitError
from .network import NetworkProfileManager, ProfileType
from .tictactoe import TicTacToeClaimEngine

logger = logging.getLogger(__name__)


class BotError(Exception):
    pass


class FaucetBot:
    """
    Bot for a single Account.  Instantiate one per account for parallel runs.
    """

    def __init__(
        self,
        account: Account,
        network_mgr: NetworkProfileManager,
        target_amount: float = 20.0,
        house_edge: float = 0.03,
        auto_cashout: bool = False,
        cashout_threshold: float = 10.0,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self.account = account
        self._net_mgr = network_mgr
        self.target_amount = target_amount
        self.house_edge = house_edge
        self.auto_cashout = auto_cashout
        self.cashout_threshold = cashout_threshold
        self._log_cb = log_callback or (lambda msg: logger.info("[%s] %s", account.label, msg))

        self.running = False
        self.paused = False
        self._last_claim_time: float = 0.0
        self.claim_cooldown: int = 60

        self.stats = {
            "session_start": None,
            "total_bets": 0,
            "total_wins": 0,
            "total_losses": 0,
            "starting_balance": 0.0,
            "current_balance": 0.0,
            "total_claimed": 0.0,
        }

        self._api: Optional[DuckDiceAPI] = None

    # --- Logging -----------------------------------------------------------

    def _log(self, msg: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self._log_cb(f"[{ts}] {msg}")

    # --- API init with network routing ------------------------------------

    def _build_api(self) -> DuckDiceAPI:
        proxies: Optional[dict] = None
        playwright_proxy: Optional[dict] = None
        profile_id = self.account.network_profile_id

        if profile_id:
            profile = self._net_mgr.get(profile_id)
            if profile and profile.type == ProfileType.PROXY:
                proxies = self._net_mgr.get_proxies_dict(profile_id)
                playwright_proxy = self._net_mgr.get_playwright_proxy(profile_id)
            elif profile and profile.type == ProfileType.VPN:
                # VPN is connected at session start; traffic flows through it natively
                pass

        return DuckDiceAPI(
            api_key=self.account.api_key,
            cookie=self.account.cookie,
            fingerprint=self.account.fingerprint,
            proxies=proxies,
        )

    # --- Session lifecycle ------------------------------------------------

    def start(self) -> None:
        self.running = True
        self.stats["session_start"] = datetime.now(timezone.utc)
        self._log("=" * 60)
        self._log(f"🎰 BOT STARTED  |  Account: {self.account.label}")
        self._log("=" * 60)

        # Connect VPN if applicable
        self._vpn_connect()

        self._api = self._build_api()

        # Refresh PAW level
        paw = self._api.get_paw_level(force=True)
        self.account.paw_level = paw
        self._log(f"🐾 PAW level: {paw}  |  TTT games needed: {self._api.ttt_games_needed()}")

        currency = self.account.preferred_currency
        min_bet = self._api.get_min_bet(currency)
        self._log(f"Currency: {currency}  |  Min bet: {min_bet}  |  Target: {self.target_amount}")

        balance = self._api.get_balance(currency)
        self.stats["starting_balance"] = balance["faucet"]
        self._run_loop(currency, min_bet)

    def stop(self) -> None:
        self.running = False
        self._log("�� Bot stopped")
        self._vpn_disconnect()

    def pause(self) -> None:
        self.paused = True
        self._log("⏸ Bot paused")

    def resume(self) -> None:
        self.paused = False
        self._log("▶ Bot resumed")

    # --- VPN lifecycle ----------------------------------------------------

    def _vpn_connect(self) -> None:
        pid = self.account.network_profile_id
        if not pid:
            return
        profile = self._net_mgr.get(pid)
        if profile and profile.type == ProfileType.VPN:
            self._log("🛡 Connecting VPN...")
            ok = self._net_mgr.vpn_connect(pid)
            if ok:
                ip = self._net_mgr.verify_ip(pid)
                self._log(f"🛡 VPN connected  |  External IP: {ip or 'unknown'}")
            else:
                self.running = False
                raise BotError("VPN connection failed — aborting session for safety.")

    def _vpn_disconnect(self) -> None:
        pid = self.account.network_profile_id
        if pid:
            profile = self._net_mgr.get(pid)
            if profile and profile.type == ProfileType.VPN:
                self._net_mgr.vpn_disconnect(pid)
                self._log("🛡 VPN disconnected")

    # --- Main loop --------------------------------------------------------

    def _run_loop(self, currency: str, min_bet: float) -> None:
        assert self._api is not None
        while self.running:
            while self.paused and self.running:
                time.sleep(0.5)
            if not self.running:
                break

            try:
                balance = self._api.get_balance(currency)
            except CookieExpiredError:
                self._log("🔑 Cookie expired — stopping session. Please update your cookie.")
                self.running = False
                break
            except RateLimitError as e:
                self._log(f"⚠️ {e}")
                time.sleep(30)
                continue

            faucet = balance["faucet"]
            self.stats["current_balance"] = faucet

            if faucet >= self.target_amount:
                self._log(f"🎉 TARGET REACHED: {faucet:.8f} {currency}")
                if self.auto_cashout and faucet >= self.cashout_threshold:
                    self._api.cashout(currency, faucet)
                break

            if faucet < min_bet:
                self._do_claim(currency)
                continue

            self._do_bet(currency, faucet)

        self._show_stats()

    # --- Claiming ---------------------------------------------------------

    def _do_claim(self, currency: str) -> None:
        assert self._api is not None
        # Respect cooldown
        elapsed = time.time() - self._last_claim_time
        if elapsed < self.claim_cooldown:
            wait = int(self.claim_cooldown - elapsed)
            self._log(f"⏳ Cooldown: {wait}s remaining…")
            for remaining in range(wait, 0, -1):
                if not self.running:
                    return
                while self.paused and self.running:
                    time.sleep(0.5)
                if remaining % 10 == 0:
                    self._log(f"⏳ Cooldown: {remaining}s")
                time.sleep(1)

        games = self._api.ttt_games_needed()
        if games > 0:
            self._log(f"🎮 PAW {self.account.paw_level}: playing {games} TTT game(s)…")
            profile_id = self.account.network_profile_id
            pw_proxy = self._net_mgr.get_playwright_proxy(profile_id) if profile_id else None
            engine = TicTacToeClaimEngine(
                cookie=self.account.cookie,
                fingerprint=self.account.fingerprint,
                playwright_proxy=pw_proxy,
            )
            try:
                ok = engine.run(games_needed=games, currency=currency)
            except Exception as e:
                self._log(f"❌ TTT engine error: {e}")
                time.sleep(10)
                return
            if ok:
                self._last_claim_time = time.time()
                self.stats["total_claimed"] += 1
                self._log("✅ Faucet claimed via TTT!")
                # Refresh PAW level after successful claim
                self.account.paw_level = self._api.get_paw_level(force=True)
            else:
                self._log("❌ TTT claim failed. Retrying in 10s…")
                time.sleep(10)
        else:
            self._log("🔵 Claiming faucet (direct)…")
            try:
                ok = self._api.claim_faucet(currency)
            except CookieExpiredError:
                self._log("🔑 Cookie expired during claim. Please update your cookie.")
                self.running = False
                return
            if ok:
                self._last_claim_time = time.time()
                self.stats["total_claimed"] += 1
                self._log("✅ Faucet claimed!")
                time.sleep(10)
            else:
                self._log("❌ Claim failed. Retrying in 10s…")
                time.sleep(10)

    # --- Betting ----------------------------------------------------------

    def _do_bet(self, currency: str, faucet: float) -> None:
        assert self._api is not None
        multiplier = self.target_amount / faucet if faucet else 0
        raw_chance = (100.0 * (1.0 - self.house_edge)) / multiplier if multiplier else 0.0
        chance = max(0.01, min(99.0, round(raw_chance, 2)))

        self._log(f"🎲 Faucet: {faucet:.8f} {currency}  |  {multiplier:.2f}x needed  |  Chance: {chance:.2f}%")

        try:
            result = self._api.play_dice(currency, faucet, chance, is_high=True, use_faucet=True)
        except CookieExpiredError:
            self._log("🔑 Cookie expired during bet. Please update your cookie.")
            self.running = False
            return
        except RateLimitError as e:
            self._log(f"⚠️ {e}")
            time.sleep(30)
            return

        self.stats["total_bets"] += 1

        if result:
            data = result.get("data", {})
            new_bal = float(data.get("balance", {}).get("faucet", 0))
            win = data.get("win", False)
            if win:
                self.stats["total_wins"] += 1
                self._log(f"🎉 WON!  New faucet: {new_bal:.8f} {currency}")
            else:
                self.stats["total_losses"] += 1
                self._log(f"❌ Lost.  New faucet: {new_bal:.8f} {currency}")
        else:
            self._log("❌ Bet failed (no response).")

        time.sleep(2)

    # --- Stats ------------------------------------------------------------

    def _show_stats(self) -> None:
        self._log("=" * 60)
        self._log("📊 SESSION STATISTICS")
        self._log("=" * 60)
        start = self.stats["session_start"]
        if start:
            self._log(f"Duration: {datetime.now(timezone.utc) - start}")
        self._log(f"Total bets:  {self.stats['total_bets']}")
        self._log(f"Wins:        {self.stats['total_wins']}")
        self._log(f"Losses:      {self.stats['total_losses']}")
        n = self.stats["total_bets"]
        if n:
            self._log(f"Win rate:    {self.stats['total_wins']/n*100:.2f}%")
        profit = self.stats["current_balance"] - self.stats["starting_balance"]
        self._log(f"Profit/Loss: {profit:+.8f}")
        self._log(f"Claims:      {self.stats['total_claimed']}")
        self._log("=" * 60)

    def get_stats(self) -> dict:
        return self.stats.copy()
