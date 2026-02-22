# FaucetPlay — Multi-Platform DuckDice Faucet Farming App
## 🗺️ Product Roadmap

> A desktop app DuckDice gamblers will actually love — beautiful GUI, one-click onboarding,
> multi-account management, PAW-aware faucet claiming, strict one-proxy-per-account isolation,
> VPN integration, and smart automation.

---

## ✅ Already Shipped (v0.1 Alpha)

| Area | Status |
|------|--------|
| CLI bot (claim → all-in roll loop) | ✅ Done |
| DuckDice Bot API wrapper (`core/api.py`) | ✅ Done |
| Bot state machine with pause/stop (`core/bot.py`) | ✅ Done |
| Config + credential management skeleton (`core/config.py`) | ✅ Done |
| Scheduler skeleton (`core/scheduler.py`) | ✅ Done |
| Session statistics tracking | ✅ Done |

**Immediate tech-debt to fix before GUI work:**
- [ ] Remove hardcoded API key & cookie from `faucetplay.py`
- [ ] Move all config to `core/config.py` + encrypted local store
- [ ] Implement proper rate-limit back-off + cookie expiry detection
- [ ] Dynamic per-currency minimum bet fetch

---

## 🦆 DuckDice PAW Level System — Faucet Claiming Rules

> **Critical for correct bot behavior.** Every account has a PAW level (0–5) that determines
> *how* the faucet can be claimed. The bot must detect the account's level and apply the right flow.

| PAW Level | Claim Method | Tic-Tac-Toe Games Required | Notes |
|-----------|-------------|---------------------------|-------|
| 0 | Mini-game only | ~5 games | Slowest; newly created accounts |
| 1 | Mini-game only | ~4 games | |
| 2 | Mini-game only | ~3 games | |
| 3 | Mini-game + direct | ~1 game | Transitional level |
| 4 | Direct API claim | 0 | Standard farming level |
| 5 | Direct API claim | 0 | Highest loyalty tier; best faucet amounts |

**Implementation requirements:**
- Fetch and store PAW level on session start; re-check after each claim
- Levels 0–3: automate Tic-Tac-Toe via headless browser (Playwright)
  - Detect board state from page DOM
  - Apply optimal minimax strategy (never loses, fastest win)
  - Complete required N games before claim unlocks
  - Route browser through per-account proxy
- Levels 4–5: use existing direct API claim
- Show PAW level badge per account in the GUI
- Detect PAW level drop mid-session and switch flow automatically

---

## Phase 1 — Hardening, Security & PAW-Aware Claiming 🔒
**Goal: production-ready core that handles all PAW levels correctly**

- [ ] Encrypted credential vault (keyring / Fernet AES)
- [ ] Cookie expiry detection + re-prompt in GUI
- [ ] Exponential back-off on API errors and 429 rate limits
- [ ] Dynamic minimum-bet fetch per currency from API
- [ ] Structured logging to rotating file (no secrets in logs)
- [ ] Unit tests for `core/api.py` and `core/bot.py`
- [ ] Typed config dataclass + JSON schema validation

### PAW Level Detection & Tic-Tac-Toe Engine
- [ ] `api.get_paw_level(account)` — fetch current PAW level from user-info endpoint
- [ ] Cache level per account; re-fetch after every successful claim
- [ ] `core/tictactoe.py` — headless Playwright browser module:
  - Launch headless Chromium (attach via cookie session)
  - Parse board state from DOM on `/faucet` page
  - Minimax move solver — never loses, completes game in minimum moves
  - Play N games until claim unlocks (N from PAW level table above)
  - Respect per-game cooldown and page load delays
  - Return control to normal API claim flow after games complete
- [ ] Proxy-aware Playwright browser launch
- [ ] Auto-detect PAW level drop mid-session and switch claim flow

**Deliverable:** tested core that handles all PAW levels 0–5 correctly

---

## Phase 2 — Multi-Account Manager, Proxy & VPN Isolation 👥
**Goal: manage unlimited DuckDice accounts from one place with strict IP isolation**

