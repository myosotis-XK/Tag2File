from src.utils import format_file_size
from .media_viewers import MultiImageViewer

import os
import time
import sys 

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QScrollArea,
                             QWidget, QLabel, QPushButton, QRadioButton, QCheckBox, QMessageBox, QButtonGroup)
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import Qt, pyqtSignal

# ClickableLabel 类定义（保持不变）
class ClickableLabel(QLabel):
    clicked = pyqtSignal(str)
    double_clicked = pyqtSignal(str)

    def __init__(self, parent=None, file_path=None):
        super().__init__(parent)
        self.file_path = file_path

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.file_path:
                self.clicked.emit(self.file_path)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.file_path:
                self.double_clicked.emit(self.file_path)
        super().mouseDoubleClickEvent(event)

# FileSelectionComponent 类定义
class FileSelectionComponent(QDialog):
    result_selected = pyqtSignal(list)

    def __init__(self, parent=None, file_groups=None, selection_type='single',
                 image_size=200, group_titles=None, initial_selection_handler=None):
        super().__init__(parent)
        self.file_groups = file_groups if file_groups is not None else []
        self.selection_type = selection_type
        self.image_size = image_size
        self.group_titles = group_titles if group_titles is not None else []
        self.initial_selection_handler = initial_selection_handler
        
        self.group_selections_data = [] 
        self.radio_button_groups = []
        self.file_path_to_selection_widget = {}
        # 新增：存储每个组的“不选择”QRadioButton，即便它是隐藏的，也需要操作它
        self.no_selection_radio_buttons = [] 
        self.checkbox_groups = []

        self.image_viewers = []

        self._init_ui()
        self._populate_content()

    def _init_ui(self):
        self.setWindowTitle("文件选择")
        self.resize(800, 600)

        main_layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        button_layout = QHBoxLayout()
        confirm_button = QPushButton("确认")
        cancel_button = QPushButton("取消")
        button_layout.addWidget(confirm_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

        confirm_button.clicked.connect(self._on_confirm)
        cancel_button.clicked.connect(self.reject)

    def _populate_content(self):
        font = QFont()
        font.setFamily("Verdana")
        font.setStyleHint(QFont.SansSerif)

        if not self.file_groups:
            no_data_label = QLabel("没有可供选择的文件组。")
            no_data_label.setAlignment(Qt.AlignCenter)
            self.scroll_layout.addWidget(no_data_label)
            return

        for i, group_paths in enumerate(self.file_groups):
            current_group_selected_paths = []
            self.group_selections_data.append(current_group_selected_paths) 

            group_label_text = self.group_titles[i] if i < len(self.group_titles) else f"文件组 {i+1} (共 {len(group_paths)} 个文件)"
            group_label = QLabel(group_label_text)
            group_label.setStyleSheet("font-weight: bold; background-color: #f0f0f0; padding: 5px;")
            self.scroll_layout.addWidget(group_label)

            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setSpacing(10)
            layout.setAlignment(Qt.AlignLeft)

            button_group = None
            if self.selection_type == 'single':
                button_group = QButtonGroup(self)
                self.radio_button_groups.append(button_group)

                # --- 修改点 1: 创建并隐藏“不选择任何文件”选项 ---
                no_selection_widget = QRadioButton("不选择任何文件")
                no_selection_widget.setProperty("is_no_selection", True) 
                no_selection_widget.file_path = None 
                button_group.addButton(no_selection_widget)
                # 连接信号：当这个隐藏按钮被选中时，清空当前组的选择
                no_selection_widget.toggled.connect(
                    lambda checked, idx=i: self._on_radio_button_toggled(checked, idx, None)
                )
                self.no_selection_radio_buttons.append(no_selection_widget) # 存储以便后续操作
                no_selection_widget.hide() # 隐藏它！
                # 不再将它添加到布局中

            initial_selected_for_this_group = []
            if self.initial_selection_handler:
                try:
                    initial_selected_for_this_group = self.initial_selection_handler(group_paths)
                    if not isinstance(initial_selected_for_this_group, list):
                        initial_selected_for_this_group = []
                    initial_selected_for_this_group = [
                        p for p in initial_selected_for_this_group if p in group_paths
                    ]
                except Exception as e:
                    print(f"Error calling initial_selection_handler for group {i}: {e}")
                    initial_selected_for_this_group = []

            for j, file_path in enumerate(group_paths):
                selection_widget = self._add_file_item(layout, file_path, font, button_group, group_idx=i)
                if selection_widget:
                    if self.selection_type == 'single':
                        selection_widget.toggled.connect(
                            lambda checked, idx=i, path=file_path: \
                                self._on_radio_button_toggled(checked, idx, path)
                        )
                    else: # multiple
                        selection_widget.toggled.connect(
                            lambda checked, idx=i, path=file_path: self._on_checkbox_toggled(checked, idx, path)
                        )
                    
                    self.file_path_to_selection_widget[file_path] = selection_widget

                    # 应用初始选择
                    if file_path in initial_selected_for_this_group:
                        selection_widget.setChecked(True)
            
            # 如果是单选模式且没有文件被选中，则默认选中隐藏的“不选择”按钮
            if self.selection_type == 'single' and not initial_selected_for_this_group:
                 if no_selection_widget:
                    no_selection_widget.setChecked(True) # 确保默认是“不选择”状态
            
            layout.addStretch()
            self.scroll_layout.addWidget(container)

    def _add_file_item(self, parent_layout, file_path, font, button_group=None, group_idx=-1):
        file_widget = QWidget()
        file_layout = QVBoxLayout(file_widget)
        file_layout.setAlignment(Qt.AlignCenter)

        image_label = ClickableLabel(file_path=file_path)
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setFixedSize(self.image_size, self.image_size)
        
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(self.image_size, self.image_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            image_label.setPixmap(pixmap)
        else:
            image_label.setText("无法预览")
            image_label.setStyleSheet("color: #999; border: 1px solid #ccc; background-color: #f8f8f8;")

        display_info_text = ""
        if os.path.exists(file_path):
            file_info = os.stat(file_path)
            
            display_info_text += f"{file_path}\n"
            
            mod_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(file_info.st_mtime))
            display_info_text += f"{mod_time}\n"
            
            size_str = format_file_size(file_info.st_size)
            display_info_text += f"{size_str}"
        else:
            display_info_text = f"文件不存在:\n{file_path}"

        path_label = ClickableLabel(file_path=file_path)
        path_label.setText(display_info_text)
        path_label.setAlignment(Qt.AlignCenter)
        path_label.setStyleSheet("font-size: 11px; color: #666;")
        path_label.setWordWrap(True)
        path_label.setMaximumWidth(self.image_size + 50)

        # 连接 ClickableLabel 的信号
        image_label.clicked.connect(lambda path=file_path, idx=group_idx: self._toggle_selection_for_path(path, idx))
        path_label.clicked.connect(lambda path=file_path, idx=group_idx: self._toggle_selection_for_path(path, idx))
        image_label.double_clicked.connect(self._open_file_with_system)
        path_label.double_clicked.connect(self._open_file_with_system)

        selection_widget = None
        if self.selection_type == 'single':
            selection_widget = QRadioButton("选择")
            if button_group:
                button_group.addButton(selection_widget)
        else:
            selection_widget = QCheckBox("选中")
            selection_widget.setChecked(False)

        if selection_widget:
            selection_widget.file_path = file_path

        file_layout.addWidget(image_label)
        file_layout.addWidget(path_label)
        if selection_widget:
            file_layout.addWidget(selection_widget, alignment=Qt.AlignCenter)

        parent_layout.addWidget(file_widget)
        return selection_widget

    def _toggle_selection_for_path(self, file_path, group_idx):
        """
        根据文件路径和组索引切换对应选择控件的状态。
        在单选模式下：
        - 如果点击的是当前已选中的文件，则取消选择（等同于选中隐藏的“不选择”按钮）。
        - 否则，选中点击的文件。
        """
        if file_path is None: # 不应直接通过ClickableLabel点击到隐藏的“不选择”按钮
            return

        selection_widget = self.file_path_to_selection_widget.get(file_path)
        if selection_widget:
            if self.selection_type == 'single':
                current_selection = self.group_selections_data[group_idx]
                
                # --- 修改点 2: 判断是否已选中，并触发“不选择”或选中 ---
                if current_selection and current_selection[0] == file_path:
                    # 如果当前点击的文件就是已经选中的文件，则“取消选择”
                    no_selection_radio = self.no_selection_radio_buttons[group_idx]
                    no_selection_radio.setChecked(True) # 选中隐藏的“不选择”按钮
                else:
                    # 否则，选中点击的文件
                    selection_widget.setChecked(True)
            else: # multiple
                # 多选模式下，点击切换选中状态
                selection_widget.setChecked(not selection_widget.isChecked())

    def _open_file_with_system(self, file_path):
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "文件不存在", f"无法打开文件：\n{file_path}\n文件已不存在。")
            return

        supported_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp']
        ext = os.path.splitext(file_path)[1].lower()

        if ext in supported_formats:
            # 找到file_path所在的组
            group_file_list = None
            for group in self.file_groups:
                if file_path in group:
                    group_file_list = group
                    break

            if not group_file_list:
                QMessageBox.warning(self, "未找到文件组", f"文件未包含在任何文件组中：\n{file_path}")
                return

            image_viewer = MultiImageViewer()
            self.image_viewers.append(image_viewer)
            image_viewer.destroyed.connect(lambda: self.image_viewers.remove(image_viewer))

            image_viewer.load_image_files(group_file_list.copy(), file_path)
            image_viewer.show()

        else:
            try:
                os.startfile(file_path)
            except Exception as e:
                QMessageBox.critical(self, "打开文件失败", f"无法打开文件：\n{file_path}\n错误：{e}")

    def _on_radio_button_toggled(self, checked, group_idx, file_path):
        """
        处理 QRadioButton toggled 状态。
        file_path 为 None 表示是隐藏的“不选择任何文件”按钮。
        """
        if checked:
            if file_path is None: # 选中了隐藏的“不选择”按钮
                self.group_selections_data[group_idx] = [] # 清空当前组的选择
            else: # 选中了某个具体文件按钮
                self.group_selections_data[group_idx] = [file_path]
        else:
            # 当一个 QRadioButton 被取消选中时（因为它组里的另一个被选中了），
            # 如果取消选中的是当前在 group_selections_data 中的那个，则将其移除。
            # 这种情况通常发生在从一个文件切换到另一个文件，或从文件切换到“不选择”按钮。
            if file_path is not None and file_path in self.group_selections_data[group_idx]:
                self.group_selections_data[group_idx].remove(file_path)

    def _on_checkbox_toggled(self, checked, group_idx, file_path):
        if checked and file_path not in self.group_selections_data[group_idx]:
            self.group_selections_data[group_idx].append(file_path)
        elif not checked and file_path in self.group_selections_data[group_idx]:
            self.group_selections_data[group_idx].remove(file_path)

    def _on_confirm(self):
        self.result_selected.emit(self.group_selections_data)
        self.accept()


