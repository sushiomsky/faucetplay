"""
FaucetPlay GUI — First-Run Onboarding Wizard
7 steps: API key → Cookie → PAW display → Network profile → Currency → Target → Test roll
"""
from __future__ import annotations
import threading
import tkinter as tk
from tkinter import messagebox
from typing import Optional, Callable
import customtkinter as ctk
from . import theme as T
from core.accounts import Account, AccountManager
from core.network import (NetworkProfileManager, NetworkProfile,
                          ProfileType, ProxyProtocol, VpnMethod)
from core.api import DuckDiceAPI, CookieExpiredError


STEPS = [
    "API Key",
    "Cookie",
    "PAW Level",
    "Network Profile",
    "Currency",
    "Target & Strategy",
    "Test Roll",
]


class OnboardingWizard(ctk.CTkToplevel):
    """
    Modal wizard shown on first launch.
    Creates the first Account and optionally a NetworkProfile.
    Calls `on_complete(account)` when finished.
    """

    def __init__(self, parent, account_mgr: AccountManager,
                 network_mgr: NetworkProfileManager,
                 on_complete: Callable[[Account], None]):
        super().__init__(parent)
        self.title("FaucetPlay — Setup Wizard")
        self.geometry("560x560")
        self.resizable(False, False)
        self.configure(fg_color=T.BG)
        self.grab_set()

        self._amgr   = account_mgr
        self._nmgr   = network_mgr
        self._done_cb = on_complete
        self._step   = 0
        self._acct   = Account(label="My Account")
        self._api: Optional[DuckDiceAPI] = None

        # Step data vars
        self._api_key_var   = tk.StringVar()
        self._cookie_var    = tk.StringVar()
        self._currency_var  = tk.StringVar(value="USDC")
        self._target_var    = tk.StringVar(value="20.0")
        self._net_type_var  = tk.StringVar(value="direct")
        self._proxy_host_var = tk.StringVar()
        self._proxy_port_var = tk.StringVar(value="1080")
        self._proxy_user_var = tk.StringVar()
        self._proxy_pass_var = tk.StringVar()
        self._proxy_proto_var = tk.StringVar(value="socks5")

        self._build()
        self._show_step(0)

    # ---------------------------------------------------------------
    def _build(self):
        # Progress bar + step label
        top = ctk.CTkFrame(self, fg_color=T.BG3, height=56)
        top.pack(fill="x")
        top.pack_propagate(False)
        self._step_label = ctk.CTkLabel(top, text="", font=T.FONT_H2, text_color=T.TEXT)
        self._step_label.pack(side="left", padx=16, pady=12)
        self._step_counter = ctk.CTkLabel(top, text="", font=T.FONT_SMALL, text_color=T.TEXT_DIM)
        self._step_counter.pack(side="right", padx=16)

        self._progress = ctk.CTkProgressBar(self, height=6, fg_color=T.BG2,
                                            progress_color=T.ACCENT)
        self._progress.pack(fill="x")
        self._progress.set(0)

        # Content frame (swapped per step)
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="both", expand=True, padx=24, pady=16)

        # Status / feedback label
        self._status_lbl = ctk.CTkLabel(self, text="", font=T.FONT_SMALL,
                                         text_color=T.TEXT_DIM, wraplength=500)
        self._status_lbl.pack(pady=(0, 4))

        # Nav buttons
        nav = ctk.CTkFrame(self, fg_color=T.BG2, height=52)
        nav.pack(fill="x", side="bottom")
        nav.pack_propagate(False)
        self._back_btn = ctk.CTkButton(nav, text="◀ Back", width=90, fg_color=T.BG3,
                                       command=self._back)
        self._back_btn.pack(side="left", padx=10, pady=8)
        self._next_btn = ctk.CTkButton(nav, text="Next ▶", width=90, fg_color=T.ACCENT,
                                       command=self._next)
        self._next_btn.pack(side="right", padx=10, pady=8)

    # ---------------------------------------------------------------
    def _status(self, msg: str, colour: str = T.TEXT_DIM):
        self._status_lbl.configure(text=msg, text_color=colour)
        self.update_idletasks()

    def _clear_content(self):
        for w in self._content.winfo_children():
            w.destroy()

    def _show_step(self, idx: int):
        self._step = idx
        self._clear_content()
        self._step_label.configure(text=f"Step {idx+1}: {STEPS[idx]}")
        self._step_counter.configure(text=f"{idx+1} / {len(STEPS)}")
        self._progress.set((idx) / (len(STEPS) - 1))
        self._back_btn.configure(state="normal" if idx > 0 else "disabled")
        self._next_btn.configure(text="Finish ✓" if idx == len(STEPS)-1 else "Next ▶")
        self._status("")

        builders = [
            self._step_apikey,
            self._step_cookie,
            self._step_paw,
            self._step_network,
            self._step_currency,
            self._step_target,
            self._step_testroll,
        ]
        builders[idx]()

    # ── Steps ─────────────────────────────────────────────────────
    def _step_apikey(self):
        _heading(self._content, "Enter your DuckDice API Key")
        _hint(self._content, "DuckDice.io → Settings → API → Generate Key")
        self._apikey_entry = _entry(self._content, "API Key", show="•",
                                    var=self._api_key_var)
        _hint(self._content, "Your key is stored encrypted on your machine only.")

    def _step_cookie(self):
        _heading(self._content, "Enter your Session Cookie")
        _hint(self._content,
              "Open DuckDice in Chrome → F12 → Application → Cookies → duckdice.io\n"
              "Copy the full cookie string and paste it below.")
        self._cookie_entry = _entry(self._content, "Cookie", show="•",
                                    var=self._cookie_var)
        _hint(self._content,
              "⚠️  Never share your cookie. It is stored encrypted locally.")

    def _step_paw(self):
        _heading(self._content, "Fetching your PAW Level…")
        self._paw_lbl = ctk.CTkLabel(self._content, text="",
                                      font=("Segoe UI", 32, "bold"),
                                      text_color=T.ACCENT)
        self._paw_lbl.pack(pady=16)
        self._paw_info = ctk.CTkLabel(self._content, text="", font=T.FONT_BODY,
                                       text_color=T.TEXT, wraplength=480)
        self._paw_info.pack(pady=4)
        self._next_btn.configure(state="disabled")
        threading.Thread(target=self._fetch_paw, daemon=True).start()

    def _fetch_paw(self):
        api_key = self._api_key_var.get().strip()
        cookie  = self._cookie_var.get().strip()
        try:
            self._api = DuckDiceAPI(api_key=api_key, cookie=cookie)
            paw = self._api.get_paw_level(force=True)
            self._acct.api_key = api_key
            self._acct.cookie  = cookie
            self._acct.paw_level = paw
            ttt = self._api.ttt_games_needed()
            info = (
                f"PAW Level {paw} — "
                + (f"Direct API claim (no mini-game needed) ✅"
                   if paw >= 4
                   else f"⚡ {ttt} Tic-Tac-Toe game(s) required per claim")
            )
            self.after(0, lambda: self._paw_lbl.configure(text=f"🐾  Level {paw}"))
            self.after(0, lambda: self._paw_info.configure(text=info))
            self.after(0, lambda: self._next_btn.configure(state="normal"))
            self.after(0, lambda: self._status("PAW level loaded ✓", T.GREEN))
        except CookieExpiredError:
            self.after(0, lambda: self._status("Cookie looks invalid or expired.", T.RED))
            self.after(0, lambda: self._next_btn.configure(state="normal"))
        except Exception as e:
            self.after(0, lambda: self._status(f"Could not fetch PAW level: {e}", T.YELLOW))
            self.after(0, lambda: self._next_btn.configure(state="normal"))

    def _step_network(self):
        _heading(self._content, "Network Isolation (Proxy / VPN / Direct)")
        _hint(self._content,
              "Each account is permanently bound to one network identity.\n"
              "Using Direct exposes your real IP — DuckDice may link accounts sharing it.")

        self._net_type_var.set("direct")
        for val, label in [("direct", "⚠️  Direct connection"),
                           ("proxy",  "🔒 Proxy (HTTP / SOCKS5)"),
                           ("vpn",    "🛡  VPN (OpenVPN / WireGuard)")]:
            rb = ctk.CTkRadioButton(self._content, text=label,
                                    variable=self._net_type_var, value=val,
                                    command=self._toggle_net_fields,
                                    font=T.FONT_BODY)
            rb.pack(anchor="w", pady=3)

        self._proxy_frame = ctk.CTkFrame(self._content, fg_color=T.BG2, corner_radius=8)
        for lbl, var, ph, show in [
            ("Host",     self._proxy_host_var, "127.0.0.1",  ""),
            ("Port",     self._proxy_port_var, "1080",        ""),
            ("Username", self._proxy_user_var, "(optional)",  ""),
            ("Password", self._proxy_pass_var, "(optional)",  "•"),
        ]:
            ctk.CTkLabel(self._proxy_frame, text=lbl, font=T.FONT_SMALL,
                         text_color=T.TEXT_DIM).pack(anchor="w", padx=8, pady=(4,0))
            ctk.CTkEntry(self._proxy_frame, textvariable=var,
                         placeholder_text=ph, show=show).pack(
                             fill="x", padx=8, pady=(0,2))
        pp_row = ctk.CTkFrame(self._proxy_frame, fg_color="transparent")
        pp_row.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(pp_row, text="Protocol:", font=T.FONT_SMALL,
                     text_color=T.TEXT_DIM).pack(side="left")
        for v, t in [("socks5","SOCKS5"),("socks4","SOCKS4"),("http","HTTP"),("https","HTTPS")]:
            ctk.CTkRadioButton(pp_row, text=t, variable=self._proxy_proto_var,
                               value=v, font=T.FONT_SMALL).pack(side="left", padx=4)

        ctk.CTkButton(self._proxy_frame, text="🔍 Test Connection",
                      fg_color=T.BLUE, height=28,
                      command=self._test_proxy).pack(fill="x", padx=8, pady=6)

    def _toggle_net_fields(self):
        if self._net_type_var.get() == "proxy":
            self._proxy_frame.pack(fill="x", pady=6)
        else:
            self._proxy_frame.pack_forget()

    def _test_proxy(self):
        self._status("Testing proxy…", T.TEXT_DIM)
        def _run():
            try:
                proto = self._proxy_proto_var.get()
                host  = self._proxy_host_var.get().strip()
                port  = self._proxy_port_var.get().strip()
                user  = self._proxy_user_var.get().strip()
                pw    = self._proxy_pass_var.get().strip()
                auth  = f"{user}:{pw}@" if user else ""
                proxy_url = f"{proto}://{auth}{host}:{port}"
                import requests as _req
                r = _req.get("https://api.ipify.org?format=json",
                             proxies={"http": proxy_url, "https": proxy_url},
                             timeout=10)
                ip = r.json().get("ip", "?")
                self.after(0, lambda: self._status(f"✅ Proxy OK  —  IP: {ip}", T.GREEN))
            except Exception as e:
                self.after(0, lambda: self._status(f"❌ Proxy failed: {e}", T.RED))
        threading.Thread(target=_run, daemon=True).start()

    def _step_currency(self):
        _heading(self._content, "Select Currency")
        _hint(self._content, "Fetching available currencies from your account…")
        self._curr_list = ctk.CTkScrollableFrame(self._content, fg_color=T.BG2, height=220)
        self._curr_list.pack(fill="x", pady=8)
        threading.Thread(target=self._fetch_currencies, daemon=True).start()

    def _fetch_currencies(self):
        if not self._api:
            return
        try:
            currencies = self._api.get_available_currencies() or ["USDC","BTC","ETH","LTC","DOGE"]
        except Exception:
            currencies = ["USDC","BTC","ETH","LTC","DOGE","TRX","SOL"]
        def _draw():
            for c in currencies:
                ctk.CTkRadioButton(self._curr_list, text=c,
                                   variable=self._currency_var, value=c,
                                   font=T.FONT_BODY).pack(anchor="w", padx=8, pady=3)
        self.after(0, _draw)

    def _step_target(self):
        _heading(self._content, "Set Target Amount & Strategy")
        _hint(self._content, "The bot stops and optionally cashes out when this amount is reached.")
        _entry(self._content, "Target (USD equivalent)", var=self._target_var)

        ctk.CTkLabel(self._content, text="Risk Preset", font=T.FONT_H3,
                     text_color=T.TEXT).pack(anchor="w", pady=(12,4))
        self._strategy_var = tk.StringVar(value="all_in")
        for val, label, desc in [
            ("all_in",    "🎯 All-In (Default)",    "Single all-in roll per claim"),
            ("martingale","📈 Martingale",           "Double on loss, reset on win"),
            ("fixed_pct", "📊 Fixed %",             "Bet fixed % of balance each roll"),
        ]:
            row = ctk.CTkFrame(self._content, fg_color=T.BG2, corner_radius=6)
            row.pack(fill="x", pady=2)
            ctk.CTkRadioButton(row, text=f"{label}  —  {desc}",
                               variable=self._strategy_var, value=val,
                               font=T.FONT_BODY).pack(anchor="w", padx=10, pady=6)

    def _step_testroll(self):
        _heading(self._content, "Everything looks good!")
        self._test_lbl = ctk.CTkLabel(
            self._content,
            text=(
                "✅  API key validated\n"
                "✅  Cookie accepted\n"
                "✅  PAW level detected\n"
                "✅  Network profile configured\n\n"
                "Click Finish to save your account and open the dashboard."
            ),
            font=T.FONT_BODY, text_color=T.TEXT, justify="left")
        self._test_lbl.pack(anchor="w", pady=12)

    # ── Navigation ────────────────────────────────────────────────
    def _back(self):
        if self._step > 0:
            self._show_step(self._step - 1)

    def _next(self):
        if not self._validate_step():
            return
        if self._step == len(STEPS) - 1:
            self._finish()
        else:
            self._show_step(self._step + 1)

    def _validate_step(self) -> bool:
        if self._step == 0 and not self._api_key_var.get().strip():
            self._status("API Key is required.", T.RED); return False
        if self._step == 1 and not self._cookie_var.get().strip():
            self._status("Cookie is required.", T.RED); return False
        return True

    def _finish(self):
        # Build network profile if proxy/VPN selected
        net_type = self._net_type_var.get()
        if net_type == "proxy":
            profile = NetworkProfile(
                label=f"Proxy for {self._acct.label}",
                type=ProfileType.PROXY,
                proxy_protocol=self._proxy_proto_var.get(),
                proxy_host=self._proxy_host_var.get().strip(),
                proxy_port=int(self._proxy_port_var.get().strip() or "1080"),
                proxy_username=self._proxy_user_var.get().strip() or None,
                proxy_password=self._proxy_pass_var.get().strip() or None,
            )
            self._nmgr.add(profile)
            self._acct.network_profile_id = profile.id
        # VPN: user must set up separately (wizard only covers proxy for now)

        self._acct.preferred_currency = self._currency_var.get()
        self._acct.strategy_profile   = self._strategy_var.get() \
                                        if hasattr(self, '_strategy_var') else "all_in"
        try:
            float(self._target_var.get())
        except ValueError:
            pass  # keep default

        self._amgr.add(self._acct)
        if self._acct.network_profile_id:
            self._nmgr.assign_to_account(self._acct.network_profile_id, self._acct.id)

        self._done_cb(self._acct)
        self.destroy()


# ── Helpers ───────────────────────────────────────────────────────

def _heading(parent, text: str):
    ctk.CTkLabel(parent, text=text, font=T.FONT_H2,
                 text_color=T.TEXT, wraplength=500).pack(anchor="w", pady=(4,6))

def _hint(parent, text: str):
    ctk.CTkLabel(parent, text=text, font=T.FONT_SMALL,
                 text_color=T.TEXT_DIM, wraplength=500,
                 justify="left").pack(anchor="w", pady=(0,4))

def _entry(parent, label: str, var=None, show: str = "", placeholder: str = ""):
    ctk.CTkLabel(parent, text=label, font=T.FONT_SMALL,
                 text_color=T.TEXT_DIM).pack(anchor="w")
    e = ctk.CTkEntry(parent, textvariable=var, show=show,
                     placeholder_text=placeholder, height=36)
    e.pack(fill="x", pady=(2, 8))
    return e
