"""
FaucetPlay GUI — Scheduler Panel
Per-account daily claim times + session windows + system auto-start toggle.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import messagebox
from typing import Optional
import customtkinter as ctk
from . import theme as T
from core.accounts import Account, AccountManager
from core.scheduler import BotScheduler, AccountSchedule, ClaimTime, SessionWindow

DAYS_SHORT = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
DAYS_FULL  = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]


class SchedulerPanel(ctk.CTkFrame):
    """
    Shows and edits the full schedule for the currently selected account.
    """

    def __init__(self, parent, account_mgr: AccountManager,
                 scheduler: BotScheduler, **kw):
        super().__init__(parent, fg_color=T.BG, **kw)
        self._amgr = account_mgr
        self._sched = scheduler
        self._account: Optional[Account] = None
        self._acct_sched: Optional[AccountSchedule] = None
        self._day_vars: list[tk.BooleanVar] = []
        self._build()

    # ---------------------------------------------------------------
    def load_account(self, account_id: str):
        acct = self._amgr.get(account_id)
        if not acct:
            return
        self._account = acct
        # Load or create blank schedule
        self._acct_sched = AccountSchedule(account_id=acct.id)
        self._refresh_ui()

    # ---------------------------------------------------------------
    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # Title bar
        hdr = ctk.CTkFrame(self, fg_color=T.BG3)
        hdr.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 8))
        ctk.CTkLabel(hdr, text="⏰  SCHEDULER", font=T.FONT_H2,
                     text_color=T.TEXT).pack(side="left", padx=14, pady=10)
        self._next_lbl = ctk.CTkLabel(hdr, text="", font=T.FONT_SMALL,
                                      text_color=T.TEXT_DIM)
        self._next_lbl.pack(side="right", padx=14)

        # No-account placeholder
        self._placeholder = ctk.CTkLabel(
            self, text="← Select an account to configure its schedule",
            font=T.FONT_BODY, text_color=T.TEXT_DIM)
        self._placeholder.grid(row=1, column=0, pady=40)

        # Content (hidden until account selected)
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.grid(row=2, column=0, sticky="nsew", padx=16, pady=4)
        self._content.grid_remove()
        self.grid_rowconfigure(2, weight=1)

        self._build_content()
        self._build_autostart()

    def _build_content(self):
        c = self._content
        c.grid_columnconfigure((0,1), weight=1)

        # ── Left: Daily claim times ────────────────────────────────
        left = ctk.CTkFrame(c, fg_color=T.BG2, corner_radius=8)
        left.grid(row=0, column=0, sticky="nsew", padx=(0,6), pady=4)
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="Daily Claim Times",
                     font=T.FONT_H3, text_color=T.ACCENT).pack(anchor="w", padx=12, pady=8)

        ctk.CTkLabel(left, text="Time (HH:MM)", font=T.FONT_SMALL,
                     text_color=T.TEXT_DIM).pack(anchor="w", padx=12)
        self._claim_time_entry = ctk.CTkEntry(left, placeholder_text="08:00")
        self._claim_time_entry.pack(fill="x", padx=12, pady=2)

        ctk.CTkLabel(left, text="Jitter ± minutes", font=T.FONT_SMALL,
                     text_color=T.TEXT_DIM).pack(anchor="w", padx=12)
        self._jitter_entry = ctk.CTkEntry(left, placeholder_text="0")
        self._jitter_entry.pack(fill="x", padx=12, pady=2)

        ctk.CTkButton(left, text="+ Add Claim Time", fg_color=T.ACCENT,
                      height=32, command=self._add_claim_time).pack(
                          fill="x", padx=12, pady=6)

        self._claim_list = ctk.CTkScrollableFrame(left, fg_color=T.BG, height=140)
        self._claim_list.pack(fill="both", expand=True, padx=8, pady=(0,8))

        # ── Right: Session windows ─────────────────────────────────
        right = ctk.CTkFrame(c, fg_color=T.BG2, corner_radius=8)
        right.grid(row=0, column=1, sticky="nsew", padx=(6,0), pady=4)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="Session Windows",
                     font=T.FONT_H3, text_color=T.ACCENT).pack(anchor="w", padx=12, pady=8)

        # Day selector
        day_row = ctk.CTkFrame(right, fg_color="transparent")
        day_row.pack(fill="x", padx=12, pady=2)
        self._day_vars = []
        for d in DAYS_SHORT:
            v = tk.BooleanVar()
            self._day_vars.append(v)
            ctk.CTkCheckBox(day_row, text=d, variable=v,
                            width=44, checkbox_width=14, checkbox_height=14,
                            font=T.FONT_SMALL).pack(side="left", padx=1)

        tf = ctk.CTkFrame(right, fg_color="transparent")
        tf.pack(fill="x", padx=12, pady=2)
        tf.grid_columnconfigure((1,3), weight=1)
        ctk.CTkLabel(tf, text="Start:", font=T.FONT_SMALL,
                     text_color=T.TEXT_DIM).grid(row=0, column=0, sticky="w")
        self._win_start = ctk.CTkEntry(tf, placeholder_text="09:00")
        self._win_start.grid(row=0, column=1, sticky="ew", padx=4)
        ctk.CTkLabel(tf, text="Stop:", font=T.FONT_SMALL,
                     text_color=T.TEXT_DIM).grid(row=0, column=2, sticky="w", padx=(8,0))
        self._win_stop = ctk.CTkEntry(tf, placeholder_text="17:00")
        self._win_stop.grid(row=0, column=3, sticky="ew", padx=4)

        nf = ctk.CTkFrame(right, fg_color="transparent")
        nf.pack(fill="x", padx=12, pady=2)
        ctk.CTkLabel(nf, text="Name:", font=T.FONT_SMALL,
                     text_color=T.TEXT_DIM).pack(side="left")
        self._win_name = ctk.CTkEntry(nf, placeholder_text="Night Grind")
        self._win_name.pack(side="left", fill="x", expand=True, padx=4)

        ctk.CTkButton(right, text="+ Add Window", fg_color=T.BLUE,
                      height=32, command=self._add_window).pack(
                          fill="x", padx=12, pady=6)

        self._win_list = ctk.CTkScrollableFrame(right, fg_color=T.BG, height=140)
        self._win_list.pack(fill="both", expand=True, padx=8, pady=(0,8))

        # ── Bottom: Save / Apply ───────────────────────────────────
        bot = ctk.CTkFrame(c, fg_color="transparent")
        bot.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8,0))
        ctk.CTkButton(bot, text="💾 Save & Apply", fg_color=T.ACCENT,
                      height=36, command=self._save).pack(side="right", padx=4)
        self._enabled_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(bot, text="Schedule enabled for this account",
                        variable=self._enabled_var,
                        font=T.FONT_BODY).pack(side="left", padx=4)

    def _build_autostart(self):
        """System auto-start toggle at the bottom of the panel."""
        bar = ctk.CTkFrame(self, fg_color=T.BG2)
        bar.grid(row=3, column=0, sticky="ew", padx=16, pady=(8,12))

        ctk.CTkLabel(bar, text="System Auto-Start",
                     font=T.FONT_H3, text_color=T.TEXT).pack(side="left", padx=12, pady=8)
        self._autostart_var = tk.BooleanVar(value=False)
        ctk.CTkSwitch(bar, text="Launch app on system startup (minimized)",
                      variable=self._autostart_var,
                      font=T.FONT_BODY,
                      command=self._toggle_autostart).pack(side="left", padx=8)

    # ---------------------------------------------------------------
    def _refresh_ui(self):
        if not self._acct_sched:
            return
        self._placeholder.grid_remove()
        self._content.grid()
        self._enabled_var.set(self._acct_sched.enabled)
        self._refresh_claim_list()
        self._refresh_win_list()
        self._next_lbl.configure(text=f"Next: {self._sched.next_run()}")

    def _refresh_claim_list(self):
        for w in self._claim_list.winfo_children():
            w.destroy()
        if not self._acct_sched:
            return
        for i, ct in enumerate(self._acct_sched.claim_times):
            row = ctk.CTkFrame(self._claim_list, fg_color=T.BG3, corner_radius=6)
            row.pack(fill="x", pady=2)
            lbl = f"🕐 {ct.time_str}"
            if ct.jitter_minutes:
                lbl += f"  ±{ct.jitter_minutes}m"
            ctk.CTkLabel(row, text=lbl, font=T.FONT_BODY,
                         text_color=T.TEXT).pack(side="left", padx=8, pady=4)
            ctk.CTkButton(row, text="✕", width=24, height=24,
                          fg_color=T.RED, hover_color=T.BG,
                          command=lambda idx=i: self._remove_claim(idx)
                          ).pack(side="right", padx=4)

    def _refresh_win_list(self):
        for w in self._win_list.winfo_children():
            w.destroy()
        if not self._acct_sched:
            return
        for i, sw in enumerate(self._acct_sched.session_windows):
            row = ctk.CTkFrame(self._win_list, fg_color=T.BG3, corner_radius=6)
            row.pack(fill="x", pady=2)
            days_str = ",".join(d[:3].capitalize() for d in sw.days)
            ctk.CTkLabel(row, text=f"📅 {sw.name or days_str}  {sw.start_time}–{sw.end_time}",
                         font=T.FONT_SMALL, text_color=T.TEXT).pack(side="left", padx=8, pady=4)
            ctk.CTkButton(row, text="✕", width=24, height=24,
                          fg_color=T.RED, hover_color=T.BG,
                          command=lambda idx=i: self._remove_window(idx)
                          ).pack(side="right", padx=4)

    # ── Actions ─────────────────────────────────────────────────────
    def _add_claim_time(self):
        if not self._acct_sched:
            return
        t = self._claim_time_entry.get().strip()
        if not t:
            return
        try:
            h, m = map(int, t.split(":"))
            assert 0 <= h < 24 and 0 <= m < 60
        except Exception:
            messagebox.showerror("Invalid", "Enter time as HH:MM (e.g. 08:00)")
            return
        jitter = 0
        try:
            jitter = int(self._jitter_entry.get().strip() or "0")
        except ValueError:
            pass
        self._acct_sched.claim_times.append(ClaimTime(time_str=t, jitter_minutes=jitter))
        self._claim_time_entry.delete(0, "end")
        self._jitter_entry.delete(0, "end")
        self._refresh_claim_list()

    def _remove_claim(self, idx: int):
        if self._acct_sched and 0 <= idx < len(self._acct_sched.claim_times):
            self._acct_sched.claim_times.pop(idx)
            self._refresh_claim_list()

    def _add_window(self):
        if not self._acct_sched:
            return
        days = [DAYS_FULL[i] for i, v in enumerate(self._day_vars) if v.get()]
        if not days:
            messagebox.showwarning("Days", "Select at least one day.")
            return
        start = self._win_start.get().strip() or "09:00"
        stop  = self._win_stop.get().strip()  or "17:00"
        name  = self._win_name.get().strip()
        self._acct_sched.session_windows.append(
            SessionWindow(name=name, days=days, start_time=start, end_time=stop))
        self._win_name.delete(0, "end")
        self._refresh_win_list()

    def _remove_window(self, idx: int):
        if self._acct_sched and 0 <= idx < len(self._acct_sched.session_windows):
            self._acct_sched.session_windows.pop(idx)
            self._refresh_win_list()

    def _save(self):
        if not self._acct_sched:
            return
        self._acct_sched.enabled = self._enabled_var.get()
        self._sched.set_account_schedule(self._acct_sched)
        messagebox.showinfo("Saved", "Schedule saved and applied.")
        self._next_lbl.configure(text=f"Next: {self._sched.next_run()}")

    def _toggle_autostart(self):
        if self._autostart_var.get():
            ok = BotScheduler.register_autostart()
            if not ok:
                self._autostart_var.set(False)
                messagebox.showerror("Auto-start",
                    "Could not register auto-start on this platform.")
        else:
            BotScheduler.unregister_autostart()
