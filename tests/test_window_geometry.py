"""Session-only geometry restoration shared by remembered windows."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QPoint, QSize
from PyQt5.QtWidgets import QApplication, QDialog, QMainWindow, QWidget

from src.utils.window_position import WindowPositionKeeper


class WindowGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.previous = WindowPositionKeeper._geometries.copy()
        WindowPositionKeeper._geometries.clear()

    def tearDown(self):
        WindowPositionKeeper._geometries.clear()
        WindowPositionKeeper._geometries.update(self.previous)

    def test_dialog_and_widget_restore_their_own_position_and_size(self):
        for window_type, key, position, size in (
            (QDialog, "category_manager", QPoint(105, 115), QSize(340, 260)),
            (QWidget, "file_properties", QPoint(175, 135), QSize(380, 290)),
        ):
            with self.subTest(key=key):
                window = window_type()
                window._position_keeper = WindowPositionKeeper(window, key)
                window.resize(size)
                window.show()
                self.app.processEvents()
                window.move(position)
                self.app.processEvents()
                expected_position, expected_size = QPoint(window.pos()), QSize(window.size())
                window.close()
                self.app.processEvents()

                reopened = window_type()
                reopened._position_keeper = WindowPositionKeeper(reopened, key)
                reopened.show()
                self.app.processEvents()
                self.assertEqual(reopened.pos(), expected_position)
                self.assertEqual(reopened.size(), expected_size)
                reopened.close()
                self.app.processEvents()

    def test_main_window_restores_maximized_and_normal_geometry(self):
        window = QMainWindow()
        window._position_keeper = WindowPositionKeeper(window, "tag_manager")
        window.resize(420, 310)
        window.show()
        self.app.processEvents()
        window.move(130, 140)
        self.app.processEvents()
        position, size = QPoint(window.pos()), QSize(window.size())
        window.showMaximized()
        self.app.processEvents()
        window.close()
        self.app.processEvents()

        reopened = QMainWindow()
        reopened._position_keeper = WindowPositionKeeper(reopened, "tag_manager")
        reopened.show()
        self.app.processEvents()
        self.assertTrue(reopened.isMaximized())
        reopened.showNormal()
        self.app.processEvents()
        self.assertEqual(reopened.pos(), position)
        self.assertEqual(reopened.size(), size)
        reopened.close()
        self.app.processEvents()

    def test_embedded_window_does_not_replace_saved_geometry(self):
        window = QMainWindow()
        window._position_keeper = WindowPositionKeeper(window, "image_viewer")
        window.resize(400, 300)
        window.show()
        self.app.processEvents()
        window.close()
        self.app.processEvents()
        saved_geometry = WindowPositionKeeper._geometries["image_viewer"]

        host = QMainWindow()
        embedded = QMainWindow()
        embedded._position_keeper = WindowPositionKeeper(embedded, "image_viewer")
        host.setCentralWidget(embedded)
        host.show()
        self.app.processEvents()
        host.close()
        self.app.processEvents()
        self.assertEqual(WindowPositionKeeper._geometries["image_viewer"], saved_geometry)


if __name__ == "__main__":
    unittest.main()
