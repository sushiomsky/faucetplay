<div align="center">

# 🎰 FaucetPlay

### Farm DuckDice faucets on autopilot

[![Release](https://img.shields.io/github/v/release/faucetplay/faucetplay?color=e94560&label=latest)](https://github.com/faucetplay/faucetplay/releases/latest)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](#install)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Stop leaving faucet money on the table.**  
FaucetPlay claims your DuckDice faucets, bets them up to your target, cashes out, and repeats — while you do literally anything else.

[📥 Download](#install) · [🚀 Quick Start](#quick-start) · [❓ FAQ](#faq) · [📋 Changelog](#changelog)

</div>

---

## ✨ Features

| | |
|---|---|
| 🎯 **Smart faucet claiming** | Auto-detects your PAW level and plays exactly the required Tic-Tac-Toe games to unlock each claim |
| 📈 **Target-based betting** | Set a profit target; FaucetPlay bets up to it using the Martingale-inspired adaptive strategy |
| 💰 **Auto cashout** | Hits target → transfers to your main balance → keeps farming the same target again |
| �� **Cooldown-aware** | Cashout on cooldown? It pauses betting and resumes the moment the window opens |
| ⏰ **Daily scheduler** | Set up to 3 claim times per day (with jitter) — perfect for set-and-forget passive income |
| 🚀 **System auto-start** | Register FaucetPlay to launch minimized at login on Windows, macOS, and Linux |
| 🔒 **Encrypted credentials** | Your API key and session cookie are stored with Fernet AES encryption, never in plaintext |
| 🆕 **Auto-update notifications** | Checks GitHub releases on startup and shows a banner when a new version is available |
| 📊 **Live dashboard** | Balance cards, win/loss counters, progress bar, real-time log with filter and copy |
| 🎨 **Dark UI** | Polished CustomTkinter interface — dark mode only, as it should be |

---

## 📥 Install

### Option A — Download pre-built binary (recommended)

Go to [**Releases**](https://github.com/faucetplay/faucetplay/releases/latest) and grab the package for your OS:

| OS | File |
|---|---|
| Windows 10/11 | `FaucetPlay-vX.X.X-windows.zip` |
| macOS 12+ | `FaucetPlay-vX.X.X-macos.dmg` |
| Linux (x64) | `FaucetPlay-vX.X.X-linux.tar.gz` |

Unzip and run `FaucetPlay` — no Python needed.

### Option B — Run from source

```bash
# Requires Python 3.11+
git clone https://github.com/faucetplay/faucetplay.git
cd faucetplay
pip install -r requirements.txt
playwright install chromium
python faucetplay_app.py
```

---

## 🚀 Quick Start

1. **Launch** FaucetPlay — the setup wizard opens automatically on first run.
2. **Enter your DuckDice API key** (Settings → API on DuckDice).
3. **Enter your session cookie** — open DuckDice in Chrome → DevTools (F12) → Application → Cookies → copy the `_session` value.
4. **Set your currency and target** (e.g., USDC, 20.0).
5. Click **▶ Start Farming** and watch the balance grow.

> **Tip:** PAW levels 0–2 require Tic-Tac-Toe games before each faucet claim. FaucetPlay handles all of this automatically using a headless browser — no action needed from you.

---

## ⚙️ Settings Reference

| Setting | Description |
|---|---|
| **API Key** | Your DuckDice API key |
| **Session Cookie** | Your `_session` cookie value for browser automation |
| **Currency** | Which coin to farm (USDC, BTC, ETH, LTC, …) |
| **Target Amount** | Faucet balance that triggers a cashout |
| **House Edge** | Dice bet edge (default 3% — lower = slightly safer) |
| **Auto Cashout** | Automatically transfer to main balance on target hit |
| **Continue After Cashout** | Keep farming the same target after each cashout |
| **Claim Times** | Up to 3 HH:MM daily claim times |
| **Jitter** | Random ±N minutes around each claim time (avoids patterns) |
| **System Auto-Start** | Launch FaucetPlay minimized at login |

---

## ❓ FAQ

**Does this work with all PAW levels?**  
Yes. Levels 0–2 require Tic-Tac-Toe (5 / 4 / 3 games respectively). FaucetPlay detects your level and plays automatically.

**Is my account safe?**  
FaucetPlay behaves like a normal browser session. Credentials are stored encrypted on your device. That said, bot usage is against DuckDice's ToS — use at your own discretion and risk.

**Why does the bot sometimes pause?**  
DuckDice enforces cashout cooldowns (usually 1 hour). When FaucetPlay hits its target and a cooldown is active, it pauses betting until the window opens, then cashes out and resumes.

**Can I run it headlessly / on a server?**  
Yes: `python faucetplay_app.py --no-gui`. Pair with the scheduler for fully automated daily claiming.

**Will it update itself automatically?**  
FaucetPlay checks for new GitHub releases on startup. When one is found, a banner appears with a direct link to download the new package. One-click update installs are on the roadmap.

---

## 🛠️ Building from Source

```bash
pip install pyinstaller
pyinstaller faucetplay.spec
# Output: dist/FaucetPlay/
```

The release workflow (`.github/workflows/release.yml`) builds all three platforms in parallel on every `v*` tag push.

---

## 📋 Changelog

See [ROADMAP.md](ROADMAP.md) for the full product roadmap.

### v1.0.0 — Initial Release
- PAW-level aware faucet claiming with Tic-Tac-Toe automation
- Adaptive betting strategy engine
- Auto cashout with cooldown awareness
- Daily scheduler with jitter + system auto-start
- Encrypted credential storage
- Auto-update notifications via GitHub releases
- 3-platform binary releases (Windows / macOS / Linux)

---

## ⚠️ Disclaimer

FaucetPlay is provided for educational purposes. Gambling involves real financial risk. Use at your own discretion. The authors accept no liability for losses incurred through use of this software.

---

<div align="center">
Made with ❤️ for the DuckDice community · <a href="LICENSE">MIT License</a>
</div>
