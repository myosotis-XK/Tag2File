from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QScrollArea, QSizePolicy, QTextEdit, QLayout
from PyQt5.QtGui import QPixmap, QColor, QFont
from PyQt5.QtCore import Qt, QPoint, QRect, QSize
from .DictManage import *
from .ImageViewer import *

class SingleFileTagView(QScrollArea, Observer):
    def __init__(self, file_paths, TagFileShowArea):
        super().__init__()
        self.DictManage = DictManage()
        self.DictManage.add_observer(self)
        self.TagFileShowArea = TagFileShowArea
        self.relation_graph = self.DictManage.relation_graph
        self.special_tags_status = self.DictManage.special_tags_status
        self.file_paths = file_paths
        self.current_index = 0
        if len(file_paths) > 0:
            self.current_file_path = self.file_paths[0]
        else:
            self.current_file_path = None
        self.initUI()

    def initUI(self):
        # 左侧：文件缩略图
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setMinimumSize(200, 200)  # 设置最小大小

        # 右侧：标签显示和控制按钮
        right_layout = QVBoxLayout()

        fileinfo_area = QScrollArea()
        fileinfo_area.setWidgetResizable(True)
        fileinfo_widget = QWidget()
        # 创建一个文本编辑器，显示文件属性
        self.text_edit = QTextEdit(fileinfo_widget)
        self.text_edit.setReadOnly(True)  # 设置为只读

        # 设置字体
        font = QFont("Arial", 12)  # 使用 Arial 字体，大小为 12
        self.text_edit.setFont(font)
        layout = QVBoxLayout(fileinfo_widget)
        layout.addWidget(self.text_edit)
        fileinfo_area.setWidget(fileinfo_widget)
        fileinfo_area.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        fileinfo_area.setMaximumWidth(250)
        right_layout.addWidget(fileinfo_area)


        # 标签显示区域
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

        # 控制按钮
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

        # 创建一个容器widget来放置所有内容
        container = QWidget()
        layout = QHBoxLayout(container)
        self.image_viewer = ImageViewer(self)
        layout.addWidget(self.image_viewer, 3)
        layout.addLayout(right_layout, 1)

        # 设置主滚动区域的widget
        self.setWidget(container)
        self.setWidgetResizable(True)
        self.show_current_file()

    def observer_update(self):
        self.update_tags()

    def show_current_file(self):   
        # 显示图片
        if self.current_file_path is None:
            self.pixmap = QPixmap()
        else:
            label = self.TagFileShowArea.labels[self.current_file_path]
            self.pixmap = QPixmap(self.current_file_path)
            if self.pixmap.isNull():
                icon_label = label.findChild(QLabel, "icon_label")
                self.pixmap = icon_label.pixmap()
            message = (
                f"<b>{label.file_name}</b><br><br>"
                f"<b>文件路径: </b>&nbsp; {label.file_path}<br><br>"
                f"<b>文件大小: </b>&nbsp; {label.file_size}<br><br>"
                f"<b>修改时间: </b>&nbsp; {label.file_date}<br><br>"
            )
            self.text_edit.setHtml(message)
        self.image_viewer.load_image(self.pixmap)
        # self.change_image_size()
        # 显示标签
        self.update_tags()
    
    def change_image_size(self):
        if not self.pixmap.isNull():
            label_size = self.image_label.size()
            # 计算缩放后的图片大小，保持宽高比
            scaled_pixmap = self.pixmap.scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            # 设置图片
            self.image_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 当窗口大小改变时，重新调整图片大小
        # if hasattr(self, 'image_label') and self.image_label.pixmap():
        #     self.change_image_size()

    def update_tags(self):
        # 清除现有标签
        for i in reversed(range(self.tag_layout.count())): 
            self.tag_layout.itemAt(i).widget().setParent(None)

        # 添加新标签
        file_tags = self.relation_graph['file'].get(self.current_file_path, {}).get('tag', set())
        for value in self.relation_graph['category'].values():
            tags = value['tagOrder']
            color = QColor(value['tagColor'])
            bg_color = color.name()
            darker_color = QColor(color)
            darker_color.setHsv(color.hue(), color.saturation(), int(color.value() * 0.7))
            border_color = darker_color.name()
            for tag in tags:
                if tag in file_tags:
                    label = QLabel(tag, self)
                    label.setStyleSheet(f"""
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
                    """)
                    label.setCursor(Qt.PointingHandCursor)  # 设置鼠标指针样式
                    label.mousePressEvent = lambda event, tag=tag: self.delete_tag_current_file(tag) if event.button() == Qt.LeftButton else None  # 绑定点击事件
                    self.tag_layout.addWidget(label)

    def show_previous(self):
        if len(self.file_paths) > 0:
            self.current_index = (self.current_index - 1) % len(self.file_paths)
            self.current_file_path = self.file_paths[self.current_index]
            self.show_current_file()

    def show_next(self):
        if len(self.file_paths) > 0:
            self.current_index = (self.current_index + 1) % len(self.file_paths)
            self.current_file_path = self.file_paths[self.current_index]
            self.show_current_file()

    def add_tag_current_file(self, tag):
        file_path = self.current_file_path
        if tag not in self.relation_graph['file'].get(file_path, {}).get('tag', set()):
            self.DictManage.add_tag(tag, [file_path])
        
    def delete_tag_current_file(self, tag):
        file_path = self.current_file_path
        self.DictManage.delete_tag(tag, [file_path])

    def update_index(self, file_paths=None):
        if file_paths is not None:
            self.current_file_path = file_paths
        if self.current_file_path in self.file_paths:
            self.current_index = self.file_paths.index(self.current_file_path)
        else:
            self.current_index = 0
        if len(self.file_paths) > 0:
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
            spaceX = self.spacing() + wid.style().layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Horizontal)
            spaceY = self.spacing() + wid.style().layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Vertical)
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