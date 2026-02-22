"""Core module initialization"""

from .api import DuckDiceAPI, CookieExpiredError, RateLimitError
from .config import BotConfig
from .bot import FaucetBot, BotError
from .accounts import Account, AccountManager
from .network import NetworkProfile, NetworkProfileManager, ProfileType, ProxyProtocol, VpnMethod
from .tictactoe import TicTacToeClaimEngine, best_move
from .scheduler import BotScheduler

__all__ = [
    'DuckDiceAPI', 'CookieExpiredError', 'RateLimitError',
    'BotConfig',
    'FaucetBot', 'BotError',
    'Account', 'AccountManager',
    'NetworkProfile', 'NetworkProfileManager', 'ProfileType', 'ProxyProtocol', 'VpnMethod',
    'TicTacToeClaimEngine', 'best_move',
    'BotScheduler',
]
