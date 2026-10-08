"""Compose video and subtitles in one scene, including with Windows video backends."""

import os

from PyQt5.QtCore import QPointF, QRectF, QSizeF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QTextOption
from PyQt5.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt5.QtWidgets import QFrame, QGraphicsDropShadowEffect, QGraphicsScene, QGraphicsTextItem, QGraphicsView


class CaptionItem(QGraphicsTextItem):
    def __init__(self):
        super().__init__()
        shadow = QGraphicsDropShadowEffect()
        shadow.setColor(QColor(0, 0, 0, 240))
        shadow.setBlurRadius(6)
        shadow.setOffset(0, 1)
        self.setGraphicsEffect(shadow)


class VideoSurface(QGraphicsView):
    doubleClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bottom_inset = 0
        scene = QGraphicsScene(self)
        self.setScene(scene)
        self.setFrameShape(QFrame.NoFrame)
        self.setBackgroundBrush(Qt.black)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.video_item = QGraphicsVideoItem()
        self.video_item.setAspectRatioMode(Qt.KeepAspectRatio)
        scene.addItem(self.video_item)
        self.caption_item = CaptionItem()
        self.caption_item.setZValue(1)
        self.caption_item.setDefaultTextColor(Qt.white)
        self.caption_item.setAcceptedMouseButtons(Qt.NoButton)
        option = QTextOption(Qt.AlignHCenter)
        option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.caption_item.document().setDefaultTextOption(option)
        scene.addItem(self.caption_item)
        self.caption_item.hide()
        self.video_item.nativeSizeChanged.connect(self._layout_scene)

    @property
    def subtitle_text(self):
        return self.caption_item.toPlainText()

    def set_subtitle(self, text):
        if text != self.subtitle_text:
            self.caption_item.setPlainText(text)
            self.caption_item.setVisible(bool(text))
            self._layout_caption()

    def set_bottom_inset(self, pixels):
        if self.bottom_inset != pixels:
            self.bottom_inset = pixels
            self._layout_caption()

    def _layout_scene(self, *args):
        size = QSizeF(self.viewport().size())
        self.setSceneRect(QRectF(QPointF(), size))
        self.video_item.setSize(size)
        self._layout_caption()

    def _layout_caption(self):
        bounds = self.sceneRect()
        native = self.video_item.nativeSize()
        if native.width() > 0 and native.height() > 0:
            fitted = native.scaled(bounds.size(), Qt.KeepAspectRatio)
            bounds = QRectF(bounds.center().x() - fitted.width() / 2,
                            bounds.center().y() - fitted.height() / 2,
                            fitted.width(), fitted.height())
        font = QFont('Microsoft YaHei' if os.name == 'nt' else self.font().family())
        font.setPixelSize(max(16, min(36, round(bounds.height() * 0.055))))
        font.setBold(True)
        self.caption_item.setFont(font)
        self.caption_item.setTextWidth(max(1, bounds.width() * 0.9))
        caption = self.caption_item.boundingRect()
        bottom = min(bounds.bottom(), self.sceneRect().bottom() - self.bottom_inset)
        self.caption_item.setPos(bounds.center().x() - caption.width() / 2,
                                 max(bounds.top(), bottom - caption.height() - 12))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_scene()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)
