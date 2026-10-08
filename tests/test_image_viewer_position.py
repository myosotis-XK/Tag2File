"""Image viewer window geometry across openings in one application run."""

import os
from pathlib import Path
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QPoint, QSize
from PyQt5.QtWidgets import QApplication

from src.ui.media_viewers.image.multi_viewer import MultiImageViewer
from src.utils.window_position import WindowPositionKeeper


class ImageViewerPositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.saved_geometry = WindowPositionKeeper._geometries.pop("image_viewer", None)

    def tearDown(self):
        WindowPositionKeeper._geometries.pop("image_viewer", None)
        if self.saved_geometry is not None:
            WindowPositionKeeper._geometries["image_viewer"] = self.saved_geometry

    def test_normal_close_restores_position_and_size(self):
        window = MultiImageViewer()
        reopened = None
        try:
            window.resize(420, 320)
            window.show()
            self.app.processEvents()
            window.move(135, 145)
            self.app.processEvents()
            position, size = QPoint(window.pos()), QSize(window.size())
            window.close()

            reopened = MultiImageViewer()
            reopened.show()
            self.app.processEvents()
            self.assertFalse(reopened.isMaximized())
            self.assertEqual(reopened.pos(), position)
            self.assertEqual(reopened.size(), size)
        finally:
            window.close()
            if reopened is not None:
                reopened.close()
            self.app.processEvents()

    def test_maximized_close_restores_maximized_and_normal_geometry(self):
        window = MultiImageViewer()
        reopened = None
        try:
            window.resize(420, 320)
            window.show()
            self.app.processEvents()
            window.move(135, 145)
            self.app.processEvents()
            position, size = QPoint(window.pos()), QSize(window.size())

            window.showMaximized()
            self.app.processEvents()
            self.assertTrue(window.isMaximized())
            window.close()

            reopened = MultiImageViewer()
            reopened.show()
            self.app.processEvents()
            self.assertTrue(reopened.isMaximized())
            self.assertFalse(reopened.isFullScreen())
            self.assertFalse(reopened.image_viewer.immersive_mode)

            reopened.showNormal()
            self.app.processEvents()
            self.assertEqual(reopened.pos(), position)
            self.assertEqual(reopened.size(), size)
        finally:
            window.close()
            if reopened is not None:
                reopened.close()
            self.app.processEvents()

    def test_restored_window_can_be_resized_and_closed_normally(self):
        window = MultiImageViewer()
        reopened = None
        third = None
        try:
            window.resize(420, 320)
            window.show()
            self.app.processEvents()
            window.showMaximized()
            self.app.processEvents()
            window.close()

            reopened = MultiImageViewer()
            reopened.show()
            self.app.processEvents()
            reopened.showNormal()
            reopened.resize(460, 340)
            reopened.move(155, 125)
            self.app.processEvents()
            position, size = QPoint(reopened.pos()), QSize(reopened.size())
            reopened.close()

            third = MultiImageViewer()
            third.show()
            self.app.processEvents()
            self.assertFalse(third.isMaximized())
            self.assertEqual(third.pos(), position)
            self.assertEqual(third.size(), size)
        finally:
            window.close()
            if reopened is not None:
                reopened.close()
            if third is not None:
                third.close()
            self.app.processEvents()

    def test_immersive_mode_does_not_restore_as_title_bar_maximization(self):
        window = MultiImageViewer()
        reopened = None
        try:
            window.resize(420, 320)
            image_path = Path(__file__).resolve().parents[1] / "data/image/example/1.jpg"
            self.assertTrue(window.image_viewer.load_image(str(image_path)))
            window.show()
            self.app.processEvents()
            window.toggle_immersive_mode()
            self.app.processEvents()
            self.assertTrue(window.isFullScreen())
            window.close()

            reopened = MultiImageViewer()
            reopened.show()
            self.app.processEvents()
            self.assertFalse(reopened.isFullScreen())
            self.assertFalse(reopened.isMaximized())
            self.assertFalse(reopened.image_viewer.immersive_mode)
        finally:
            window.close()
            if reopened is not None:
                reopened.close()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
