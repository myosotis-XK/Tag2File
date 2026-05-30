from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                             QMessageBox, QColorDialog,
                             QSplitter, QWidget, QLabel, QDesktopWidget,
                             QFrame,
                             QLineEdit, QDialogButtonBox, QCompleter)
from PyQt5.QtCore import Qt, QStringListModel
from PyQt5.QtGui import QColor
from src.core.DictManage import *  
from src.ui.components.style_utils import (
    apply_button_style,
    apply_dialog_style,
    apply_line_edit_style,
    apply_list_widget_style,
    build_tag_color_tokens,
    configure_dialog_button_box,
    create_button,
    create_context_menu,
)

class CategoryManager(QDialog):  
    def __init__(self):
        QDialog.__init__(self)  
        self.DictManage = DictManage()  
        self.DictManage.categoryChanged.connect(self._on_dict_changed)
        self.DictManage.tagChanged.connect(self._on_dict_changed)
        
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
        apply_list_widget_style(self.categoryList)
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
        self.addButton = create_button("添加类别")
        self.upCategoryButton = create_button("上移")  
        self.downCategoryButton = create_button("下移")
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
        apply_list_widget_style(self.tagList)
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
        self.addTagButton = create_button("添加标签")
        self.upTagButton = create_button("上移")  
        self.downTagButton = create_button("下移")
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
        apply_dialog_style(self)

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
        # 检查点击位置是否有项目
        item = self.categoryList.itemAt(position)
        if not item:
            return  # 如果右击的是空白区域，不显示菜单
        
        # 将点击的项目设为当前选中项
        self.categoryList.setCurrentItem(item)
        
        # 创建菜单
        menu = create_context_menu(self)
        category = item.text()
        

        editAction = menu.addAction("重命名")
        deleteAction = menu.addAction("删除")
        colorAction = menu.addAction("设置颜色")



        # 根据特殊类别状态动态设置文本
        specialText = "设为普通类别" if self.DictManage.query_category(category)[0][2] else "设为筛选类别"
        specialAction = menu.addAction(specialText)

        if category == "文件类型":
            editAction.setEnabled(False)
            deleteAction.setEnabled(False)
            specialAction.setEnabled(False)
        
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
            self.changeSpecialCategory()

    def showTagContextMenu(self, position):
        # 检查点击位置是否有项目
        item = self.tagList.itemAt(position)
        if not item or not self.current_category:
            return  # 如果右击的是空白区域或没有选择分类，不显示菜单
        
        # 将点击的项目设为当前选中项
        self.tagList.setCurrentItem(item)
        
        # 创建菜单
        menu = create_context_menu(self)
        removeAction = menu.addAction("移除标签")
        
        # 显示菜单并获取用户选择
        action = menu.exec_(self.tagList.mapToGlobal(position))
        
        # 处理用户选择
        if action == removeAction:
            self.removeTag()

    def onCategoryOrderChanged(self):
        # 当用户拖动完成后更新数据模型
        categories = [self.categoryList.item(i).text() for i in range(self.categoryList.count())]
        self.DictManage.reorder_categories(categories)
    
    def onTagOrderChanged(self):
        tags = [self.tagList.item(i).text() for i in range(self.tagList.count())]
        self.DictManage.reorder_tags(tags)

    def center(self):  
        # 获取屏幕几何信息  
        screen = QDesktopWidget().screenNumber(QDesktopWidget().cursor().pos())  
        center_point = QDesktopWidget().screenGeometry(screen).center()  
        
        # 获取窗口几何信息  
        frame_geometry = self.frameGeometry()  
        
        # 将窗口中心设置为屏幕中心  
        frame_geometry.moveCenter(center_point)  
        self.move(frame_geometry.topLeft())  

    def observer_update(self):  
        self.loadCategories()  
        # 恢复选择状态  
        if self.current_category:  
            items = self.categoryList.findItems(self.current_category, Qt.MatchExactly)  
            if items:  
                self.categoryList.setCurrentItem(items[0])

    def _on_dict_changed(self, action, payload):
        self.observer_update()

    def loadCategories(self):  
        self.categoryList.clear()
        rows = self.DictManage.query_category()
        categorys = [row[0] for row in rows]
        self.categoryList.addItems(categorys)

    def onCategoryChanged(self, current):  
        self.tagList.clear()
        if current:  
            if type(current) != str:  
                self.current_category = current.text()  
                current = self.current_category  
            else:  
                self.current_category = current  
            tags = self.DictManage.query('category', current, 'tag')
            self.tagList.addItems(tags)  
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
        category, ok = self._prompt_text_value("添加类别", "输入新类别名称:")  
        if ok and category:  
            rows = self.DictManage.query_category()
            categorys = [row[0] for row in rows]
            if category not in categorys:  
                self.DictManage.create_category(category)
            else:  
                QMessageBox.warning(self, "警告", "类别已存在！")  

    def editCategory(self):  
        currentItem = self.categoryList.currentItem()  
        if currentItem:  
            oldCategory = currentItem.text()  
            if oldCategory == "文件类型":
                QMessageBox.warning(self, "警告", "“文件类型” 类别不允许重命名！")
                return
            newCategory, ok = self._prompt_text_value("编辑类别", "输入新类别名称:", text=oldCategory)  
            if ok and newCategory:  
                rows = self.DictManage.query_category()
                categories = [row[0] for row in rows]
                if newCategory == oldCategory:
                    return
                if newCategory in categories:
                    QMessageBox.warning(self, "警告", "类别已存在！")
                    return
                self.DictManage.rename_category(oldCategory, newCategory)
                
                # 如果正在修改当前选中的类别，需要更新记录  
                if self.current_category == oldCategory:  
                    self.current_category = newCategory  

    def deleteCategory(self):  
        currentItem = self.categoryList.currentItem()  
        if currentItem:  
            category = currentItem.text()  
            if category == "文件类型":
                QMessageBox.warning(self, "警告", "“文件类型” 类别不允许删除！")
                return
            reply = QMessageBox.question(self, "确认删除", f"确定要删除类别 '{category}' 吗？",  
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)  
            if reply == QMessageBox.Yes:  
                self.DictManage.delete_category(category)

    def setColor(self):  
        currentItem = self.categoryList.currentItem()  
        if currentItem:  
            category = currentItem.text()  
            current_color = self.DictManage.query_category(category)[0][1]
            color = self._get_category_color_with_preview(category, current_color)
            if color.isValid():  
                self.DictManage.set_category_color(category, color.name())

    def _get_category_color_with_preview(self, category, initial_color):
        dialog = QColorDialog(QColor(initial_color), self)
        dialog.setWindowTitle(f"设置类别颜色 - {category}")
        dialog.setOption(QColorDialog.DontUseNativeDialog, True)

        preview_panel = self._create_color_preview_panel(category)
        layout = dialog.layout()
        if isinstance(layout, QVBoxLayout):
            original_items = []
            while layout.count():
                original_items.append(layout.takeAt(0))

            left_container = QWidget(dialog)
            left_layout = QVBoxLayout(left_container)
            left_layout.setContentsMargins(0, 0, 0, 0)
            left_layout.setSpacing(layout.spacing())

            for item in original_items:
                if item.widget():
                    left_layout.addWidget(item.widget())
                elif item.layout():
                    left_layout.addLayout(item.layout())
                elif item.spacerItem():
                    left_layout.addItem(item.spacerItem())

            content_row = QHBoxLayout()
            content_row.setContentsMargins(0, 0, 0, 0)
            content_row.setSpacing(14)
            content_row.addWidget(left_container, 1)
            content_row.addWidget(preview_panel)
            layout.addLayout(content_row)
        else:
            layout.addWidget(preview_panel, 0, layout.columnCount(), layout.rowCount(), 1)

        dialog.currentColorChanged.connect(lambda color: self._update_color_preview(color, category))
        self._update_color_preview(QColor(initial_color), category)

        if dialog.exec_() == QDialog.Accepted:
            return dialog.currentColor()
        return QColor()

    def _create_color_preview_panel(self, category):
        panel = QFrame(self)
        panel.setFixedWidth(180)
        panel.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                border-radius: 0px;
            }
            QLabel {
                background-color: transparent;
                border: none;
            }
        """)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("颜色预览", panel)
        title.setStyleSheet("font-weight: bold; color: #2f2f2f;")
        layout.addWidget(title)

        self.category_preview_chip = QLabel(category, panel)
        self.category_preview_hover_chip = QLabel(f"{category} hover", panel)
        self.category_preview_text = QLabel(category, panel)
        self.category_preview_text_hover = QLabel(f"{category} hover", panel)

        for chip in [self.category_preview_chip, self.category_preview_hover_chip]:
            chip.setAlignment(Qt.AlignCenter)
            chip.setMinimumHeight(32)
        for text_label in [self.category_preview_text, self.category_preview_text_hover]:
            text_label.setMinimumHeight(26)

        layout.addWidget(self.category_preview_chip)
        layout.addWidget(self.category_preview_hover_chip)
        layout.addWidget(self.category_preview_text)
        layout.addWidget(self.category_preview_text_hover)
        layout.addStretch()

        return panel

    def _update_color_preview(self, color, category):
        tokens = build_tag_color_tokens(color)

        self.category_preview_chip.setText(category)
        self.category_preview_chip.setStyleSheet(f"""
            QLabel {{
                background-color: {tokens['bg_normal'].name()};
                color: {tokens['text_on_bg_normal'].name()};
                border: 1px solid {tokens['border_normal'].name()};
                border-radius: 10px;
                padding: 5px 10px;
                font: 14px;
            }}
        """)

        self.category_preview_hover_chip.setText(f"{category} hover")
        self.category_preview_hover_chip.setStyleSheet(f"""
            QLabel {{
                background-color: {tokens['bg_hover'].name()};
                color: {tokens['text_on_bg_hover'].name()};
                border: 1px solid {tokens['border_hover'].name()};
                border-radius: 10px;
                padding: 5px 10px;
                font: 14px;
            }}
        """)

        self.category_preview_text.setText(category)
        self.category_preview_text.setStyleSheet(f"""
            QLabel {{
                color: {tokens['text_normal'].name()};
                font: 14px;
                padding: 2px 0px;
            }}
        """)

        self.category_preview_text_hover.setText(f"{category} hover")
        self.category_preview_text_hover.setStyleSheet(f"""
            QLabel {{
                color: {tokens['text_hover'].name()};
                font: 14px;
                padding: 2px 0px;
            }}
        """)

    def changeSpecialCategory(self):
        currentItem = self.categoryList.currentItem()
        if currentItem:
            category = currentItem.text()
            is_special = bool(self.DictManage.query_category(category)[0][2])
            self.DictManage.set_category_special(category, int(not is_special))

    def cherk_tag(self, tag):
        operators = [' ∩ ', ' ∪ ', "'", '(', ')']
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

    def _prompt_tag_name(self, existing_tags):
        dialog = QDialog(self)
        dialog.setWindowTitle("添加标签")
        apply_dialog_style(dialog)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("选择或输入新标签名称:", dialog))

        line_edit = QLineEdit(dialog)
        line_edit.setText("")
        apply_line_edit_style(line_edit)
        completer_model = QStringListModel(list(existing_tags), line_edit)
        completer = QCompleter(completer_model, line_edit)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        line_edit.setCompleter(completer)
        layout.addWidget(line_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        configure_dialog_button_box(button_box)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        line_edit.setFocus()

        if dialog.exec_() != QDialog.Accepted:
            return "", False

        return line_edit.text().strip(), True

    def _prompt_text_value(self, title, label_text, text=""):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setModal(True)
        dialog.setMinimumWidth(360)
        apply_dialog_style(dialog)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        label = QLabel(label_text, dialog)
        layout.addWidget(label)

        line_edit = QLineEdit(dialog)
        line_edit.setText(text)
        apply_line_edit_style(line_edit)
        layout.addWidget(line_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        configure_dialog_button_box(button_box)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        line_edit.selectAll()
        line_edit.setFocus()

        if dialog.exec_() != QDialog.Accepted:
            return "", False

        return line_edit.text().strip(), True

    def addTag(self):  
        currentCategory = self.categoryList.currentItem()  
        if currentCategory:  
            category = currentCategory.text()  
            existing_tags = self.DictManage.get_all_tags()

            tag, ok = self._prompt_tag_name(existing_tags)
            if ok and tag:  
                if tag not in existing_tags:
                    if not self.cherk_tag(tag):
                        return
                    self.DictManage.create_tag(tag)  
                if tag not in self.DictManage.query('category', category, 'tag'):  
                    self.current_tag = tag  # 记住新添加的标签  
                    self.DictManage.change_tag_category(tag, category)  
                    self.onCategoryChanged(category)

    def removeTag(self):  
        currentCategory = self.categoryList.currentItem()  
        currentTag = self.tagList.currentItem()  
        if currentCategory and currentTag:  
            category = currentCategory.text()  
            tag = currentTag.text()  
            if self.current_tag == tag:  
                self.current_tag = None  
            
            self.DictManage.change_tag_category(tag, '未分类')  
            self.onCategoryChanged(category)  

    def upMoveTag(self):
        currentTag = self.tagList.currentItem()
        if currentTag and self.current_category:
            current_index = self.tagList.row(currentTag)
            if current_index > 0:
                tags = [self.tagList.item(i).text() for i in range(self.tagList.count())]
                tags[current_index], tags[current_index-1] = tags[current_index-1], tags[current_index]
                self.DictManage.reorder_tags(tags)
                # 保持选中状态
                self.tagList.setCurrentRow(current_index-1)

    def downMoveTag(self):
        currentTag = self.tagList.currentItem()
        if currentTag and self.current_category:
            current_index = self.tagList.row(currentTag)
            if current_index < self.tagList.count() - 1:
                tags = [self.tagList.item(i).text() for i in range(self.tagList.count())]
                tags[current_index], tags[current_index+1] = tags[current_index+1], tags[current_index]
                self.DictManage.reorder_tags(tags)
                # 保持选中状态
                self.tagList.setCurrentRow(current_index+1)

    def upMoveCategory(self):  
        currentItem = self.categoryList.currentItem()  
        if currentItem:  
            current_index = self.categoryList.row(currentItem)
            if current_index > 0:
                categories = [self.categoryList.item(i).text() for i in range(self.categoryList.count())]
                categories[current_index], categories[current_index-1] = categories[current_index-1], categories[current_index]
                self.DictManage.reorder_categories(categories)
                # 保持选中状态
                self.categoryList.setCurrentRow(current_index-1)
    
    def downMoveCategory(self):  
        currentItem = self.categoryList.currentItem()  
        if currentItem:  
            current_index = self.categoryList.row(currentItem)
            if current_index < self.categoryList.count() - 1:
                categories = [self.categoryList.item(i).text() for i in range(self.categoryList.count())]
                categories[current_index], categories[current_index+1] = categories[current_index+1], categories[current_index]
                self.DictManage.reorder_categories(categories)
                # 保持选中状态
                self.categoryList.setCurrentRow(current_index+1)
