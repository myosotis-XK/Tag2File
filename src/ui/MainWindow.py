import os
import sys  
from io import BytesIO
from dataclasses import dataclass
from typing import Optional
from PyQt5.QtWidgets import QMainWindow, QHBoxLayout, QWidget, QVBoxLayout, QPushButton, QTreeWidgetItem, QApplication, QSystemTrayIcon, QSizePolicy
from PyQt5.QtGui import QColor, QFontMetrics
import socket
import qrcode
from src.utils import *
from src.core.DictManage import *
from src.models.TagClass import *
from .FileShowArea import *
from .TagView import *
from .TagInput import TagInputWidget
from .TagbaseManager import *
from .CategoryManager import *


@dataclass
class SearchSnapshot:
    file_paths: list[str]
    selected_files: list[str]
    current_file: Optional[str]
    scroll_offset: QPoint
    tag_expression: str

class WebUsagePopup(QWidget):
    def __init__(self, url):
        super().__init__()
        self.setWindowTitle("Web端入口")
        self.setFixedSize(300, 350)
        self.url = url
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(15)  # 元素间距

        # “访问地址”标题
        label_title = QLabel("访问地址")
        font_title = QFont()
        font_title.setPointSize(14)
        font_title.setBold(True)
        label_title.setFont(font_title)
        label_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(label_title)

        # URL 单独一行，可点击
        label_url = QLabel(f"<a href='{self.url}'>{self.url}</a>")
        font_url = QFont()
        font_url.setPointSize(12)
        label_url.setFont(font_url)
        label_url.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        label_url.setOpenExternalLinks(True)
        label_url.setAlignment(Qt.AlignCenter)
        layout.addWidget(label_url)

        # 生成二维码
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(self.url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(buffer.getvalue())

        # 二维码显示
        label_qr = QLabel()
        label_qr.setPixmap(pixmap)
        label_qr.setAlignment(Qt.AlignCenter)
        layout.addWidget(label_qr)

        self.setLayout(layout)


class Tag2File(QMainWindow):
    def __init__(self):
        super().__init__()
        self.DictManage = DictManage()
        self.DictManage.tagChanged.connect(self._on_tag_changed)
        self.DictManage.categoryChanged.connect(self._on_category_changed)
        self.DictManage.fileChanged.connect(self._on_file_changed)
        self.DictManage.tagbaseChanged.connect(self._on_tagbase_changed)

        self.child_widget = [] # 文件属性窗口
        self.tag_view = None
        self.categoryManager = None
        self.tagbaseManager = None
        self.web_popup = None 
        self.image_paths = []
        self.tag_expression = ''
        self.browse_mode = "search"
        self.search_snapshot: Optional[SearchSnapshot] = None
        self.browse_root: Optional[str] = None
        self.current_folder: Optional[str] = None

        self.icon = QIcon(os.path.join(root, 'data', 'icon', 'app', 'favicon.ico'))
        self.setWindowTitle("Tag2File") 
        self.setWindowIcon(self.icon)
        self.resize(1200, 700)

        # 托盘设置
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.icon)
        self.tray_icon.setToolTip("Tag2File")     

        # 托盘菜单
        tray_menu = QMenu()
        show_action = QAction("显示窗口", self)
        quit_action = QAction("退出", self)
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)

        # 连接信号
        show_action.triggered.connect(self.show_normal)
        quit_action.triggered.connect(self.exit_app)
        self.tray_icon.activated.connect(self.on_tray_activated)

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout(central_widget)

        # 创建菜单栏
        menubar = self.menuBar()

        # 创建设置菜单
        file_menu = menubar.addMenu("开始")
        file_menu.addAction("标签库", self.showTagbaseManager)
        file_menu.addAction("Web端入口", self.show_web_usage)
        file_menu.addAction("最小化到托盘", self.minimize_to_tray)

        # 创建界面
        self.file_view = QWidget()
        self.MainFileShowArea = MainFileShowArea(self)
        self.MainFileShowArea.requestManageTags.connect(lambda file_paths: self.showTagView(None, file_paths))
        self.MainFileShowArea.folderActivated.connect(self.enter_folder)
        self.initFileView()
        # 将视图添加到布局中
        self.layout.addWidget(self.file_view)

        self.show()
        self.MainFileShowArea.updateLayout()

    def initFileView(self):
        # 创建切换按钮布局
        switch_layout = QHBoxLayout()
        tag_button = QPushButton("管理标签")
        tag_button.setFixedHeight(30)
        tag_button.setStyleSheet("font-size: 14px;")
        tag_button.clicked.connect(self.showTagView)
        switch_layout.addWidget(tag_button)

        category_button = QPushButton("管理类别")
        category_button.setFixedHeight(30)
        category_button.setStyleSheet("font-size: 14px;")
        category_button.clicked.connect(self.showCategoryManager)
        switch_layout.addWidget(category_button)
        # 创建搜索框布局
        search_layout = QVBoxLayout()
        search_button = QPushButton("查询", self)
        search_button.setFixedHeight(30)
        search_button.setStyleSheet("font-size: 14px;")
        search_button.clicked.connect(lambda: self.changeFile())  # 绑定切换函数
        # 创建清空输入框的按钮  
        clear_button = QPushButton("清空", self)
        clear_button.setFixedHeight(30)
        clear_button.setStyleSheet("font-size: 14px;")
        clear_button.clicked.connect(self.clearInput)  # 绑定清空函数
        
        search_layout2 = QHBoxLayout()
        search_layout2.addWidget(search_button)
        search_layout2.addWidget(clear_button)

        self.tag_input = TagInputWidget(self)
        search_layout.addWidget(self.tag_input)
        search_layout.addLayout(search_layout2)

        self.tag_tree = self.create_tag_widget()


        # 创建左侧菜单布局
        self.menu_layout = QVBoxLayout()
        self.menu_layout.addLayout(switch_layout)
        self.menu_layout.addLayout(search_layout)
        self.menu_layout.addWidget(self.tag_tree)

        self.menu_layout.setContentsMargins(0, 0, 0, 0)  # 左、上、右、下边距


        menu_widget = QWidget()
        menu_widget.setLayout(self.menu_layout)
        menu_widget.setFixedWidth(250)

        self.folder_nav_bar = QWidget()
        self.folder_nav_bar.setObjectName("folder_nav_bar")
        self.folder_nav_bar.setFixedHeight(36)
        self.folder_nav_bar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.folder_nav_bar.setStyleSheet("QWidget#folder_nav_bar { background-color: white; }")
        folder_nav_layout = QHBoxLayout(self.folder_nav_bar)
        folder_nav_layout.setContentsMargins(8, 0, 0, 0)
        folder_nav_layout.setSpacing(8)

        self.restore_search_button = QPushButton("返回搜索结果")
        self.restore_search_button.setFixedHeight(30)
        self.restore_search_button.setStyleSheet("font-size: 14px;")
        self.restore_search_button.clicked.connect(self.restore_search_snapshot)
        folder_nav_layout.addWidget(self.restore_search_button)

        self.go_parent_button = QPushButton("上一级")
        self.go_parent_button.setFixedHeight(30)
        self.go_parent_button.setStyleSheet("font-size: 14px;")
        self.go_parent_button.clicked.connect(self.go_parent_or_restore)
        folder_nav_layout.addWidget(self.go_parent_button)

        self.current_path_label = QLabel("")
        self.current_path_label.setMinimumWidth(0)
        self.current_path_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.current_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.current_path_label.setStyleSheet("background-color: white; padding-left: 8px;")
        folder_nav_layout.addWidget(self.current_path_label, 1)
        self._full_current_path = ""

        self.right_panel = QWidget()
        self.right_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(0)
        self.right_layout.addWidget(self.folder_nav_bar)
        self.right_layout.addWidget(self.MainFileShowArea)
        self.right_layout.setStretch(0, 0)
        self.right_layout.setStretch(1, 1)

        # 创建主布局
        self.main_layout = QHBoxLayout(self.file_view)
        self.main_layout.addWidget(menu_widget)
        self.main_layout.addWidget(self.right_panel)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self._update_folder_nav()

    def on_tray_activated(self, reason):
        """托盘图标点击事件"""
        if reason == QSystemTrayIcon.Trigger:
            self.show_normal()

    def show_normal(self):
        """恢复窗口"""
        self.show()
        self.tray_icon.hide()
        self.setWindowState(Qt.WindowActive)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_current_path_label()

    def minimize_to_tray(self):
        """最小化到托盘"""
        self.hide()
        self.tray_icon.show()

    def exit_app(self):
        """退出程序"""
        self.tray_icon.hide()
        self.close()

    def create_tag_widget(self):
        tree = CategoryTreeWidget(self)
        tree.setIndentation(10)

        # 创建类别项
        for item in self.DictManage.query_category():
            category = item[0]
            color = QColor(item[1])
            is_special = item[2]

            category_item = QTreeWidgetItem(tree)
            category_item.setText(0, category)
            category_font = QApplication.font() 
            category_font.setPointSize(14)
            category_item.setFont(0, category_font)

            tags = self.DictManage.query('category', category, 'tag')
            for tag in tags:
                if is_special:
                    label = SpecialTagLabel(tag, color, self)
                    label.checkStateChanged.connect(self.onSpecialLabelCheckChanged)
                    label.isChecked = self.DictManage.get_special_tag_status(tag)
                else:
                    file_count = self.DictManage.query_tag_file_count(tag)
                    label = TagLabel(tag, file_count, color, self)
                label_item = QTreeWidgetItem(category_item)
                tree.setItemWidget(label_item, 0, label)
            # 设置展开状态
            if is_special:
                category_item.setExpanded(False)
            else:
                category_item.setExpanded(True)
        return tree

    def update_tag_widget(self):
        # 保存当前的展开状态

        expanded_categories = []
        root = self.tag_tree.invisibleRootItem()
        for i in range(root.childCount()):
            category_item = root.child(i)
            if category_item.isExpanded():
                expanded_categories.append(category_item.text(0))
        # 获取当前滚动条的位置
        current_scroll = self.tag_tree.verticalScrollBar().value()
        # 更新标签树
        new_tag_tree = self.create_tag_widget()
        self.menu_layout.replaceWidget(self.tag_tree, new_tag_tree)
        self.tag_tree.deleteLater()
        self.tag_tree = new_tag_tree
        # 恢复展开状态
        root = self.tag_tree.invisibleRootItem()
        for i in range(root.childCount()):
            category_item = root.child(i)
            if category_item.text(0) in expanded_categories:
                category_item.setExpanded(True)
        # 安全地设置滚动条位置
        max_scroll = self.tag_tree.verticalScrollBar().maximum()
        new_scroll = min(current_scroll, max_scroll)
        self.tag_tree.verticalScrollBar().setValue(new_scroll)

    def onSpecialLabelCheckChanged(self, tag, checked):
        self.DictManage.change_special_tags_status(tag, checked)
        self.changeFile(self.tag_expression)

    def observer_update(self):
        self.update_tag_widget()
        if self.browse_mode == "folder_browse":
            return
        self.changeFile(self.tag_expression, True)

    def _on_tag_changed(self, action, payload):
        self.observer_update()

    def _on_category_changed(self, action, payload):
        self.update_tag_widget()

    def _on_file_changed(self, action, payload):
        self.update_tag_widget()
        if self.browse_mode == "folder_browse":
            return
        self.changeFile(self.tag_expression, True)

    def _on_tagbase_changed(self, db_path):
        self.observer_update()


    def closeEvent(self, event):
        self.MainFileShowArea.closeEvent(event)
        if self.categoryManager != None:
            self.categoryManager.close()
        if self.tagbaseManager!= None:
            self.tagbaseManager.close()
        if self.tag_view != None:
            self.tag_view.close()

        super().closeEvent(event)


    # ——————————————————————辅助功能————————————————————————

    # 获取tag对应文件路径
    def get_tag_files(self, tag_expression: str) -> list[tuple[str, int, float]]:
        file_paths = get_tag_files(tag_expression, self.DictManage)
        if file_paths is False:
            message_box = QMessageBox(self)
            message_box.setIcon(QMessageBox.Information)
            message_box.setWindowTitle("错误！")
            message_box.setText(f"错误的表达式：{tag_expression}")
            message_box.exec_()
            return False

        return file_paths




    #————————————————————菜单栏功能——————————————————————

    def showTagView(self, event, file_paths=None):
        if file_paths is None:
            file_paths = []
        if self.tag_view is None:
            self.tag_view = TagView(self, file_paths)
            self.tag_view.show()
        else:
            self.tag_view.addFile(file_paths)
            self.tag_view.show()
            self.tag_view.activateWindow()
            self.tag_view.setWindowState(Qt.WindowActive)

    def showCategoryManager(self):
        self.categoryManager = CategoryManager()
        self.categoryManager.show()

    def showTagbaseManager(self):
        self.tagbaseManager = TagbaseManager(self)
        self.tagbaseManager.show()

    # 改变显示文件
    def changeFile(self, tag_expression = None, recover=False):
        if tag_expression == None:
            self.tag_expression = self.tag_input.get_query()
        else:
            self.tag_expression = tag_expression
        self._clear_folder_browse()
        if self.tag_expression == '':
            file_paths = []
            self.MainFileShowArea.set_files(file_paths)
        else:
            file_paths = self.get_tag_files(self.tag_expression)
            if file_paths is False:
                return
            self.MainFileShowArea.set_files(file_paths, recover_scroll=recover)

    def enter_folder(self, folder_path: str) -> None:
        folder_path = os.path.normpath(folder_path)
        snapshot = self.search_snapshot
        browse_root = self.browse_root
        if self.browse_mode != "folder_browse":
            snapshot = SearchSnapshot(
                file_paths=self.MainFileShowArea.get_files(),
                selected_files=self.MainFileShowArea.get_selected_files(),
                current_file=self.MainFileShowArea.get_current_file(),
                scroll_offset=self.MainFileShowArea.get_scroll_offset(),
                tag_expression=self.tag_expression,
            )
            browse_root = folder_path
        if self.show_folder(folder_path):
            self.search_snapshot = snapshot
            self.browse_root = browse_root
            self.browse_mode = "folder_browse"
            self._update_folder_nav()

    def show_folder(self, folder_path: str) -> bool:
        try:
            file_meta_datas: list[tuple[str, int, float]] = []
            with os.scandir(folder_path) as entries:
                for entry in entries:
                    try:
                        stat_info = entry.stat()
                    except OSError:
                        continue
                    file_size = 0 if entry.is_dir() else stat_info.st_size
                    file_meta_datas.append((entry.path.replace("\\", "/"), file_size, stat_info.st_mtime))
        except OSError as exc:
            QMessageBox.critical(self, "错误", f"无法打开文件夹：\n{folder_path}\n{exc}")
            return False

        self.current_folder = folder_path
        self.MainFileShowArea.set_files(file_meta_datas)
        self._update_folder_nav()
        return True

    def go_parent_or_restore(self) -> None:
        if self.browse_mode != "folder_browse" or not self.current_folder or not self.browse_root:
            self.restore_search_snapshot()
            return

        current_folder = os.path.normpath(self.current_folder)
        parent_folder = os.path.dirname(current_folder)
        if not parent_folder or parent_folder == current_folder:
            self.restore_search_snapshot()
            return

        try:
            browse_root = os.path.normpath(self.browse_root)
            within_root = os.path.commonpath([os.path.normpath(parent_folder), browse_root]) == browse_root
        except ValueError:
            within_root = False

        if within_root:
            self.show_folder(parent_folder)
        else:
            self.restore_search_snapshot()

    def restore_search_snapshot(self) -> None:
        if self.search_snapshot is None:
            self._clear_folder_browse()
            self.MainFileShowArea.set_files([])
            return

        snapshot = self.search_snapshot
        self.MainFileShowArea.set_files([(file_path, 0, 0) for file_path in snapshot.file_paths], recover_scroll=False)
        self.MainFileShowArea.set_selected_files(snapshot.selected_files, snapshot.current_file)
        self.MainFileShowArea.set_scroll_offset(snapshot.scroll_offset)
        self.tag_expression = snapshot.tag_expression
        self._clear_folder_browse()

    def _clear_folder_browse(self) -> None:
        self.browse_mode = "search"
        self.search_snapshot = None
        self.browse_root = None
        self.current_folder = None
        self._update_folder_nav()

    def _update_folder_nav(self) -> None:
        is_browse_mode = self.browse_mode == "folder_browse"
        self.folder_nav_bar.setVisible(is_browse_mode)
        self.restore_search_button.setEnabled(is_browse_mode and self.search_snapshot is not None)
        self.go_parent_button.setEnabled(is_browse_mode)
        self._full_current_path = self.current_folder or ""
        self._refresh_current_path_label()

    def _refresh_current_path_label(self) -> None:
        if not hasattr(self, "current_path_label"):
            return
        metrics = QFontMetrics(self.current_path_label.font())
        available_width = max(0, self.current_path_label.width() - 8)
        if available_width <= 0:
            self.current_path_label.setText("")
            self.current_path_label.setToolTip(self._full_current_path)
            return
        elided_text = metrics.elidedText(self._full_current_path, Qt.ElideMiddle, available_width)
        self.current_path_label.setText(elided_text)
        self.current_path_label.setToolTip(self._full_current_path)

    def clearInput(self):  
        self.tag_input.clear()

    #点击tag输入文本框
    def onTagClick(self, tag):
        self.tag_input.add_element(tag)

    def _get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        return ip

    def show_web_usage(self):
        local_ip = self._get_local_ip()
        port = 10252
        url = f"http://{local_ip}:{port}"

        self.web_popup = WebUsagePopup(url)
        self.web_popup.show()
