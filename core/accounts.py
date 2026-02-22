"""
FaucetPlay — Account Model & Manager
Each account maps 1:1 to a NetworkProfile (proxy, VPN, or direct).
All sensitive fields are Fernet-encrypted in accounts.json.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet

from .network import NetworkProfileManager


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class Account:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    label: str = "Account"

    # --- Credentials (stored encrypted) ---
    api_key: str = ""
    cookie:  str = ""
    fingerprint: str = ""

    # --- Network isolation ---
    # null  → direct connection (shown with ⚠️ warning in GUI)
    network_profile_id: Optional[str] = None

    # --- DuckDice state ---
    paw_level: int = 0               # 0-5; re-fetched each session
    preferred_currency: str = "USDC"

    # --- Bot config references ---
    strategy_profile: str = "all_in"
    scheduler_profile: str = ""      # id of saved schedule

    # --- Runtime flags ---
    active: bool = True
    auto_launch: bool = False        # include in system-startup auto-launch

    # --- Timestamps ---
    created_at:    Optional[str] = None
    last_run_at:   Optional[str] = None
    last_claim_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Account":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class AccountManager:
    """
    Manages all accounts stored in ~/.faucetplay/accounts.json.
    Sensitive fields (api_key, cookie, fingerprint) are Fernet-encrypted.
    Works together with NetworkProfileManager to enforce network isolation rules.
    """

    SENSITIVE = {'api_key', 'cookie', 'fingerprint'}

    def __init__(
        self,
        config_dir: Optional[Path] = None,
        cipher: Optional[Fernet] = None,
        network_mgr: Optional[NetworkProfileManager] = None,
    ):
        self._dir = config_dir or (Path.home() / '.faucetplay')
        self._dir.mkdir(parents=True, exist_ok=True)
        self._store = self._dir / 'accounts.json'
        self._cipher = cipher or self._load_or_create_cipher()
        self._network = network_mgr or NetworkProfileManager(config_dir=self._dir)
        self._accounts: dict[str, Account] = {}
        self.load()

    # --- Cipher ------------------------------------------------------------

    def _load_or_create_cipher(self) -> Fernet:
        key_file = self._dir / '.accounts_key'
        if key_file.exists():
            return Fernet(key_file.read_bytes())
        key = Fernet.generate_key()
        key_file.write_bytes(key)
        if os.name != 'nt':
            os.chmod(key_file, 0o600)
        return Fernet(key)

    def _enc(self, val: str) -> str:
        if not val:
            return val
        return self._cipher.encrypt(val.encode()).decode()

    def _dec(self, val: str) -> str:
        if not val:
            return val
        try:
            return self._cipher.decrypt(val.encode()).decode()
        except Exception:
            return val  # plaintext fallback for migration

    # --- Persistence -------------------------------------------------------

    def load(self) -> None:
        if not self._store.exists():
            return
        with open(self._store, 'r') as f:
            raw: list[dict] = json.load(f)
        for d in raw:
            for key in self.SENSITIVE:
                if d.get(key):
                    d[key] = self._dec(d[key])
            a = Account.from_dict(d)
            self._accounts[a.id] = a

    def save(self) -> None:
        out = []
        for a in self._accounts.values():
            d = a.to_dict()
            for key in self.SENSITIVE:
                if d.get(key):
                    d[key] = self._enc(d[key])
            out.append(d)
        with open(self._store, 'w') as f:
            json.dump(out, f, indent=2)
        if os.name != 'nt':
            os.chmod(self._store, 0o600)

    # --- CRUD --------------------------------------------------------------

    def add(self, account: Account) -> Account:
        if not account.created_at:
            account.created_at = _now()
        self._accounts[account.id] = account
        # Bind the network profile permanently if one is assigned
        if account.network_profile_id:
            self._bind_network(account.id, account.network_profile_id)
        self.save()
        return account

    def get(self, account_id: str) -> Optional[Account]:
        return self._accounts.get(account_id)

    def all(self) -> list[Account]:
        return list(self._accounts.values())

    def active_accounts(self) -> list[Account]:
        return [a for a in self._accounts.values() if a.active]

    def update(self, account: Account) -> None:
        existing = self._accounts.get(account.id)
        if existing and existing.network_profile_id != account.network_profile_id:
            # Network profile changed — bind new profile
            if account.network_profile_id:
                self._bind_network(account.id, account.network_profile_id)
        self._accounts[account.id] = account
        self.save()

    def delete(self, account_id: str) -> None:
        """
        Remove account from the store.
        The linked NetworkProfile stays blacklisted in the network store
        (binding history preserved forever per isolation rules).
        """
        account = self._accounts.get(account_id)
        if account and account.network_profile_id:
            # Record deletion in the network profile's audit note
            self._network.unassign_account(account_id)
        del self._accounts[account_id]
        self.save()

    def duplicate(self, account_id: str, new_label: str = "") -> Account:
        """
        Clone an account with a fresh id and NO network profile assigned.
        The user must assign a new (unbound) network profile to the clone.
        """
        src = self._accounts.get(account_id)
        if src is None:
            raise KeyError(f"Account {account_id!r} not found.")
        clone = Account.from_dict(src.to_dict())
        clone.id = str(uuid.uuid4())
        clone.label = new_label or f"{src.label} (copy)"
        clone.network_profile_id = None   # must be re-assigned to a fresh profile
        clone.created_at = _now()
        clone.last_run_at = None
        clone.last_claim_at = None
        self._accounts[clone.id] = clone
        self.save()
        return clone

    # --- Network profile binding -------------------------------------------

    def _bind_network(self, account_id: str, profile_id: str,
                      force: bool = False) -> None:
        try:
            self._network.assign_to_account(profile_id, account_id, force=force)
        except ValueError as e:
            raise ValueError(str(e)) from e

    def assign_network_profile(self, account_id: str, profile_id: str,
                               force: bool = False) -> None:
        """
        Assign (and permanently bind) a network profile to an account.
        Raises ValueError if the profile is already bound to another account
        and force=False.
        """
        account = self._accounts.get(account_id)
        if account is None:
            raise KeyError(f"Account {account_id!r} not found.")
        self._bind_network(account_id, profile_id, force=force)
        account.network_profile_id = profile_id
        self.save()

    # --- Import/Export -----------------------------------------------------

    def import_from_csv(self, csv_path: str) -> list[Account]:
        """
        Import accounts from a CSV file.
        Expected columns: label, api_key, cookie, currency, paw_level
        (network profiles must be assigned separately after import)
        """
        import csv
        added: list[Account] = []
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                a = Account(
                    label=row.get('label', 'Imported'),
                    api_key=row.get('api_key', ''),
                    cookie=row.get('cookie', ''),
                    preferred_currency=row.get('currency', 'USDC'),
                    paw_level=int(row.get('paw_level', 0)),
                )
                self.add(a)
                added.append(a)
        return added

    def export_to_csv(self, csv_path: str) -> None:
        """Export non-sensitive account data to CSV (no credentials)."""
        import csv
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'id', 'label', 'preferred_currency', 'paw_level',
                'strategy_profile', 'active', 'created_at', 'last_run_at'
            ])
            writer.writeheader()
            for a in self._accounts.values():
                writer.writerow({
                    'id': a.id,
                    'label': a.label,
                    'preferred_currency': a.preferred_currency,
                    'paw_level': a.paw_level,
                    'strategy_profile': a.strategy_profile,
                    'active': a.active,
                    'created_at': a.created_at,
                    'last_run_at': a.last_run_at,
                })


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
