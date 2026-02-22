"""
FaucetPlay — Bot Engine
Single-account faucet farming: claim → bet → cashout → repeat.

State machine
─────────────
FARMING      Claim faucet (PAW-aware TTT if needed) → bet toward target.
             On target reached → attempt cashout if auto_cashout is enabled.
CASHOUT_WAIT Target hit, cashout on cooldown. Pause betting, countdown, retry.
POST_CASHOUT Cashout done. If continue_after_cashout → new round; else stop.
STOPPED      Terminal state.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Callable, Optional

from .api import DuckDiceAPI, CookieExpiredError, RateLimitError
from .config import BotConfig
from .tictactoe import TicTacToeClaimEngine

logger = logging.getLogger(__name__)


class BotError(Exception):
    pass


class BotState(Enum):
    FARMING      = auto()
    CASHOUT_WAIT = auto()
    POST_CASHOUT = auto()
    STOPPED      = auto()


class FaucetBot:
    """Single-account faucet bot.  Create one instance; call start() in a thread."""

    def __init__(
        self,
        config: BotConfig,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self._cfg = config
        self._log_cb = log_callback or (lambda msg: logger.info(msg))

        self.running = False
        self.paused  = False
        self._state  = BotState.STOPPED

        self._last_claim_time: float = 0.0
        self.claim_cooldown: int = 60

        # Derived from config (set at start())
        self.target_amount: float = 0.0
        self.cashout_threshold: float = 0.0

        # Cashout cooldown tracking
        self._cashout_available_at: float = 0.0

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
            "rounds_completed": 0,
        }

        self._api: Optional[DuckDiceAPI] = None

    # ── Logging ────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self._log_cb(f"[{ts}] {msg}")

    # ── Session lifecycle ──────────────────────────────────────────

    def start(self) -> None:
        self.running = True
        self._state  = BotState.FARMING
        self.stats["session_start"] = datetime.now(timezone.utc)

        api_key  = self._cfg.get("api_key", "")
        cookie   = self._cfg.get("cookie", "")
        currency = self._cfg.get("currency", "USDC")
        self.target_amount    = float(self._cfg.get("target_amount") or 20.0)
        self.cashout_threshold = float(self._cfg.get("cashout_threshold") or 0) or self.target_amount

        self._api = DuckDiceAPI(api_key=api_key, cookie=cookie)

        self._log("=" * 60)
        self._log("🎰 FAUCETPLAY STARTED")
        self._log("=" * 60)

        paw = self._api.get_paw_level(force=True)
        self._log(f"🐾 PAW Level {paw}  |  TTT required: {self._api.ttt_games_needed()}")

        min_bet = self._api.get_min_bet(currency)
        self._log(f"💱 {currency}  |  min bet: {min_bet}  |  target: {self.target_amount}")
        auto_co = self._cfg.get("auto_cashout", False)
        self._log(f"💰 Auto-cashout: {'ON' if auto_co else 'OFF'}"
                  + (f"  threshold: {self.cashout_threshold}" if auto_co else ""))

        balance = self._api.get_balance(currency)
        self.stats["starting_balance"] = balance.get("faucet", 0.0)

        self._main_loop(currency, min_bet)

    def stop(self) -> None:
        self.running = False
        self._state = BotState.STOPPED
        self._log("🛑 Bot stopped")

    def pause(self) -> None:
        self.paused = True
        self._log("⏸  Bot paused")

    def resume(self) -> None:
        self.paused = False
        self._log("▶  Bot resumed")

    def cashout_now(self) -> None:
        """Manual cashout from GUI button."""
        if self._api and self._state in (BotState.FARMING, BotState.CASHOUT_WAIT):
            currency = self._cfg.get("currency", "USDC")
            balance  = self._api.get_balance(currency)
            faucet   = balance.get("faucet", 0.0)
            if faucet > 0:
                self._do_cashout(currency, faucet)

    # ── Main loop ──────────────────────────────────────────────────

    def _main_loop(self, currency: str, min_bet: float) -> None:
        while self.running and self._state != BotState.STOPPED:
            self._wait_if_paused()
            if not self.running:
                break

            if self._state == BotState.FARMING:
                self._farm_one_round(currency, min_bet)
            elif self._state == BotState.CASHOUT_WAIT:
                self._wait_for_cashout(currency)
            elif self._state == BotState.POST_CASHOUT:
                if self._cfg.get("continue_after_cashout", True):
                    self._log("─" * 50)
                    self._log(f"🔄 Round {self.stats['rounds_completed']} complete. "
                              "Starting new round…")
                    self.stats["rounds_completed"] += 1
                    self._state = BotState.FARMING
                else:
                    self._log("✅ continue_after_cashout is OFF — stopping.")
                    self.running = False

        self._show_stats()

    def _farm_one_round(self, currency: str, min_bet: float) -> None:
        assert self._api is not None
        while self.running and self._state == BotState.FARMING:
            self._wait_if_paused()
            if not self.running:
                return

            try:
                balance = self._api.get_balance(currency)
            except CookieExpiredError:
                self._log("🔑 Cookie expired — update it in Settings.")
                self.running = False
                return
            except RateLimitError as e:
                self._log(f"⚠️  {e}"); time.sleep(30); continue

            faucet = balance.get("faucet", 0.0)
            self.stats["current_balance"] = faucet

            if faucet >= self.cashout_threshold:
                self._log(f"🎯 TARGET REACHED: {faucet:.8f} {currency}")
                if self._cfg.get("auto_cashout", False):
                    self._trigger_cashout(currency, faucet)
                else:
                    self._log("💰 Auto-cashout disabled. Stopping.")
                    self.running = False
                return

            if faucet < min_bet:
                self._do_claim(currency)
                continue

            self._do_bet(currency, faucet)

    # ── Cashout orchestration ──────────────────────────────────────

    def _trigger_cashout(self, currency: str, amount: float) -> None:
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
            cooldown    = result.get("cooldown", 0)
            self.stats["cashout_count"]    += 1
            self.stats["total_cashed_out"] += transferred

            self._log(f"✅ Cashout OK: {transferred:.8f} {currency} → main")
            self._cashout_available_at = (time.time() + cooldown) if cooldown > 0 else 0.0
            if cooldown > 0:
                self._log(f"⏳ Next cashout in {_fmt_duration(cooldown)}")
            self._state = BotState.POST_CASHOUT
        else:
            cooldown = result.get("cooldown", self._cfg.get("cashout_cooldown_seconds", 3600))
            self._log(f"⚠️  Cashout failed: {result['message']}")
            if cooldown > 0:
                self._log(f"⏳ Cooldown: {_fmt_duration(cooldown)} — pausing.")
                self._cashout_available_at = time.time() + cooldown
                self._state = BotState.CASHOUT_WAIT

    def _wait_for_cashout(self, currency: str) -> None:
        assert self._api is not None
        self._log("⏸  Waiting for cashout cooldown…")
        while self.running and self._state == BotState.CASHOUT_WAIT:
            remaining = self._cashout_cooldown_remaining()
            if remaining <= 0:
                break
            interval = 10 if remaining < 60 else 60
            self._log(f"⏳ Cashout in {_fmt_duration(remaining)} — next check in {interval}s")
            for _ in range(interval):
                if not self.running:
                    return
                self._wait_if_paused()
                time.sleep(1)
        if not self.running:
            return
        try:
            balance = self._api.get_balance(currency)
            faucet  = balance.get("faucet", 0.0)
        except Exception:
            faucet = 0.0
        if faucet > 0:
            self._do_cashout(currency, faucet)
        else:
            self._state = BotState.POST_CASHOUT

    def _cashout_cooldown_remaining(self) -> int:
        if self._cashout_available_at == 0.0:
            return 0
        return max(0, int(self._cashout_available_at - time.time()))

    # ── Claiming ───────────────────────────────────────────────────

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
            self._log(f"🎮 PAW level requires {games} TTT game(s)…")
            engine = TicTacToeClaimEngine(
                cookie=self._cfg.get("cookie", ""),
                fingerprint=None,
                playwright_proxy=None,
            )
            try:
                ok = engine.run(games_needed=games, currency=currency)
            except Exception as e:
                self._log(f"❌ TTT error: {e}"); time.sleep(10); return
            if ok:
                self._last_claim_time = time.time()
                self.stats["total_claimed"] += 1
                self._log("✅ Claimed via Tic-Tac-Toe!")
                paw = self._api.get_paw_level(force=True)
                self._log(f"🐾 PAW updated: {paw}")
            else:
                self._log("❌ TTT failed. Retry in 10s…"); time.sleep(10)
        else:
            self._log("🔵 Claiming faucet…")
            try:
                ok = self._api.claim_faucet(currency)
            except CookieExpiredError:
                self._log("🔑 Cookie expired."); self.running = False; return
            if ok:
                self._last_claim_time = time.time()
                self.stats["total_claimed"] += 1
                self._log("✅ Faucet claimed!")
                time.sleep(10)
            else:
                self._log("❌ Claim failed. Retry in 10s…"); time.sleep(10)

    # ── Betting ────────────────────────────────────────────────────

    def _do_bet(self, currency: str, faucet: float) -> None:
        assert self._api is not None
        house_edge = float(self._cfg.get("house_edge", 0.03))
        multiplier = self.cashout_threshold / faucet if faucet else 0
        raw_chance = (100.0 * (1.0 - house_edge)) / multiplier if multiplier else 0.0
        chance     = max(0.01, min(99.0, round(raw_chance, 2)))

        self._log(f"🎲 {faucet:.8f} {currency}  ×{multiplier:.2f}  chance {chance:.2f}%")

        try:
            result = self._api.play_dice(currency, faucet, chance,
                                         is_high=True, use_faucet=True)
        except CookieExpiredError:
            self._log("🔑 Cookie expired."); self.running = False; return
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
            self._log("❌ Bet failed.")
        time.sleep(2)

    # ── Helpers ────────────────────────────────────────────────────

    def _wait_if_paused(self) -> None:
        while self.paused and self.running:
            time.sleep(0.5)

    def _show_stats(self) -> None:
        self._log("=" * 60)
        self._log("📊 SESSION STATS")
        self._log("=" * 60)
        start = self.stats["session_start"]
        if start:
            self._log(f"Duration:    {datetime.now(timezone.utc) - start}")
        self._log(f"Rounds:      {self.stats['rounds_completed']}")
        n = self.stats["total_bets"]
        if n:
            wr = self.stats["total_wins"] / n * 100
            self._log(f"Bets:        {n}  W/L: {self.stats['total_wins']}/{self.stats['total_losses']}  ({wr:.1f}%)")
        self._log(f"Claims:      {self.stats['total_claimed']}")
        self._log(f"Cashouts:    {self.stats['cashout_count']}  total: {self.stats['total_cashed_out']:.8f}")
        profit = self.stats["current_balance"] - self.stats["starting_balance"]
        self._log(f"Faucet P/L:  {profit:+.8f}")
        self._log("=" * 60)

    def get_stats(self) -> dict:
        return self.stats.copy()

    def get_cashout_countdown(self) -> int:
        return self._cashout_cooldown_remaining()

    def get_state(self) -> str:
        return self._state.name


# ── Utility ────────────────────────────────────────────────────────

def _fmt_duration(seconds: int) -> str:
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"
