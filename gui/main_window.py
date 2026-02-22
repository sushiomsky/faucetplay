"""
FaucetPlay GUI — Main Window
Single-account dashboard with live stats, log viewer, and settings.
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
from .wizard import OnboardingWizard
from core.bot import FaucetBot, BotError
from core.config import BotConfig
from core.scheduler import BotScheduler

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


# ── Widgets ────────────────────────────────────────────────────────────────

class BalanceCard(ctk.CTkFrame):
    def __init__(self, parent, title: str, value: str = "—",
                 colour: str = T.TEXT, **kw):
        super().__init__(parent, fg_color=T.BG2, corner_radius=10, **kw)
        ctk.CTkLabel(self, text=title, font=T.FONT_SMALL,
                     text_color=T.TEXT_DIM).pack(pady=(8, 0))
        self._val = ctk.CTkLabel(self, text=value, font=T.FONT_H1,
                                  text_color=colour)
        self._val.pack(pady=(2, 8))

    def set(self, value: str, colour: str = T.TEXT):
        self._val.configure(text=value, text_color=colour)


class LogViewer(ctk.CTkFrame):
    COLOURS = {
        "🎉": T.GREEN, "✅": T.GREEN,
        "❌": T.RED,   "🔴": T.RED,
        "⚠️": T.YELLOW, "🔑": T.YELLOW,
        "🔵": T.BLUE,  "🎮": T.TEAL,
        "💰": T.GREEN,  "🐾": T.ACCENT2,
        "⏳": T.ACCENT2,
    }

    def __init__(self, parent, **kw):
        super().__init__(parent, fg_color=T.BG2, corner_radius=8, **kw)
        hdr = ctk.CTkFrame(self, fg_color=T.BG3)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text="LOG", font=T.FONT_H3,
                     text_color=T.TEXT_DIM).pack(side="left", padx=10, pady=6)
        ctk.CTkButton(hdr, text="Clear", width=54, height=24,
                      fg_color=T.BG2, hover_color=T.BG, font=T.FONT_SMALL,
                      command=self.clear).pack(side="right", padx=6, pady=4)
        self._text = tk.Text(
            self, bg=T.BG2, fg=T.TEXT, font=T.FONT_MONO,
            bd=0, highlightthickness=0, state="disabled",
            wrap="word", padx=8, pady=4,
        )
        self._text.pack(fill="both", expand=True)
        for emoji, col in self.COLOURS.items():
            self._text.tag_config(emoji, foreground=col)

    def append(self, line: str):
        self._text.configure(state="normal")
        tag = next((e for e in self.COLOURS if e in line), None)
        self._text.insert("end", line + "\n", tag or "")
        self._text.see("end")
        self._text.configure(state="disabled")

    def clear(self):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")


# ── Main Window ────────────────────────────────────────────────────────────

class MainWindow(ctk.CTk):
    def __init__(self, config: BotConfig):
        super().__init__()
        self._cfg   = config
        self._sched = BotScheduler()
        self._bot: Optional[FaucetBot] = None
        self._log_queue: queue.Queue = queue.Queue()
        self._bot_thread: Optional[threading.Thread] = None

        self.title("FaucetPlay 🎰")
        self.geometry("920x680")
        self.minsize(780, 580)
        self.configure(fg_color=T.BG)

        self._build()
        self._poll_logs()
        self._check_first_run()

    # ── Layout ─────────────────────────────────────────────────────

    def _build(self):
        # Title bar
        title_bar = ctk.CTkFrame(self, fg_color=T.BG3, height=48)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        ctk.CTkLabel(title_bar, text="🎰  FaucetPlay", font=T.FONT_H1,
                     text_color=T.ACCENT).pack(side="left", padx=16, pady=10)
        self._conn_lbl = ctk.CTkLabel(title_bar, text="", font=T.FONT_SMALL,
                                       text_color=T.TEXT_DIM)
        self._conn_lbl.pack(side="right", padx=16)

        # Tab view
        self._tabs = ctk.CTkTabview(self, fg_color=T.BG, segmented_button_fg_color=T.BG3,
                                     segmented_button_selected_color=T.ACCENT,
                                     segmented_button_selected_hover_color=T.ACCENT2)
        self._tabs.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        for tab in ("Dashboard", "Settings"):
            self._tabs.add(tab)

        self._build_dashboard()
        self._build_settings()

    def _build_dashboard(self):
        tab = self._tabs.tab("Dashboard")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(3, weight=1)

        # ── Cards row ──────────────────────────────────────────
        cards = ctk.CTkFrame(tab, fg_color="transparent")
        cards.grid(row=0, column=0, sticky="ew", pady=(4, 8))
        self._card_faucet  = BalanceCard(cards, "Faucet Balance",  colour=T.TEAL)
        self._card_main    = BalanceCard(cards, "Main Balance",    colour=T.BLUE)
        self._card_profit  = BalanceCard(cards, "Session Profit",  colour=T.GREEN)
        self._card_cashout = BalanceCard(cards, "💰 Cashed Out",   colour=T.ACCENT)
        self._card_bets    = BalanceCard(cards, "Bets W / L",      colour=T.TEXT)
        for card in (self._card_faucet, self._card_main, self._card_profit,
                     self._card_cashout, self._card_bets):
            card.pack(side="left", expand=True, fill="both", padx=4)

        # ── Progress / status bar ──────────────────────────────
        prog_frame = ctk.CTkFrame(tab, fg_color=T.BG2, corner_radius=8)
        prog_frame.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        pf = ctk.CTkFrame(prog_frame, fg_color="transparent")
        pf.pack(fill="x", padx=12, pady=6)

        self._status_lbl = ctk.CTkLabel(pf, text="Ready — configure and press Start",
                                         font=T.FONT_BODY, text_color=T.TEXT_DIM)
        self._status_lbl.pack(side="left")
        self._cashout_cd_lbl = ctk.CTkLabel(pf, text="", font=T.FONT_BODY,
                                             text_color=T.ACCENT2)
        self._cashout_cd_lbl.pack(side="left", padx=(10, 0))
        self._paw_lbl = ctk.CTkLabel(pf, text="", font=T.FONT_BODY,
                                      text_color=T.ACCENT2)
        self._paw_lbl.pack(side="right")

        self._cashout_btn = ctk.CTkButton(
            pf, text="💰 Cashout Now", width=120, height=28,
            font=T.FONT_BODY, fg_color=T.ACCENT, hover_color=T.ACCENT2,
            command=self._manual_cashout,
        )
        self._cashout_btn.pack(side="right", padx=(0, 8))
        self._cashout_btn.configure(state="disabled")

        self._progress = ctk.CTkProgressBar(prog_frame, height=8,
                                             fg_color=T.BG3, progress_color=T.ACCENT)
        self._progress.pack(fill="x", padx=12, pady=(0, 8))
        self._progress.set(0)

        # ── Control bar ────────────────────────────────────────
        ctrl = ctk.CTkFrame(tab, fg_color=T.BG3, height=52)
        ctrl.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        ctrl.grid_propagate(False)

        self._start_btn = ctk.CTkButton(
            ctrl, text="▶  Start", width=100, height=36,
            fg_color=T.GREEN, hover_color="#1e8449", command=self._start_bot)
        self._pause_btn = ctk.CTkButton(
            ctrl, text="⏸  Pause", width=100, height=36,
            fg_color=T.YELLOW, hover_color="#b7950b", command=self._pause_bot)
        self._stop_btn  = ctk.CTkButton(
            ctrl, text="⏹  Stop", width=100, height=36,
            fg_color=T.RED, hover_color="#922b21", command=self._stop_bot)

        for btn in (self._start_btn, self._pause_btn, self._stop_btn):
            btn.pack(side="left", padx=8, pady=8)
        self._set_controls_state(running=False, paused=False)

        # Config shortcut
        ctk.CTkButton(ctrl, text="⚙  Settings", width=100, height=36,
                       fg_color=T.BG2, hover_color=T.BG,
                       command=lambda: self._tabs.set("Settings")
                       ).pack(side="right", padx=8, pady=8)

        # ── Log viewer ─────────────────────────────────────────
        self._log = LogViewer(tab)
        self._log.grid(row=3, column=0, sticky="nsew", pady=(0, 4))

    def _build_settings(self):
        tab = self._tabs.tab("Settings")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        self._settings_panel = SettingsPanel(
            tab, self._cfg, self._sched,
            on_save=self._on_settings_saved,
        )
        self._settings_panel.grid(row=0, column=0, sticky="nsew")

    # ── First run ──────────────────────────────────────────────────

    def _check_first_run(self):
        if not self._cfg.get("api_key"):
            self.after(300, self._open_wizard)
        else:
            self._refresh_conn_label()

    def _open_wizard(self):
        OnboardingWizard(self, self._cfg, on_complete=self._on_wizard_done)

    def _on_wizard_done(self):
        self._refresh_conn_label()
        self._log.append("✅  Setup complete! Press ▶ Start to begin farming.")
        self._log.append(f"🐾  Currency: {self._cfg.get('currency')}  "
                         f"|  Target: {self._cfg.get('target_amount')}")

    def _on_settings_saved(self):
        self._refresh_conn_label()
        if self._bot and self._bot.running:
            self._log.append("ℹ️  Settings saved — restart the bot to apply changes.")

    def _refresh_conn_label(self):
        currency = self._cfg.get("currency", "USDC")
        target   = self._cfg.get("target_amount", 0)
        has_key  = bool(self._cfg.get("api_key"))
        self._conn_lbl.configure(
            text=f"{'✅' if has_key else '⚠️'}  {currency}  |  target: {target}",
            text_color=T.GREEN if has_key else T.YELLOW,
        )

    # ── Bot control ────────────────────────────────────────────────

    def _start_bot(self):
        if self._bot and self._bot.running:
            if self._bot.paused:
                self._bot.resume()
                self._set_controls_state(running=True, paused=False)
                self._status_lbl.configure(text="Farming…", text_color=T.GREEN)
            return

        if not self._cfg.get("api_key"):
            self._log.append("⚠️  No API key — open Settings first.")
            self._tabs.set("Settings")
            return

        self._log_queue: queue.Queue = queue.Queue()
        q = self._log_queue

        def log_cb(msg: str):
            q.put(msg)

        self._bot = FaucetBot(config=self._cfg, log_callback=log_cb)
        self._set_controls_state(running=True, paused=False)
        self._status_lbl.configure(text="Starting…", text_color=T.TEXT_DIM)
        self._progress.set(0)
        for card in (self._card_faucet, self._card_main, self._card_profit,
                     self._card_cashout, self._card_bets):
            card.set("—")

        self._bot_thread = threading.Thread(
            target=self._run_bot_thread, daemon=True)
        self._bot_thread.start()

    def _run_bot_thread(self):
        assert self._bot is not None
        try:
            self._bot.start()
        except BotError as e:
            self._log_queue.put(f"🔴 Bot error: {e}")
        finally:
            self.after(0, self._on_bot_done)

    def _on_bot_done(self):
        self._set_controls_state(running=False, paused=False)
        self._status_lbl.configure(text="Stopped.", text_color=T.TEXT_DIM)
        self._cashout_btn.configure(state="disabled")
        self._cashout_cd_lbl.configure(text="")

    def _pause_bot(self):
        if not self._bot:
            return
        if self._bot.paused:
            self._bot.resume()
            self._set_controls_state(running=True, paused=False)
            self._status_lbl.configure(text="Farming…", text_color=T.GREEN)
        else:
            self._bot.pause()
            self._set_controls_state(running=True, paused=True)
            self._status_lbl.configure(text="Paused.", text_color=T.YELLOW)

    def _stop_bot(self):
        if self._bot:
            self._bot.stop()
        self._set_controls_state(running=False, paused=False)

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

    # ── Log polling ────────────────────────────────────────────────

    def _poll_logs(self):
        for _ in range(50):
            try:
                line = self._log_queue.get_nowait()
                self._log.append(line)
            except queue.Empty:
                break
        self._update_cards()
        self._update_cashout_countdown()
        self.after(150, self._poll_logs)

    def _update_cards(self):
        if not self._bot:
            return
        stats = self._bot.get_stats()
        n      = stats["total_bets"]
        w      = stats["total_wins"]
        l      = stats["total_losses"]
        cur_b  = stats["current_balance"]
        profit = cur_b - stats["starting_balance"]
        cashed = stats["total_cashed_out"]
        p_col  = T.GREEN if profit >= 0 else T.RED
        state  = self._bot.get_state()

        def _update():
            self._card_faucet.set(f"{cur_b:.6f}", T.TEAL)
            self._card_profit.set(f"{profit:+.6f}", p_col)
            cnt = stats["cashout_count"]
            self._card_cashout.set(
                f"{cashed:.6f}" + (f"  ×{cnt}" if cnt > 1 else ""),
                T.GREEN if cashed > 0 else T.TEXT_DIM,
            )
            self._card_bets.set(f"{w} / {l}", T.TEXT)

            threshold = self._bot.cashout_threshold
            if threshold > 0:
                self._progress.set(min(cur_b / threshold, 1.0))

            state_label = {
                "FARMING":      "Farming…",
                "CASHOUT_WAIT": "⏳ Awaiting cashout cooldown…",
                "POST_CASHOUT": "💰 Cashed out!",
                "STOPPED":      "Stopped",
            }.get(state, state)
            status_col = {
                "FARMING":      T.GREEN,
                "CASHOUT_WAIT": T.ACCENT2,
                "POST_CASHOUT": T.GREEN,
                "STOPPED":      T.TEXT_DIM,
            }.get(state, T.TEXT)
            self._status_lbl.configure(text=state_label, text_color=status_col)

            is_running = self._bot.running
            self._cashout_btn.configure(
                state="normal" if is_running else "disabled")

        self.after(0, _update)

    def _update_cashout_countdown(self):
        if not self._bot:
            return
        secs = self._bot.get_cashout_countdown()
        if secs > 0:
            h, r = divmod(secs, 3600)
            m, s = divmod(r, 60)
            text = (f"⏳ cashout in {h}h {m:02d}m {s:02d}s" if h
                    else f"⏳ cashout in {m}m {s:02d}s" if m
                    else f"⏳ cashout in {s}s")
            self.after(0, lambda: self._cashout_cd_lbl.configure(
                text=text, text_color=T.ACCENT2))
        else:
            self.after(0, lambda: self._cashout_cd_lbl.configure(text=""))
