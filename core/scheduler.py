"""
FaucetPlay — Scheduler
Single-account daily claim scheduling with jitter and system auto-start.
"""

from __future__ import annotations

import logging
import os
import platform
import random
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

import schedule

logger = logging.getLogger(__name__)


class BotScheduler:
    """Daily claim scheduler for a single account."""

    def __init__(self) -> None:
        self._on_trigger: Optional[Callable[[], None]] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._claim_times: List[str] = []   # list of "HH:MM" strings
        self._jitter_minutes: int = 0

    # ── Config ─────────────────────────────────────────────────────

    def set_claim_times(self, times: List[str], jitter_minutes: int = 0) -> None:
        """Set daily claim times (e.g. ["08:00", "20:00"]) and jitter."""
        self._claim_times = times
        self._jitter_minutes = jitter_minutes

    def on_trigger(self, callback: Callable[[], None]) -> None:
        """Register callback called when a claim time fires."""
        self._on_trigger = callback

    # ── Lifecycle ──────────────────────────────────────────────────

    def start(self) -> None:
        if self._running:
            return
        schedule.clear()
        for t in self._claim_times:
            schedule.every().day.at(t).do(self._fire)
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Scheduler started with times: %s (jitter ±%dm)",
                    self._claim_times, self._jitter_minutes)

    def stop(self) -> None:
        self._running = False
        schedule.clear()

    def _run(self) -> None:
        while self._running:
            schedule.run_pending()
            time.sleep(30)

    def _fire(self) -> None:
        if self._on_trigger is None:
            return
        jitter = 0
        if self._jitter_minutes > 0:
            jitter = random.randint(-self._jitter_minutes * 60,
                                     self._jitter_minutes * 60)
        if jitter > 0:
            logger.info("Scheduler jitter: waiting %ds before triggering", jitter)
            time.sleep(jitter)
        elif jitter < 0:
            pass  # fire early; skip negative sleep
        self._on_trigger()

    # ── System auto-start ──────────────────────────────────────────

    def register_autostart(self, app_path: str, app_name: str = "FaucetPlay") -> bool:
        """Register the app to start on system login."""
        system = platform.system()
        try:
            if system == "Windows":
                return self._autostart_windows(app_path, app_name)
            elif system == "Darwin":
                return self._autostart_macos(app_path, app_name)
            elif system == "Linux":
                return self._autostart_linux(app_path, app_name)
        except Exception as e:
            logger.warning("Auto-start registration failed: %s", e)
        return False

    def unregister_autostart(self, app_name: str = "FaucetPlay") -> bool:
        system = platform.system()
        try:
            if system == "Windows":
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                     r"Software\Microsoft\Windows\CurrentVersion\Run",
                                     0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(key, app_name)
                winreg.CloseKey(key)
                return True
            elif system == "Darwin":
                plist = Path.home() / "Library/LaunchAgents" / f"io.faucetplay.{app_name}.plist"
                if plist.exists():
                    plist.unlink()
                return True
            elif system == "Linux":
                entry = Path.home() / ".config/autostart" / f"{app_name}.desktop"
                if entry.exists():
                    entry.unlink()
                return True
        except Exception as e:
            logger.warning("Auto-start removal failed: %s", e)
        return False

    def _autostart_windows(self, path: str, name: str) -> bool:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ,
                          f'"{path}" --minimized')
        winreg.CloseKey(key)
        return True

    def _autostart_macos(self, path: str, name: str) -> bool:
        plist_dir = Path.home() / "Library/LaunchAgents"
        plist_dir.mkdir(parents=True, exist_ok=True)
        plist = plist_dir / f"io.faucetplay.{name}.plist"
        plist.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>io.faucetplay.{name}</string>
  <key>ProgramArguments</key><array>
    <string>{path}</string><string>--minimized</string>
  </array>
  <key>RunAtLoad</key><true/>
</dict></plist>
""")
        return True

    def _autostart_linux(self, path: str, name: str) -> bool:
        autostart_dir = Path.home() / ".config/autostart"
        autostart_dir.mkdir(parents=True, exist_ok=True)
        entry = autostart_dir / f"{name}.desktop"
        entry.write_text(f"""[Desktop Entry]
Type=Application
Name={name}
Exec="{path}" --minimized
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
""")
        return True
