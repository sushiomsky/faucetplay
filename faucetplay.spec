# -*- mode: python ; coding: utf-8 -*-
"""
FaucetPlay PyInstaller spec.
Produces a single-folder bundle (onedir) for fastest startup.
Run:  pyinstaller faucetplay.spec
"""

import sys
from pathlib import Path

block_cipher = None

# Collect customtkinter theme/image data
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ctk_datas    = collect_data_files("customtkinter")
ctk_hiddens  = collect_submodules("customtkinter")

a = Analysis(
    ["faucetplay_app.py"],
    pathex=["."],
    binaries=[],
    datas=ctk_datas + [
        ("assets", "assets"),
    ],
    hiddenimports=ctk_hiddens + [
        "cryptography",
        "cryptography.fernet",
        "cryptography.hazmat.primitives.kdf.pbkdf2",
        "cryptography.hazmat.backends.openssl",
        "playwright",
        "playwright.sync_api",
        "schedule",
        "tkinter",
        "tkinter.ttk",
        "_tkinter",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "scipy", "pandas", "PIL", "cv2"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FaucetPlay",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no terminal window on Windows/macOS
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # set to "assets/icon.ico" when icon is available
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FaucetPlay",
)

# macOS .app bundle
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="FaucetPlay.app",
        icon=None,           # set to "assets/icon.icns" when available
        bundle_identifier="io.faucetplay.app",
        info_plist={
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSHumanReadableCopyright": "© 2025 FaucetPlay",
        },
    )
