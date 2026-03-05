"""
FaucetBot unit tests.

Tests state machine and basic structure.
"""
from core.bot import BotState


def test_state_enum_values():
    """BotState enum has expected values."""
    assert BotState.FARMING.value == 1
    assert BotState.CASHOUT_WAIT.value == 2
    assert BotState.POST_CASHOUT.value == 3
    assert BotState.STOPPED.value == 4


def test_state_name_to_value_mapping():
    """All BotState names are accessible."""
    states = {
        BotState.FARMING: "farming",
        BotState.CASHOUT_WAIT: "cashout_wait",
        BotState.POST_CASHOUT: "post_cashout",
        BotState.STOPPED: "stopped",
    }
    for state, name in states.items():
        assert state.name.lower() == name or state.name.replace("_", "").lower() == name.replace("_", "")
