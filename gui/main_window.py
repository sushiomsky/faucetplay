"""
FaucetPlay GUI — Main Window
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import datetime, timezone
from typing import Optional

import customtkinter as ctk

from . import theme as T
from .settings_panel import SettingsPanel
from .toast import ToastManager
from .wizard import OnboardingWizard
from core.bot import FaucetBot, BotError
from core.config import BotConfig
from core.scheduler import BotScheduler
from core.version import APP_NAME, APP_VERSION, TAGLINE
from core.updater import UpdateChecker, UpdateInfo

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


# ═══════════════════════════════════════════════════════════════════
# Reusable widgets
# ═══════════════════════════════════════════════════════════════════

class BalanceCard(ctk.CTkFrame):
    def __init__(self, parent, title: str, value: str = "—",
                 colour: str = T.TEXT, subtitle: str = "", **kw):
        kw.setdefault("width", 130)
        super().__init__(parent, fg_color=T.BG_CARD, corner_radius=T.CORNER_MD, **kw)
        ctk.CTkLabel(self, text=title, font=T.FONT_SMALL,
                     text_color=T.TEXT_DIM).pack(pady=(10, 0))
        self._colour = colour
        self._val = ctk.CTkLabel(self, text=value, font=T.FONT_CARD_VAL,
                                  text_color=colour)
        self._val.pack(pady=(4, 2 if subtitle else 10))
        self._sub_lbl: Optional[ctk.CTkLabel] = None
        if subtitle:
            self._sub_lbl = ctk.CTkLabel(self, text=subtitle, font=T.FONT_SMALL,
                                          text_color=T.TEXT_DIM)
            self._sub_lbl.pack(pady=(0, 8))

    def set(self, value: str, colour: Optional[str] = None,
            subtitle: Optional[str] = None):
        if colour:
            self._colour = colour
        self._val.configure(text=value, text_color=self._colour)
        if subtitle is not None and self._sub_lbl:
            self._sub_lbl.configure(text=subtitle)

    def flash(self, colour: str = T.GOLD):
        """Briefly highlight the value then revert."""
        self._val.configure(text_color=colour)
        self.after(600, lambda: self._val.configure(text_color=self._colour))


# ───────────────────────────────────────────────────────────────────

class LogViewer(ctk.CTkFrame):
    MAX_LINES  = 1000
    TRIM_COUNT = 200

    COLOURS = {
        "🎉": T.GOLD,   "✅": T.GREEN,
        "❌": T.RED,    "🔴": T.RED,
        "⚠️": T.YELLOW, "🔑": T.YELLOW,
        "🔵": T.BLUE,   "🎮": T.TEAL,
        "💰": T.GOLD,   "🐾": T.ACCENT2,
        "⏳": T.ACCENT2, "🎲": T.TEXT_DIM,
        "🔄": T.BLUE,   "🛑": T.RED,
    }

    def __init__(self, parent, **kw):
        super().__init__(parent, fg_color=T.BG2, corner_radius=T.CORNER_MD, **kw)
        self._lines: list[tuple[str, Optional[str]]] = []
        self._filter = "All"

        # Header
        hdr = ctk.CTkFrame(self, fg_color=T.BG3, corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text="ACTIVITY LOG", font=T.FONT_H3,
                     text_color=T.TEXT_DIM).pack(side="left", padx=12, pady=6)
        self._count_lbl = ctk.CTkLabel(hdr, text="", font=T.FONT_SMALL,
                                        text_color=T.TEXT_DIM)
        self._count_lbl.pack(side="left", padx=4)
        for txt, cmd in [("📋 Copy", self._copy), ("🗑 Clear", self.clear)]:
            ctk.CTkButton(hdr, text=txt, width=72, height=24,
                          fg_color=T.BG2, hover_color=T.BG,
                          font=T.FONT_SMALL, command=cmd,
                          ).pack(side="right", padx=3, pady=4)

        # Filter bar
        fbar = ctk.CTkFrame(self, fg_color=T.BG3, height=34)
        fbar.pack(fill="x")
        fbar.pack_propagate(False)
        self._seg = ctk.CTkSegmentedButton(
            fbar, values=["All", "✅ Wins", "❌ Errors", "⏳ Wait"],
            command=self._set_filter, font=T.FONT_SMALL,
            selected_color=T.ACCENT, selected_hover_color=T.ACCENT2,
            unselected_color=T.BG2, unselected_hover_color=T.BG3,
        )
        self._seg.pack(side="left", padx=8, pady=4)
        self._seg.set("All")

        # Text area with scrollbar
        tf = ctk.CTkFrame(self, fg_color=T.BG2)
        tf.pack(fill="both", expand=True)
        self._text = tk.Text(
            tf, bg=T.BG2, fg=T.TEXT, font=T.FONT_MONO,
            bd=0, highlightthickness=0, state="disabled",
            wrap="word", padx=10, pady=6, spacing1=2,
        )
        sb = ctk.CTkScrollbar(tf, command=self._text.yview)
        self._text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._text.pack(side="left", fill="both", expand=True)

        for emoji, col in self.COLOURS.items():
            self._text.tag_config(emoji, foreground=col)

    def _set_filter(self, value: str):
        self._filter = value
        self._rerender()

    def _passes(self, line: str) -> bool:
        f = self._filter
        if f == "All":          return True
        if f == "✅ Wins":      return any(e in line for e in ("✅","🎉","💰"))
        if f == "❌ Errors":    return any(e in line for e in ("❌","🔴"))
        if f == "⏳ Wait":      return any(e in line for e in ("⏳","⚠️"))
        return True

    def _rerender(self):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        for line, tag in self._lines:
            if self._passes(line):
                self._text.insert("end", line + "\n", tag or "")
        self._text.see("end")
        self._text.configure(state="disabled")

    def append(self, line: str):
        tag = next((e for e in self.COLOURS if e in line), None)
        self._lines.append((line, tag))
        if len(self._lines) > self.MAX_LINES:
            self._lines = self._lines[self.TRIM_COUNT:]
            self._rerender()
        else:
            if self._passes(line):
                self._text.configure(state="normal")
                self._text.insert("end", line + "\n", tag or "")
                self._text.see("end")
                self._text.configure(state="disabled")
        n = len(self._lines)
        self._count_lbl.configure(text=f"{n} line{'s' if n != 1 else ''}")

    def clear(self):
        self._lines.clear()
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")
        self._count_lbl.configure(text="")

    def _copy(self):
        txt = "\n".join(l for l, _ in self._lines)
        self.clipboard_clear()
        self.clipboard_append(txt)


# ═══════════════════════════════════════════════════════════════════
# Update banner
# ═══════════════════════════════════════════════════════════════════

class UpdateBanner(ctk.CTkFrame):
    """Dismissible banner shown when a new release is available."""

    def __init__(self, parent, info: UpdateInfo, **kw):
        super().__init__(parent, fg_color=T.BG3, corner_radius=0,
                         border_width=0, **kw)
        self._info = info

        accent_bar = ctk.CTkFrame(self, fg_color=T.GOLD, width=4)
        accent_bar.pack(side="left", fill="y")
        accent_bar.pack_propagate(False)

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(side="left", fill="both", expand=True, padx=10, pady=6)

        ctk.CTkLabel(
            inner,
            text=f"🆕  {APP_NAME} v{info.version} is available",
            font=T.FONT_H3, text_color=T.GOLD,
        ).pack(side="left")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(side="right", padx=8, pady=6)

        ctk.CTkButton(
            btn_frame, text="View Release", width=100, height=28,
            fg_color=T.GOLD, hover_color=T.ACCENT2, text_color=T.BG,
            font=T.FONT_SMALL,
            command=lambda: UpdateChecker.open_download_page(info.release_url),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_frame, text="✕", width=28, height=28,
            fg_color="transparent", hover_color=T.BG,
            text_color=T.TEXT_DIM, font=T.FONT_H3,
            command=self.destroy,
        ).pack(side="left")


# ═══════════════════════════════════════════════════════════════════
# Hero / empty state panel
# ═══════════════════════════════════════════════════════════════════

class HeroPanel(ctk.CTkFrame):
    """
    Shown in the dashboard when the bot is not running.
    Gives a compelling 'ready to earn' feel with a big start button.
    """

    def __init__(self, parent, config: BotConfig, on_start, on_setup, **kw):
        super().__init__(parent, fg_color="transparent", **kw)
        self._cfg      = config
        self._on_start = on_start
        self._on_setup = on_setup
        self._build()

    def _build(self):
        # Centred card
        card = ctk.CTkFrame(self, fg_color=T.BG_CARD, corner_radius=T.CORNER_LG)
        card.place(relx=0.5, rely=0.5, anchor="center")

        # Icon + headline
        ctk.CTkLabel(card, text="🎰", font=(T.FONT_H1[0], 52)).pack(pady=(28, 4))
        ctk.CTkLabel(card, text=TAGLINE, font=T.FONT_H2,
                     text_color=T.ACCENT).pack(pady=(0, 2))

        # Config summary pill
        currency = self._cfg.get("currency", "USDC")
        target   = self._cfg.get("target_amount", 0)
        auto_co  = self._cfg.get("auto_cashout", False)
        has_key  = bool(self._cfg.get("api_key"))

        summary_col = T.GREEN if has_key else T.YELLOW
        summary_txt = (
            f"{'✅ Ready' if has_key else '⚠️ Not configured'}  ·  "
            f"{currency}  ·  Target: {target}"
            + ("  ·  Auto-cashout ON" if auto_co else "")
        )
        ctk.CTkLabel(card, text=summary_txt, font=T.FONT_SMALL,
                     text_color=summary_col).pack(pady=(4, 20))

        # Big start button
        btn_text = "▶  START FARMING" if has_key else "⚙  Configure First"
        btn_cmd  = self._on_start if has_key else self._on_setup
        btn_col  = T.GREEN if has_key else T.ACCENT
        ctk.CTkButton(
            card, text=btn_text, width=260, height=52,
            font=(T.FONT_H2[0], 15, "bold"),
            fg_color=btn_col,
            hover_color="#1e8449" if has_key else T.ACCENT2,
            corner_radius=T.CORNER_MD,
            command=btn_cmd,
        ).pack(padx=32, pady=(0, 12))

        # Tips row
        tips = ctk.CTkFrame(card, fg_color="transparent")
        tips.pack(pady=(4, 24))
        for tip in ("F5 to start", "Space to pause", "Esc to stop"):
            ctk.CTkLabel(tips, text=f"  {tip}  ", font=T.FONT_SMALL,
                         text_color=T.TEXT_DIM,
                         fg_color=T.BG2, corner_radius=T.CORNER_SM,
                         ).pack(side="left", padx=4)

    def refresh(self, config: BotConfig):
        """Rebuild after settings change."""
        self._cfg = config
        for w in self.winfo_children():
            w.destroy()
        self._build()


# ═══════════════════════════════════════════════════════════════════
# Main Window
# ═══════════════════════════════════════════════════════════════════

class MainWindow(ctk.CTk):

    PULSE_INTERVAL = 900   # ms for status-dot pulse

    def __init__(self, config: BotConfig):
        super().__init__()
        self._cfg   = config
        self._sched = BotScheduler()
        self._bot: Optional[FaucetBot] = None
        self._log_queue: queue.Queue   = queue.Queue()
        self._bot_thread: Optional[threading.Thread] = None
        self._start_time: Optional[datetime] = None
        self._pulse_state = True

        self.title(f"{APP_NAME} {APP_VERSION} — {TAGLINE}")
        self.geometry("960x700")
        self.minsize(800, 580)
        self.configure(fg_color=T.BG)

        self._build()
        self.toasts = ToastManager(self)
        self._poll_logs()
        self._pulse_dot()
        self._check_first_run()
        self.after(3000, self._check_updates)

    # ── Layout ─────────────────────────────────────────────────────

    def _build(self):
        # ── Header ─────────────────────────────────────────────
        self._header = ctk.CTkFrame(self, fg_color=T.BG3, height=52)
        self._header.pack(fill="x")
        self._header.pack_propagate(False)

        logo_f = ctk.CTkFrame(self._header, fg_color="transparent")
        logo_f.pack(side="left", padx=14, pady=6)
        ctk.CTkLabel(logo_f, text="🎰", font=(T.FONT_H1[0], 22)).pack(side="left")
        name_f = ctk.CTkFrame(logo_f, fg_color="transparent")
        name_f.pack(side="left", padx=6)
        ctk.CTkLabel(name_f, text=APP_NAME, font=T.FONT_H2,
                     text_color=T.ACCENT).pack(anchor="w")
        ctk.CTkLabel(name_f, text=TAGLINE, font=T.FONT_SMALL,
                     text_color=T.TEXT_DIM).pack(anchor="w")

        self._header_right = ctk.CTkFrame(self._header, fg_color="transparent")
        self._header_right.pack(side="right", padx=14)
        self._conn_lbl = ctk.CTkLabel(self._header_right, text="",
                                       font=T.FONT_SMALL, text_color=T.TEXT_DIM)
        self._conn_lbl.pack(side="right")

        # Update banner slot (hidden until update found)
        self._banner_slot = ctk.CTkFrame(self, fg_color="transparent", height=0)
        self._banner_slot.pack(fill="x")
        self._banner_slot.pack_propagate(False)

        # ── Tabs ───────────────────────────────────────────────
        self._tabs = ctk.CTkTabview(
            self, fg_color=T.BG,
            segmented_button_fg_color=T.BG3,
            segmented_button_selected_color=T.ACCENT,
            segmented_button_selected_hover_color=T.ACCENT2,
        )
        self._tabs.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        for tab in ("Dashboard", "Settings"):
            self._tabs.add(tab)

        self._build_dashboard()
        self._build_settings()
        self._bind_shortcuts()

    def _build_dashboard(self):
        tab = self._tabs.tab("Dashboard")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(4, weight=1)

        # ── Balance cards ───────────────────────────────────────
        cards_frame = ctk.CTkFrame(tab, fg_color="transparent")
        cards_frame.grid(row=0, column=0, sticky="ew", pady=(4, 4))

        self._card_faucet  = BalanceCard(cards_frame, "Faucet Balance", colour=T.TEAL)
        self._card_main    = BalanceCard(cards_frame, "Main Balance",   colour=T.BLUE)
        self._card_profit  = BalanceCard(cards_frame, "Session Profit", colour=T.GREEN)
        self._card_cashout = BalanceCard(cards_frame, "Cashed Out 💰",  colour=T.GOLD)
        self._card_bets    = BalanceCard(cards_frame, "Bets  W / L",    colour=T.TEXT)
        for card in (self._card_faucet, self._card_main, self._card_profit,
                     self._card_cashout, self._card_bets):
            card.pack(side="left", expand=True, fill="both", padx=3)

        # ── Quick-stats bar ─────────────────────────────────────
        sbar = ctk.CTkFrame(tab, fg_color=T.BG2, corner_radius=T.CORNER_SM, height=28)
        sbar.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        sbar.pack_propagate(False)

        def _stat(text, **kw):
            lbl = ctk.CTkLabel(sbar, text=text, font=T.FONT_SMALL,
                                text_color=T.TEXT_DIM, **kw)
            lbl.pack(side="left", padx=(10, 0))
            return lbl

        def _sep():
            ctk.CTkLabel(sbar, text=" │ ", font=T.FONT_SMALL,
                         text_color=T.TEXT_DIM).pack(side="left")

        self._stat_dur    = _stat("⏱  —")
        _sep(); self._stat_bets   = _stat("🎰  0 bets")
        _sep(); self._stat_claims = _stat("📥  0 claims")
        _sep(); self._stat_rounds = _stat("🔄  0 rounds")
        _sep(); self._stat_wr     = _stat("📈  —% win rate")

        # ── Progress bar row ────────────────────────────────────
        pf = ctk.CTkFrame(tab, fg_color=T.BG2, corner_radius=T.CORNER_SM)
        pf.grid(row=2, column=0, sticky="ew", pady=(0, 4))

        status_row = ctk.CTkFrame(pf, fg_color="transparent")
        status_row.pack(fill="x", padx=12, pady=(6, 2))

        self._status_dot = ctk.CTkLabel(status_row, text="●", font=T.FONT_BODY,
                                         text_color=T.TEXT_DIM)
        self._status_dot.pack(side="left", padx=(0, 6))
        self._status_lbl = ctk.CTkLabel(status_row,
                                         text="Ready  —  press ▶ Start or F5",
                                         font=T.FONT_BODY, text_color=T.TEXT_DIM)
        self._status_lbl.pack(side="left")

        self._cashout_cd_lbl = ctk.CTkLabel(status_row, text="",
                                             font=T.FONT_SMALL, text_color=T.ACCENT2)
        self._cashout_cd_lbl.pack(side="left", padx=(12, 0))

        self._cashout_btn = ctk.CTkButton(
            status_row, text="💰 Cashout Now", width=120, height=26,
            font=T.FONT_SMALL, fg_color=T.GOLD, hover_color=T.ACCENT2,
            text_color=T.BG, command=self._manual_cashout,
        )
        self._cashout_btn.pack(side="right", padx=(0, 4))
        self._cashout_btn.configure(state="disabled")

        bar_row = ctk.CTkFrame(pf, fg_color="transparent")
        bar_row.pack(fill="x", padx=12, pady=(0, 8))
        self._prog_lbl = ctk.CTkLabel(bar_row, text="", font=T.FONT_SMALL,
                                       text_color=T.TEXT_DIM, width=180, anchor="e")
        self._prog_lbl.pack(side="right")
        self._progress = ctk.CTkProgressBar(bar_row, height=10,
                                             fg_color=T.BG3,
                                             progress_color=T.ACCENT)
        self._progress.pack(side="left", fill="x", expand=True)
        self._progress.set(0)

        # ── Control bar ─────────────────────────────────────────
        ctrl = ctk.CTkFrame(tab, fg_color=T.BG3, height=52)
        ctrl.grid(row=3, column=0, sticky="ew", pady=(0, 4))
        ctrl.grid_propagate(False)

        self._start_btn = ctk.CTkButton(
            ctrl, text="▶  Start", width=110, height=36,
            fg_color=T.GREEN, hover_color="#1e8449",
            font=T.FONT_BODY, command=self._start_bot)
        self._pause_btn = ctk.CTkButton(
            ctrl, text="⏸  Pause", width=110, height=36,
            fg_color=T.YELLOW, hover_color="#b7950b",
            font=T.FONT_BODY, command=self._pause_bot)
        self._stop_btn = ctk.CTkButton(
            ctrl, text="⏹  Stop", width=110, height=36,
            fg_color=T.RED, hover_color="#922b21",
            font=T.FONT_BODY, command=self._stop_bot)

        for b in (self._start_btn, self._pause_btn, self._stop_btn):
            b.pack(side="left", padx=6, pady=8)

        ctk.CTkButton(
            ctrl, text="⚙  Settings", width=110, height=36,
            fg_color=T.BG2, hover_color=T.BG, font=T.FONT_BODY,
            command=lambda: self._tabs.set("Settings"),
        ).pack(side="right", padx=6, pady=8)

        self._set_controls_state(False, False)

        # ── Dashboard content (hero | log) ──────────────────────
        tab.grid_rowconfigure(4, weight=1)
        self._content_frame = ctk.CTkFrame(tab, fg_color="transparent")
        self._content_frame.grid(row=4, column=0, sticky="nsew")
        self._content_frame.grid_columnconfigure(0, weight=1)
        self._content_frame.grid_rowconfigure(0, weight=1)

        # Hero panel (idle)
        self._hero = HeroPanel(
            self._content_frame, self._cfg,
            on_start=self._start_bot,
            on_setup=lambda: self._tabs.set("Settings"),
        )
        self._hero.grid(row=0, column=0, sticky="nsew")

        # Log viewer (running) — hidden initially
        self._log = LogViewer(self._content_frame)
        self._log.grid(row=0, column=0, sticky="nsew")
        self._log.grid_remove()

    def _build_settings(self):
        tab = self._tabs.tab("Settings")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        self._settings_panel = SettingsPanel(
            tab, self._cfg, self._sched,
            on_save=self._on_settings_saved,
        )
        self._settings_panel.grid(row=0, column=0, sticky="nsew")

    # ── Keyboard shortcuts ─────────────────────────────────────────

    def _bind_shortcuts(self):
        self.bind("<F5>",            lambda e: self._start_bot())
        self.bind("<Control-Return>",lambda e: self._start_bot())
        self.bind("<Control-p>",     lambda e: self._kb_pause(e))
        self.bind("<space>",         lambda e: self._kb_pause(e))
        self.bind("<Escape>",        lambda e: self._kb_stop(e))
        self.bind("<Control-comma>", lambda e: self._tabs.set("Settings"))

    def _kb_pause(self, _):
        fw = self.focus_get()
        if fw and fw.winfo_class().lower() in ("entry", "text"):
            return
        if self._bot and self._bot.running:
            self._pause_bot()

    def _kb_stop(self, _):
        if self._bot and self._bot.running:
            self._stop_bot()

    # ── Auto-update ────────────────────────────────────────────────

    def _check_updates(self):
        UpdateChecker().check_async(self._on_update_result)

    def _on_update_result(self, info: Optional[UpdateInfo]):
        if info is None:
            return
        # Show banner on the main thread
        self.after(0, lambda: self._show_update_banner(info))
        self.after(0, lambda: self.toasts.show(
            f"v{info.version} available — see header", "update", 8000
        ))

    def _show_update_banner(self, info: UpdateInfo):
        banner = UpdateBanner(self._banner_slot, info)
        banner.pack(fill="x")
        self._banner_slot.configure(height=44)

    # ── First run / setup ──────────────────────────────────────────

    def _check_first_run(self):
        if not self._cfg.get("api_key"):
            self.after(300, self._open_wizard)
        else:
            self._refresh_header()

    def _open_wizard(self):
        OnboardingWizard(self, self._cfg, on_complete=self._on_wizard_done)

    def _on_wizard_done(self):
        self._refresh_header()
        self._hero.refresh(self._cfg)
        self.toasts.show("Setup complete! Press Start to begin farming 🎰", "success")

    def _on_settings_saved(self):
        self._refresh_header()
        self._hero.refresh(self._cfg)
        if self._bot and self._bot.running:
            self.toasts.show("Settings saved — restart bot to apply changes", "info")
        else:
            self.toasts.show("Settings saved ✅", "success", 2500)

    def _refresh_header(self):
        currency = self._cfg.get("currency", "USDC")
        target   = self._cfg.get("target_amount", 0)
        has_key  = bool(self._cfg.get("api_key"))
        self._conn_lbl.configure(
            text=f"{'✅' if has_key else '⚠️ Not configured'}  {currency}  ·  target {target}",
            text_color=T.GREEN if has_key else T.YELLOW,
        )

    # ── Hero / log switcher ────────────────────────────────────────

    def _show_hero(self):
        self._log.grid_remove()
        self._hero.grid()

    def _show_log(self):
        self._hero.grid_remove()
        self._log.grid()

    # ── Bot control ────────────────────────────────────────────────

    def _start_bot(self):
        if self._bot and self._bot.running:
            if self._bot.paused:
                self._bot.resume()
                self._set_controls_state(True, False)
                self._status("Farming…", T.GREEN)
            return

        if not self._cfg.get("api_key"):
            self.toasts.show("No API key — open Settings first ⚙", "warning")
            self._tabs.set("Settings")
            return

        self._log_queue = queue.Queue()
        q = self._log_queue

        def log_cb(msg: str):
            q.put(msg)

        self._bot = FaucetBot(config=self._cfg, log_callback=log_cb)
        self._start_time = datetime.now(timezone.utc)
        self._set_controls_state(True, False)
        self._status("Starting…", T.TEXT_DIM)
        self._progress.set(0)
        self._prog_lbl.configure(text="")
        for card in (self._card_faucet, self._card_main, self._card_profit,
                     self._card_cashout, self._card_bets):
            card.set("—")
        self._log.clear()
        self._show_log()

        self._bot_thread = threading.Thread(
            target=self._run_bot_thread, daemon=True)
        self._bot_thread.start()

    def _run_bot_thread(self):
        assert self._bot is not None
        try:
            self._bot.start()
        except BotError as e:
            self._log_queue.put(f"🔴 Bot error: {e}")
            self.after(0, lambda: self.toasts.show(str(e), "error"))
        finally:
            self.after(0, self._on_bot_done)

    def _on_bot_done(self):
        self._update_stats_display()
        self._set_controls_state(False, False)
        self._status("Session complete.", T.TEXT_DIM)
        self._status_dot.configure(text_color=T.TEXT_DIM)
        self._cashout_btn.configure(state="disabled")
        self._cashout_cd_lbl.configure(text="")
        self.toasts.show("Session finished 🏁", "info")

    def _pause_bot(self):
        if not self._bot:
            return
        if self._bot.paused:
            self._bot.resume()
            self._set_controls_state(True, False)
            self._status("Farming…", T.GREEN)
        else:
            self._bot.pause()
            self._set_controls_state(True, True)
            self._status("Paused.", T.YELLOW)

    def _stop_bot(self):
        if self._bot:
            self._bot.stop()
        self._set_controls_state(False, False)
        self.after(800, self._show_hero)

    def _manual_cashout(self):
        if self._bot:
            threading.Thread(target=self._bot.cashout_now, daemon=True).start()

    def _set_controls_state(self, running: bool, paused: bool = False):
        self._start_btn.configure(
            text="▶  Resume" if (running and paused) else "▶  Start",
            state="disabled" if (running and not paused) else "normal",
        )
        self._pause_btn.configure(
            text="▶  Resume" if paused else "⏸  Pause",
            state="normal" if running else "disabled",
        )
        self._stop_btn.configure(state="normal" if running else "disabled")

    def _status(self, text: str, colour: str):
        self._status_lbl.configure(text=text, text_color=colour)

    # ── Animations ─────────────────────────────────────────────────

    def _pulse_dot(self):
        """Alternate between ● and ◉ while FARMING."""
        if self._bot and self._bot.running and not self._bot.paused:
            state = self._bot.get_state()
            if state == "FARMING":
                self._pulse_state = not self._pulse_state
                col = T.GREEN if self._pulse_state else "#1a7a40"
                self._status_dot.configure(text_color=col)
        self.after(self.PULSE_INTERVAL, self._pulse_dot)

    # ── Log polling & card updates ─────────────────────────────────

    def _poll_logs(self):
        prev_wins = (self._bot.stats["total_wins"]
                     if self._bot else 0)
        prev_cash = (self._bot.stats["total_cashed_out"]
                     if self._bot else 0.0)

        for _ in range(60):
            try:
                line = self._log_queue.get_nowait()
                self._log.append(line)
            except queue.Empty:
                break

        if self._bot:
            new_wins = self._bot.stats["total_wins"]
            new_cash = self._bot.stats["total_cashed_out"]

            # Toast on win
            if new_wins > prev_wins:
                cur = self._bot.stats["current_balance"]
                self.toasts.show(
                    f"Won!  Faucet: {cur:.6f} {self._cfg.get('currency','')}", "success"
                )
                self._card_faucet.flash(T.GOLD)

            # Toast on cashout
            if new_cash > prev_cash:
                diff = new_cash - prev_cash
                self.toasts.show(
                    f"Cashed out {diff:.6f} → main wallet 💰", "success", 6000
                )
                self._card_cashout.flash(T.GOLD)

            self._update_stats_display()
            self._update_cashout_countdown()

        self.after(150, self._poll_logs)

    def _update_stats_display(self):
        if not self._bot:
            return
        stats  = self._bot.get_stats()
        n      = stats["total_bets"]
        w      = stats["total_wins"]
        l      = stats["total_losses"]
        cur_b  = stats["current_balance"]
        profit = cur_b - stats["starting_balance"]
        cashed = stats["total_cashed_out"]
        cashct = stats["cashout_count"]
        claims = int(stats.get("total_claimed", 0))
        rounds = int(stats.get("rounds_completed", 0))
        state  = self._bot.get_state()
        paused = getattr(self._bot, "paused", False)

        p_col = T.GREEN if profit >= 0 else T.RED
        wr    = f"{w/n*100:.0f}%" if n else "—%"

        # Duration
        if self._start_time:
            elapsed = datetime.now(timezone.utc) - self._start_time
            s = int(elapsed.total_seconds())
            dur = f"⏱  {s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
        else:
            dur = "⏱  —"

        # State label & dot colour
        state_map = {
            "FARMING":      ("Paused." if paused else "Farming…",
                             T.YELLOW if paused else T.GREEN),
            "CASHOUT_WAIT": ("⏳ Awaiting cashout cooldown…", T.ACCENT2),
            "POST_CASHOUT": ("💰 Cashed out! Starting new round…", T.GOLD),
            "STOPPED":      ("Stopped.", T.TEXT_DIM),
        }
        state_txt, state_col = state_map.get(state, (state, T.TEXT))
        dot_col = state_col

        threshold = self._bot.cashout_threshold
        pct = min(cur_b / threshold, 1.0) if threshold > 0 else 0.0

        def _upd():
            self._card_faucet.set(f"{cur_b:.6f}", T.TEAL)
            self._card_profit.set(f"{profit:+.6f}", p_col)
            self._card_cashout.set(
                f"{cashed:.6f}" + (f"  ×{cashct}" if cashct > 1 else ""),
                T.GOLD if cashed > 0 else T.TEXT_DIM,
            )
            self._card_bets.set(f"{w} / {l}", T.TEXT)
            self._stat_dur.configure(text=dur)
            self._stat_bets.configure(text=f"🎰  {n} bets")
            self._stat_claims.configure(text=f"📥  {claims} claims")
            self._stat_rounds.configure(text=f"🔄  {rounds} rounds")
            self._stat_wr.configure(text=f"📈  {wr} win rate")
            self._progress.set(pct)
            if threshold > 0:
                self._prog_lbl.configure(
                    text=f"{cur_b:.4f} / {threshold:.4f}  ({pct*100:.0f}%)"
                )
            self._status(state_txt, state_col)
            if not (self._bot and self._bot.running and
                    self._bot.get_state() == "FARMING" and not paused):
                self._status_dot.configure(text_color=dot_col)
            self._cashout_btn.configure(
                state="normal" if (self._bot and self._bot.running) else "disabled"
            )

        self.after(0, _upd)

    def _update_cashout_countdown(self):
        if not self._bot:
            return
        secs = self._bot.get_cashout_countdown()
        if secs > 0:
            h, r = divmod(secs, 3600)
            m, s = divmod(r, 60)
            txt = (f"⏳ cashout in {h}h {m:02d}m {s:02d}s" if h
                   else f"⏳ cashout in {m}m {s:02d}s" if m
                   else f"⏳ cashout in {s}s")
            self.after(0, lambda: self._cashout_cd_lbl.configure(
                text=txt, text_color=T.ACCENT2))
        else:
            self.after(0, lambda: self._cashout_cd_lbl.configure(text=""))
