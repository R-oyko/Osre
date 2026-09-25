"""Finds and names the beatmaps available to play. Separate from beatmap.py
on purpose: beatmap.py only knows how to parse ONE .osu file's contents,
while BeatmapLibrary is the thing that knows about the Beatmaps/ folder,
.osz archives, and turning filenames into a difficulty-select menu."""

import glob
import os
import zipfile

from beatmap import extract_osz


class BeatmapLibrary:
    """Owns everything about *finding* beatmaps: unzipping .osz mapsets that
    show up in Beatmaps/, listing every .osu difficulty inside them, and
    turning each filename into a readable "Song [Difficulty]" label for the
    select screen."""

    def __init__(self, base_dir):
        self.beatmaps_dir = os.path.join(base_dir, 'Beatmaps')
        self.osu_files = []
        self.difficulty_names = []
        self._scan()

    # --- Discovery -----------------------------------------------------
    def _scan(self):
        """Extracts any not-yet-extracted .osz archives, then collects
        every .osu file under Beatmaps/ (recursively) and builds the
        matching display names."""
        osz_files = [p for p in glob.glob(os.path.join(self.beatmaps_dir, '*.osz')) if os.path.isfile(p)]
        for osz_path in osz_files:
            folder_name = os.path.splitext(os.path.basename(osz_path))[0]
            extract_folder = os.path.join(self.beatmaps_dir, folder_name)
            try:
                extract_osz(osz_path, extract_folder)
            except (PermissionError, OSError, zipfile.BadZipFile) as e:
                print(f"[warn] Skipping '{os.path.basename(osz_path)}': {e}")
                print("       (file may be open in another program, still syncing, or blocked by antivirus/Windows)")

        self.osu_files = sorted(glob.glob(os.path.join(self.beatmaps_dir, '**', '*.osu'), recursive=True))
        if not self.osu_files:
            raise FileNotFoundError(f"No .osu or .osz files found inside {self.beatmaps_dir}")

        self.difficulty_names = [self._display_name(f) for f in self.osu_files]

    # --- Filename -> display name --------------------------------------
    @staticmethod
    def _short_diff_name(path):
        """'Song - Artist [Hard].osu' -> 'Hard'."""
        name = os.path.splitext(os.path.basename(path))[0]
        if '[' in name and name.endswith(']'):
            return name[name.rfind('[') + 1:-1]
        return name

    @staticmethod
    def _song_title_from_filename(path):
        """'Song - Artist [Hard].osu' -> 'Song - Artist'."""
        name = os.path.splitext(os.path.basename(path))[0]
        if '[' in name and name.endswith(']'):
            return name[:name.rfind('[')].strip(' -')
        return name

    def _display_name(self, path):
        """Combines song + difficulty into one label for the select menu."""
        song = self._song_title_from_filename(path)
        diff = self._short_diff_name(path)
        return song if song == diff else f'{song} [{diff}]'

    # --- Access ----------------------------------------------------------
    def __len__(self):
        return len(self.osu_files)

    def path_for(self, index):
        """The .osu file path for the Nth entry in difficulty_names."""
        return self.osu_files[index]