> **IP isolation rule:** One proxy (or VPN profile) is permanently bound to exactly one account.
> Deleting an account does **not** free its proxy — the IP/endpoint stays blacklisted forever
> and cannot be assigned to any other account. This prevents DuckDice from linking accounts
> by shared IP history. The only way to reuse a network identity is to add it as a brand-new
> entry via the Proxy/VPN library (manual override by the user, with a clear warning).

### 2.1 Account Data Model
- [ ] `core/accounts.py` — `Account` dataclass:
  - `id`, `label`, `api_key` (encrypted), `cookie` (encrypted)
  - `network_profile_id` (FK → NetworkProfile; `null` = direct connection)
  - `paw_level`, `preferred_currency`, `strategy_profile`, `scheduler_profile`
  - `active`, `created_at`, `last_run_at`, `last_claim_at`
- [ ] Multi-account config store: `~/.faucetplay/accounts.json` (sensitive fields Fernet-encrypted)
- [ ] `AccountManager` — CRUD for accounts, import/export, duplicate account

### 2.2 Network Profile Library (Proxy & VPN)

> Each account chooses **one** network profile, or runs direct. Profiles live in a separate
> library (`network_profiles.json`) and are bound permanently to an account on assignment.

#### Proxy Profiles
- [ ] `core/network.py` — `NetworkProfile` dataclass:
  - `id`, `label`, `type` (`proxy` | `vpn` | `direct`)
  - For proxy: `proxy_protocol` (HTTP / HTTPS / SOCKS4 / SOCKS5), `host`, `port`, `username` (encrypted), `password` (encrypted)
  - `bound_to_account_id` — set on first assignment, **never cleared** (even after account deletion)
  - `blacklisted` — `true` once bound; blocks reassignment to any other account
  - `created_at`, `last_used_at`, `last_verified_at`
- [ ] Proxy applied to:
  - All `requests` API calls via `proxies=` parameter
  - Playwright browser sessions for Tic-Tac-Toe (PAW levels 0–3)
- [ ] Proxy health-check button in GUI (test connection, show resolved IP)
- [ ] Proxy failure handling: pause account immediately, alert user, **never** fall back to direct IP silently

#### VPN Profiles
- [ ] VPN as an alternative to proxy — each VPN profile is also bound 1:1 to one account
- [ ] Supported integration methods:
  - **OpenVPN** — launch `openvpn --config <file>` as subprocess, wait for TUN interface up
  - **WireGuard** — call `wg-quick up <profile>` (Linux/macOS); use `wireguard-nt` on Windows
  - **System VPN (manual)** — user connects VPN themselves; app verifies external IP changed before proceeding
- [ ] VPN config file stored encrypted in `~/.faucetplay/vpn/`
- [ ] VPN connect / disconnect lifecycle tied to account session start/stop
- [ ] IP verification after VPN connect: hit `https://api.ipify.org` and confirm IP ≠ host IP before any DuckDice request
- [ ] VPN failure: pause account, alert user, do **not** proceed without VPN active

#### Shared Rules for Both
- [ ] **1 profile → 1 account, forever.** Assignment is irreversible without explicit manual override.
- [ ] Manual override dialog: "⚠️ This IP/endpoint was previously used by account `<label>`. Assigning it to a new account may link them on DuckDice. Type CONFIRM to proceed."
- [ ] Network Profile Library UI: table of all profiles with columns — label, type, bound account, status, last IP, last verified
- [ ] "Direct connection" option available but shown with warning: "Your real IP will be used. All direct-connection accounts share the same IP — DuckDice may link them."

### 2.3 Account Dashboard (GUI)
- [ ] Accounts sidebar — list all accounts with live status icons
  - 🟢 Running / ⏸ Paused / ⏰ Scheduled / 🔴 Error / 💤 Idle
- [ ] PAW level badge next to each account name
- [ ] Network badge per account: 🔒 Proxy / 🛡 VPN / ⚠️ Direct
- [ ] Per-account row stats: today's claims, current balance, session profit
- [ ] Add / Edit / Delete / Duplicate account dialogs
- [ ] Drag-to-reorder accounts list
- [ ] "Run all" and "Stop all" global controls
- [ ] Per-account dedicated log tab
- [ ] Import accounts from CSV (bulk onboarding for power users)
- [ ] Active resolved IP displayed per account row (pulled from IP check)

