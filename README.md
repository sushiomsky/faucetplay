<div align="center">

# 🎰 FaucetPlay

### Farm DuckDice faucets on autopilot — beautiful GUI, smart automation, zero babysitting

[![Release](https://img.shields.io/github/v/release/sushiomsky/faucetplay?color=e94560&label=latest)](https://github.com/sushiomsky/faucetplay/releases/latest)
[![Build](https://img.shields.io/github/actions/workflow/status/sushiomsky/faucetplay/release.yml?label=build)](https://github.com/sushiomsky/faucetplay/actions)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](#-install)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](#-run-from-source)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Stop leaving faucet money on the table.**  
FaucetPlay claims your DuckDice faucets, plays the required Tic-Tac-Toe games automatically, bets toward your target with your chosen strategy, cashes out, and repeats — while you do literally anything else.

[📥 Download](#-install) · [🚀 Quick Start](#-quick-start) · [⚙️ Settings](#%EF%B8%8F-settings-reference) · [🗺️ Roadmap](#%EF%B8%8F-planned-features--roadmap) · [❓ FAQ](#-faq) · [📋 Changelog](#-changelog)

</div>

---

## ✨ Current Features (v1.5.0)

### 🤖 Faucet Automation
| Feature | Details |
|---|---|
| 🎯 **PAW-aware faucet claiming** | Detects your account's PAW level (0–5) and follows the correct claim flow automatically |
| 🎮 **Tic-Tac-Toe engine** | Headless Playwright browser plays all required TTT games using minimax — never loses, completes in minimum moves |
| 🔁 **Continuous farming loop** | Claim → bet → cashout → repeat, fully unattended |
| ⏳ **Cooldown awareness** | Detects cashout cooldowns and pauses betting until the window opens — never wastes a bet |

### 🎲 Betting Strategies
| Strategy | Description |
|---|---|
| **All-In** | Bet entire balance — reach target in one lucky roll |
| **Martingale** | Double bet after each loss; reset to base on any win |
| **Reverse Martingale** | Double on win, reset on loss — ride hot streaks |
| **D'Alembert** | +1 unit on loss, −1 on win — gentle progressive system |
| **Fibonacci** | Follow the Fibonacci sequence on consecutive losses |
| **Fixed Percentage** | Always wager X% of balance at a fixed win-chance |
| **Custom Lua Script** | Load your own `faucet_adaptive_strategy.lua` for full control |

All strategies respect per-round stop-loss and reset cleanly after each cashout.

### 🌐 Browser Session & Cookie Handling
| Feature | Details |
|---|---|
| 🔍 **Auto-extract from browser** | Reads your DuckDice cookies directly from Chrome or Firefox — no DevTools needed |
| 💾 **Persistent session** | Playwright `browser_state.json` saved after first login — no re-authentication on restarts |
| 🌐 **Browser Session mode** | Routes all API calls through Playwright's `APIRequestContext` for an identical TLS fingerprint to a real browser |
| 🔓 **OS keychain support** | Optional `browser-cookie3` handles macOS Keychain & Windows DPAPI decryption |

### 🔒 Security & Storage
| Feature | Details |
|---|---|
| **Fernet AES encryption** | API key and session cookie stored encrypted at `~/.faucetplay_bot/config.json` |
| **Key isolation** | Encryption key lives at `~/.faucetplay_bot/.key` (mode 0o600) — never bundled in the app |
| **No secrets in logs** | All log output is scrubbed of credential values |

### ⏰ Scheduler & Automation
| Feature | Details |
|---|---|
| **Daily claim scheduler** | Set up to 3 HH:MM claim times per day |
| **Jitter** | Random ±N minute offset per claim time to avoid fingerprinting patterns |
| **System auto-start** | Register FaucetPlay to launch minimized at login (Windows, macOS, Linux) |
| **Headless / server mode** | `--no-gui` flag runs the bot with saved config, no display required |

### 🖥️ GUI & UX
| Feature | Details |
|---|---|
| **Setup wizard** | First-run onboarding — API key → cookie → currency → target in under 2 minutes |
| **Live dashboard** | Faucet & main balance cards, target progress bar, win/loss counters, session timer |
| **Real-time log** | Color-coded scrolling log with text filter and one-click copy |
| **Strategy selector** | Choose or switch betting mode from the Settings panel |
| **Toast notifications** | Non-intrusive win, target, and error toasts |
| **In-app feedback** | Report bugs or request features directly to GitHub Issues — no account needed |
| **Auto-update banner** | Checks GitHub releases on startup; shows a download link when a newer version exists |
| **Unsaved-changes indicator** | Save buttons show `●` whenever there are pending unsaved changes |
| **Dark UI** | Polished CustomTkinter interface — dark mode only, as it should be |

### 💬 Auto-Chat
| Feature | Details |
|---|---|
| **Randomised chat messages** | Picks from a local SQLite message database and posts at a configurable random interval |
| **100 default messages** | Seeded on first run — ready to use out of the box |
| **Dry-run mode (default ON)** | Messages are only logged locally until you explicitly enable Live mode |
| **Rest periods** | Silence chat during overnight windows or any HH:MM range (supports overnight wrap-around) |
| **Message manager** | Add/remove messages, per-message enable toggle, live search, bulk Enable/Disable All |
| **Activity mini-log** | Last 30 sent/dry-run entries shown live with timestamps in the Auto-Chat tab |
| **⚡ Send Now** | Force an immediate message without waiting for the next interval |

---

## 📥 Install

### Option A — Pre-built binary (recommended, no Python needed)

Go to [**Releases**](https://github.com/sushiomsky/faucetplay/releases/latest) and download for your OS:

| Platform | File | Notes |
|---|---|---|
| 🪟 Windows 10/11 | `FaucetPlay-Windows.zip` | Extract and run `FaucetPlay.exe` |
| 🍎 macOS Intel | `FaucetPlay-macOS-Intel.dmg` | 2015–2020 Macs with Core i5/i7/i9 — requires macOS 10.15+ |
| 🍎 macOS Apple Silicon | `FaucetPlay-macOS-AppleSilicon.dmg` | M1 / M2 / M3 / M4 Macs |
| 🐧 Linux x64 | `FaucetPlay-Linux.tar.gz` | Extract and run `./faucetplay.sh` |

> **Not sure which Mac you have?** Apple menu → About This Mac. Intel chip = Intel DMG. M1/M2/M3/M4 = Apple Silicon DMG.

### Option B — Run from source

```bash
# Requires Python 3.11+
git clone https://github.com/sushiomsky/faucetplay.git
cd faucetplay
pip install -r requirements.txt
playwright install chromium
python faucetplay_app.py
```

Optional — enable OS-level cookie auto-extraction:

```bash
pip install browser-cookie3
```

---

## 🚀 Quick Start

1. **Launch** FaucetPlay — the setup wizard opens automatically on first run.
2. **Enter your DuckDice API key** — found at DuckDice → Settings → API.
3. **Add your session cookie** — two options:
   - Click **🔍 Detect from Chrome/Firefox** to auto-extract (recommended).
   - Or paste manually: Chrome DevTools (F12) → Application → Cookies → copy `_session`.
4. **Set your currency** (e.g. `USDC`) and **target amount** (e.g. `20.0`).
5. **Choose a betting strategy** in the Settings panel (default: All-In).
6. Click **▶ Start Farming** and watch the balance grow.

> **PAW levels 0–3** require Tic-Tac-Toe games before each faucet claim. FaucetPlay plays them all automatically in a headless browser — no action required from you.

---

## ⚙️ Settings Reference

### Credentials
| Setting | Description |
|---|---|
| **API Key** | Your DuckDice API key |
| **Session Cookie** | Raw `_session` cookie value — use the auto-detect button or paste manually |
| **Browser Session** | Toggle to route all requests through Playwright (recommended for stability) |

### Farming
| Setting | Description |
|---|---|
| **Currency** | Which coin to farm — USDC, BTC, ETH, LTC, DOGE, and more |
| **Target Amount** | Faucet balance that triggers an auto-cashout |
| **House Edge** | Dice roll edge percentage (default 3%; lower = smaller multiplier) |
| **Betting Mode** | All-In / Martingale / Reverse Martingale / D'Alembert / Fibonacci / Fixed % |
| **Auto Cashout** | Automatically transfer to main balance when target is reached |
| **Continue After Cashout** | Keep farming the same target after every cashout |

### Scheduler
| Setting | Description |
|---|---|
| **Claim Times** | Up to 3 HH:MM daily claim times (24-hour format) |
| **Jitter** | Random ±N minute offset per claim to avoid behavioral patterns |
| **System Auto-Start** | Register FaucetPlay to launch minimized at system login |

---

## 🛠️ Building from Source

```bash
pip install pyinstaller
pyinstaller faucetplay.spec
# Output binary: dist/FaucetPlay/
# Required separately: playwright install chromium
```

The spec file (`faucetplay.spec`) bundles `customtkinter`, `playwright`, `cryptography`, `schedule`, and all assets into a single-folder `onedir` package for fast startup.

### CI/CD — GitHub Actions Release Workflow

Triggered by pushing any `v*` tag. Runs 4 jobs in parallel after integration tests pass:

| Job | Runner | Output |
|---|---|---|
| `build-windows` | `windows-latest` | `FaucetPlay-Windows.zip` |
| `build-macos-intel` | `macos-14` + Rosetta 2 | `FaucetPlay-macOS-Intel.dmg` |
| `build-macos-arm` | `macos-14` (native) | `FaucetPlay-macOS-AppleSilicon.dmg` |
| `build-linux` | `ubuntu-22.04` | `FaucetPlay-Linux.tar.gz` |

The `release` job then creates a GitHub Release and attaches all four artifacts automatically.

To trigger a release:

```bash
git tag v1.5.0
git push origin v1.5.0
```

> The `FEEDBACK_TOKEN` placeholder in `core/version.py` is substituted with the `FEEDBACK_TOKEN` repository secret at build time to enable in-app GitHub Issue submission.

---

## 🗺️ Planned Features & Roadmap

> See [ROADMAP.md](ROADMAP.md) for full detail on each phase.

### Near-Term (Phase 2–3)
- **Multi-account manager** — unlimited DuckDice accounts from one window
- **Proxy & VPN isolation** — one network profile permanently bound to one account; never shared
- **Account dashboard** — per-account live status, PAW badge, network badge, balance cards
- **Import accounts from CSV** — bulk onboarding for power users

### Scheduler Improvements (Phase 4)
- Per-account claim time windows with weekday selection
- Claim-only mode (no betting) + combined claim-and-bet mode
- Session time windows with timezone support and max-duration limits
- Conditional stops: stop after +Y profit or after Z consecutive losses
- Weekly calendar grid UI

### Advanced Strategies (Phase 5)
- **Paroli** — press 3 consecutive wins then reset
- **Strategy backtester** — simulate N rounds with any strategy; show ROI curve
- Per-strategy stop-loss, take-profit, max bet cap, reset trigger
- Custom Lua script loader with full API access

### Multi-Currency Portfolio (Phase 6)
- Farm BTC, DOGE, USDC, ETH, LTC simultaneously per account
- Portfolio overview: all currencies × all accounts in USD
- Exchange rate feed via CoinGecko (no API key required)
- Historical balance chart per currency per account

### Auto Withdrawal (Phase 7)
- Faucet → Main wallet cashout integration
- Configurable daily withdrawal limit safety cap per account
- Address whitelist and withdrawal confirmation countdown
- Full transaction history log (SQLite)

### Analytics (Phase 8)
- Session history database (SQLite) — every bet from every account
- Profit/loss chart (hourly, daily, weekly)
- Win/loss streak tracker, bet distribution histogram
- CSV / Excel export and cross-account aggregate report

### Notifications (Phase 9)
- Desktop toast notifications
- Telegram bot integration — live session updates to your phone
- Discord webhook — post wins and targets to your server
- Email alerts via SMTP

### Distribution (Phase 10)
- Inno Setup Windows installer with start menu shortcuts
- `.deb` and AppImage packages for Linux
- SHA256 checksums published with every release
- Windows Defender / VirusTotal clean-check in CI

---

## 🏗️ Architecture

```
faucetplay_app.py           Entry point — CLI args, wires core + GUI
core/
  bot.py                    FaucetBot state machine (FARMING → CASHOUT_WAIT → POST_CASHOUT → STOPPED)
  api.py                    DuckDiceAPI — REST wrapper with retry/back-off and cookie auth
  config.py                 BotConfig — settings at ~/.faucetplay_bot/config.json
  strategies.py             BettingStrategy base class + 6 implementations + factory
  tictactoe.py              TicTacToeClaimEngine — Playwright browser + minimax solver
  browser_session.py        BrowserSession — persistent Playwright APIRequestContext
  cookie_extractor.py       Auto-extract cookies from Chrome / Firefox
  scheduler.py              BotScheduler — daily claim times with jitter, auto-start
  updater.py                GitHub releases API version check on startup
  version.py                APP_VERSION, repo URLs, changelog
gui/
  main_window.py            MainWindow (CustomTkinter) — bot runs in background thread
  theme.py                  All colour/font/sizing constants
  settings_panel.py         Settings UI — reads/writes BotConfig
  wizard.py                 First-run onboarding wizard
  toast.py                  Toast notification manager
  feedback_dialog.py        In-app bug/feature report → GitHub Issues API
faucet_adaptive_strategy.lua   Lua script for DuckDice's built-in script runner
strategy_configurator.py       Generates Lua script + strategy_config.json
```

---

## ❓ FAQ

**Does this work with all PAW levels?**  
Yes. PAW 0 requires ~5 TTT games, PAW 1 ~4, PAW 2 ~3, PAW 3 ~1, PAW 4–5 use a direct API claim. FaucetPlay detects your level and handles everything automatically.

**Is my account safe?**  
FaucetPlay replicates normal browser behavior — same TLS fingerprint, cookies, and request headers as a real Chrome session. Credentials are stored encrypted on your device. That said, automation is against DuckDice's ToS — use at your own risk.

**Why does the bot sometimes pause?**  
DuckDice enforces cashout cooldowns (typically 1 hour). When FaucetPlay hits its target and a cooldown is active, it waits, then cashes out and resumes automatically.

**My cookie keeps expiring — what do I do?**  
Enable **Browser Session** mode in Settings. This uses Playwright's full session persistence and reuses cookies across restarts, dramatically reducing re-authentication frequency.

**Can I run it headlessly on a server?**  
Yes: `python faucetplay_app.py --no-gui`. The scheduler runs fully automated daily claims without any display.

**How do I auto-start FaucetPlay at boot?**  
Settings → Auto-Start → enable **System Auto-Start**. FaucetPlay registers itself with the OS startup mechanism and launches minimized to the system tray.

**Will it update itself automatically?**  
FaucetPlay checks GitHub releases on every startup. When a new version is found, a banner appears with a direct link to download the new package. One-click auto-update is on the roadmap.

**How do I report a bug or suggest a feature?**  
Settings → About → **🐛 Report Bug** or **💡 Feature Request**. This posts directly to GitHub Issues with your app version, OS, and recent log lines attached — no GitHub account needed.

---

## 📋 Changelog

### v1.5.0 — Auto-Chat & UX Overhaul
- 💬 **Auto-Chat engine** — sends random messages to DuckDice chat on a randomised schedule
- 📦 100 default messages seeded in a local SQLite database (`~/.faucetplay_bot/chat_messages.db`)
- 🔇 **Dry-run ON by default** — nothing is sent until you flip the switch to Live mode
- ⏱  **Configurable interval** (min/max seconds) with random jitter between messages
- 🌙 **Rest periods** — silence chat during overnight or any HH:MM windows
- ⚡ **Send Now** — force an immediate message without waiting for the next interval
- 📝 **Message manager** — live search/filter, count badge, Enable/Disable All, per-row toggle & delete, Enter-to-add
- 📡 **Activity mini-log** — last 30 sent/dry-run entries shown live in the Auto-Chat tab
- 🟡 **Unsaved-changes indicator** — Save buttons show `●` when there are pending changes

### v1.4.0 — Automatic Cookie Extraction & Playwright Browser Session
- 🔍 **Detect from Chrome/Firefox** — reads `duckdice.io` cookies from your installed browser (no login required if already signed in)
- 🤖 **Auto-Extract** saves full `browser_state.json` — session reused on future runs, no re-login needed
- 🌐 **Browser Session mode** — all API calls routed through Playwright's `APIRequestContext` (identical TLS fingerprint to a real browser)
- `core/browser_session.py` — persistent Playwright session, drop-in for `requests`
- `core/cookie_extractor.py` — Chrome/Firefox SQLite + `browser-cookie3` OS keychain support
- Settings panel: two new cookie buttons + Browser Session toggle

### v1.3.0 — Multiple Betting Strategies
- 6 betting modes: All-In, Martingale, Reverse Martingale, Fixed %, D'Alembert, Fibonacci
- Strategy selector in Settings → Betting Mode with context-sensitive fields
- Bot tracks win/loss per roll and passes it to the active strategy
- Strategy state resets cleanly after cashout
- 30 new unit tests covering all strategies and the factory

### v1.2.1 — macOS Compatibility Fix
- Split macOS build: Intel DMG (macOS 10.15+) and Apple Silicon DMG (M1–M4)
- Intel build compiled via Rosetta 2 with `MACOSX_DEPLOYMENT_TARGET=10.15`
- Release notes now guide users to the correct DMG for their Mac

### v1.2.0 — In-App Feedback
- 🐛 Report Bug / 💡 Feature Request buttons in Settings → About
- Posts directly to GitHub Issues — zero login required
- Auto-attaches: app version, OS, Python version, last 30 log lines
- Dev builds fall back to pre-filled browser URL

### v1.1.0 — Reliability & Code Quality
- Fix win/cashout toasts never firing (poll-cycle tracking bug)
- Main Balance card now shows live balance after cashout
- Bet guard: redirects to claim if balance falls below min_bet
- `assert` → `BotError` raise (safe under `python -O`)
- Config: proper logging + `InvalidToken` warning on decrypt fail
- Scheduler: negative jitter now logs correctly
- Settings: jitter field validates input, no more `int()` crash

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

FaucetPlay is provided for educational purposes. Gambling involves real financial risk. Automation may violate DuckDice's Terms of Service. Use at your own discretion and risk. The authors accept no liability for losses or account actions incurred through use of this software.

---

<div align="center">
Made with ❤️ for the DuckDice community &nbsp;·&nbsp; <a href="LICENSE">MIT License</a> &nbsp;·&nbsp; <a href="ROADMAP.md">Roadmap</a> &nbsp;·&nbsp; <a href="CONTRIBUTING.md">Contributing</a>
</div>
