from .FileShowArea import *
from .SingleFileTagView import *
from .DictManage import *
from PyQt5.QtWidgets import QSplitter, QHBoxLayout, QLineEdit, QMessageBox, QInputDialog, QMainWindow
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor

default_value = {
    'quickly_model': False
}
init_config_section('TagView', default_value)
save_config()

class TagView(QMainWindow, Observer):
    def __init__(self, MainWindow, file_paths):
        super().__init__()

        self.DictManage = DictManage()
        self.DictManage.add_observer(self)
        self.special_tags_status = self.DictManage.special_tags_status
        self.file_paths = file_paths

        self.MainWindow = MainWindow
        self.resize(1200, 700)  # 设置窗口初始大小
        self.setWindowTitle("标签管理")

        self.model = 'batch'
        self.quickly_model = config.getboolean('TagView', 'quickly_model', fallback=False)

        # 创建中央窗口部件
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        # 创建和设置其他UI组件
        self.setup_ui()
        self.show()
        if len(self.file_paths) == 1:
            self.toggle_view()

    def setup_ui(self):
        self.TagFileShowArea = TagFileShowArea(self.file_paths)
        self.SingleFileTagView = SingleFileTagView(self.file_paths, self.TagFileShowArea)
        self.SingleFileTagView.hide()
        
        # 创建按钮和输入框
        self.floder_button = QPushButton("不接受文件夹", self)
        if self.TagFileShowArea.acceptFloder:
            self.floder_button.setText("接受文件夹")
        self.floder_button.clicked.connect(self.change_floder_model)
        self.floder_button.setFixedHeight(30)
        self.floder_button.setStyleSheet("font-size: 14px;")

        self.model_button = QPushButton("普通模式", self)
        if self.quickly_model:
            self.model_button.setText("快速模式")
        self.model_button.clicked.connect(self.change_quickly_model)
        self.model_button.setFixedHeight(30)
        self.model_button.setStyleSheet("font-size: 14px;")

        self.tag_input = QLineEdit(self)
        self.tag_input.setPlaceholderText("输入标签...")
        self.tag_input.setFixedHeight(30)
        self.tag_input.setStyleSheet("font-size: 14px;")

        add_button = QPushButton("添加", self)
        add_button.clicked.connect(self.addTag)
        add_button.setFixedHeight(30)
        add_button.setStyleSheet("font-size: 14px;")
        delete_button = QPushButton("删除", self)
        delete_button.clicked.connect(self.deleteTag)
        delete_button.setFixedHeight(30)
        delete_button.setStyleSheet("font-size: 14px;")
        clear_button = QPushButton("清空", self)
        clear_button.clicked.connect(self.clearFile)
        clear_button.setFixedHeight(30)
        clear_button.setStyleSheet("font-size: 14px;")
        self.switch_view_button = QPushButton("切换视图")
        self.switch_view_button.clicked.connect(self.toggle_view)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.floder_button)
        button_layout.addWidget(self.model_button)
        button_layout.addWidget(self.tag_input)
        button_layout.addWidget(add_button)
        button_layout.addWidget(delete_button)
        button_layout.addWidget(clear_button)
        button_layout.addWidget(self.switch_view_button)
        button_layout.addStretch()

        self.tag_scroll_area = QScrollArea(self)
        self.tag_scroll_area.setWidgetResizable(True)
        self.tag_scroll_area.setWidget(self.create_tag_widget())
        # 创建tag区域
        tag_menu_widget = QWidget()
        tag_menu_layout = QVBoxLayout(tag_menu_widget)
        tag_menu_layout.addLayout(button_layout)
        tag_menu_layout.addWidget(self.tag_scroll_area)
        
        # 创建 QSplitter
        self.splitter = QSplitter(Qt.Vertical)  # 使用垂直方向的分隔条
        # 将控件添加到 splitter 中
        self.splitter.addWidget(self.TagFileShowArea)
        self.splitter.addWidget(tag_menu_widget)
        
        # 设置主布局
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.addWidget(self.splitter)  # 将 QSplitter 添加到布局中
        # 设置伸缩因子
        self.splitter.setSizes([350, 200])

    def observer_update(self):
        self.tag_scroll_area.setWidget(self.create_tag_widget())

    def closeEvent(self, event):
        self.TagFileShowArea.closeEvent(event)
        self.MainWindow.tag_view = None
        super().closeEvent(event)

    def create_tag_widget(self):
        # 创建标签区域
        tag_layout = QFlowLayout()
        for value in self.DictManage.relation_graph['category'].values():
            tags = value['tagOrder']
            color = QColor(value['tagColor'])
            bg_color = color.name()
            darker_color = QColor(color)
            darker_color.setHsv(color.hue(), color.saturation(), int(color.value() * 0.7))
            border_color = darker_color.name()
            for tag in tags:
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
                label.mousePressEvent = lambda event, tag=tag: self.onTagClick(tag) if event.button() == Qt.LeftButton else None  # 绑定点击事件
                label.setContextMenuPolicy(Qt.CustomContextMenu)  # 允许自定义右键菜单
                label.customContextMenuRequested.connect(lambda pos, label=label: self.show_tag_context_menu(pos, label))  # 绑定右键菜单事件
                tag_layout.addWidget(label)

        tag_widget = QWidget()
        tag_widget.setLayout(tag_layout)
        return tag_widget

    def addFile(self, file_paths):
        new_file_paths = list(set(file_paths) - set(self.file_paths))
        if len(new_file_paths) > 0:
            self.file_paths.extend(new_file_paths)
            self.TagFileShowArea.createFileLabels(new_file_paths)
            self.TagFileShowArea.updateLayout()
            self.TagFileShowArea.startLoadingImages(self.TagFileShowArea.threadpool, new_file_paths)


    # ——————————————————————Tag相关操作————————————————————————————

    # 左键点击
    def onTagClick(self, tag):
        if self.model == 'batch':
            self.tag_input.setText(tag) # 输入文本框
        else:
            file_path = self.SingleFileTagView.current_file_path
            if self.quickly_model:
                self.SingleFileTagView.show_next()
                QApplication.processEvents()
            if tag not in self.DictManage.relation_graph['file'].get(file_path, {}).get('tag', set()):
                self.DictManage.add_tag(tag, [file_path])

    # 右键菜单
    def show_tag_context_menu(self, pos, label):
        context_menu = QMenu(self)
        
        delete_action = QAction("删除", self)
        delete_action.triggered.connect(lambda: self.delete_tag_action(label))
        
        rename_action = QAction("重命名", self)
        rename_action.triggered.connect(lambda: self.rename_tag_action(label))
        
        change_category_action = QAction("修改类别", self)
        change_category_action.triggered.connect(lambda: self.change_tag_category_action(label))
        
        context_menu.addAction(delete_action)
        context_menu.addAction(rename_action)
        context_menu.addAction(change_category_action)

        label_global_pos = label.mapToGlobal(QPoint(0, 0)) # 获取标签的全局位置
        global_pos = label_global_pos + pos # 计算菜单弹出位置
        context_menu.exec_(global_pos)

    def delete_tag_action(self, label):
        tag = label.text()
        self.DictManage.destroy_tag(tag)

    def cherk_tag(self, tag):
        operators = [' ∩ ', ' ∪ ', "'", '(', ')', '-']
        for op in operators:
            if op in tag:
                # 提示错误的消息框
                message_box = QMessageBox(self)
                message_box.setIcon(QMessageBox.Information)
                message_box.setWindowTitle("错误！")
                message_box.setText(f"存在非法字符：{op}")
                message_box.exec_()
                return False
        return True

    def rename_tag_action(self, label):
        tag = label.text()
        # 弹出输入框，让用户输入新名字, 输入框默认值为标签名
        new_name, ok = QInputDialog.getText(self, "重命名", "输入新标签名称:", text=tag)
        if ok and new_name:
            if not self.cherk_tag(new_name):
                return
            if new_name in self.DictManage.relation_graph['tag']:
                reply = QMessageBox.question(self, "继续", f"'{new_name}' 标签已存在，继续将合并标签，是否继续？",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.DictManage.rename_tag(tag, new_name)
            else:
                self.DictManage.rename_tag(tag, new_name)

    def change_tag_category_action(self, label):
        tag = label.text()
        # 弹出一个对话框，让用户选择新的类别
        existing_category = self.DictManage.relation_graph['category'].keys()
        category, ok = QInputDialog.getItem(self, "修改类别", "选择或输入类别名称:", existing_category, 0, True)
        if ok and category:
            if category not in self.DictManage.relation_graph['category']:
                # 提示类别不存在的消息框
                message_box = QMessageBox(self)
                message_box.setIcon(QMessageBox.Information)
                message_box.setWindowTitle("错误！")
                message_box.setText(f"'{category}' 类别不存在")
                message_box.exec_()
                return False
            self.DictManage.change_tag_category(tag, category)

    def addTag(self):
        tag = self.tag_input.text()
        # 判断违规字符
        if not tag or not self.cherk_tag(tag):
            return
        if self.model == 'batch':
            self.DictManage.add_tag(tag, self.TagFileShowArea.file_paths)

            # 显示“添加成功”的消息框
            message_box = QMessageBox(self)
            message_box.setIcon(QMessageBox.Information)
            message_box.setWindowTitle("提示")
            message_box.setText("添加成功！")
            message_box.setStandardButtons(QMessageBox.Ok)
            # 让消息框在0.5秒后自动关闭
            QTimer.singleShot(500, message_box.close)
            # 显示消息框
            message_box.exec_()
        else:
            self.SingleFileTagView.add_tag_current_file(tag)

        # 清空输入框
        self.tag_input.clear()

    def deleteTag(self):
        tag = self.tag_input.text()
        if self.model == 'batch':
            self.DictManage.delete_tag(tag, self.TagFileShowArea.file_paths)
        
            message_box = QMessageBox(self)
            message_box.setIcon(QMessageBox.Information)
            message_box.setWindowTitle("提示")
            message_box.setText("删除成功！")
            message_box.setStandardButtons(QMessageBox.Ok)
            # 让消息框在0.5秒后自动关闭
            QTimer.singleShot(500, message_box.close)
            # 显示消息框
            message_box.exec_()
        else:
            self.SingleFileTagView.delete_tag_current_file(tag)

    def clearFile(self):
        self.TagFileShowArea.changeFile([])
        self.file_paths.clear()
        self.TagFileShowArea.file_paths = self.file_paths

    def toggle_view(self):
        current_sizes = self.splitter.sizes()

        if self.TagFileShowArea.isVisible():
            self.model = 'single'
            # 清空选中标签
            for file_path in self.TagFileShowArea.select_labels_keys:
                label = self.TagFileShowArea.labels[file_path]
                updateStyle(label, "background-color: transparent;")
            file_path = None
            if not self.TagFileShowArea.now_select_label_key is None:
                label = self.TagFileShowArea.labels[self.TagFileShowArea.now_select_label_key]
                file_path = self.TagFileShowArea.now_select_label_key
                self.TagFileShowArea.now_select_label_key = None
                updateStyle(label, "border: none;")
            self.TagFileShowArea.hide()
            self.splitter.replaceWidget(0, self.SingleFileTagView)
            self.SingleFileTagView.show()
            self.SingleFileTagView.update_index(file_path)
            self.switch_view_button.setText("单文件视图")
        else:
            self.model = 'batch'
            self.SingleFileTagView.hide()
            self.splitter.replaceWidget(0, self.TagFileShowArea)
            self.TagFileShowArea.show()
            if not self.SingleFileTagView.current_file_path is None and self.SingleFileTagView.current_file_path in self.TagFileShowArea.labels:
                label = self.TagFileShowArea.labels[self.SingleFileTagView.current_file_path]
                file_path = label.file_path
                file_item = self.TagFileShowArea.file_items[file_path]
                self.TagFileShowArea.now_select_label_key = file_path
                updateStyle(label, "border: 1px solid #99d1ff;")
                # 滚动条滚动到当前标签
                label_global_rect = file_item.label_pos
                self.TagFileShowArea.verticalScrollBar().setValue(label_global_rect.y())
            self.switch_view_button.setText("多文件视图")

        self.splitter.setSizes(current_sizes)

    def change_quickly_model(self):
        self.quickly_model = not self.quickly_model
        config.set('TagView', 'quickly_model', str(self.quickly_model))
        save_config()
        if self.quickly_model:
            self.model_button.setText("快速模式")
        else:
            self.model_button.setText("普通模式")

    def change_floder_model(self):
        self.TagFileShowArea.acceptFloder = not self.TagFileShowArea.acceptFloder
        config.set('TagFileShowArea', 'acceptFloder', str(self.TagFileShowArea.acceptFloder))
        save_config()
        if self.TagFileShowArea.acceptFloder:
            self.floder_button.setText("接受文件夹")
        else:
            self.floder_button.setText("不接受文件夹")

    def keyPressEvent(self, event):
        if self.model == 'single':
            if event.key() == Qt.Key_A:
                self.SingleFileTagView.show_previous()
            elif event.key() == Qt.Key_D:
                self.SingleFileTagView.show_next()
            else:
                super().keyPressEvent(event)  
        else:
            super().keyPressEvent(event)