import os
import random

from .audio_utils import AUDIO_FILE_EXTENSIONS


class AudioPlaylistController:
    def __init__(self, current_file=None):
        self.audio_files = []
        self.current_index = -1
        self.current_file = current_file

    def set_playlist(self, file_paths, current_file=None):
        self.audio_files = self.filter_audio_files(file_paths)
        self.current_file = current_file or self.current_file

        if not self.audio_files:
            self.current_index = -1
            self.current_file = None
            return -1

        if self.current_file in self.audio_files:
            self.current_index = self.audio_files.index(self.current_file)
        else:
            self.current_index = 0
            self.current_file = self.audio_files[0]

        return self.current_index

    def filter_audio_files(self, file_paths):
        valid_files = []
        for file_path in file_paths:
            if not os.path.exists(file_path):
                continue
            if os.path.splitext(file_path)[1].lower() not in AUDIO_FILE_EXTENSIONS:
                continue
            valid_files.append(file_path)
        return valid_files

    def set_current_index(self, index):
        if 0 <= index < len(self.audio_files):
            self.current_index = index
            self.current_file = self.audio_files[index]
            return True
        return False

    def get_current_file(self):
        if 0 <= self.current_index < len(self.audio_files):
            return self.audio_files[self.current_index]
        return None

    def get_next_index(self, play_mode):
        return self._get_adjacent_index(play_mode, direction=1)

    def get_previous_index(self, play_mode):
        return self._get_adjacent_index(play_mode, direction=-1)

    def _get_adjacent_index(self, play_mode, direction):
        if not self.audio_files:
            return -1

        if self.current_index < 0 or self.current_index >= len(self.audio_files):
            self.current_index = 0
            self.current_file = self.audio_files[0]

        if play_mode == 1 and len(self.audio_files) > 1:
            candidates = list(range(len(self.audio_files)))
            candidates.remove(self.current_index)
            return random.choice(candidates)

        step = -1 if direction < 0 else 1
        return (self.current_index + step) % len(self.audio_files)

    def remove_at(self, index):
        if index < 0 or index >= len(self.audio_files):
            return {'removed_current': False, 'next_index': self.current_index}

        removed_current = index == self.current_index
        self.audio_files.pop(index)

        if not self.audio_files:
            self.current_index = -1
            self.current_file = None
            return {'removed_current': removed_current, 'next_index': -1}

        if index < self.current_index:
            self.current_index -= 1
        elif removed_current:
            if index >= len(self.audio_files):
                self.current_index = len(self.audio_files) - 1
            else:
                self.current_index = index

        self.current_file = self.audio_files[self.current_index]
        return {'removed_current': removed_current, 'next_index': self.current_index}

    def build_title(self, prefix):
        if self.current_index < 0 or not self.audio_files:
            return prefix

        file_name = os.path.basename(self.current_file)
        total_files = len(self.audio_files)
        return f"{prefix} - {file_name} ({self.current_index + 1}/{total_files})"
