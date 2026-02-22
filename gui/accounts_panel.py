"""
FaucetPlay GUI — Accounts Panel
Left-sidebar list of accounts + Add/Edit/Delete/Duplicate dialogs.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from typing import Callable, Optional
import customtkinter as ctk
from . import theme as T
from core.accounts import Account, AccountManager
from core.network import NetworkProfileManager, ProfileType, ProxyProtocol, VpnMethod, NetworkProfile


PAW_EMOJI = ["🐾⁰","🐾¹","🐾²","🐾³","🐾⁴","🐾⁵"]
NET_BADGE  = {ProfileType.PROXY: "🔒", ProfileType.VPN: "🛡", ProfileType.DIRECT: "⚠️", None: "⚠️"}
STATUS_ICONS = {
    "running":   ("🟢", T.STATUS_RUNNING),
    "paused":    ("⏸", T.STATUS_PAUSED),
    "scheduled": ("⏰", T.STATUS_SCHEDULED),
    "error":     ("🔴", T.STATUS_ERROR),
    "idle":      ("💤", T.STATUS_IDLE),
}


class AccountsPanel(ctk.CTkFrame):
    """
    Sidebar panel listing all accounts.
    Calls `on_select(account_id)` when user selects an account.
    """

    def __init__(self, parent, account_mgr: AccountManager,
                 network_mgr: NetworkProfileManager,
                 on_select: Callable[[str], None], **kw):
        super().__init__(parent, fg_color=T.BG2, width=T.SIDEBAR_W, **kw)
        self._amgr = account_mgr
        self._nmgr = network_mgr
        self._on_select = on_select
        self._status: dict[str, str] = {}   # account_id → status key
        self._selected: Optional[str] = None
        self._build()

    # ---------------------------------------------------------------
    def _build(self):
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)

        # Header
        hdr = ctk.CTkFrame(self, fg_color=T.BG3)
        hdr.grid(row=0, column=0, sticky="ew", padx=0, pady=(0,1))
        ctk.CTkLabel(hdr, text="ACCOUNTS", font=T.FONT_H3,
                     text_color=T.ACCENT).pack(side="left", padx=10, pady=8)
        ctk.CTkButton(hdr, text="+", width=28, height=28,
                      fg_color=T.ACCENT, hover_color=T.BG3,
                      command=self._add_account).pack(side="right", padx=6, pady=6)

        # Scrollable list
        self._list_frame = ctk.CTkScrollableFrame(self, fg_color=T.BG2)
        self._list_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self.grid_rowconfigure(1, weight=1)

        # Bottom toolbar
        bar = ctk.CTkFrame(self, fg_color=T.BG3, height=36)
        bar.grid(row=2, column=0, sticky="ew")
        for text, cmd in [("✏️", self._edit_account), ("🗑", self._delete_account),
                          ("📋", self._duplicate_account), ("📥", self._import_csv)]:
            ctk.CTkButton(bar, text=text, width=34, height=28,
                          fg_color="transparent", hover_color=T.BG2,
                          command=cmd).pack(side="left", padx=2, pady=4)

        self.refresh()

    # ---------------------------------------------------------------
    def refresh(self):
        """Rebuild the account list from AccountManager."""
        for w in self._list_frame.winfo_children():
            w.destroy()

        for acct in self._amgr.all():
            self._add_row(acct)

    def set_status(self, account_id: str, status: str):
        """Update runtime status badge (running/paused/scheduled/error/idle)."""
        self._status[account_id] = status
        self.refresh()

    # ---------------------------------------------------------------
    def _add_row(self, acct: Account):
        status = self._status.get(acct.id, "idle")
        icon, colour = STATUS_ICONS.get(status, ("💤", T.STATUS_IDLE))
        paw  = PAW_EMOJI[min(acct.paw_level, 5)]

        # Network badge
        profile = self._nmgr.get(acct.network_profile_id) if acct.network_profile_id else None
        net_icon = NET_BADGE.get(profile.type if profile else None, "⚠️")

        is_selected = acct.id == self._selected
        bg = T.BG3 if is_selected else T.BG2
        hover = T.BG3

        row = ctk.CTkFrame(self._list_frame, fg_color=bg, corner_radius=6)
        row.pack(fill="x", padx=4, pady=2)
        row.bind("<Button-1>", lambda e, aid=acct.id: self._select(aid))

        # Status dot + label
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        left.bind("<Button-1>", lambda e, aid=acct.id: self._select(aid))

        ctk.CTkLabel(left, text=f"{icon} {acct.label}",
                     font=T.FONT_BODY, text_color=colour,
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(left, text=f"  {paw}  {net_icon}  {acct.preferred_currency}",
                     font=T.FONT_SMALL, text_color=T.TEXT_DIM,
                     anchor="w").pack(fill="x")

    def _select(self, account_id: str):
        self._selected = account_id
        self.refresh()
        self._on_select(account_id)

    # ---------------------------------------------------------------
    def _selected_account(self) -> Optional[Account]:
        if not self._selected:
            messagebox.showwarning("No selection", "Select an account first.")
            return None
        return self._amgr.get(self._selected)

    # ---------------------------------------------------------------
    def _add_account(self):
        dlg = AccountDialog(self, self._nmgr, title="Add Account")
        self.wait_window(dlg)
        if dlg.result:
            self._amgr.add(dlg.result)
            self.refresh()

    def _edit_account(self):
        acct = self._selected_account()
        if not acct:
            return
        dlg = AccountDialog(self, self._nmgr, title="Edit Account", account=acct)
        self.wait_window(dlg)
        if dlg.result:
            self._amgr.update(dlg.result)
            self.refresh()

    def _delete_account(self):
        acct = self._selected_account()
        if not acct:
            return
        if messagebox.askyesno(
            "Delete account",
            f"Delete '{acct.label}'?\n\n"
            "Its network profile stays blacklisted and cannot be reused."
        ):
            self._amgr.delete(acct.id)
            self._selected = None
            self.refresh()

    def _duplicate_account(self):
        acct = self._selected_account()
        if not acct:
            return
        name = simpledialog.askstring("Duplicate", "Label for the new account:",
                                      initialvalue=f"{acct.label} (copy)")
        if name:
            clone = self._amgr.duplicate(acct.id, new_label=name)
            messagebox.showinfo("Duplicated",
                f"'{clone.label}' created.\n\n"
                "Assign a fresh network profile before running it.")
            self.refresh()

    def _import_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if path:
            added = self._amgr.import_from_csv(path)
            messagebox.showinfo("Import", f"Imported {len(added)} account(s).")
            self.refresh()


# -----------------------------------------------------------------------
# Account Add/Edit dialog
# -----------------------------------------------------------------------

class AccountDialog(ctk.CTkToplevel):
    def __init__(self, parent, network_mgr: NetworkProfileManager,
                 title: str = "Account", account: Optional[Account] = None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.configure(fg_color=T.BG)
        self._nmgr = network_mgr
        self._src  = account
        self.result: Optional[Account] = None
        self._build()
        self.grab_set()

    def _build(self):
        pad = dict(padx=14, pady=6)
        f = ctk.CTkFrame(self, fg_color=T.BG)
        f.pack(fill="both", expand=True, padx=16, pady=12)

        def row(lbl, widget_factory, var=None):
            ctk.CTkLabel(f, text=lbl, font=T.FONT_BODY,
                         text_color=T.TEXT_DIM, anchor="w").pack(fill="x", **pad)
            w = widget_factory(f)
            w.pack(fill="x", **pad)
            return w

        a = self._src or Account()

        self._label  = row("Label",    lambda p: ctk.CTkEntry(p, placeholder_text="My Account"))
        self._apikey = row("API Key",  lambda p: ctk.CTkEntry(p, show="•"))
        self._cookie = row("Cookie",   lambda p: ctk.CTkEntry(p, show="•"))
        self._fp     = row("Fingerprint (optional)", lambda p: ctk.CTkEntry(p))
        self._curr   = row("Currency", lambda p: ctk.CTkEntry(p, placeholder_text="USDC"))

        # Network profile selector
        ctk.CTkLabel(f, text="Network Profile", font=T.FONT_BODY,
                     text_color=T.TEXT_DIM, anchor="w").pack(fill="x", **pad)
        profiles = self._nmgr.available()
        choices  = ["⚠️  Direct (no proxy/VPN)"] + [
            f"{NET_BADGE.get(p.type, '?')} {p.label}" for p in profiles
        ]
        self._profile_ids = [None] + [p.id for p in profiles]
        self._net_var = ctk.StringVar(value=choices[0])
        self._net_dd  = ctk.CTkOptionMenu(f, values=choices, variable=self._net_var,
                                          fg_color=T.BG2)
        self._net_dd.pack(fill="x", **pad)

        # Prefill
        self._label.insert(0,  a.label)
        self._apikey.insert(0, a.api_key)
        self._cookie.insert(0, a.cookie)
        self._fp.insert(0,     a.fingerprint)
        self._curr.insert(0,   a.preferred_currency)

        # Buttons
        bf = ctk.CTkFrame(f, fg_color="transparent")
        bf.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(bf, text="Save", fg_color=T.ACCENT,
                      command=self._save).pack(side="right", padx=4)
        ctk.CTkButton(bf, text="Cancel", fg_color=T.BG3,
                      command=self.destroy).pack(side="right")

    def _save(self):
        a = self._src or Account()
        a.label              = self._label.get().strip() or "Account"
        a.api_key            = self._apikey.get().strip()
        a.cookie             = self._cookie.get().strip()
        a.fingerprint        = self._fp.get().strip()
        a.preferred_currency = self._curr.get().strip().upper() or "USDC"

        idx = 0
        chosen = self._net_var.get()
        for i, p in enumerate(self._nmgr.available()):
            if p.label in chosen:
                idx = i + 1
                break
        profile_id = self._profile_ids[idx] if idx < len(self._profile_ids) else None
        a.network_profile_id = profile_id

        if not a.api_key:
            messagebox.showwarning("Missing", "API Key is required.")
            return
        self.result = a
        self.destroy()
