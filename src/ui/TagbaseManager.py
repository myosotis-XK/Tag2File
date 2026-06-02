import os
import re
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QLabel,
    QFileDialog,
    QMessageBox,
    QLineEdit,
    QDialogButtonBox,
)
from PyQt5.QtCore import Qt
from src.utils import *
from src.core.DictManage import DictManage
from src.ui.components.style_utils import (
    apply_dialog_style,
    apply_line_edit_style,
    configure_dialog_button_box,
    create_button,
    create_context_menu,
)
from src.ui.ui_text import CommonText, TagbaseManagerText

class TagbaseManager(QDialog):
    def __init__(self, father=None):
        super().__init__()
        self.setWindowTitle(self.tr(TagbaseManagerText.WINDOW_TITLE))
        self.resize(600, 400)
        self.father = father
        self.DictManage = DictManage()
        # 获取当前标签库信息
        self.current_tagbase_name = config.get('DictManage', 'tagbase_name', fallback='tagbase')
        self.current_tagbase_path = config.get('DictManage', 'tagbase_folder', fallback='default_folder')
        if self.current_tagbase_path == 'default_folder':
            self.current_tagbase_path = self.DictManage.default_folder
        
        self.file_ext = ['.db', '.db-shm', '.db-wal']
        self.init_ui()
        self.load_tagbases()
        
    def init_ui(self):
        layout = QVBoxLayout()
        apply_dialog_style(self)
        
        # 当前标签库信息
        current_info_layout = QVBoxLayout()
        current_info_layout.addWidget(QLabel(self.tr(TagbaseManagerText.CURRENT_TAGBASE)))
        
        self.current_name_label = QLabel(f"{self.tr(TagbaseManagerText.NAME)}: {self.current_tagbase_name}")
        self.current_path_label = QLabel(f"{self.tr(TagbaseManagerText.PATH)}: {self.current_tagbase_path}")
        current_info_layout.addWidget(self.current_name_label)
        current_info_layout.addWidget(self.current_path_label)
        
        # 标签库列表 - 改为TreeWidget以支持多列
        self.tagbase_list = QTreeWidget()
        self.tagbase_list.setHeaderLabels([
            self.tr(TagbaseManagerText.NAME),
            self.tr(TagbaseManagerText.PATH),
            self.tr(TagbaseManagerText.SIZE),
        ])
        self.tagbase_list.setColumnWidth(0, 150)
        self.tagbase_list.setColumnWidth(1, 280)
        
        # 添加右键菜单
        self.tagbase_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tagbase_list.customContextMenuRequested.connect(self.show_context_menu)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.switch_btn = create_button(self.tr(CommonText.SWITCH))
        self.switch_btn.clicked.connect(self.switch_tagbase)
        
        self.create_btn = create_button(self.tr(CommonText.CREATE))
        self.create_btn.clicked.connect(self.create_tagbase)
        
        self.add_btn = create_button(self.tr(TagbaseManagerText.ADD_EXISTING_TAGBASE))
        self.add_btn.clicked.connect(self.add_existing_tagbase)
        
        button_layout.addWidget(self.switch_btn)
        button_layout.addWidget(self.create_btn)
        button_layout.addWidget(self.add_btn)
        
        layout.addLayout(current_info_layout)
        layout.addWidget(QLabel(self.tr(TagbaseManagerText.AVAILABLE_TAGBASES)))
        layout.addWidget(self.tagbase_list)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)

    def show_context_menu(self, position):
        """显示右键菜单"""
        # 检查点击位置是否有项目
        item = self.tagbase_list.itemAt(position)
        if not item:
            return  # 如果右击的是空白区域，不显示菜单
        
        # 将点击的项目设为当前选中项
        self.tagbase_list.setCurrentItem(item)
        
        # 创建菜单
        context_menu = create_context_menu(self)
        
        # 添加菜单项
        edit_action = context_menu.addAction(self.tr(CommonText.EDIT))
        delete_action = context_menu.addAction(self.tr(CommonText.DELETE))
        repair_action = context_menu.addAction(self.tr(TagbaseManagerText.REPAIR_FROM_BACKUP))
        
        # 获取用户选择的动作
        action = context_menu.exec_(self.tagbase_list.mapToGlobal(position))
        
        # 根据选择执行相应操作
        if action == edit_action:
            self.edit_tagbase()
        elif action == delete_action:
            self.delete_tagbase()
        elif action == repair_action:
            self.repair_from_backup()
    
    def get_file_size(self, path, name):
        """计算标签库文件的总大小"""
        try:
            size = 0
            full_path = os.path.join(path, name).replace('\\', '/')
                
            for ext in self.file_ext:
                file_path = full_path + ext
                if os.path.exists(file_path):
                    size += os.path.getsize(file_path)
            
            # 转换为易读格式
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size/1024:.2f} KB"
            elif size < 1024 * 1024 * 1024:
                return f"{size/(1024*1024):.2f} MB"
            else:
                return f"{size/(1024*1024*1024):.2f} GB"
        except Exception:
            return self.tr(TagbaseManagerText.UNKNOWN)
    
    def load_tagbases(self):
        """加载所有标签库"""
        self.tagbase_list.clear()
        
        self.tagbase_path_list = config.get('DictManage', 'tagbase_list', fallback='').split('|')
        if '' in self.tagbase_path_list:
            self.tagbase_path_list.remove('')
        
        # 查找默认路径的所有标签库
        if os.path.exists(self.DictManage.default_folder):
            for item in os.listdir(self.DictManage.default_folder):
                if item.endswith(self.file_ext[0]):
                    name = item[:-3]
                    tagbase_path = os.path.join(self.DictManage.default_folder, name).replace('\\', '/')
                    if tagbase_path not in self.tagbase_path_list:
                        self.tagbase_path_list.append(tagbase_path)
            
        self.tagbase_list.sortItems(0, Qt.AscendingOrder)

        # 保存更新后的标签库列表
        config.set('DictManage', 'tagbase_list', '|'.join(self.tagbase_path_list))
        save_config()

        for tagbase_path in self.tagbase_path_list:
            name = os.path.basename(tagbase_path)
            path_dir = os.path.dirname(tagbase_path)
            # 计算文件大小
            size_str = self.get_file_size(path_dir, name)
            # 添加到树形控件
            item = QTreeWidgetItem([name, path_dir, size_str])
            self.tagbase_list.addTopLevelItem(item)
    
    def _switch_tagbase(self, name, path):
        """切换当前标签库"""
        # 更新配置
        config.set('DictManage', 'tagbase_name', name)
        config.set('DictManage', 'tagbase_folder', path)
        save_config()
        self.father.MainFileShowArea.set_files([])
        self.DictManage.load_tagbase(os.path.join(path, name + self.file_ext[0]).replace('\\', '/'))
        # 更新显示
        self.current_tagbase_name = name
        self.current_tagbase_path = path
        self.current_name_label.setText(f"{self.tr(TagbaseManagerText.NAME)}: {name}")
        self.current_path_label.setText(f"{self.tr(TagbaseManagerText.PATH)}: {path}")

    def switch_tagbase(self):
        """切换当前标签库"""
        selected = self.tagbase_list.currentItem()
        if not selected:
            QMessageBox.warning(self, self.tr(CommonText.WARNING), self.tr(TagbaseManagerText.SELECT_TAGBASE_FIRST))
            return
            
        name = selected.text(0)  # 第一列：名称
        path = selected.text(1)  # 第二列：路径

        self._switch_tagbase(name, path)
        self.close()
    
    def create_tagbase(self):
        """创建新标签库"""
        name, ok = self._prompt_text_value(self.tr(TagbaseManagerText.CREATE_TAGBASE_TITLE), self.tr(TagbaseManagerText.ENTER_NEW_TAGBASE_NAME))
        if not ok or not name:
            return
        
        # 检查名称合法性
        invalid_chars = r'[\/:*?"<>|]'
        if re.search(invalid_chars, name):
            QMessageBox.warning(self, self.tr(CommonText.ERROR), self.tr(TagbaseManagerText.INVALID_NAME))
            return
        
        # 创建空标签库
        floder_path = os.path.join(root, 'data', 'tagbase').replace('\\', '/')
        tagbase_path = os.path.join(floder_path, name + self.file_ext[0]).replace('\\', '/')
        
        # 调用DictManage的create_tagbase方法
        self.DictManage.create_tagbase(tagbase_path)

        # 添加到配置
        self.tagbase_path_list.append(tagbase_path)  # 默认路径只存名称
        config.set('DictManage', 'tagbase_list', '|'.join(self.tagbase_path_list))
        save_config()
        
        # 更新列表
        self.load_tagbases()
        QMessageBox.information(self, self.tr(CommonText.SUCCESS), self.tr(TagbaseManagerText.CREATED_TAGBASE).format(name=name))
    
    def edit_tagbase(self):
        """编辑标签库名称和路径"""
        selected = self.tagbase_list.currentItem()
        if not selected:
            QMessageBox.warning(self, self.tr(CommonText.WARNING), self.tr(TagbaseManagerText.SELECT_TAGBASE_FIRST))
            return
            
        old_name = selected.text(0)  # 第一列：名称
        old_path = selected.text(1)  # 第二列：路径
        
        # 创建编辑对话框
        edit_dialog = QDialog(self)
        edit_dialog.setWindowTitle(self.tr(TagbaseManagerText.EDIT_TAGBASE_TITLE))
        edit_dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # 名称输入
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel(f"{self.tr(TagbaseManagerText.NAME)}:"))
        name_input = QLineEdit(old_name)
        name_layout.addWidget(name_input)
        layout.addLayout(name_layout)
        
        # 路径输入
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel(f"{self.tr(TagbaseManagerText.PATH)}:"))
        path_input = QLineEdit(old_path)
        path_input.setReadOnly(True)  # 路径通过浏览按钮选择
        path_layout.addWidget(path_input)
        
        browse_btn = create_button(self.tr(CommonText.BROWSE))

        def browse_path():
            path = QFileDialog.getExistingDirectory(edit_dialog, self.tr(TagbaseManagerText.SELECT_DIRECTORY), path_input.text())
            if path:
                path = normalize_path_lowercase(path)
                path_input.setText(path)
        
        browse_btn.clicked.connect(browse_path)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        ok_btn = create_button(self.tr(CommonText.CONFIRM))
        cancel_btn = create_button(self.tr(CommonText.CANCEL))
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        edit_dialog.setLayout(layout)
        
        # 连接按钮信号
        cancel_btn.clicked.connect(edit_dialog.reject)
        
        def confirm_edit():
            new_name = name_input.text()
            new_path = path_input.text()
            
            # 检查名称合法性
            invalid_chars = r'[\/:*?"<>|]'
            if not new_name:
                QMessageBox.warning(edit_dialog, self.tr(CommonText.ERROR), self.tr(TagbaseManagerText.NAME_EMPTY))
                return
            
            if re.search(invalid_chars, new_name):
                QMessageBox.warning(edit_dialog, self.tr(CommonText.ERROR), self.tr(TagbaseManagerText.INVALID_NAME))
                return

            # 只有名称或路径有变化时才进行修改
            if new_name != old_name or new_path != old_path:
                edit_dialog.accept()
            else:
                edit_dialog.reject()  # 没有变化，直接取消
        
        ok_btn.clicked.connect(confirm_edit)
        
        # 显示对话框
        if edit_dialog.exec_() != QDialog.Accepted:
            return  # 用户取消
        
        new_name = name_input.text()
        new_path = path_input.text()

        # 重命名文件
        try:
            old_full_path = os.path.join(old_path, old_name).replace('\\', '/')
            new_full_path = os.path.join(new_path, new_name).replace('\\', '/')
            
            # 重命名所有相关文件
            for ext in self.file_ext:
                src = old_full_path + ext
                if os.path.exists(src):
                    os.rename(src, new_full_path + ext)
            
            # 如果是当前标签库，更新配置
            if old_name == self.current_tagbase_name and old_path == self.current_tagbase_path:
                config.set('DictManage', 'tagbase_name', new_name)
                config.set('DictManage', 'tagbase_folder', new_path)
                self.current_tagbase_name = new_name
                self.current_tagbase_path = new_path
                self.current_name_label.setText(f"{self.tr(TagbaseManagerText.NAME)}: {new_name}")
                self.current_path_label.setText(f"{self.tr(TagbaseManagerText.PATH)}: {new_path}")
            
            self.tagbase_path_list = [new_full_path if p == old_full_path else p for p in self.tagbase_path_list]
            config.set('DictManage', 'tagbase_list', '|'.join(self.tagbase_path_list))
            save_config()
            
            # 更新列表
            self.load_tagbases()
            QMessageBox.information(self, self.tr(CommonText.SUCCESS), self.tr(TagbaseManagerText.EDIT_COMPLETED))
            
        except Exception as e:
            QMessageBox.critical(self, self.tr(CommonText.ERROR), self.tr(TagbaseManagerText.EDIT_FAILED).format(error=str(e)))
    
    def delete_tagbase(self):
        """删除标签库"""
        selected = self.tagbase_list.currentItem()
        if not selected:
            QMessageBox.warning(self, self.tr(CommonText.WARNING), self.tr(TagbaseManagerText.SELECT_TAGBASE_FIRST))
            return
            
        name = selected.text(0)  # 第一列：名称
        path = selected.text(1)  # 第二列：路径
        
        # 确认删除
        reply = QMessageBox.question(self, self.tr(TagbaseManagerText.CONFIRM_DELETE_TITLE), 
                                   self.tr(TagbaseManagerText.CONFIRM_DELETE_TAGBASE).format(name=name), 
                                   QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
            
        try:
            # 删除文件
            full_path = os.path.join(path, name).replace('\\', '/')
                
            for ext in self.file_ext:
                file_path = full_path + ext
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            self.tagbase_path_list.pop(self.tagbase_path_list.index(full_path))
            config.set('DictManage', 'tagbase_list', '|'.join(self.tagbase_path_list))
            # 如果是当前标签库，取tagbase_path_list的第一个作为当前标签库
            if name == self.current_tagbase_name and path == self.current_tagbase_path:
                if self.tagbase_path_list:
                    tagbase_path = self.tagbase_path_list[0]
                else:
                    tagbase_path = f'{self.DictManage.default_folder}/tagbase'
                    config.set('DictManage', 'tagbase_folder', self.DictManage.default_folder)
                    config.set('DictManage', 'tagbase_name', 'tagbase')
                    save_config()
                    tagbase_path = tagbase_path + self.file_ext[0]
                    self.DictManage.create_tagbase(tagbase_path)
                    self.DictManage.load_tagbase()

                tagbase_name = os.path.basename(tagbase_path)
                tagbase_path_dir = os.path.dirname(tagbase_path)
                self._switch_tagbase(tagbase_name, tagbase_path_dir)
            
            # 更新列表
            self.load_tagbases()
            QMessageBox.information(self, self.tr(CommonText.SUCCESS), self.tr(TagbaseManagerText.DELETE_COMPLETED))
            
        except Exception as e:
            QMessageBox.critical(self, self.tr(CommonText.ERROR), self.tr(TagbaseManagerText.DELETE_FAILED).format(error=str(e)))
    
    def add_existing_tagbase(self):
        """添加现有标签库"""
        # 打开文件对话框，让用户选择任意一种标签库文件
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr(TagbaseManagerText.SELECT_TAGBASE_FILE),
            self.DictManage.default_folder,
            self.tr(TagbaseManagerText.TAGBASE_FILE_FILTER).format(ext=self.file_ext[0]),
        )

        if not file_path:
            return  # 用户取消选择
        
        # 获取文件路径和基本名称（去掉扩展名）
        file_path = normalize_path_lowercase(file_path)
        dir_path = os.path.dirname(file_path)
        full_name = os.path.basename(file_path)
        
        # 处理可能的扩展名
        if full_name.endswith(self.file_ext[0]):
            file_name = full_name[:-3]
        else:
            file_name = full_name
        
        # 检查是否已存在
        tagbase_path = os.path.join(dir_path, file_name).replace('\\', '/')
        if tagbase_path in self.tagbase_path_list:
            QMessageBox.information(self, self.tr(CommonText.INFO), self.tr(TagbaseManagerText.TAGBASE_ALREADY_LISTED).format(file_name=file_name))
            return

        # 添加到标签库列表
        self.tagbase_path_list.append(tagbase_path)
        config.set('DictManage', 'tagbase_list', '|'.join(self.tagbase_path_list))
        save_config()
        
        # 刷新列表
        self.load_tagbases()
        
        QMessageBox.information(self, self.tr(CommonText.SUCCESS), self.tr(TagbaseManagerText.ADDED_TAGBASE).format(file_name=file_name))

    def _prompt_text_value(self, title, label_text, text=""):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setModal(True)
        dialog.setMinimumWidth(360)
        apply_dialog_style(dialog)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(QLabel(label_text, dialog))

        line_edit = QLineEdit(dialog)
        line_edit.setText(text)
        apply_line_edit_style(line_edit)
        layout.addWidget(line_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        configure_dialog_button_box(button_box, translate=self.tr)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        line_edit.selectAll()
        line_edit.setFocus()

        if dialog.exec_() != QDialog.Accepted:
            return "", False
        return line_edit.text().strip(), True
