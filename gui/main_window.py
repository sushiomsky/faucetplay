"""
FaucetPlay GUI — Main Window
Dark-theme dashboard: accounts sidebar, live balance cards,
log viewer, start/stop/pause controls, per-account stats.
"""
from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from datetime import datetime, timezone
from typing import Dict, Optional

import customtkinter as ctk

from . import theme as T
from .accounts_panel import AccountsPanel
from .scheduler_panel import SchedulerPanel
from .wizard import OnboardingWizard
from core.accounts import Account, AccountManager
from core.network import NetworkProfileManager, ProfileType
from core.bot import FaucetBot, BotError
from core.config import BotConfig
from core.scheduler import BotScheduler

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


# ─────────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────
class LogViewer(ctk.CTkFrame):
    COLOURS = {
        "🎉": T.GREEN, "✅": T.GREEN,
        "❌": T.RED,   "🔴": T.RED,
        "⚠️": T.YELLOW,"🔑": T.YELLOW,
        "🔵": T.BLUE,  "🎮": T.TEAL,
        "🛡": T.BLUE,  "🐾": T.ACCENT2,
    }

    def __init__(self, parent, **kw):
        super().__init__(parent, fg_color=T.BG2, corner_radius=8, **kw)
        hdr = ctk.CTkFrame(self, fg_color=T.BG3)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text="LOG", font=T.FONT_H3,
                     text_color=T.TEXT_DIM).pack(side="left", padx=10, pady=6)
        ctk.CTkButton(hdr, text="Clear", width=54, height=24,
                      fg_color=T.BG2, hover_color=T.BG,
                      font=T.FONT_SMALL,
                      command=self.clear).pack(side="right", padx=6, pady=4)

        self._text = tk.Text(
            self, bg=T.BG2, fg=T.TEXT, font=T.FONT_MONO,
            bd=0, highlightthickness=0, state="disabled",
            wrap="word", padx=8, pady=4,
        )
        self._text.pack(fill="both", expand=True)
        # colour tags
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


# ─────────────────────────────────────────────────────────────────
class BotControlBar(ctk.CTkFrame):
    def __init__(self, parent, on_start, on_pause, on_stop, on_start_all, on_stop_all, **kw):
        super().__init__(parent, fg_color=T.BG3, height=52, **kw)
        self.pack_propagate(False)

        self._start_btn = ctk.CTkButton(
            self, text="▶ Start", width=90, height=36, fg_color=T.GREEN,
            hover_color="#1e8449", command=on_start)
        self._pause_btn = ctk.CTkButton(
            self, text="⏸ Pause", width=90, height=36, fg_color=T.YELLOW,
            hover_color="#b7770d", text_color=T.BG, command=on_pause)
        self._stop_btn = ctk.CTkButton(
            self, text="⏹ Stop", width=90, height=36, fg_color=T.RED,
            hover_color="#922b21", command=on_stop)

        for btn in (self._start_btn, self._pause_btn, self._stop_btn):
            btn.pack(side="left", padx=6, pady=8)

        ctk.CTkFrame(self, fg_color=T.BG2, width=2).pack(side="left", padx=8, fill="y", pady=8)

        ctk.CTkButton(self, text="▶▶ All", width=80, height=36,
                      fg_color=T.BG2, hover_color=T.BG,
                      command=on_start_all).pack(side="left", padx=4)
        ctk.CTkButton(self, text="⏹⏹ All", width=80, height=36,
                      fg_color=T.BG2, hover_color=T.BG,
                      command=on_stop_all).pack(side="left", padx=4)

        # Keyboard shortcuts
        self._start_btn.bind("<Return>", lambda e: on_start())

    def set_running(self, running: bool, paused: bool = False):
        if running and not paused:
            self._start_btn.configure(state="disabled")
            self._pause_btn.configure(state="normal", text="⏸ Pause")
            self._stop_btn.configure(state="normal")
        elif paused:
            self._start_btn.configure(state="disabled")
            self._pause_btn.configure(state="normal", text="▶ Resume")
            self._stop_btn.configure(state="normal")
        else:
            self._start_btn.configure(state="normal")
            self._pause_btn.configure(state="disabled")
            self._stop_btn.configure(state="disabled")


