"""
FaucetPlay GUI — Settings Panel
Inline-editable settings: credentials, strategy, cashout, schedule.
"""
from __future__ import annotations

import sys
import threading
import tkinter as tk
from typing import Callable, List, Optional

import customtkinter as ctk

from . import theme as T
from .feedback_dialog import FeedbackDialog
from core.api import DuckDiceAPI
from core.config import BotConfig
from core.scheduler import BotScheduler
from core.strategies import STRATEGY_LABELS, STRATEGY_NAMES


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
        self._browser_session_var = tk.BooleanVar(value=bool(config.get("use_browser_session", False)))

        # Strategy vars
        saved_strategy = config.get("strategy", "all_in")
        self._strategy_var      = tk.StringVar(value=STRATEGY_LABELS.get(saved_strategy, "All-In"))
        self._base_bet_var      = tk.StringVar(value=str(config.get("strategy_base_bet", "0.001")))
        self._bet_percent_var   = tk.StringVar(value=str(config.get("strategy_bet_percent", "1.0")))
        self._strat_chance_var  = tk.StringVar(value=str(config.get("strategy_chance", "49.5")))

        # Schedule time entries (up to 3 claim times)
        saved_times: List[str] = config.get("schedules", []) or []
        while len(saved_times) < 3:
            saved_times.append("")
        self._time_vars = [tk.StringVar(value=t) for t in saved_times[:3]]
        self._jitter_var = tk.StringVar(value=str(config.get("jitter_minutes", "5")))

        self._dirty = False
        self._save_btn: Optional["ctk.CTkButton"] = None

        self._build()

        # Watch all vars for unsaved changes
        _watched = (
            self._api_key_var, self._cookie_var, self._currency_var, self._target_var,
            self._edge_var, self._base_bet_var, self._bet_percent_var,
            self._strat_chance_var, self._jitter_var, self._strategy_var,
            self._auto_co_var, self._continue_var, self._sched_on_var,
            self._browser_session_var, *self._time_vars,
        )
        for _v in _watched:
            _v.trace_add("write", self._mark_dirty)

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
        hint.pack(anchor="w", padx=4, pady=(0, 4))

        # Cookie auto-detection buttons
        cookie_btn_row = ctk.CTkFrame(self, fg_color="transparent")
        cookie_btn_row.pack(anchor="w", pady=(0, 4))

        self._detect_btn = ctk.CTkButton(
            cookie_btn_row, text="🔍 Detect from Chrome/Firefox", height=30,
            fg_color=T.BG3, hover_color=T.BG2, font=T.FONT_SMALL,
            command=self._detect_cookie,
        )
        self._detect_btn.pack(side="left", padx=(0, 6))

        self._capture_btn = ctk.CTkButton(
            cookie_btn_row, text="🤖 Open Browser & Capture", height=30,
            fg_color=T.BG3, hover_color=T.BG2, font=T.FONT_SMALL,
            command=self._capture_cookie,
        )
        self._capture_btn.pack(side="left")

        self._cookie_status_lbl = ctk.CTkLabel(
            self, text="", font=T.FONT_SMALL, text_color=T.TEXT_DIM)
        self._cookie_status_lbl.pack(anchor="w", padx=4, pady=(0, 4))

        # Browser Session mode
        bs_row = ctk.CTkFrame(self, fg_color="transparent")
        bs_row.pack(fill="x", pady=3)
        ctk.CTkCheckBox(bs_row,
                         text="🌐  Browser Session mode (Playwright)",
                         variable=self._browser_session_var,
                         font=T.FONT_BODY).pack(side="left")
        ctk.CTkLabel(bs_row,
                      text="  Routes all API calls through a real browser — harder to detect",
                      font=T.FONT_SMALL, text_color=T.TEXT_DIM).pack(side="left")

        self._test_btn = ctk.CTkButton(
            self, text="🔍 Test Connection", height=32,
            fg_color=T.BG3, hover_color=T.BG2, font=T.FONT_BODY,
            command=self._test_connection,
        )
        self._test_btn.pack(anchor="w", pady=(0, 4))

        # ── Strategy ─────────────────────────────────────────────
        _section("🎲  Strategy")
        _row("Currency", lambda p: ctk.CTkOptionMenu(
            p, variable=self._currency_var, height=32,
            values=["USDC", "BTC", "ETH", "LTC", "DOGE", "TRX", "SOL", "BNB", "XRP"],
            fg_color=T.BG3, button_color=T.BG3, button_hover_color=T.BG2,
        ))

        # Target amount row with presets
        target_row = ctk.CTkFrame(self, fg_color="transparent")
        target_row.pack(fill="x", pady=3)
        ctk.CTkLabel(target_row, text="Target amount", width=160, anchor="w",
                      font=T.FONT_BODY, text_color=T.TEXT).pack(side="left")
        ctk.CTkEntry(target_row, textvariable=self._target_var, height=32,
                      width=100).pack(side="left")
        for preset in ("5", "10", "20", "50", "100"):
            _v = preset
            ctk.CTkButton(
                target_row, text=_v, width=38, height=26,
                fg_color=T.BG3, hover_color=T.BG2, font=T.FONT_SMALL,
                command=lambda v=_v: self._target_var.set(v),
            ).pack(side="left", padx=(4, 0))

        self._target_err_lbl = ctk.CTkLabel(self, text="", font=T.FONT_SMALL,
                                             text_color=T.RED)
        self._target_err_lbl.pack(anchor="w", padx=(164, 0))

        def _validate_target(*_):
            try:
                val = float(self._target_var.get())
                if val <= 0:
                    raise ValueError()
                self._target_err_lbl.configure(text="")
            except ValueError:
                if self._target_var.get():
                    self._target_err_lbl.configure(text="⚠ Must be a positive number")
        self._target_var.trace_add("write", _validate_target)

        # House edge row with hint
        _row("House edge", lambda p: ctk.CTkEntry(p, textvariable=self._edge_var, height=32))
        ctk.CTkLabel(self, text="Default 0.03 (3%). Lower = safer but slower.",
                      font=T.FONT_SMALL, text_color=T.TEXT_DIM).pack(
            anchor="w", padx=(164, 0), pady=(0, 4))

        # ── Betting Mode ─────────────────────────────────────────
        _section("🎯  Betting Mode")

        _label_to_name = {v: k for k, v in STRATEGY_LABELS.items()}
        _label_list    = [STRATEGY_LABELS[n] for n in STRATEGY_NAMES]

        def _on_strategy_change(label: str):
            name = _label_to_name.get(label, "all_in")
            # Update description label
            from core.strategies import STRATEGIES
            cls = STRATEGIES.get(name)
            _desc_lbl.configure(text=cls.DESCRIPTION if cls else "")
            # Show/hide sub-option frames
            is_all_in  = name == "all_in"
            is_percent = name == "fixed_percent"
            _base_row_frame.pack_forget() if is_all_in else _base_row_frame.pack(fill="x", pady=3)
            _pct_row_frame.pack(fill="x", pady=3) if is_percent else _pct_row_frame.pack_forget()
            _chance_row_frame.pack_forget() if is_all_in else _chance_row_frame.pack(fill="x", pady=3)

        _row("Strategy", lambda p: ctk.CTkOptionMenu(
            p, variable=self._strategy_var, height=32,
            values=_label_list,
            fg_color=T.BG3, button_color=T.BG3, button_hover_color=T.BG2,
            command=_on_strategy_change,
        ))

        _desc_lbl = ctk.CTkLabel(self, text="", font=T.FONT_SMALL,
                                  text_color=T.TEXT_DIM, wraplength=480, justify="left")
        _desc_lbl.pack(anchor="w", padx=(164, 0), pady=(0, 2))

        # Base bet (hidden for All-In)
        _base_row_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(_base_row_frame, text="Base bet", width=160, anchor="w",
                      font=T.FONT_BODY, text_color=T.TEXT).pack(side="left")
        ctk.CTkEntry(_base_row_frame, textvariable=self._base_bet_var,
                     height=32, width=120).pack(side="left")
        ctk.CTkLabel(_base_row_frame, text="Start amount (Martingale / D'Alembert / Fibonacci)",
                      font=T.FONT_SMALL, text_color=T.TEXT_DIM).pack(side="left", padx=(8, 0))

        # Bet percent (only for Fixed %)
        _pct_row_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(_pct_row_frame, text="Bet percent %", width=160, anchor="w",
                      font=T.FONT_BODY, text_color=T.TEXT).pack(side="left")
        ctk.CTkEntry(_pct_row_frame, textvariable=self._bet_percent_var,
                     height=32, width=80).pack(side="left")
        ctk.CTkLabel(_pct_row_frame, text="% of faucet balance per roll",
                      font=T.FONT_SMALL, text_color=T.TEXT_DIM).pack(side="left", padx=(8, 0))

        # Win-chance (hidden for All-In)
        _chance_row_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(_chance_row_frame, text="Win chance %", width=160, anchor="w",
                      font=T.FONT_BODY, text_color=T.TEXT).pack(side="left")
        ctk.CTkEntry(_chance_row_frame, textvariable=self._strat_chance_var,
                     height=32, width=80).pack(side="left")
        ctk.CTkLabel(_chance_row_frame, text="Fixed win probability (e.g. 49.5)",
                      font=T.FONT_SMALL, text_color=T.TEXT_DIM).pack(side="left", padx=(8, 0))

        # Apply initial visibility
        _on_strategy_change(self._strategy_var.get())

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
        self._save_btn = ctk.CTkButton(self, text="💾  Save Settings", height=38,
                       fg_color=T.ACCENT, hover_color=T.ACCENT2,
                       font=T.FONT_BODY, command=self._save)
        self._save_btn.pack(pady=4)

        # ── About & Updates ───────────────────────────────────────
        _section("ℹ️  About & Updates")
        from core.version import APP_NAME, APP_VERSION, GITHUB_RELEASES, CHANGELOG
        from core.updater import UpdateChecker as _UC

        about_card = ctk.CTkFrame(self, fg_color=T.BG2, corner_radius=T.CORNER_MD)
        about_card.pack(fill="x", pady=4)

        top_row = ctk.CTkFrame(about_card, fg_color="transparent")
        top_row.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(top_row, text=f"🎰  {APP_NAME}", font=T.FONT_H2,
                      text_color=T.ACCENT).pack(side="left")
        ctk.CTkLabel(top_row, text=f"v{APP_VERSION}", font=T.FONT_BODY,
                      text_color=T.TEXT_DIM).pack(side="left", padx=8)

        self._update_lbl = ctk.CTkLabel(about_card, text="", font=T.FONT_SMALL,
                                         text_color=T.TEXT_DIM)
        self._update_lbl.pack(anchor="w", padx=12)

        btn_row = ctk.CTkFrame(about_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=6)
        ctk.CTkButton(btn_row, text="🌐 GitHub Releases", width=140, height=30,
                       fg_color=T.BG3, font=T.FONT_SMALL,
                       command=lambda: __import__("webbrowser").open(GITHUB_RELEASES),
                       ).pack(side="left", padx=(0, 6))
        self._check_upd_btn = ctk.CTkButton(
            btn_row, text="🔍 Check for Updates", width=150, height=30,
            fg_color=T.BG3, font=T.FONT_SMALL,
            command=self._check_for_updates,
        )
        self._check_upd_btn.pack(side="left")

        # ── Feedback buttons ──────────────────────────────────────
        feedback_row = ctk.CTkFrame(about_card, fg_color="transparent")
        feedback_row.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkButton(feedback_row, text="🐛 Report Bug", width=130, height=30,
                       fg_color=T.RED, hover_color="#c0392b", font=T.FONT_SMALL,
                       command=lambda: self._open_feedback("bug"),
                       ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(feedback_row, text="💡 Feature Request", width=150, height=30,
                       fg_color=T.BG3, font=T.FONT_SMALL,
                       command=lambda: self._open_feedback("feature"),
                       ).pack(side="left")

        cl_box = ctk.CTkTextbox(about_card, height=90, fg_color=T.BG,
                                 font=T.FONT_MONO, state="normal")
        cl_box.insert("end", CHANGELOG)
        cl_box.configure(state="disabled")
        cl_box.pack(fill="x", padx=12, pady=(0, 10))

    def _check_for_updates(self):
        from core.updater import UpdateChecker
        from core.version import APP_VERSION
        self._check_upd_btn.configure(state="disabled", text="Checking…")
        def _done(info):
            self.after(0, lambda: self._on_upd_result(info))
        UpdateChecker().check_async(_done, APP_VERSION)

    def _on_upd_result(self, info):
        self._check_upd_btn.configure(state="normal", text="🔍 Check for Updates")
        if info is None:
            self._update_lbl.configure(
                text="✅ You're on the latest version.", text_color=T.GREEN)
        else:
            from core.updater import UpdateChecker as _UC
            self._update_lbl.configure(
                text=f"🆕 v{info.version} available!", text_color=T.GOLD)
            _UC.open_download_page(info.release_url)

    def _open_feedback(self, report_type: str):
        """Open the in-app feedback dialog (bug or feature)."""
        FeedbackDialog(self, report_type=report_type)

    # ── Cookie auto-detection ────────────────────────────────

    def _detect_cookie(self):
        """Try to read duckdice.io cookies from an installed Chrome/Firefox."""
        self._detect_btn.configure(state="disabled", text="Detecting…")
        threading.Thread(target=self._do_detect_cookie, daemon=True).start()

    def _do_detect_cookie(self):
        try:
            from core.cookie_extractor import extract_best
            cookie, source = extract_best("duckdice.io")
            if cookie:
                self.after(0, lambda: self._cookie_var.set(cookie))
                label = source.replace("_", " ").title()
                self.after(0, lambda: self._cookie_status_lbl.configure(
                    text=f"✅  Found in {label}", text_color=T.GREEN))
                self.after(4000, lambda: self._cookie_status_lbl.configure(text=""))
            else:
                self.after(0, lambda: self._cookie_status_lbl.configure(
                    text="No DuckDice session found in Chrome/Firefox.",
                    text_color=T.YELLOW))
                self.after(4000, lambda: self._cookie_status_lbl.configure(text=""))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._cookie_status_lbl.configure(
                text=f"Detection error: {err}", text_color=T.RED))
        finally:
            self.after(0, lambda: self._detect_btn.configure(
                state="normal", text="🔍 Detect from Chrome/Firefox"))

    def _capture_cookie(self):
        """Open a Playwright browser window and capture the cookie on login."""
        self._capture_btn.configure(state="disabled", text="Opening browser…")
        self._cookie_status_lbl.configure(
            text="Log in to DuckDice in the browser that opens…", text_color=T.ACCENT2)
        threading.Thread(target=self._do_capture_cookie, daemon=True).start()

    def _do_capture_cookie(self):
        import time as _time
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=False)
                context = browser.new_context()
                page    = context.new_page()
                page.goto("https://duckdice.io", wait_until="domcontentloaded",
                          timeout=15_000)
                cookie_str = None
                for _ in range(120):
                    cookies = context.cookies()
                    if any(c["name"] == "_session" for c in cookies):
                        cookie_str = "; ".join(
                            f"{c['name']}={c['value']}"
                            for c in cookies
                            if "duckdice" in c.get("domain", "")
                        )
                        # Persist browser state
                        try:
                            from core.browser_session import _DEFAULT_STATE
                            _DEFAULT_STATE.parent.mkdir(parents=True, exist_ok=True)
                            context.storage_state(path=str(_DEFAULT_STATE))
                        except Exception:
                            pass
                        break
                    _time.sleep(1)
                browser.close()
            if cookie_str:
                self.after(0, lambda: self._cookie_var.set(cookie_str))
                self.after(0, lambda: self._cookie_status_lbl.configure(
                    text="✅  Cookie captured & session saved!", text_color=T.GREEN))
                self.after(4000, lambda: self._cookie_status_lbl.configure(text=""))
            else:
                self.after(0, lambda: self._cookie_status_lbl.configure(
                    text="Timed out — log in within 2 minutes.", text_color=T.YELLOW))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._cookie_status_lbl.configure(
                text=f"Browser error: {err}", text_color=T.RED))
        finally:
            self.after(0, lambda: self._capture_btn.configure(
                state="normal", text="🤖 Open Browser & Capture"))

    # ── Test connection ────────────────────────────────────────

    def _test_connection(self):
        self._test_btn.configure(state="disabled", text="Testing…")
        threading.Thread(target=self._do_test_connection, daemon=True).start()

    def _do_test_connection(self):
        try:
            api = DuckDiceAPI(
                api_key=self._api_key_var.get().strip(),
                cookie=self._cookie_var.get().strip(),
            )
            paw = api.get_paw_level(force=True)
            self.after(0, lambda: self._status_lbl.configure(
                text=f"✅ Connected — PAW Level {paw}", text_color=T.GREEN))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._status_lbl.configure(
                text=f"❌ {err}", text_color=T.RED))
        finally:
            self.after(0, lambda: self._test_btn.configure(
                state="normal", text="🔍 Test Connection"))

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
        self._cfg.set("use_browser_session",   self._browser_session_var.get())

        # Strategy
        from core.strategies import STRATEGY_LABELS as _SL
        _label_to_name = {v: k for k, v in _SL.items()}
        self._cfg.set("strategy", _label_to_name.get(self._strategy_var.get(), "all_in"))
        try:
            self._cfg.set("strategy_base_bet",    float(self._base_bet_var.get() or "0.001"))
        except ValueError:
            pass
        try:
            self._cfg.set("strategy_bet_percent", float(self._bet_percent_var.get() or "1.0"))
        except ValueError:
            pass
        try:
            self._cfg.set("strategy_chance",      float(self._strat_chance_var.get() or "49.5"))
        except ValueError:
            pass
        try:
            jitter = max(0, int(self._jitter_var.get() or "5"))
        except ValueError:
            jitter = 5
            self._jitter_var.set("5")
        self._cfg.set("jitter_minutes", jitter)

        times = [t.get().strip() for t in self._time_vars if t.get().strip()]
        self._cfg.set("schedules", times)

        self._cfg.save()

        # Update scheduler live
        if self._sched_on_var.get() and times:
            self._sched.set_claim_times(times, jitter_minutes=jitter)

        # Auto-start registration
        if self._autostart_var.get():
            self._sched.register_autostart(sys.executable)

        self._status_lbl.configure(text="✅  Settings saved.", text_color=T.GREEN)
        self.after(3000, lambda: self._status_lbl.configure(text=""))
        self._dirty = False
        if self._save_btn:
            self._save_btn.configure(text="💾  Save Settings")
        if self._on_save:
            self._on_save()

    def _mark_dirty(self, *_) -> None:
        if not self._dirty:
            self._dirty = True
            if self._save_btn:
                self._save_btn.configure(text="💾  Save Settings ●")
