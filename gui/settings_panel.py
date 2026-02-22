"""
FaucetPlay GUI — Settings Panel
Inline-editable settings: credentials, strategy, cashout, schedule.
"""
from __future__ import annotations

import threading
import tkinter as tk
from typing import Callable, List, Optional

import customtkinter as ctk

from . import theme as T
from core.config import BotConfig
from core.scheduler import BotScheduler


class SettingsPanel(ctk.CTkScrollableFrame):
    """Full settings editor.  Changes are written back to BotConfig on save."""

    def __init__(self, parent, config: BotConfig,
                 scheduler: BotScheduler,
                 on_save: Optional[Callable[[], None]] = None,
                 **kw):
        super().__init__(parent, fg_color=T.BG, **kw)
        self._cfg   = config
        self._sched = scheduler
        self._on_save = on_save

        # StringVars
        self._api_key_var    = tk.StringVar(value=config.get("api_key", ""))
        self._cookie_var     = tk.StringVar(value=config.get("cookie", ""))
        self._currency_var   = tk.StringVar(value=config.get("currency", "USDC"))
        self._target_var     = tk.StringVar(value=str(config.get("target_amount", "20.0")))
        self._edge_var       = tk.StringVar(value=str(config.get("house_edge", "0.03")))
        self._auto_co_var    = tk.BooleanVar(value=bool(config.get("auto_cashout", True)))
        self._continue_var   = tk.BooleanVar(value=bool(config.get("continue_after_cashout", True)))
        self._sched_on_var   = tk.BooleanVar(value=bool(config.get("scheduler_enabled", False)))
        self._autostart_var  = tk.BooleanVar(value=False)

        # Schedule time entries (up to 3 claim times)
        saved_times: List[str] = config.get("schedules", []) or []
        while len(saved_times) < 3:
            saved_times.append("")
        self._time_vars = [tk.StringVar(value=t) for t in saved_times[:3]]
        self._jitter_var = tk.StringVar(value=str(config.get("jitter_minutes", "5")))

        self._build()

    def _build(self):
        def _section(text: str):
            f = ctk.CTkFrame(self, fg_color=T.BG3, height=32, corner_radius=6)
            f.pack(fill="x", pady=(14, 4))
            ctk.CTkLabel(f, text=text, font=T.FONT_H3,
                          text_color=T.ACCENT2).pack(side="left", padx=10, pady=6)

        def _row(label: str, widget_factory):
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=label, width=160, anchor="w",
                          font=T.FONT_BODY, text_color=T.TEXT).pack(side="left")
            w = widget_factory(row)
            w.pack(side="left", fill="x", expand=True)
            return w

        def _secret_row(label: str, var: tk.StringVar):
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=label, width=160, anchor="w",
                          font=T.FONT_BODY, text_color=T.TEXT).pack(side="left")
            e = ctk.CTkEntry(row, textvariable=var, show="•", height=32)
            e.pack(side="left", fill="x", expand=True)
            show_var = tk.BooleanVar(value=False)
            def _toggle():
                e.configure(show="" if show_var.get() else "•")
            ctk.CTkCheckBox(row, text="Show", variable=show_var, command=_toggle,
                             width=60, font=T.FONT_SMALL).pack(side="left", padx=(6,0))

        # ── Credentials ─────────────────────────────────────────
        _section("🔑  Credentials")
        _secret_row("API Key", self._api_key_var)
        _secret_row("Cookie", self._cookie_var)

        hint = ctk.CTkLabel(self, text=(
            "How to find your cookie: DuckDice.io → F12 → Application "
            "→ Cookies → copy the full string."
        ), font=T.FONT_SMALL, text_color=T.TEXT_DIM, wraplength=480, justify="left")
        hint.pack(anchor="w", padx=4, pady=(0,4))

        # ── Strategy ─────────────────────────────────────────────
        _section("🎲  Strategy")
        _row("Currency", lambda p: ctk.CTkEntry(p, textvariable=self._currency_var, height=32))
        _row("Target amount", lambda p: ctk.CTkEntry(p, textvariable=self._target_var, height=32))
        _row("House edge (0–1)", lambda p: ctk.CTkEntry(p, textvariable=self._edge_var, height=32))

        # ── Cashout ───────────────────────────────────────────────
        _section("💰  Cashout")
        co_row = ctk.CTkFrame(self, fg_color="transparent")
        co_row.pack(fill="x", pady=3)
        ctk.CTkCheckBox(co_row, text="Auto cashout when target reached",
                         variable=self._auto_co_var, font=T.FONT_BODY).pack(anchor="w")
        ct_row = ctk.CTkFrame(self, fg_color="transparent")
        ct_row.pack(fill="x", pady=3)
        ctk.CTkCheckBox(ct_row, text="Continue farming same target after each cashout",
                         variable=self._continue_var, font=T.FONT_BODY).pack(anchor="w")

        # ── Schedule ──────────────────────────────────────────────
        _section("⏰  Schedule")
        sc_row = ctk.CTkFrame(self, fg_color="transparent")
        sc_row.pack(fill="x", pady=3)
        ctk.CTkCheckBox(sc_row, text="Enable daily scheduled claiming",
                         variable=self._sched_on_var, font=T.FONT_BODY).pack(anchor="w")

        sched_box = ctk.CTkFrame(self, fg_color=T.BG2, corner_radius=8)
        sched_box.pack(fill="x", pady=4)
        ctk.CTkLabel(sched_box, text="Claim times (HH:MM, leave blank to skip)",
                      font=T.FONT_SMALL, text_color=T.TEXT_DIM).pack(anchor="w", padx=10, pady=(6,2))
        for i, tv in enumerate(self._time_vars):
            row = ctk.CTkFrame(sched_box, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(row, text=f"Time {i+1}:", width=60, font=T.FONT_SMALL,
                          text_color=T.TEXT_DIM).pack(side="left")
            ctk.CTkEntry(row, textvariable=tv, placeholder_text="e.g. 08:00",
                          height=30, width=100).pack(side="left", padx=(4,0))

        jrow = ctk.CTkFrame(sched_box, fg_color="transparent")
        jrow.pack(fill="x", padx=10, pady=(2,8))
        ctk.CTkLabel(jrow, text="Jitter ±min:", width=80, font=T.FONT_SMALL,
                      text_color=T.TEXT_DIM).pack(side="left")
        ctk.CTkEntry(jrow, textvariable=self._jitter_var, width=60, height=30).pack(side="left", padx=4)

        # ── Auto-start ────────────────────────────────────────────
        _section("🚀  System Auto-Start")
        as_row = ctk.CTkFrame(self, fg_color="transparent")
        as_row.pack(fill="x", pady=3)
        ctk.CTkCheckBox(as_row, text="Launch FaucetPlay minimized at system login",
                         variable=self._autostart_var, font=T.FONT_BODY).pack(anchor="w")

        # ── Save button ───────────────────────────────────────────
        ctk.CTkFrame(self, height=1, fg_color=T.BG3).pack(fill="x", pady=12)
        self._status_lbl = ctk.CTkLabel(self, text="", font=T.FONT_SMALL,
                                         text_color=T.TEXT_DIM)
        self._status_lbl.pack(pady=(0, 4))
        ctk.CTkButton(self, text="💾  Save Settings", height=38,
                       fg_color=T.ACCENT, hover_color=T.ACCENT2,
                       font=T.FONT_BODY, command=self._save).pack(pady=4)

    # ── Save ──────────────────────────────────────────────────────

    def _save(self):
        try:
            target = float(self._target_var.get())
            if target <= 0:
                raise ValueError()
        except ValueError:
            self._status_lbl.configure(text="Invalid target amount.", text_color=T.RED)
            return

        try:
            edge = float(self._edge_var.get())
        except ValueError:
            edge = 0.03

        self._cfg.set("api_key",               self._api_key_var.get().strip())
        self._cfg.set("cookie",                self._cookie_var.get().strip())
        self._cfg.set("currency",              self._currency_var.get().strip() or "USDC")
        self._cfg.set("target_amount",         target)
        self._cfg.set("house_edge",            edge)
        self._cfg.set("auto_cashout",          self._auto_co_var.get())
        self._cfg.set("continue_after_cashout", self._continue_var.get())
        self._cfg.set("scheduler_enabled",     self._sched_on_var.get())
        self._cfg.set("jitter_minutes",        int(self._jitter_var.get() or "5"))

        times = [t.get().strip() for t in self._time_vars if t.get().strip()]
        self._cfg.set("schedules", times)

        self._cfg.save()

        # Update scheduler live
        if self._sched_on_var.get() and times:
            self._sched.set_claim_times(times,
                                         jitter_minutes=int(self._jitter_var.get() or "5"))

        # Auto-start registration
        import sys
        from core.scheduler import BotScheduler
        if self._autostart_var.get():
            self._sched.register_autostart(sys.executable)

        self._status_lbl.configure(text="✅  Settings saved.", text_color=T.GREEN)
        if self._on_save:
            self._on_save()
