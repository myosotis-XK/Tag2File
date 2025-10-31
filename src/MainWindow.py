from .utils import *
from .DictManage import *
from .FileShowArea import *
from .TagView import *
from .TagClass import *
from .CategoryManager import *
from .TagbaseManager import *
from .TagInput import TagInputWidget
import sys  
from PyQt5.QtWidgets import QMainWindow, QHBoxLayout, QWidget, QVBoxLayout, QPushButton, QTreeWidgetItem, QApplication
from PyQt5.QtGui import QColor

class Tag2File(QMainWindow, Observer):
    def __init__(self):
        super().__init__()
        self.DictManage = DictManage()
        self.DictManage.add_observer(self)
        self.relation_graph = self.DictManage.relation_graph
        self.special_categories = self.DictManage.special_categories
        self.special_tags_status = self.DictManage.special_tags_status

        self.child_widget = [] # 文件属性窗口
        self.tag_view = None
        self.categoryManager = None
        self.tagbaseManager = None
        self.image_paths = []
        self.tag_expression = ''

        self.setWindowTitle("Tag2File")
        self.resize(1200, 700)
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout(central_widget)

        # 创建菜单栏
        menubar = self.menuBar()

        # 创建设置菜单
        file_menu = menubar.addMenu("开始")
        file_menu.addAction("标签库", self.showTagbaseManager)

        # 创建界面
        self.file_view = QWidget()
        self.MainFileShowArea = MainFileShowArea(self)
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


        # 创建主布局
        self.main_layout = QHBoxLayout(self.file_view)
        self.main_layout.addWidget(menu_widget)
        self.main_layout.addWidget(self.MainFileShowArea)
        self.main_layout.setContentsMargins(0, 0, 0, 0) 

    def create_tag_widget(self):
        tree = CategoryTreeWidget(self)
        tree.setIndentation(10)

        # 创建固定文件类型项
        category_item = QTreeWidgetItem(tree)
        category_item.setText(0, "文件类型")
        category_font = QApplication.font() 
        category_font.setPointSize(14)
        category_item.setFont(0, category_font)

        color = QColor(0,0,0)
        for tag in ["图片","视频","音频","其他"]:
            label = SpecialTagLabel(tag, color, self)
            label.checkStateChanged.connect(self.onSpecialLabelCheckChanged)
            if tag in self.special_tags_status:
                label.isChecked = self.special_tags_status[tag]
            else:
                self.DictManage.change_special_tags_status(tag, True)
            label_item = QTreeWidgetItem(category_item)
            tree.setItemWidget(label_item, 0, label)


        # 创建类别项
        for category, value in self.relation_graph['category'].items():
            category_item = QTreeWidgetItem(tree)
            category_item.setText(0, category)
            category_font = QApplication.font() 
            category_font.setPointSize(14)
            category_item.setFont(0, category_font)

            tags = value['tagOrder']
            color = QColor(value['tagColor'])
            for tag in tags:
                if category in self.special_categories:
                    label = SpecialTagLabel(tag, color, self)
                    label.checkStateChanged.connect(self.onSpecialLabelCheckChanged)
                    if tag in self.special_tags_status:
                        label.isChecked = self.special_tags_status[tag]
                    else:
                        self.DictManage.change_special_tags_status(tag, True)
                else:
                    file_count = len(self.relation_graph['tag'].get(tag, {}).get('file', set()))
                    label = TagLabel(tag, file_count, color, self)
                label_item = QTreeWidgetItem(category_item)
                tree.setItemWidget(label_item, 0, label)

            # 设置展开状态
            if category in self.special_categories:
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
        self.changeFile(self.tag_expression, True)

    def closeEvent(self, event):
        self.MainFileShowArea.closeEvent(event)
        if self.categoryManager != None:
            self.categoryManager.close()
        if self.tagbaseManager!= None:
            self.tagbaseManager.close()
        if self.tag_view != None:
            self.tag_view.close()

        try:
            self.DictManage.compact_tagbase()
        except Exception as e:
            print(f"Error compacting shelve: {e}")

        super().closeEvent(event)


    # ——————————————————————辅助功能————————————————————————

    # 获取tag对应文件路径
    def get_tag_files(self, tag_expression: str):
        file_paths = get_tag_files(tag_expression, self.special_tags_status)
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
        if self.tag_expression == '':
            file_paths = []
            self.MainFileShowArea.changeFile(file_paths)
        else:
            file_paths = self.get_tag_files(self.tag_expression)
            if file_paths is False:
                return
            self.MainFileShowArea.changeFile(file_paths, recover)

    def clearInput(self):  
        self.tag_input.clear()

    #点击tag输入文本框
    def onTagClick(self, tag):
        self.tag_input.add_element(tag)


if __name__ == '__main__':  
    app = QApplication(sys.argv)
    set_application_font()
    viewer = Tag2File()

    sys.exit(app.exec_())