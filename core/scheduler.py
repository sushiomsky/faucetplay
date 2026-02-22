"""
FaucetPlay — Scheduler
Handles:
  1. Per-account daily faucet claim times (with PAW-aware routing)
  2. Per-account session time windows (start/stop by weekday/time)
  3. System auto-start registration on Windows / macOS / Linux
  4. Jitter support for anti-fingerprinting
"""

from __future__ import annotations

import logging
import os
import platform
import random
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

import schedule

logger = logging.getLogger(__name__)

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ClaimTime:
    """A single daily claim time for one account."""
    time_str: str        # "HH:MM" in local time
    jitter_minutes: int = 0   # ±N minutes random offset


@dataclass
class SessionWindow:
    """A recurring session window for one account."""
    name: str = ""
    days: List[str] = field(default_factory=list)   # subset of DAYS
    start_time: str = "09:00"
    end_time: str   = "17:00"
    enabled: bool   = True
    max_duration_minutes: int = 0   # 0 = unlimited


@dataclass
class AccountSchedule:
    """Complete schedule config for one account."""
    account_id: str
    claim_times: List[ClaimTime] = field(default_factory=list)
    session_windows: List[SessionWindow] = field(default_factory=list)
    enabled: bool = True


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class BotScheduler:
    """
    Central scheduler.  One instance for the whole app.
    Callbacks are registered per account_id.
    """

    def __init__(self) -> None:
        self._schedules: Dict[str, AccountSchedule] = {}
        self._claim_callbacks:  Dict[str, Callable[[str], None]] = {}
        self._start_callbacks:  Dict[str, Callable[[str], None]] = {}
        self._stop_callbacks:   Dict[str, Callable[[str], None]] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # --- Registration ------------------------------------------------------

    def set_account_schedule(self, sched: AccountSchedule) -> None:
        self._schedules[sched.account_id] = sched
        if self._running:
            self._rebuild()

    def remove_account_schedule(self, account_id: str) -> None:
        self._schedules.pop(account_id, None)
        if self._running:
            self._rebuild()

    def on_claim(self, account_id: str, callback: Callable[[str], None]) -> None:
        """Register callback called when it's time to claim for account_id."""
        self._claim_callbacks[account_id] = callback

    def on_start(self, account_id: str, callback: Callable[[str], None]) -> None:
        """Register callback called when a session window opens."""
        self._start_callbacks[account_id] = callback

    def on_stop(self, account_id: str, callback: Callable[[str], None]) -> None:
        """Register callback called when a session window closes."""
        self._stop_callbacks[account_id] = callback

    # --- Schedule building -------------------------------------------------

    def _rebuild(self) -> None:
        schedule.clear()
        for acct_id, sched in self._schedules.items():
            if not sched.enabled:
                continue

            # Daily claim times
            for ct in sched.claim_times:
                jitter = random.randint(-ct.jitter_minutes, ct.jitter_minutes) \
                         if ct.jitter_minutes else 0
                h, m = map(int, ct.time_str.split(":"))
                m += jitter
                if m < 0:
                    h -= 1; m += 60
                if m >= 60:
                    h += 1; m -= 60
                h = h % 24
                time_str = f"{h:02d}:{m:02d}"

                def _claim(aid=acct_id):
                    cb = self._claim_callbacks.get(aid)
                    if cb:
                        threading.Thread(target=cb, args=(aid,), daemon=True).start()

                schedule.every().day.at(time_str).do(_claim)
                logger.debug("Scheduled claim for %s at %s (jitter: %+dm)",
                             acct_id, time_str, jitter)

            # Session windows
            for window in sched.session_windows:
                if not window.enabled:
                    continue
                for day in window.days:
                    day_sched = getattr(schedule.every(), day.lower(), None)
                    if day_sched is None:
                        continue

                    def _start(aid=acct_id):
                        cb = self._start_callbacks.get(aid)
                        if cb:
                            threading.Thread(target=cb, args=(aid,), daemon=True).start()

                    def _stop(aid=acct_id):
                        cb = self._stop_callbacks.get(aid)
                        if cb:
                            threading.Thread(target=cb, args=(aid,), daemon=True).start()

                    day_sched.at(window.start_time).do(_start)
                    day_sched.at(window.end_time).do(_stop)

    # --- Lifecycle ---------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._rebuild()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Scheduler started (%d account schedules)", len(self._schedules))

    def stop(self) -> None:
        self._running = False
        schedule.clear()
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("Scheduler stopped")

    def _loop(self) -> None:
        while self._running:
            schedule.run_pending()
            time.sleep(1)

    def next_run(self) -> str:
        nr = schedule.next_run()
        return nr.strftime("%Y-%m-%d %H:%M:%S") if nr else "No schedules"

    # --- System auto-start ------------------------------------------------

    @staticmethod
    def register_autostart(app_path: Optional[str] = None) -> bool:
        """
        Register the application to launch automatically on system startup.
        Returns True on success.
        """
        exe = app_path or sys.executable
        system = platform.system()

        try:
            if system == "Windows":
                return _autostart_windows(exe)
            elif system == "Darwin":
                return _autostart_macos(exe)
            elif system == "Linux":
                return _autostart_linux(exe)
            else:
                logger.warning("Auto-start not supported on %s", system)
                return False
        except Exception as e:
            logger.error("Failed to register auto-start: %s", e)
            return False

    @staticmethod
    def unregister_autostart() -> bool:
        """Remove the application from system startup."""
        system = platform.system()
        try:
            if system == "Windows":
                return _autostart_windows_remove()
            elif system == "Darwin":
                return _autostart_macos_remove()
            elif system == "Linux":
                return _autostart_linux_remove()
            return False
        except Exception as e:
            logger.error("Failed to remove auto-start: %s", e)
            return False


