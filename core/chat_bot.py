"""
FaucetPlay — Auto-Chat Engine

Sends random messages to the DuckDice chat at randomised intervals within a
configured window, and stays silent during configured rest periods.

Config keys (stored in BotConfig)
──────────────────────────────────
  chat_enabled         bool    Master on/off switch
  chat_dry_run         bool    Log message instead of actually sending it
  chat_interval_min    int     Minimum seconds between messages (default 120)
  chat_interval_max    int     Maximum seconds between messages (default 600)
  chat_rest_periods    list    Each item: {"start": "HH:MM", "end": "HH:MM"}
                               During these windows no messages are sent.

Usage
─────
    bot = ChatBot(api, config, db)
    bot.start()   # spawns a background daemon thread
    bot.stop()    # signals the thread to exit
"""

from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime, timezone
from typing import Callable, List, Optional

from .api import DuckDiceAPI
from .chat_db import ChatMessageDB
from .config import BotConfig

logger = logging.getLogger(__name__)


class ChatBot:
    """Background auto-chat engine.  One instance per GUI session."""

    # Minimum sane interval values (guards against mis-config)
    MIN_INTERVAL_FLOOR = 10   # seconds
    MAX_INTERVAL_CEIL  = 86400  # 24 h

    def __init__(
        self,
        api: DuckDiceAPI,
        config: BotConfig,
        db: Optional[ChatMessageDB] = None,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self._api  = api
        self._cfg  = config
        self._db   = db or ChatMessageDB()
        self._log  = log_callback or (lambda m: logger.info(m))

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Updated live from _refresh_config() on each iteration
        self.enabled:      bool  = False
        self.dry_run:      bool  = True
        self.interval_min: int   = 120
        self.interval_max: int   = 600
        self.rest_periods: List[dict] = []

        # Public stats (read from GUI thread)
        self.sent_count:   int  = 0
        self.skipped_count: int = 0
        self.last_message: str  = ""
        self.last_sent_at: Optional[str] = None
        self.next_send_in: int  = 0   # seconds

    # ── Control ───────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background chat thread (no-op if already running)."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, name="ChatBot", daemon=True
        )
        self._thread.start()
        self._log("💬 Auto-chat started")

    def stop(self) -> None:
        """Signal the thread to exit and wait briefly for it."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        self._log("💬 Auto-chat stopped")

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ── Main loop ─────────────────────────────────────────────────────────

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            self._refresh_config()

            if not self.enabled:
                # Sleep in small slices so stop() is responsive
                self._interruptible_sleep(10)
                continue

            if self._in_rest_period():
                self._log("💬 Auto-chat: rest period active — sleeping 60 s")
                self.skipped_count += 1
                self._interruptible_sleep(60)
                continue

            msg = self._db.get_random()
            if not msg:
                self._log("💬 Auto-chat: no enabled messages — sleeping 30 s")
                self._interruptible_sleep(30)
                continue

            if self.dry_run:
                self._log(f"💬 [DRY RUN — not sent] {msg}")
            else:
                ok = self._api.send_chat_message(msg)
                if ok:
                    self._log(f"💬 Chat sent: {msg}")
                else:
                    self._log("💬 Auto-chat: send failed — will retry next cycle")

            self.sent_count   += 1
            self.last_message  = msg
            self.last_sent_at  = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

            wait_min = max(self.MIN_INTERVAL_FLOOR, self.interval_min)
            wait_max = max(wait_min + 1, self.interval_max)
            wait_max = min(wait_max, self.MAX_INTERVAL_CEIL)
            wait = random.randint(wait_min, wait_max)
            self._log(f"💬 Auto-chat: next message in {wait}s")
            self.next_send_in = wait
            self._interruptible_sleep(wait)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _refresh_config(self) -> None:
        self.enabled      = bool(self._cfg.get("chat_enabled",      False))
        self.dry_run      = bool(self._cfg.get("chat_dry_run",       True))
        self.interval_min = int(self._cfg.get("chat_interval_min",   120))
        self.interval_max = int(self._cfg.get("chat_interval_max",   600))
        self.rest_periods = list(self._cfg.get("chat_rest_periods",  []) or [])

    def _interruptible_sleep(self, seconds: int) -> None:
        """Sleep in 1-second slices so stop() wakes us quickly."""
        remaining = seconds
        while remaining > 0 and not self._stop_event.is_set():
            self.next_send_in = remaining
            time.sleep(min(1, remaining))
            remaining -= 1
        self.next_send_in = 0

    def _in_rest_period(self) -> bool:
        """Return True if the current local time falls within any rest period."""
        now = datetime.now()
        now_minutes = now.hour * 60 + now.minute
        for period in self.rest_periods:
            try:
                start_h, start_m = map(int, period["start"].split(":"))
                end_h,   end_m   = map(int, period["end"].split(":"))
            except (KeyError, ValueError, AttributeError):
                continue
            start_mins = start_h * 60 + start_m
            end_mins   = end_h   * 60 + end_m
            if start_mins <= end_mins:
                if start_mins <= now_minutes < end_mins:
                    return True
            else:
                # Overnight period e.g. 22:00 – 06:00
                if now_minutes >= start_mins or now_minutes < end_mins:
                    return True
        return False
