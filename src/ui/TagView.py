from PyQt5.QtCore import QPoint, Qt, QPropertyAnimation, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QInputDialog,
)

from src.core.DictManage import DictManage
from src.utils import config, init_config_section, save_config
from src.ui.components.style_utils import create_colored_label

from .FileShowArea import TagFileShowArea
from .SingleFileTagView import QFlowLayout, SingleFileTagView


default_value = {
    "quickly_model": False,
}
init_config_section("TagView", default_value)
save_config()


# ---------------- Tag Management Window ----------------

class TagView(QMainWindow):
    def __init__(self, MainWindow, file_paths):
        super().__init__()

        self.DictManage = DictManage()
        self.DictManage.tagChanged.connect(self._on_tag_or_category_changed)
        self.DictManage.categoryChanged.connect(self._on_tag_or_category_changed)
        self.file_paths = file_paths

        self.MainWindow = MainWindow
        self.resize(1200, 700)
        self.setWindowTitle("标签管理")

        self.model = "batch"
        self.quickly_model = config.getboolean("TagView", "quickly_model", fallback=False)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.setup_ui()
        self.show()
        if len(self.file_paths) == 1:
            self.toggle_view()

    def setup_ui(self):
        # 上半部分是文件区，下半部分是标签区；两者通过 splitter 保持联动但职责分离。
        self.TagFileShowArea = TagFileShowArea(self.file_paths)
        self.TagFileShowArea.filesChanged.connect(self._sync_files_from_area)
        self.SingleFileTagView = SingleFileTagView(self.file_paths, self.TagFileShowArea)
        self.SingleFileTagView.hide()

        self.floder_button = QPushButton("不接受文件夹", self)
        if self.TagFileShowArea.accepts_folder():
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

        tag_menu_widget = QWidget()
        tag_menu_layout = QVBoxLayout(tag_menu_widget)
        tag_menu_layout.addLayout(button_layout)
        tag_menu_layout.addWidget(self.tag_scroll_area)

        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.addWidget(self.TagFileShowArea)
        self.splitter.addWidget(tag_menu_widget)

        main_layout = QVBoxLayout(self.central_widget)
        main_layout.addWidget(self.splitter)
        self.splitter.setSizes([350, 200])

    def observer_update(self):
        # 这里重建的是右侧标签面板，不动文件区；
        # 先记住滚动位置，避免标签更新后把用户视野弹回顶部。
        scroll_value = self.tag_scroll_area.verticalScrollBar().value()
        tag_widget = self.create_tag_widget()
        self.tag_scroll_area.setWidget(tag_widget)
        self.tag_scroll_area.verticalScrollBar().setValue(scroll_value)

    def closeEvent(self, event):
        self.TagFileShowArea.closeEvent(event)
        self.MainWindow.tag_view = None
        self.SingleFileTagView.closeEvent(event)
        super().closeEvent(event)

    def _on_tag_or_category_changed(self, action, payload):
        self.observer_update()

    def create_tag_widget(self):
        # 标签列表直接从 DictManage 重建，避免在 UI 层缓存一份容易过期的树结构。
        tag_layout = QFlowLayout()
        for item in self.DictManage.query_category():
            category = item[0]
            if category == "文件类型":
                continue
            color = item[1]
            tags = self.DictManage.query("category", category, "tag")
            for tag in tags:
                label = create_colored_label(tag, color, self)
                label.mousePressEvent = (
                    lambda event, tag=tag: self.onTagClick(tag) if event.button() == Qt.LeftButton else None
                )
                label.setContextMenuPolicy(Qt.CustomContextMenu)
                label.customContextMenuRequested.connect(
                    lambda pos, label=label: self.show_tag_context_menu(pos, label)
                )
                tag_layout.addWidget(label)
        tag_widget = QWidget()
        tag_widget.setLayout(tag_layout)
        return tag_widget

    def addFile(self, file_paths):
        new_file_paths = list(set(file_paths) - set(self.file_paths))
        if new_file_paths:
            self.TagFileShowArea.append_files([(file_path, 0, 0) for file_path in new_file_paths])

    def onTagClick(self, tag):
        if self.model == "batch":
            self.tag_input.setText(tag)
        else:
            # 单文件模式下，点击标签表示“给当前文件打标签”而不是构造批量查询条件。
            file_path = self.SingleFileTagView.current_file_path
            if file_path is None:
                return
            if self.quickly_model:
                self.SingleFileTagView.show_next()
                QApplication.processEvents()
            self.DictManage.add_tag(tag, [file_path])

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

        label_global_pos = label.mapToGlobal(QPoint(0, 0))
        global_pos = label_global_pos + pos
        context_menu.exec_(global_pos)

    def delete_tag_action(self, label):
        self.DictManage.destroy_tag(label.text())

    def cherk_tag(self, tag):
        operators = [" and ", " or ", "'", "(", ")", "-"]
        for op in operators:
            if op in tag:
                QMessageBox.information(self, "错误", f"存在非法字符: {op}")
                return False
        return True

    def rename_tag_action(self, label):
        tag = label.text()
        new_name, ok = QInputDialog.getText(self, "重命名", "输入新标签名称:", text=tag)
        if ok and new_name:
            if not self.cherk_tag(new_name):
                return
            if new_name in self.DictManage.get_all_tags():
                reply = QMessageBox.question(
                    self,
                    "继续",
                    f"'{new_name}' 标签已存在，继续将合并标签，是否继续？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply == QMessageBox.Yes:
                    self.DictManage.rename_tag(tag, new_name)
            else:
                self.DictManage.rename_tag(tag, new_name)

    def change_tag_category_action(self, label):
        tag = label.text()
        rows = self.DictManage.query_category()
        existing_category = [row[0] for row in rows]
        category, ok = QInputDialog.getItem(self, "修改类别", "选择或输入新类别名称:", existing_category, 0, True)
        if ok and category:
            if category not in existing_category:
                QMessageBox.information(self, "错误", f"'{category}' 类别不存在")
                return False
            self.DictManage.change_tag_category(tag, category)

    def _show_toast(self, text, duration=500):
        toast = QLabel(text, self)
        toast.setStyleSheet(
            """
            QLabel {
                background-color: rgba(50, 50, 50, 180);
                color: white;
                padding: 8px 16px;
                border-radius: 8px;
            }
        """
        )
        toast.setAlignment(Qt.AlignCenter)
        toast.adjustSize()
        toast.move((self.width() - toast.width()) // 2, (self.height() - toast.height()) // 2)
        toast.setWindowOpacity(1)
        toast.show()

        fade = QPropertyAnimation(toast, b"windowOpacity", self)
        fade.setDuration(200)
        fade.setStartValue(1)
        fade.setEndValue(0)
        fade.finished.connect(toast.deleteLater)

        if not hasattr(self, "_toasts"):
            self._toasts = []
        self._toasts.append(fade)
        fade.finished.connect(lambda: self._toasts.remove(fade))
        QTimer.singleShot(max(0, duration - 200), fade.start)

    def addTag(self):
        tag = self.tag_input.text()
        if not tag or not self.cherk_tag(tag):
            return
        if self.model == "batch":
            self.DictManage.add_tag(tag, self.TagFileShowArea.get_files())
            self._show_toast("添加成功")
        else:
            self.SingleFileTagView.add_tag_current_file(tag)
        self.tag_input.clear()

    def deleteTag(self):
        tag = self.tag_input.text()
        if self.model == "batch":
            self.DictManage.delete_tag(tag, self.TagFileShowArea.get_files())
            self._show_toast("删除成功")
        else:
            self.SingleFileTagView.delete_tag_current_file(tag)

    def clearFile(self):
        self.TagFileShowArea.set_files([])
        self.file_paths.clear()
        self.SingleFileTagView.update_index(None)

    def toggle_view(self):
        current_sizes = self.splitter.sizes()

        if self.TagFileShowArea.isVisible():
            self.model = "single"
            # 从文件墙切到单文件模式时，优先沿用当前聚焦文件；
            # 如果当前没有聚焦项，再退化到列表第一项。
            file_path = self.TagFileShowArea.get_current_file()
            if file_path is None and self.TagFileShowArea.get_files():
                file_path = self.TagFileShowArea.get_files()[0]
            self.TagFileShowArea.hide()
            self.splitter.replaceWidget(0, self.SingleFileTagView)
            self.SingleFileTagView.show()
            self.SingleFileTagView.update_index(file_path)
            self.switch_view_button.setText("单文件视图")
        else:
            self.model = "batch"
            self.SingleFileTagView.hide()
            self.splitter.replaceWidget(0, self.TagFileShowArea)
            self.TagFileShowArea.show()
            # 切回文件墙时，把单文件模式中的当前文件重新同步回网格，并滚动到可见区域。
            file_path = self.SingleFileTagView.current_file_path
            if file_path is not None:
                self.TagFileShowArea.set_current_file(file_path, keep_selection=False)
                self.TagFileShowArea.scroll_to_file(file_path)
            self.switch_view_button.setText("多文件视图")

        self.splitter.setSizes(current_sizes)

    def change_quickly_model(self):
        self.quickly_model = not self.quickly_model
        config.set("TagView", "quickly_model", str(self.quickly_model))
        save_config()
        if self.quickly_model:
            self.model_button.setText("快速模式")
        else:
            self.model_button.setText("普通模式")

    def change_floder_model(self):
        self.TagFileShowArea.set_accept_folder(not self.TagFileShowArea.accepts_folder())
        if self.TagFileShowArea.accepts_folder():
            self.floder_button.setText("接受文件夹")
        else:
            self.floder_button.setText("不接受文件夹")

    def _sync_files_from_area(self, file_paths):
        # TagFileShowArea 现在是文件列表的单一事实来源；
        # 这里把它的变更同步给单文件视图，避免两边各自维护一份顺序。
        self.file_paths = list(file_paths)
        self.SingleFileTagView.file_paths = self.file_paths
        self.SingleFileTagView.update_index(self.SingleFileTagView.current_file_path)

    def keyPressEvent(self, event):
        if self.model == "single":
            if event.key() == Qt.Key_A:
                self.SingleFileTagView.show_previous()
            elif event.key() == Qt.Key_D:
                self.SingleFileTagView.show_next()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)
