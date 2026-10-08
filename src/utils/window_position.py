"""仅在本次运行中分别记住各类弹窗的位置。"""

from PyQt5 import sip
from PyQt5.QtCore import QEvent, QObject, QPoint
from PyQt5.QtWidgets import QApplication


class WindowPositionKeeper(QObject):
    _positions = {}

    def __init__(self, window, key):
        super().__init__(window)
        self.window = window
        self.key = key
        self.normal_position = None
        self._normal_position_frozen = False
        window.installEventFilter(self)

    def eventFilter(self, watched, event):
        if sip.isdeleted(self.window):
            return False
        # 多图片查看器也可嵌入图片浏览器；只记录独立窗口的位置。
        if not self.window.isWindow():
            return super().eventFilter(watched, event)
        if event.type() == QEvent.Show and not event.spontaneous():
            self.restore_position()
            self.remember_normal_position()
        elif event.type() == QEvent.Move:
            self.remember_normal_position()
        elif event.type() == QEvent.Hide and not event.spontaneous():
            self.save_position()
        return super().eventFilter(watched, event)

    def remember_normal_position(self):
        if not self._normal_position_frozen and not (
            self.window.isMaximized() or self.window.isMinimized() or self.window.isFullScreen()
        ):
            self.normal_position = self.window.pos()

    def freeze_normal_position(self):
        """Keep the windowed position during a transition into full screen."""
        self.remember_normal_position()
        self._normal_position_frozen = True

    def unfreeze_normal_position(self):
        self._normal_position_frozen = False
        self.remember_normal_position()

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
