from datetime import datetime

from PyQt5.QtCore import QPoint, QRect, QSize, Qt
from PyQt5.QtGui import QColor, QFont, QPixmap
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.DictManage import DictManage, Observer
from src.ui.media_viewers import ImageViewer

from .FileShowArea import TagFileShowArea


# ---------------- Single File Detail View ----------------

class SingleFileTagView(QScrollArea, Observer):
    def __init__(self, file_paths: str, TagFileShowArea: TagFileShowArea):
        super().__init__()
        self.DictManage = DictManage()
        self.DictManage.add_observer(self)
        self.TagFileShowArea = TagFileShowArea
        self.file_paths = file_paths
        self.current_index = 0
        self.current_file_path = self.file_paths[0] if self.file_paths else None
        self.initUI()

    def initUI(self):
        # 左侧专注预览当前文件，右侧显示当前文件的元数据和标签，
        # 让单文件模式更适合顺序标注和快速浏览。
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setMinimumSize(200, 200)

        right_layout = QVBoxLayout()

        fileinfo_area = QScrollArea()
        fileinfo_area.setWidgetResizable(True)
        fileinfo_widget = QWidget()
        self.text_edit = QTextEdit(fileinfo_widget)
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Arial", 12))
        layout = QVBoxLayout(fileinfo_widget)
        layout.addWidget(self.text_edit)
        fileinfo_area.setWidget(fileinfo_widget)
        fileinfo_area.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        fileinfo_area.setMaximumWidth(250)
        right_layout.addWidget(fileinfo_area)

        tag_area = QScrollArea()
        tag_area.setWidgetResizable(True)
        tag_widget = QWidget()
        self.tag_layout = QFlowLayout(tag_widget)
        tag_area.setWidget(tag_widget)
        tag_area.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        tag_area.setMaximumWidth(250)
        right_layout.addWidget(tag_area)
        right_layout.setStretchFactor(fileinfo_area, 1)
        right_layout.setStretchFactor(tag_area, 2)

        button_layout = QHBoxLayout()
        self.prev_button = QPushButton("上一张")
        self.prev_button.setFixedHeight(30)
        self.prev_button.setMaximumWidth(120)
        self.prev_button.clicked.connect(self.show_previous)
        self.next_button = QPushButton("下一张")
        self.next_button.setFixedHeight(30)
        self.next_button.setMaximumWidth(120)
        self.next_button.clicked.connect(self.show_next)
        button_layout.addWidget(self.prev_button)
        button_layout.addWidget(self.next_button)
        right_layout.addLayout(button_layout)

        container = QWidget()
        layout = QHBoxLayout(container)
        self.image_viewer = ImageViewer(self)
        layout.addWidget(self.image_viewer, 3)
        layout.addLayout(right_layout, 1)

        self.setWidget(container)
        self.setWidgetResizable(True)
        self.show_current_file()

    def closeEvent(self, event):
        self.DictManage.remove_observer(self)
        super().closeEvent(event)

    def observer_update(self):
        self.update_tags()

    def show_current_file(self):
        # 单文件视图不再直接摸 FileShowArea 的内部 FileItem，
        # 统一通过只读视图对象拿当前文件的展示元数据。
        view = self.TagFileShowArea.get_file_view(self.current_file_path)
        if view is None:
            self.pixmap = QPixmap()
            self.text_edit.clear()
        else:
            self.pixmap = QPixmap(view.file_path)
            if self.pixmap.isNull() and view.icon_source is not None:
                self.pixmap = view.icon_source.source
            message = (
                f"<b>{view.file_name}</b><br><br>"
                f"<b>文件路径: </b>&nbsp; {view.file_path}<br><br>"
                f"<b>文件大小: </b>&nbsp; {view.formatted_size}<br><br>"
                f"<b>修改时间: </b>&nbsp; {datetime.fromtimestamp(view.file_date).strftime('%Y年%m月%d日，%H:%M:%S')}<br><br>"
            )
            self.text_edit.setHtml(message)
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
            color = QColor(item[1])
            tags = self.DictManage.query("category", category, "tag")
            bg_color = color.name()
            darker_color = QColor(color)
            darker_color.setHsv(color.hue(), color.saturation(), int(color.value() * 0.7))
            border_color = darker_color.name()
            for tag in tags:
                if tag in file_tags:
                    label = QLabel(tag, self)
                    label.setStyleSheet(
                        f"""
                        QLabel {{
                            background-color: {bg_color};
                            color: #333333;
                            border: 1px solid {border_color};
                            border-radius: 10px;
                            padding: 5px 10px;
                            margin: 3px;
                            font: 14px;
                        }}
                        QLabel:hover {{
                            background-color: {color.lighter(110).name()};
                            border-color: #c0c0c0;
                        }}
                    """
                    )
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
