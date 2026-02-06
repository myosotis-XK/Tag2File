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

    def release(self, label: QLabel):
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


class MovieIcon(IconSource):
    def __init__(self, movie: QMovie, max_size: int):
        super().__init__()
        movie.finished.connect(movie.start)
        self.source = movie
        self.scaled_movie(max_size)

    def apply(self, label: QLabel):
        label.setMovie(self.source)
        self.source.start()

    def release(self, label: QLabel):
        label.setMovie(None)
        self.source.stop()

    def scaled_movie(self, max_size: int):
        self.source.jumpToFrame(0)
        rect = self.source.frameRect()
        w, h = rect.width(), rect.height()
        if w > h:
            new_w = max_size
            new_h = int(h * max_size / w)
        else:
            new_h = max_size
            new_w = int(w * max_size / h)
        self.source.setScaledSize(QSize(new_w, new_h))

class PixmapSequenceIcon(IconSource):
    def __init__(self, sequence: ThumbnailSequence):
        super().__init__()
        print(f"Creating PixmapSequenceIcon with {len(sequence.frames)} frames and intervals: {sequence.durations}")
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
        print(f"Applying PixmapSequenceIcon with {len(self.frames)} frames")
        self.label = label

        self.label.setPixmap(self.frames[0])

        self.timer = QTimer(label)
        self.timer.timeout.connect(self._next_frame)
        self.timer.start(self.intervals[0])

    def release(self, label: QLabel): 
        if self.timer: 
            self.timer.stop() 
            self.timer.timeout.disconnect() 
            self.timer.deleteLater() 
            self.timer = None 
        self.label = None

    def _next_frame(self):
        self.index = (self.index + 1) % len(self.frames)
        self.label.setPixmap(self.frames[self.index])

        # 更新下一帧间隔
        self.timer.setInterval(self.intervals[self.index])

extension_icon_source_cache = {}
def get_file_init_icon_source(file_path: str, image_size: int) -> IconSource:
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