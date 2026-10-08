"""Compact Explorer-style drag thumbnails and insertion feedback."""

from PyQt5.QtCore import QPoint, QPointF, QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPalette, QPen, QPixmap, QPolygonF
from PyQt5.QtWidgets import QLabel, QWidget


def build_drag_preview(view, paths, lead_path, press_position):
    """Render cached artwork without capturing the selected tile or its filename."""
    edge = min(96, max(48, view.image_size))
    ratio = view.devicePixelRatioF()
    size = QSize(edge + 40, edge + 38)
    preview = QPixmap(round(size.width() * ratio), round(size.height() * ratio))
    preview.setDevicePixelRatio(ratio)
    preview.fill(Qt.transparent)
    painter = QPainter(preview)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    card = QRectF(8, 14, edge + 8, edge + 8)

    def paper(rect, opacity):
        painter.setOpacity(opacity)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 24))
        painter.drawRoundedRect(rect.translated(1, 2), 2, 2)
        painter.setPen(QPen(QColor(132, 143, 155, 170), 1))
        painter.setBrush(QColor(255, 255, 255, 235))
        painter.drawRoundedRect(rect, 2, 2)

    if len(paths) > 1:
        for offset in range(min(2, len(paths) - 1), 0, -1):
            paper(card.translated(offset * 4, -offset * 4), 0.45)
    paper(card, 0.8)

    label = view._labels.get(lead_path)
    icon_label = label.findChild(QLabel, "icon_label") if label is not None else None
    pixmap = icon_label.pixmap() if icon_label is not None else None
    if pixmap is None or pixmap.isNull():
        item = view.state.get_item_if_exists(lead_path)
        source = item.icon_source.get("current") if item is not None else None
        pixmap = getattr(source, "source", None)
    if isinstance(pixmap, QPixmap) and not pixmap.isNull():
        artwork = pixmap.scaled(round(edge * ratio), round(edge * ratio),
                                Qt.KeepAspectRatio, Qt.SmoothTransformation)
        artwork.setDevicePixelRatio(ratio)
        width, height = artwork.width() / ratio, artwork.height() / ratio
        painter.drawPixmap(QPointF(card.center().x() - width / 2, card.center().y() - height / 2), artwork)

    if len(paths) > 1:
        # Keep the count readable even though the artwork itself is translucent.
        painter.setOpacity(1)
        font = QFont(view.font())
        font.setPointSizeF(9)
        font.setBold(True)
        painter.setFont(font)
        text = str(len(paths))
        width = max(26, QFontMetrics(font).horizontalAdvance(text) + 14)
        badge = QRectF(min(card.right() - 10, size.width() - width - 3), card.bottom() - 10, width, 24)
        painter.setPen(QPen(QColor(255, 255, 255), 1.5))
        painter.setBrush(view.palette().color(QPalette.Highlight))
        painter.drawRoundedRect(badge, 4, 4)
        painter.setPen(view.palette().color(QPalette.HighlightedText))
        painter.drawText(badge, Qt.AlignCenter, text)
    painter.end()

    hotspot = QPoint(round(card.center().x()), round(card.center().y()))
    if icon_label is not None:
        local = press_position - icon_label.mapTo(view, QPoint())
        hotspot = QPoint(round(card.x() + 4 + min(1, max(0, local.x() / icon_label.width())) * edge),
                         round(card.y() + 4 + min(1, max(0, local.y() / icon_label.height())) * edge))
    return preview, hotspot


class InsertionMarker(QWidget):
    """A thin stem with small end pointers, positioned in the gap between tiles."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("manual_sort_marker")
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = self.palette().color(QPalette.Highlight)
        center = self.width() / 2
        painter.setPen(QPen(color, 1.5))
        painter.drawLine(QPointF(center, 4), QPointF(center, self.height() - 4))
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawPolygon(QPolygonF([QPointF(1, 0), QPointF(self.width() - 1, 0), QPointF(center, 4)]))
        painter.drawPolygon(QPolygonF([QPointF(1, self.height()), QPointF(self.width() - 1, self.height()),
                                      QPointF(center, self.height() - 4)]))
        painter.end()
