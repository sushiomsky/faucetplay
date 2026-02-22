"""Shared theme constants for the FaucetPlay GUI."""
import platform

# Cross-platform font selection
_sys = platform.system()
if _sys == "Windows":
    _FONT = "Segoe UI"
elif _sys == "Darwin":
    _FONT = "SF Pro Display"
else:
    _FONT = "Ubuntu"

if _sys == "Windows":
    _MONO = "Consolas"
elif _sys == "Darwin":
    _MONO = "Menlo"
else:
    _MONO = "DejaVu Sans Mono"

# Main palette
BG        = "#1a1a2e"
BG2       = "#16213e"
BG3       = "#0f3460"
BG_CARD   = "#1e2340"   # slightly lighter card background
ACCENT    = "#e94560"
ACCENT2   = "#f5a623"
TEXT      = "#eaeaea"
TEXT_DIM  = "#888888"
GREEN     = "#27ae60"
RED       = "#e74c3c"
YELLOW    = "#f39c12"
BLUE      = "#2980b9"
TEAL      = "#1abc9c"
GOLD      = "#f0c040"   # win / cashout highlight

# Status colours
STATUS_RUNNING   = GREEN
STATUS_PAUSED    = YELLOW
STATUS_IDLE      = TEXT_DIM
STATUS_ERROR     = RED
STATUS_SCHEDULED = BLUE

# Fonts  (family, size, weight)
FONT_H1       = (_FONT, 20, "bold")
FONT_H2       = (_FONT, 14, "bold")
FONT_H3       = (_FONT, 12, "bold")
FONT_BODY     = (_FONT, 11)
FONT_SMALL    = (_FONT, 9)
FONT_MONO     = (_MONO, 10)
FONT_CARD_VAL = (_FONT, 18, "bold")

# Corner radii
CORNER_SM = 6
CORNER_MD = 10
CORNER_LG = 14

# Animation interval (ms)
ANIM_MS = 80

# Widget sizing
BTN_H      = 36
SIDEBAR_W  = 220
CARD_PAD   = 12
