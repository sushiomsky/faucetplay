"""
FaucetPlay — Version & Release Metadata
"""

APP_NAME    = "FaucetPlay"
APP_VERSION = "1.3.0"
TAGLINE     = "Farm DuckDice faucets on autopilot"

# GitHub repository (owner/repo)
GITHUB_OWNER     = "sushiomsky"
GITHUB_REPO      = "faucetplay"
GITHUB_REPO_FULL = f"{GITHUB_OWNER}/{GITHUB_REPO}"
GITHUB_RELEASES  = f"https://github.com/{GITHUB_REPO_FULL}/releases"
GITHUB_API_LATEST = (
    f"https://api.github.com/repos/{GITHUB_REPO_FULL}/releases/latest"
)
GITHUB_API_ISSUES = (
    f"https://api.github.com/repos/{GITHUB_REPO_FULL}/issues"
)

# Bot token injected at build time (CI replaces @FEEDBACK_TOKEN@ via secret).
# Empty string → fallback to browser URL when running from source.
FEEDBACK_TOKEN = "@FEEDBACK_TOKEN@"

# One-line changelog shown in the About panel
CHANGELOG = """\
v1.3.0 — Multiple betting strategies
  • 6 betting modes: All-In, Martingale, Reverse Martingale, Fixed %, D'Alembert, Fibonacci
  • Strategy selector in Settings → Betting Mode with context-sensitive fields
  • Bot tracks win/loss per roll and passes it to active strategy
  • Strategy state resets cleanly between rounds after cashout
  • 30 new unit tests covering all strategies and the factory

v1.2.1 — macOS compatibility fix
  • Split macOS build: Intel DMG (macOS 10.15+) + Apple Silicon DMG (M1–M4)
  • Intel build sets MACOSX_DEPLOYMENT_TARGET=10.15 (Catalina and newer)
  • Release notes now show which DMG to pick

v1.2.0 — In-app feedback (no account needed)
  • 🐛 Report Bug / 💡 Feature Request buttons in Settings → About
  • Submits directly to GitHub Issues — zero login required
  • Auto-attaches: app version, OS, Python version, last 30 log lines
  • Success screen with link to view your submitted report
  • Dev builds fall back to pre-filled browser URL

v1.1.0 — Reliability & code quality
  • Fix win/cashout toasts never firing (poll-cycle tracking bug)
  • Main Balance card now shows live balance after cashout
  • Bet guard: redirects to claim if balance falls below min_bet
  • assert → BotError raise (safe under python -O)
  • Config: proper logging + InvalidToken warning on decrypt fail
  • Scheduler: negative jitter now logs correctly instead of silently dropping
  • Settings: jitter field validates input, no more int() crash on bad value
  • Remove stale withdraw() stub and inline import time alias
  • Removed obsolete files from repo (scheduler_panel, faucetplay.py, etc.)

v1.0.0 — Initial release
  • Single-account faucet farming with PAW-aware claiming
  • Auto-cashout loop with cooldown wait
  • Daily scheduler with jitter
  • Encrypted local credential storage
  • macOS / Windows / Linux packages
"""
