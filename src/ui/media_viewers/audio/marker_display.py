from PyQt5.QtCore import QPoint, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QMouseEvent, QPainter
from PyQt5.QtWidgets import QLabel, QMenu, QWidget

from .audio_utils import marker_jump_position, marker_tooltip_text


class MarkerDisplayWidget(QWidget):
    """Timeline visualization for markers."""

    markerJumped = pyqtSignal(int)
    marker_edit_requested = pyqtSignal(dict)
    marker_delete_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.markers = []
        self.snap_threshold = 15
        self.duration_ms = 0
        self.setFixedHeight(30)
        self.setStyleSheet("""
            MarkerDisplayWidget {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 3px;
            }
        """)

        self.floating_label = QLabel(self, Qt.ToolTip)
        self.floating_label.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        self.floating_label.setStyleSheet("""
            background-color: #34495e;
            color: #ecf0f1;
            padding: 5px 10px;
            border-radius: 4px;
            font-family: 'Segoe UI', 'Microsoft YaHei';
            font-size: 11px;
        """)
        self.floating_label.hide()

    def set_duration(self, duration_ms):
        self.duration_ms = duration_ms
        self.update()

    def set_markers(self, markers):
        self.markers = list(markers)
        self.update()

    def _value_to_pixel(self, value):
        if self.duration_ms <= 0:
            return 0
        return int((value / self.duration_ms) * self.width())

    def _pixel_to_value(self, x_pos):
        if self.width() <= 0:
            return 0
        ratio = x_pos / self.width()
        return int(max(0, min(1, ratio)) * self.duration_ms)

    def _find_marker_at(self, x_pos):
        if self.duration_ms <= 0:
            return None

        for marker in self.markers:
            if marker.get('type') == 0:
                marker_x = self._value_to_pixel(marker.get('time', 0))
                if abs(marker_x - x_pos) < self.snap_threshold:
                    return marker
            else:
                start_x = self._value_to_pixel(marker.get('start', 0))
                end_x = self._value_to_pixel(marker.get('end', 0))
                if start_x <= x_pos <= end_x:
                    return marker

        return None

    def _find_markers_at(self, x_pos):
        if self.duration_ms <= 0:
            return []

        overlapping_markers = []
        for marker in self.markers:
            if marker.get('type') == 0:
                marker_x = self._value_to_pixel(marker.get('time', 0))
                if abs(marker_x - x_pos) < self.snap_threshold:
                    overlapping_markers.append(marker)
            else:
                start_x = self._value_to_pixel(marker.get('start', 0))
                end_x = self._value_to_pixel(marker.get('end', 0))
                if start_x <= x_pos <= end_x:
                    overlapping_markers.append(marker)

        return overlapping_markers

    def mouseMoveEvent(self, event: QMouseEvent):
        overlapping_markers = self._find_markers_at(event.x())
        if overlapping_markers:
            display_text = "\n".join(marker_tooltip_text(marker) for marker in overlapping_markers)
            self.floating_label.setText(display_text)
            self.floating_label.adjustSize()
            global_pos = self.mapToGlobal(QPoint(event.x() - self.floating_label.width() // 2, -45))
            self.floating_label.move(global_pos)
            self.floating_label.show()
        else:
            self.floating_label.hide()

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.floating_label.hide()
        super().leaveEvent(event)

    def contextMenuEvent(self, event):
        marker = self._find_marker_at(event.x())
        if not marker:
            return

        menu = QMenu(self)
        edit_action = menu.addAction("编辑标记")
        delete_action = menu.addAction("删除标记")
        action = menu.exec_(event.globalPos())

        if action == edit_action:
            self.marker_edit_requested.emit(dict(marker))
        elif action == delete_action:
            self.marker_delete_requested.emit(marker['id'])

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            overlapping_markers = self._find_markers_at(event.x())
            if overlapping_markers:
                click_time = self._pixel_to_value(event.x())
                closest_marker = min(
                    overlapping_markers,
                    key=lambda marker: abs(marker_jump_position(marker) - click_time),
                )
                self.markerJumped.emit(marker_jump_position(closest_marker))

        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f5f5f5"))
        painter.setPen(QColor("#ddd"))
        painter.drawRoundedRect(0, 0, self.width() - 1, self.height() - 1, 3, 3)

        if not self.duration_ms or not self.markers:
            painter.end()
            return

        for marker in self.markers:
            color = QColor(marker.get('color', '#3498db'))
            if marker.get('type') == 0:
                x_pos = self._value_to_pixel(marker.get('time', 0))
                painter.setBrush(color)
                painter.setPen(Qt.NoPen)
                painter.drawRect(x_pos - 2, 4, 4, self.height() - 8)
            else:
                start_x = self._value_to_pixel(marker.get('start', 0))
                end_x = self._value_to_pixel(marker.get('end', 0))
                rect_color = QColor(color)
                rect_color.setAlpha(100)
                painter.setBrush(rect_color)
                painter.setPen(color)
                painter.drawRect(start_x, 8, end_x - start_x, self.height() - 16)

        painter.end()
