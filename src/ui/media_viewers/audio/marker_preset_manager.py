from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
                             QPushButton, QColorDialog, QMessageBox, QLabel, QLineEdit, QWidget,
                             QFormLayout)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor


class PresetEditDialog(QDialog):
    """预设编辑对话框 - 统一的创建/编辑界面"""

    def __init__(self, preset_data=None, parent=None):
        """
        初始化预设编辑对话框

        Args:
            preset_data: 编辑时传入预设数据，新建时为 None
            parent: 父窗口
        """
        super().__init__(parent)

        self.preset_data = preset_data
        self.selected_color = preset_data.get('color', '#3498db') if preset_data else '#3498db'

        self.setWindowTitle("编辑预设" if preset_data else "添加预设")
        self.setMinimumWidth(400)

        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # 表单布局
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        # 预设名称
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("例如：精彩片段")
        if self.preset_data:
            self.name_input.setText(self.preset_data.get('name', ''))
        self.name_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
            }
        """)
        form_layout.addRow("名称:", self.name_input)

        # 颜色选择
        color_layout = QHBoxLayout()

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(80, 35)
        self.update_color_button()
        self.color_btn.clicked.connect(self.choose_color)
        color_layout.addWidget(self.color_btn)

        color_label = QLabel("点击选择颜色")
        color_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        color_layout.addWidget(color_label)
        color_layout.addStretch()

        form_layout.addRow("颜色:", color_layout)

        layout.addLayout(form_layout)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumSize(100, 35)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        # 确认按钮
        confirm_btn = QPushButton("确定")
        confirm_btn.setMinimumSize(100, 35)
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        confirm_btn.clicked.connect(self.accept_data)
        btn_layout.addWidget(confirm_btn)

        layout.addLayout(btn_layout)

    def update_color_button(self):
        """更新颜色按钮显示"""
        self.color_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.selected_color};
                border: 2px solid #2c3e50;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                opacity: 0.8;
            }}
        """)

    def choose_color(self):
        """打开颜色选择器"""
        initial_color = QColor(self.selected_color)
        color = QColorDialog.getColor(initial_color, self, "选择预设颜色")

        if color.isValid():
            self.selected_color = color.name()
            self.update_color_button()

    def accept_data(self):
        """验证并接受数据"""
        name = self.name_input.text().strip()

        if not name:
            QMessageBox.warning(self, "提示", "请输入预设名称")
            self.name_input.setFocus()
            return

        self.accept()

    def get_data(self):
        """获取对话框数据"""
        return {
            'name': self.name_input.text().strip(),
            'color': self.selected_color
        }


