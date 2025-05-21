from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,   
                             QPushButton, QInputDialog, QMessageBox,   
                             QColorDialog, QSplitter, QWidget, QLabel, QDesktopWidget,
                             QMenu)  
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
        # 启用拖放功能
        self.categoryList.setDragDropMode(QListWidget.InternalMove)
        self.categoryList.setDefaultDropAction(Qt.MoveAction)
        self.categoryList.model().rowsMoved.connect(self.onCategoryOrderChanged)
        # 右键菜单
        self.categoryList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.categoryList.customContextMenuRequested.connect(self.showCategoryContextMenu)
        leftLayout.addWidget(self.categoryList)  

        # 类别操作按钮：添加/上移/下移
        buttonLayout = QHBoxLayout()  
        self.addButton = QPushButton("添加类别")
        self.upCategoryButton = QPushButton("上移")  
        self.downCategoryButton = QPushButton("下移")
        buttonLayout.addWidget(self.addButton)
        buttonLayout.addWidget(self.upCategoryButton)  
        buttonLayout.addWidget(self.downCategoryButton)
        leftLayout.addLayout(buttonLayout)  

        # 右侧：标签列表和按钮  
        rightWidget = QWidget()  
        rightLayout = QVBoxLayout(rightWidget)  

        self.tagListLabel = QLabel("标签列表")  
        rightLayout.addWidget(self.tagListLabel)  

        self.tagList = QListWidget()
        # 启用拖放功能
        self.tagList.setDragDropMode(QListWidget.InternalMove)
        self.tagList.setDefaultDropAction(Qt.MoveAction)
        self.tagList.model().rowsMoved.connect(self.onTagOrderChanged)
        # 右键菜单
        self.tagList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tagList.customContextMenuRequested.connect(self.showTagContextMenu)
        rightLayout.addWidget(self.tagList)  

        # 标签操作按钮：添加/上移/下移
        tagButtonLayout = QHBoxLayout()  
        self.addTagButton = QPushButton("添加标签")
        self.upTagButton = QPushButton("上移")  
        self.downTagButton = QPushButton("下移")
        tagButtonLayout.addWidget(self.addTagButton)
        tagButtonLayout.addWidget(self.upTagButton)  
        tagButtonLayout.addWidget(self.downTagButton)
        rightLayout.addLayout(tagButtonLayout)  

        # 使用QSplitter来允许用户调整左右两侧的宽度  
        splitter = QSplitter(Qt.Horizontal)  
        splitter.addWidget(leftWidget)  
        splitter.addWidget(rightWidget)  

        layout.addWidget(splitter)  
        self.setLayout(layout)  

        # 连接信号和槽  
        self.addButton.clicked.connect(self.addCategory)
        self.upCategoryButton.clicked.connect(self.upMoveCategory)  
        self.downCategoryButton.clicked.connect(self.downMoveCategory)
        self.categoryList.currentItemChanged.connect(self.onCategoryChanged)  
        self.addTagButton.clicked.connect(self.addTag) 
        self.upTagButton.clicked.connect(self.upMoveTag)  
        self.downTagButton.clicked.connect(self.downMoveTag)
        self.tagList.currentItemChanged.connect(self.onTagChanged)  

    def showCategoryContextMenu(self, position):
        menu = QMenu()
        currentItem = self.categoryList.currentItem()
        
        if currentItem:
            editAction = menu.addAction("重命名")
            deleteAction = menu.addAction("删除")
            colorAction = menu.addAction("设置颜色")
            
            # 根据特殊类别状态动态设置文本
            category = currentItem.text()
            specialText = "设为普通类别" if category in self.DictManage.special_categories else "设为筛选类别"
            specialAction = menu.addAction(specialText)
            
            # 获取用户点击的操作
            action = menu.exec_(self.categoryList.mapToGlobal(position))
            
            # 根据用户选择执行相应操作
            if action == editAction:
                self.editCategory()
            elif action == deleteAction:
                self.deleteCategory()
            elif action == colorAction:
                self.setColor()
            elif action == specialAction:
                self.setSpecialCategory()

    def showTagContextMenu(self, position):
        menu = QMenu()
        currentTag = self.tagList.currentItem()
        
        if currentTag and self.current_category:
            removeAction = menu.addAction("移除标签")
            
            action = menu.exec_(self.tagList.mapToGlobal(position))
            
            if action == removeAction:
                self.removeTag()

    def onCategoryOrderChanged(self):
        # 当用户拖动完成后更新数据模型
        categories = [self.categoryList.item(i).text() for i in range(self.categoryList.count())]
        self.reorderCategories(categories)
    
    def reorderCategories(self, new_order):
        # 重新排序类别
        new_categories = {}
        for category in new_order:
            if category in self.relation_graph['category']:
                new_categories[category] = self.relation_graph['category'][category]
        
        # 处理可能未包含在new_order中的类别
        for category in self.relation_graph['category']:
            if category not in new_categories:
                new_categories[category] = self.relation_graph['category'][category]
        
        self.relation_graph['category'] = new_categories
        self.saveCategories()
    
    def onTagOrderChanged(self):
        if not self.current_category:
            return
        tags = [self.tagList.item(i).text() for i in range(self.tagList.count())]
        self.DictManage.reorder_tags(self.current_category, tags)

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
            items = self.categoryList.findItems(self.current_category, Qt.MatchExactly)  
            if items:  
                self.categoryList.setCurrentItem(items[0])

    def loadCategories(self):  
        self.categoryList.clear()  
        self.categoryList.addItems(self.relation_graph['category'].keys())  

    def onCategoryChanged(self, current):  
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
    
    def onTagChanged(self, current):  
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

    def setSpecialCategory(self):
        currentItem = self.categoryList.currentItem()
        if currentItem:
            category = currentItem.text()
            if category in self.DictManage.special_categories:
                self.DictManage.special_categories.remove(category)
            else:
                self.DictManage.special_categories.append(category)
            
            # 保存更改
            with shelve.open(self.DictManage.tag_dict_path, writeback=True) as shelf:
                shelf['special_categories'] = self.DictManage.special_categories
            self.DictManage.save_notify()

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
        currentTag = self.tagList.currentItem()
        if currentTag and self.current_category:
            current_index = self.tagList.row(currentTag)
            if current_index > 0:
                tags = [self.tagList.item(i).text() for i in range(self.tagList.count())]
                tags[current_index], tags[current_index-1] = tags[current_index-1], tags[current_index]
                self.DictManage.reorder_tags(self.current_category, tags)
                # 保持选中状态
                self.tagList.setCurrentRow(current_index-1)

    def downMoveTag(self):
        currentTag = self.tagList.currentItem()
        if currentTag and self.current_category:
            current_index = self.tagList.row(currentTag)
            if current_index < self.tagList.count() - 1:
                tags = [self.tagList.item(i).text() for i in range(self.tagList.count())]
                tags[current_index], tags[current_index+1] = tags[current_index+1], tags[current_index]
                self.DictManage.reorder_tags(self.current_category, tags)
                # 保持选中状态
                self.tagList.setCurrentRow(current_index+1)

    def upMoveCategory(self):  
        currentItem = self.categoryList.currentItem()  
        if currentItem:  
            current_index = self.categoryList.row(currentItem)
            if current_index > 0:
                categories = [self.categoryList.item(i).text() for i in range(self.categoryList.count())]
                categories[current_index], categories[current_index-1] = categories[current_index-1], categories[current_index]
                self.reorderCategories(categories)
                # 保持选中状态
                self.categoryList.setCurrentRow(current_index-1)
    
    def downMoveCategory(self):  
        currentItem = self.categoryList.currentItem()  
        if currentItem:  
            current_index = self.categoryList.row(currentItem)
            if current_index < self.categoryList.count() - 1:
                categories = [self.categoryList.item(i).text() for i in range(self.categoryList.count())]
                categories[current_index], categories[current_index+1] = categories[current_index+1], categories[current_index]
                self.reorderCategories(categories)
                # 保持选中状态
                self.categoryList.setCurrentRow(current_index+1)

    def saveCategories(self):  
        self.DictManage.save_notify()