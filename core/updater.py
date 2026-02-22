"""
FaucetPlay — Auto-Update Checker
Checks GitHub Releases API for newer versions and can open the download
page or download the platform-appropriate asset.
"""
from __future__ import annotations

import logging
import platform
import re
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

import requests

from .version import APP_VERSION, GITHUB_API_LATEST, GITHUB_RELEASES

logger = logging.getLogger(__name__)


# ── Data classes ───────────────────────────────────────────────────────────

@dataclass
class ReleaseAsset:
    name: str
    download_url: str
    size_bytes: int


@dataclass
class UpdateInfo:
    version: str
    release_url: str
    release_notes: str
    assets: List[ReleaseAsset] = field(default_factory=list)

    @property
    def notes_preview(self) -> str:
        """First 300 chars of release notes, stripped."""
        return self.release_notes.strip()[:300]


# ── Version comparison ─────────────────────────────────────────────────────

def _parse_version(v: str) -> tuple[int, ...]:
    """Parse 'v1.2.3' or '1.2.3-beta' → (1, 2, 3)."""
    v = v.lstrip("v").split("-")[0]
    parts = re.split(r"[.\s]", v)
    try:
        return tuple(int(p) for p in parts if p.isdigit())
    except Exception:
        return (0,)


def is_newer(latest: str, current: str = APP_VERSION) -> bool:
    return _parse_version(latest) > _parse_version(current)


# ── Update checker ─────────────────────────────────────────────────────────

class UpdateChecker:
    """
    Non-blocking update checker.  Call `check_async(callback)` on startup.
    The callback is called on a background thread with UpdateInfo or None.
    """

    TIMEOUT = 8  # seconds for the GitHub API request

    def check_async(
        self,
        callback: Callable[[Optional[UpdateInfo]], None],
        current: str = APP_VERSION,
    ) -> None:
        """Spawn a daemon thread; call callback(UpdateInfo) or callback(None)."""
        t = threading.Thread(
            target=self._check, args=(callback, current), daemon=True
        )
        t.start()

    def _check(
        self,
        callback: Callable[[Optional[UpdateInfo]], None],
        current: str,
    ) -> None:
        try:
            resp = requests.get(
                GITHUB_API_LATEST,
                headers={"Accept": "application/vnd.github+json"},
                timeout=self.TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.debug("Update check failed: %s", e)
            callback(None)
            return

        tag = data.get("tag_name", "")
        if not tag or not is_newer(tag, current):
            callback(None)
            return

        assets = [
            ReleaseAsset(
                name=a["name"],
                download_url=a["browser_download_url"],
                size_bytes=a.get("size", 0),
            )
            for a in data.get("assets", [])
        ]

        info = UpdateInfo(
            version=tag.lstrip("v"),
            release_url=data.get("html_url", GITHUB_RELEASES),
            release_notes=data.get("body", ""),
            assets=assets,
        )
        logger.info("Update available: %s", info.version)
        callback(info)

    # ── Platform asset selection ───────────────────────────────────────────

    @staticmethod
    def best_asset(assets: List[ReleaseAsset]) -> Optional[ReleaseAsset]:
        """
        Pick the most appropriate asset for the current platform.
        Preference order (name suffix match):
          Windows : .exe, .zip
          macOS   : .dmg, .zip
          Linux   : .tar.gz, .AppImage, .zip
        """
        system = platform.system()
        if system == "Windows":
            prefs = [".exe", ".zip"]
        elif system == "Darwin":
            prefs = [".dmg", ".zip"]
        else:
            prefs = [".tar.gz", ".AppImage", ".zip"]

        for suffix in prefs:
            for a in assets:
                if a.name.lower().endswith(suffix):
                    return a
        return assets[0] if assets else None

    # ── Download helper ────────────────────────────────────────────────────

    @staticmethod
    def download_asset(
        asset: ReleaseAsset,
        dest_dir: Optional[Path] = None,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """
        Download `asset` to `dest_dir` (defaults to temp dir).
        `progress_cb(downloaded_bytes, total_bytes)` is called during download.
        Returns the path to the downloaded file.
        """
        dest_dir = dest_dir or Path(tempfile.gettempdir())
        dest = dest_dir / asset.name
        resp = requests.get(asset.download_url, stream=True, timeout=60)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total)
        return dest

    # ── Apply update (open installer / file manager) ───────────────────────

    @staticmethod
    def open_download_page(release_url: str) -> None:
        """Open the GitHub release page in the default browser."""
        import webbrowser
        webbrowser.open(release_url)

    @staticmethod
    def open_downloaded_file(path: Path) -> None:
        """
        Open the downloaded file with the OS default handler
        (e.g., Finder on macOS, Explorer on Windows, xdg-open on Linux).
        """
        system = platform.system()
        try:
            if system == "Windows":
                subprocess.Popen(["explorer", "/select,", str(path)])
            elif system == "Darwin":
                subprocess.Popen(["open", "-R", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path.parent)])
        except Exception as e:
            logger.warning("Could not open file manager: %s", e)
