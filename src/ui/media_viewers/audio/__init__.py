"""
音频播放器模块
支持音频播放、时间轴标记、播放列表等功能
"""

from .audio_player import ModernPlayer
from .marker_edit_dialog import MarkerEditDialog
from .marker_list_panel import MarkerListPanel
from .marker_preset_manager import MarkerPresetManager
from .playlist_panel import PlaylistPanel

__all__ = [
    'ModernPlayer',
    'MarkerEditDialog',
    'MarkerListPanel',
    'MarkerPresetManager',
    'PlaylistPanel'
]
