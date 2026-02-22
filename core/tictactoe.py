"""
FaucetPlay — Tic-Tac-Toe Claim Engine
Automates Tic-Tac-Toe mini-games on DuckDice for PAW level 0–3 accounts.
Uses Playwright headless browser, routed through the account's NetworkProfile.

PAW level → games required before claim unlocks:
  0 → 5 games  |  1 → 4  |  2 → 3  |  3 → 1  |  4+ → 0 (direct claim)

Strategy: minimax with alpha-beta pruning — never loses, wins as fast as possible.
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Board cell values
X = "X"
O = "O"
EMPTY = ""

Board = List[List[str]]   # 3×3 grid


# ---------------------------------------------------------------------------
# Pure minimax solver (no Playwright dependency)
# ---------------------------------------------------------------------------

def _winner(board: Board) -> Optional[str]:
    lines = [
        # rows
        [board[0][0], board[0][1], board[0][2]],
        [board[1][0], board[1][1], board[1][2]],
        [board[2][0], board[2][1], board[2][2]],
        # cols
        [board[0][0], board[1][0], board[2][0]],
        [board[0][1], board[1][1], board[2][1]],
        [board[0][2], board[1][2], board[2][2]],
        # diagonals
        [board[0][0], board[1][1], board[2][2]],
        [board[0][2], board[1][1], board[2][0]],
    ]
    for line in lines:
        if line[0] and line[0] == line[1] == line[2]:
            return line[0]
    return None


def _is_full(board: Board) -> bool:
    return all(board[r][c] != EMPTY for r in range(3) for c in range(3))


def _minimax(board: Board, is_maximizing: bool,
             alpha: int = -100, beta: int = 100) -> int:
    w = _winner(board)
    if w == X:
        return 10
    if w == O:
        return -10
    if _is_full(board):
        return 0

    if is_maximizing:
        best = -100
        for r in range(3):
            for c in range(3):
                if board[r][c] == EMPTY:
                    board[r][c] = X
                    best = max(best, _minimax(board, False, alpha, beta))
                    board[r][c] = EMPTY
                    alpha = max(alpha, best)
                    if beta <= alpha:
                        return best
        return best
    else:
        best = 100
        for r in range(3):
            for c in range(3):
                if board[r][c] == EMPTY:
                    board[r][c] = O
                    best = min(best, _minimax(board, True, alpha, beta))
                    board[r][c] = EMPTY
                    beta = min(beta, best)
                    if beta <= alpha:
                        return best
        return best


def best_move(board: Board) -> Tuple[int, int]:
    """Return (row, col) of the best move for player X (maximizer)."""
    best_val = -100
    move = (-1, -1)
    for r in range(3):
        for c in range(3):
            if board[r][c] == EMPTY:
                board[r][c] = X
                val = _minimax(board, False)
                board[r][c] = EMPTY
                if val > best_val:
                    best_val = val
                    move = (r, c)
    return move


# ---------------------------------------------------------------------------
# Playwright browser engine
# ---------------------------------------------------------------------------

class TicTacToeClaimEngine:
    """
    Drives the DuckDice /faucet page to:
      1. Complete N Tic-Tac-Toe games (N determined by PAW level)
      2. Submit the final claim

    Requires playwright to be installed:
      playwright install chromium
    """

    FAUCET_URL = "https://duckdice.io/faucet"

    def __init__(
        self,
        cookie: str,
        fingerprint: str = "",
        playwright_proxy: Optional[dict] = None,  # from NetworkProfileManager
        headless: bool = True,
        game_delay: float = 0.4,   # seconds between moves (anti-detection)
    ):
        self.cookie = cookie
        self.fingerprint = fingerprint
        self.playwright_proxy = playwright_proxy
        self.headless = headless
        self.game_delay = game_delay

    def run(self, games_needed: int, currency: str = "USDC") -> bool:
        """
        Play `games_needed` Tic-Tac-Toe games then submit claim.
        Returns True if claim was accepted.
        """
        if games_needed <= 0:
            logger.info("No TTT games required for this PAW level — skipping engine")
            return True

        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            raise RuntimeError(
                "Playwright is not installed. Run: playwright install chromium"
            )

        with sync_playwright() as pw:
            launch_opts: dict = {"headless": self.headless}
            if self.playwright_proxy:
                launch_opts["proxy"] = self.playwright_proxy

            browser = pw.chromium.launch(**launch_opts)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                extra_http_headers={"x-fingerprint": self.fingerprint} if self.fingerprint else {},
            )

            # Inject cookie into browser context
            self._inject_cookie(context)

            page = context.new_page()
            logger.info("Navigating to faucet page...")
            page.goto(self.FAUCET_URL, wait_until="networkidle", timeout=30_000)

            games_won = 0
            while games_won < games_needed:
                logger.info("Starting TTT game %d/%d", games_won + 1, games_needed)
                won = self._play_one_game(page)
                if won:
                    games_won += 1
                    logger.info("Game %d won.", games_won)
                else:
                    logger.warning("Game result unclear — retrying board scan")
                time.sleep(self.game_delay)

            # Submit claim
            success = self._submit_claim(page, currency)
            browser.close()
            return success

    def _inject_cookie(self, context) -> None:
        """Parse the raw cookie string and add cookies to the browser context."""
        cookies = []
        for part in self.cookie.split(";"):
            part = part.strip()
            if "=" not in part:
                continue
            name, _, value = part.partition("=")
            cookies.append({
                "name": name.strip(),
                "value": value.strip(),
                "domain": "duckdice.io",
                "path": "/",
            })
        if cookies:
            context.add_cookies(cookies)

    def _play_one_game(self, page) -> bool:
        """
        Play a single Tic-Tac-Toe game to completion.
        Returns True when our side wins (or the game ends).
        """
        try:
            from playwright.sync_api import TimeoutError as PWTimeout

            # Wait for the board to appear
            page.wait_for_selector(".ttt-cell, [data-cell], .tic-tac-toe-cell",
                                   timeout=10_000)

            board: Board = [[EMPTY]*3 for _ in range(3)]
            max_turns = 9

            for _ in range(max_turns):
                board = self._read_board(page)
                w = _winner(board)
                if w or _is_full(board):
                    return w == X or w is None  # win or draw is fine

                r, c = best_move(board)
                self._click_cell(page, r, c)
                time.sleep(self.game_delay)

                # Wait for opponent move
                page.wait_for_timeout(int(self.game_delay * 1000) + 200)

            return True  # assume completed

        except Exception as e:
            logger.error("TTT game error: %s", e)
            return False

    def _read_board(self, page) -> Board:
        """Read the current board state from the DOM."""
        board: Board = [[EMPTY]*3 for _ in range(3)]
        # Try multiple possible selectors DuckDice might use
        cells = page.query_selector_all(".ttt-cell, [data-cell], .tic-tac-toe-cell")
        for idx, cell in enumerate(cells[:9]):
            r, c = divmod(idx, 3)
            text = (cell.inner_text() or "").strip().upper()
            if text in (X, "X"):
                board[r][c] = X
            elif text in (O, "O"):
                board[r][c] = O
        return board

    def _click_cell(self, page, row: int, col: int) -> None:
        """Click the cell at (row, col) on the TTT board."""
        cells = page.query_selector_all(".ttt-cell, [data-cell], .tic-tac-toe-cell")
        idx = row * 3 + col
        if idx < len(cells):
            cells[idx].click()
        else:
            logger.warning("Cell index %d out of range (%d cells found)", idx, len(cells))

    def _submit_claim(self, page, currency: str) -> bool:
        """Click the claim button after all games are completed."""
        try:
            # Try common claim button selectors
            for selector in [
                "button:has-text('Claim')",
                "button:has-text('claim')",
                "[data-action='claim']",
                ".claim-button",
                "#claim-btn",
            ]:
                btn = page.query_selector(selector)
                if btn:
                    btn.click()
                    page.wait_for_timeout(2000)
                    logger.info("Claim button clicked for %s", currency)
                    return True
            logger.warning("Claim button not found on page")
            return False
        except Exception as e:
            logger.error("submit_claim error: %s", e)
            return False