# ---------------------------------------------------------------------------
# Platform auto-start helpers
# ---------------------------------------------------------------------------

APP_NAME = "FaucetPlay"
APP_KEY  = "com.faucetplay.app"


def _autostart_windows(exe_path: str) -> bool:
    import winreg  # type: ignore
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0, winreg.KEY_SET_VALUE,
    )
    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ,
                      f'"{exe_path}" --minimized')
    winreg.CloseKey(key)
    logger.info("Windows auto-start registered")
    return True


def _autostart_windows_remove() -> bool:
    import winreg  # type: ignore
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE,
        )
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
    except FileNotFoundError:
        pass
    return True


def _autostart_macos(exe_path: str) -> bool:
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist = plist_dir / f"{APP_KEY}.plist"
    plist.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>            <string>{APP_KEY}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{exe_path}</string>
        <string>--minimized</string>
    </array>
    <key>RunAtLoad</key>        <true/>
    <key>KeepAlive</key>        <false/>
</dict>
</plist>
""")
    os.system(f"launchctl load {plist}")
    logger.info("macOS LaunchAgent registered: %s", plist)
    return True


def _autostart_macos_remove() -> bool:
    plist = Path.home() / "Library" / "LaunchAgents" / f"{APP_KEY}.plist"
    if plist.exists():
        os.system(f"launchctl unload {plist}")
        plist.unlink()
    return True


def _autostart_linux(exe_path: str) -> bool:
    desktop_dir = Path.home() / ".config" / "autostart"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    desktop = desktop_dir / f"{APP_KEY}.desktop"
    desktop.write_text(f"""[Desktop Entry]
Type=Application
Name={APP_NAME}
Exec={exe_path} --minimized
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
""")
    logger.info("Linux autostart entry created: %s", desktop)
    return True


def _autostart_linux_remove() -> bool:
    desktop = Path.home() / ".config" / "autostart" / f"{APP_KEY}.desktop"
    if desktop.exists():
        desktop.unlink()
    return True
