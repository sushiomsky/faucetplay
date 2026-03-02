"""
FaucetPlay — Chat Message Store

SQLite database of messages used by the auto-chat engine.
Located at  ~/.faucetplay_bot/chat_messages.db

Schema
──────
messages(id INTEGER PRIMARY KEY AUTOINCREMENT,
         text TEXT UNIQUE NOT NULL,
         enabled INTEGER NOT NULL DEFAULT 1,
         created_at TEXT NOT NULL)

Public API
──────────
ChatMessageDB.get_all()        → list[dict]  (all rows, ordered by id)
ChatMessageDB.get_enabled()    → list[str]   (text of enabled rows)
ChatMessageDB.get_random()     → str | None  (random enabled message)
ChatMessageDB.add(text)        → int | None  (new row id, or None if duplicate)
ChatMessageDB.remove(row_id)   → bool
ChatMessageDB.set_enabled(row_id, enabled: bool) → bool
ChatMessageDB.count()          → int         (total messages)
"""

from __future__ import annotations

import logging
import random
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── 100 generic casino / gambling chat messages ───────────────────────────

DEFAULT_MESSAGES: List[str] = [
    # Greetings / farewells
    "gm everyone! 🌅",
    "gn all, good luck on your sessions! 🌙",
    "hey guys!",
    "what's up everyone 👋",
    "morning grind time 🌄",
    "back again, let's go! 🚀",
    "hope everyone's having a great session",
    "just checking in — good luck out there!",
    "hey hey hey 👋",
    "evening everyone 🌆",

    # Luck / positive vibes
    "good luck everyone! 🍀",
    "may the RNG gods be kind today 🙏",
    "stay lucky! ✨",
    "fingers crossed 🤞",
    "feeling lucky today!",
    "may the odds be ever in your favor 🎲",
    "sending good vibes your way 💫",
    "luck is on our side today 🌟",
    "this is our day! 🎉",
    "green candles only 📈",

    # Reactions / wins
    "gg everyone",
    "nice win! 🎉",
    "let's gooo! 🚀🚀",
    "that's what I'm talking about! 💪",
    "WAGMI 🙌",
    "LETS GOOO",
    "easy money 😎",
    "on a roll!",
    "hot streak 🔥",
    "boom! 💥",

    # DuckDice specific
    "DuckDice is the best 🦆",
    "love this site",
    "duckdice never disappoints 🦆",
    "best faucet out there 🚿",
    "who else loves duckdice?",
    "quack quack 🦆",
    "ducks before bucks 🦆",
    "this duck prints 💸",
    "loving the faucet rewards today",
    "duckdice fam 🦆❤️",

    # Strategy / gambling chat
    "what's everyone's strategy today?",
    "low chance or high chance — that's the question",
    "grinding the faucet 💪",
    "stack those sats 🟠",
    "patience is key in gambling",
    "slow and steady wins the race 🐢",
    "always set your limits folks",
    "responsible gambling is the way",
    "anyone else on the grind today?",
    "diversify your bets!",

    # Crypto general
    "crypto never sleeps 🌐",
    "hodl strong 💎🙌",
    "just here stacking satoshis",
    "btc looking good today?",
    "love free crypto 🎁",
    "every sat counts 🟠",
    "faucets are free money, don't sleep on it",
    "stacking up slowly but surely 📦",
    "crypto to the moon eventually 🌕",
    "building the portfolio one faucet at a time",

    # Weekend / time
    "happy friday everyone 🎊",
    "weekend grind! 💰",
    "monday motivation 💪",
    "who else is grinding all weekend?",
    "mid-week hustle 🛠️",
    "long weekend = more grinding time 😁",
    "nothing better than passive income on a Saturday",
    "Sunday funday at the dice table 🎲",
    "TGIF and time to grind 🙌",
    "holiday grind never stops",

    # Questions / conversational
    "anyone know the cashout cooldown today?",
    "what currency is everyone farming?",
    "usdc or btc — which do you prefer?",
    "how's everyone's session going?",
    "anyone else running the faucet bot?",
    "tips for grinding PAW level 4?",
    "what's the best target to set?",
    "how many claims a day do you do?",
    "is the site running slow for anyone?",
    "what's your favorite strategy?",

    # Motivation / mindset
    "every loss brings you closer to a win 🎲",
    "consistency beats luck long term",
    "keep going, the next claim is the big one 💪",
    "discipline wins in gambling",
    "stay calm and roll on 🎲",
    "grind today, celebrate tomorrow 🥂",
    "small wins add up! 📊",
    "patience and persistence 🙏",
    "never bet more than you can afford — stay smart",
    "one step closer to the target 🎯",

    # Fun / casual
    "alright let's do this! 🎰",
    "rolling the dice again 🎲",
    "another day another faucet 💧",
    "love that claiming sound 🔔",
    "this is my therapy 😂",
    "just one more roll 😅",
    "dice don't lie 🎲",
    "I trust the process",
    "variance is real, stay disciplined 📉📈",
    "we out here grinding, no days off 💯",
]

assert len(DEFAULT_MESSAGES) == 100, f"Expected 100 messages, got {len(DEFAULT_MESSAGES)}"


class ChatMessageDB:
    """SQLite-backed store for auto-chat messages."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / ".faucetplay_bot" / "chat_messages.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._path = db_path
        self._init_db()

    # ── Internal helpers ──────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    text       TEXT    UNIQUE NOT NULL,
                    enabled    INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT    NOT NULL
                )
            """)
            conn.commit()
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        """Insert default messages that are not already in the DB."""
        ts = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO messages (text, enabled, created_at) VALUES (?, 1, ?)",
                [(msg, ts) for msg in DEFAULT_MESSAGES],
            )
            conn.commit()

    # ── Public API ────────────────────────────────────────────────────────

    def get_all(self) -> List[dict]:
        """Return all messages as dicts with keys: id, text, enabled, created_at."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, text, enabled, created_at FROM messages ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_enabled(self) -> List[str]:
        """Return text of all enabled messages."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT text FROM messages WHERE enabled = 1 ORDER BY id"
            ).fetchall()
        return [r["text"] for r in rows]

    def get_random(self) -> Optional[str]:
        """Return a random enabled message text, or None if none are enabled."""
        messages = self.get_enabled()
        if not messages:
            return None
        return random.choice(messages)

    def add(self, text: str) -> Optional[int]:
        """
        Insert a new message.  Returns the new row id, or None if text already
        exists (duplicate is silently ignored).
        """
        text = text.strip()
        if not text:
            return None
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO messages (text, enabled, created_at) VALUES (?, 1, ?)",
                    (text, datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()
                return cur.lastrowid
        except sqlite3.IntegrityError:
            logger.debug("Duplicate message ignored: %r", text)
            return None

    def remove(self, row_id: int) -> bool:
        """Delete a message by id.  Returns True if a row was deleted."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM messages WHERE id = ?", (row_id,))
            conn.commit()
        return cur.rowcount > 0

    def set_enabled(self, row_id: int, enabled: bool) -> bool:
        """Enable or disable a message.  Returns True if row was found."""
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE messages SET enabled = ? WHERE id = ?",
                (1 if enabled else 0, row_id),
            )
            conn.commit()
        return cur.rowcount > 0

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
