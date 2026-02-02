from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import QPixmap, QMovie
from PyQt5.QtCore import QSize

class IconSource:
    def __init__(self):
        self.source = None

    def apply(self, label: QLabel):
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