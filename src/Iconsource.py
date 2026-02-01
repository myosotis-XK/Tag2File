from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import QPixmap, QMovie

class IconSource:
    def __init__(self):
        self.source = None

    def apply(self, label: QLabel):
        raise NotImplementedError
    
class PixmapIcon(IconSource):
    def __init__(self, pixmap: QPixmap):
        super().__init__()
        self.source = pixmap

    def apply(self, label: QLabel):
        label.setPixmap(self.source)

class MovieIcon(IconSource):
    def __init__(self, movie: QMovie):
        super().__init__()
        self.source = movie

    def apply(self, label: QLabel):
        label.setMovie(self.source)
        self.source.start()