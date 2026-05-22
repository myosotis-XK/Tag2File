import os
import random
from functools import partial
from typing import Optional

from natsort import natsort_keygen
from PyQt5.QtCore import QPoint, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QCursor, QFont, QIcon, QMouseEvent, QPainter, QPalette, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QRubberBand,
    QScrollBar,
    QStyleOptionSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.DictManage import DictManage
from src.models import Background, Border, FileItem
from src.utils import config, format_file_size, init_config_section, save_config

from .FileSelectionComponent import FileSelectionComponent
from .file_grid import (
    ActionResult,
    FileActionService,
    FileGridLayoutEngine,
    FileGridState,
    FileViewModel,
    ThumbnailController,
    build_file_item,
)
from .media_viewers import AudioPlayer, MultiImageViewer

default_value = {
    "SMALL_SIZE": 50,
    "MEDIUM_SIZE": 100,
    "LARGE_SIZE": 250,
    "SPACING_RATE": 0.05,
    "current_image_size": "mid",
    "current_sort_key": "date",
    "current_sort_order": "desc",
    "WINDOW_FRAMES": 60,
    "SCROLL_DISTANCE_PER_SECOND": 500,
    "LABEL_SPACING": 5,
    "label_name_size": 20,
}
init_config_section("FileShowArea", default_value)

default_value = {
    "acceptFloder": "False",
}
init_config_section("TagFileShowArea", default_value)
save_config()


# ---------------- Base File Grid Widget ----------------

