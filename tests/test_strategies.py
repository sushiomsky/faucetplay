"""
Unit tests for core/strategies.py

These run without network access and test all strategy implementations
for correct bet sizing, progression logic, and factory behaviour.
"""
from __future__ import annotations

import pytest
from core.strategies import (
    AllInStrategy,
    MartingaleStrategy,
    ReverseMartingaleStrategy,
    FixedPercentageStrategy,
    DAlembert,
    FibonacciStrategy,
    make_strategy,
    STRATEGY_NAMES,
    STRATEGY_LABELS,
)

# Shared constants
BAL   = 1.0
MIN   = 0.001
TARG  = 20.0
EDGE  = 0.03


# ─────────────────────────────────────────────────────────────────
# AllIn
# ─────────────────────────────────────────────────────────────────

class TestAllIn:
    def test_bets_entire_balance(self):
        s = AllInStrategy()
        amount, _ = s.next_bet(BAL, MIN, TARG, EDGE)
        assert amount == BAL

    def test_chance_targets_cashout(self):
        s = AllInStrategy()
        _, chance = s.next_bet(BAL, MIN, TARG, EDGE)
        # chance ≈ 100 * (1 - edge) / multiplier
        multiplier = TARG / BAL
        expected = (100.0 * (1.0 - EDGE)) / multiplier
        assert abs(chance - round(expected, 2)) < 0.01

    def test_chance_clamped_to_99(self):
        """When balance ≈ target, chance should not exceed 99."""
        s = AllInStrategy()
        _, chance = s.next_bet(19.9, MIN, 20.0, EDGE)
        assert chance <= 99.0

    def test_chance_clamped_to_0_01(self):
        """Very tiny balance vs huge target → chance ≈ 0.01 minimum."""
        s = AllInStrategy()
        _, chance = s.next_bet(0.001, MIN, 1_000_000.0, EDGE)
        assert chance >= 0.01

    def test_reset_is_noop(self):
        s = AllInStrategy()
        s.reset()   # should not raise


# ─────────────────────────────────────────────────────────────────
# Martingale
# ─────────────────────────────────────────────────────────────────

class TestMartingale:
    def test_starts_at_base_bet(self):
        s = MartingaleStrategy(base_bet=0.01)
        amount, _ = s.next_bet(1.0, MIN, TARG, EDGE, last_win=None)
        assert amount == pytest.approx(0.01)

    def test_doubles_on_loss(self):
        s = MartingaleStrategy(base_bet=0.01)
        s.next_bet(1.0, MIN, TARG, EDGE, last_win=None)   # first bet
        amount, _ = s.next_bet(0.99, MIN, TARG, EDGE, last_win=False)
        assert amount == pytest.approx(0.02)

    def test_resets_on_win(self):
        s = MartingaleStrategy(base_bet=0.01)
        # simulate two losses first
        s.next_bet(1.0, MIN, TARG, EDGE, last_win=False)
        s.next_bet(1.0, MIN, TARG, EDGE, last_win=False)
        amount, _ = s.next_bet(1.0, MIN, TARG, EDGE, last_win=True)
        assert amount == pytest.approx(0.01)

    def test_capped_at_balance(self):
        s = MartingaleStrategy(base_bet=0.5)
        # force many doublings
        for _ in range(10):
            s.next_bet(1.0, MIN, TARG, EDGE, last_win=False)
        amount, _ = s.next_bet(1.0, MIN, TARG, EDGE, last_win=False)
        assert amount <= 1.0

    def test_reset_restores_base(self):
        s = MartingaleStrategy(base_bet=0.01)
        s.next_bet(1.0, MIN, TARG, EDGE, last_win=False)
        s.reset()
        amount, _ = s.next_bet(1.0, MIN, TARG, EDGE)
        assert amount == pytest.approx(0.01)

    def test_fixed_chance(self):
        s = MartingaleStrategy(chance=45.0)
        _, chance = s.next_bet(1.0, MIN, TARG, EDGE)
        assert chance == pytest.approx(45.0)


# ─────────────────────────────────────────────────────────────────
# Reverse Martingale
# ─────────────────────────────────────────────────────────────────

class TestReverseMartingale:
    def test_starts_at_base(self):
        s = ReverseMartingaleStrategy(base_bet=0.01)
        amount, _ = s.next_bet(1.0, MIN, TARG, EDGE)
        assert amount == pytest.approx(0.01)

    def test_doubles_on_win(self):
        s = ReverseMartingaleStrategy(base_bet=0.01)
        s.next_bet(1.0, MIN, TARG, EDGE, last_win=None)
        amount, _ = s.next_bet(1.0, MIN, TARG, EDGE, last_win=True)
        assert amount == pytest.approx(0.02)

    def test_resets_on_loss(self):
        s = ReverseMartingaleStrategy(base_bet=0.01)
        s.next_bet(1.0, MIN, TARG, EDGE, last_win=True)
        s.next_bet(1.0, MIN, TARG, EDGE, last_win=True)
        amount, _ = s.next_bet(1.0, MIN, TARG, EDGE, last_win=False)
        assert amount == pytest.approx(0.01)


# ─────────────────────────────────────────────────────────────────
# Fixed Percentage
# ─────────────────────────────────────────────────────────────────