# ─────────────────────────────────────────────────────────────────
class MainWindow(ctk.CTk):
    """
    Top-level application window.
    """

    def __init__(self, config: BotConfig, account_mgr: AccountManager,
                 network_mgr: NetworkProfileManager, scheduler: BotScheduler):
        super().__init__()
        self.title("FaucetPlay 🎰")
        self.geometry("1200x760")
        self.minsize(900, 600)
        self.configure(fg_color=T.BG)

        self._cfg      = config
        self._amgr     = account_mgr
        self._nmgr     = network_mgr
        self._sched    = scheduler
        self._selected_id: Optional[str] = None
        self._bots:   Dict[str, FaucetBot]   = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._log_queues: Dict[str, queue.Queue] = {}

        self._build()
        self._check_first_run()
        self._start_scheduler()
        self._poll_logs()

    # ── Build ────────────────────────────────────────────────────
    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left: accounts sidebar
        self._accounts_panel = AccountsPanel(
            self, self._amgr, self._nmgr,
            on_select=self._on_account_select,
        )
        self._accounts_panel.grid(row=0, column=0, sticky="ns", padx=(8,4), pady=8)

        # Right: tabbed content
        self._tabs = ctk.CTkTabview(self, fg_color=T.BG2,
                                     segmented_button_fg_color=T.BG3,
                                     segmented_button_selected_color=T.ACCENT,
                                     text_color=T.TEXT)
        self._tabs.grid(row=0, column=1, sticky="nsew", padx=(4,8), pady=8)

        for tab in ("Dashboard", "Scheduler", "Analytics"):
            self._tabs.add(tab)

        self._build_dashboard()
        self._build_scheduler_tab()

    def _build_dashboard(self):
        tab = self._tabs.tab("Dashboard")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        # Balance cards row
        cards = ctk.CTkFrame(tab, fg_color="transparent")
        cards.grid(row=0, column=0, sticky="ew", pady=(4, 8))
        self._card_faucet  = BalanceCard(cards, "Faucet Balance",  colour=T.TEAL)
        self._card_main    = BalanceCard(cards, "Main Balance",    colour=T.BLUE)
        self._card_profit  = BalanceCard(cards, "Session Profit",  colour=T.GREEN)
        self._card_cashout = BalanceCard(cards, "💰 Cashed Out",   colour=T.ACCENT)
        self._card_bets    = BalanceCard(cards, "Bets / W / L",    colour=T.TEXT)
        for card in (self._card_faucet, self._card_main, self._card_profit,
                     self._card_cashout, self._card_bets):
            card.pack(side="left", expand=True, fill="both", padx=4)

        # Progress bar + status
        prog_frame = ctk.CTkFrame(tab, fg_color=T.BG2, corner_radius=8)
        prog_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        pf_inner = ctk.CTkFrame(prog_frame, fg_color="transparent")
        pf_inner.pack(fill="x", padx=12, pady=8)
        self._status_lbl = ctk.CTkLabel(pf_inner, text="Select an account to begin",
                                         font=T.FONT_BODY, text_color=T.TEXT_DIM)
        self._status_lbl.pack(side="left")
        # Cashout countdown label (hidden until cooldown active)
        self._cashout_cd_lbl = ctk.CTkLabel(pf_inner, text="", font=T.FONT_BODY,
                                             text_color=T.ACCENT2)
        self._cashout_cd_lbl.pack(side="left", padx=(12, 0))
        self._paw_lbl = ctk.CTkLabel(pf_inner, text="", font=T.FONT_BODY,
                                      text_color=T.ACCENT2)
        self._paw_lbl.pack(side="right")
        # Manual cashout button (only active while bot is running)
        self._cashout_btn = ctk.CTkButton(
            pf_inner, text="💰 Cashout Now", width=120, height=28,
            font=T.FONT_BODY, fg_color=T.ACCENT, hover_color=T.ACCENT2,
            command=self._manual_cashout,
        )
        self._cashout_btn.pack(side="right", padx=(0, 8))
        self._cashout_btn.configure(state="disabled")
        self._progress = ctk.CTkProgressBar(prog_frame, height=10,
                                             fg_color=T.BG3, progress_color=T.ACCENT)
        self._progress.pack(fill="x", padx=12, pady=(0,8))
        self._progress.set(0)

        # Control bar
        self._ctrl = BotControlBar(
            tab,
            on_start=self._start_bot,
            on_pause=self._pause_bot,
            on_stop=self._stop_bot,
            on_start_all=self._start_all,
            on_stop_all=self._stop_all,
        )
        self._ctrl.grid(row=1, column=0, sticky="ew", pady=(8,0))
        self._ctrl.grid(row=1, column=0)  # put in correct row later

        # Re-layout: push control bar and progress into row 1
        self._ctrl.grid_forget()
        prog_frame.grid_forget()

        prog_frame.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        self._ctrl.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        tab.grid_rowconfigure(3, weight=1)

        # Log viewer
        self._log = LogViewer(tab)
        self._log.grid(row=3, column=0, sticky="nsew", pady=(0,4))

    def _build_scheduler_tab(self):
        tab = self._tabs.tab("Scheduler")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        self._sched_panel = SchedulerPanel(tab, self._amgr, self._sched)
        self._sched_panel.grid(row=0, column=0, sticky="nsew")

    # ── First run / wizard ───────────────────────────────────────
    def _check_first_run(self):
        if not self._amgr.all():
            self.after(300, self._open_wizard)

    def _open_wizard(self):
        OnboardingWizard(
            self, self._amgr, self._nmgr,
            on_complete=self._on_wizard_done,
        )

    def _on_wizard_done(self, account: Account):
        self._accounts_panel.refresh()
        self._on_account_select(account.id)
        self._log.append(f"✅ Account '{account.label}' created. Welcome to FaucetPlay!")

    # ── Account selection ────────────────────────────────────────
    def _on_account_select(self, account_id: str):
        self._selected_id = account_id
        acct = self._amgr.get(account_id)
        if not acct:
            return

        self._sched_panel.load_account(account_id)

        # Network badge
        profile = self._nmgr.get(acct.network_profile_id) if acct.network_profile_id else None
        net_str = ""
        if profile:
            net_str = f"🔒 Proxy" if profile.type == ProfileType.PROXY else "🛡 VPN"
        else:
            net_str = "⚠️ Direct"

        self._paw_lbl.configure(
            text=f"🐾 PAW {acct.paw_level}  |  {acct.preferred_currency}  |  {net_str}")
        self._status_lbl.configure(
            text=f"Account: {acct.label}", text_color=T.TEXT)

        # Restore button state
        is_running = account_id in self._bots and self._bots[account_id].running
        is_paused  = is_running and self._bots[account_id].paused
        self._ctrl.set_running(is_running, is_paused)

        self._log.clear()
        if account_id in self._log_queues:
            pass  # existing log queue; new messages will flow in

    # ── Bot control ──────────────────────────────────────────────
    def _start_bot(self):
        if not self._selected_id:
            return
        acct = self._amgr.get(self._selected_id)
        if not acct:
            return
        if self._selected_id in self._bots and self._bots[self._selected_id].running:
            # Resume if paused
            self._bots[self._selected_id].resume()
            self._ctrl.set_running(True, False)
            return

        q: queue.Queue = queue.Queue()
        self._log_queues[self._selected_id] = q

        def log_cb(msg: str):
            q.put(msg)
            self._update_cards_from_log(self._selected_id, msg)

        target = float(self._cfg.get('target_amount') or 20.0)
        bot = FaucetBot(
            account=acct,
            network_mgr=self._nmgr,
            target_amount=target,
            house_edge=float(self._cfg.get('house_edge') or 0.03),
            log_callback=log_cb,
        )
        self._bots[self._selected_id] = bot
        self._ctrl.set_running(True)
        self._accounts_panel.set_status(self._selected_id, "running")

        t = threading.Thread(target=self._run_bot,
                             args=(self._selected_id, bot), daemon=True)
        self._threads[self._selected_id] = t
        t.start()

    def _run_bot(self, account_id: str, bot: FaucetBot):
        try:
            bot.start()
        except BotError as e:
            q = self._log_queues.get(account_id)
            if q:
                q.put(f"🔴 Bot error: {e}")
        finally:
            self.after(0, lambda: self._on_bot_stopped(account_id))

    def _on_bot_stopped(self, account_id: str):
        self._accounts_panel.set_status(account_id, "idle")
        if account_id == self._selected_id:
            self._ctrl.set_running(False)
            self._status_lbl.configure(text="Bot stopped.", text_color=T.TEXT_DIM)

    def _pause_bot(self):
        if not self._selected_id:
            return
        bot = self._bots.get(self._selected_id)
        if not bot:
            return
        if bot.paused:
            bot.resume()
            self._ctrl.set_running(True, False)
            self._accounts_panel.set_status(self._selected_id, "running")
        else:
            bot.pause()
            self._ctrl.set_running(True, True)
            self._accounts_panel.set_status(self._selected_id, "paused")

    def _stop_bot(self):
        if not self._selected_id:
            return
        bot = self._bots.get(self._selected_id)
        if bot:
            bot.stop()
        self._ctrl.set_running(False)
        self._accounts_panel.set_status(self._selected_id, "idle")

    def _start_all(self):
        for acct in self._amgr.active_accounts():
            self._selected_id = acct.id
            self._start_bot()

    def _stop_all(self):
        for bot in self._bots.values():
            bot.stop()
        self._accounts_panel.refresh()
        self._ctrl.set_running(False)

    # ── Scheduler integration ────────────────────────────────────
    def _start_scheduler(self):
        for acct in self._amgr.all():
            self._sched.on_claim(acct.id, lambda aid: self._scheduled_claim(aid))
            self._sched.on_start(acct.id, lambda aid: self._scheduled_start(aid))
            self._sched.on_stop(acct.id,  lambda aid: self._scheduled_stop(aid))
        self._sched.start()

    def _scheduled_claim(self, account_id: str):
        self._log.append(f"⏰ Scheduled claim triggered for account {account_id[:8]}…")
        self.after(0, lambda: self._on_account_select(account_id))
        self.after(100, self._start_bot)

    def _scheduled_start(self, account_id: str):
        self._log.append(f"⏰ Scheduled session start for {account_id[:8]}")
        self.after(0, lambda: (self._on_account_select(account_id),
                               self._start_bot()))

    def _scheduled_stop(self, account_id: str):
        self._log.append(f"⏰ Scheduled session stop for {account_id[:8]}")
        bot = self._bots.get(account_id)
        if bot:
            bot.stop()

    # ── Log polling ──────────────────────────────────────────────
    def _poll_logs(self):
        """Drain log queues for the selected account and update the UI."""
        if self._selected_id and self._selected_id in self._log_queues:
            q = self._log_queues[self._selected_id]
            for _ in range(50):  # max 50 lines per tick
                try:
                    line = q.get_nowait()
                    self._log.append(line)
                except queue.Empty:
                    break
        self._poll_cashout_countdown()
        self.after(150, self._poll_logs)

    def _poll_cashout_countdown(self):
        """Update the cashout countdown label while cooldown is active."""
        bot = self._bots.get(self._selected_id) if self._selected_id else None
        if not bot:
            return
        secs = bot.get_cashout_countdown()
        state = bot.get_state()
        if secs > 0:
            h, r = divmod(secs, 3600)
            m, s = divmod(r, 60)
            cd_text = (f"⏳ Cashout in {h}h {m:02d}m {s:02d}s" if h
                       else f"⏳ Cashout in {m}m {s:02d}s" if m
                       else f"⏳ Cashout in {s}s")
            self._cashout_cd_lbl.configure(text=cd_text, text_color=T.ACCENT2)
        elif state == "CASHOUT_WAIT":
            self._cashout_cd_lbl.configure(text="⏳ Waiting for cashout…",
                                           text_color=T.ACCENT2)
        else:
            self._cashout_cd_lbl.configure(text="")

    # ── Card updates ─────────────────────────────────────────────
    def _update_cards_from_log(self, account_id: str, msg: str):
        """Parse log messages to update balance/stats cards."""
        if account_id != self._selected_id:
            return
        bot = self._bots.get(account_id)
        if not bot:
            return
        stats = bot.get_stats()
        n = stats["total_bets"]
        w = stats["total_wins"]
        l = stats["total_losses"]
        profit = stats["current_balance"] - stats["starting_balance"]
        p_col = T.GREEN if profit >= 0 else T.RED
        cashed = stats["total_cashed_out"]
        state  = bot.get_state()

        def _update():
            self._card_faucet.set(f"{stats['current_balance']:.6f}", T.TEAL)
            self._card_profit.set(f"{profit:+.6f}", p_col)
            self._card_cashout.set(
                f"{cashed:.6f}"
                + (f" ×{stats['cashout_count']}" if stats["cashout_count"] > 1 else ""),
                T.GREEN if cashed > 0 else T.TEXT,
            )
            self._card_bets.set(f"{n} / {w} / {l}", T.TEXT)
            if bot.cashout_threshold > 0:
                pct = min(stats["current_balance"] / bot.cashout_threshold, 1.0)
                self._progress.set(pct)
            acct = self._amgr.get(account_id)
            if acct:
                state_label = {
                    "FARMING":      "Farming…",
                    "CASHOUT_WAIT": "⏳ Awaiting cashout cooldown…",
                    "POST_CASHOUT": "💰 Cashed out!",
                    "STOPPED":      "Stopped",
                }.get(state, state)
                status_col = T.ACCENT2 if state == "CASHOUT_WAIT" else T.GREEN
                self._status_lbl.configure(
                    text=f"Account: {acct.label}  |  {state_label}",
                    text_color=status_col,
                )
            # Enable manual cashout button when bot is running
            is_running = bot.running and state in ("FARMING", "CASHOUT_WAIT")
            self._cashout_btn.configure(state="normal" if is_running else "disabled")
        self.after(0, _update)

    def _manual_cashout(self):
        """Trigger an immediate cashout for the selected account."""
        bot = self._bots.get(self._selected_id) if self._selected_id else None
        if bot:
            t = threading.Thread(target=bot.cashout_now, daemon=True)
            t.start()
