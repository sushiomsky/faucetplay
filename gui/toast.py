"""
FaucetPlay GUI — Toast Notification System
Stacked, auto-dismissing toasts in the bottom-right corner of the window.
"""
from __future__ import annotations

import tkinter as tk
from typing import Literal, Optional

import customtkinter as ctk

from . import theme as T

ToastKind = Literal["success", "error", "warning", "info", "update"]

_KIND_STYLE: dict[str, tuple[str, str]] = {
    "success": (T.GREEN,   "✅"),
    "error":   (T.RED,     "❌"),
    "warning": (T.YELLOW,  "⚠️"),
    "info":    (T.BLUE,    "ℹ️"),
    "update":  (T.ACCENT2, "🆕"),
}


class _Toast(ctk.CTkFrame):
    """A single toast card."""

    HEIGHT    = 60
    WIDTH     = 320
    FADE_STEP = 40   # ms between opacity steps

    def __init__(self, parent: tk.Misc, message: str, kind: ToastKind,
                 on_done: callable):
        colour, icon = _KIND_STYLE.get(kind, (T.BLUE, "ℹ️"))
        super().__init__(
            parent,
            fg_color=T.BG3,
            corner_radius=T.CORNER_MD,
            border_width=1,
            border_color=colour,
            width=self.WIDTH,
            height=self.HEIGHT,
        )
        self.grid_propagate(False)
        self._on_done = on_done
        self._alpha   = 1.0

        # Icon
        ctk.CTkLabel(self, text=icon, font=T.FONT_H2,
                     text_color=colour, width=32).pack(side="left", padx=(10, 4))
        # Message
        ctk.CTkLabel(self, text=message, font=T.FONT_SMALL,
                     text_color=T.TEXT, wraplength=240,
                     justify="left").pack(side="left", fill="both",
                                          expand=True, padx=(0, 8))
        # Close button
        ctk.CTkButton(self, text="×", width=20, height=20, font=T.FONT_H3,
                      fg_color="transparent", hover_color=T.BG,
                      text_color=T.TEXT_DIM,
                      command=self._dismiss).pack(side="right", padx=(0, 6))

    def _dismiss(self):
        self._on_done(self)
        self.destroy()

    def schedule_auto_dismiss(self, ms: int = 4000):
        self.after(ms, lambda: self._on_done(self) or self._fade())

    def _fade(self):
        if not self.winfo_exists():
            return
        try:
            self.destroy()
        except Exception:
            pass


class ToastManager:
    """
    Manages a stack of toasts anchored to the bottom-right of `root`.
    Usage:
        mgr = ToastManager(root)
        mgr.show("You won!", "success")
    """

    MARGIN_RIGHT  = 16
    MARGIN_BOTTOM = 16
    GAP           = 8

    def __init__(self, root: ctk.CTk):
        self._root   = root
        self._toasts: list[_Toast] = []

    def show(self, message: str, kind: ToastKind = "info",
             duration_ms: int = 4000) -> None:
        """Show a toast. Thread-safe (schedules on main loop via after)."""
        self._root.after(0, lambda: self._create(message, kind, duration_ms))

    def _create(self, message: str, kind: ToastKind, duration_ms: int) -> None:
        t = _Toast(self._root, message, kind, self._remove)
        t.place(x=0, y=0)          # placed properly in _restack
        self._toasts.append(t)
        t.lift()
        self._restack()
        t.schedule_auto_dismiss(duration_ms)

    def _remove(self, toast: _Toast) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
        self._restack()

    def _restack(self) -> None:
        """Re-position all toasts bottom-right, newest on top."""
        rw = self._root.winfo_width()
        rh = self._root.winfo_height()
        if rw < 10 or rh < 10:
            self._root.after(200, self._restack)
            return

        y = rh - self.MARGIN_BOTTOM
        for toast in reversed(self._toasts):
            if not toast.winfo_exists():
                continue
            h = _Toast.HEIGHT
            y -= h
            x = rw - _Toast.WIDTH - self.MARGIN_RIGHT
            toast.place(x=x, y=y)
            y -= self.GAP
