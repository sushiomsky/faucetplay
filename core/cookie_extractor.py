"""
FaucetPlay — Cookie Extractor

Extracts duckdice.io session cookies from installed browsers without
requiring the user to open DevTools or copy anything manually.

Strategies (tried in order by extract_best()):
  1. browser_cookie3   — reads Chrome / Firefox OS cookie store
                         (handles macOS Keychain / Windows DPAPI decryption)
  2. Direct SQLite     — reads Chrome's cookie DB directly on Linux
                         (Chrome on Linux stores cookies unencrypted)
  3. Firefox SQLite    — direct SQLite read of Firefox's cookies.sqlite

Usage
─────
    from core.cookie_extractor import extract_best
    cookie, source = extract_best("duckdice.io")
    # cookie: "name=value; name2=value2" or ""
    # source: "chrome", "firefox", "chrome_sqlite", "firefox_sqlite", or ""
"""

from __future__ import annotations

import logging
import platform
import sqlite3
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

DOMAIN = "duckdice.io"


# ─────────────────────────────────────────────────────────────────
# Strategy 1: browser_cookie3 (optional dependency)
# ─────────────────────────────────────────────────────────────────

def _via_browser_cookie3(domain: str = DOMAIN) -> Tuple[str, str]:
    """Try to extract cookies via browser_cookie3 library."""
    try:
        import browser_cookie3  # type: ignore
    except ImportError:
        logger.warning("browser_cookie3 not installed — cannot auto-extract cookies")
        return "", ""

    for name, fn in [("chrome", browser_cookie3.chrome),
                     ("firefox", browser_cookie3.firefox)]:
        try:
            logger.debug("Attempting cookie extraction from %s...", name)
            jar = fn(domain_name=domain)
            cookies = [f"{c.name}={c.value}" for c in jar]
            if cookies:
                logger.info("cookie_extractor: got %d cookies from %s via browser_cookie3",
                            len(cookies), name)
                return "; ".join(cookies), name
            else:
                logger.debug("No cookies found in %s for domain %s", name, domain)
        except PermissionError as exc:
            # macOS Keychain access denied or Windows DPAPI issue
            if platform.system() == "Darwin":
                logger.warning(
                    "browser_cookie3 %s — permission denied. "
                    "On macOS, you may need to grant Keychain access. "
                    "Try closing %s completely and running again, or grant access when prompted.",
                    name, name.title()
                )
            else:
                logger.warning("browser_cookie3 %s — permission denied: %s", name, exc)
        except Exception as exc:
            exc_str = str(exc).lower()
            if "keychain" in exc_str or "password" in exc_str:
                logger.warning(
                    "browser_cookie3 %s — macOS Keychain access issue. "
                    "Please grant access when prompted, or close %s and try again.",
                    name, name.title()
                )
            else:
                logger.debug("browser_cookie3 %s failed: %s", name, exc)

    return "", ""


# ─────────────────────────────────────────────────────────────────
# Strategy 2: Chrome SQLite (Linux — cookies stored unencrypted)
# ─────────────────────────────────────────────────────────────────

def _chrome_cookie_paths() -> List[Path]:
    system = platform.system()
    if system == "Linux":
        candidates = [
            Path.home() / ".config/google-chrome/Default/Cookies",
            Path.home() / ".config/chromium/Default/Cookies",
            Path.home() / ".config/google-chrome/Profile 1/Cookies",
        ]
    elif system == "Darwin":
        base = Path.home() / "Library/Application Support"
        candidates = [
            base / "Google/Chrome/Default/Cookies",
            base / "Chromium/Default/Cookies",
        ]
    elif system == "Windows":
        import os
        base = Path(os.environ.get("LOCALAPPDATA", ""))
        candidates = [
            base / "Google/Chrome/User Data/Default/Cookies",
            base / "Google/Chrome/User Data/Default/Network/Cookies",
        ]
    else:
        candidates = []
    return [p for p in candidates if p.exists()]


def _read_sqlite_cookies(db_path: Path, domain: str) -> List[str]:
    """Read cookies from a Chrome/Firefox SQLite database (copy to avoid lock)."""
    cookies = []
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        shutil.copy2(db_path, tmp_path)
        with sqlite3.connect(str(tmp_path)) as conn:
            # Chrome schema
            try:
                rows = conn.execute(
                    "SELECT name, value, encrypted_value FROM cookies "
                    "WHERE host_key LIKE ?",
                    (f"%{domain}%",),
                ).fetchall()
                for name, value, enc in rows:
                    # Use plaintext value if available; skip encrypted ones
                    if value:
                        cookies.append(f"{name}={value}")
                    # encrypted_value: only decodable on Linux without OS encryption
                    elif enc and platform.system() == "Linux":
                        try:
                            # Chrome on Linux uses a fixed key or "peanuts" password
                            decrypted = _decrypt_chrome_linux(enc)
                            if decrypted:
                                cookies.append(f"{name}={decrypted}")
                        except Exception:
                            pass
            except sqlite3.OperationalError:
                pass
    finally:
        tmp_path.unlink(missing_ok=True)
    return cookies


