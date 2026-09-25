"""Static configuration for the whole game: screen size, playfield scaling,
timing windows, and the coordinate transform from osu!pixels to screen
pixels. Nothing here depends on pygame having been initialized yet, so this
module is always safe to import first."""

import math

# --- Window size --------------------------------------------------------
SCREEN_W, SCREEN_H = 1920, 1080

# --- Playfield scaling ---------------------------------------------------
PLAYFIELD_W, PLAYFIELD_H = 512, 384
SCALE = min(SCREEN_W / PLAYFIELD_W, SCREEN_H / PLAYFIELD_H) * 0.8
OFFSET_X = (SCREEN_W - PLAYFIELD_W * SCALE) / 2
OFFSET_Y = (SCREEN_H - PLAYFIELD_H * SCALE) / 2


def to_screen_pos(x, y):
    """Converts an (x, y) in osu!pixel space to actual screen pixels."""
    return (OFFSET_X + x * SCALE, OFFSET_Y + y * SCALE)


# --- Hit-object sizing -----------------------------------------------------
OSU_CIRCLE_RADIUS = 32
CIRCLE_RADIUS = int(OSU_CIRCLE_RADIUS * SCALE)

OSU_SPINNER_RADIUS = 64
SPINNER_RADIUS = int(OSU_SPINNER_RADIUS * SCALE)

# --- Timing windows --------------------------------------------------------
APPROACH_TIME = 1000
HIT_WINDOW = 220
SPINS_NEEDED = 5
EFFECT_DURATION = 400

HOLD_TOLERANCE = CIRCLE_RADIUS * 2.2

APPROACH_CIRCLE_START_SCALE = 3.0

SLIDER_HOLD_LENIENCY = 0.5

# --- Stacking -----------------------------------------------------------
STACK_POSITION_THRESHOLD = 3.0
STACK_TIME_WINDOW = APPROACH_TIME
STACK_OFFSET_RATIO = 0.13


def stack_offset_px(stack_index):
    """Screen-pixel (dx, dy) nudge for an object at the given stack index."""
    if stack_index <= 0:
        return (0.0, 0.0)
    step = CIRCLE_RADIUS * STACK_OFFSET_RATIO
    return (-stack_index * step, -stack_index * step)


# --- Visuals -----------------------------------------------------------
CIRCLE_FILL_ALPHA = 165

COMBO_COLORS = [
    (102, 204, 255),
    (255, 102, 178),
    (153, 255, 153),
    (255, 204, 102),
]