**Deliverable:** unlimited accounts, each permanently and exclusively bound to one network identity

---

## Phase 3 — GUI v1: Onboarding & Dashboard 🖥️
**Goal: a beautiful app any DuckDice gambler can set up in under 2 minutes**

### 3.1 Setup Wizard (first-run onboarding)
- [ ] Welcome screen with logo and short explainer
- [ ] Step 1 — API key input with inline validation (calls `/user-info`)
- [ ] Step 2 — Cookie input with browser copy-paste guide + screenshot
- [ ] Step 3 — PAW level auto-detected; explains what it means for claiming
- [ ] Step 4 — Network profile: assign proxy, VPN, or direct (with isolation warning for direct)
- [ ] Step 5 — Pick preferred currency (live-fetched list with icons)
- [ ] Step 6 — Set target amount + risk preset (Easy / Normal / Degen)
- [ ] Step 7 — Quick test roll to confirm everything works
- [ ] Credentials saved encrypted; wizard skipped on future launches

### 3.2 Main Dashboard
- [ ] Dark theme by default (light theme toggle)
- [ ] Aggregated balance overview: all accounts total in USD
- [ ] Per-account balance cards: Faucet / Main
- [ ] Target progress bar per account with % and estimated rolls remaining
- [ ] Real-time session stats: bets, wins, losses, win-rate, net profit
- [ ] Live scrolling log with color-coded events:
  - 🟢 Win / 🔴 Loss / 🔵 Claim / 🟡 Tic-Tac-Toe game / 🟠 Error
- [ ] Start / Pause / Stop buttons with keyboard shortcuts
- [ ] Session timer and "claims today" counter per account
- [ ] Active network badge per account (🔒 Proxy / 🛡 VPN / ⚠️ Direct) with resolved IP

### 3.3 Settings Panel
- [ ] API key / cookie with show-hide toggle
- [ ] PAW level display (read-only, with manual refresh button)
- [ ] Network profile selector (proxy / VPN / direct) with permanent-binding warning
- [ ] Currency selector
- [ ] House edge input
- [ ] Auto-cashout threshold
- [ ] Auto-withdrawal toggle + address input

**Deliverable:** full GUI app runnable from source on Windows / macOS / Linux

---

## Phase 4 — Advanced Scheduler: Daily Claims & App Auto-Start ⏰
**Goal: fully hands-off farming — the app wakes up, claims, bets, and sleeps automatically**

### 4.1 Daily Faucet Claim Scheduler (per account)
- [ ] Set one or more exact claim times per account per day (e.g. "08:00, 20:00")
- [ ] Claim-only mode: claim faucet and stack, no betting
- [ ] Claim + bet mode: claim then immediately run betting strategy
- [ ] PAW-aware scheduling:
  - Levels 0–3: launch headless browser, complete Tic-Tac-Toe games, then claim
  - Levels 4–5: fire direct API claim at scheduled time
- [ ] Jitter option: ±N minutes random offset per claim time (anti-fingerprinting)
- [ ] Skip claim automatically if cooldown hasn't expired (detect from API)
- [ ] Per-account claim history log: timestamp, result, faucet amount received

