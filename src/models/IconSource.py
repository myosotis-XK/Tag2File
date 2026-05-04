import os
from PIL import Image
from PyQt5.QtWidgets import QLabel, QFileIconProvider
from PyQt5.QtGui import QPixmap, QImage, QPainterPath, QPen, QFont, QColor, QPainter
from PyQt5.QtCore import QFileInfo, QTimer, Qt, QPointF
from src.utils import ThumbnailSequence

class IconSource:
    def __init__(self):
        self.source = None

    def apply(self, label: QLabel):
        pass

    @staticmethod
    def pil_to_pixmap(pil_image: Image.Image) -> QPixmap:
        if pil_image.mode != 'RGBA':
            pil_image = pil_image.convert('RGBA')

        qimage = QImage(
            pil_image.tobytes(),
            pil_image.width,
            pil_image.height,
            pil_image.width * 4,
            QImage.Format_RGBA8888
        )

        return QPixmap.fromImage(qimage)
    
class PixmapIcon(IconSource):
    def __init__(self, image: Image.Image | QPixmap):
        super().__init__()
        if isinstance(image, Image.Image):
            self.source = self.pil_to_pixmap(image)
        elif isinstance(image, QPixmap):
            self.source = image

    def apply(self, label: QLabel):
        label.setPixmap(self.source)

class PixmapSequenceIcon(IconSource):
    def __init__(self, sequence: ThumbnailSequence):
        super().__init__()
        self.frames = []
        self.index = 0

        for frame in sequence.frames:
            self.frames.append(self.pil_to_pixmap(frame))

        # GIF 使用原始 duration，否则默认 80ms
        if sequence.durations:
            self.intervals = sequence.durations
        else:
            self.intervals = [80] * len(self.frames)

        self.source = self.frames[0]

        self.timer = None
        self.label = None

    def apply(self, label: QLabel):
        self.label = label
        label.setPixmap(self.frames[0])

        # 创建并关联 timer
        timer = QTimer(label)
        timer.timeout.connect(self._next_frame)
        timer.start(self.intervals[0])
        label.timer = timer

    def _next_frame(self):
        timer: QTimer = getattr(self.label, "timer", None)
        if timer is None:
            return
        self.index = (self.index + 1) % len(self.frames)
        self.label.setPixmap(self.frames[self.index])
        # 更新下一帧间隔
        timer.setInterval(self.intervals[self.index])

from PyQt5.QtCore import Qt
extension_icon_cache = {}
def get_file_init_icon(file_path: str, image_size: int) -> IconSource:
    """根据文件类型获取初始图标，并缩放到指定大小"""
    if os.path.isdir(file_path):
        file_extension = 'folder'
    else:
        file_extension = os.path.splitext(file_path)[1]
    try:
        icon = extension_icon_cache[image_size][file_extension]
    except KeyError:
        icon_provider = QFileIconProvider()
        file_icon = icon_provider.icon(QFileInfo(file_path))
        pixmap = file_icon.pixmap(image_size, image_size)
        pixmap = pixmap.scaled(
            image_size, image_size, 
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        icon = PixmapIcon(pixmap)
        # 将图标添加到缓存
        if image_size not in extension_icon_cache:
            extension_icon_cache[image_size] = {}
        if file_extension != '':
            extension_icon_cache[image_size][file_extension] = icon
    return icon

def draw_text_on_pixmap(pixmap: QPixmap, text: str) -> QPixmap:
    pixmap = pixmap.copy()
    painter = QPainter(pixmap)
    
    # 应用半透明的暗色遮罩
    painter.fillRect(pixmap.rect(), QColor(0, 0, 0, 64))  # 黑色半透明遮罩

    rect = pixmap.rect()
    
    # 计算自适应的字体大小
    font_size = min(rect.width(), rect.height()) // 6
    font = QFont("Arial", font_size)
    font.setBold(True)
    painter.setFont(font)

    # 设置文字颜色和描边
    text_color = QColor("red")
    outline_color = QColor("black")

    # 计算文本边界以确保居中
    text_rect = painter.boundingRect(rect, Qt.AlignCenter, text)

    # 创建文字路径并居中
    path = QPainterPath()
    path.addText(QPointF(rect.center().x() - text_rect.width() / 2,
                        rect.center().y() + text_rect.height() / 4), font, text)

    # 先绘制白色轮廓
    painter.setPen(QPen(outline_color, font_size // 10))
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(path)

    # 再绘制红色文字
    painter.setPen(Qt.NoPen)
    painter.setBrush(text_color)
    painter.drawPath(path)

    painter.end()
    return pixmap