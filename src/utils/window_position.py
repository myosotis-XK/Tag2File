"""仅在本次运行中分别记住各类弹窗的位置。"""

from PyQt5.QtCore import QEvent, QObject, QPoint
from PyQt5.QtWidgets import QApplication


class WindowPositionKeeper(QObject):
    _positions = {}

    def __init__(self, window, key):
        super().__init__(window)
        self.window = window
        self.key = key
        self.normal_position = None
        window.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Show and not event.spontaneous():
            self.restore_position()
            self.remember_normal_position()
        elif event.type() == QEvent.Move:
            self.remember_normal_position()
        elif event.type() == QEvent.Hide and not event.spontaneous():
            self.save_position()
        return super().eventFilter(watched, event)

    def remember_normal_position(self):
        if not (self.window.isMaximized() or self.window.isMinimized() or self.window.isFullScreen()):
            self.normal_position = self.window.pos()

    def restore_position(self):
        position = self._positions.get(self.key)
        if position is None:
            return
        x, y = position.x(), position.y()

        # 显示器布局改变后，确保标题栏仍在可用屏幕内。
        screen = QApplication.screenAt(position) or QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        frame_size = self.window.frameGeometry().size()
        max_x = max(available.left(), available.right() - frame_size.width() + 1)
        max_y = max(available.top(), available.bottom() - frame_size.height() + 1)
        x = min(max(x, available.left()), max_x)
        y = min(max(y, available.top()), max_y)
        self.window.move(x, y)

    def save_position(self):
        self.remember_normal_position()
        if self.normal_position is None:
            return
        self._positions[self.key] = QPoint(self.normal_position)
