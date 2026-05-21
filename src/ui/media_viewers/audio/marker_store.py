from src.core.DictManage import DictManage

from .audio_utils import normalize_audio_path, sort_markers


class MarkerStore:
    def __init__(self, dict_manage=None):
        self.dict_manage = dict_manage or DictManage()

    def get_markers(self, audio_file_path):
        normalized_path = normalize_audio_path(audio_file_path)
        if not normalized_path:
            return []
        markers = self.dict_manage.get_audio_markers(normalized_path)
        return sort_markers(markers)

    def add_marker(self, audio_file_path, marker_data):
        normalized_path = normalize_audio_path(audio_file_path)
        self.dict_manage.add_audio_marker(normalized_path, marker_data)

    def update_marker(self, audio_file_path, marker_id, marker_data):
        normalized_path = normalize_audio_path(audio_file_path)
        self.dict_manage.update_audio_marker(normalized_path, marker_id, marker_data)

    def delete_marker(self, audio_file_path, marker_id):
        normalized_path = normalize_audio_path(audio_file_path)
        self.dict_manage.delete_audio_marker(normalized_path, marker_id)

    def get_presets(self):
        return self.dict_manage.get_all_marker_presets()

    def get_preset_rows(self):
        return self.dict_manage.dataAPI.get_all_marker_presets()
