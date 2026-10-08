"""仅在本次运行中分别记住各类独立窗口的位置、大小和最大化状态。"""

from PyQt5 import sip
from PyQt5.QtCore import QEvent, QObject, Qt


class WindowPositionKeeper(QObject):
    _geometries = {}

    def __init__(self, window, key):
        super().__init__(window)
        self.window = window
        self.key = key

        # Restore before the first show. Moving a window during its Show event
        # can make Qt replace its saved normal geometry with maximized bounds.
        geometry = self._geometries.get(key)
        if geometry is not None and window.isWindow():
            window.restoreGeometry(geometry)
            # Full screen belongs to each viewer's separate immersive UI.
            if window.isFullScreen():
                window.setWindowState(window.windowState() & ~Qt.WindowFullScreen)
        window.installEventFilter(self)

    def eventFilter(self, watched, event):
        if sip.isdeleted(self.window):
            return False
        # An image viewer can also be embedded inside the image browser.
        if watched is self.window and self.window.isWindow():
            if event.type() == QEvent.Hide and not event.spontaneous():
                self.save_geometry()
        return super().eventFilter(watched, event)

    def save_geometry(self):
        if not sip.isdeleted(self.window) and self.window.isWindow():
            self._geometries[self.key] = self.window.saveGeometry()
