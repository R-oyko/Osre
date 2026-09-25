"""Stateless drawing helpers shared by Circle/Slider/Spinner. Fonts are
created lazily on first use (rather than at import time) so this module can
be imported before pygame.font has anything to work with."""

import math

import pygame

from constants import CIRCLE_FILL_ALPHA

# --- Lazy font cache ---------------------------------------------------
_fonts = {}


def get_font(name, size, bold=False):
    """Lazily creates and caches a SysFont so every caller shares the same
    instance instead of re-rendering a fresh font object every frame."""
    key = (name, size, bold)
    if key not in _fonts:
        _fonts[key] = pygame.font.SysFont(name, size, bold=bold)
    return _fonts[key]


def number_font():
    """Font used for the big number drawn on top of each hit object."""
    return get_font(None, 60, bold=True)


def miss_font():
    """Font used for the 'X' miss-effect popup."""
    return get_font(None, 44, bold=True)


def small_font():
    """Font used for small in-play labels (e.g. spinner rotation count)."""
    return get_font(None, 32)


# --- Hit-circle rendering ------------------------------------------------
def draw_hit_circle(surface, pos, radius, color):
    """The translucent, white-rimmed circle used for both circle hit-objects
    AND the slider ball -- keeping this in one place is exactly what keeps
    their transparency in sync."""
    pad = radius + 4
    temp = pygame.Surface((pad * 2, pad * 2), pygame.SRCALPHA)
    center = (pad, pad)
    pygame.draw.circle(temp, (255, 255, 255, 255), center, pad)
    pygame.draw.circle(temp, (*color, CIRCLE_FILL_ALPHA), center, radius)
    surface.blit(temp, (pos[0] - pad, pos[1] - pad))


def draw_outlined_number(surface, text, pos, text_color=(255, 255, 255), outline_color=(0, 0, 0)):
    """Draws the hit-object number with a dark outline so it stays readable
    regardless of the combo color or how see-through the circle is."""
    font = number_font()
    outline = font.render(text, True, outline_color)
    for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, -2), (-2, 2), (2, 2)):
        surface.blit(outline, outline.get_rect(center=(pos[0] + ox, pos[1] + oy)))
    main = font.render(text, True, text_color)
    surface.blit(main, main.get_rect(center=pos))


# --- Slider body rendering -------------------------------------------------
def draw_thick_path(surface, points, radius, fill_color):
    """Stamps a thick line (white outline + colored fill) along a list of
    points, by repeatedly drawing circles walked along each segment. Used
    once, offscreen, to build a slider's body -- see build_slider_body_cache
    below."""
    if len(points) < 2:
        return

    def stamp(color, r):
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            dist = math.dist((x1, y1), (x2, y2))
            steps = max(1, int(dist / 4))
            for s in range(steps + 1):
                t = s / steps
                x = x1 + (x2 - x1) * t
                y = y1 + (y2 - y1) * t
                pygame.draw.circle(surface, color, (x, y), r)

    stamp((255, 255, 255), radius + 6)
    stamp(fill_color, radius)


def build_slider_body_cache(screen_points, radius, fill_color):
    """Pre-renders a slider's body onto its own small surface once, instead
    of re-stamping every circle along the curve on every single frame. That
    per-frame re-stamping was the main reason sliders felt choppy/laggy
    instead of smooth. Returns (surface, top_left_screen_pos) to blit each
    frame, or None if there weren't enough points to draw anything."""
    if len(screen_points) < 2:
        return None

    pad = int(radius) + 8
    xs = [p[0] for p in screen_points]
    ys = [p[1] for p in screen_points]
    min_x, max_x = min(xs) - pad, max(xs) + pad
    min_y, max_y = min(ys) - pad, max(ys) + pad
    width = max(1, int(max_x - min_x))
    height = max(1, int(max_y - min_y))

    surface = pygame.Surface((width, height), pygame.SRCALPHA)
    local_points = [(x - min_x, y - min_y) for x, y in screen_points]
    draw_thick_path(surface, local_points, radius, fill_color)
    surface.set_alpha(CIRCLE_FILL_ALPHA)
    return surface, (min_x, min_y)


# --- Slider reverse arrow --------------------------------------------------
def draw_reverse_arrow(surface, tip_pos, point_toward, size, color=(255, 255, 255)):
    """Draws the little triangle that tells the player a repeat slider is
    about to bounce back, pointing from tip_pos toward point_toward."""
    dx = point_toward[0] - tip_pos[0]
    dy = point_toward[1] - tip_pos[1]
    dist = math.hypot(dx, dy) or 1
    dx, dy = dx / dist, dy / dist
    px, py = -dy, dx

    front = (tip_pos[0] + dx * size, tip_pos[1] + dy * size)
    back_left = (tip_pos[0] - dx * size * 0.6 + px * size * 0.8,
                 tip_pos[1] - dy * size * 0.6 + py * size * 0.8)
    back_right = (tip_pos[0] - dx * size * 0.6 - px * size * 0.8,
                  tip_pos[1] - dy * size * 0.6 - py * size * 0.8)
    pygame.draw.polygon(surface, color, [front, back_left, back_right])
