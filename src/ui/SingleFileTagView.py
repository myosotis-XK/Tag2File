from datetime import datetime

from PyQt5.QtCore import QPoint, QRect, QSize, Qt
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import (
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

from .FileShowArea import TagFileShowArea


# ---------------- Single File Detail View ----------------

class SingleFileTagView(QScrollArea):
    def __init__(self, file_paths: str, TagFileShowArea: TagFileShowArea):
        super().__init__()
        self.DictManage = DictManage()
        self.DictManage.tagChanged.connect(self._on_data_changed)
        self.DictManage.categoryChanged.connect(self._on_data_changed)
        self.DictManage.fileChanged.connect(self._on_file_changed)
        self.TagFileShowArea = TagFileShowArea
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

        fileinfo_area = QScrollArea()
        fileinfo_area.setWidgetResizable(True)
        apply_scroll_area_style(fileinfo_area, tone="soft")
        fileinfo_widget = QWidget()
        fileinfo_widget.setStyleSheet("background-color: #f8fbff;")
        self.info_label = QLabel(fileinfo_widget)
        self.info_label.setFont(QFont("Arial", 12))
        self.info_label.setWordWrap(True)
        self.info_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.info_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.info_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border: none;
                color: #314456;
                padding: 2px;
            }
        """)
        layout = QVBoxLayout(fileinfo_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.info_label)
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
        super().closeEvent(event)

    def observer_update(self):
        self.update_tags()

    def _on_data_changed(self, action, payload):
        self.observer_update()

    def _on_file_changed(self, action, payload):
        if self.current_file_path is None:
            return
        changed_paths = set(payload.get("file_paths", [])) if isinstance(payload, dict) else set()
        path_mapping = payload.get("path_mapping", {}) if isinstance(payload, dict) else {}
        old_path = payload.get("old_path") if isinstance(payload, dict) else None
        new_path = payload.get("new_path") if isinstance(payload, dict) else None

        if old_path and self.current_file_path == old_path:
            self.current_file_path = new_path
            self.update_index(new_path)
            return
        if self.current_file_path in path_mapping:
            mapped_path = path_mapping[self.current_file_path]
            self.current_file_path = mapped_path
            self.update_index(mapped_path)
            return
        if not changed_paths or self.current_file_path in changed_paths:
            self.update_index(self.current_file_path)

    def show_current_file(self):
        # 单文件视图不再直接摸 FileShowArea 的内部 FileItem，
        # 统一通过只读视图对象拿当前文件的展示元数据。
        view = self.TagFileShowArea.get_file_view(self.current_file_path)
        if view is None:
            self.pixmap = QPixmap()
            self.info_label.clear()
        else:
            self.pixmap = QPixmap(view.file_path)
            if self.pixmap.isNull() and view.icon_source is not None:
                self.pixmap = view.icon_source.source
            message = self.tr(SingleFileTagViewText.FILE_INFO_HTML).format(
                file_name=view.file_name,
                file_path=view.file_path,
                file_size=view.formatted_size,
                modified_time=datetime.fromtimestamp(view.file_date).strftime("%Y年%m月%d日，%H:%M:%S"),
            )
            self.info_label.setTextFormat(Qt.RichText)
            self.info_label.setText(message)
        self.image_viewer.load_image(self.pixmap)
        self.update_tags()

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def update_tags(self):
        # 标签区每次全量重建，逻辑简单且和 DictManage 的最新状态保持一致。
        for i in reversed(range(self.tag_layout.count())):
            self.tag_layout.itemAt(i).widget().setParent(None)

        if self.current_file_path is None:
            return

        file_tags = self.DictManage.query("file", self.current_file_path, "tag")
        for item in self.DictManage.query_category():
            category = item[0]
            color = item[1]
            tags = self.DictManage.query("category", category, "tag")
            for tag in tags:
                if tag in file_tags:
                    label = create_colored_label(tag, color, self)
                    label.setCursor(Qt.PointingHandCursor)
                    label.mousePressEvent = (
                        lambda event, tag=tag: self.delete_tag_current_file(tag)
                        if event.button() == Qt.LeftButton
                        else None
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
