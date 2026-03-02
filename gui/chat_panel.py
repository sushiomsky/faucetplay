"""
FaucetPlay GUI — Auto-Chat Panel

Tab content for the Auto-Chat feature.  Allows the user to:
  • Enable / disable auto-chat with a dry-run safety toggle
  • Set message interval (minimum and maximum seconds)
  • Add / remove rest-period windows (HH:MM – HH:MM, no messages sent)
  • Browse, add, enable/disable, and delete chat messages

All changes are written immediately to BotConfig and the ChatMessageDB.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable, List, Optional

import customtkinter as ctk

from . import theme as T
from core.chat_db import ChatMessageDB
from core.chat_bot import ChatBot
from core.config import BotConfig


class ChatPanel(ctk.CTkScrollableFrame):
    """Full auto-chat settings and message manager."""

    def __init__(
        self,
        parent,
        config: BotConfig,
        db: ChatMessageDB,
        chat_bot: Optional[ChatBot] = None,
        on_save: Optional[Callable[[], None]] = None,
        **kw,
    ):
        super().__init__(parent, fg_color=T.BG, **kw)
        self._cfg      = config
        self._db       = db
        self._chat_bot = chat_bot
        self._on_save  = on_save

        # ── State vars ────────────────────────────────────────────
        self._enabled_var  = tk.BooleanVar(value=bool(config.get("chat_enabled",  False)))
        self._dry_run_var  = tk.BooleanVar(value=bool(config.get("chat_dry_run",   True)))
        self._min_var      = tk.StringVar(value=str(config.get("chat_interval_min", 120)))
        self._max_var      = tk.StringVar(value=str(config.get("chat_interval_max", 600)))

        # Rest-period rows: each entry is {"start": StringVar, "end": StringVar}
        self._rest_rows: List[dict] = []
        self._rest_container: Optional[ctk.CTkFrame] = None

        # Message list state
        self._msg_rows: List[dict] = []   # {"id": int, "text": str, frame, enabled_var}
        self._msg_container: Optional[ctk.CTkFrame] = None
        self._new_msg_var = tk.StringVar()

        self._status_lbl: Optional[ctk.CTkLabel] = None

        self._build()
        self._load_rest_periods()
        self._load_messages()

    # ── Layout ────────────────────────────────────────────────────────────

    def _build(self) -> None:
        def _section(text: str):
            f = ctk.CTkFrame(self, fg_color=T.BG3, height=32, corner_radius=6)
            f.pack(fill="x", pady=(14, 4))
            ctk.CTkLabel(f, text=text, font=T.FONT_H3,
                          text_color=T.ACCENT2).pack(side="left", padx=10, pady=6)

        # ── Enable / dry-run ──────────────────────────────────────
        _section("💬  Auto-Chat")

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", pady=4)

        ctk.CTkSwitch(
            top, text="Enable auto-chat", variable=self._enabled_var,
            font=T.FONT_BODY, text_color=T.TEXT,
            progress_color=T.ACCENT,
        ).pack(side="left", padx=(4, 20))

        ctk.CTkSwitch(
            top, text="🔇 Dry run  (log only — never sends to real chat)",
            variable=self._dry_run_var,
            font=T.FONT_BODY, text_color=T.YELLOW,
            progress_color=T.YELLOW,
        ).pack(side="left")

        dry_hint = ctk.CTkLabel(
            self,
            text="⚠  Dry run is ON by default. Disable it only when you want to "
                 "post messages to the live DuckDice chat.",
            font=T.FONT_SMALL, text_color=T.TEXT_DIM,
            wraplength=600, justify="left",
        )
        dry_hint.pack(anchor="w", padx=6, pady=(0, 6))

        # ── Interval ──────────────────────────────────────────────
        _section("⏱  Message Interval")

        int_row = ctk.CTkFrame(self, fg_color="transparent")
        int_row.pack(fill="x", pady=4)

        def _int_field(label: str, var: tk.StringVar, hint: str):
            f = ctk.CTkFrame(int_row, fg_color="transparent")
            f.pack(side="left", padx=(0, 24))
            ctk.CTkLabel(f, text=label, font=T.FONT_BODY,
                          text_color=T.TEXT).pack(anchor="w")
            ctk.CTkEntry(f, textvariable=var, width=90, height=32).pack()
            ctk.CTkLabel(f, text=hint, font=T.FONT_SMALL,
                          text_color=T.TEXT_DIM).pack(anchor="w")

        _int_field("Minimum (seconds)", self._min_var, "e.g. 120  (2 min)")
        _int_field("Maximum (seconds)", self._max_var, "e.g. 600  (10 min)")

        ctk.CTkLabel(
            self,
            text="A random delay between Min and Max is chosen after each sent message.",
            font=T.FONT_SMALL, text_color=T.TEXT_DIM,
        ).pack(anchor="w", padx=6)

        # ── Rest periods ─────────────────────────────────────────
        _section("🌙  Rest Periods  (no messages sent)")

        ctk.CTkLabel(
            self,
            text="Add time windows where auto-chat stays silent (e.g. 23:00 – 07:00).  "
                 "Overnight ranges (end < start) are supported.",
            font=T.FONT_SMALL, text_color=T.TEXT_DIM,
            wraplength=600, justify="left",
        ).pack(anchor="w", padx=6, pady=(0, 4))

        self._rest_container = ctk.CTkFrame(self, fg_color="transparent")
        self._rest_container.pack(fill="x")

        ctk.CTkButton(
            self, text="＋  Add rest period", height=30,
            fg_color=T.BG3, hover_color=T.BG2, font=T.FONT_SMALL,
            command=self._add_rest_row,
        ).pack(anchor="w", padx=4, pady=(4, 8))

        # ── Message list ─────────────────────────────────────────
        _section("📝  Messages")

        # Add new message
        add_row = ctk.CTkFrame(self, fg_color="transparent")
        add_row.pack(fill="x", pady=(4, 2))
        ctk.CTkEntry(
            add_row, textvariable=self._new_msg_var,
            placeholder_text="Type a new message…", height=32,
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(
            add_row, text="Add", height=32, width=80,
            fg_color=T.ACCENT, hover_color=T.ACCENT2, font=T.FONT_SMALL,
            command=self._add_message,
        ).pack(side="left")

        ctk.CTkLabel(
            self,
            text="Toggle the checkbox to enable / disable individual messages without deleting them.",
            font=T.FONT_SMALL, text_color=T.TEXT_DIM,
        ).pack(anchor="w", padx=6, pady=(0, 4))

        # Scrollable message container
        self._msg_container = ctk.CTkFrame(
            self, fg_color=T.BG2, corner_radius=T.CORNER_MD
        )
        self._msg_container.pack(fill="x", pady=(0, 4))

        # ── Save button + status ──────────────────────────────────
        _section("")  # visual spacer

        save_row = ctk.CTkFrame(self, fg_color="transparent")
        save_row.pack(fill="x", pady=6)
        ctk.CTkButton(
            save_row, text="💾  Save chat settings", height=36,
            fg_color=T.ACCENT, hover_color=T.ACCENT2, font=T.FONT_BODY,
            command=self._save,
        ).pack(side="left", padx=(0, 12))

        self._status_lbl = ctk.CTkLabel(
            save_row, text="", font=T.FONT_SMALL, text_color=T.GREEN
        )
        self._status_lbl.pack(side="left")

        # Live stats row (populated by _refresh_stats via poll)
        self._stats_lbl = ctk.CTkLabel(
            self, text="", font=T.FONT_SMALL, text_color=T.TEXT_DIM
        )
        self._stats_lbl.pack(anchor="w", padx=6)
        self._poll_stats()

    # ── Rest period rows ──────────────────────────────────────────────────

    def _load_rest_periods(self) -> None:
        periods: list = self._cfg.get("chat_rest_periods", []) or []
        for p in periods:
            self._add_rest_row(p.get("start", "22:00"), p.get("end", "07:00"))

    def _add_rest_row(self, start: str = "22:00", end: str = "07:00") -> None:
        assert self._rest_container is not None
        row = ctk.CTkFrame(self._rest_container, fg_color="transparent")
        row.pack(fill="x", pady=2)

        sv = tk.StringVar(value=start)
        ev = tk.StringVar(value=end)

        ctk.CTkLabel(row, text="From", font=T.FONT_SMALL,
                      text_color=T.TEXT_DIM, width=36).pack(side="left")
        ctk.CTkEntry(row, textvariable=sv, width=70, height=28).pack(side="left", padx=(2, 8))
        ctk.CTkLabel(row, text="To", font=T.FONT_SMALL,
                      text_color=T.TEXT_DIM, width=20).pack(side="left")
        ctk.CTkEntry(row, textvariable=ev, width=70, height=28).pack(side="left", padx=(2, 8))
        ctk.CTkLabel(row, text="(HH:MM  24h)", font=T.FONT_SMALL,
                      text_color=T.TEXT_DIM).pack(side="left", padx=(0, 8))

        entry = {"start": sv, "end": ev, "frame": row}
        self._rest_rows.append(entry)

        def _remove():
            self._rest_rows.remove(entry)
            row.destroy()

        ctk.CTkButton(
            row, text="✕", width=28, height=28,
            fg_color=T.BG3, hover_color=T.RED, font=T.FONT_SMALL,
            command=_remove,
        ).pack(side="left")

    # ── Message list ──────────────────────────────────────────────────────

    def _load_messages(self) -> None:
        assert self._msg_container is not None
        # Clear existing rows
        for r in self._msg_rows:
            r["frame"].destroy()
        self._msg_rows.clear()
        for row in self._db.get_all():
            self._add_msg_row(row["id"], row["text"], bool(row["enabled"]))

    def _add_msg_row(self, row_id: int, text: str, enabled: bool) -> None:
        assert self._msg_container is not None
        frame = ctk.CTkFrame(self._msg_container, fg_color="transparent", height=30)
        frame.pack(fill="x", padx=6, pady=1)
        frame.pack_propagate(False)

        enabled_var = tk.BooleanVar(value=enabled)

        def _on_toggle():
            self._db.set_enabled(row_id, enabled_var.get())

        ctk.CTkCheckBox(
            frame, text="", variable=enabled_var,
            command=_on_toggle, width=24, height=24,
        ).pack(side="left", padx=(2, 4))

        ctk.CTkLabel(
            frame, text=text, font=T.FONT_SMALL,
            text_color=T.TEXT if enabled else T.TEXT_DIM,
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        entry = {"id": row_id, "text": text, "frame": frame, "enabled_var": enabled_var}
        self._msg_rows.append(entry)

        def _remove():
            self._db.remove(row_id)
            self._msg_rows.remove(entry)
            frame.destroy()

        ctk.CTkButton(
            frame, text="✕", width=24, height=24,
            fg_color="transparent", hover_color=T.RED, font=T.FONT_SMALL,
            command=_remove,
        ).pack(side="right", padx=2)

    def _add_message(self) -> None:
        text = self._new_msg_var.get().strip()
        if not text:
            return
        new_id = self._db.add(text)
        if new_id is None:
            self._flash_status("Message already exists.", T.YELLOW)
            return
        self._add_msg_row(new_id, text, True)
        self._new_msg_var.set("")
        self._flash_status(f"Added: {text[:40]}…" if len(text) > 40 else f"Added: {text}", T.GREEN)

    # ── Save ──────────────────────────────────────────────────────────────

    def _save(self) -> None:
        # Validate intervals
        try:
            imin = int(self._min_var.get())
            imax = int(self._max_var.get())
            if imin < 10:
                raise ValueError("min < 10")
            if imax <= imin:
                raise ValueError("max <= min")
        except ValueError as exc:
            self._flash_status(f"Invalid interval: {exc}", T.RED)
            return

        # Collect rest periods
        rest_periods = []
        for row in self._rest_rows:
            s = row["start"].get().strip()
            e = row["end"].get().strip()
            if s and e:
                rest_periods.append({"start": s, "end": e})

        self._cfg.set("chat_enabled",       self._enabled_var.get())
        self._cfg.set("chat_dry_run",        self._dry_run_var.get())
        self._cfg.set("chat_interval_min",   imin)
        self._cfg.set("chat_interval_max",   imax)
        self._cfg.set("chat_rest_periods",   rest_periods)
        self._cfg.save()

        # Propagate to running ChatBot immediately (it re-reads on each loop)
        # No extra call needed — ChatBot calls _refresh_config() each iteration.

        self._flash_status("✅  Chat settings saved.", T.GREEN)
        if self._on_save:
            self._on_save()

    # ── Live stats polling ────────────────────────────────────────────────

    def _poll_stats(self) -> None:
        if self._chat_bot:
            cb = self._chat_bot
            mode   = "🔇 dry run" if cb.dry_run else "🟢 live"
            status = "running" if cb.is_running() else "stopped"
            nxt    = f"next in {cb.next_send_in}s" if cb.next_send_in > 0 else ""
            parts  = [
                f"Status: {status}  [{mode}]",
                f"Sent: {cb.sent_count}",
                f"Skipped: {cb.skipped_count}",
            ]
            if cb.last_message:
                parts.append(f'Last: "{cb.last_message[:30]}…"' if len(cb.last_message) > 30
                              else f'Last: "{cb.last_message}"')
            if nxt:
                parts.append(nxt)
            self._stats_lbl.configure(text="  ·  ".join(parts))
        self.after(1000, self._poll_stats)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _flash_status(self, text: str, colour: str = T.GREEN) -> None:
        if self._status_lbl:
            self._status_lbl.configure(text=text, text_color=colour)
            self.after(4000, lambda: self._status_lbl.configure(text=""))  # type: ignore[union-attr]