class FileShowArea(QWidget):
    selectionChanged = pyqtSignal(list)
    currentFileChanged = pyqtSignal(object)
    filesChanged = pyqtSignal(list)
    fileActivated = pyqtSignal(str)
    folderActivated = pyqtSignal(str)
    requestManageTags = pyqtSignal(list)
    requestRemoveFiles = pyqtSignal(list)
    errorOccurred = pyqtSignal(str)
    infoRequested = pyqtSignal(str)

    file_status_map = {
        (0, 0, 0): (Border.NONE, Background.TRANSPARENT),
        (0, 0, 1): (Border.NONE, Background.LIGHTBLUE),
        (0, 1, 0): (Border.NONE, Background.DARKBLUE),
        (0, 1, 1): (Border.BLUE, Background.DARKBLUE),
        (1, 0, 0): (Border.BLUE, Background.TRANSPARENT),
        (1, 0, 1): (Border.BLUE, Background.LIGHTBLUE),
        (1, 1, 0): (Border.BLUE, Background.DARKBLUE),
        (1, 1, 1): (Border.BLUE, Background.DARKBLUE),
    }

    def __init__(self, file_paths: list | None = None):
        super().__init__()
        self.dict_manage = DictManage()
        self.state = FileGridState()
        self.layout_engine = FileGridLayoutEngine()
        self.thumbnail_controller = ThumbnailController(self.applyIconSource, self)
        self.action_service = FileActionService(self.dict_manage)

        self.SMALL_SIZE = config.getint("FileShowArea", "SMALL_SIZE", fallback=50)
        self.MEDIUM_SIZE = config.getint("FileShowArea", "MEDIUM_SIZE", fallback=100)
        self.LARGE_SIZE = config.getint("FileShowArea", "LARGE_SIZE", fallback=250)
        self.current_image_size = config.get("FileShowArea", "current_image_size", fallback="mid")
        self.current_sort_key = config.get("FileShowArea", "current_sort_key", fallback="date")
        self.current_sort_order = config.get("FileShowArea", "current_sort_order", fallback="desc")
        self.WINDOW_FRAMES = config.getint("FileShowArea", "WINDOW_FRAMES", fallback=60)
        self.SCROLL_DISTANCE_PER_SECOND = config.getint(
            "FileShowArea", "SCROLL_DISTANCE_PER_SECOND", fallback=500
        )
        self.SCROLL_DISTANCE_PER_FRAME = self.SCROLL_DISTANCE_PER_SECOND / self.WINDOW_FRAMES
        self.SPACING_RATE = config.getfloat("FileShowArea", "SPACING_RATE", fallback=0.05)
        self.LABEL_SPACING = config.getint("FileShowArea", "LABEL_SPACING", fallback=5)
        self.label_name_size = config.getint("FileShowArea", "label_name_size", fallback=20)

        image_size_dict = {
            "small": self.SMALL_SIZE,
            "mid": self.MEDIUM_SIZE,
            "large": self.LARGE_SIZE,
        }
        self.image_size = image_size_dict[self.current_image_size]
        self.LABEL_INNER_SPACING = int(self.image_size * self.SPACING_RATE)
        self.label_width = self.image_size + 2 * self.LABEL_INNER_SPACING

        self._labels: dict[str, QLabel] = {}
        self._label_pool: list[QLabel] = []
        self._labels_rect: list[list[tuple[tuple[int, int], tuple[int, int], str] | None]] = []
        self._content_size = QSize(1000, 2000)
        self._offset = QPoint(0, 0)
        self._horizontal_spacing = self.LABEL_SPACING
        self._max_col = 0
        self._max_row = 0
        self._pending_thumbnail_files: list[str] = []
        self._last_thumbnail_request_key: tuple[int, frozenset[str]] | None = None

        self.mouse_press = False
        self.mouse_move = False

        self.child_widget: list[QWidget] = []
        self.image_viewers: list[QWidget] = []

        self.auto_scroll_timer = QTimer(self)
        self.auto_scroll_timer.setInterval(round(1000 / self.WINDOW_FRAMES))
        self.thumbnail_request_timer = QTimer(self)
        self.thumbnail_request_timer.setSingleShot(True)
        # 合并连续滚动产生的缩略图请求，避免每一帧都重提后台任务。
        self.thumbnail_request_timer.setInterval(30)
        self.thumbnail_request_timer.timeout.connect(self._flush_thumbnail_request)

        self.infoRequested.connect(self._show_info_message)
        self.errorOccurred.connect(self._show_error_message)

        self.initFileView()
        self.update_scrollbars()

        initial_paths = file_paths or []
        initial_meta = [(file_path, 0, 0) for file_path in initial_paths]
        self.set_files(initial_meta)

    # ---------------- QWidget Lifecycle ----------------

    def initFileView(self):
        # FileShowArea 自己维护滚动条和可视区域，而不是套一层 QScrollArea，
        # 这样可以更精细地控制懒加载、框选和标签复用。
        self.setAutoFillBackground(True)
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(255, 255, 255))
        self.setPalette(palette)

        self.v_scroll = QScrollBar(Qt.Vertical, self)
        self.v_scroll.setFixedWidth(15)
        self.v_scroll.valueChanged.connect(self.on_v_scroll)

        self.h_scroll = QScrollBar(Qt.Horizontal, self)
        self.h_scroll.setFixedHeight(15)
        self.h_scroll.valueChanged.connect(self.on_h_scroll)

        self.corner = QWidget(self)
        option = QStyleOptionSlider()
        self.v_scroll.initStyleOption(option)
        bg_color = self.v_scroll.style().standardPalette().color(QPalette.Button)
        self.corner.setStyleSheet(f"background-color: {bg_color.name()};")

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)
        self.setMouseTracking(True)

        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self.origin = QPoint()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updateLayout()

    def wheelEvent(self, event):
        delta = event.angleDelta()
        if delta.y() != 0:
            self.v_scroll.setValue(self.v_scroll.value() - int(delta.y() * 0.5))
        if delta.x() != 0:
            self.h_scroll.setValue(self.h_scroll.value() - int(delta.x() * 0.5))

    def closeEvent(self, event):
        self.thumbnail_controller.invalidate()
        self.auto_scroll_timer.stop()
        self.thumbnail_request_timer.stop()
        for widget in self.child_widget[:]:
            widget.close()
        for viewer in self.image_viewers[:]:
            viewer.close()
        super().closeEvent(event)

    # ---------------- Public API ----------------

    def set_files(self, file_meta_datas: list[tuple[str, int, float]] | None = None, recover_scroll: bool = False) -> None:
        if file_meta_datas is None:
            file_meta_datas = []
        file_meta_datas = self._normalize_file_meta_datas(file_meta_datas)
        file_paths = [file_meta_data[0] for file_meta_data in file_meta_datas]

        # 完整替换文件集时，先回收所有可见标签并使旧缩略图任务失效，
        # 再整体重建状态，避免 UI 还引用旧文件对象。
        self.thumbnail_controller.invalidate()
        self._recycle_all_labels()
        self.state.clear_ctrl_selection()
        self.state.clear_selection()
        self.state.set_files(file_paths)
        self._sync_file_items(file_meta_datas)
        self._sort_files()
        self.updateLayout(recover_scroll=recover_scroll)
        if not recover_scroll:
            self.v_scroll.setValue(0)
        self._emit_selection_changed()
        self._emit_current_changed()
        self.filesChanged.emit(self.get_files())

    def append_files(self, file_meta_datas: list[tuple[str, int, float]]) -> None:
        if not file_meta_datas:
            return
        file_meta_datas = self._normalize_file_meta_datas(file_meta_datas)
        new_paths = [item[0] for item in file_meta_datas if not self.state.contains(item[0])]
        if not new_paths:
            return
        self.state.append_files(new_paths)
        self._sync_file_items([item for item in file_meta_datas if item[0] in new_paths])
        self._sort_files()
        self.updateLayout()
        self.filesChanged.emit(self.get_files())

    def remove_files(self, file_paths: list[str]) -> None:
        if not file_paths:
            return
        for file_path in file_paths:
            if file_path in self._labels:
                self.recycleFileLabel(file_path)
        self.state.remove_files(file_paths)
        self.updateLayout()
        self._emit_selection_changed()
        self._emit_current_changed()
        self.filesChanged.emit(self.get_files())

    def refresh_files(self, file_paths: list[str] | None = None) -> None:
        if file_paths is None:
            file_paths = self.get_selected_files() or self.get_files()
        if not file_paths:
            return
        try:
            file_meta_datas = self.action_service.refresh_file_meta(file_paths)
        except Exception as exc:
            self.errorOccurred.emit(str(exc))
            return

        # 刷新时强制让这些文件重新走元数据和缩略图链路，
        # 这样文件内容变化后不会继续沿用旧缓存。
        for file_path in file_paths:
            if file_path in self._labels:
                self.recycleFileLabel(file_path)
            self.state.get_items().pop(file_path, None)
            cached_item = self.state.get_cached_item(file_path)
            if cached_item is not None:
                cached_item.icon = False
        self._sync_file_items(file_meta_datas)
        self.thumbnail_controller.load(self.state, file_paths, self.image_size, use_cache=False)
        self.updateLayout(recover_scroll=True)

    def get_files(self) -> list[str]:
        return self.state.get_files()

    def get_selected_files(self) -> list[str]:
        return self.state.get_selected_files()

    def get_current_file(self) -> Optional[str]:
        return self.state.get_current_file()

    def get_file_view(self, file_path: Optional[str]) -> Optional[FileViewModel]:
        if not file_path:
            return None
        file_item = self.state.get_item_if_exists(file_path)
        if file_item is None:
            return None
        return FileViewModel(
            file_path=file_item.file_path,
            file_name=file_item.file_name,
            file_size_bytes=file_item.file_size_bytes,
            file_date=file_item.file_date,
            label_pos=file_item.label_pos,
            label_size=file_item.label_size,
            icon_source=file_item.icon_source.get("current"),
        )

    def set_current_file(self, file_path: Optional[str], keep_selection: bool = False) -> None:
        previous = self.state.set_current_file(file_path)
        if previous and previous != file_path:
            self._refresh_item_style(previous)
        if file_path:
            if not keep_selection:
                changed_paths = self.state.clear_selection()
                self._refresh_item_styles(changed_paths)
                self.state.set_selected(file_path, True)
                self._refresh_item_style(file_path)
                self._emit_selection_changed()
            self._refresh_item_style(file_path)
        self._emit_current_changed()

    def scroll_to_file(self, file_path: str) -> None:
        file_item = self.state.get_item_if_exists(file_path)
        if file_item is None:
            return
        self.v_scroll.setValue(file_item.label_pos[1])

    def clear_selection(self) -> None:
        previous = self.state.clear_selection()
        self._refresh_item_styles(previous)
        self._emit_selection_changed()

    def get_scroll_offset(self) -> QPoint:
        return QPoint(self._offset)

    def set_scroll_offset(self, offset: QPoint | int) -> None:
        if isinstance(offset, int):
            x_value = self.h_scroll.value()
            y_value = offset
        else:
            x_value = offset.x()
            y_value = offset.y()
        self.h_scroll.setValue(max(0, x_value))
        self.v_scroll.setValue(max(0, y_value))

    def set_selected_files(self, file_paths: list[str], current_file: Optional[str] = None) -> None:
        previous = self.state.clear_selection()
        changed = set(previous)
        previous_current = self.state.set_current_file(current_file)
        if previous_current:
            changed.add(previous_current)
        valid_paths = [file_path for file_path in file_paths if self.state.contains(file_path)]
        for file_path in valid_paths:
            self.state.set_selected(file_path, True)
            changed.add(file_path)
        if current_file is not None and self.state.contains(current_file):
            changed.add(current_file)
        self._refresh_item_styles(changed)
        self._emit_selection_changed()
        self._emit_current_changed()

    # ---------------- Label Creation & Rendering ----------------

    def set_sort(self, sort_key: str, sort_order: str) -> None:
        self.current_sort_key = sort_key
        self.current_sort_order = sort_order
        config.set("FileShowArea", "current_sort_key", sort_key)
        config.set("FileShowArea", "current_sort_order", sort_order)
        save_config()
        self._sort_files()
        self.updateLayout(recover_scroll=True)

    def set_thumbnail_level(self, level: str) -> None:
        level_to_size = {
            "small": self.SMALL_SIZE,
            "mid": self.MEDIUM_SIZE,
            "large": self.LARGE_SIZE,
        }
        if level not in level_to_size:
            return
        self.current_image_size = level
        self.image_size = level_to_size[level]
        config.set("FileShowArea", "current_image_size", level)
        save_config()

        self.LABEL_INNER_SPACING = int(self.image_size * self.SPACING_RATE)
        self.label_width = self.image_size + 2 * self.LABEL_INNER_SPACING

        self.thumbnail_controller.invalidate()
        self._recycle_all_labels()
        for label in self._label_pool:
            icon_label = label.findChild(QLabel, "icon_label")
            file_name_label = label.findChild(QLabel, "file_name_label")
            icon_label.setFixedSize(self.image_size, self.image_size)
            icon_label.move(self.LABEL_INNER_SPACING, self.LABEL_INNER_SPACING)
            file_name_label.setFixedWidth(self.label_width - 4)
            file_name_label.move(2, self.label_width)

        for file_item in self.state.get_items().values():
            file_item.icon = False
            file_item.update_label_size(self.label_width)
        self.updateLayout(recover_scroll=True)

    def createFileLabel(self) -> QLabel:
        label = QLabel()
        label.setObjectName("file_label")

        icon_label = QLabel(label)
        icon_label.setObjectName("icon_label")
        icon_label.setStyleSheet("background-color: transparent;")
        icon_label.setFixedSize(self.image_size, self.image_size)
        icon_label.setAlignment(Qt.AlignHCenter | Qt.AlignBottom)
        icon_label.move(self.LABEL_INNER_SPACING, self.LABEL_INNER_SPACING)

        file_name_label = QLabel(label)
        file_name_label.setObjectName("file_name_label")
        file_name_label.setStyleSheet("background-color: transparent;")
        file_name_label.setWordWrap(True)
        file_name_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        file_name_label.setFixedWidth(self.label_width - 4)
        file_name_label.move(2, self.label_width)

        label.mouseDoubleClickEvent = partial(self.openFile, label=label)
        label.mousePressEvent = partial(self.onLabelLeftClick, label=label)
        label.setContextMenuPolicy(Qt.CustomContextMenu)
        label.customContextMenuRequested.connect(partial(self.showLabelMenu, label=label))
        label.enterEvent = partial(self.setBackgroundColorOnEnter, label=label)
        label.leaveEvent = self.resetBackgroundColorOnLeave
        label.setParent(self)
        label.hide()
        return label

    def setFileQLabel(self, file_path: str) -> None:
        file_item = self.state.get_item_if_exists(file_path)
        if file_item is None:
            return

        if not self._label_pool:
            self._label_pool.append(self.createFileLabel())

        label = self._label_pool.pop()
        icon_label = label.findChild(QLabel, "icon_label")
        file_name_label = label.findChild(QLabel, "file_name_label")
        label.file_path = file_path
        icon_label.file_path = file_path
        file_name_label.file_path = file_path

        file_item.apply(icon_label)
        file_name_label.setText("\u200B".join(file_item.file_name))
        file_name_label.setFixedHeight(file_item.name_height)

        label.setFixedSize(QSize(file_item.label_size[0], file_item.label_size[1]))
        label.move(QPoint(file_item.label_pos[0], file_item.label_pos[1]) - self._offset)
        self._labels[file_path] = label
        self._refresh_item_style(file_path)
        label.show()

    def applyIconSource(self, file_path: str) -> None:
        if file_path not in self._labels:
            return
        file_item = self.state.get_item_if_exists(file_path)
        if file_item is None:
            return
        icon_label = self._labels[file_path].findChild(QLabel, "icon_label")
        file_item.apply(icon_label)

    # ---------------- Layout / Virtualization ----------------

    def updateLayout(self, recover_scroll: bool = True):
        # 布局引擎只负责算位置；真正的 QLabel 创建、回收和移动仍留在控件层。
        scroll_percentage = self.v_scroll.value() / self.v_scroll.maximum() if self.v_scroll.maximum() else 0
        snapshot = self.layout_engine.compute_layout(
            file_paths=self.state.get_files(),
            file_items=self.state.get_items(),
            area_width=self.width(),
            area_height=self.height(),
            label_width=self.label_width,
            label_spacing=self.LABEL_SPACING,
            v_scroll_width=self.v_scroll.width(),
            h_scroll_height=self.h_scroll.height(),
        )
        self._labels_rect = snapshot.labels_rect
        self._content_size = snapshot.content_size
        self._horizontal_spacing = snapshot.horizontal_spacing
        self._max_col = snapshot.max_col
        self._max_row = snapshot.max_row

        if self._offset.y() > self._content_size.height() - self.height():
            self._offset.setY(max(0, self._content_size.height() - self.height()))

        self.update_scrollbars()
        if recover_scroll and self.v_scroll.maximum():
            self.v_scroll.setValue(int(scroll_percentage * self.v_scroll.maximum()))
        self.lazy_load()

    def lazy_load(self):
        # 只保留视口附近的标签，向上下各扩一段缓冲区，
        # 用来减少快速滚动时频繁创建/销毁控件带来的抖动。
        visible_rect = QRect(self._offset, self._offset + self.rect().bottomRight())
        extra_h = int(visible_rect.height() * 0.5)
        visible_rect.adjust(0, -extra_h, 0, extra_h)

        visible_files = self.layout_engine.get_files_in_rect(
            rect=visible_rect,
            labels_rect=self._labels_rect,
            label_width=self.label_width,
            label_spacing=self.LABEL_SPACING,
            max_row=self._max_row,
            max_col=self._max_col,
        )

        for file_path in self.state.get_visible_files() - visible_files:
            if file_path in self._labels:
                self.recycleFileLabel(file_path)

        for file_path in visible_files:
            if file_path not in self._labels:
                self.setFileQLabel(file_path)
            else:
                label = self._labels[file_path]
                file_item = self.state.get_item(file_path)
                label.move(QPoint(file_item.label_pos[0], file_item.label_pos[1]) - self._offset)
                label.show()

        self.state.set_visible_files(visible_files)
        # 标签位置照常即时更新；缩略图请求延后一点统一提交。
        self._schedule_thumbnail_request(visible_files)
        self.v_scroll.raise_()
        self.h_scroll.raise_()
        self.corner.raise_()

    # ---------------- Selection / Scrolling ----------------

    def mousePressEvent(self, event):
        self.setFocus()
        if event.button() != Qt.LeftButton:
            return

        self.mouse_press = True
        if not event.modifiers() & Qt.ControlModifier:
            previous = self.state.clear_selection()
            self._refresh_item_styles(previous)
            self._emit_selection_changed()
        else:
            self.state.snapshot_selection()
        self.origin = event.pos() + self._offset

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.mouse_press:
            return
        if event.buttons() & Qt.LeftButton:
            # 框选命中的判定基于内容坐标系，所以这里要把鼠标位置和滚动偏移统一换算。
            self.rubber_band.setGeometry(QRect(self.origin - self._offset, event.pos()).normalized())
            self.rubber_band.show()
            self.selectLabelsInRect(QRect(self.origin, event.pos() + self._offset).normalized(), event.modifiers())
            if self.rect().contains(event.pos()):
                self.auto_scroll_timer.stop()
            else:
                self.autoScroll(event.pos())
        else:
            self.mouseReleaseEvent(event)

    def mouseReleaseEvent(self, event):
        if self.mouse_press and event.button() == Qt.LeftButton:
            self.rubber_band.hide()
        self.auto_scroll_timer.stop()
        self.mouse_press = False
        self.state.clear_ctrl_selection()

    def selectLabelsInRect(self, rubber_rect: QRect, modifiers):
        selected = self.layout_engine.get_files_in_rect(
            rect=rubber_rect,
            labels_rect=self._labels_rect,
            label_width=self.label_width,
            label_spacing=self.LABEL_SPACING,
            max_row=self._max_row,
            max_col=self._max_col,
        )
        changed: set[str] = set()
        if not modifiers & Qt.ControlModifier:
            current_selected = self.state.get_selected_set()
            for file_path in current_selected - selected:
                self.state.set_selected(file_path, False)
                changed.add(file_path)
            for file_path in selected - current_selected:
                self.state.set_selected(file_path, True)
                changed.add(file_path)
        else:
            ctrl_previous = self.state.get_ctrl_selection()
            snapshot = self.state.get_selection_snapshot()
            for file_path in ctrl_previous - selected:
                should_select = file_path in snapshot
                self.update_label_select_status(file_path, should_select)
                changed.add(file_path)
            for file_path in selected - ctrl_previous:
                should_select = file_path not in snapshot
                self.update_label_select_status(file_path, should_select)
                changed.add(file_path)
            self.state.set_ctrl_selection(selected)

        self._refresh_item_styles(changed)
        self._emit_selection_changed()

    def update_label_select_status(self, file_path: str, should_select: bool):
        self.state.set_selected(file_path, should_select)

    def on_v_scroll(self, value):
        self._offset.setY(value)
        self.on_scroll()

    def on_h_scroll(self, value):
        self._offset.setX(value)
        self.on_scroll()

    def on_scroll(self):
        self.lazy_load()
        local_pos = self.mapFromGlobal(QCursor.pos())
        if self.mouse_press:
            # 滚动过程中如果仍在框选，需要同步更新橡皮筋位置和命中结果。
            x = max(1, min(local_pos.x(), self.width() - 1))
            y = max(1, min(local_pos.y(), self.height() - 1))
            widget_pos = self.mapFrom(self, QPoint(x, y))
            self.rubber_band.setGeometry(QRect(self.origin - self._offset, widget_pos).normalized())
            self.rubber_band.show()
            self.selectLabelsInRect(
                QRect(self.origin, widget_pos + self._offset).normalized(),
                QApplication.keyboardModifiers(),
            )
        else:
            label = self.childAt(local_pos)
            if isinstance(label, QLabel) and hasattr(label, "file_path"):
                file_path = label.file_path
                label = self._labels.get(file_path)
            else:
                file_path = None
            if file_path != self.state.get_hover_file():
                if self.state.get_hover_file():
                    self.resetBackgroundColorOnLeave(None)
                if isinstance(label, QLabel):
                    self.setBackgroundColorOnEnter(None, label)
        self.update()

    def update_scrollbars(self):
        w, h = self.width(), self.height()
        cw, ch = self._content_size.width(), self._content_size.height()

        self.v_scroll.setGeometry(w - 15, 0, 15, h - 15)
        self.v_scroll.setMinimum(0)
        self.v_scroll.setMaximum(max(0, ch - h))
        self.v_scroll.setPageStep(h)
        self.v_scroll.setValue(self._offset.y())

        self.h_scroll.setGeometry(0, h - 15, w - 15, 15)
        self.h_scroll.setMinimum(0)
        self.h_scroll.setMaximum(max(0, cw - w))
        self.h_scroll.setPageStep(w)
        self.h_scroll.setValue(self._offset.x())
        self.corner.setGeometry(w - 15, h - 15, 15, 15)

    def autoScroll(self, mouse_pos: QPoint, auto: bool = False):
        scroll_area_rect = self.rect()
        if mouse_pos.y() < scroll_area_rect.top():
            movement_scale = max(0.5, -(mouse_pos.y() - scroll_area_rect.top()) / 50)
            move_value = round(movement_scale * self.SCROLL_DISTANCE_PER_FRAME)
            self.v_scroll.setValue(self.v_scroll.value() - move_value)
        elif mouse_pos.y() > scroll_area_rect.bottom():
            movement_scale = max(0.5, (mouse_pos.y() - scroll_area_rect.bottom()) / 50)
            move_value = round(movement_scale * self.SCROLL_DISTANCE_PER_FRAME)
            self.v_scroll.setValue(self.v_scroll.value() + move_value)

        if not auto:
            try:
                self.auto_scroll_timer.timeout.disconnect()
            except TypeError:
                pass
            self.auto_scroll_timer.timeout.connect(lambda: self.autoScroll(mouse_pos, True))
            if not self.auto_scroll_timer.isActive():
                self.auto_scroll_timer.start()

    # ---------------- Menus / File Operations ----------------

    def showContextMenu(self, pos: QPoint):
        previous = self.state.clear_selection()
        self._refresh_item_styles(previous)
        self._emit_selection_changed()

        context_menu = QMenu(self)
        self.addViewMenu(context_menu)
        self.addSortMenu(context_menu)
        select_all_action = QAction("全选", self)
        select_all_action.triggered.connect(self.select_all_file)
        context_menu.addAction(select_all_action)

        global_pos = self.mapToGlobal(pos)
        context_menu.exec_(global_pos)

    def addViewMenu(self, context_menu: QMenu):
        view_menu = context_menu.addMenu("查看")

        small_action = QAction("小图标", self)
        small_action.triggered.connect(lambda: self.set_thumbnail_level("small"))
        if self.current_image_size == "small":
            small_action.setIcon(QIcon(self.create_black_dot(6)))

        medium_action = QAction("中等图标", self)
        medium_action.triggered.connect(lambda: self.set_thumbnail_level("mid"))
        if self.current_image_size == "mid":
            medium_action.setIcon(QIcon(self.create_black_dot(6)))

        large_action = QAction("大图标", self)
        large_action.triggered.connect(lambda: self.set_thumbnail_level("large"))
        if self.current_image_size == "large":
            large_action.setIcon(QIcon(self.create_black_dot(6)))

        view_menu.addAction(small_action)
        view_menu.addAction(medium_action)
        view_menu.addAction(large_action)

    def addSortMenu(self, context_menu: QMenu):
        sort_menu = context_menu.addMenu("排序")

        for key, text in [
            ("name", "按文件名"),
            ("size", "按文件大小"),
            ("date", "按修改日期"),
            ("random", "随机排序"),
        ]:
            action = QAction(text, self)
            action.triggered.connect(lambda _, sort_key=key: self.set_sort(sort_key, self.current_sort_order))
            if self.current_sort_key == key:
                action.setIcon(QIcon(self.create_black_dot(6)))
            sort_menu.addAction(action)

        sort_menu.addSeparator()
        asc_action = QAction("升序", self)
        asc_action.triggered.connect(lambda: self.set_sort(self.current_sort_key, "asc"))
        if self.current_sort_order == "asc":
            asc_action.setIcon(QIcon(self.create_black_dot(6)))

        desc_action = QAction("降序", self)
        desc_action.triggered.connect(lambda: self.set_sort(self.current_sort_key, "desc"))
        if self.current_sort_order == "desc":
            desc_action.setIcon(QIcon(self.create_black_dot(6)))

        sort_menu.addAction(asc_action)
        sort_menu.addAction(desc_action)

    def select_all_file(self):
        changed = self.state.select_all()
        self._refresh_item_styles(changed)
        if not self.state.get_current_file() and self.get_files():
            self.state.set_current_file(self.get_files()[0])
            self._refresh_item_style(self.get_files()[0])
            self._emit_current_changed()
        self._emit_selection_changed()

    def onLabelLeftClick(self, event: QMouseEvent, label: QLabel):
        if event.button() != Qt.LeftButton:
            return
        file_path = label.file_path
        if event.modifiers() & Qt.ControlModifier:
            self.state.snapshot_selection()
            should_select = file_path not in self.state.get_selection_snapshot()
            self.update_label_select_status(file_path, should_select)
            self._refresh_item_style(file_path)
            self._emit_selection_changed()
        else:
            previous, current = self.state.select_only(file_path)
            self._refresh_item_styles(previous | current)
            self._emit_selection_changed()

        previous_current = self.state.set_current_file(file_path)
        if previous_current and previous_current != file_path:
            self._refresh_item_style(previous_current)
        self._refresh_item_style(file_path)
        self._emit_current_changed()

        self.mouse_press = True
        self.origin = label.mapTo(self, event.pos()) + self._offset

    def openFile(self, event, label: QLabel, default: bool = False):
        file_path = label.file_path
        if not os.path.exists(file_path):
            self.errorOccurred.emit(f"无法打开文件：\n{file_path}\n文件已不存在。")
            return

        if os.path.isdir(file_path):
            if self._handle_directory_activation(file_path):
                return
            try:
                os.startfile(file_path)
            except Exception as exc:
                self.errorOccurred.emit(f"无法打开文件：\n{file_path}\n{exc}")
            return

        self.fileActivated.emit(file_path)

        supported_image_formats = [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"]
        supported_audio_formats = [".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".wma"]
        ext = os.path.splitext(file_path)[1].lower()

        if not default and ext in supported_image_formats:
            image_viewer = MultiImageViewer()
            self.image_viewers.append(image_viewer)
            image_viewer.destroyed.connect(lambda: self.image_viewers.remove(image_viewer))
            image_viewer.load_image_files(self.get_files(), file_path)
            image_viewer.show()
        elif not default and ext in supported_audio_formats:
            audio_player = AudioPlayer(file_path, self.get_files())
            self.image_viewers.append(audio_player)
            audio_player.destroyed.connect(lambda: self.image_viewers.remove(audio_player))
            audio_player.show()
        else:
            try:
                os.startfile(file_path)
            except Exception as exc:
                self.errorOccurred.emit(f"无法打开文件：\n{file_path}\n{exc}")

    def showLabelMenu(self, pos: QPoint, label: QLabel):
        file_path = label.file_path
        if file_path not in self.state.get_selected_set():
            previous = self.state.clear_selection()
            self._refresh_item_styles(previous)
            if not self.isMouseOnThumbnail(pos, label):
                self.customContextMenuRequested.emit(label.mapTo(self, pos))
                return None

        previous_current = self.state.get_current_file()
        if previous_current and previous_current != file_path:
            self.state.set_current_file(file_path)
            self._refresh_item_style(previous_current)
        else:
            self.state.set_current_file(file_path)

        self.state.set_selected(file_path, True)
        self._refresh_item_style(file_path)
        self._emit_selection_changed()
        self._emit_current_changed()

        # 右键菜单的“选中项”语义和左键保持一致：
        # 如果当前项不在选区内，先把它提升为当前选中项，再弹出菜单。
        context_menu = QMenu(self)
        properties_action = QAction("属性", self)
        properties_action.triggered.connect(lambda: self.displayImageProperties(file_path))
        context_menu.addAction(properties_action)

        if os.path.exists(file_path):
            file_menu = context_menu.addMenu("文件操作")

            open_default_action = QAction("系统默认方式打开", self)
            open_default_action.triggered.connect(lambda: self.openFile(None, label, default=True))
            file_menu.addAction(open_default_action)

            open_folder_action = QAction("打开文件所在位置", self)
            open_folder_action.triggered.connect(lambda: self._handle_action_result(self.action_service.open_folder(file_path)))
            file_menu.addAction(open_folder_action)

            copy_file_action = QAction("复制", self)
            copy_file_action.triggered.connect(lambda: self.changeFilePathMessageBox("copy"))
            file_menu.addAction(copy_file_action)

            move_file_action = QAction("剪切", self)
            move_file_action.triggered.connect(lambda: self.changeFilePathMessageBox("cut"))
            file_menu.addAction(move_file_action)

            rename_file_action = QAction("重命名", self)
            rename_file_action.triggered.connect(lambda: self.renameFile(file_path))
            file_menu.addAction(rename_file_action)

            delete_file_action = QAction("删除", self)
            delete_file_action.triggered.connect(lambda: self.confirmDelete(os_delete=True))
            file_menu.addAction(delete_file_action)
        else:
            select_invalid_action = QAction("选中所有失效文件", self)
            select_invalid_action.triggered.connect(self.selectAllUnvalidFile)
            context_menu.addAction(select_invalid_action)

            repair_file_action = QAction("修复文件", self)
            repair_file_action.triggered.connect(self.repairFile)
            context_menu.addAction(repair_file_action)

        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(lambda: self.refresh_files(self.get_selected_files()))
        context_menu.addAction(refresh_action)

        delete_from_base_action = QAction("从库中删除", self)
        delete_from_base_action.triggered.connect(self.confirmDelete)
        context_menu.addAction(delete_from_base_action)

        global_pos = label.mapToGlobal(QPoint(0, 0)) + pos
        return context_menu, global_pos

    def changeFilePathMessageBox(self, file_action: str):
        selected_files = self.get_selected_files()
        if not selected_files:
            return
        parent_path = os.path.dirname(selected_files[0])
        options = QFileDialog.Options()
        options |= QFileDialog.ShowDirsOnly
        target_folder = QFileDialog.getExistingDirectory(self, "选择目标文件夹", parent_path, options=options)
        if not target_folder:
            return

        move_tags = file_action == "cut"
        if file_action == "copy":
            reply = QMessageBox.question(
                self,
                "提示",
                "是否同步复制标签？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            move_tags = reply == QMessageBox.Yes

        result = self.action_service.copy_or_move_files(selected_files, target_folder, file_action, move_tags)
        self._handle_action_result(result)

    def renameFile(self, file_path: str):
        new_name, ok = QInputDialog.getText(
            self,
            "重命名文件",
            "请输入新的文件名：",
            text=os.path.basename(file_path),
        )
        if not ok or not new_name:
            return
        result = self.action_service.rename_file(file_path, new_name)
        self._handle_action_result(result)

    def confirmDelete(self, os_delete: bool = False):
        if os_delete:
            message = "确定要删除选中的文件吗？此操作将在系统层删除文件！"
        else:
            message = "确定要从库中删除选中的文件吗？"
        reply = QMessageBox.question(self, "确认删除", message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            result = self.action_service.delete_files(self.get_selected_files(), os_delete=os_delete)
            self._handle_action_result(result)

    def selectAllUnvalidFile(self):
        previous = self.state.clear_selection()
        self._refresh_item_styles(previous)
        for file_path in self.get_files():
            if not os.path.exists(file_path):
                self.state.set_selected(file_path, True)
                self._refresh_item_style(file_path)
        self._emit_selection_changed()

    def repairFile(self):
        selected_missing = [file_path for file_path in self.get_selected_files() if not os.path.exists(file_path)]
        if not selected_missing:
            self.infoRequested.emit("当前没有选中失效文件。")
            return

        options = QFileDialog.Options()
        options |= QFileDialog.ShowDirsOnly
        folder_path = QFileDialog.getExistingDirectory(self, "选择候选文件所在文件夹", options=options)
        if not folder_path:
            return

        repair_file_groups, repair_group_titles, originals = self.action_service.build_repair_candidates(selected_missing, folder_path)
        if not repair_file_groups:
            self.infoRequested.emit("当前没有需要修复的失效文件。")
            return

        def repair_initial_selector(group_files_list):
            return [group_files_list[0]] if group_files_list else []

        self.repair_dialog = FileSelectionComponent(
            parent=self,
            file_groups=repair_file_groups,
            selection_type="single",
            image_size=180,
            group_titles=repair_group_titles,
            initial_selection_handler=repair_initial_selector,
        )

        def handle_repair_selection(selected_groups_2d):
            mapping: dict[str, str] = {}
            for index, group_selection in enumerate(selected_groups_2d):
                if index >= len(originals) or not group_selection:
                    continue
                mapping[originals[index]] = group_selection[0]
            if not mapping:
                return
            result = self.action_service.repair_files(mapping)
            self._handle_action_result(result)

        self.repair_dialog.result_selected.connect(handle_repair_selection)
        self.repair_dialog.show()

    def displayImageProperties(self, file_path: str):
        view = self.get_file_view(file_path)
        if view is None:
            return

        widget = QWidget()
        self.child_widget.append(widget)
        widget.destroyed.connect(lambda: self.child_widget.remove(widget) if widget in self.child_widget else None)
        widget.setWindowTitle(f"{view.file_name} 属性")
        widget.resize(500, 300)

        text_edit = QTextEdit(widget)
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Arial", 12))

        tags = self.dict_manage.query("file", file_path, "tag")
        tags_str = ", ".join(list(tags)) if tags else "无标签"
        message = (
            f"<b>文件名:</b>&nbsp; {view.file_name}<br><br>"
            f"<b>文件路径:</b>&nbsp; {view.file_path}<br><br>"
            f"<b>文件大小:</b>&nbsp; {view.formatted_size}<br><br>"
            f"<b>修改时间:</b>&nbsp; {view.formatted_date}<br><br>"
            f"<b>文件标签:</b>&nbsp; {tags_str}"
        )
        text_edit.setHtml(message)

        ok_button = QPushButton("确定", widget)
        ok_button.clicked.connect(widget.close)

        layout = QVBoxLayout(widget)
        layout.addWidget(text_edit)
        layout.addWidget(ok_button)
        widget.setLayout(layout)

        mouse_position = QCursor.pos()
        screen_geometry = QApplication.desktop().availableGeometry()
        x = mouse_position.x() - 250
        y = mouse_position.y() - 150
        if x + widget.width() > screen_geometry.right():
            x = screen_geometry.right() - widget.width() - 30
        if y + widget.height() > screen_geometry.bottom():
            y = screen_geometry.bottom() - widget.height() - 50
        if x < screen_geometry.left():
            x = screen_geometry.left() + 30
        if y < screen_geometry.top():
            y = screen_geometry.top() + 30
        widget.move(x, y)
        widget.show()

    # ---------------- Internal Helpers ----------------

    def recycleFileLabel(self, file_path: str):
        label = self._labels.pop(file_path)
        file_item = self.state.get_item(file_path)
        icon_label = label.findChild(QLabel, "icon_label")
        file_item.release(icon_label)
        label.hide()
        self._label_pool.append(label)

    def create_black_dot(self, size: int):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(Qt.black)
        painter.drawEllipse(0, 0, size, size)
        painter.end()
        return pixmap

    def isMouseOnThumbnail(self, mouse_pos: QPoint, label: QLabel):
        icon_label = label.findChild(QLabel, "icon_label")
        pixmap = icon_label.pixmap()
        if pixmap is None:
            return True
        pixmap_size = pixmap.size()
        offset_x = (self.image_size - pixmap_size.width()) // 2
        offset_y = self.image_size - pixmap_size.height()
        thumbnail_rect = QRect(
            offset_x + self.LABEL_INNER_SPACING,
            offset_y + self.LABEL_INNER_SPACING,
            pixmap_size.width(),
            pixmap_size.height(),
        )
        return thumbnail_rect.contains(mouse_pos)

    def set_file_css(self, file_item: FileItem):
        border, background = self.file_status_map[(file_item.specifid, file_item.selected, file_item.hover)]
        if border != file_item.border or background != file_item.background:
            file_item.border = border
            file_item.background = background
        label = self._labels.get(file_item.file_path)
        if label:
            style = f"""
            QLabel#{label.objectName()} {{
                {file_item.border.value}
                {file_item.background.value}
            }}
            """
            label.setStyleSheet(style)

    def setBackgroundColorOnEnter(self, event, label: QLabel):
        file_path = label.file_path
        previous = self.state.set_hover_file(file_path)
        if previous and previous != file_path:
            self._refresh_item_style(previous)
        self._refresh_item_style(file_path)

    def resetBackgroundColorOnLeave(self, event):
        previous = self.state.set_hover_file(None)
        if previous:
            self._refresh_item_style(previous)

    def _handle_directory_activation(self, file_path: str) -> bool:
        return False

    def _normalize_file_meta_datas(self, file_meta_datas: list[tuple[str, int, float]]) -> list[tuple[str, int, float]]:
        # 外部传入 (path, 0, 0) 时，按“需要即时补齐元数据”处理，
        # 让 append / set_files / 刷新入口都能共用同一种输入格式。
        normalized: list[tuple[str, int, float]] = []
        for file_path, file_size, file_date in file_meta_datas:
            if (file_size == 0 and file_date == 0) and os.path.exists(file_path):
                stat_info = os.stat(file_path)
                normalized.append((file_path, stat_info.st_size, stat_info.st_mtime))
            else:
                normalized.append((file_path, file_size, file_date))
        return normalized

    def _sync_file_items(self, file_meta_datas: list[tuple[str, int, float]]) -> None:
        for file_meta_data in file_meta_datas:
            file_path = file_meta_data[0]
            cached_item = self.state.get_cached_item(file_path)
            file_item = build_file_item(file_meta_data, self.label_width, self.image_size, cached_item)
            self.state.set_item(file_path, file_item)
            self._refresh_item_style(file_path)

    def _sort_files(self):
        file_paths = self.get_files()
        if self.current_sort_key == "name":
            nkey = natsort_keygen(key=lambda path: self.state.get_item(path).file_name)
            file_paths.sort(key=nkey, reverse=(self.current_sort_order == "desc"))
        elif self.current_sort_key == "size":
            file_paths.sort(
                key=lambda path: self.state.get_item(path).file_size_bytes,
                reverse=(self.current_sort_order == "desc"),
            )
        elif self.current_sort_key == "date":
            file_paths.sort(
                key=lambda path: self.state.get_item(path).file_date,
                reverse=(self.current_sort_order == "desc"),
            )
        elif self.current_sort_key == "random":
            random.shuffle(file_paths)
        self.state.reorder_files(file_paths)

    def _recycle_all_labels(self):
        for file_path in list(self._labels.keys()):
            self.recycleFileLabel(file_path)
        self.state.set_visible_files(set())

    def _schedule_thumbnail_request(self, visible_files: set[str]) -> None:
        request_key = (self.image_size, frozenset(visible_files))
        if request_key == self._last_thumbnail_request_key:
            return
        # 滚动期间只保留“最后一次看到的可见集”，等定时器触发时再真正提交。
        self._pending_thumbnail_files = list(visible_files)
        self.thumbnail_request_timer.start()

    def _flush_thumbnail_request(self) -> None:
        if not self._pending_thumbnail_files:
            return
        request_key = (self.image_size, frozenset(self._pending_thumbnail_files))
        if request_key == self._last_thumbnail_request_key:
            return
        self._last_thumbnail_request_key = request_key
        self.thumbnail_controller.load(self.state, self._pending_thumbnail_files, self.image_size)

    def _refresh_item_style(self, file_path: str):
        file_item = self.state.get_item_if_exists(file_path)
        if file_item is None:
            return
        file_item.specifid = 1 if self.state.get_current_file() == file_path else 0
        file_item.selected = 1 if self.state.is_selected(file_path) else 0
        file_item.hover = 1 if self.state.get_hover_file() == file_path else 0
        self.set_file_css(file_item)

    def _refresh_item_styles(self, file_paths):
        for file_path in file_paths:
            self._refresh_item_style(file_path)

    def _emit_selection_changed(self):
        self.selectionChanged.emit(self.get_selected_files())

    def _emit_current_changed(self):
        self.currentFileChanged.emit(self.get_current_file())

    def _show_info_message(self, message: str):
        QMessageBox.information(self, "提示", message)

    def _show_error_message(self, message: str):
        QMessageBox.critical(self, "错误", message)

    def _handle_action_result(self, result: ActionResult):
        if result.path_mapping:
            # 文件移动/重命名后，外层仍以旧路径列表为主；
            # 这里统一把当前文件集替换成新路径，避免调用方自己维护映射。
            updated_files = []
            for file_path in self.get_files():
                updated_files.append(result.path_mapping.get(file_path, file_path))
            deduped_files = []
            seen = set()
            for file_path in updated_files:
                if file_path not in seen:
                    deduped_files.append(file_path)
                    seen.add(file_path)
            if deduped_files != self.get_files():
                self.set_files([(file_path, 0, 0) for file_path in deduped_files], recover_scroll=True)

        if result.errors:
            self.errorOccurred.emit("\n".join(result.errors))


# ---------------- Scenario Specializations ----------------

class MainFileShowArea(FileShowArea):
    def __init__(self, main_window, file_paths: list | None = None):
        super().__init__(file_paths)
        self.main_window = main_window

    def _handle_directory_activation(self, file_path: str) -> bool:
        self.folderActivated.emit(file_path)
        return True

    def showLabelMenu(self, pos: QPoint, label: QLabel):
        result = super().showLabelMenu(pos, label)
        if result is None:
            return
        context_menu, global_pos = result

        tag_action = QAction("管理标签", self)
        tag_action.triggered.connect(lambda: self.requestManageTags.emit(self.get_selected_files()))
        context_menu.insertAction(context_menu.actions()[0], tag_action)
        context_menu.exec_(global_pos)


class TagFileShowArea(FileShowArea):
    def __init__(self, file_paths: list | None = None):
        self.prompt_label = QLabel("请拖入文件或文件夹")
        self.prompt_label.setAlignment(Qt.AlignCenter)
        self.prompt_label.setStyleSheet(
            """
            color: gray;
            font-size: 16px;
        """
        )
        self.prompt_label.hide()

        super().__init__(file_paths)
        self.prompt_label.setParent(self)

        self.setAcceptDrops(True)
        self._accept_folder = config.getboolean("TagFileShowArea", "acceptFloder", fallback=False)

    def accepts_folder(self) -> bool:
        return self._accept_folder

    def set_accept_folder(self, enabled: bool) -> None:
        self._accept_folder = enabled
        config.set("TagFileShowArea", "acceptFloder", str(enabled))
        save_config()

    def showLabelMenu(self, pos: QPoint, label: QLabel):
        result = super().showLabelMenu(pos, label)
        if result is None:
            return
        context_menu, global_pos = result
        remove_action = QAction("移除", self)
        remove_action.triggered.connect(self.removeSelectedFiles)
        context_menu.addAction(remove_action)
        context_menu.exec_(global_pos)

    def removeSelectedFiles(self):
        selected = self.get_selected_files()
        if not selected:
            return
        self.requestRemoveFiles.emit(selected)
        self.remove_files(selected)

    def updateLayout(self, recover_scroll: bool = True):
        super().updateLayout(recover_scroll=recover_scroll)
        if len(self.get_files()) == 0:
            parent_width = self.width()
            parent_height = self.height()
            label_width = self.prompt_label.width()
            label_height = self.prompt_label.height()
            self.prompt_label.move((parent_width - label_width) // 2, (parent_height - label_height) // 2)
            self.prompt_label.show()
        else:
            self.prompt_label.hide()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        file_paths = self.action_service.collect_files(paths, self._accept_folder)
        existing = set(self.get_files())
        file_paths = [file_path for file_path in file_paths if file_path not in existing]
        self.append_files([(file_path, 0, 0) for file_path in file_paths])
