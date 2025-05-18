from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,   
                             QPushButton, QInputDialog, QMessageBox,   
                             QColorDialog, QSplitter, QWidget, QLabel, QDesktopWidget)  
from PyQt5.QtGui import QColor  
from PyQt5.QtCore import Qt  
from .DictManage import *  

class CategoryManager(QDialog, Observer):  
    def __init__(self):  
        QDialog.__init__(self)  
        Observer.__init__(self)  
        self.DictManage = DictManage()  
        self.DictManage.add_observer(self)  
        self.relation_graph = self.DictManage.relation_graph  
        self.special_tags_status = self.DictManage.special_tags_status  
        
        # 记住当前选择的类别和标签  
        self.current_category = None  
        self.current_tag = None  

        self.setWindowTitle("标签类别管理")  
        self.setGeometry(100, 100, 600, 400)  
        self.initUI()  
        self.loadCategories()  
        self.center()  

    def initUI(self):  
        layout = QHBoxLayout()  

        # 左侧：类别列表和按钮  
        leftWidget = QWidget()  
        leftLayout = QVBoxLayout(leftWidget)  

        self.categoryList = QListWidget()  
        leftLayout.addWidget(self.categoryList)  

        # 类别按钮 - 第一行  
        buttonLayout1 = QHBoxLayout()  
        self.addButton = QPushButton("添加类别")  
        self.editButton = QPushButton("编辑类别")  
        self.deleteButton = QPushButton("删除类别")  
        self.colorButton = QPushButton("设置颜色")  

        buttonLayout1.addWidget(self.addButton)  
        buttonLayout1.addWidget(self.editButton)  
        buttonLayout1.addWidget(self.deleteButton)  
        buttonLayout1.addWidget(self.colorButton)  

        # 类别按钮 - 第二行  
        buttonLayout2 = QHBoxLayout()  
        self.upCategoryButton = QPushButton("上移类别")  
        self.downCategoryButton = QPushButton("下移类别")  

        buttonLayout2.addWidget(self.upCategoryButton)  
        buttonLayout2.addWidget(self.downCategoryButton)  

        leftLayout.addLayout(buttonLayout1)  
        leftLayout.addLayout(buttonLayout2)  

        # 右侧：标签列表和按钮  
        rightWidget = QWidget()  
        rightLayout = QVBoxLayout(rightWidget)  

        self.tagListLabel = QLabel("标签列表")  
        rightLayout.addWidget(self.tagListLabel)  

        self.tagList = QListWidget()  
        rightLayout.addWidget(self.tagList)  

        # 标签按钮 - 第一行  
        tagButtonLayout1 = QHBoxLayout()  
        self.addTagButton = QPushButton("添加标签")  
        self.removeTagButton = QPushButton("移除标签")  
        tagButtonLayout1.addWidget(self.addTagButton)  
        tagButtonLayout1.addWidget(self.removeTagButton)  

        # 标签按钮 - 第二行  
        tagButtonLayout2 = QHBoxLayout()  
        self.upTagButton = QPushButton("上移标签")  
        self.downTagButton = QPushButton("下移标签")  
        tagButtonLayout2.addWidget(self.upTagButton)  
        tagButtonLayout2.addWidget(self.downTagButton)  

        rightLayout.addLayout(tagButtonLayout1)  
        rightLayout.addLayout(tagButtonLayout2)  

        # 使用QSplitter来允许用户调整左右两侧的宽度  
        splitter = QSplitter(Qt.Horizontal)  
        splitter.addWidget(leftWidget)  
        splitter.addWidget(rightWidget)  

        layout.addWidget(splitter)  
        self.setLayout(layout)  

        # 连接信号和槽  
        self.addButton.clicked.connect(self.addCategory)  
        self.editButton.clicked.connect(self.editCategory)  
        self.deleteButton.clicked.connect(self.deleteCategory)  
        self.colorButton.clicked.connect(self.setColor)  
        self.categoryList.currentItemChanged.connect(self.onCategoryChanged)  
        self.addTagButton.clicked.connect(self.addTag)  
        self.removeTagButton.clicked.connect(self.removeTag)  
        self.upCategoryButton.clicked.connect(self.upMoveCategory)  
        self.downCategoryButton.clicked.connect(self.downMoveCategory)  
        self.upTagButton.clicked.connect(self.upMoveTag)  
        self.downTagButton.clicked.connect(self.downMoveTag)  
        
        # 添加标签选择变化跟踪  
        self.tagList.currentItemChanged.connect(self.onTagChanged)  

    def center(self):  
        # 获取屏幕几何信息  
        screen = QDesktopWidget().screenNumber(QDesktopWidget().cursor().pos())  
        center_point = QDesktopWidget().screenGeometry(screen).center()  
        
        # 获取窗口几何信息  
        frame_geometry = self.frameGeometry()  
        
        # 将窗口中心设置为屏幕中心  
        frame_geometry.moveCenter(center_point)  
        self.move(frame_geometry.topLeft())  

    def closeEvent(self, event):  
        self.DictManage.remove_observer(self)  
        super().closeEvent(event)  

    def observer_update(self):  
        self.loadCategories()  
        # 恢复选择状态  
        if self.current_category:  
            # 查找并选择之前选中的类别  
            items = self.categoryList.findItems(self.current_category, Qt.MatchExactly)  
            if items:  
                self.categoryList.setCurrentItem(items[0])  
                # 当类别被选中后，onCategoryChanged会处理标签的恢复  

    def loadCategories(self):  
        self.categoryList.clear()  
        self.categoryList.addItems(self.relation_graph['category'].keys())  

    def onCategoryChanged(self, current, previous):  
        self.tagList.clear()  
        if current:  
            if type(current) != str:  
                self.current_category = current.text()  
                current = self.current_category  
            else:  
                self.current_category = current  
            self.tagList.addItems(self.relation_graph['category'][current]['tagOrder'])  
            self.tagListLabel.setText(f"标签列表 - {current}")  
            
            # 恢复标签选择  
            if self.current_tag:  
                tag_items = self.tagList.findItems(self.current_tag, Qt.MatchExactly)  
                if tag_items:  
                    self.tagList.setCurrentItem(tag_items[0])  
    
    def onTagChanged(self, current, previous):  
        # 记录当前选中的标签  
        if current:  
            self.current_tag = current.text()  

    def addCategory(self):  
        category, ok = QInputDialog.getText(self, "添加类别", "输入新类别名称:")  
        if ok and category:  
            if category not in self.relation_graph['category']:  
                self.relation_graph['category'][category] = {'tag': set(), 'tagColor': QColor(200, 200, 200).name(), 'tagOrder': []}  
                self.saveCategories()  
                self.loadCategories()  
            else:  
                QMessageBox.warning(self, "警告", "类别已存在！")  

    def editCategory(self):  
        currentItem = self.categoryList.currentItem()  
        if currentItem:  
            oldCategory = currentItem.text()  
            newCategory, ok = QInputDialog.getText(self, "编辑类别", "输入新类别名称:", text=oldCategory)  
            if ok and newCategory and newCategory != oldCategory:  
                self.relation_graph['category'][newCategory] = self.relation_graph['category'].pop(oldCategory)  
                
                # 如果正在修改当前选中的类别，需要更新记录  
                if self.current_category == oldCategory:  
                    self.current_category = newCategory  
                
                self.saveCategories()  
                self.loadCategories()  

    def deleteCategory(self):  
        currentItem = self.categoryList.currentItem()  
        if currentItem:  
            category = currentItem.text()  
            reply = QMessageBox.question(self, "确认删除", f"确定要删除类别 '{category}' 吗？",  
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)  
            if reply == QMessageBox.Yes:  
                del self.relation_graph['category'][category]  
                
                # 如果删除当前选中的类别，需要清除记录  
                if self.current_category == category:  
                    self.current_category = None  
                    self.current_tag = None  
                
                self.saveCategories()  
                self.loadCategories()  

    def setColor(self):  
        currentItem = self.categoryList.currentItem()  
        if currentItem:  
            category = currentItem.text()  
            color = QColorDialog.getColor()  
            if color.isValid():  
                self.relation_graph['category'][category]['tagColor'] = color.name()  
                self.saveCategories()  

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

    def addTag(self):  
        currentCategory = self.categoryList.currentItem()  
        if currentCategory:  
            category = currentCategory.text()  
            existing_tags = self.relation_graph['tag'].keys()  
            
            tag, ok = QInputDialog.getItem(self, "添加标签", "选择或输入新标签名称:", existing_tags, 0, True)  
            if ok and tag:  
                if tag not in existing_tags:
                    if not self.cherk_tag(tag):
                        return
                    self.DictManage.add_tag(tag, [])  
                if tag not in self.relation_graph['category'][category]['tag']:  
                    self.current_tag = tag  # 记住新添加的标签  
                    self.DictManage.change_tag_category(tag, category)  
                    self.onCategoryChanged(category, None)  
                else:  
                    QMessageBox.warning(self, "警告", "标签已存在于此类别！")  

    def removeTag(self):  
        currentCategory = self.categoryList.currentItem()  
        currentTag = self.tagList.currentItem()  
        if currentCategory and currentTag:  
            category = currentCategory.text()  
            tag = currentTag.text()  
            reply = QMessageBox.question(self, "确认移除", f"确定要从类别 '{category}' 中移除标签 '{tag}' 吗？",  
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)  
            if reply == QMessageBox.Yes:  
                # 清除当前选中的标签记录  
                if self.current_tag == tag:  
                    self.current_tag = None  
                
                self.DictManage.change_tag_category(tag, '未分类')  
                self.onCategoryChanged(category, None)  

    def upMoveTag(self):  
        currentCategory = self.categoryList.currentItem()  
        currentTag = self.tagList.currentItem()  
        if currentCategory and currentTag:  
            category = currentCategory.text()  
            tag = currentTag.text()  
            self.current_category = category  # 记住当前选择的类别  
            self.current_tag = tag  # 记住当前选择的标签  
            list_object = self.relation_graph['category'][category]['tagOrder']  
            self.DictManage.move_element(list_object, tag, 'up')  
    
    def downMoveTag(self):  
        currentCategory = self.categoryList.currentItem()  
        currentTag = self.tagList.currentItem()  
        if currentCategory and currentTag:  
            category = currentCategory.text()  
            tag = currentTag.text()  
            self.current_category = category  # 记住当前选择的类别  
            self.current_tag = tag  # 记住当前选择的标签  
            list_object = self.relation_graph['category'][category]['tagOrder']  
            self.DictManage.move_element(list_object, tag, 'down')  

    def upMoveCategory(self):  
        currentCategory = self.categoryList.currentItem()  
        if currentCategory:  
            category = currentCategory.text()  
            self.current_category = category  # 记住当前选择的类别  
            self.DictManage.move_key(self.relation_graph['category'], category, 'up')  
    
    def downMoveCategory(self):  
        currentCategory = self.categoryList.currentItem()  
        if currentCategory:  
            category = currentCategory.text()  
            self.current_category = category  # 记住当前选择的类别  
            self.DictManage.move_key(self.relation_graph['category'], category, 'down')  

    def saveCategories(self):  
        self.DictManage.save_notify()  