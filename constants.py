"""Static configuration for the whole game: screen size, playfield scaling,
timing windows, and the coordinate transform from osu!pixels to screen
pixels. Nothing here depends on pygame having been initialized yet, so this
module is always safe to import first."""

import math

# --- Window size --------------------------------------------------------
SCREEN_W, SCREEN_H = 1920, 1080

# --- Playfield scaling ---------------------------------------------------
# osu! beatmaps are authored in a fixed 512x384 "osu!pixel" coordinate
# space. PLAYFIELD_W/H is that space; SCALE/OFFSET_X/Y convert it to fit
# inside our actual window (centered, with a little margin).
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
APPROACH_TIME = 1000        # ms an object is visible before its hit time
HIT_WINDOW = 220            # ms of leeway on either side of a hit time that still counts
SPINS_NEEDED = 5            # full rotations required to clear a spinner
EFFECT_DURATION = 400       # ms the hit/miss pop animation plays for

# How far the mouse/finger can drift from the slider ball and still count
# as "holding" it.
HOLD_TOLERANCE = CIRCLE_RADIUS * 2.2

# How much bigger than the hit circle the approach circle starts (real osu!
# starts noticeably further out than "circle + 2x radius").
APPROACH_CIRCLE_START_SCALE = 3.0

# A slider doesn't need to be held all the way to the very last millisecond
# to count -- real osu! judges you on how much of it you actually tracked.
# Holding at least this fraction of the slider's duration counts as a hit.
SLIDER_HOLD_LENIENCY = 0.5

# --- Stacking -----------------------------------------------------------
# When several circles/sliders land on (near enough) the same spot close
# together in time, real osu! nudges each later one slightly up-left so you
# can see how many are piled there instead of them perfectly overlapping.
STACK_POSITION_THRESHOLD = 3.0  # osu!pixels apart counts as "the same spot"
STACK_TIME_WINDOW = APPROACH_TIME  # only stack objects that'd be visible together
STACK_OFFSET_RATIO = 0.13  # fraction of a circle radius nudged per stack level


def stack_offset_px(stack_index):
    """Screen-pixel (dx, dy) nudge for an object at the given stack index."""
    if stack_index <= 0:
        return (0.0, 0.0)
    step = CIRCLE_RADIUS * STACK_OFFSET_RATIO
    return (-stack_index * step, -stack_index * step)


# --- Visuals -----------------------------------------------------------
# Translucent fill so the number underneath reads clearly no matter how
# bright/saturated the combo color is. Shared by every hit circle AND the
# slider ball/body, so they all look the same amount of "see-through".
CIRCLE_FILL_ALPHA = 165

# The colors combos cycle through, in order, restarting every 4 combos.
COMBO_COLORS = [
    (102, 204, 255),
    (255, 102, 178),
    (153, 255, 153),
    (255, 204, 102),
]
