import os
from PIL import Image
from PyQt5.QtWidgets import QLabel, QFileIconProvider
from PyQt5.QtGui import QPixmap, QMovie, QImage
from PyQt5.QtCore import QFileInfo, QSize, QTimer
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

extension_icon_source_cache = {}
def get_file_init_icon(file_path: str, image_size: int) -> IconSource:
    """根据文件类型获取初始图标，并缩放到指定大小"""
    file_extension = os.path.splitext(file_path)[1]
    try:
        source = extension_icon_source_cache[image_size][file_extension]
    except KeyError:
        icon_provider = QFileIconProvider()
        file_icon = icon_provider.icon(QFileInfo(file_path))
        pixmap = file_icon.pixmap(image_size, image_size)
        source = PixmapIcon(pixmap)
        # 将图标添加到缓存
        if image_size not in extension_icon_source_cache:
            extension_icon_source_cache[image_size] = {}
        extension_icon_source_cache[image_size][file_extension] = source
    return source