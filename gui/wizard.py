"""
FaucetPlay — First-Run Onboarding Wizard
5 steps: API Key → Cookie → PAW Level → Currency → Target & Cashout
"""
from __future__ import annotations

import threading
import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from . import theme as T
from core.api import DuckDiceAPI, CookieExpiredError
from core.config import BotConfig


STEPS = [
    "API Key",
    "Session Cookie",
    "PAW Level",
    "Currency",
    "Target & Cashout",
]


class OnboardingWizard(ctk.CTkToplevel):
    """
    Modal first-run wizard.  Populates a BotConfig and calls on_complete().
    """

    def __init__(self, parent, config: BotConfig,
                 on_complete: Callable[[], None]):
        super().__init__(parent)
        self.title("FaucetPlay — Setup")
        self.geometry("540x580")
        self.resizable(False, False)
        self.configure(fg_color=T.BG)
        self.grab_set()

        self._cfg      = config
        self._done_cb  = on_complete
        self._step     = 0
        self._api: Optional[DuckDiceAPI] = None
        self._paw: int = 0

        self._api_key_var    = tk.StringVar(value=config.get("api_key", ""))
        self._cookie_var     = tk.StringVar(value=config.get("cookie", ""))
        self._currency_var   = tk.StringVar(value=config.get("currency", "USDC"))
        self._target_var     = tk.StringVar(value=str(config.get("target_amount", "20.0")))
        self._auto_co_var    = tk.BooleanVar(value=bool(config.get("auto_cashout", True)))
        self._continue_var   = tk.BooleanVar(value=bool(config.get("continue_after_cashout", True)))

        self._build()
        self._show_step(0)

    # ── Layout ─────────────────────────────────────────────────────

    def _build(self):
        top = ctk.CTkFrame(self, fg_color=T.BG3, height=52)
        top.pack(fill="x")
        top.pack_propagate(False)
        self._step_label = ctk.CTkLabel(top, text="", font=T.FONT_H2,
                                         text_color=T.TEXT)
        self._step_label.pack(side="left", padx=16, pady=12)
        self._step_counter = ctk.CTkLabel(top, text="", font=T.FONT_SMALL,
                                           text_color=T.TEXT_DIM)
        self._step_counter.pack(side="right", padx=16)

        self._progress = ctk.CTkProgressBar(self, height=6, fg_color=T.BG2,
                                            progress_color=T.ACCENT)
        self._progress.pack(fill="x")
        self._progress.set(0)

        # Step dots indicator
        dots_frame = ctk.CTkFrame(self, fg_color="transparent")
        dots_frame.pack(pady=(4, 0))
        self._dots: list[ctk.CTkLabel] = []
        for _ in range(len(STEPS)):
            lbl = ctk.CTkLabel(dots_frame, text="○", font=T.FONT_H3,
                                text_color=T.TEXT_DIM)
            lbl.pack(side="left", padx=3)
            self._dots.append(lbl)

        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="both", expand=True, padx=24, pady=12)

        self._status_lbl = ctk.CTkLabel(self, text="", font=T.FONT_SMALL,
                                         text_color=T.TEXT_DIM, wraplength=500)
        self._status_lbl.pack(pady=(0, 4))

        nav = ctk.CTkFrame(self, fg_color=T.BG2, height=52)
        nav.pack(fill="x", side="bottom")
        nav.pack_propagate(False)
        self._back_btn = ctk.CTkButton(nav, text="◀ Back", width=90,
                                        fg_color=T.BG3, command=self._back)
        self._back_btn.pack(side="left", padx=10, pady=8)
        self._next_btn = ctk.CTkButton(nav, text="Next ▶", width=110,
                                        fg_color=T.ACCENT, command=self._next)
        self._next_btn.pack(side="right", padx=10, pady=8)

    def _clear(self):
        for w in self._content.winfo_children():
            w.destroy()

    def _status(self, msg: str, colour: str = T.TEXT_DIM):
        self._status_lbl.configure(text=msg, text_color=colour)
        self.update_idletasks()

    def _show_step(self, idx: int):
        self._step = idx
        self._clear()
        self._step_label.configure(text=f"Step {idx+1}: {STEPS[idx]}")
        self._step_counter.configure(text=f"{idx+1} / {len(STEPS)}")
        self._progress.set(idx / max(len(STEPS) - 1, 1))
        self._back_btn.configure(state="normal" if idx > 0 else "disabled")
        self._next_btn.configure(text="Finish ✓" if idx == len(STEPS)-1 else "Next ▶",
                                  state="normal")
        self._status("")
        # Update dots
        for i, dot in enumerate(self._dots):
            if i == idx:
                dot.configure(text="●", text_color=T.ACCENT)
            else:
                dot.configure(text="○", text_color=T.TEXT_DIM)
        [self._step_apikey, self._step_cookie, self._step_paw,
         self._step_currency, self._step_target][idx]()

    # ── Steps ──────────────────────────────────────────────────────

    def _step_apikey(self):
        _heading(self._content, "Enter your DuckDice API Key")
        _hint(self._content,
              "DuckDice.io → Settings → API → Generate Key\n"
              "Your key is stored encrypted on your machine only.")
        _entry(self._content, "API Key", var=self._api_key_var, show="•")
        _hint(self._content,
              "💡 The API key lets FaucetPlay claim your faucet and place bets "
              "on your behalf — it cannot withdraw funds.")

    def _step_cookie(self):
        _heading(self._content, "Enter your Session Cookie")
        _hint(self._content,
              "Open DuckDice in Chrome/Firefox → press F12 → Application tab\n"
              "→ Cookies → duckdice.io → copy the full cookie string.")
        _entry(self._content, "Cookie string", var=self._cookie_var, show="•")
        _hint(self._content,
              "⚠️  Never share your cookie. It grants access to your account.\n"
              "FaucetPlay stores it encrypted locally and never transmits it.")

    def _step_paw(self):
        _heading(self._content, "Detecting your PAW Level…")
        _hint(self._content,
              "PAW (Play and Win) level determines how you claim faucets.\n"
              "Lower levels require a quick Tic-Tac-Toe mini-game.")

        # PAW levels reference table
        tbl = ctk.CTkFrame(self._content, fg_color=T.BG3, corner_radius=6)
        tbl.pack(fill="x", pady=(4, 10))
        PAW_ROWS = [
            (0, "New Player",   "Tic-Tac-Toe (many games)",  T.TEXT_DIM),
            (1, "Bronze",       "Tic-Tac-Toe (3 games)",     T.TEXT_DIM),
            (2, "Silver 🥈",    "Tic-Tac-Toe (2 games)",     T.ACCENT2),
            (3, "Gold 🥇",      "Tic-Tac-Toe (1 game)",      T.ACCENT2),
            (4, "Platinum 💎",  "Direct API claim ✅",        T.GREEN),
            (5, "Diamond 💠",   "Direct API claim ✅",        T.GREEN),
        ]
        hdrs = [("Level", 50), ("Tier", 110), ("Claim Method", 220)]
        for col, (h, w) in enumerate(hdrs):
            ctk.CTkLabel(tbl, text=h, font=T.FONT_SMALL, text_color=T.TEXT_DIM,
                          width=w, anchor="w").grid(row=0, column=col,
                                                     padx=(10 if col == 0 else 4, 4),
                                                     pady=(6, 2), sticky="w")
        for r, (lvl, tier, method, col) in enumerate(PAW_ROWS, start=1):
            ctk.CTkLabel(tbl, text=str(lvl), font=T.FONT_SMALL, text_color=col,
                          width=50, anchor="w").grid(row=r, column=0,
                                                      padx=(10, 4), pady=2, sticky="w")
            ctk.CTkLabel(tbl, text=tier, font=T.FONT_SMALL, text_color=T.TEXT,
                          width=110, anchor="w").grid(row=r, column=1,
                                                       padx=4, pady=2, sticky="w")
            ctk.CTkLabel(tbl, text=method, font=T.FONT_SMALL, text_color=col,
                          width=220, anchor="w").grid(row=r, column=2,
                                                       padx=(4, 10), pady=2, sticky="w")

        self._paw_badge = ctk.CTkLabel(self._content, text="",
                                        font=(T.FONT_H1[0], 28, "bold"),
                                        text_color=T.ACCENT)
        self._paw_badge.pack(pady=(4, 2))
        self._paw_info = ctk.CTkLabel(self._content, text="Connecting…",
                                       font=T.FONT_BODY, text_color=T.TEXT_DIM,
                                       wraplength=480)
        self._paw_info.pack()

        self._next_btn.configure(state="disabled")
        threading.Thread(target=self._fetch_paw, daemon=True).start()

    def _fetch_paw(self):
        try:
            self._api = DuckDiceAPI(
                api_key=self._api_key_var.get().strip(),
                cookie=self._cookie_var.get().strip(),
            )
            paw = self._api.get_paw_level(force=True)
            self._paw = paw
            ttt = self._api.ttt_games_needed()
            claim_method = ("Direct API claim ✅"
                            if paw >= 4
                            else f"{ttt} Tic-Tac-Toe game(s) per claim ⚡")
            level_descs = {0: "New player", 1: "Bronze", 2: "Silver",
                           3: "Gold", 4: "Platinum", 5: "Diamond"}
            desc = level_descs.get(paw, "")
            self.after(0, lambda: self._paw_badge.configure(
                text=f"🐾  Level {paw}  ({desc})"))
            self.after(0, lambda: self._paw_info.configure(
                text=f"Claim method: {claim_method}",
                text_color=T.TEXT))
            self.after(0, lambda: self._next_btn.configure(state="normal"))
            self.after(0, lambda: self._status("Connected! PAW level detected ✓", T.GREEN))
        except CookieExpiredError:
            self.after(0, lambda: self._paw_info.configure(
                text="Cookie appears invalid or expired.", text_color=T.RED))
            self.after(0, lambda: self._status("Check your cookie and go back.", T.RED))
            self.after(0, lambda: self._next_btn.configure(state="normal"))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._paw_info.configure(
                text=f"Could not connect: {err}", text_color=T.YELLOW))
            self.after(0, lambda: self._status("Connection failed — check API key & cookie.", T.YELLOW))
            self.after(0, lambda: self._next_btn.configure(state="normal"))

    def _step_currency(self):
        _heading(self._content, "Choose your Currency")
        _hint(self._content, "Select the currency you want to farm faucets in.")
        self._curr_list = ctk.CTkScrollableFrame(self._content, fg_color=T.BG2,
                                                  height=230)
        self._curr_list.pack(fill="x", pady=8)
        threading.Thread(target=self._fetch_currencies, daemon=True).start()

    def _fetch_currencies(self):
        currencies = ["USDC", "BTC", "ETH", "LTC", "DOGE", "TRX", "SOL", "BNB"]
        if self._api:
            try:
                currencies = self._api.get_available_currencies() or currencies
            except Exception:
                pass
        def _draw():
            for c in currencies:
                ctk.CTkRadioButton(self._curr_list, text=c,
                                   variable=self._currency_var, value=c,
                                   font=T.FONT_BODY).pack(anchor="w", padx=12, pady=4)
        self.after(0, _draw)

    def _step_target(self):
        _heading(self._content, "Target Amount & Cashout")
        _hint(self._content,
              "The bot will farm until your faucet balance reaches this amount.")
        _entry(self._content, "Target amount", var=self._target_var)

        ctk.CTkFrame(self._content, height=1, fg_color=T.BG3).pack(
            fill="x", pady=8)

        _label(self._content, "Cashout options")
        ctk.CTkCheckBox(self._content,
                         text="Auto cashout faucet → main when target reached",
                         variable=self._auto_co_var,
                         font=T.FONT_BODY).pack(anchor="w", pady=4)
        ctk.CTkCheckBox(self._content,
                         text="Continue farming toward the same target after each cashout",
                         variable=self._continue_var,
                         font=T.FONT_BODY).pack(anchor="w", pady=4)

    # ── Navigation ─────────────────────────────────────────────────

    def _back(self):
        if self._step > 0:
            self._show_step(self._step - 1)

    def _next(self):
        if not self._validate():
            return
        if self._step == len(STEPS) - 1:
            self._finish()
        else:
            self._show_step(self._step + 1)

    def _validate(self) -> bool:
        if self._step == 0 and not self._api_key_var.get().strip():
            self._status("API Key is required.", T.RED); return False
        if self._step == 1 and not self._cookie_var.get().strip():
            self._status("Cookie is required.", T.RED); return False
        if self._step == 4:
            try:
                val = float(self._target_var.get())
                if val <= 0:
                    raise ValueError()
            except ValueError:
                self._status("Enter a valid target amount (e.g. 20.0).", T.RED)
                return False
        return True

    def _finish(self):
        self._cfg.set("api_key",               self._api_key_var.get().strip())
        self._cfg.set("cookie",                self._cookie_var.get().strip())
        self._cfg.set("currency",              self._currency_var.get())
        self._cfg.set("target_amount",         float(self._target_var.get()))
        self._cfg.set("auto_cashout",          self._auto_co_var.get())
        self._cfg.set("continue_after_cashout", self._continue_var.get())
        self._cfg.set("cashout_threshold",     0.0)  # 0 = use target_amount
        self._cfg.save()
        self._done_cb()
        self.destroy()


# ── Widget helpers ─────────────────────────────────────────────────

def _heading(parent, text: str):
    ctk.CTkLabel(parent, text=text, font=T.FONT_H2, text_color=T.TEXT,
                 wraplength=490).pack(anchor="w", pady=(4, 6))

def _hint(parent, text: str):
    ctk.CTkLabel(parent, text=text, font=T.FONT_SMALL, text_color=T.TEXT_DIM,
                 wraplength=490, justify="left").pack(anchor="w", pady=(0, 4))

def _label(parent, text: str):
    ctk.CTkLabel(parent, text=text, font=T.FONT_H3, text_color=T.TEXT
                 ).pack(anchor="w", pady=(4, 2))

def _entry(parent, label: str, var=None, show: str = ""):
    ctk.CTkLabel(parent, text=label, font=T.FONT_SMALL,
                 text_color=T.TEXT_DIM).pack(anchor="w")
    e = ctk.CTkEntry(parent, textvariable=var, show=show, height=36)
    e.pack(fill="x", pady=(2, 8))
    return e
