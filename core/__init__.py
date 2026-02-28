"""Core module"""

from .api import DuckDiceAPI, CookieExpiredError, RateLimitError
from .config import BotConfig
from .bot import FaucetBot, BotError, BotState
from .tictactoe import TicTacToeClaimEngine
from .scheduler import BotScheduler
from .version import APP_NAME, APP_VERSION, TAGLINE
from .updater import UpdateChecker, UpdateInfo
from .browser_session import BrowserSession, state_file_exists, delete_state_file
from .cookie_extractor import extract_best, has_browser_cookie3
from .strategies import (
    BettingStrategy, AllInStrategy, MartingaleStrategy,
    ReverseMartingaleStrategy, FixedPercentageStrategy,
    DAlembert, FibonacciStrategy,
    STRATEGIES, STRATEGY_LABELS, STRATEGY_NAMES, make_strategy,
)

__all__ = [
    'DuckDiceAPI', 'CookieExpiredError', 'RateLimitError',
    'BotConfig',
    'FaucetBot', 'BotError', 'BotState',
    'TicTacToeClaimEngine',
    'BotScheduler',
    'APP_NAME', 'APP_VERSION', 'TAGLINE',
    'UpdateChecker', 'UpdateInfo',
    'BrowserSession', 'state_file_exists', 'delete_state_file',
    'extract_best', 'has_browser_cookie3',
    'BettingStrategy', 'AllInStrategy', 'MartingaleStrategy',
    'ReverseMartingaleStrategy', 'FixedPercentageStrategy',
    'DAlembert', 'FibonacciStrategy',
    'STRATEGIES', 'STRATEGY_LABELS', 'STRATEGY_NAMES', 'make_strategy',
]
