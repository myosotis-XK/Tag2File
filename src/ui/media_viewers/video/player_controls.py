"""Controls and styling for the desktop video player."""

from functools import lru_cache
from pathlib import Path

from PyQt5.QtCore import QByteArray, QPointF, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QLabel, QSlider, QStyle, QStyleOptionSlider

from src.utils.path import root


PLAYER_STYLE = '''
    QWidget#video_player_root, QWidget#video_content { background: #08090b; color: #e8ebf1;
        font-family: "Microsoft YaHei", "Segoe UI"; font-size: 13px; }
    QWidget#transport { background: #171a20; }
    QWidget#playlist_sidebar { background: #1b1e24; border-left: 1px solid #2c3039; }
    QLabel { color: #d8dce5; background: transparent; border: none; }
    QLabel#playlist_title { color: #f2f4f8; font-size: 16px; font-weight: 600; }
    QLabel#playlist_meta { color: #aeb5c2; font-size: 12px; }
    QLabel#time_label { color: #b9c1cd; font-family: "Segoe UI"; font-size: 14px; }
    QLabel#playback_status { color: #e7c28b; background: #242127; padding: 8px 16px; }
    QToolButton { background: transparent; border: none; border-radius: 6px; padding: 0px; }
    QToolButton:hover { background: #2b313b; }
    QToolButton:pressed, QToolButton:checked { background: #263c52; }
    QToolButton#play_button { background: #399efa; border-radius: 24px; }
    QToolButton#play_button:hover { background: #62b3ff; }
    QToolButton#play_button:disabled { background: #303943; }
    QToolButton::menu-indicator { image: none; width: 0; }
    QSlider { background: transparent; border: none; }
    QListWidget { background: transparent; color: #bbc2cf; border: none; outline: none; font-size: 13px; }
    QListWidget::item { padding: 4px 10px; border-bottom: 1px solid #262b33; }
    QListWidget::item:hover { background: #242c37; }
    QListWidget::item:selected { background: #22354a; color: #60b3ff; }
    QSplitter::handle { background: #2c3039; }
    QScrollBar:vertical { background: transparent; width: 7px; margin: 2px; }
    QScrollBar::handle:vertical { background: #555c68; border-radius: 2px; min-height: 32px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
    QMenu { color: #e8ebf1; background: #232730; border: 1px solid #3a414e; padding: 6px; }
    QMenu::item { padding: 8px 24px; border-radius: 4px; }
    QMenu::item:selected { background: #30445c; }
    QMenu::item:disabled { color: #8892a3; }
    QMenu::separator { height: 1px; background: #3a414e; margin: 5px 8px; }
    QToolTip { color: #e8ebf1; background: #282e38; border: 1px solid #444d5b; padding: 5px; }
'''

_SHAPES = {
    'playlist': '<path d="M8 6h13M8 12h13M8 18h13"/><path d="M3 6h1M3 12h1M3 18h1"/>',
    'subtitles': '<rect x="2" y="4" width="20" height="16" rx="3"/><path d="M10 9a3 3 0 1 0 0 6M19 9a3 3 0 1 0 0 6"/>',
    'fullscreen': '<path d="M9 3H3v6M15 3h6v6M3 15v6h6M21 15v6h-6"/>',
    'restore': '<path d="M3 9h6V3M21 9h-6V3M9 21v-6H3M15 21v-6h6"/>',
    'more': '<circle cx="4" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="20" cy="12" r="1"/>',
    'add': '<path d="M12 4v16M4 12h16"/>',
    'close': '<path d="M6 6l12 12M18 6L6 18"/>',
    'playing': '<path d="M5 10v8M12 5v13M19 8v10"/>',
}


@lru_cache(maxsize=48)
def player_icon(name, color='#e8ebf1'):
    if name in _SHAPES:
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
               f'fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" '
               f'stroke-linejoin="round">{_SHAPES[name]}</svg>')
    else:
        svg = (Path(root) / 'data' / 'icon' / 'audio' / f'{name}.svg').read_text(encoding='utf-8')
        svg = svg.replace('#1f6fa5', color).replace('#ffffff', color)
    renderer = QSvgRenderer(QByteArray(svg.encode('utf-8')))
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


class StatusLabel(QLabel):
    """Status messages occupy space only while there is something to show."""
    def setText(self, text):
        super().setText(text)
        self.setVisible(bool(text))

    def clear(self):
        self.setText('')


class SeekSlider(QSlider):
    """A thin horizontal track with click-to-position and drag preview support."""
    def paintEvent(self, event):
        # Draw the track ourselves: native Windows styles give the styled slider
        # pages a different height from its groove, leaving a thick grey strip.
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        left, right, y = 6, max(6, self.width() - 6), self.height() / 2
        offset = QStyle.sliderPositionFromValue(self.minimum(), self.maximum(),
                                               self.sliderPosition(), right - left, option.upsideDown)
        handle = QPointF(left + offset, y)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor('#444b57'), 4, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(left, y), QPointF(right, y))
        if self.isEnabled():
            painter.setPen(QPen(QColor('#48a6ff'), 4, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QPointF(right if option.upsideDown else left, y), handle)
        color = '#d8dce5' if self.objectName() == 'volume_slider' else '#48a6ff'
        painter.setBrush(QColor(color if self.isEnabled() else '#666d78'))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(handle, 6, 6)
        if self.hasFocus():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor('#b9dfff'), 1))
            painter.drawEllipse(handle, 8, 8)

    def _move_to(self, x):
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        value = QStyle.sliderValueFromPosition(self.minimum(), self.maximum(),
                                               x - 6, max(1, self.width() - 12), option.upsideDown)
        self.setValue(value)
        self.sliderMoved.emit(value)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.isEnabled():
            self.setSliderDown(True)
            self._move_to(event.pos().x())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.isSliderDown():
            self._move_to(event.pos().x())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.isSliderDown():
            self._move_to(event.pos().x())
            self.setSliderDown(False)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
