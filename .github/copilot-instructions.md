# FaucetPlay — Copilot Instructions

## Running the app

```bash
# GUI mode (default)
python faucetplay_app.py

# Headless / server mode (uses saved config)
python faucetplay_app.py --no-gui

# Start GUI minimized (used by system auto-start)
python faucetplay_app.py --minimized
```

## Build

```bash
pip install pyinstaller
pyinstaller faucetplay.spec
# Output: dist/FaucetPlay/
# Requires: playwright install chromium
```

## Lint & tests

```bash
# Lint (max-line-length=127, only fatal errors enforced in CI)
flake8 . --select=E9,F63,F7,F82

# Smoke test (no formal test suite — CI just checks imports)
python -c "from core import DuckDiceAPI, BotConfig, FaucetBot, BotScheduler; print('OK')"
```

## Architecture

```
faucetplay_app.py      Entry point — parses CLI args, wires core + GUI
core/
  bot.py               FaucetBot state machine (FARMING → CASHOUT_WAIT → POST_CASHOUT → STOPPED)
  api.py               DuckDiceAPI — REST wrapper with retry/back-off and cookie auth
  config.py            BotConfig — settings stored at ~/.faucetplay_bot/config.json
  tictactoe.py         TicTacToeClaimEngine — Playwright browser + minimax solver
  scheduler.py         BotScheduler — daily claim times with jitter, system auto-start
  updater.py           Checks GitHub releases API for new versions on startup
  version.py           Single source of truth for APP_VERSION, GitHub repo URLs, changelog
gui/
  main_window.py       MainWindow (CustomTkinter) — runs FaucetBot in a background thread
  theme.py             All colour/font/sizing constants — import as `from . import theme as T`
  settings_panel.py    Settings UI — reads/writes BotConfig
  wizard.py            First-run onboarding wizard
  toast.py             Toast notification manager
  feedback_dialog.py   In-app bug/feature report (posts to GitHub Issues API)
faucet_adaptive_strategy.lua   Lua script for DuckDice's built-in script runner (not Python)
strategy_configurator.py       Generates the Lua script + strategy_config.json
```

## Key conventions

**Bot state machine** — `FaucetBot` is always in one of four states (`BotState` enum). State transitions happen inside `_main_loop`. Never call `_farm_one_round` / `_wait_for_cashout` directly from outside the loop.

**Log callback pattern** — `FaucetBot` takes an optional `log_callback: Callable[[str], None]`. The GUI passes a queue-safe wrapper; headless mode passes `print`. All internal logging goes through `self._log(msg)` which prepends a UTC timestamp.

**Credential encryption** — `api_key` and `cookie` are the only fields encrypted in config. The Fernet key lives at `~/.faucetplay_bot/.key` (mode 0o600). Decryption failures log a warning and return `""` — never raise.

**PAW level → TTT games** — defined in `DuckDiceAPI.TTT_GAMES_REQUIRED = (5, 4, 3, 1, 0, 0)`. PAW 4+ can use the direct REST claim; PAW 0–3 must go through `TicTacToeClaimEngine` (Playwright).

**API retry strategy** — `DuckDiceAPI` uses a `requests` session with `urllib3.Retry` for 5xx errors, plus a manual back-off loop for 429s (up to `RATE_LIMIT_RETRIES = 6` attempts). All requests include a Chrome User-Agent and the raw `Cookie` header.

**GUI thread safety** — `FaucetBot.start()` is always run in a `threading.Thread`. GUI updates from the bot go through a `queue.Queue`; the main window polls it with `after()`. Never call CustomTkinter widget methods from the bot thread.

**Theme** — dark mode only (`ctk.set_appearance_mode("dark")`). All colours, fonts, and corner radii are in `gui/theme.py`. Import it as `from . import theme as T` and reference constants like `T.ACCENT`, `T.FONT_H2`.

**Commit message prefixes** — `Add:`, `Fix:`, `Update:`, `Docs:`, `Refactor:`.

**Release workflow** — triggered by pushing a `v*` tag. Builds Windows, macOS (Intel + Apple Silicon), and Linux in parallel via `.github/workflows/release.yml`. `FEEDBACK_TOKEN` in `version.py` is replaced at build time by the CI secret; it enables in-app GitHub Issue submission.
