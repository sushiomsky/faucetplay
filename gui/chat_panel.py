"""
FaucetPlay GUI — Auto-Chat Panel

UX-first design:
  • Prominent status card (disabled / dry-run / live) with countdown
  • Interval fields with human-readable hints (e.g. "2m 00s")
  • Rest-period rows with inline HH:MM validation
  • Message list with live search, count badge, bulk enable/disable,
    per-row toggle & delete, Enter-to-add, auto-scroll to new row
  • Activity mini-log showing the last 30 sent / dry-run messages
  • "Send Now" button to force an immediate message
  • Sticky save bar always visible (no scrolling to reach it)
"""
from __future__ import annotations

import re
import tkinter as tk
from typing import Callable, List, Optional

import customtkinter as ctk

from . import theme as T
from core.chat_bot import ChatBot
from core.chat_db import ChatMessageDB
from core.config import BotConfig

_HM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _fmt_secs(s: int) -> str:
    """120 → '2m 00s', 45 → '45s'"""
    if s <= 0:
        return "—"
    m, sec = divmod(int(s), 60)
    return f"{m}m {sec:02d}s" if m else f"{sec}s"


def _validate_hm(text: str) -> bool:
    return bool(_HM_RE.match(text.strip()))


# ═══════════════════════════════════════════════════════════════════════════