### 4.2 App Auto-Start on System Boot
- [ ] "Launch on system startup" toggle in Settings
  - Windows: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` registry key
  - macOS: `~/Library/LaunchAgents/com.faucetplay.plist`
  - Linux: `~/.config/autostart/faucetplay.desktop`
- [ ] Start minimized to system tray on auto-launch
- [ ] Per-account toggle: "include in auto-launch"

### 4.3 Session Time Windows (per account)
- [ ] Start/stop at configured times, daily or on selected weekdays
- [ ] Timezone-aware (auto-detect system timezone; per-account override)
- [ ] Maximum session duration limit
- [ ] Sleep window between sessions (anti-detection cooldown)
- [ ] Conditional stops: "stop after +Y profit" or "after Z consecutive losses"

### 4.4 Scheduler UI
- [ ] Weekly calendar grid — click cells to enable/disable hour slots per account
- [ ] Claim time list with add/edit/remove controls per account
- [ ] Saved schedule profiles: "Night Grind", "Claim Only AM+PM", etc.
- [ ] Next-run and next-claim countdown displayed per account in dashboard
- [ ] "Run now" button — override schedule, start immediately
- [ ] Conflict detector: warns if two accounts share a network profile or are both on direct connection

**Deliverable:** fully automated multi-account claiming and session management

---

## Phase 5 — Betting Strategies 🎯
**Goal: give gamblers real control over every session**

- [ ] Strategy selector in GUI (cards with description and risk label)
- [ ] **All-In** — current single-roll to target
- [ ] **Martingale** — double bet on loss, reset on win
- [ ] **Reverse Martingale** — double on win, reset on loss
- [ ] **D'Alembert** — +1 unit on loss, −1 on win
- [ ] **Fibonacci** — follow Fibonacci sequence on losses
- [ ] **Paroli** — press 3 consecutive wins then reset
- [ ] **Fixed Percentage** — always bet X% of faucet balance
- [ ] **Custom / Script** — Lua script loader (reuse `faucet_adaptive_strategy.lua` pattern)
- [ ] Strategy backtester — simulate N rounds with chosen strategy, display ROI curve
- [ ] Per-strategy config: stop-loss, take-profit, max bet cap, reset trigger
- [ ] Per-account strategy assignment

**Deliverable:** 7+ strategy modes, backtester, custom Lua scripting, per-account assignment

---

## Phase 6 — Multi-Currency & Portfolio 💱
**Goal: manage all currencies across all accounts from one screen**

- [ ] Portfolio overview: all currencies × all accounts, USD equivalents
- [ ] Per-currency independent bot instances (run BTC + DOGE simultaneously)
- [ ] Exchange rate feed (CoinGecko public API, no key required)
- [ ] Currency-specific strategy and target configs per account
- [ ] "Sweep all" — claim & bet across all currencies in one session
- [ ] Historical balance chart per currency per account (SQLite-backed)

**Deliverable:** true multi-currency, multi-account farming portfolio

---

## Phase 7 — Auto Cashout & Withdrawal 💰
**Goal: safely move profits without manual intervention**

- [ ] Faucet → Main wallet cashout API integration
- [ ] Configurable cashout threshold per account per currency
- [ ] Address whitelist (only pre-approved external addresses)
- [ ] Daily withdrawal limit safety cap per account
- [ ] Withdrawal confirmation dialog with countdown (5 s to cancel)
- [ ] Full transaction history log (SQLite)
- [ ] Fee preview before sending
- [ ] Emergency STOP button — cancels all pending withdrawal actions

**Deliverable:** hands-free profit extraction with safety guardrails

---

## Phase 8 — Analytics & Insights 📊
**Goal: data that helps gamblers understand and improve their sessions**

- [ ] Session history database (SQLite — every bet from every account stored)
- [ ] Win/loss streak tracker per account
- [ ] Profit/loss chart (hourly, daily, weekly) — filterable by account
- [ ] Bet distribution histogram (chance % used)
- [ ] Best/worst sessions table
- [ ] Cross-account aggregate report
- [ ] CSV / Excel export
- [ ] Luck score vs expected value indicator
- [ ] Daily/weekly summary card in dashboard

**Deliverable:** rich analytics tab, export-ready data, cross-account reporting

---

## Phase 9 — Notifications & Community 🔔
**Goal: keep users informed and engaged anywhere**

- [ ] Desktop toast notifications (win, target reached, error)
- [ ] Sound alerts (configurable, mutable)
- [ ] Telegram bot integration — live session updates per account to your phone
- [ ] Discord webhook — post wins/targets to your server channel
- [ ] Email alert (SMTP, optional)
- [ ] In-app changelog / news feed (GitHub releases RSS)
- [ ] Community leaderboard (opt-in, anonymous, top earners across accounts)

**Deliverable:** multi-channel alerts and social features

---

## Phase 10 — Multi-Platform Builds & Distribution 🌍
**Goal: one-click install on every OS DuckDice gamblers use**

### 10.1 Windows
- [ ] PyInstaller one-file `.exe` with embedded icon
- [ ] Inno Setup installer — start menu + desktop shortcut + uninstaller
- [ ] Windows Defender / VirusTotal clean-check in CI
- [ ] Auto-update checker (GitHub releases API)
- [ ] Tested on Windows 10 and Windows 11

### 10.2 macOS
- [ ] PyInstaller `.app` bundle with `.dmg` disk image
- [ ] Universal binary (Apple Silicon + Intel)
- [ ] Drag-to-Applications install
- [ ] Tested on macOS 13 Ventura and 14 Sonoma

### 10.3 Linux
- [ ] AppImage (runs on any distro without install)
- [ ] `.deb` package (Ubuntu/Debian)
- [ ] Tested on Ubuntu 22.04 and Arch

### 10.4 CI/CD Pipeline
- [ ] GitHub Actions matrix build (Windows + macOS + Linux)
- [ ] Automated artifact upload to GitHub Releases on tag push
- [ ] Version bump + CHANGELOG auto-generation
- [ ] SHA256 checksums published with each release

**Deliverable:** signed, installable builds on all three platforms

---

## Phase 11 — Polish & v1.0 Release 🚀

- [ ] Full in-app help / user manual
- [ ] Video walkthrough: setup to first claim on PAW level 0 and level 4 (~5 min each)
- [ ] FAQ + troubleshooting guide (PAW levels, VPN setup, cookie expiry, proxy blacklisting)
- [ ] Accessibility pass (keyboard navigation, font-size scaling)
- [ ] Performance: GUI stays responsive under fast multi-account bet loops
- [ ] Beta testing with 20+ DuckDice community members
- [ ] GitHub Discussions + Discord server launch
- [ ] DuckDice forum / community thread announcement
- [ ] Product Hunt launch post

**Deliverable:** v1.0.0 public release

---

## 🔮 Post v1.0 — Future Vision

### v1.1 — Advanced Account Features
- Account groups and tagging (e.g. "BTC accounts", "Low PAW grind")
- Bulk operations: update strategy/schedule across all accounts at once
- Account health monitor: cookie freshness, network profile uptime, PAW trend, IP consistency

### v1.2 — AI Strategy Engine
- ML model trained on session history to suggest optimal bet % per account
- Anomaly detection: suspicious loss streaks → auto-pause
- Natural language strategy builder: *"Bet 1% chance, stop after 3 wins in a row"*

### v1.3 — Mobile Companion (React Native)
- Monitor live sessions across all accounts from your phone
- Receive push notifications per account
- Remote start/stop/pause controls

### v1.4 — Plugin Marketplace
- Community-built strategies as installable plugins
- Share, rate, and monetize strategies in-app

---

## 🐛 Known Issues (Carry-Forward)

| Issue | Priority |
|-------|----------|
| API key & cookie hardcoded in `faucetplay.py` | 🔴 Critical |
| PAW level not detected — claim flow is level-agnostic | 🔴 Critical |
| No Tic-Tac-Toe automation for low PAW accounts | 🔴 Critical |
| No multi-account support in any layer | 🟠 High |
| No proxy/VPN support — no IP isolation between accounts | 🟠 High |
| Proxy/VPN permanent-binding logic not implemented | 🟠 High |
| Minimum bet not fetched dynamically per currency | 🟠 High |
| Cookie expiration not detected — silently fails | 🟠 High |
| No rate-limit back-off on 429 responses | 🟡 Medium |
| GUI directory is empty — no UI yet | 🟡 Medium |
| `cashout()` and `withdraw()` in `api.py` are stubs | 🟡 Medium |

---

## 📈 Success Metrics

| Metric | Target |
|--------|--------|
| v1.0 release | Phase 11 complete |
| Downloads (first 30 days) | 500+ |
| Crash rate | < 0.5% of sessions |
| Setup-to-first-claim time (any PAW level) | < 3 minutes |
| Community size | 200+ Discord members |
| User rating | 4.5+ stars |

---

**Last Updated:** 2026-02-22
**Current Version:** 0.1.0-alpha
**Target v1.0 Release:** Q3 2026
