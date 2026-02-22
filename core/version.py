"""
FaucetPlay — Version & Release Metadata
"""

APP_NAME    = "FaucetPlay"
APP_VERSION = "1.0.0"
TAGLINE     = "Farm DuckDice faucets on autopilot"

# GitHub repository (owner/repo)
GITHUB_OWNER     = "sushiomsky"
GITHUB_REPO      = "faucetplay"
GITHUB_REPO_FULL = f"{GITHUB_OWNER}/{GITHUB_REPO}"
GITHUB_RELEASES  = f"https://github.com/{GITHUB_REPO_FULL}/releases"
GITHUB_API_LATEST = (
    f"https://api.github.com/repos/{GITHUB_REPO_FULL}/releases/latest"
)

# One-line changelog shown in the About panel
CHANGELOG = """\
v1.0.0 — Initial release
  • Single-account faucet farming with PAW-aware claiming
  • Auto-cashout loop with cooldown wait
  • Daily scheduler with jitter
  • Encrypted local credential storage
  • macOS / Windows / Linux packages
"""
