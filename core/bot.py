"""
FaucetPlay — Bot Engine
Drives the claim → bet → cashout → repeat cycle for a single Account.

Cashout loop state machine
──────────────────────────
FARMING:
  Claim faucet (PAW-aware) → bet toward target.
  On target reached → attempt cashout:
    • If cashout succeeds → move to POST_CASHOUT
    • If cashout on cooldown → move to CASHOUT_WAIT

CASHOUT_WAIT:
  Pause all betting.  Sleep (with interrupt checks) until cooldown expires.
  Display countdown in log.  On expiry → retry cashout → POST_CASHOUT.

POST_CASHOUT:
  If continue_after_cashout is True AND faucet still has claims available:
    → reset current_round stats, stay FARMING, aim for same target again.
  Else → stop session.

This means the bot can cycle indefinitely:
  claim → bet → cashout → [wait if cooldown] → claim → bet → cashout → …
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Callable, Optional

from .accounts import Account
from .api import DuckDiceAPI, CookieExpiredError, RateLimitError
from .network import NetworkProfileManager, ProfileType
from .tictactoe import TicTacToeClaimEngine

logger = logging.getLogger(__name__)


class BotError(Exception):
    pass


class BotState(Enum):
    FARMING       = auto()   # claiming + betting toward target
    CASHOUT_WAIT  = auto()   # target hit, waiting for cashout cooldown
    POST_CASHOUT  = auto()   # cashout done, deciding whether to continue
    STOPPED       = auto()


class FaucetBot:
    """Bot for a single Account.  Instantiate one per account for parallel runs."""

    def __init__(
        self,
        account: Account,
        network_mgr: NetworkProfileManager,
        target_amount: float = 20.0,
        house_edge: float = 0.03,
        auto_cashout: bool = True,
        cashout_threshold: float = 0.0,       # 0 = use target_amount
        cashout_cooldown_hint: int = 3600,     # expected cooldown (s); overridden by API
        continue_after_cashout: bool = True,   # keep farming after each cashout
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self.account = account
        self._net_mgr = network_mgr
        self.target_amount = target_amount
        self.house_edge = house_edge
        self.auto_cashout = auto_cashout
        self.cashout_threshold = cashout_threshold or target_amount
        self.cashout_cooldown_hint = cashout_cooldown_hint
        self.continue_after_cashout = continue_after_cashout
        self._log_cb = log_callback or (lambda msg: logger.info("[%s] %s", account.label, msg))

        self.running = False
        self.paused  = False
        self._state  = BotState.STOPPED

        self._last_claim_time: float = 0.0
        self.claim_cooldown: int = 60

        # Cashout tracking
        self._cashout_available_at: float = 0.0   # epoch seconds; 0 = available now
        self._cashout_count: int = 0
        self._total_cashed_out: float = 0.0

        self.stats = {
            "session_start":    None,
            "total_bets":       0,
            "total_wins":       0,
            "total_losses":     0,
            "starting_balance": 0.0,
            "current_balance":  0.0,
            "total_claimed":    0.0,
            "cashout_count":    0,
            "total_cashed_out": 0.0,
            "rounds_completed": 0,   # how many full target→cashout cycles
        }

        self._api: Optional[DuckDiceAPI] = None

    # ── Logging ────────────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self._log_cb(f"[{ts}] {msg}")

    # ── Network routing ────────────────────────────────────────────────────

    def _build_api(self) -> DuckDiceAPI:
        proxies: Optional[dict] = None
        profile_id = self.account.network_profile_id
        if profile_id:
            profile = self._net_mgr.get(profile_id)
            if profile and profile.type == ProfileType.PROXY:
                proxies = self._net_mgr.get_proxies_dict(profile_id)
        return DuckDiceAPI(
            api_key=self.account.api_key,
            cookie=self.account.cookie,
            fingerprint=self.account.fingerprint,
            proxies=proxies,
        )

    # ── Session lifecycle ──────────────────────────────────────────────────

    def start(self) -> None:
        self.running = True
        self._state  = BotState.FARMING
        self.stats["session_start"] = datetime.now(timezone.utc)

        self._log("=" * 60)
        self._log(f"🎰 BOT STARTED  |  {self.account.label}")
        self._log("=" * 60)

        self._vpn_connect()
        self._api = self._build_api()

        paw = self._api.get_paw_level(force=True)
        self.account.paw_level = paw
        self._log(f"🐾 PAW {paw}  |  TTT needed: {self._api.ttt_games_needed()}")

        currency = self.account.preferred_currency
        min_bet  = self._api.get_min_bet(currency)
        self._log(f"💱 {currency}  |  min bet: {min_bet}  |  target: {self.target_amount}")
        self._log(f"💰 Auto-cashout: {'ON' if self.auto_cashout else 'OFF'}"
                  + (f"  |  continue after cashout: ON" if self.continue_after_cashout else ""))

        balance = self._api.get_balance(currency)
        self.stats["starting_balance"] = balance["faucet"]

        self._main_loop(currency, min_bet)

    def stop(self) -> None:
        self.running = False
        self._state = BotState.STOPPED
        self._log("🛑 Bot stopped")
        self._vpn_disconnect()

    def pause(self) -> None:
        self.paused = True
        self._log("⏸  Bot paused")

    def resume(self) -> None:
        self.paused = False
        self._log("▶  Bot resumed")

    def cashout_now(self) -> None:
        """Manual cashout trigger (called from GUI button)."""
        if self._api and self._state in (BotState.FARMING, BotState.CASHOUT_WAIT):
            currency = self.account.preferred_currency
            balance  = self._api.get_balance(currency)
            faucet   = balance["faucet"]
            if faucet > 0:
                self._do_cashout(currency, faucet)

    # ── VPN lifecycle ──────────────────────────────────────────────────────

    def _vpn_connect(self) -> None:
        pid = self.account.network_profile_id
        if not pid:
            return
        profile = self._net_mgr.get(pid)
        if profile and profile.type == ProfileType.VPN:
            self._log("🛡 Connecting VPN…")
            ok = self._net_mgr.vpn_connect(pid)
            if ok:
                ip = self._net_mgr.verify_ip(pid)
                self._log(f"🛡 VPN up  |  IP: {ip or 'unknown'}")
            else:
                self.running = False
                raise BotError("VPN connection failed — aborting for safety.")

    def _vpn_disconnect(self) -> None:
        pid = self.account.network_profile_id
        if pid:
            profile = self._net_mgr.get(pid)
            if profile and profile.type == ProfileType.VPN:
                self._net_mgr.vpn_disconnect(pid)
                self._log("🛡 VPN disconnected")

    # ── Main loop ──────────────────────────────────────────────────────────

    def _main_loop(self, currency: str, min_bet: float) -> None:
        """
        Outer loop that drives the full
        FARMING → CASHOUT_WAIT → POST_CASHOUT → FARMING … cycle.
        """
        while self.running and self._state != BotState.STOPPED:
            self._wait_if_paused()
            if not self.running:
                break

            if self._state == BotState.FARMING:
                self._farm_one_round(currency, min_bet)

            elif self._state == BotState.CASHOUT_WAIT:
                self._wait_for_cashout(currency)

            elif self._state == BotState.POST_CASHOUT:
                if self.continue_after_cashout:
                    self._log("─" * 50)
                    self._log(f"🔄 Round {self.stats['rounds_completed']} complete. "
                              "Starting new round toward same target…")
                    self.stats["rounds_completed"] += 1
                    self._state = BotState.FARMING
                else:
                    self._log("✅ continue_after_cashout is OFF — stopping.")
                    self.running = False

        self._show_stats()

    def _farm_one_round(self, currency: str, min_bet: float) -> None:
        """
        Inner farming loop: claim → bet → repeat until target reached.
        Sets self._state on exit.
        """
        assert self._api is not None

        while self.running and self._state == BotState.FARMING:
            self._wait_if_paused()
            if not self.running:
                return

            try:
                balance = self._api.get_balance(currency)
            except CookieExpiredError:
                self._log("🔑 Cookie expired — please update your cookie.")
                self.running = False
                return
            except RateLimitError as e:
                self._log(f"⚠️  {e}"); time.sleep(30); continue

            faucet = balance["faucet"]
            self.stats["current_balance"] = faucet

            # ── Target reached ──────────────────────────────────────────
            if faucet >= self.cashout_threshold:
                self._log(f"🎯 TARGET REACHED: {faucet:.8f} {currency}")
                if self.auto_cashout:
                    self._trigger_cashout(currency, faucet)
                else:
                    self._log("💰 Auto-cashout disabled. Stopping at target.")
                    self.running = False
                return

            # ── Need to claim ───────────────────────────────────────────
            if faucet < min_bet:
                self._do_claim(currency)
                continue

            # ── Bet ─────────────────────────────────────────────────────
            self._do_bet(currency, faucet)

    # ── Cashout orchestration ──────────────────────────────────────────────

    def _trigger_cashout(self, currency: str, amount: float) -> None:
        """
        Try to cashout.  If cooldown is active, transition to CASHOUT_WAIT.
        """
        # Quick pre-check (dry-run probe)
        remaining = self._cashout_cooldown_remaining()
        if remaining > 0:
            self._log(f"⏳ Cashout cooldown: {_fmt_duration(remaining)} remaining. "
                      "Pausing betting…")
            self._cashout_available_at = time.time() + remaining
            self._state = BotState.CASHOUT_WAIT
            return

        self._do_cashout(currency, amount)

    def _do_cashout(self, currency: str, amount: float) -> None:
        assert self._api is not None
        self._log(f"💰 Cashing out {amount:.8f} {currency} → main wallet…")
        result = self._api.cashout(currency, amount)

        if result["success"]:
            transferred = result["amount"]
            cooldown    = result["cooldown"]
            self._cashout_count += 1
            self._total_cashed_out += transferred
            self.stats["cashout_count"]    = self._cashout_count
            self.stats["total_cashed_out"] = self._total_cashed_out

            self._log(f"✅ Cashout successful: {transferred:.8f} {currency} → main")
            if cooldown > 0:
                self._cashout_available_at = time.time() + cooldown
                self._log(f"⏳ Next cashout available in {_fmt_duration(cooldown)}")
            else:
                self._cashout_available_at = 0.0

            self._state = BotState.POST_CASHOUT

        else:
            cooldown = result.get("cooldown", self.cashout_cooldown_hint)
            self._log(f"⚠️  Cashout failed: {result['message']}")
            if cooldown > 0:
                self._log(f"⏳ Cooldown: {_fmt_duration(cooldown)} — pausing betting.")
                self._cashout_available_at = time.time() + cooldown
                self._state = BotState.CASHOUT_WAIT
            else:
                # Non-cooldown failure: log and continue farming
                self._log("↩️  Will retry cashout on next target hit.")

    def _wait_for_cashout(self, currency: str) -> None:
        """
        Sleep until the cashout cooldown expires, logging a countdown every
        60 s (or every 10 s in the last minute).  Then attempt cashout again.
        """
        assert self._api is not None
        self._log("⏸  CASHOUT WAIT — betting suspended until cooldown expires.")

        while self.running and self._state == BotState.CASHOUT_WAIT:
            remaining = self._cashout_cooldown_remaining()
            if remaining <= 0:
                break

            # Log interval: every 60 s normally, every 10 s in final minute
            interval = 10 if remaining < 60 else 60
            self._log(f"⏳ Cashout available in {_fmt_duration(remaining)} — "
                      f"next check in {interval}s")

            # Sleep in 1-second ticks so pause/stop is responsive
            for _ in range(interval):
                if not self.running:
                    return
                self._wait_if_paused()
                time.sleep(1)

        if not self.running:
            return

        # Cooldown expired — attempt cashout with current faucet balance
        try:
            balance = self._api.get_balance(currency)
        except Exception:
            balance = {"faucet": 0.0}

        faucet = balance.get("faucet", 0.0)
        if faucet > 0:
            self._do_cashout(currency, faucet)
        else:
            # Faucet is empty after cooldown (was bet away / already cashed out)
            self._log("ℹ️  Faucet is empty after cooldown. Resuming farming.")
            self._state = BotState.POST_CASHOUT

    def _cashout_cooldown_remaining(self) -> int:
        """Seconds until cashout is allowed.  0 = available now."""
        if self._cashout_available_at == 0.0:
            return 0
        remaining = self._cashout_available_at - time.time()
        return max(0, int(remaining))

    # ── Claiming ───────────────────────────────────────────────────────────

    def _do_claim(self, currency: str) -> None:
        assert self._api is not None
        elapsed = time.time() - self._last_claim_time
        if elapsed < self.claim_cooldown:
            wait = int(self.claim_cooldown - elapsed)
            self._log(f"⏳ Claim cooldown: {wait}s…")
            for remaining in range(wait, 0, -1):
                if not self.running:
                    return
                self._wait_if_paused()
                if remaining % 10 == 0:
                    self._log(f"⏳ Claim cooldown: {remaining}s")
                time.sleep(1)

        games = self._api.ttt_games_needed()
        if games > 0:
            self._log(f"🎮 PAW {self.account.paw_level}: playing {games} TTT game(s)…")
            pid = self.account.network_profile_id
            pw_proxy = self._net_mgr.get_playwright_proxy(pid) if pid else None
            engine = TicTacToeClaimEngine(
                cookie=self.account.cookie,
                fingerprint=self.account.fingerprint,
                playwright_proxy=pw_proxy,
            )
            try:
                ok = engine.run(games_needed=games, currency=currency)
            except Exception as e:
                self._log(f"❌ TTT error: {e}"); time.sleep(10); return
            if ok:
                self._last_claim_time = time.time()
                self.stats["total_claimed"] += 1
                self._log("✅ Faucet claimed via TTT!")
                self.account.paw_level = self._api.get_paw_level(force=True)
            else:
                self._log("❌ TTT claim failed. Retry in 10s…"); time.sleep(10)
        else:
            self._log("🔵 Claiming faucet (direct)…")
            try:
                ok = self._api.claim_faucet(currency)
            except CookieExpiredError:
                self._log("🔑 Cookie expired during claim."); self.running = False; return
            if ok:
                self._last_claim_time = time.time()
                self.stats["total_claimed"] += 1
                self._log("✅ Faucet claimed!")
                time.sleep(10)
            else:
                self._log("❌ Claim failed. Retry in 10s…"); time.sleep(10)

    # ── Betting ────────────────────────────────────────────────────────────

    def _do_bet(self, currency: str, faucet: float) -> None:
        assert self._api is not None
        multiplier = self.cashout_threshold / faucet if faucet else 0
        raw_chance = (100.0 * (1.0 - self.house_edge)) / multiplier if multiplier else 0.0
        chance = max(0.01, min(99.0, round(raw_chance, 2)))

        self._log(f"🎲 {faucet:.8f} {currency}  |  {multiplier:.2f}x needed  |  "
                  f"chance: {chance:.2f}%")

        try:
            result = self._api.play_dice(currency, faucet, chance,
                                         is_high=True, use_faucet=True)
        except CookieExpiredError:
            self._log("🔑 Cookie expired during bet."); self.running = False; return
        except RateLimitError as e:
            self._log(f"⚠️  {e}"); time.sleep(30); return

        self.stats["total_bets"] += 1
        if result:
            data    = result.get("data", {})
            new_bal = float(data.get("balance", {}).get("faucet", 0))
            win     = data.get("win", False)
            if win:
                self.stats["total_wins"] += 1
                self._log(f"🎉 WON!  Faucet: {new_bal:.8f} {currency}")
            else:
                self.stats["total_losses"] += 1
                self._log(f"❌ Lost.  Faucet: {new_bal:.8f} {currency}")
        else:
            self._log("❌ Bet failed (no response).")
        time.sleep(2)

    # ── Helpers ────────────────────────────────────────────────────────────

    def _wait_if_paused(self) -> None:
        while self.paused and self.running:
            time.sleep(0.5)

    def _show_stats(self) -> None:
        self._log("=" * 60)
        self._log("📊 SESSION STATS")
        self._log("=" * 60)
        start = self.stats["session_start"]
        if start:
            self._log(f"Duration:        {datetime.now(timezone.utc) - start}")
        self._log(f"Rounds:          {self.stats['rounds_completed']}")
        self._log(f"Total bets:      {self.stats['total_bets']}")
        n = self.stats["total_bets"]
        if n:
            wr = self.stats["total_wins"] / n * 100
            self._log(f"Wins/Losses:     {self.stats['total_wins']} / "
                      f"{self.stats['total_losses']}  ({wr:.1f}%)")
        self._log(f"Claims made:     {self.stats['total_claimed']}")
        self._log(f"Cashouts:        {self.stats['cashout_count']}  "
                  f"(total: {self.stats['total_cashed_out']:.8f})")
        profit = self.stats["current_balance"] - self.stats["starting_balance"]
        self._log(f"Faucet P/L:      {profit:+.8f}")
        self._log("=" * 60)

    def get_stats(self) -> dict:
        return self.stats.copy()

    def get_cashout_countdown(self) -> int:
        """Seconds remaining until next cashout (for GUI display)."""
        return self._cashout_cooldown_remaining()

    def get_state(self) -> str:
        return self._state.name


# ── Utility ────────────────────────────────────────────────────────────────

def _fmt_duration(seconds: int) -> str:
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"
