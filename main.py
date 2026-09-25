"""Entry point. Run this file to play -- `python main.py`.

pygame.init()/mixer.init() must happen before anything else touches
pygame.font or pygame.mixer, so this file does that first and only then
imports/creates the Game.
"""

import pygame

# --- pygame setup, before anything else is imported -------------------
pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2)

from game import Game


# --- Program entry point ------------------------------------------------
def main():
    game = Game()
    try:
        game.run()
    except SystemExit:
        pass


if __name__ == '__main__':
    main()
