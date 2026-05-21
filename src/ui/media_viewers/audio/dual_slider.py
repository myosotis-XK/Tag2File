from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QVBoxLayout, QWidget

from .marker_display import MarkerDisplayWidget
from .play_back_slider import PlaybackSlider


class DualSliderWidget(QWidget):
    sliderMoved = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.marker_display = MarkerDisplayWidget()
        layout.addWidget(self.marker_display)

        self.playback_slider = PlaybackSlider(Qt.Horizontal)
        layout.addWidget(self.playback_slider)

        self.marker_display.markerJumped.connect(self._on_marker_jumped)
        self.playback_slider.sliderMoved.connect(self.sliderMoved.emit)

    def _on_marker_jumped(self, position):
        self.playback_slider.setValue(position)
        self.sliderMoved.emit(position)

    def setRange(self, min_val, max_val):
        self.playback_slider.setRange(min_val, max_val)
        self.marker_display.set_duration(max_val)

    def setValue(self, value):
        self.playback_slider.setValue(value)

    def isSliderDown(self):
        return self.playback_slider.isSliderDown()

    def set_markers(self, markers):
        self.marker_display.set_markers(markers)
        self.marker_display.setVisible(bool(markers))

    def refresh_markers(self, markers):
        self.set_markers(markers)

    def set_quick_marker_creator(self, creator):
        self.playback_slider.set_quick_marker_creator(creator)
