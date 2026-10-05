from datetime import datetime

from PyQt5.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.DictManage import DictManage
from src.ui.components.style_utils import apply_panel_style, apply_scroll_area_style, create_button, create_colored_label
from src.ui.media_viewers import ImageViewer
from src.ui.ui_text import CommonText, SingleFileTagViewText
from src.utils.image_loader import load_pixmap

from .FileShowArea import TagFileShowArea


# ---------------- Single File Detail View ----------------

class SingleFileTagView(QScrollArea):
    def __init__(self, file_paths: str, TagFileShowArea: TagFileShowArea):
        super().__init__()
        self.DictManage = DictManage()
        self.DictManage.tagChanged.connect(self._on_data_changed)
        self.DictManage.categoryChanged.connect(self._on_data_changed)
        self.DictManage.fileChanged.connect(self._on_file_changed)
        self.DictManage.tagFileRelationChanged.connect(self._on_relation_changed)
        self.DictManage.tagbaseChanged.connect(self._on_tagbase_changed)
        self._tags_dirty = True
        self._preview_dirty = True
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._flush_refresh)
        self.TagFileShowArea = TagFileShowArea
        self.TagFileShowArea.thumbnailReady.connect(self._on_thumbnail_ready)
        self.file_paths = file_paths
        self.current_index = 0
        self.current_file_path = self.file_paths[0] if self.file_paths else None
        self.initUI()

    def initUI(self):
        # 左侧专注预览当前文件，右侧显示当前文件的元数据和标签，
        # 让单文件模式更适合顺序标注和快速浏览。
        self.setStyleSheet("""
            QScrollArea {
                background-color: #f4f7fb;
                border: none;
            }
        """)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setMinimumSize(200, 200)

        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        self.fileinfo_card = QWidget()
        apply_panel_style(self.fileinfo_card, tone="soft")
        fileinfo_card_layout = QVBoxLayout(self.fileinfo_card)
        fileinfo_card_layout.setContentsMargins(8, 8, 8, 8)
        fileinfo_card_layout.setSpacing(10)

        fileinfo_area = QScrollArea()
        fileinfo_area.setWidgetResizable(True)
        apply_scroll_area_style(fileinfo_area, tone="soft")
        fileinfo_widget = QWidget()
        fileinfo_widget.setStyleSheet("background-color: #f8fbff;")

        self.file_name_value = QLabel(fileinfo_widget)
        self.file_name_value.setWordWrap(True)
        self.file_name_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.file_name_value.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border: none;
                color: #1f2d3d;
                font-size: 14px;
                font-weight: 600;
                padding: 2px;
            }
        """)
        self.path_value = self._create_info_value_label(fileinfo_widget)
        self.size_value = self._create_info_value_label(fileinfo_widget)
        self.modified_time_value = self._create_info_value_label(fileinfo_widget)

        layout = QVBoxLayout(fileinfo_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)
        layout.addWidget(self.file_name_value)
        layout.addWidget(self._create_info_row(self.tr(CommonText.FILE_PATH), self.path_value, fileinfo_widget))
        layout.addWidget(self._create_info_row(self.tr(CommonText.FILE_SIZE), self.size_value, fileinfo_widget))
        layout.addWidget(self._create_info_row(self.tr(CommonText.MODIFIED_TIME), self.modified_time_value, fileinfo_widget))
        layout.addStretch()
        fileinfo_area.setWidget(fileinfo_widget)
        fileinfo_area.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        fileinfo_area.setMaximumWidth(250)
        fileinfo_card_layout.addWidget(fileinfo_area)
        right_layout.addWidget(self.fileinfo_card)

        self.tag_card = QWidget()
        apply_panel_style(self.tag_card, tone="soft")
        tag_card_layout = QVBoxLayout(self.tag_card)
        tag_card_layout.setContentsMargins(8, 8, 8, 8)

        tag_area = QScrollArea()
        tag_area.setWidgetResizable(True)
        apply_scroll_area_style(tag_area, tone="soft")
        tag_widget = QWidget()
        tag_widget.setStyleSheet("background-color: #f8fbff;")
        self.tag_layout = QFlowLayout(tag_widget, margin=4, spacing=6)
        tag_area.setWidget(tag_widget)
        tag_area.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        tag_area.setMaximumWidth(250)
        tag_card_layout.addWidget(tag_area)
        right_layout.addWidget(self.tag_card)
        right_layout.setStretchFactor(fileinfo_area, 1)
        right_layout.setStretchFactor(tag_area, 2)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 4)
        button_layout.setSpacing(6)
        self.prev_button = create_button(self.tr(CommonText.PREVIOUS))
        self.prev_button.setMaximumWidth(120)
        self.prev_button.clicked.connect(self.show_previous)
        self.next_button = create_button(self.tr(CommonText.NEXT))
        self.next_button.setMaximumWidth(120)
        self.next_button.clicked.connect(self.show_next)
        button_layout.addWidget(self.prev_button)
        button_layout.addWidget(self.next_button)
        right_layout.addLayout(button_layout)

        container = QWidget()
        container.setStyleSheet("background-color: #f4f7fb;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.preview_card = QWidget()
        apply_panel_style(self.preview_card, tone="default")
        preview_layout = QVBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        self.image_viewer = ImageViewer(self)
        preview_layout.addWidget(self.image_viewer)
        layout.addWidget(self.preview_card, 3)
        layout.addLayout(right_layout, 1)

        self.setWidget(container)
        self.setWidgetResizable(True)
        self.show_current_file()

    def closeEvent(self, event):
        self._refresh_timer.stop()
        super().closeEvent(event)

    def observer_update(self):
        self._request_refresh()

    def showEvent(self, event):
        super().showEvent(event)
        if self._tags_dirty or self._preview_dirty:
            self._refresh_timer.start(0)

    def _request_refresh(self, preview=False):
        self._tags_dirty = True
        self._preview_dirty |= preview
        if self.isVisible() and not self._refresh_timer.isActive():
            self._refresh_timer.start(0)

    def _flush_refresh(self):
        if not self.isVisible():
            return
        if self._preview_dirty:
            self.update_index(self.current_file_path)
        elif self._tags_dirty:
            self.update_tags()

    def _on_data_changed(self, action, payload):
        if action != "special_status_changed":
            self._request_refresh()

    def _on_relation_changed(self, action, payload):
        if self.current_file_path in payload["file_paths"]:
            self._request_refresh()

    def _on_tagbase_changed(self, db_path):
        self._refresh_timer.stop()
        self._request_refresh()

    def _on_file_changed(self, action, payload):
        if self.current_file_path is None or action == "audio_markers_changed":
            return
        changed_paths = set(payload.get("file_paths", [])) if isinstance(payload, dict) else set()
        path_mapping = payload.get("path_mapping", {}) if isinstance(payload, dict) else {}
        old_path = payload.get("old_path") if isinstance(payload, dict) else None
        new_path = payload.get("new_path") if isinstance(payload, dict) else None

        if old_path and self.current_file_path == old_path:
            self.current_file_path = new_path
            self._request_refresh(preview=True)
            return
        if self.current_file_path in path_mapping:
            mapped_path = path_mapping[self.current_file_path]
            self.current_file_path = mapped_path
            self._request_refresh(preview=True)
            return
        if not changed_paths or self.current_file_path in changed_paths:
            self._request_refresh(preview=True)

    def show_current_file(self):
        if not self.isVisible():
            self._request_refresh(preview=True)
            return
        self._preview_dirty = False
        # 单文件视图不再直接摸 FileShowArea 的内部 FileItem，
        # 统一通过只读视图对象拿当前文件的展示元数据。
        view = self.TagFileShowArea.get_file_view(self.current_file_path)
        if view is None:
            self.pixmap = QPixmap()
            self.file_name_value.clear()
            self.path_value.clear()
            self.size_value.clear()
            self.modified_time_value.clear()
        else:
            self.pixmap = load_pixmap(view.file_path)
            if self.pixmap.isNull() and view.icon_source is not None:
                self.pixmap = view.icon_source.source
            self.file_name_value.setText(view.file_name)
            self.path_value.setText(view.file_path)
            self.size_value.setText(view.formatted_size)
            self.modified_time_value.setText(
                datetime.fromtimestamp(view.file_date).strftime("%Y年%m月%d日，%H:%M:%S")
            )
        self.image_viewer.load_image(self.pixmap)
        self.update_tags()
        if view is not None:
            self.TagFileShowArea.request_file_thumbnail(view.file_path)

    def _on_thumbnail_ready(self, file_path):
        if file_path != self.current_file_path:
            return
        if not self.isVisible():
            self._preview_dirty = True
            return
        view = self.TagFileShowArea.get_file_view(file_path)
        if view is None or view.icon_source is None:
            return
        # 图片仍优先显示原图；视频等格式在后台封面就绪后替换默认图标。
        pixmap = load_pixmap(file_path)
        if pixmap.isNull():
            pixmap = view.icon_source.source
        self.pixmap = pixmap
        self.image_viewer.load_image(pixmap)

    def _create_info_value_label(self, parent):
        label = QLabel(parent)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border: none;
                color: #314456;
                font-size: 12px;
                padding: 0px;
            }
        """)
        return label

    def _create_info_row(self, title, value_label, parent):
        row = QFrame(parent)
        row.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                border-top: 1px solid #e3ebf3;
                padding-top: 4px;
            }
        """)
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(2)

        title_label = QLabel(title, row)
        title_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border: none;
                color: #465a6e;
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
                font-size: 13px;
                font-weight: 400;
                padding: 0px;
            }
        """)
        row_layout.addWidget(title_label)
        row_layout.addWidget(value_label)
        return row

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def update_tags(self):
        self._tags_dirty = False
        while self.tag_layout.count():
            item = self.tag_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

        if self.current_file_path is None:
            return

        for tag, color in self.DictManage.get_file_tag_details(self.current_file_path):
            label = create_colored_label(tag, color, self)
            label.setCursor(Qt.PointingHandCursor)
            label.mousePressEvent = (
                lambda event, tag=tag: self.delete_tag_current_file(tag)
                if event.button() == Qt.LeftButton else None
            )
            self.tag_layout.addWidget(label)

    def show_previous(self):
        # 上一张 / 下一张始终按 FileShowArea 当前公开的文件顺序导航。
        self.file_paths = self.TagFileShowArea.get_files()
        if self.file_paths:
            self.current_index = (self.current_index - 1) % len(self.file_paths)
            self.current_file_path = self.file_paths[self.current_index]
            self.TagFileShowArea.set_current_file(self.current_file_path, keep_selection=False)
            self.show_current_file()

    def show_next(self):
        self.file_paths = self.TagFileShowArea.get_files()
        if self.file_paths:
            self.current_index = (self.current_index + 1) % len(self.file_paths)
            self.current_file_path = self.file_paths[self.current_index]
            self.TagFileShowArea.set_current_file(self.current_file_path, keep_selection=False)
            self.show_current_file()

    def add_tag_current_file(self, tag):
        if self.current_file_path is not None:
            self.DictManage.add_tag(tag, [self.current_file_path])

    def delete_tag_current_file(self, tag):
        if self.current_file_path is not None:
            self.DictManage.delete_tag(tag, [self.current_file_path])

    def update_index(self, file_path=None):
        # 当前索引始终以 FileShowArea 暴露的文件顺序为准，
        # 避免排序变化后单文件视图还停留在旧顺序上。
        self.file_paths = self.TagFileShowArea.get_files()
        if file_path is not None:
            self.current_file_path = file_path
        if self.current_file_path in self.file_paths:
            self.current_index = self.file_paths.index(self.current_file_path)
        else:
            self.current_index = 0
        if self.file_paths:
            self.current_file_path = self.file_paths[self.current_index]
        else:
            self.current_file_path = None
        self.show_current_file()


class QFlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super(QFlowLayout, self).__init__(parent)
        self.itemList = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super(QFlowLayout, self).setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        size += QSize(2 * self.contentsMargins().top(), 2 * self.contentsMargins().top())
        return size

    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0

        for item in self.itemList:
            wid = item.widget()
            spaceX = self.spacing() + wid.style().layoutSpacing(
                QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Horizontal
            )
            spaceY = self.spacing() + wid.style().layoutSpacing(
                QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Vertical
            )
            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0

            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())

        return y + lineHeight - rect.y()
