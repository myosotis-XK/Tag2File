import os
from enum import Enum
from PyQt5.QtWidgets import QLabel, QApplication
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QFont, QFontMetrics
from src.utils import config
from .IconSource import IconSource


class Border(Enum):
    NONE = "border: none;"
    BLUE = "border: 1px solid #99d1ff;"

class Background(Enum):
    TRANSPARENT = "background-color: transparent;"
    LIGHTBLUE = "background-color: #e5f3ff;"
    DARKBLUE = "background-color: #cde8ff;"

class FileItem():
    SPACING_RATE = config.getfloat('FileShowArea', 'SPACING_RATE', fallback=0.05)
    _font_metrics: QFontMetrics | None = None
    _single_line_height: int | None = None

    @classmethod
    def _get_font_metrics(cls) -> tuple[QFontMetrics, int]:
        if cls._font_metrics is None or cls._single_line_height is None:
            app = QApplication.instance()
            font = app.font() if app is not None else QFont()
            cls._font_metrics = QFontMetrics(font)
            cls._single_line_height = cls._font_metrics.lineSpacing()
        return cls._font_metrics, cls._single_line_height

    def __init__(self, file_path:str, file_size_bytes: int, file_date: float, label_width: int):
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)

        self.label_width = label_width
        self.label_pos = (0, 0)
        self.update_label_size()

        self.file_size_bytes = file_size_bytes
        self.file_date = file_date

        self.icon: bool = False
        self.icon_source: dict[str, IconSource] = None

        self.specifid = 0
        self.selected = 0
        self.hover = 0

        self.border = Border.NONE
        self.background = Background.TRANSPARENT

    def update_label_size(self, label_width: int=None):
        if label_width is None:
            label_width = self.label_width
        else:
            self.label_width = label_width
        self.name_height = self.calculate_name_height(self.file_name, label_width, 3)
        self.label_size = (label_width, label_width + self.name_height)

    # 计算文件名标签的高度
    def calculate_name_height(self, file_name: str, label_width: int, max_lines: int) -> int:
        font_metrics, single_line_height = self._get_font_metrics()
        text_width = font_metrics.horizontalAdvance(file_name)  # 文本总宽度
        num_lines = max(1, (text_width // (label_width-4)) + 1)  # 计算需要的行数
        total_lines = min(num_lines, max_lines)  # 限制最大行数
        name_height = total_lines * single_line_height  # 总高度
        return name_height + int(label_width*self.SPACING_RATE)
    
    def apply(self, label: QLabel):
        icon = self.icon_source.get('current')
        if icon:
            self.release(label)
            icon.apply(label)

    def release(self, label: QLabel):
        if hasattr(label, 'timer') and label.timer:
            timer: QTimer = label.timer
            label.timer = None

            timer.stop()
            timer.timeout.disconnect()
            timer.deleteLater()
