"""Hit-sound loading. Prefers the beatmap's own hitnormal sample (what real
osu! plays); falls back to a synthesized click if the mapset doesn't ship
one."""

import array
import glob
import math
import os

import pygame


# --- Fallback sound --------------------------------------------------------
def synthesize_hit_sound(frequency=1000.0, duration_ms=55, volume=0.55, sample_rate=44100):
    """Generates a short percussive click from scratch, used whenever the
    beatmap folder doesn't have its own hitnormal sample to load."""
    n_samples = int(sample_rate * duration_ms / 1000)
    amplitude = int(32767 * volume)
    buf = array.array('h')
    for i in range(n_samples):
        t = i / sample_rate
        envelope = (1 - i / n_samples) ** 2  # quick attack, fast decay -> "click" feel
        sample = int(amplitude * envelope * math.sin(2 * math.pi * frequency * t))
        buf.append(sample)
        buf.append(sample)  # stereo
    return pygame.mixer.Sound(buffer=buf.tobytes())


# --- Beatmap-provided sound -------------------------------------------------
def load_hit_sound(beatmap_path):
    """Looks in the beatmap's own folder for a *hitnormal* sample; if none
    exists (or none of them will load), falls back to the synthesized
    click above so the game always has *some* hit sound."""
    folder = os.path.dirname(beatmap_path)
    candidates = []
    for ext in ('wav', 'ogg', 'mp3'):
        candidates += glob.glob(os.path.join(folder, f'*hitnormal*.{ext}'))
    for path in candidates:
        try:
            return pygame.mixer.Sound(path)
        except pygame.error:
            continue
    return synthesize_hit_sound()