def _decrypt_chrome_linux(encrypted: bytes) -> str:
    """Decrypt Chrome v10 cookies on Linux using the fixed 'peanuts' key."""
    # Chrome Linux v10 format: b"v10" + AES-128-CBC ciphertext
    if not encrypted or not encrypted.startswith(b"v10"):
        return encrypted.decode("utf-8", errors="ignore") if encrypted else ""
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        import os

        password = b"peanuts"
        salt = b"saltysalt"
        kdf = PBKDF2HMAC(algorithm=hashes.SHA1(), length=16, salt=salt, iterations=1)
        key = kdf.derive(password)

        iv = b" " * 16   # Chrome uses 16 spaces as IV on Linux
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        dec = cipher.decryptor()
        decrypted = dec.update(encrypted[3:]) + dec.finalize()
        # Remove PKCS7 padding
        pad = decrypted[-1]
        return decrypted[:-pad].decode("utf-8", errors="ignore")
    except Exception as exc:
        logger.debug("Chrome Linux decrypt failed: %s", exc)
        return ""


def _via_chrome_sqlite(domain: str = DOMAIN) -> Tuple[str, str]:
    paths = _chrome_cookie_paths()
    if not paths:
        logger.debug("No Chrome cookie paths found for this OS")
        return "", ""
    
    for path in paths:
        try:
            if not path.exists():
                logger.debug("Chrome cookie path does not exist: %s", path)
                continue
            cookies = _read_sqlite_cookies(path, domain)
            if cookies:
                logger.info("cookie_extractor: got %d cookies from Chrome SQLite (%s)",
                            len(cookies), path)
                return "; ".join(cookies), "chrome_sqlite"
        except PermissionError as exc:
            logger.debug("Chrome SQLite %s — permission denied (browser may be running): %s", path, exc)
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower():
                logger.debug("Chrome SQLite %s — database locked (browser may be running)", path)
            else:
                logger.debug("Chrome SQLite %s — database error: %s", path, exc)
        except Exception as exc:
            logger.debug("Chrome SQLite %s — unexpected error: %s", path, exc)
    return "", ""


# ─────────────────────────────────────────────────────────────────
# Strategy 3: Firefox SQLite
# ─────────────────────────────────────────────────────────────────

def _firefox_cookie_paths() -> List[Path]:
    system = platform.system()
    if system == "Linux":
        base = Path.home() / ".mozilla/firefox"
    elif system == "Darwin":
        base = Path.home() / "Library/Application Support/Firefox/Profiles"
    elif system == "Windows":
        import os
        base = Path(os.environ.get("APPDATA", "")) / "Mozilla/Firefox/Profiles"
    else:
        return []
    return list(base.glob("*/cookies.sqlite")) if base.exists() else []


def _via_firefox_sqlite(domain: str = DOMAIN) -> Tuple[str, str]:
    paths = _firefox_cookie_paths()
    if not paths:
        logger.debug("No Firefox cookie paths found")
        return "", ""
    
    for path in paths:
        try:
            if not path.exists():
                logger.debug("Firefox cookie path does not exist: %s", path)
                continue
            cookies = []
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                shutil.copy2(path, tmp_path)
                with sqlite3.connect(str(tmp_path)) as conn:
                    rows = conn.execute(
                        "SELECT name, value FROM moz_cookies WHERE host LIKE ?",
                        (f"%{domain}%",),
                    ).fetchall()
                    cookies = [f"{n}={v}" for n, v in rows if v]
            finally:
                tmp_path.unlink(missing_ok=True)
            if cookies:
                logger.info("cookie_extractor: got %d cookies from Firefox (%s)",
                            len(cookies), path)
                return "; ".join(cookies), "firefox_sqlite"
        except PermissionError as exc:
            logger.debug("Firefox SQLite %s — permission denied (browser may be running): %s", path, exc)
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower():
                logger.debug("Firefox SQLite %s — database locked (browser may be running)", path)
            else:
                logger.debug("Firefox SQLite %s — database error: %s", path, exc)
        except Exception as exc:
            logger.debug("Firefox SQLite %s — unexpected error: %s", path, exc)
    return "", ""


# ─────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────

def extract_best(domain: str = DOMAIN) -> Tuple[str, str]:
    """
    Try all extraction strategies and return the first successful result.

    Returns
    -------
    (cookie_string, source)
        cookie_string : "name=value; name2=value2" or ""
        source        : "chrome" | "firefox" | "chrome_sqlite" |
                        "firefox_sqlite" | ""
    """
    strategies = [
        ("browser_cookie3", _via_browser_cookie3),
        ("chrome_sqlite", _via_chrome_sqlite),
        ("firefox_sqlite", _via_firefox_sqlite),
    ]
    
    for strategy_name, fn in strategies:
        try:
            cookie, source = fn(domain)
            if cookie:
                logger.info("extract_best: successfully extracted cookies via %s", strategy_name)
                return cookie, source
        except Exception as exc:
            logger.warning("extract_best: strategy %s raised: %s", strategy_name, exc)
    
    # No cookies found — provide platform-specific guidance
    system = platform.system()
    if system == "Darwin":
        logger.warning(
            "cookie_extractor: no cookies found in any installed browser. "
            "On macOS, try: (1) Grant Keychain access when prompted, "
            "(2) Close Chrome/Firefox completely and try again, "
            "(3) Use the 'Open Browser & Capture' button instead."
        )
    elif system == "Windows":
        logger.warning(
            "cookie_extractor: no cookies found in any installed browser. "
            "On Windows, try: (1) Close Chrome/Firefox completely and try again, "
            "(2) Use the 'Open Browser & Capture' button instead."
        )
    else:
        logger.warning(
            "cookie_extractor: no cookies found in any installed browser. "
            "Try closing Chrome/Firefox and trying again, or paste cookie manually."
        )
    return "", ""


def has_browser_cookie3() -> bool:
    """Return True if browser_cookie3 is installed."""
    try:
        import browser_cookie3  # noqa: F401
        return True
    except ImportError:
        return False
