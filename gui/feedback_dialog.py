"""
FaucetPlay — In-app feedback dialog.
Submits bug reports / feature requests directly to GitHub Issues via a
scoped bot token baked into the build.  No GitHub account required.
Falls back to pre-filled browser URL if token is unavailable (dev builds).
"""
from __future__ import annotations

import platform
import queue
import sys
import threading
import urllib.parse
import webbrowser
from typing import Optional

import customtkinter as ctk
import requests

from . import theme as T
from core.version import (
    APP_VERSION, GITHUB_OWNER, GITHUB_REPO,
    GITHUB_API_ISSUES, FEEDBACK_TOKEN,
)

_ISSUES_WEB    = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/issues/new"
_TOKEN_LIVE    = FEEDBACK_TOKEN not in ("", "@FEEDBACK_TOKEN@")

_BUG_BODY = """\
## Describe the bug
{description}

## Steps to reproduce
1.
2.
3.

## Expected behaviour
<!-- What you expected to happen -->

## Environment
- **App version:** v{version}
- **OS:** {os}
- **Python:** {python}

## Recent log output
```
{logs}
```
"""

_FEAT_BODY = """\
## Summary
{description}

## Motivation / use-case
<!-- Why would this be useful? -->

## Proposed solution
<!-- Any ideas on how to implement? -->

## Environment
- **App version:** v{version}
- **OS:** {os}
"""


