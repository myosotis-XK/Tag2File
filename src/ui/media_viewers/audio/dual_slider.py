from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal

from .play_back_slider import PlaybackSlider
from .maeker_display import MarkerDisplayWidget

class DualSliderWidget(QWidget):
    """双进度条容器 - 上方标记显示区，下方播放进度条"""

    # 信号：当播放进度条被拖动时发出
    sliderMoved = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)

        # 标记显示区域（上）
        self.marker_display = MarkerDisplayWidget()
        self.layout.addWidget(self.marker_display)

        # 播放进度条（下）
        self.playback_slider = PlaybackSlider(Qt.Horizontal)
        self.layout.addWidget(self.playback_slider)

        # 连接信号
        self.marker_display.markerJumped.connect(self._on_marker_jumped)
        self.playback_slider.sliderMoved.connect(self.sliderMoved.emit)

    def _on_marker_jumped(self, position):
        """标记跳转时同步播放进度条并发出信号"""
        self.playback_slider.setValue(position)
        self.sliderMoved.emit(position)

    def setRange(self, min_val, max_val):
        """设置播放进度条的范围和标记区域的时长"""
        self.playback_slider.setRange(min_val, max_val)
        self.marker_display.set_duration(max_val)

    def setValue(self, value):
        """设置播放进度条的值"""
        self.playback_slider.setValue(value)

    def isSliderDown(self):
        """检查播放进度条是否被按下"""
        return self.playback_slider.isSliderDown()

    def set_markers(self, markers):
        """设置标记数据"""
        self.marker_display.set_markers(markers)

        # 根据标记数量控制标记显示区域的可见性
        if markers:
            self.marker_display.show()
        else:
            self.marker_display.hide()

    def set_audio_file_path(self, path):
        """设置音频文件路径"""
        self.marker_display.set_audio_file_path(path)

    def set_quick_marker_creator(self, creator):
        """设置快速标记创建器引用"""
        self.playback_slider.set_quick_marker_creator(creator)

    def set_marker_list_panel(self, panel):
        """设置标记列表面板引用"""
        self.marker_display.set_marker_list_panel(panel)

    def _reload_markers(self):
        """重新加载标记"""
        self.marker_display._reload_markers()

        # 更新可见性
        if self.marker_display.markers:
            self.marker_display.show()
        else:
            self.marker_display.hide()