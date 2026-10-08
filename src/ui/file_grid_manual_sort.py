"""Internal drag gestures for the main file grid's manual sorting mode."""

from PyQt5.QtCore import QEvent, QMimeData, QObject, QPoint, QRect, Qt, QTimer
from PyQt5.QtGui import QCursor, QDrag
from PyQt5.QtWidgets import QApplication, QLabel

from .file_grid_drag_visuals import InsertionMarker, build_drag_preview


class ManualSortController(QObject):
    MIME_TYPE = "application/x-tag2file-manual-sort"

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self._pending_path = None
        self._press_position = QPoint()
        self._active = False
        self._drag_paths = []
        self._drag_db = None
        self._target = None
        self._pointer = QPoint()
        self.marker = InsertionMarker(view)
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setInterval(view.auto_scroll_timer.interval())
        self.scroll_timer.timeout.connect(self._auto_scroll)
        view.installEventFilter(self)
        for label in [*view._labels.values(), *view._label_pool]:
            self.install(label)

    def install(self, label):
        label.installEventFilter(self)
        for child in label.findChildren(QLabel):
            child.installEventFilter(self)

    def cancel(self):
        if self._active:
            QDrag.cancel()
        self._clear()

    def _clear(self):
        self.scroll_timer.stop()
        self.marker.hide()
        self._pending_path = None
        self._active = False
        self._drag_paths = []
        self._drag_db = None
        self._target = None

    def eventFilter(self, watched, event):
        if not self.view.is_manual_sort():
            return False
        kind = event.type()
        if kind == QEvent.MouseButtonDblClick:
            self._pending_path = None
            return False
        if kind == QEvent.MouseButtonPress:
            path = getattr(watched, "file_path", None)
            if event.button() != Qt.LeftButton or event.modifiers() != Qt.NoModifier or not path:
                return False
            label = self.view._labels.get(path)
            if label is None:
                return False
            label_position = watched.mapTo(label, event.pos()) if watched is not label else event.pos()
            if not self.view.isMouseOnThumbnail(label_position, label):
                self._pending_path = None
                return False
            self._pending_path = path
            self._press_position = watched.mapTo(self.view, event.pos())
            self.view.setFocus()
            if path not in self.view.get_selected_files():
                self.view.set_selected_files([path], path)
            else:
                self.view.set_current_file(path, keep_selection=True)
            # File drags must not enter the base widget's rubber-band selection state.
            self.view.mouse_press = False
            return True
        if kind == QEvent.MouseMove and self._pending_path:
            if not event.buttons() & Qt.LeftButton:
                self._pending_path = None
                return False
            position = watched.mapTo(self.view, event.pos())
            if (position - self._press_position).manhattanLength() >= QApplication.startDragDistance():
                self._start_drag()
            return True
        if kind == QEvent.MouseButtonRelease and self._pending_path and event.button() == Qt.LeftButton:
            path = self._pending_path
            self._pending_path = None
            if self.view.state.contains(path):
                self.view.set_selected_files([path], path)
            return True
        return False

    def _start_drag(self):
        if not self._pending_path or not self.view.state.contains(self._pending_path):
            self._clear()
            return
        lead_path = self._pending_path
        self._drag_paths = self.view.get_selected_files()
        self._drag_db = self.view.dict_manage.dataAPI.db_path
        self._pending_path = None
        self._active = True
        self.view.auto_scroll_timer.stop()
        self.view.rubber_band.hide()
        drag = QDrag(self.view)
        mime = QMimeData()
        mime.setData(self.MIME_TYPE, b"internal")
        drag.setMimeData(mime)
        preview, hotspot = build_drag_preview(self.view, self._drag_paths, lead_path, self._press_position)
        drag.setPixmap(preview)
        drag.setHotSpot(hotspot)
        # Poll throughout the native drag loop, including outside the application window.
        self.scroll_timer.start()
        try:
            drag.exec_(Qt.MoveAction)
        finally:
            self._clear()
            drag.deleteLater()

    def _valid(self):
        return (self._active and self.view.is_manual_sort()
                and self._drag_db == self.view.dict_manage.dataAPI.db_path
                and all(self.view.state.contains(path) for path in self._drag_paths))

    def accepts(self, event):
        return (self._valid() and event.source() is self.view
                and event.mimeData().hasFormat(self.MIME_TYPE))

    def move(self, event):
        if not self.accepts(event):
            event.ignore()
            return
        self.update_position(event.pos())
        event.setDropAction(Qt.MoveAction)
        event.accept()
        # Restarting on every DragMove can postpone every timeout while the mouse is moving.
        if not self.scroll_timer.isActive():
            self.scroll_timer.start()

    def leave(self):
        self.marker.hide()
        self._target = None

    def update_position(self, position):
        self._pointer = QPoint(position)
        self._target = None
        self.marker.hide()
        if not self._valid():
            return
        files = self.view.get_files()
        index = self.view.layout_engine.get_insertion_index(position + self.view._offset, self.view._labels_rect)
        moving = set(self._drag_paths)
        remaining = [path for path in files if path not in moving]
        slot = sum(path not in moving for path in files[:index])
        candidate = remaining[:slot] + self._drag_paths + remaining[slot:]
        if not remaining or candidate == files:
            return
        target = remaining[slot] if slot < len(remaining) else remaining[-1]
        placement = "before" if slot < len(remaining) else "after"
        self._target = (target, placement)
        item = self.view.state.get_item(target)
        x, y = item.label_pos
        gap = max(5, self.view._horizontal_spacing)
        x += item.label_size[0] + gap / 2 if placement == "after" else -gap / 2
        y += self.view.LABEL_INNER_SPACING - 4
        self.marker.setGeometry(QRect(round(x - self.view._offset.x() - 5), y - self.view._offset.y(),
                                      10, self.view.image_size + 8))
        self.marker.show()
        self.marker.raise_()

    def _auto_scroll(self):
        if not self._valid():
            self.cancel()
            return
        position = self.view.mapFromGlobal(QCursor.pos())
        viewport = QRect(0, 0, self.view.width() - self.view.v_scroll.width(),
                         self.view.height() - self.view.h_scroll.height())
        if viewport.isEmpty():
            self.marker.hide()
            self._target = None
            return

        def step(coordinate, length):
            band = min(40, length / 3)
            if coordinate < band:
                depth = (band - coordinate) / band
                direction = -1
            elif coordinate > length - band:
                depth = (coordinate - (length - band)) / band
                direction = 1
            else:
                return 0
            speed = self.view.SCROLL_DISTANCE_PER_FRAME * min(2.5, max(0.25, depth))
            return direction * max(1, round(speed))

        old_offset = self.view.get_scroll_offset()
        self.view.v_scroll.setValue(self.view.v_scroll.value() + step(position.y(), viewport.height()))
        self.view.h_scroll.setValue(self.view.h_scroll.value() + step(position.x(), viewport.width()))
        # Leaving the view is not the end of the drag. Continue scrolling, but only
        # show a valid insertion target when the pointer comes back into the content.
        if viewport.contains(position):
            if old_offset != self.view.get_scroll_offset() or position != self._pointer:
                self.update_position(position)
        else:
            self.marker.hide()
            self._target = None

    def drop(self, event):
        self.scroll_timer.stop()
        if not self.accepts(event):
            event.ignore()
            return
        self.update_position(event.pos())
        if self._target is None:
            event.ignore()
            return
        try:
            self.view.dict_manage.move_files_manually(self._drag_paths, *self._target)
        except Exception as exc:
            event.ignore()
            self.view.errorOccurred.emit(str(exc))
        else:
            event.setDropAction(Qt.MoveAction)
            event.accept()
        finally:
            self.leave()