class FeedbackDialog(ctk.CTkToplevel):
    """
    Modal dialog — submits directly to GitHub Issues API via embedded bot token.
    No GitHub account needed for the user.
    """

    def __init__(self, parent,
                 log_queue: Optional[queue.Queue] = None,
                 report_type: str = "bug",
                 **kw):
        super().__init__(parent, **kw)
        self._log_queue  = log_queue
        self._report_type = report_type

        title_str = "🐛 Report a Bug" if report_type == "bug" else "💡 Feature Request"
        self.title(title_str)
        self.geometry("500x530")
        self.resizable(False, False)
        self.configure(fg_color=T.BG)
        self.grab_set()
        self.lift()
        self.focus_force()

        self._build(title_str)

    # ── UI ──────────────────────────────────────────────────────────

    def _build(self, title_str: str):
        self._form_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._form_frame.pack(fill="both", expand=True)
        self._build_form(title_str)

    def _build_form(self, title_str: str):
        f = self._form_frame
        pad = {"padx": 20}

        ctk.CTkLabel(f, text=title_str, font=T.FONT_H2,
                     text_color=T.ACCENT).pack(anchor="w", pady=(18, 2), **pad)

        mode_txt = ("Submit directly — no GitHub account needed."
                    if _TOKEN_LIVE else
                    "Will open GitHub in your browser (dev build).")
        ctk.CTkLabel(f, text=mode_txt, font=T.FONT_SMALL,
                     text_color=T.TEXT_DIM).pack(anchor="w", pady=(0, 12), **pad)

        ctk.CTkLabel(f, text="Title *", font=T.FONT_BODY,
                     text_color=T.TEXT).pack(anchor="w", **pad)
        self._title_var = ctk.StringVar()
        ctk.CTkEntry(f, textvariable=self._title_var,
                     placeholder_text="Short summary…",
                     width=460, height=34,
                     fg_color=T.BG2, border_color=T.BG3).pack(pady=(2, 10), **pad)

        desc_lbl = ("What happened? Include steps to reproduce."
                    if self._report_type == "bug" else
                    "Describe the feature you'd like.")
        ctk.CTkLabel(f, text=desc_lbl, font=T.FONT_BODY,
                     text_color=T.TEXT).pack(anchor="w", **pad)
        self._desc_box = ctk.CTkTextbox(f, height=140, fg_color=T.BG2,
                                         border_color=T.BG3, border_width=1,
                                         font=T.FONT_MONO)
        self._desc_box.pack(fill="x", pady=(2, 10), **pad)

        info_frame = ctk.CTkFrame(f, fg_color=T.BG2, corner_radius=T.CORNER_SM)
        info_frame.pack(fill="x", pady=(0, 8), **pad)
        ctk.CTkLabel(info_frame, text=f"🖥  {self._sys_info()}",
                     font=T.FONT_SMALL, text_color=T.TEXT_DIM).pack(
            anchor="w", padx=10, pady=6)

        self._include_logs_var = ctk.BooleanVar(value=True)
        if self._report_type == "bug":
            ctk.CTkCheckBox(f, text="Include last 30 log lines (helps debugging)",
                            variable=self._include_logs_var,
                            font=T.FONT_SMALL,
                            fg_color=T.ACCENT, hover_color=T.BG3,
                            text_color=T.TEXT_DIM).pack(anchor="w", pady=(0, 6), **pad)

        self._status_lbl = ctk.CTkLabel(f, text="", font=T.FONT_SMALL,
                                         text_color=T.RED)
        self._status_lbl.pack(anchor="w", padx=20)

        btn_row = ctk.CTkFrame(f, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(8, 18))
        ctk.CTkButton(btn_row, text="Cancel", width=90, height=34,
                      fg_color=T.BG3, font=T.FONT_BODY,
                      command=self.destroy).pack(side="right", padx=(6, 0))
        submit_lbl = ("🚀 Send Report" if _TOKEN_LIVE else "🌐 Open on GitHub")
        self._submit_btn = ctk.CTkButton(
            btn_row, text=submit_lbl, width=160, height=34,
            fg_color=T.ACCENT, font=T.FONT_BODY,
            command=self._submit,
        )
        self._submit_btn.pack(side="right")

    def _show_success(self, issue_url: str):
        """Replace form with success screen."""
        for w in self._form_frame.winfo_children():
            w.destroy()

        f = self._form_frame
        ctk.CTkLabel(f, text="✅", font=("Segoe UI Emoji", 48)).pack(pady=(40, 8))
        ctk.CTkLabel(f, text="Report submitted — thank you!",
                     font=T.FONT_H2, text_color=T.GREEN).pack()
        ctk.CTkLabel(f, text="We'll look into it and follow up on GitHub.",
                     font=T.FONT_SMALL, text_color=T.TEXT_DIM).pack(pady=(4, 20))
        if issue_url:
            ctk.CTkButton(f, text="🔗 View on GitHub", width=160, height=34,
                           fg_color=T.BG3, font=T.FONT_BODY,
                           command=lambda: webbrowser.open(issue_url)).pack(pady=(0, 8))
        ctk.CTkButton(f, text="Close", width=100, height=34,
                       fg_color=T.ACCENT, font=T.FONT_BODY,
                       command=self.destroy).pack()

    # ── Helpers ─────────────────────────────────────────────────────

    def _sys_info(self) -> str:
        return (f"v{APP_VERSION} · "
                f"{platform.system()} {platform.release()} · "
                f"Python {sys.version.split()[0]}")

    def _collect_logs(self) -> str:
        if not self._log_queue:
            return "(no log queue attached)"
        lines: list[str] = []
        try:
            while True:
                lines.append(str(self._log_queue.get_nowait()))
        except Exception:
            pass
        for item in lines:
            try:
                self._log_queue.put_nowait(item)
            except Exception:
                pass
        return "\n".join(lines[-30:]) or "(empty)"

    def _build_body(self, description: str) -> str:
        os_info = f"{platform.system()} {platform.release()}"
        python_ver = sys.version.split()[0]
        if self._report_type == "bug":
            logs = self._collect_logs() if self._include_logs_var.get() else "(omitted)"
            return _BUG_BODY.format(
                description=description,
                version=APP_VERSION,
                os=os_info,
                python=python_ver,
                logs=logs,
            )
        return _FEAT_BODY.format(
            description=description,
            version=APP_VERSION,
            os=os_info,
        )

    # ── Submission ───────────────────────────────────────────────────

    def _submit(self):
        title = self._title_var.get().strip()
        if not title:
            self._status_lbl.configure(text="⚠️  Please enter a title.", text_color=T.RED)
            return

        self._submit_btn.configure(state="disabled", text="Sending…")
        self._status_lbl.configure(text="", text_color=T.RED)

        description = self._desc_box.get("1.0", "end").strip() or "*(no description)*"
        label = "bug" if self._report_type == "bug" else "enhancement"
        prefix = "[BUG] " if self._report_type == "bug" else "[FEATURE] "
        body = self._build_body(description)

        threading.Thread(
            target=self._do_submit,
            args=(prefix + title, body, label),
            daemon=True,
        ).start()

    def _do_submit(self, title: str, body: str, label: str):
        if _TOKEN_LIVE:
            self._submit_via_api(title, body, label)
        else:
            self._submit_via_browser(title, body, label)

    def _submit_via_api(self, title: str, body: str, label: str):
        try:
            resp = requests.post(
                GITHUB_API_ISSUES,
                json={"title": title, "body": body, "labels": [label]},
                headers={
                    "Authorization": f"token {FEEDBACK_TOKEN}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=15,
            )
            resp.raise_for_status()
            issue_url = resp.json().get("html_url", "")
            self.after(0, lambda: self._show_success(issue_url))
        except requests.exceptions.Timeout:
            self.after(0, lambda: self._on_api_error("Request timed out — please try again."))
        except requests.exceptions.ConnectionError:
            self.after(0, lambda: self._on_api_error("No internet connection."))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._on_api_error(f"Failed to submit: {err}"))

    def _submit_via_browser(self, title: str, body: str, label: str):
        """Dev-build fallback: open pre-filled GitHub issue in browser."""
        params = urllib.parse.urlencode({
            "title": title, "body": body, "labels": label,
        })
        webbrowser.open(f"{_ISSUES_WEB}?{params}")
        self.after(0, self.destroy)

    def _on_api_error(self, msg: str):
        self._submit_btn.configure(state="normal", text="🚀 Send Report")
        self._status_lbl.configure(text=f"❌  {msg}", text_color=T.RED)
