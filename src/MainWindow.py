from .utils import *
from .FileShowArea import *
from .TagView import *
from .TagClass import *
from .CategoryManager import *
from .DictManage import *
from .TagInput import TagInputWidget
import sys  
import os  
from PyQt5.QtWidgets import QMainWindow, QHBoxLayout, QWidget, QVBoxLayout, QPushButton, QTreeWidgetItem, QApplication
from PyQt5.QtGui import QColor

class Tag2File(QMainWindow, Observer):
    def __init__(self):
        super().__init__()
        self.DictManage = DictManage()
        self.DictManage.add_observer(self)
        self.relation_graph = self.DictManage.relation_graph
        self.special_tags_status = self.DictManage.special_tags_status

        self.child_widget = [] # 文件属性窗口
        self.tag_view = None
        self.categoryManager = None
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
        file_menu.addAction("标签库", self.change_tag_base)

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
        self.tag_input = TagInputWidget(self.DictManage.relation_graph, self)
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
        
        special_categories = ["文件类型", "年龄分级", "质量"]

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
                if category in special_categories:
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
            if category in special_categories:
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
        self.changeFile(self.tag_expression)

    def closeEvent(self, event):
        self.MainFileShowArea.closeEvent(event)
        if self.categoryManager != None:
            self.categoryManager.close()
        if self.tag_view != None:
            self.tag_view.close()

        # 调用父类的 closeEvent 以确保主窗口正常关闭
        super().closeEvent(event)


    # ——————————————————————辅助功能————————————————————————

    #递归获取文件路径
    def get_all_files(slef, directory):
        directory = directory.replace('\\', '/') 
        files = []
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                file_path = os.path.join(root, filename).replace('\\', '/')
                files.append(file_path)
        return files
    
    # 获取tag对应文件路径
    def get_tag_files(self, tag_expression: str):
        result_tag = parse_set_expression(tag_expression)
        if not result_tag:
            message_box = QMessageBox(self)
            message_box.setIcon(QMessageBox.Information)
            message_box.setWindowTitle("错误！")
            message_box.setText(f"错误的表达式：{tag_expression}")
            message_box.exec_()
            return False
        result_files = eval(str(result_tag))
        if result_tag.Complement: # 如果结果是补集，则取所有文件的补集
            all_files = set(self.relation_graph['file'].keys())
            result_files = all_files - result_files
        # 处理特殊tag
        for spcial_tag, ischecked in self.special_tags_status.items():
            if not ischecked and spcial_tag not in ["图片","视频","音频","其他"]:
                result_files = result_files - self.relation_graph['tag'].get(spcial_tag, {}).get('file', set())
            
        for file_type in ["图片","视频","音频","其他"]:
            if not self.special_tags_status[file_type]:
                result_files = {file for file in result_files if self.get_file_type(file) != file_type}

        # 将结果转换为列表并规范化路径
        file_paths = list(result_files)
        for i in range(len(file_paths)):
            file_paths[i] = file_paths[i].replace('\\', '/')
        
        return file_paths

    def get_file_type(self, file_path):
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type:
            if mime_type.startswith('image'):
                return "图片"
            elif mime_type.startswith('video'):
                return "视频"
            elif mime_type.startswith('audio'):
                return "音频"
        return "其他"


    #————————————————————菜单栏功能——————————————————————

    def change_tag_base(self):
        # 获取当前的tagbase_name
        current_tagbase_name = config.get('DictManage', 'tagbase_name')

        # 弹出对话框让用户输入新的tagbase_name
        new_tagbase_name, ok = QInputDialog.getText(self, '修改标签库名称', '请输入新的标签库名称:', text=current_tagbase_name)

        if ok and new_tagbase_name:
            # 更新配置文件中的tagbase_name
            config.set('DictManage', 'tagbase_name', new_tagbase_name)
            save_config()

            # 更新界面或其他相关操作
            self.MainFileShowArea.changeFile([])
            self.DictManage.load_tagbase()
            self.update_tag_widget()

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
        if self.categoryManager == None:
            self.categoryManager = CategoryManager()
            self.categoryManager.show()
        else:
            self.categoryManager.show()
            self.categoryManager.activateWindow()
            self.categoryManager.setWindowState(Qt.WindowActive)

    # 改变显示文件
    def changeFile(self, tag_expression = None):
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
            self.MainFileShowArea.changeFile(file_paths)

    def clearInput(self):  
        self.tag_input.clear()
    
    # #集合操作输入文本框
    # def SetButtenClick(self, char):
    #     cursor_position = self.tag_input.cursorPosition()
    #     current_text = self.tag_input.text()
    #     new_text = current_text[:cursor_position] + char + current_text[cursor_position:]
    #     self.tag_input.setText(new_text)
    #     self.tag_input.setCursorPosition(cursor_position + len(char))  # 更新游标位置到新字符后

    # #点击tag输入文本框
    # def onTagClick(self, tag):
    #     cursor_position = self.tag_input.cursorPosition()  # 获取当前游标位置
    #     current_text = self.tag_input.text()  # 获取当前文本
    #     new_text = current_text[:cursor_position] + tag + current_text[cursor_position:]  # 在游标位置插入标签
    #     self.tag_input.setText(new_text)  # 设置新的文本
    #     self.tag_input.setCursorPosition(cursor_position + len(tag))  # 更新游标位置到标签后

    #点击tag输入文本框
    def onTagClick(self, tag):
        self.tag_input.add_tag(tag)


if __name__ == '__main__':  
    app = QApplication(sys.argv)
    set_application_font()
    viewer = Tag2File()

    sys.exit(app.exec_())