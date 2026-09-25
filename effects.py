"""The little ring/X pop that plays at a hit-object's position when it's
judged. One Effect instance per pop; EffectManager owns the list of
currently-animating ones."""

import pygame

from constants import CIRCLE_RADIUS, EFFECT_DURATION
from render_utils import miss_font


# --- A single pop animation -------------------------------------------------
class Effect:
    """One hit-ring or miss-X animation, from the moment it's spawned until
    it fades out EFFECT_DURATION ms later."""

    def __init__(self, pos, color, kind):
        self.pos = pos
        self.color = color
        self.kind = kind
        self.start_ms = pygame.time.get_ticks()

    @property
    def age(self):
        """Milliseconds since this effect was spawned."""
        return pygame.time.get_ticks() - self.start_ms

    @property
    def is_expired(self):
        return self.age > EFFECT_DURATION

    @property
    def progress(self):
        """0.0 (just spawned) to 1.0 (about to expire)."""
        return self.age / EFFECT_DURATION

    def draw(self, surface):
        t = self.progress
        alpha = int(255 * (1 - t))

        if self.kind == 'hit':
            radius = int(CIRCLE_RADIUS + t * 30)
            ring_surface = pygame.Surface((radius * 2 + 10, radius * 2 + 10), pygame.SRCALPHA)
            pygame.draw.circle(ring_surface, (*self.color, alpha),
                                (radius + 5, radius + 5), radius, 5)
            surface.blit(ring_surface, (self.pos[0] - radius - 5, self.pos[1] - radius - 5))
        else:
            text = miss_font().render('X', True, (255, 60, 60))
            text.set_alpha(alpha)
            offset_y = -20 * t
            surface.blit(text, text.get_rect(center=(self.pos[0], self.pos[1] + offset_y)))


# --- The collection of all currently-playing effects ------------------------
class EffectManager:
    """Owns every Effect that's still animating and draws/prunes them each
    frame, so the rest of the game never has to manage that list itself."""

    def __init__(self):
        self.effects = []

    def spawn(self, pos, color, kind):
        """Starts a new hit/miss pop at pos. Does nothing if pos is None
        (e.g. a judgement that has no meaningful on-screen location)."""
        if pos is not None:
            self.effects.append(Effect(pos, color, kind))

    def clear(self):
        """Wipes every in-flight effect -- used when a new beatmap starts."""
        self.effects = []

    def draw(self, surface):
        """Draws every active effect and removes any that have finished."""
        for eff in self.effects[:]:
            if eff.is_expired:
                self.effects.remove(eff)
                continue
            eff.draw(surface)