class ChatPanel(ctk.CTkFrame):
    """
    Auto-Chat tab.  Uses a two-pane layout:
      left  — sticky settings sidebar (status card, interval, rest periods, save)
      right — message manager + activity log
    Both panes scroll independently via CTkScrollableFrame.
    """

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
        self._bot      = chat_bot
        self._on_save  = on_save

        # ── State vars ────────────────────────────────────────────
        self._enabled_var = tk.BooleanVar(value=bool(config.get("chat_enabled",   False)))
        self._dry_var     = tk.BooleanVar(value=bool(config.get("chat_dry_run",    True)))
        self._min_var     = tk.StringVar(value=str(config.get("chat_interval_min", 120)))
        self._max_var     = tk.StringVar(value=str(config.get("chat_interval_max", 600)))

        self._rest_rows: List[dict]  = []
        self._msg_rows:  List[dict]  = []
        self._filter_var = tk.StringVar()
        self._new_msg_var = tk.StringVar()

        # Watch for unsaved changes
        self._dirty = False
        for v in (self._enabled_var, self._dry_var, self._min_var, self._max_var):
            v.trace_add("write", self._mark_dirty)

        self._build()
        self._load_rest_periods()
        self._load_messages()
        self._poll()

    # ── Top-level layout ──────────────────────────────────────────────────

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=0, minsize=300)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left pane — settings (scrollable)
        self._left = ctk.CTkScrollableFrame(self, fg_color=T.BG, width=300)
        self._left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        # Right pane — messages + activity (scrollable)
        self._right = ctk.CTkScrollableFrame(self, fg_color=T.BG)
        self._right.grid(row=0, column=1, sticky="nsew")

        self._build_left()
        self._build_right()

    # ── Left pane ─────────────────────────────────────────────────────────

    def _build_left(self) -> None:
        L = self._left

        # ── Status card ───────────────────────────────────────────
        self._status_card = ctk.CTkFrame(L, fg_color=T.BG3, corner_radius=T.CORNER_MD)
        self._status_card.pack(fill="x", pady=(8, 0))

        self._mode_lbl = ctk.CTkLabel(
            self._status_card, text="", font=T.FONT_H3,
            text_color=T.TEXT_DIM,
        )
        self._mode_lbl.pack(pady=(10, 2))

        self._countdown_lbl = ctk.CTkLabel(
            self._status_card, text="", font=T.FONT_SMALL, text_color=T.TEXT_DIM,
        )
        self._countdown_lbl.pack(pady=(0, 4))

        self._error_lbl = ctk.CTkLabel(
            self._status_card, text="", font=T.FONT_SMALL,
            text_color=T.RED, wraplength=270,
        )
        self._error_lbl.pack(padx=10, pady=(0, 6))

        # Send Now button
        self._send_now_btn = ctk.CTkButton(
            self._status_card, text="⚡ Send Now", height=28,
            fg_color=T.BG2, hover_color=T.ACCENT, font=T.FONT_SMALL,
            command=self._send_now,
        )
        self._send_now_btn.pack(pady=(0, 10))

        # ── Enable / Dry-run toggles ─────────────────────────────
        _sec(L, "⚙️  Chat Settings")

        self._enabled_sw = ctk.CTkSwitch(
            L, text="Enable auto-chat",
            variable=self._enabled_var,
            font=T.FONT_BODY, text_color=T.TEXT,
            progress_color=T.GREEN,
            command=self._update_status_card,
        )
        self._enabled_sw.pack(anchor="w", padx=8, pady=(6, 2))

        self._dry_sw = ctk.CTkSwitch(
            L, text="Dry run  (log only)",
            variable=self._dry_var,
            font=T.FONT_BODY, text_color=T.YELLOW,
            progress_color=T.YELLOW,
            command=self._update_status_card,
        )
        self._dry_sw.pack(anchor="w", padx=8, pady=(2, 2))

        ctk.CTkLabel(
            L,
            text="When dry run is ON messages are only logged — nothing is sent to chat.",
            font=T.FONT_SMALL, text_color=T.TEXT_DIM,
            wraplength=270, justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 8))

        # ── Interval ─────────────────────────────────────────────
        _sec(L, "⏱  Interval")

        for label, var, hint_attr in [
            ("Min (seconds)", self._min_var, "_min_hint"),
            ("Max (seconds)", self._max_var, "_max_hint"),
        ]:
            row = ctk.CTkFrame(L, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=3)
            ctk.CTkLabel(row, text=label, width=100, anchor="w",
                          font=T.FONT_SMALL, text_color=T.TEXT).pack(side="left")
            ent = ctk.CTkEntry(row, textvariable=var, width=70, height=30)
            ent.pack(side="left", padx=(4, 6))
            hint = ctk.CTkLabel(row, text="", font=T.FONT_SMALL,
                                 text_color=T.TEXT_DIM, width=80)
            hint.pack(side="left")
            setattr(self, hint_attr, hint)

        self._interval_err = ctk.CTkLabel(
            L, text="", font=T.FONT_SMALL, text_color=T.RED, wraplength=270
        )
        self._interval_err.pack(anchor="w", padx=10)

        # Live-update interval hints as user types
        self._min_var.trace_add("write", lambda *_: self._update_interval_hints())
        self._max_var.trace_add("write", lambda *_: self._update_interval_hints())
        self._update_interval_hints()

        # ── Rest periods ─────────────────────────────────────────
        _sec(L, "🌙  Rest Periods")

        ctk.CTkLabel(
            L,
            text="No messages during these windows.\nOvernight ranges (e.g. 23:00–06:00) work too.",
            font=T.FONT_SMALL, text_color=T.TEXT_DIM,
            wraplength=270, justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 4))

        self._rest_container = ctk.CTkFrame(L, fg_color="transparent")
        self._rest_container.pack(fill="x")

        ctk.CTkButton(
            L, text="＋  Add window", height=28,
            fg_color=T.BG3, hover_color=T.BG2, font=T.FONT_SMALL,
            command=self._add_rest_row,
        ).pack(anchor="w", padx=8, pady=(4, 12))

        # ── Save bar ──────────────────────────────────────────────
        save_frame = ctk.CTkFrame(L, fg_color=T.BG2, corner_radius=T.CORNER_MD)
        save_frame.pack(fill="x", pady=(8, 12))

        self._save_btn = ctk.CTkButton(
            save_frame, text="💾  Save Settings", height=36,
            fg_color=T.ACCENT, hover_color=T.ACCENT2, font=T.FONT_BODY,
            command=self._save,
        )
        self._save_btn.pack(fill="x", padx=8, pady=(8, 4))

        self._save_status = ctk.CTkLabel(
            save_frame, text="", font=T.FONT_SMALL, text_color=T.GREEN
        )
        self._save_status.pack(pady=(0, 8))

        self._update_status_card()

    # ── Right pane ────────────────────────────────────────────────────────

    def _build_right(self) -> None:
        R = self._right

        # ── Message manager ───────────────────────────────────────
        _sec(R, "📝  Messages")

        # Count + bulk buttons row
        top_row = ctk.CTkFrame(R, fg_color="transparent")
        top_row.pack(fill="x", pady=(4, 2))

        self._count_lbl = ctk.CTkLabel(
            top_row, text="", font=T.FONT_SMALL, text_color=T.TEXT_DIM
        )
        self._count_lbl.pack(side="left", padx=(4, 0))

        for label, cmd in [("Enable all", self._enable_all), ("Disable all", self._disable_all)]:
            ctk.CTkButton(
                top_row, text=label, height=26, width=90,
                fg_color=T.BG3, hover_color=T.BG2, font=T.FONT_SMALL,
                command=cmd,
            ).pack(side="right", padx=(4, 0))

        # Search filter
        filter_row = ctk.CTkFrame(R, fg_color="transparent")
        filter_row.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(filter_row, text="🔍", font=T.FONT_BODY,
                      text_color=T.TEXT_DIM).pack(side="left", padx=(4, 2))
        filter_ent = ctk.CTkEntry(
            filter_row, textvariable=self._filter_var,
            placeholder_text="Filter messages…", height=30,
        )
        filter_ent.pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(
            filter_row, text="✕", width=28, height=28,
            fg_color="transparent", hover_color=T.BG3, font=T.FONT_SMALL,
            command=lambda: self._filter_var.set(""),
        ).pack(side="left")
        self._filter_var.trace_add("write", lambda *_: self._apply_filter())

        # Add-new row
        add_row = ctk.CTkFrame(R, fg_color="transparent")
        add_row.pack(fill="x", pady=(0, 4))
        self._new_entry = ctk.CTkEntry(
            add_row, textvariable=self._new_msg_var,
            placeholder_text="Type a new message and press Enter or Add…", height=32,
        )
        self._new_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._new_entry.bind("<Return>", lambda _: self._add_message())
        ctk.CTkButton(
            add_row, text="Add", height=32, width=70,
            fg_color=T.ACCENT, hover_color=T.ACCENT2, font=T.FONT_SMALL,
            command=self._add_message,
        ).pack(side="left")

        self._add_status = ctk.CTkLabel(R, text="", font=T.FONT_SMALL,
                                         text_color=T.TEXT_DIM)
        self._add_status.pack(anchor="w", padx=4)

        # Message list container
        self._msg_container = ctk.CTkFrame(R, fg_color=T.BG2, corner_radius=T.CORNER_MD)
        self._msg_container.pack(fill="x", pady=(0, 8))

        # Empty-state label (shown when filter has no matches)
        self._empty_lbl = ctk.CTkLabel(
            self._msg_container, text="No messages match your filter.",
            font=T.FONT_SMALL, text_color=T.TEXT_DIM,
        )

        # ── Activity mini-log ─────────────────────────────────────
        _sec(R, "📡  Recent Activity")

        self._activity_box = ctk.CTkTextbox(
            R, height=180, fg_color=T.BG2,
            font=T.FONT_MONO, state="disabled",
            corner_radius=T.CORNER_MD,
        )
        self._activity_box.pack(fill="x", pady=(0, 8))

    # ── Rest period rows ──────────────────────────────────────────────────

    def _load_rest_periods(self) -> None:
        for p in (self._cfg.get("chat_rest_periods", []) or []):
            self._add_rest_row(p.get("start", "22:00"), p.get("end", "07:00"))

    def _add_rest_row(self, start: str = "22:00", end: str = "07:00") -> None:
        row = ctk.CTkFrame(self._rest_container, fg_color=T.BG2,
                            corner_radius=T.CORNER_SM)
        row.pack(fill="x", pady=2, padx=4)

        sv = tk.StringVar(value=start)
        ev = tk.StringVar(value=end)

        ctk.CTkLabel(row, text="From", font=T.FONT_SMALL,
                      text_color=T.TEXT_DIM, width=34).pack(side="left", padx=(6, 2))
        se = ctk.CTkEntry(row, textvariable=sv, width=68, height=28)
        se.pack(side="left", padx=(0, 6))
        ctk.CTkLabel(row, text="To", font=T.FONT_SMALL,
                      text_color=T.TEXT_DIM, width=18).pack(side="left")
        ee = ctk.CTkEntry(row, textvariable=ev, width=68, height=28)
        ee.pack(side="left", padx=(2, 4))

        err_lbl = ctk.CTkLabel(row, text="", font=T.FONT_SMALL, text_color=T.RED, width=60)
        err_lbl.pack(side="left")

        def _validate_entry(*_):
            s_ok = not sv.get() or _validate_hm(sv.get())
            e_ok = not ev.get() or _validate_hm(ev.get())
            err_lbl.configure(text="" if (s_ok and e_ok) else "⚠ HH:MM")
        sv.trace_add("write", _validate_entry)
        ev.trace_add("write", _validate_entry)

        entry = {"start": sv, "end": ev, "frame": row}
        self._rest_rows.append(entry)

        def _remove():
            self._rest_rows.remove(entry)
            row.destroy()
            self._mark_dirty()

        ctk.CTkButton(
            row, text="✕", width=26, height=26,
            fg_color="transparent", hover_color=T.RED, font=T.FONT_SMALL,
            command=_remove,
        ).pack(side="right", padx=4)
        self._mark_dirty()

    # ── Message list ──────────────────────────────────────────────────────

    def _load_messages(self) -> None:
        for r in self._msg_rows:
            r["frame"].destroy()
        self._msg_rows.clear()
        for row in self._db.get_all():
            self._add_msg_row(row["id"], row["text"], bool(row["enabled"]))
        self._update_count()

    def _add_msg_row(self, row_id: int, text: str, enabled: bool) -> None:
        frame = ctk.CTkFrame(self._msg_container, fg_color="transparent")
        frame.pack(fill="x", padx=6, pady=1)

        enabled_var = tk.BooleanVar(value=enabled)
        text_colour = T.TEXT if enabled else T.TEXT_DIM

        lbl = ctk.CTkLabel(
            frame, text=text, font=T.FONT_SMALL,
            text_color=text_colour, anchor="w",
        )

        def _on_toggle():
            self._db.set_enabled(row_id, enabled_var.get())
            lbl.configure(text_color=T.TEXT if enabled_var.get() else T.TEXT_DIM)
            self._update_count()

        cb = ctk.CTkCheckBox(
            frame, text="", variable=enabled_var,
            command=_on_toggle, width=22, height=22,
        )
        cb.pack(side="left", padx=(2, 4))
        lbl.pack(side="left", fill="x", expand=True)

        entry = {"id": row_id, "text": text.lower(), "frame": frame,
                  "enabled_var": enabled_var}
        self._msg_rows.append(entry)

        def _remove():
            self._db.remove(row_id)
            self._msg_rows.remove(entry)
            frame.destroy()
            self._update_count()
            self._apply_filter()

        ctk.CTkButton(
            frame, text="✕", width=22, height=22,
            fg_color="transparent", hover_color=T.RED, font=T.FONT_SMALL,
            command=_remove,
        ).pack(side="right", padx=2)

    def _add_message(self) -> None:
        text = self._new_msg_var.get().strip()
        if not text:
            return
        new_id = self._db.add(text)
        if new_id is None:
            self._flash(self._add_status, "Already exists.", T.YELLOW)
            return
        self._add_msg_row(new_id, text, True)
        self._new_msg_var.set("")
        self._new_entry.focus()
        self._apply_filter()
        self._update_count()
        # Scroll to bottom so newly added row is visible
        self._right._parent_canvas.yview_moveto(1.0)
        self._flash(self._add_status, "✅ Added.", T.GREEN)

    def _apply_filter(self) -> None:
        q = self._filter_var.get().lower().strip()
        visible = 0
        for entry in self._msg_rows:
            show = not q or q in entry["text"]
            if show:
                entry["frame"].pack(fill="x", padx=6, pady=1)
                visible += 1
            else:
                entry["frame"].pack_forget()
        # Show / hide empty-state label
        if visible == 0 and self._msg_rows:
            self._empty_lbl.pack(pady=10)
        else:
            self._empty_lbl.pack_forget()
        self._update_count(visible)

    def _enable_all(self) -> None:
        for entry in self._msg_rows:
            entry["enabled_var"].set(True)
            self._db.set_enabled(entry["id"], True)
            # update label colour
            for widget in entry["frame"].winfo_children():
                if isinstance(widget, ctk.CTkLabel):
                    widget.configure(text_color=T.TEXT)
        self._update_count()

    def _disable_all(self) -> None:
        for entry in self._msg_rows:
            entry["enabled_var"].set(False)
            self._db.set_enabled(entry["id"], False)
            for widget in entry["frame"].winfo_children():
                if isinstance(widget, ctk.CTkLabel):
                    widget.configure(text_color=T.TEXT_DIM)
        self._update_count()

    def _update_count(self, visible: Optional[int] = None) -> None:
        total   = len(self._msg_rows)
        enabled = sum(1 for r in self._msg_rows if r["enabled_var"].get())
        if visible is None:
            visible = sum(1 for r in self._msg_rows if r["frame"].winfo_ismapped())
        if visible < total:
            text = f"{total} messages · {enabled} enabled · {visible} shown"
        else:
            text = f"{total} messages · {enabled} enabled"
        self._count_lbl.configure(text=text)

    # ── Save ──────────────────────────────────────────────────────────────

    def _save(self) -> None:
        # Validate intervals
        try:
            imin = int(self._min_var.get())
            imax = int(self._max_var.get())
            if imin < 10:
                raise ValueError("Minimum must be ≥ 10 seconds")
            if imax <= imin:
                raise ValueError("Maximum must be greater than Minimum")
        except ValueError as exc:
            self._interval_err.configure(text=f"⚠ {exc}")
            return
        self._interval_err.configure(text="")

        # Validate rest periods
        rest: list = []
        for row in self._rest_rows:
            s, e = row["start"].get().strip(), row["end"].get().strip()
            if not s and not e:
                continue
            if not _validate_hm(s) or not _validate_hm(e):
                self._flash(self._save_status, "⚠ Fix rest periods (HH:MM format)", T.RED)
                return
            rest.append({"start": s, "end": e})

        self._cfg.set("chat_enabled",      self._enabled_var.get())
        self._cfg.set("chat_dry_run",       self._dry_var.get())
        self._cfg.set("chat_interval_min",  imin)
        self._cfg.set("chat_interval_max",  imax)
        self._cfg.set("chat_rest_periods",  rest)
        self._cfg.save()

        self._dirty = False
        self._save_btn.configure(text="💾  Save Settings")
        self._flash(self._save_status, "✅  Saved.", T.GREEN)
        if self._on_save:
            self._on_save()

    # ── Polling (live updates) ────────────────────────────────────────────

    def _poll(self) -> None:
        self._update_status_card()
        self._update_interval_hints()
        self._update_activity_log()
        self.after(1000, self._poll)

    def _update_status_card(self) -> None:
        enabled = self._enabled_var.get()
        dry_run = self._dry_var.get()

        if not enabled:
            colour, icon, label = T.TEXT_DIM, "○", "Auto-chat disabled"
        elif dry_run:
            colour, icon, label = T.YELLOW, "🔇", "DRY RUN — nothing sent"
        else:
            colour, icon, label = T.RED, "🔴", "LIVE — messages will be sent"

        self._mode_lbl.configure(
            text=f"{icon}  {label}", text_color=colour
        )
        self._status_card.configure(border_width=2 if (enabled and not dry_run) else 0,
                                     border_color=T.RED)

        # Countdown
        if self._bot and self._bot.is_running() and enabled:
            nxt = self._bot.next_send_in
            if nxt > 0:
                self._countdown_lbl.configure(
                    text=f"⏳  Next in {_fmt_secs(nxt)}", text_color=T.TEXT_DIM
                )
            else:
                self._countdown_lbl.configure(
                    text="⚡ Sending soon…", text_color=T.ACCENT2
                )
        else:
            self._countdown_lbl.configure(text="")

        # Error
        if self._bot and self._bot.last_error:
            self._error_lbl.configure(text=f"⚠ {self._bot.last_error}")
        else:
            self._error_lbl.configure(text="")

        # Send-now button state
        can_send = self._bot is not None and self._bot.is_running() and enabled
        self._send_now_btn.configure(state="normal" if can_send else "disabled")

    def _update_interval_hints(self) -> None:
        for var, attr in [(self._min_var, "_min_hint"), (self._max_var, "_max_hint")]:
            try:
                getattr(self, attr).configure(text=_fmt_secs(int(var.get())))
            except (ValueError, AttributeError):
                try:
                    getattr(self, attr).configure(text="⚠ not a number")
                except AttributeError:
                    pass

    def _update_activity_log(self) -> None:
        if not self._bot:
            return
        log = list(self._bot.recent_log)
        if not log:
            return
        lines = []
        for ts, msg, dry in reversed(log):
            prefix = "🔇" if dry else "💬"
            lines.append(f"{ts}  {prefix}  {msg}")
        content = "\n".join(lines)
        self._activity_box.configure(state="normal")
        self._activity_box.delete("0.0", "end")
        self._activity_box.insert("end", content)
        self._activity_box.configure(state="disabled")

    # ── Helpers ───────────────────────────────────────────────────────────

    def _send_now(self) -> None:
        if self._bot:
            self._bot.send_now()
            self._flash(self._save_status, "⚡ Sent immediately!", T.ACCENT2)

    def _mark_dirty(self, *_) -> None:
        self._dirty = True
        self._save_btn.configure(text="💾  Save Settings ●")

    def _flash(self, lbl: ctk.CTkLabel, text: str, colour: str = T.GREEN) -> None:
        lbl.configure(text=text, text_color=colour)
        self.after(4000, lambda: lbl.configure(text="") if lbl.winfo_exists() else None)


# ── Helper ────────────────────────────────────────────────────────────────

def _sec(parent, text: str) -> None:
    f = ctk.CTkFrame(parent, fg_color=T.BG3, height=30, corner_radius=6)
    f.pack(fill="x", pady=(12, 4))
    f.pack_propagate(False)
    ctk.CTkLabel(f, text=text, font=T.FONT_H3,
                  text_color=T.ACCENT2).pack(side="left", padx=10)