# --- 如何使用这个组件 ---
if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # --- 修复文件场景的初始选择处理函数 ---
    def repair_initial_selector(group_files_list):
        if group_files_list:
            return [group_files_list[0]]
        return []

    # --- 模拟第一段代码的修复文件场景 ---
    # 创建一些虚拟文件用于测试
    dummy_repair_files = [
        "temp_image_1.jpg", 
        "temp_image_2.png", 
        "temp_image_3.gif"
    ]
    for f in dummy_repair_files:
        with open(f, 'w') as temp_f:
            temp_f.write("dummy content for image file " * 100) # 增加一些内容让文件大小不为0
        # 模拟不同的修改时间
        if f == "temp_image_2.png":
            os.utime(f, (time.time() - 3600 * 5, time.time() - 3600 * 5)) # 5 hours ago
        elif f == "temp_image_3.gif":
            os.utime(f, (time.time() - 86400 * 2, time.time() - 86400 * 2)) # 2 days ago

    repair_file_groups_input = [
        [dummy_repair_files[1], dummy_repair_files[0]],
        [dummy_repair_files[2]],
        ["non_existent_file_repair.jpg", dummy_repair_files[0]] 
    ]

    repair_group_titles = [
        f"修复 'Doc_A.jpg'",
        f"修复 'Doc_B.png'",
        f"修复 'Doc_C.gif'"
    ]

    print("\n--- 修复文件选择组件示例 (增强交互) ---")
    repair_dialog = FileSelectionComponent(
        file_groups=repair_file_groups_input,
        selection_type='single',
        image_size=150,
        group_titles=repair_group_titles,
        initial_selection_handler=repair_initial_selector
    )

    def handle_repair_selection_pure(selected_groups_2d):
        print("确认修复选择的（候选）文件列表（二维格式）：")
        for i, group_selection in enumerate(selected_groups_2d):
            original_placeholder = repair_group_titles[i].replace("修复 '", "").replace("'", "")
            if group_selection:
                print(f"  原始文件: '{original_placeholder}' 建议修复为: '{group_selection[0]}'")
            else:
                print(f"  原始文件: '{original_placeholder}' 未选择修复文件。")

    repair_dialog.result_selected.connect(handle_repair_selection_pure)
    if repair_dialog.exec_() == QDialog.Accepted:
        print("修复对话框确认关闭。")
    else:
        print("修复对话框取消关闭。")


    # --- 重复文件场景的初始选择处理函数 ---
    def duplicate_initial_selector(group_files_list):
        if not group_files_list:
            return []
        
        file_mod_times = []
        for f_path in group_files_list:
            if os.path.exists(f_path):
                file_mod_times.append((f_path, os.path.getmtime(f_path)))
            else:
                file_mod_times.append((f_path, 0))

        file_mod_times.sort(key=lambda x: x[1], reverse=True) # Sort by modification time, latest first

        selected_to_delete = [item[0] for item in file_mod_times[1:]] # Select all but the latest
        return selected_to_delete


    # --- 模拟第二段代码的重复文件删除场景 ---
    dummy_duplicate_files = [
        "dup_image_A.jpg", "dup_image_B.jpg", "dup_image_C.jpg",
        "dup_doc_X.pdf", "dup_doc_Y.pdf"
    ]
    for f in dummy_duplicate_files:
        with open(f, 'w') as temp_f:
            temp_f.write("dummy content for doc " * 50)
        if f == "dup_image_A.jpg":
            os.utime(f, (time.time() - 7200, time.time() - 7200)) # 2 hours ago
        elif f == "dup_doc_Y.pdf":
            os.utime(f, (time.time() - 100, time.time() - 100)) # 100 seconds ago

    duplicate_file_groups_input = [
        [dummy_duplicate_files[0], dummy_duplicate_files[1], dummy_duplicate_files[2]],
        [dummy_duplicate_files[3], dummy_duplicate_files[4]],
        ["another_non_existent.txt"]
    ]
    
    duplicate_group_titles = [
        "重复组 (图片)",
        "重复组 (文档)",
        "重复组 (单文件)"
    ]

    print("\n--- 重复文件删除组件示例 (增强交互) ---")
    duplicate_dialog = FileSelectionComponent(
        file_groups=duplicate_file_groups_input,
        selection_type='multiple',
        image_size=200,
        group_titles=duplicate_group_titles,
        initial_selection_handler=duplicate_initial_selector
    )

    def handle_delete_selection_pure(selected_groups_2d):
        print("确认删除文件（外部逻辑处理，二维格式）：")
        for i, group_selection in enumerate(selected_groups_2d):
            print(f"  来自组 {i+1} 的选择: {group_selection}")
            if group_selection:
                for f in group_selection:
                    print(f"    - 准备删除文件: {f}")
            else:
                print("    - 该组没有选择任何文件删除。")

    duplicate_dialog.result_selected.connect(handle_delete_selection_pure)
    if duplicate_dialog.exec_() == QDialog.Accepted:
        print("重复文件对话框确认关闭。")
    else:
        print("重复文件对话框取消关闭。")

    # Clean up dummy files
    for f in dummy_repair_files + dummy_duplicate_files:
        if os.path.exists(f):
            os.remove(f)

    sys.exit(app.exec_())