class PresetListItemWidget(QWidget):
    """预设列表项组件 - 与 PresetSelector 统一的样式"""

    def __init__(self, preset_data, parent=None):
        """
        初始化列表项组件

        Args:
            preset_data: 预设数据 {'id', 'name', 'color', 'emoji', 'is_builtin'}
        """
        super().__init__(parent)

        self.preset_data = preset_data

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # 预设按钮（与 PresetSelector 样式一致）
        emoji_text = f"{preset_data['emoji']} " if preset_data.get('emoji') else ""
        self.preset_btn = QPushButton(f"{emoji_text}{preset_data['name']}")
        self.preset_btn.setMinimumHeight(35)
        self.preset_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {preset_data['color']};
                color: white;
                border: 2px solid transparent;
                border-radius: 5px;
                font-weight: bold;
                padding: 8px 15px;
                text-align: left;
            }}
            QPushButton:hover {{
                border: 2px solid #2c3e50;
            }}
        """)
        layout.addWidget(self.preset_btn, 1)

        # 内置标签
        if preset_data['is_builtin']:
            builtin_label = QLabel("内置")
            builtin_label.setStyleSheet("""
                QLabel {
                    color: #7f8c8d;
                    font-size: 11px;
                    background-color: #ecf0f1;
                    border-radius: 3px;
                    padding: 4px 8px;
                }
            """)
            builtin_label.setFixedHeight(25)
            layout.addWidget(builtin_label)


class MarkerPresetManager(QDialog):
    """标记预设管理对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("标记预设管理")
        self.resize(600, 450)

        from src.core.DictManage import DictManage
        self.dict_manage = DictManage()

        self.init_ui()
        self.load_presets()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # 标题说明
        title_label = QLabel("📋 管理标记预设类型")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title_label)

        info_label = QLabel("💡 内置预设不可删除和编辑，可拖动调整预设显示顺序")
        info_label.setStyleSheet("font-size: 11px; color: #7f8c8d; padding: 5px;")
        layout.addWidget(info_label)

        # 预设列表
        self.preset_list = QListWidget()
        self.preset_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 5px;
                background-color: white;
            }
            QListWidget::item {
                border: none;
                padding: 2px;
                margin: 2px 0;
            }
            QListWidget::item:selected {
                background-color: transparent;
            }
        """)

        # 启用拖放排序
        self.preset_list.setDragDropMode(QListWidget.InternalMove)
        self.preset_list.setDefaultDropAction(Qt.MoveAction)

        # 监听拖放完成事件
        self.preset_list.model().rowsMoved.connect(self.on_order_changed)

        # 双击编辑
        self.preset_list.itemDoubleClicked.connect(self.edit_preset_from_item)

        layout.addWidget(self.preset_list)

        # 按钮区域
        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("➕ 添加预设")
        self.add_btn.setMinimumHeight(35)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        self.add_btn.clicked.connect(self.add_preset)
        btn_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("✏️ 编辑预设")
        self.edit_btn.setMinimumHeight(35)
        self.edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.edit_btn.clicked.connect(self.edit_preset)
        btn_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("🗑️ 删除预设")
        self.delete_btn.setMinimumHeight(35)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.delete_btn.clicked.connect(self.delete_preset)
        btn_layout.addWidget(self.delete_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.setMinimumHeight(35)
        close_btn.setMinimumWidth(100)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def load_presets(self):
        """加载所有预设"""
        self.preset_list.clear()

        presets = self.dict_manage.dataAPI.get_all_marker_presets()

        for preset_id, name, color, emoji, order_index, is_builtin in presets:
            # 创建列表项
            item = QListWidgetItem()

            # 存储预设信息
            preset_data = {
                'id': preset_id,
                'name': name,
                'color': color,
                'emoji': emoji,
                'is_builtin': is_builtin,
                'order_index': order_index
            }
            item.setData(Qt.UserRole, preset_data)

            # 创建自定义 Widget
            widget = PresetListItemWidget(preset_data)

            # 设置列表项大小
            item.setSizeHint(widget.sizeHint())

            self.preset_list.addItem(item)
            self.preset_list.setItemWidget(item, widget)

    def add_preset(self):
        """添加新预设"""
        dialog = PresetEditDialog(parent=self)

        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()

            try:
                # 添加到数据库（emoji 留空）
                self.dict_manage.dataAPI.create_marker_preset(
                    data['name'],
                    data['color'],
                    ""  # emoji 为空字符串
                )

                # 刷新列表
                self.load_presets()

                QMessageBox.information(self, "成功", f"预设 '{data['name']}' 已添加")

            except Exception as e:
                QMessageBox.critical(self, "错误", f"添加预设失败:\n{str(e)}")

    def edit_preset_from_item(self, item):
        """从列表项双击编辑"""
        preset_data = item.data(Qt.UserRole)

        # 检查是否是内置预设
        if preset_data['is_builtin']:
            QMessageBox.warning(self, "警告", "内置预设不能编辑")
            return

        self._edit_preset_data(preset_data)

    def edit_preset(self):
        """编辑选中的预设"""
        current_item = self.preset_list.currentItem()

        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择一个预设")
            return

        preset_data = current_item.data(Qt.UserRole)

        # 检查是否是内置预设
        if preset_data['is_builtin']:
            QMessageBox.warning(self, "警告", "内置预设不能编辑")
            return

        self._edit_preset_data(preset_data)

    def _edit_preset_data(self, preset_data):
        """执行编辑预设操作"""
        dialog = PresetEditDialog(preset_data=preset_data, parent=self)

        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()

            try:
                # 更新数据库
                self.dict_manage.update_marker_preset(
                    preset_data['id'],
                    data['name'],
                    data['color']
                )

                # 刷新列表
                self.load_presets()

                QMessageBox.information(self, "成功", f"预设 '{data['name']}' 已更新")

            except Exception as e:
                QMessageBox.critical(self, "错误", f"更新预设失败:\n{str(e)}")

    def delete_preset(self):
        """删除选中的预设"""
        current_item = self.preset_list.currentItem()

        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择一个预设")
            return

        preset_data = current_item.data(Qt.UserRole)

        # 检查是否是内置预设
        if preset_data['is_builtin']:
            QMessageBox.warning(self, "警告", "内置预设不能删除")
            return

        # 确认删除
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除预设 '{preset_data['name']}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        try:
            # 从数据库删除
            self.dict_manage.dataAPI.delete_marker_preset(preset_data['id'])

            # 刷新列表
            self.load_presets()

            QMessageBox.information(self, "成功", "预设已删除")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除预设失败:\n{str(e)}")

    def on_order_changed(self):
        """拖动排序后更新数据库"""
        try:
            # 遍历列表项，更新 order_index
            for i in range(self.preset_list.count()):
                item = self.preset_list.item(i)
                preset_data = item.data(Qt.UserRole)

                # 更新数据库中的 order_index
                self.dict_manage.update_marker_preset_order(
                    preset_data['id'],
                    i
                )

                # 更新内存中的数据
                preset_data['order_index'] = i
                item.setData(Qt.UserRole, preset_data)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"更新排序失败:\n{str(e)}")


if __name__ == "__main__":
    """测试代码"""
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    dialog = MarkerPresetManager()
    dialog.exec_()

    sys.exit(app.exec_())
