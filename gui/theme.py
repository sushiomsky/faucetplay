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

# Main palette — muted neutral dark theme
BG        = "#1a1a1a"      # deep black
BG2       = "#2a2a2a"      # dark grey
BG3       = "#3a3a3a"      # medium grey
BG_CARD   = "#242424"      # slightly lighter card background
ACCENT    = "#6b8cae"      # muted blue-grey
ACCENT2   = "#8a9aaa"      # lighter grey-blue
TEXT      = "#e8e8e8"      # soft white
TEXT_DIM  = "#777777"      # dim grey
GREEN     = "#6fa676"      # muted green
RED       = "#c97c7c"      # muted red
YELLOW    = "#d9a85c"      # muted gold
BLUE      = "#5a7a8a"      # muted blue
TEAL      = "#5a8a8a"      # muted teal
GOLD      = "#c9a65c"      # muted gold for highlights

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
