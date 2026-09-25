"""One class per hit-object type. Each object owns the state that used to
live in the global `runtime` dict (holding, held_time, rotations, ...) and
knows how to draw and judge itself for one frame via `step()`.

`step()` draws the object for this frame and returns a Judgement the moment
it's fully resolved (hit or missed), or None while it's still active -- this
mirrors exactly what the old per-frame draw loop did, just moved onto the
object instead of scattered across a 200-line for-loop.
"""

import math
from collections import namedtuple

import pygame

from constants import (
    APPROACH_CIRCLE_START_SCALE, APPROACH_TIME, CIRCLE_RADIUS, COMBO_COLORS,
    HIT_WINDOW, HOLD_TOLERANCE, SLIDER_HOLD_LENIENCY, SPINNER_RADIUS,
    SPINS_NEEDED, STACK_POSITION_THRESHOLD, STACK_TIME_WINDOW,
    stack_offset_px, to_screen_pos,
)
from render_utils import (
    build_slider_body_cache, draw_hit_circle, draw_outlined_number,
    draw_reverse_arrow, small_font,
)

Judgement = namedtuple('Judgement', ['success', 'pos', 'color'])


# --- Shared base -----------------------------------------------------------
class HitObject:
    """Fields and behavior every hit-object type has: a position, a time,
    its combo number/color, and how stacking nudges its on-screen position."""

    def __init__(self, x, y, time, number, color, new_combo=False):
        self.x = x
        self.y = y
        self.time = time
        self.number = number
        self.color = color
        self.new_combo = new_combo
        self.stack_index = 0

    @property
    def screen_pos(self):
        """Where this object's origin point is on screen right now,
        including the stacking nudge."""
        sx, sy = to_screen_pos(self.x, self.y)
        dx, dy = stack_offset_px(self.stack_index)
        return (sx + dx, sy + dy)


# --- Circle --------------------------------------------------------------
class Circle(HitObject):
    """A single click target: draw the approach circle shrinking in, and
    judge a miss if it's never clicked in time."""

    def try_hit(self, mouse_pos, elapsed):
        """Called when the player clicks/taps. Returns a Judgement if this
        click lands on the circle within its hit window, else None."""
        pos = self.screen_pos
        if math.dist(mouse_pos, pos) <= CIRCLE_RADIUS and abs(elapsed - self.time) <= HIT_WINDOW:
            return Judgement(True, pos, self.color)
        return None

    def step(self, surface, elapsed, mouse_pos, holding_input):
        """Draws the circle + approach ring for this frame, and returns a
        miss Judgement once it's past its hit window and still unclicked."""
        pos = self.screen_pos
        time_until_hit = self.time - elapsed
        progress = max(0, min(1, time_until_hit / APPROACH_TIME))
        approach_radius = CIRCLE_RADIUS + progress * CIRCLE_RADIUS * APPROACH_CIRCLE_START_SCALE

        draw_hit_circle(surface, pos, CIRCLE_RADIUS, self.color)
        pygame.draw.circle(surface, (255, 255, 255), pos, approach_radius, 6)
        draw_outlined_number(surface, str(self.number), pos)

        if time_until_hit < -HIT_WINDOW:
            return Judgement(False, pos, self.color)
        return None


