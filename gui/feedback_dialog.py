"""
FaucetPlay — In-app feedback dialog.
Collects bug reports / feature requests and opens a pre-filled GitHub issue.
No auth required — uses browser URL with template query params.
"""
from __future__ import annotations

import platform
import queue
import sys
import urllib.parse
import webbrowser
from typing import Optional

import customtkinter as ctk

from . import theme as T
from core.version import APP_VERSION, GITHUB_OWNER, GITHUB_REPO

_ISSUES_BASE = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/issues/new"

# Pre-built body templates (mirrors .github/ISSUE_TEMPLATE/)
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
    """Modal dialog for bug reports and feature requests."""

    def __init__(self, parent,
                 log_queue: Optional[queue.Queue] = None,
                 report_type: str = "bug",   # "bug" | "feature"
                 **kw):
        super().__init__(parent, **kw)
        self._log_queue = log_queue
        self._report_type = report_type

        title_str = "🐛 Report a Bug" if report_type == "bug" else "💡 Request a Feature"
        self.title(title_str)
        self.geometry("520x560")
        self.resizable(False, False)
        self.configure(fg_color=T.BG)
        self.grab_set()
        self.lift()

        self._build(title_str)

    # ── UI ──────────────────────────────────────────────────────────

    def _build(self, title_str: str):
        pad = {"padx": 20}

        # Header
        ctk.CTkLabel(self, text=title_str, font=T.FONT_H2,
                     text_color=T.ACCENT).pack(anchor="w", pady=(18, 4), **pad)
        ctk.CTkLabel(
            self,
            text="Your report opens on GitHub — add any extra detail there.",
            font=T.FONT_SMALL, text_color=T.TEXT_DIM,
            wraplength=480, justify="left",
        ).pack(anchor="w", pady=(0, 12), **pad)

        # Title
        ctk.CTkLabel(self, text="Title *", font=T.FONT_BODY,
                     text_color=T.TEXT).pack(anchor="w", **pad)
        self._title_var = ctk.StringVar()
        ctk.CTkEntry(self, textvariable=self._title_var,
                     placeholder_text="Short summary…",
                     width=480, height=34,
                     fg_color=T.BG2, border_color=T.BG3).pack(pady=(2, 10), **pad)

        # Description
        desc_label = ("What happened? (include steps to reproduce)" if self._report_type == "bug"
                      else "Describe the feature you'd like")
        ctk.CTkLabel(self, text=desc_label, font=T.FONT_BODY,
                     text_color=T.TEXT).pack(anchor="w", **pad)
        self._desc_box = ctk.CTkTextbox(self, height=130, fg_color=T.BG2,
                                         border_color=T.BG3, border_width=1,
                                         font=T.FONT_MONO)
        self._desc_box.pack(fill="x", pady=(2, 10), **pad)

        # System info preview (collapsed)
        info_frame = ctk.CTkFrame(self, fg_color=T.BG2, corner_radius=T.CORNER_SM)
        info_frame.pack(fill="x", pady=(0, 12), **pad)
        ctk.CTkLabel(info_frame,
                     text=f"🖥  {self._sys_info()}",
                     font=T.FONT_SMALL, text_color=T.TEXT_DIM).pack(
            anchor="w", padx=10, pady=6)

        # Log snippet toggle (bug only)
        self._include_logs_var = ctk.BooleanVar(value=True)
        if self._report_type == "bug":
            ctk.CTkCheckBox(self, text="Include last 30 log lines",
                            variable=self._include_logs_var,
                            font=T.FONT_SMALL,
                            fg_color=T.ACCENT, hover_color=T.BG3,
                            text_color=T.TEXT_DIM).pack(anchor="w", pady=(0, 12), **pad)

        # Status label
        self._status_lbl = ctk.CTkLabel(self, text="", font=T.FONT_SMALL,
                                         text_color=T.RED)
        self._status_lbl.pack(anchor="w", **pad)

        # Buttons
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(4, 18))
        ctk.CTkButton(btn_row, text="Cancel", width=100, height=34,
                      fg_color=T.BG3, font=T.FONT_BODY,
                      command=self.destroy).pack(side="right", padx=(6, 0))
        action_lbl = "🐛 Open Bug Report" if self._report_type == "bug" else "💡 Open Feature Request"
        ctk.CTkButton(btn_row, text=action_lbl, width=180, height=34,
                      fg_color=T.ACCENT, font=T.FONT_BODY,
                      command=self._submit).pack(side="right")

    # ── Helpers ─────────────────────────────────────────────────────

    def _sys_info(self) -> str:
        return (f"v{APP_VERSION} · "
                f"{platform.system()} {platform.release()} · "
                f"Python {sys.version.split()[0]}")

    def _collect_logs(self) -> str:
        if not self._log_queue:
            return "(no log queue attached)"
        lines: list[str] = []
        # Drain queue snapshot without blocking
        try:
            tmp: list = []
            while True:
                item = self._log_queue.get_nowait()
                tmp.append(item)
        except Exception:
            pass
        # Put items back
        for item in tmp:
            try:
                self._log_queue.put_nowait(item)
            except Exception:
                pass
        # Return last 30 lines from tmp
        return "\n".join(str(x) for x in tmp[-30:]) or "(empty)"

    def _submit(self):
        title = self._title_var.get().strip()
        if not title:
            self._status_lbl.configure(text="⚠️  Please enter a title.")
            return

        description = self._desc_box.get("1.0", "end").strip() or "*(no description provided)*"
        os_info = f"{platform.system()} {platform.release()}"
        python_ver = sys.version.split()[0]

        if self._report_type == "bug":
            logs = self._collect_logs() if self._include_logs_var.get() else "(omitted by user)"
            body = _BUG_BODY.format(
                description=description,
                version=APP_VERSION,
                os=os_info,
                python=python_ver,
                logs=logs,
            )
            label_param = "bug"
            title_prefix = "[BUG] "
        else:
            body = _FEAT_BODY.format(
                description=description,
                version=APP_VERSION,
                os=os_info,
            )
            label_param = "enhancement"
            title_prefix = "[FEATURE] "

        params = urllib.parse.urlencode({
            "title": title_prefix + title,
            "body": body,
            "labels": label_param,
        })
        url = f"{_ISSUES_BASE}?{params}"
        webbrowser.open(url)
        self.destroy()
