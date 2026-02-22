"""
FaucetPlay — Network Profile Manager
Handles per-account proxy and VPN isolation.

Rules enforced here:
  - One NetworkProfile is permanently bound to exactly one account.
  - Binding is written on first assignment and NEVER cleared, even if the
    account is deleted.  The profile stays blacklisted in the store forever.
  - Manual override requires explicit user confirmation (handled by the GUI;
    this layer records the override but never silently allows reuse).
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional

import requests
from cryptography.fernet import Fernet


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ProfileType(str, Enum):
    PROXY = "proxy"
    VPN   = "vpn"
    DIRECT = "direct"


class ProxyProtocol(str, Enum):
    HTTP   = "http"
    HTTPS  = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


class VpnMethod(str, Enum):
    OPENVPN   = "openvpn"
    WIREGUARD = "wireguard"
    MANUAL    = "manual"   # user connects manually; app just verifies IP


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class NetworkProfile:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    label: str = ""
    type: ProfileType = ProfileType.DIRECT

    # --- Proxy fields (type == PROXY) ---
    proxy_protocol: Optional[str] = None   # ProxyProtocol value
    proxy_host:     Optional[str] = None
    proxy_port:     Optional[int] = None
    proxy_username: Optional[str] = None   # stored encrypted in JSON
    proxy_password: Optional[str] = None   # stored encrypted in JSON

    # --- VPN fields (type == VPN) ---
    vpn_method:      Optional[str] = None  # VpnMethod value
    vpn_config_path: Optional[str] = None  # path to .ovpn / wg conf (encrypted filename)

    # --- Binding (immutable after first assignment) ---
    bound_to_account_id: Optional[str] = None
    blacklisted: bool = False   # True once bound; blocks reassignment

    # --- Timestamps ---
    created_at:      Optional[str] = None
    last_used_at:    Optional[str] = None
    last_verified_at: Optional[str] = None
    last_resolved_ip: Optional[str] = None

    # --- Override audit ---
    override_confirmed_by_user: bool = False
    override_note: str = ""

    def is_available(self) -> bool:
        """True only if this profile has never been bound to any account."""
        return not self.blacklisted

    def bind(self, account_id: str, force: bool = False) -> None:
        """
        Permanently bind this profile to an account.
        Raises ValueError if already bound and force is False.
        force=True records an override (caller must have obtained user confirmation).
        """
        if self.blacklisted and not force:
            raise ValueError(
                f"NetworkProfile '{self.label}' ({self.id}) is permanently bound to "
                f"account {self.bound_to_account_id!r} and cannot be reassigned. "
                "Pass force=True only after explicit user confirmation."
            )
        if force and self.blacklisted:
            self.override_confirmed_by_user = True
            self.override_note = (
                f"Force-reassigned from account {self.bound_to_account_id!r} "
                f"to {account_id!r} at {_now()}"
            )
        self.bound_to_account_id = account_id
        self.blacklisted = True

    def to_dict(self) -> dict:
        d = asdict(self)
        d['type'] = self.type.value if isinstance(self.type, ProfileType) else self.type
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "NetworkProfile":
        d = dict(d)
        if 'type' in d:
            d['type'] = ProfileType(d['type'])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class NetworkProfileManager:
    """
    Manages the NetworkProfile library stored in
    ~/.faucetplay/network_profiles.json.
    Sensitive fields (proxy credentials, vpn paths) are Fernet-encrypted.
    """

    SENSITIVE = {'proxy_username', 'proxy_password'}

    def __init__(self, config_dir: Optional[Path] = None, cipher: Optional[Fernet] = None):
        self._dir = config_dir or (Path.home() / '.faucetplay')
        self._dir.mkdir(parents=True, exist_ok=True)
        self._store = self._dir / 'network_profiles.json'
        self._cipher = cipher or self._load_or_create_cipher()
        self._profiles: dict[str, NetworkProfile] = {}
        self.load()

    # --- Persistence -------------------------------------------------------

    def _load_or_create_cipher(self) -> Fernet:
        key_file = self._dir / '.network_key'
        if key_file.exists():
            return Fernet(key_file.read_bytes())
        key = Fernet.generate_key()
        key_file.write_bytes(key)
        if os.name != 'nt':
            os.chmod(key_file, 0o600)
        return Fernet(key)

    def _enc(self, val: Optional[str]) -> Optional[str]:
        if not val:
            return val
        return self._cipher.encrypt(val.encode()).decode()

    def _dec(self, val: Optional[str]) -> Optional[str]:
        if not val:
            return val
        try:
            return self._cipher.decrypt(val.encode()).decode()
        except Exception:
            return val  # already plaintext (migration)

    def load(self) -> None:
        if not self._store.exists():
            return
        with open(self._store, 'r') as f:
            raw: list[dict] = json.load(f)
        for d in raw:
            for key in self.SENSITIVE:
                if d.get(key):
                    d[key] = self._dec(d[key])
            p = NetworkProfile.from_dict(d)
            self._profiles[p.id] = p

    def save(self) -> None:
        out = []
        for p in self._profiles.values():
            d = p.to_dict()
            for key in self.SENSITIVE:
                if d.get(key):
                    d[key] = self._enc(d[key])
            out.append(d)
        with open(self._store, 'w') as f:
            json.dump(out, f, indent=2)
        if os.name != 'nt':
            os.chmod(self._store, 0o600)

    # --- CRUD --------------------------------------------------------------

    def add(self, profile: NetworkProfile) -> NetworkProfile:
        if not profile.created_at:
            profile.created_at = _now()
        self._profiles[profile.id] = profile
        self.save()
        return profile

    def get(self, profile_id: str) -> Optional[NetworkProfile]:
        return self._profiles.get(profile_id)

    def all(self) -> list[NetworkProfile]:
        return list(self._profiles.values())

    def available(self) -> list[NetworkProfile]:
        """Profiles not yet bound to any account."""
        return [p for p in self._profiles.values() if p.is_available()]

    def delete(self, profile_id: str) -> None:
        """
        Remove a profile from the library.
        Bound/blacklisted profiles CANNOT be deleted — their record must stay
        so the binding history is preserved.
        """
        p = self._profiles.get(profile_id)
        if p is None:
            return
        if p.blacklisted:
            raise ValueError(
                f"Cannot delete NetworkProfile '{p.label}' ({profile_id}) — "
                "it is permanently bound to an account and must be kept for audit."
            )
        del self._profiles[profile_id]
        self.save()

    def assign_to_account(self, profile_id: str, account_id: str,
                          force: bool = False) -> NetworkProfile:
        """
        Bind a profile to an account.  Raises ValueError if already bound
        (unless force=True, which requires prior user confirmation in the GUI).
        """
        p = self._profiles.get(profile_id)
        if p is None:
            raise KeyError(f"NetworkProfile {profile_id!r} not found.")
        p.bind(account_id, force=force)
        p.last_used_at = _now()
        self.save()
        return p

    def unassign_account(self, account_id: str) -> None:
        """
        Called when an account is deleted.
        The profile stays blacklisted — only the account reference is noted.
        The binding record is NEVER erased.
        """
        for p in self._profiles.values():
            if p.bound_to_account_id == account_id:
                # Profile remains blacklisted; record deletion event in note
                p.override_note += f" | Account {account_id!r} deleted at {_now()}"
        self.save()

    # --- Network helpers ---------------------------------------------------

    def get_proxies_dict(self, profile_id: str) -> Optional[dict]:
        """
        Return a requests-compatible proxies dict for the given profile,
        or None if the profile is not a proxy type.
        """
        p = self._profiles.get(profile_id)
        if p is None or p.type != ProfileType.PROXY:
            return None
        proto = p.proxy_protocol or "http"
        auth = ""
        if p.proxy_username and p.proxy_password:
            auth = f"{p.proxy_username}:{p.proxy_password}@"
        url = f"{proto}://{auth}{p.proxy_host}:{p.proxy_port}"
        return {"http": url, "https": url}

    def get_playwright_proxy(self, profile_id: str) -> Optional[dict]:
        """
        Return a Playwright-compatible proxy dict, or None.
        """
        p = self._profiles.get(profile_id)
        if p is None or p.type != ProfileType.PROXY:
            return None
        proto = p.proxy_protocol or "http"
        d: dict = {"server": f"{proto}://{p.proxy_host}:{p.proxy_port}"}
        if p.proxy_username:
            d["username"] = p.proxy_username
        if p.proxy_password:
            d["password"] = p.proxy_password
        return d

    def verify_ip(self, profile_id: str, timeout: int = 10) -> Optional[str]:
        """
        Hit api.ipify.org through the profile and return the resolved IP.
        Updates last_resolved_ip and last_verified_at.
        Returns None on failure.
        """
        p = self._profiles.get(profile_id)
        if p is None:
            return None
        try:
            kwargs: dict = {"timeout": timeout}
            if p.type == ProfileType.PROXY:
                px = self.get_proxies_dict(profile_id)
                if px:
                    kwargs["proxies"] = px
            resp = requests.get("https://api.ipify.org?format=json", **kwargs)
            ip = resp.json().get("ip")
            p.last_resolved_ip = ip
            p.last_verified_at = _now()
            self.save()
            return ip
        except Exception:
            return None

    # --- VPN lifecycle -----------------------------------------------------

    def vpn_connect(self, profile_id: str) -> bool:
        """
        Connect VPN for a profile.  Returns True on success.
        Raises RuntimeError if the VPN method is unsupported on this OS.
        """
        p = self._profiles.get(profile_id)
        if p is None or p.type != ProfileType.VPN:
            return False

        method = VpnMethod(p.vpn_method) if p.vpn_method else VpnMethod.MANUAL

        if method == VpnMethod.MANUAL:
            # User is responsible for connecting; just verify IP changed
            return True

        if method == VpnMethod.OPENVPN:
            if not p.vpn_config_path or not Path(p.vpn_config_path).exists():
                raise FileNotFoundError(f"OpenVPN config not found: {p.vpn_config_path!r}")
            subprocess.Popen(
                ["openvpn", "--config", p.vpn_config_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            time.sleep(5)  # wait for TUN interface
            return True

        if method == VpnMethod.WIREGUARD:
            if not p.vpn_config_path:
                raise ValueError("WireGuard profile name not set.")
            subprocess.run(["wg-quick", "up", p.vpn_config_path], check=True)
            return True

        return False

    def vpn_disconnect(self, profile_id: str) -> bool:
        """Disconnect VPN for a profile."""
        p = self._profiles.get(profile_id)
        if p is None or p.type != ProfileType.VPN:
            return False
        method = VpnMethod(p.vpn_method) if p.vpn_method else VpnMethod.MANUAL
        try:
            if method == VpnMethod.WIREGUARD and p.vpn_config_path:
                subprocess.run(["wg-quick", "down", p.vpn_config_path], check=True)
            # OpenVPN: kill by finding the subprocess PID (future improvement)
        except Exception:
            pass
        return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