# --- Slider ----------------------------------------------------------------
class Slider(HitObject):
    """A click-and-hold-and-follow object: a head circle, a curved body,
    a ball that travels the curve (back and forth for repeat sliders), and
    a judgement based on how much of that travel was actually tracked."""

    def __init__(self, x, y, time, number, color, new_combo, *, end_time, points,
                 path_points, path_cum_lengths, path_length, slides, duration_per_slide):
        super().__init__(x, y, time, number, color, new_combo)
        # --- Shape/timing data, computed once by beatmap.py -----------
        self.end_time = end_time
        self.points = points
        self.path_points = path_points or points
        self.path_cum_lengths = path_cum_lengths
        self.path_length = path_length
        self.slides = slides
        self.duration_per_slide = duration_per_slide

        # --- Per-play state (used to live in the global `runtime` dict) --
        self.body_cache = None
        self.head_hit = False
        self.holding = False
        self.ok = False
        self.held_time = 0.0
        self.last_ms = time

    # --- Curve math ------------------------------------------------------
    def position_at(self, t):
        """Where the slider ball is (in osu!pixel space) at elapsed time t,
        walking the pre-sampled curve at constant speed and bouncing back
        and forth for repeat sliders."""
        duration = self.duration_per_slide
        path = self.path_points
        cum = self.path_cum_lengths
        total_len = self.path_length

        if duration <= 0 or len(path) < 2 or not cum or total_len <= 0:
            return path[0] if path else self.points[0]

        time_into = t - self.time
        slide_num = int(time_into // duration)
        slide_progress = (time_into % duration) / duration
        if slide_num % 2 == 1:
            slide_progress = 1 - slide_progress

        target_dist = max(0.0, min(total_len, slide_progress * total_len))

        lo, hi = 0, len(cum) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if cum[mid] < target_dist:
                lo = mid + 1
            else:
                hi = mid
        i = max(1, lo)

        seg_len = cum[i] - cum[i - 1]
        seg_t = (target_dist - cum[i - 1]) / seg_len if seg_len > 0 else 0
        seg_t = max(0.0, min(1.0, seg_t))
        p0, p1 = path[i - 1], path[i]
        return (p0[0] + (p1[0] - p0[0]) * seg_t, p0[1] + (p1[1] - p0[1]) * seg_t)

    def _reverse_arrow_endpoint(self, t):
        """Which end ('start'/'end') should currently show the "bounce
        back" reverse arrow, or None if there's no upcoming reverse."""
        if self.slides <= 1 or self.duration_per_slide <= 0:
            return None
        time_into = max(0, t - self.time)
        slide_num = int(time_into // self.duration_per_slide)
        if slide_num >= self.slides - 1:
            return None
        return 'end' if slide_num % 2 == 0 else 'start'

    # --- Input -----------------------------------------------------------
    def try_hit(self, mouse_pos, elapsed):
        """Called when the player clicks/taps. Starts tracking the slider
        if this lands on the head circle within its hit window; returns
        None (and does nothing) if the head was already hit."""
        if self.head_hit:
            return None
        pos = self.screen_pos
        if math.dist(mouse_pos, pos) <= CIRCLE_RADIUS and abs(elapsed - self.time) <= HIT_WINDOW:
            self.head_hit = True
            self.holding = True
            self.ok = True
            self.held_time = 0.0
            self.last_ms = self.time
            return Judgement(True, pos, self.color)
        return None

    # --- Per-frame draw + judge -------------------------------------------
    def step(self, surface, elapsed, mouse_pos, holding_input):
        """Draws the body, head, reverse arrow and ball for this frame,
        updates how much of the slider has been tracked, and returns the
        final Judgement once elapsed reaches end_time."""
        stack_dx, stack_dy = stack_offset_px(self.stack_index)
        screen_points = [(sx + stack_dx, sy + stack_dy)
                          for sx, sy in (to_screen_pos(px, py) for px, py in self.path_points)]

        if self.body_cache is None:
            self.body_cache = build_slider_body_cache(screen_points, CIRCLE_RADIUS, self.color)
        if self.body_cache:
            body_surface, body_topleft = self.body_cache
            surface.blit(body_surface, body_topleft)

        start_pos = self.screen_pos
        draw_hit_circle(surface, start_pos, CIRCLE_RADIUS, self.color)
        draw_outlined_number(surface, str(self.number), start_pos)

        active_end = self._reverse_arrow_endpoint(max(elapsed, self.time))
        if active_end == 'end':
            end_pos = screen_points[-1]
            toward = screen_points[-2] if len(screen_points) > 1 else start_pos
            draw_reverse_arrow(surface, end_pos, toward, CIRCLE_RADIUS * 0.5)
        elif active_end == 'start':
            toward = screen_points[1] if len(screen_points) > 1 else start_pos
            draw_reverse_arrow(surface, start_pos, toward, CIRCLE_RADIUS * 0.5)

        time_until_hit = self.time - elapsed
        if time_until_hit > -HIT_WINDOW:
            approach_progress = max(0, min(1, time_until_hit / APPROACH_TIME))
            approach_radius = CIRCLE_RADIUS + approach_progress * CIRCLE_RADIUS * APPROACH_CIRCLE_START_SCALE
            pygame.draw.circle(surface, (255, 255, 255), start_pos, approach_radius, 6)

        if elapsed >= self.time:
            raw_x, raw_y = to_screen_pos(*self.position_at(elapsed))
            ball_pos = (raw_x + stack_dx, raw_y + stack_dy)

            leash_surface = pygame.Surface(
                (int(HOLD_TOLERANCE * 2 + 8), int(HOLD_TOLERANCE * 2 + 8)), pygame.SRCALPHA
            )
            pygame.draw.circle(
                leash_surface, (255, 255, 255, 90),
                (leash_surface.get_width() // 2, leash_surface.get_height() // 2),
                HOLD_TOLERANCE, 6
            )
            surface.blit(leash_surface, (ball_pos[0] - leash_surface.get_width() / 2,
                                          ball_pos[1] - leash_surface.get_height() / 2))

            if self.holding:
                dt = max(0.0, elapsed - self.last_ms)
                self.last_ms = elapsed
                currently_valid = holding_input and math.dist(mouse_pos, ball_pos) <= HOLD_TOLERANCE
                if currently_valid:
                    self.held_time += dt
                self.ok = currently_valid

                glow_color = (80, 255, 120) if currently_valid else (255, 70, 70)
                pulse = 6 + 4 * math.sin(pygame.time.get_ticks() / 80)
                pygame.draw.circle(surface, glow_color, ball_pos, CIRCLE_RADIUS + 8 + pulse, 4)

            draw_hit_circle(surface, ball_pos, CIRCLE_RADIUS, self.color)

        if elapsed >= self.end_time:
            total_duration = max(1.0, self.end_time - self.time)
            held_ratio = self.held_time / total_duration
            success = self.holding and held_ratio >= SLIDER_HOLD_LENIENCY
            end_raw = to_screen_pos(*self.position_at(self.end_time))
            end_pos = (end_raw[0] + stack_dx, end_raw[1] + stack_dy)
            return Judgement(success, end_pos, self.color)

        return None


# --- Spinner ---------------------------------------------------------------
class Spinner(HitObject):
    """A hold-and-rotate-the-mouse-around-the-center object; judged purely
    on whether SPINS_NEEDED full rotations were completed in time."""

    def __init__(self, x, y, time, number, color, new_combo, end_time):
        super().__init__(x, y, time, number, color, new_combo)
        self.end_time = end_time
        self.rotations = 0.0
        self.last_angle = None

    def step(self, surface, elapsed, mouse_pos, holding_input):
        """Draws the spinner ring, accumulates rotation progress while the
        player holds input inside its active window, and returns the final
        Judgement once elapsed reaches end_time."""
        center = to_screen_pos(self.x, self.y)
        pygame.draw.circle(surface, self.color, center, SPINNER_RADIUS, 6)

        if elapsed >= self.time and holding_input:
            dx = mouse_pos[0] - center[0]
            dy = mouse_pos[1] - center[1]
            angle = math.atan2(dy, dx)
            if self.last_angle is not None:
                delta = angle - self.last_angle
                if delta > math.pi:
                    delta -= 2 * math.pi
                elif delta < -math.pi:
                    delta += 2 * math.pi
                self.rotations += abs(delta) / (2 * math.pi)
            self.last_angle = angle

            spin_glow = (80, 255, 120) if self.rotations >= SPINS_NEEDED else (255, 255, 255)
            pygame.draw.circle(surface, spin_glow, center, SPINNER_RADIUS + 10, 3)
        else:
            self.last_angle = None

        spin_text = small_font().render(f'{self.rotations:.1f} / {SPINS_NEEDED}', True, (255, 255, 255))
        surface.blit(spin_text, spin_text.get_rect(center=(center[0], center[1] + SPINNER_RADIUS + 30)))

        if elapsed >= self.end_time:
            return Judgement(self.rotations >= SPINS_NEEDED, center, self.color)
        return None


# --- Building a play session's hit objects ----------------------------------
def compute_stacking(objects):
    """Assigns each circle/slider a stack_index (0, 1, 2, ...) based on how
    many earlier objects sit right on top of it in time and space.
    Spinners are never stacked (they're always centered)."""
    prev_pos = None
    prev_time = None
    stack_index = 0
    for obj in objects:
        if isinstance(obj, Spinner):
            obj.stack_index = 0
            continue
        pos = (obj.x, obj.y)
        if (prev_pos is not None
                and math.dist(pos, prev_pos) <= STACK_POSITION_THRESHOLD
                and obj.time - prev_time <= STACK_TIME_WINDOW):
            stack_index += 1
        else:
            stack_index = 0
        obj.stack_index = stack_index
        prev_pos, prev_time = pos, obj.time


def build_hit_objects(raw_objects):
    """Turns beatmap.py's raw dicts into Circle/Slider/Spinner instances,
    assigning combo numbers/colors along the way (a new combo starts at the
    first object and at every object with new_combo=True), then computes
    stacking across the whole list."""
    objects = []
    combo_index = -1
    number_in_combo = 0

    for i, raw in enumerate(raw_objects):
        if i == 0 or raw.get('new_combo'):
            combo_index += 1
            number_in_combo = 1
        else:
            number_in_combo += 1
        color = COMBO_COLORS[combo_index % len(COMBO_COLORS)]
        number = number_in_combo
        new_combo = raw.get('new_combo', False)

        if raw['type'] == 'circle':
            obj = Circle(raw['x'], raw['y'], raw['time'], number, color, new_combo)
        elif raw['type'] == 'slider':
            obj = Slider(
                raw['x'], raw['y'], raw['time'], number, color, new_combo,
                end_time=raw['end_time'], points=raw['points'],
                path_points=raw.get('path_points'), path_cum_lengths=raw.get('path_cum_lengths'),
                path_length=raw.get('path_length', 0), slides=raw['slides'],
                duration_per_slide=raw['duration_per_slide'],
            )
        elif raw['type'] == 'spinner':
            obj = Spinner(raw['x'], raw['y'], raw['time'], number, color, new_combo, raw['end_time'])
        else:
            continue

        objects.append(obj)

    compute_stacking(objects)
    return objects
