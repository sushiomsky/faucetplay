"""
FaucetPlay — Betting Strategy Implementations

Each strategy's next_bet() returns (amount, chance) for the next dice roll.

Strategies
──────────
AllIn            Bet entire faucet balance; chance calculated to hit target.
Martingale       Start at base_bet, double on loss, reset on win.
ReverseMartingale Double on win, reset on loss (ride hot streaks).
FixedPercentage  Always bet X% of balance at a fixed win-chance.
DAlembert        +1 unit on loss, −1 on win (gentler progression).
Fibonacci        Follow the Fibonacci sequence on losses.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Type


class BettingStrategy:
    """Base class for all betting strategies."""

    NAME: str = "base"
    LABEL: str = "Base"
    DESCRIPTION: str = ""

    def reset(self) -> None:
        """Reset internal state for a new round."""

    def next_bet(
        self,
        faucet_balance: float,
        min_bet: float,
        cashout_threshold: float,
        house_edge: float,
        last_win: Optional[bool] = None,
    ) -> Tuple[float, float]:
        """Return ``(amount, chance)`` for the next bet.

        amount — how much to wager (clamped to [min_bet, faucet_balance])
        chance — win probability in % (clamped to [0.01, 99.0])
        """
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────
# All-In (original behaviour)
# ─────────────────────────────────────────────────────────────────

class AllInStrategy(BettingStrategy):
    """Bet the entire faucet balance; win-chance targets the cashout threshold."""

    NAME = "all_in"
    LABEL = "All-In"
    DESCRIPTION = "Bet entire balance — reach target in one lucky roll."

    def reset(self) -> None:
        pass

    def next_bet(self, faucet_balance, min_bet, cashout_threshold,
                 house_edge, last_win=None):
        amount     = faucet_balance
        multiplier = cashout_threshold / faucet_balance
        raw_chance = (100.0 * (1.0 - house_edge)) / multiplier
        chance     = max(0.01, min(99.0, round(raw_chance, 2)))
        return amount, chance


# ─────────────────────────────────────────────────────────────────
# Martingale
# ─────────────────────────────────────────────────────────────────

class MartingaleStrategy(BettingStrategy):
    """Classic Martingale — double on loss, reset on win."""

    NAME = "martingale"
    LABEL = "Martingale"
    DESCRIPTION = "Double bet after each loss; reset to base on any win."

    def __init__(self, base_bet: float = 0.001, chance: float = 49.5):
        self.base_bet = base_bet
        self.chance   = chance
        self._current = base_bet

    def reset(self) -> None:
        self._current = self.base_bet

    def next_bet(self, faucet_balance, min_bet, cashout_threshold,
                 house_edge, last_win=None):
        if last_win is True:
            self._current = self.base_bet
        elif last_win is False:
            self._current = self._current * 2
        amount = max(min_bet, min(self._current, faucet_balance))
        return round(amount, 9), self.chance


# ─────────────────────────────────────────────────────────────────
# Reverse Martingale
# ─────────────────────────────────────────────────────────────────

class ReverseMartingaleStrategy(BettingStrategy):
    """Reverse Martingale — double on win, reset on loss (ride hot streaks)."""

    NAME = "reverse_martingale"
    LABEL = "Reverse Martingale"
    DESCRIPTION = "Double bet after each win; reset to base on any loss."

    def __init__(self, base_bet: float = 0.001, chance: float = 49.5):
        self.base_bet = base_bet
        self.chance   = chance
        self._current = base_bet

    def reset(self) -> None:
        self._current = self.base_bet

    def next_bet(self, faucet_balance, min_bet, cashout_threshold,
                 house_edge, last_win=None):
        if last_win is False:
            self._current = self.base_bet
        elif last_win is True:
            self._current = self._current * 2
        amount = max(min_bet, min(self._current, faucet_balance))
        return round(amount, 9), self.chance


# ─────────────────────────────────────────────────────────────────
# Fixed Percentage
# ─────────────────────────────────────────────────────────────────

class FixedPercentageStrategy(BettingStrategy):
    """Always bet a fixed percentage of the current faucet balance."""

    NAME = "fixed_percent"
    LABEL = "Fixed %"
    DESCRIPTION = "Bet X% of balance each roll — slow but steady accumulation."

    def __init__(self, percent: float = 1.0, chance: float = 49.5):
        self.percent = percent   # e.g. 1.0 means 1%
        self.chance  = chance

    def reset(self) -> None:
        pass

    def next_bet(self, faucet_balance, min_bet, cashout_threshold,
                 house_edge, last_win=None):
        amount = max(min_bet, faucet_balance * self.percent / 100.0)
        amount = min(amount, faucet_balance)
        return round(amount, 9), self.chance


# ─────────────────────────────────────────────────────────────────
# D'Alembert
# ─────────────────────────────────────────────────────────────────

class DAlembert(BettingStrategy):
    """D'Alembert progression — gentler than Martingale."""

    NAME = "dalembert"
    LABEL = "D'Alembert"
    DESCRIPTION = "+1 unit on loss, −1 unit on win. Lower variance than Martingale."

    def __init__(self, unit: float = 0.001, chance: float = 49.5):
        self.unit   = unit
        self.chance = chance
        self._units = 1

    def reset(self) -> None:
        self._units = 1

    def next_bet(self, faucet_balance, min_bet, cashout_threshold,
                 house_edge, last_win=None):
        if last_win is False:
            self._units += 1
        elif last_win is True and self._units > 1:
            self._units -= 1
        amount = max(min_bet, min(self.unit * self._units, faucet_balance))
        return round(amount, 9), self.chance


