"""The on-screen HUD, split into the two things it actually tracks:
- HealthBar: hp, damage/heal, whether the player has died
- ScoreBoard: score, combo, max combo, accuracy

Kept as two classes (not one) because they're two different concerns that
happen to both live at the top of the screen -- a slider miss should be
able to change one without the caller having to know about the other.
"""

import pygame

from constants import SCREEN_W
from render_utils import get_font

# --- Lazily-created fonts (see render_utils.get_font for why) --------------
score_font = None
small_font = None


def _fonts():
    global score_font, small_font
    if score_font is None:
        score_font = get_font(None, 56, bold=True)
        small_font = get_font(None, 32)
    return score_font, small_font


# --- Health -----------------------------------------------------------
class HealthBar:
    """Player HP: a 0..max_hp value, plus the white/gray bar drawn for it."""

    def __init__(self, max_hp=100):
        self.max_hp = max_hp
        self.hp = max_hp

    def reset(self):
        """Called when a new beatmap starts."""
        self.hp = self.max_hp

    def damage(self, amount):
        self.hp = max(0, self.hp - amount)

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)

    @property
    def is_dead(self):
        return self.hp <= 0

    def draw(self, surface):
        """Draws the bar across the top of the screen."""
        bar_width = int((SCREEN_W - 40) * (self.hp / self.max_hp))
        pygame.draw.rect(surface, (60, 60, 60), (20, 20, SCREEN_W - 40, 16), border_radius=8)
        pygame.draw.rect(surface, (255, 255, 255), (20, 20, bar_width, 16), border_radius=8)


# --- Score / combo / accuracy ------------------------------------------
class ScoreBoard:
    """Score, current combo, best combo this play, and the running
    hit/judged counts used to compute accuracy."""

    def __init__(self):
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.total_judged = 0
        self.total_hit = 0

    def reset(self):
        """Called when a new beatmap starts."""
        self.__init__()

    @property
    def accuracy(self):
        return (self.total_hit / self.total_judged * 100) if self.total_judged else 100.0

    def register(self, is_good):
        """Updates score/combo bookkeeping for one judged hit-object.
        Returns nothing -- HealthBar.damage/heal is handled by the caller,
        since hp isn't this class's business."""
        self.total_judged += 1
        if is_good:
            self.score += 300
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)
            self.total_hit += 1
        else:
            self.combo = 0

    def draw(self, surface, screen_h):
        """Draws score (top-right), accuracy (below it) and the live combo
        counter (bottom-left)."""
        score_f, small_f = _fonts()
        score_text = score_f.render(f'{self.score:08d}', True, (255, 255, 255))
        surface.blit(score_text, (SCREEN_W - score_text.get_width() - 20, 50))

        acc_text = small_f.render(f'{self.accuracy:.2f}%', True, (255, 255, 255))
        surface.blit(acc_text, (SCREEN_W - acc_text.get_width() - 20, 110))

        combo_text = score_f.render(f'{self.combo}x', True, (255, 255, 255))
        surface.blit(combo_text, (20, screen_h - 70))
