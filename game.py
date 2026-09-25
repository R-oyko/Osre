"""The Game class ties everything else together: it owns the pygame window,
the state machine (select -> playing -> results/gameover), the currently
active hit-objects, and the HUD/effects/audio objects. Nothing else in the
codebase touches pygame.display or holds a `while True` loop -- this is the
one place that does.
"""

import os

import pygame

from constants import APPROACH_TIME, SCREEN_H, SCREEN_W
from library import BeatmapLibrary
from beatmap import load_beatmap
from hitobjects import Circle, build_hit_objects
from hud import HealthBar, ScoreBoard
from effects import EffectManager
from audio import load_hit_sound
from render_utils import get_font

# --- Game states -------------------------------------------------------
STATE_SELECT = 'select'      # difficulty-picker menu
STATE_PLAYING = 'playing'    # actively playing a beatmap
STATE_RESULTS = 'results'    # cleared the beatmap -- showing score summary
STATE_GAMEOVER = 'gameover'  # hp hit 0 -- showing score summary


class Game:
    # --- Setup -------------------------------------------------------------
    def __init__(self):
        """Creates the window, loads the beatmap library, and sets up all
        the sub-objects (HUD, effects) in their empty/idle state. Nothing
        starts playing until start_beatmap() is called."""
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption('Osre!')
        self.clock = pygame.time.Clock()

        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.library = BeatmapLibrary(base_dir)

        self.big_font = get_font(None, 90, bold=True)
        self.menu_font = get_font(None, 44, bold=True)
        self.small_font = get_font(None, 32)

        self.state = STATE_SELECT
        self.hit_objects = []     # every object in the current beatmap, in time order
        self.active_objects = []  # objects currently visible/judgeable
        self.next_index = 0       # index into hit_objects of the next one to spawn

        self.health = HealthBar()
        self.score = ScoreBoard()
        self.effects = EffectManager()

        self.audio_active = False
        self.hit_sound = None
        self.start_time = 0
        self.elapsed = 0

    # ------------------------------------------------------------------
    # Beatmap lifecycle
    # ------------------------------------------------------------------
    def start_beatmap(self, diff_index):
        """Loads the chosen difficulty, resets the HUD/effects, starts the
        song (if it has one) and enters STATE_PLAYING."""
        beatmap_path = self.library.path_for(diff_index)
        raw_objects, audio_filename = load_beatmap(beatmap_path)
        self.hit_sound = load_hit_sound(beatmap_path)

        self.hit_objects = build_hit_objects(raw_objects)
        self.active_objects = []
        self.next_index = 0

        self.health.reset()
        self.score.reset()
        self.effects.clear()

        self.audio_active = False
        if audio_filename:
            audio_path = os.path.join(os.path.dirname(beatmap_path), audio_filename)
            try:
                pygame.mixer.music.load(audio_path)
                pygame.mixer.music.play()
                self.audio_active = True
            except pygame.error as e:
                print(f"[warn] Could not load audio '{audio_filename}': {e} (playing without music)")

        self.start_time = pygame.time.get_ticks()
        self.elapsed = 0
        self.state = STATE_PLAYING

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------
    def try_click(self, mouse_pos):
        """Called on every click/tap/Z/X press while playing. Offers the
        click to the first active object that can be click-started (circles
        and slider heads -- spinners just react to held input, not clicks)
        and stops at the first one that accepts it."""
        for obj in self.active_objects[:]:
            if not hasattr(obj, 'try_hit'):
                continue  # spinners aren't click-started
            judgement = obj.try_hit(mouse_pos, self.elapsed)
            if judgement is None:
                continue

            if isinstance(obj, Circle):
                self.active_objects.remove(obj)
                self._judge(judgement)  # scores/heals/plays the hit sound
            else:
                # Slider head: sound + hit pop now, but leave the slider
                # active -- its body/ball keep being judged every frame,
                # and scoring only happens once the whole slider resolves.
                if self.hit_sound:
                    self.hit_sound.play()
                self.effects.spawn(judgement.pos, judgement.color, 'hit')
            return

    def handle_events(self):
        """Pumps the pygame event queue: quitting, difficulty selection on
        the menu, restart/quit on the summary screens, and click/tap input
        while playing."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit

            if event.type == pygame.KEYDOWN:
                if self.state == STATE_SELECT:
                    if pygame.K_1 <= event.key <= pygame.K_9:
                        idx = event.key - pygame.K_1
                        if idx < len(self.library):
                            self.start_beatmap(idx)
                    elif event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        raise SystemExit

                elif self.state in (STATE_RESULTS, STATE_GAMEOVER):
                    if event.key == pygame.K_r:
                        self.state = STATE_SELECT
                    elif event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        raise SystemExit

                elif self.state == STATE_PLAYING:
                    if event.key == pygame.K_ESCAPE:
                        pygame.mixer.music.stop()
                        self.audio_active = False
                        self.active_objects = []
                        self.state = STATE_SELECT

            if self.state == STATE_PLAYING:
                is_click = (
                    event.type == pygame.MOUSEBUTTONDOWN
                    or (event.type == pygame.KEYDOWN and event.key in (pygame.K_z, pygame.K_x))
                )
                if is_click:
                    self.try_click(pygame.mouse.get_pos())

    # ------------------------------------------------------------------
    # Judging
    # ------------------------------------------------------------------
    def _judge(self, judgement):
        """Applies one resolved Judgement to score/combo, hp, the hit sound
        and the hit/miss effect pop, then checks for game over."""
        self.score.register(judgement.success)
        if judgement.success:
            self.health.heal(2)
            if self.hit_sound:
                self.hit_sound.play()
            self.effects.spawn(judgement.pos, judgement.color, 'hit')
        else:
            self.health.damage(8)
            self.effects.spawn(judgement.pos, judgement.color, 'miss')

        if self.health.is_dead:
            pygame.mixer.music.stop()
            self.state = STATE_GAMEOVER

    # ------------------------------------------------------------------
    # Per-frame update + draw
    # ------------------------------------------------------------------
    def _update_elapsed(self):
        """Recomputes self.elapsed -- from the song's playback position
        when there's music, otherwise from the wall clock."""
        if self.audio_active:
            music_pos = pygame.mixer.music.get_pos()
            self.elapsed = music_pos if music_pos >= 0 else pygame.time.get_ticks() - self.start_time
        else:
            self.elapsed = pygame.time.get_ticks() - self.start_time

    def _spawn_due_objects(self):
        """Moves any hit_objects whose approach window has begun from the
        upcoming queue into active_objects."""
        while (self.next_index < len(self.hit_objects)
               and self.hit_objects[self.next_index].time - APPROACH_TIME <= self.elapsed):
            self.active_objects.append(self.hit_objects[self.next_index])
            self.next_index += 1

    def _step_playing(self):
        """One frame of actual gameplay: spawn due objects, let each active
        object draw + judge itself, draw the HUD/effects on top, and check
        whether the beatmap is finished."""
        self._update_elapsed()
        self._spawn_due_objects()

        mouse_held = pygame.mouse.get_pressed()[0]
        keys_held = pygame.key.get_pressed()
        z_or_x_held = keys_held[pygame.K_z] or keys_held[pygame.K_x]
        holding_input = mouse_held or z_or_x_held
        mouse_pos = pygame.mouse.get_pos()

        for obj in reversed(self.active_objects[:]):
            judgement = obj.step(self.screen, self.elapsed, mouse_pos, holding_input)
            if judgement is not None:
                self.active_objects.remove(obj)
                self._judge(judgement)

        self.effects.draw(self.screen)
        self.health.draw(self.screen)
        self.score.draw(self.screen, SCREEN_H)

        if self.next_index >= len(self.hit_objects) and not self.active_objects:
            pygame.mixer.music.stop()
            self.state = STATE_RESULTS

    # ------------------------------------------------------------------
    # Screens
    # ------------------------------------------------------------------
    def _draw_select_screen(self):
        """The difficulty-picker menu."""
        title = self.big_font.render('Osre', True, (255, 255, 255))
        self.screen.blit(title, title.get_rect(center=(SCREEN_W // 2, 180)))

        hint = self.small_font.render('Press a number key to choose a difficulty', True, (200, 200, 200))
        self.screen.blit(hint, hint.get_rect(center=(SCREEN_W // 2, 260)))

        for i, name in enumerate(self.library.difficulty_names):
            line = self.menu_font.render(f'{i + 1}. {name}', True, (255, 255, 255))
            self.screen.blit(line, line.get_rect(center=(SCREEN_W // 2, 350 + i * 60)))

    def _draw_summary_screen(self, title_text, title_color, hint_text):
        """Shared layout for both the results (Clear!) and game-over
        screens -- only the title/color/hint text differ between them."""
        title = self.big_font.render(title_text, True, title_color)
        self.screen.blit(title, title.get_rect(center=(SCREEN_W // 2, 220)))

        lines = [
            f'Score: {self.score.score:08d}',
            f'Max Combo: {self.score.max_combo}x',
            f'Accuracy: {self.score.accuracy:.2f}%',
        ]
        for i, line in enumerate(lines):
            text = self.menu_font.render(line, True, (255, 255, 255))
            self.screen.blit(text, text.get_rect(center=(SCREEN_W // 2, 380 + i * 60)))

        hint = self.small_font.render(hint_text, True, (200, 200, 200))
        self.screen.blit(hint, hint.get_rect(center=(SCREEN_W // 2, 600)))

    def draw(self):
        """Top-level per-frame draw: clears the screen, dims it slightly,
        then delegates to whichever screen matches the current state."""
        self.screen.fill((15, 15, 20))
        dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 120))
        self.screen.blit(dim, (0, 0))

        if self.state == STATE_SELECT:
            self._draw_select_screen()
        elif self.state == STATE_PLAYING:
            self._step_playing()
        elif self.state == STATE_RESULTS:
            self._draw_summary_screen('Clear!', (150, 255, 180),
                                       'Press R to pick another difficulty  |  ESC to quit')
        elif self.state == STATE_GAMEOVER:
            self._draw_summary_screen('Game Over', (255, 80, 80),
                                       'Press R to try again  |  ESC to quit')

        pygame.display.update()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self):
        """The actual `while True` game loop: handle input, draw a frame,
        cap at 60 FPS, repeat."""
        while True:
            self.handle_events()
            self.draw()
            self.clock.tick(60)