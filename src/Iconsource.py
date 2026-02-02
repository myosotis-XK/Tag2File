from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import QPixmap, QMovie
from PyQt5.QtCore import QSize, QTimer

class IconSource:
    def __init__(self):
        self.source = None

    def apply(self, label: QLabel):
        pass

    def release(self, label: QLabel):
        pass
    
class PixmapIcon(IconSource):
    def __init__(self, pixmap: QPixmap):
        super().__init__()
        self.source = pixmap

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
    def __init__(self, pixmaps: list[QPixmap], interval=80):
        """
        __init__ 在后台线程，仅做数据准备
        """
        self.frames = pixmaps
        self.source = self.frames[0]
        self.interval = interval
        self.index = 0

        # UI objects 延后创建
        self.timer = None
        self.label = None

    def apply(self, label: QLabel):
        """
        UI 线程调用
        """

        self.label = label

        # 首帧
        self.label.setPixmap(self.frames[0])

        # QTimer 必须在 UI 线程创建
        self.timer = QTimer(label)
        self.timer.setInterval(self.interval)
        self.timer.timeout.connect(self._next_frame)
        self.timer.start()

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