# ─────────────────────────────────────────────────────────────────
# Fibonacci
# ─────────────────────────────────────────────────────────────────

_FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610]


class FibonacciStrategy(BettingStrategy):
    """Follow the Fibonacci sequence on losses; step back two on a win."""

    NAME = "fibonacci"
    LABEL = "Fibonacci"
    DESCRIPTION = "Advance Fibonacci sequence on loss, retreat two steps on win."

    def __init__(self, unit: float = 0.001, chance: float = 49.5):
        self.unit   = unit
        self.chance = chance
        self._idx   = 0

    def reset(self) -> None:
        self._idx = 0

    def next_bet(self, faucet_balance, min_bet, cashout_threshold,
                 house_edge, last_win=None):
        if last_win is False:
            self._idx = min(self._idx + 1, len(_FIB) - 1)
        elif last_win is True:
            self._idx = max(0, self._idx - 2)
        amount = max(min_bet, min(self.unit * _FIB[self._idx], faucet_balance))
        return round(amount, 9), self.chance


# ─────────────────────────────────────────────────────────────────
# Registry & factory
# ─────────────────────────────────────────────────────────────────

_ALL: List[Type[BettingStrategy]] = [
    AllInStrategy,
    MartingaleStrategy,
    ReverseMartingaleStrategy,
    FixedPercentageStrategy,
    DAlembert,
    FibonacciStrategy,
]

STRATEGIES: Dict[str, Type[BettingStrategy]] = {cls.NAME: cls for cls in _ALL}

STRATEGY_LABELS: Dict[str, str] = {cls.NAME: cls.LABEL for cls in _ALL}
STRATEGY_NAMES: List[str] = [cls.NAME for cls in _ALL]


def make_strategy(name: str, cfg: dict) -> BettingStrategy:
    """Instantiate a strategy from its registry name and a config dict."""
    cls = STRATEGIES.get(name, AllInStrategy)

    if cls is AllInStrategy:
        return AllInStrategy()

    base_bet = float(cfg.get("strategy_base_bet") or cfg.get("min_bet") or 0.001)
    chance   = float(cfg.get("strategy_chance") or 49.5)
    percent  = float(cfg.get("strategy_bet_percent") or 1.0)

    if cls is MartingaleStrategy:
        return MartingaleStrategy(base_bet=base_bet, chance=chance)
    if cls is ReverseMartingaleStrategy:
        return ReverseMartingaleStrategy(base_bet=base_bet, chance=chance)
    if cls is FixedPercentageStrategy:
        return FixedPercentageStrategy(percent=percent, chance=chance)
    if cls is DAlembert:
        return DAlembert(unit=base_bet, chance=chance)
    if cls is FibonacciStrategy:
        return FibonacciStrategy(unit=base_bet, chance=chance)

    return AllInStrategy()
