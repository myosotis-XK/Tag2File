from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
                             QPushButton, QInputDialog, QColorDialog, QMessageBox, QLabel)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor


class MarkerPresetManager(QDialog):
    """标记预设管理对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("标记预设管理")
        self.resize(500, 400)

        from src.DictManage import DictManage
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

        info_label = QLabel("💡 内置预设不可删除，自定义预设可以随时添加或删除")
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
                padding: 8px;
                border-radius: 3px;
                margin: 2px;
            }
            QListWidget::item:hover {
                background-color: #ecf0f1;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)
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

            # 显示文本
            builtin_tag = " [内置]" if is_builtin else " [自定义]"
            emoji_text = f"{emoji} " if emoji else ""
            item.setText(f"{emoji_text}{name}{builtin_tag}")

            # 设置背景色为预设颜色的浅色版本
            item_color = QColor(color)
            item_color.setAlpha(30)
            item.setBackground(item_color)

            # 存储预设信息
            item.setData(Qt.UserRole, {
                'id': preset_id,
                'name': name,
                'color': color,
                'emoji': emoji,
                'is_builtin': is_builtin
            })

            self.preset_list.addItem(item)

    def add_preset(self):
        """添加新预设"""
        # 输入预设名称
        name, ok = QInputDialog.getText(
            self,
            "添加预设",
            "预设名称:"
        )

        if not ok or not name.strip():
            return

        name = name.strip()

        # 输入 emoji（可选）
        emoji, ok = QInputDialog.getText(
            self,
            "添加预设",
            "Emoji 图标（可选，留空跳过）:",
            text=""
        )

        if not ok:
            return

        emoji = emoji.strip()

        # 选择颜色
        color = QColorDialog.getColor(QColor("#3498db"), self, "选择预设颜色")

        if not color.isValid():
            return

        try:
            # 添加到数据库
            self.dict_manage.dataAPI.create_marker_preset(name, color.name(), emoji)

            # 刷新列表
            self.load_presets()

            QMessageBox.information(self, "成功", f"预设 '{name}' 已添加")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"添加预设失败:\n{str(e)}")

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


if __name__ == "__main__":
    """测试代码"""
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    dialog = MarkerPresetManager()
    dialog.exec_()

    sys.exit(app.exec_())