class TestFixedPercentage:
    def test_bets_exact_percent(self):
        s = FixedPercentageStrategy(percent=5.0)
        amount, _ = s.next_bet(2.0, MIN, TARG, EDGE)
        assert amount == pytest.approx(0.1)   # 5% of 2.0

    def test_clamped_to_min_bet(self):
        s = FixedPercentageStrategy(percent=0.001)
        amount, _ = s.next_bet(0.01, MIN, TARG, EDGE)
        assert amount >= MIN

    def test_fixed_chance(self):
        s = FixedPercentageStrategy(chance=50.0)
        _, chance = s.next_bet(1.0, MIN, TARG, EDGE)
        assert chance == pytest.approx(50.0)

    def test_last_win_ignored(self):
        s = FixedPercentageStrategy(percent=1.0)
        a1, _ = s.next_bet(1.0, MIN, TARG, EDGE, last_win=True)
        a2, _ = s.next_bet(1.0, MIN, TARG, EDGE, last_win=False)
        assert a1 == pytest.approx(a2)


# ─────────────────────────────────────────────────────────────────
# D'Alembert
# ─────────────────────────────────────────────────────────────────

class TestDAlembert:
    def test_starts_at_one_unit(self):
        s = DAlembert(unit=0.01)
        amount, _ = s.next_bet(1.0, MIN, TARG, EDGE)
        assert amount == pytest.approx(0.01)

    def test_increments_on_loss(self):
        s = DAlembert(unit=0.01)
        s.next_bet(1.0, MIN, TARG, EDGE, last_win=None)
        amount, _ = s.next_bet(1.0, MIN, TARG, EDGE, last_win=False)
        assert amount == pytest.approx(0.02)

    def test_decrements_on_win(self):
        s = DAlembert(unit=0.01)
        # get to 3 units first
        s.next_bet(1.0, MIN, TARG, EDGE, last_win=False)
        s.next_bet(1.0, MIN, TARG, EDGE, last_win=False)
        amount, _ = s.next_bet(1.0, MIN, TARG, EDGE, last_win=True)
        assert amount == pytest.approx(0.02)

    def test_never_below_one_unit(self):
        s = DAlembert(unit=0.01)
        for _ in range(5):
            s.next_bet(1.0, MIN, TARG, EDGE, last_win=True)
        amount, _ = s.next_bet(1.0, MIN, TARG, EDGE)
        assert amount >= 0.01

    def test_reset(self):
        s = DAlembert(unit=0.01)
        s.next_bet(1.0, MIN, TARG, EDGE, last_win=False)
        s.reset()
        amount, _ = s.next_bet(1.0, MIN, TARG, EDGE)
        assert amount == pytest.approx(0.01)


# ─────────────────────────────────────────────────────────────────
# Fibonacci
# ─────────────────────────────────────────────────────────────────

class TestFibonacci:
    def test_starts_at_one_unit(self):
        s = FibonacciStrategy(unit=0.01)
        amount, _ = s.next_bet(1.0, MIN, TARG, EDGE)
        assert amount == pytest.approx(0.01)

    def test_advances_on_loss(self):
        s = FibonacciStrategy(unit=0.01)
        s.next_bet(1.0, MIN, TARG, EDGE, last_win=None)
        # idx 0→1, fib[1]=1 → still 1 unit
        amount, _ = s.next_bet(1.0, MIN, TARG, EDGE, last_win=False)
        assert amount == pytest.approx(0.01)
        amount, _ = s.next_bet(1.0, MIN, TARG, EDGE, last_win=False)
        # idx 2, fib[2]=2
        assert amount == pytest.approx(0.02)

    def test_retreats_two_on_win(self):
        s = FibonacciStrategy(unit=0.01)
        # advance to idx 4 (fib=5) via losses
        for _ in range(4):
            s.next_bet(1.0, MIN, TARG, EDGE, last_win=False)
        # win → idx goes 4→2, fib[2]=2
        amount, _ = s.next_bet(1.0, MIN, TARG, EDGE, last_win=True)
        assert amount == pytest.approx(0.02)

    def test_reset(self):
        s = FibonacciStrategy(unit=0.01)
        s.next_bet(1.0, MIN, TARG, EDGE, last_win=False)
        s.reset()
        amount, _ = s.next_bet(1.0, MIN, TARG, EDGE)
        assert amount == pytest.approx(0.01)


# ─────────────────────────────────────────────────────────────────
# make_strategy factory
# ─────────────────────────────────────────────────────────────────

class TestMakeStrategy:
    def test_all_strategy_names_are_creatable(self):
        cfg = {
            "strategy_base_bet":    0.001,
            "strategy_chance":      49.5,
            "strategy_bet_percent": 1.0,
        }
        for name in STRATEGY_NAMES:
            s = make_strategy(name, cfg)
            assert isinstance(s, object)
            amount, chance = s.next_bet(1.0, 0.001, 20.0, 0.03)
            assert amount > 0
            assert 0.01 <= chance <= 99.0

    def test_unknown_name_falls_back_to_all_in(self):
        s = make_strategy("nonexistent_strategy", {})
        assert isinstance(s, AllInStrategy)

    def test_labels_and_names_match(self):
        assert set(STRATEGY_LABELS.keys()) == set(STRATEGY_NAMES)
