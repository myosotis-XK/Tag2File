from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
                             QPushButton, QFrame, QLineEdit, QCompleter)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QEvent, QStringListModel
from .TagClass import InputTagLabel
from .core.DictManage import *

class HScrollArea(QScrollArea):
    def __init__(self):
        super().__init__()

    def wheelEvent(self, event):
        # 水平滚动
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - event.angleDelta().y() // 8)

class OperatorButton(QPushButton):  
    """表示操作符的按钮"""  
    def __init__(self, text):  
        super().__init__(text)  
        
        # 为括号类符号设置特殊样式（更窄）  
        if text in ['(', ')']:  
            self.setStyleSheet("""  
                QPushButton {  
                    background-color: #95a5a6;  
                    color: white;  
                    border-radius: 15px;  
                    padding: 2px 5px;  
                    margin: 2px;  
                    font-size: 16px;  
                    font-weight: bold;  
                    min-width: 20px;  
                    max-width: 25px;  
                }  
                QPushButton:hover {  
                    background-color: #7f8c8d;  
                }  
            """)  
            self.setFixedHeight(30)  
            self.setFixedWidth(25)  
        else:  
            self.setStyleSheet("""  
                QPushButton {  
                    background-color: #95a5a6;  
                    color: white;  
                    border-radius: 15px;  
                    padding: 5px 10px;  
                    margin: 2px;  
                    font-size: 16px;  
                    font-weight: bold;  
                }  
                QPushButton:hover {  
                    background-color: #7f8c8d;  
                }  
            """)  
            self.setFixedHeight(30)  
            self.setMinimumWidth(40)  

class CollapsibleLineEdit(QLineEdit):  
    """可收缩的输入框，当内容为空时显示为最小宽度"""
    backspaceEmpty = pyqtSignal()      # 信号：当输入框为空时按下退格键
    navigateLeft = pyqtSignal()        # 信号：向左移动
    navigateRight = pyqtSignal()       # 信号：向右移动
    
    def __init__(self):  
        super().__init__()  
        self.setStyleSheet("""  
            QLineEdit {  
                border: none;  
                padding: 0px;  
                background-color: transparent;  
            }  
        """)
        self.setCursor(Qt.IBeamCursor)
        
        # 默认宽度和展开宽度
        self.min_width = 3  # 刚好足够显示光标
        self.max_width = 100
        
        # 初始状态为收缩
        self.setFixedWidth(self.min_width)
        
        # 是否强制展开
        self.force_expanded = False
        
        # 连接textChanged信号来处理宽度调整
        self.textChanged.connect(self.adjust_width)
        
    def adjust_width(self, text):
        """根据文本内容调整宽度"""
        if not text and not self.force_expanded:
            self.setFixedWidth(self.min_width)
        else:
            self.setFixedWidth(self.max_width)
    
    def set_expanded(self, expanded, placeholder_text=""):
        """强制设置展开状态"""
        self.force_expanded = expanded
        if expanded:
            self.setPlaceholderText(placeholder_text)
            self.setFixedWidth(self.max_width)
        else:
            if not self.text():
                self.setPlaceholderText("")
                self.setFixedWidth(self.min_width)
    
    def keyPressEvent(self, event):  
        # 只有在输入框为空时，才响应左右导航键
        if not self.text():
            # 左箭头键处理
            if event.key() == Qt.Key_Left:
                self.navigateLeft.emit()
                return
                
            # 右箭头键处理    
            elif event.key() == Qt.Key_Right:
                self.navigateRight.emit()
                return
            
        # 当输入框为空且用户按下退格键时，发出信号  
        if event.key() == Qt.Key_Backspace and not self.text():  
            self.backspaceEmpty.emit()
            return
            
        # 其他按键正常处理
        super().keyPressEvent(event)

class EnhancedInputTagLabel(InputTagLabel):
    """增强版标签，支持左右侧点击检测"""
    leftClicked = pyqtSignal(object)   # 左侧点击信号
    rightClicked = pyqtSignal(object)  # 右侧点击信号
    centerClicked = pyqtSignal(object) # 中间点击信号
    
    def __init__(self, text, color=None, parent=None):
        super().__init__(text, color, parent)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 计算点击位置在标签内的相对位置
            width = self.width()
            click_x = event.pos().x()
            
            if click_x < width / 5:  # 左边1/4区域
                self.leftClicked.emit(self)
            elif click_x > width * 4 / 5:  # 右边1/4区域
                self.rightClicked.emit(self)
            else:  # 中间区域
                self.centerClicked.emit(self)

class TagInputWidget(QWidget, Observer):  
    """标签输入控件，支持点击位置插入，输入框默认隐藏"""
    def __init__(self, parent=None):  
        Observer.__init__(self)
        QWidget.__init__(self, parent)
        self.DictManage = DictManage()
        self.DictManage.add_observer(self)
        self.tag_library = self.DictManage.get_all_tags()
        # 操作符列表  
        self.operators = ['∩', '∪', "'", '(', ')']  
        
        # 标签和操作符列表
        self.elements: list[EnhancedInputTagLabel] = []
        
        # 当前输入框位置
        self.current_insert_position = -1  # -1表示在末尾
        
        self.init_ui()
        
        # 检查初始状态
        self.update_input_state()
        
    def init_ui(self):  
        self.setFixedHeight(80)
        self.layout = QVBoxLayout(self)  
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建输入区域容器  
        self.input_container = QFrame()  
        self.input_container.setStyleSheet("""  
            QFrame {  
                background-color: white;  
                border: 1px solid #ddd;
                padding: 0px;  
            }  
        """)
        self.input_container.setFixedHeight(40)

        # 输入区域的流式布局
        self.tag_scroll_area = HScrollArea()
        self.tag_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tag_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tag_scroll_area.setStyleSheet("""  
            QScrollArea {  
                border: none;  
                padding: 0px;  
                background-color: transparent;  
            }  
        """)
        self.tag_scroll_area.setWidgetResizable(True)
        
        # 标签容器
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("""  
            QWidget {  
                border: none;  
                padding: 0px;  
                background-color: transparent;  
            }  
        """)
        self.tag_scroll_area.setWidget(self.content_widget)
        self.tag_layout = QHBoxLayout(self.content_widget)  
        self.tag_layout.setContentsMargins(0, 0, 0, 0)  
        self.tag_layout.setSpacing(0)  # 标签之间没有间距
        self.tag_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        # 创建可收缩输入框
        self.input_edit = CollapsibleLineEdit()
        self.input_edit.setPlaceholderText("")  # 不显示占位符
        
        # 连接信号
        self.input_edit.backspaceEmpty.connect(self.remove_element_before_current)
        self.input_edit.navigateLeft.connect(self.move_input_left)
        self.input_edit.navigateRight.connect(self.move_input_right)
        
        # 设置自动完成  
        self.tag_model = QStringListModel(list(self.tag_library))
        self.completer = QCompleter(self.tag_model)
        popup = self.completer.popup()
        popup.setFixedWidth(200)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)  
        self.completer.setFilterMode(Qt.MatchContains)  
        self.input_edit.setCompleter(self.completer)  
        
        # 操作符按钮  
        self.operator_layout = QHBoxLayout()  
        for op in self.operators:  
            op_text = op.strip()  # 去除空格  
            btn = QPushButton(op_text)  
            btn.clicked.connect(lambda _, o=op: self.add_element(o))  
            btn.setStyleSheet("""  
                QPushButton {  
                    background-color: #95a5a6;  
                    color: white;  
                    border-radius: 12px;  
                    padding: 5px 10px;  
                    font-weight: bold;  
                }  
                QPushButton:hover {  
                    background-color: #7f8c8d;  
                }  
            """)  
            self.operator_layout.addWidget(btn)  
        
        # 输入框初始布局（默认在末尾）
        self.tag_layout.addWidget(self.input_edit)
        self.tag_layout.addStretch(1)
        self.current_insert_position = -1
        
        # 添加到容器  
        input_layout = QHBoxLayout(self.input_container)
        input_layout.addWidget(self.tag_scroll_area)
        
        # 将容器添加到主布局  
        self.layout.addWidget(self.input_container)  
        self.layout.addLayout(self.operator_layout)
        
        # 设置事件处理  
        self.input_edit.returnPressed.connect(self.add_tag_from_input)
        self.completer.activated.connect(self.add_tag_from_completer)
        
        # 安装事件过滤器，处理空白区域点击
        self.content_widget.installEventFilter(self)
        
        # 初始焦点
        self.input_edit.setFocus()

    def observer_update(self):
        self.tag_library = self.DictManage.get_all_tags()
        self.tag_model.setStringList(list(self.tag_library))

    def eventFilter(self, obj, event):
        """处理标签区域的点击事件"""
        if obj == self.content_widget and event.type() == QEvent.MouseButtonPress:
            # 只在点击空白区域时处理
            for element in self.elements:
                if element.geometry().contains(event.pos()):
                    return False  # 点击在标签上，不处理
                    
            # 确定插入位置
            position = self.get_position_at_point(event.pos())
            self.move_input_to_position(position)
            self.input_edit.setFocus()
            return True
            
        return super().eventFilter(obj, event)

    def move_input_left(self):
        """向左移动输入框"""
        if not self.elements:
            return
            
        if self.current_insert_position == -1:
            # 当前在末尾，移动到最后一个元素前
            self.move_input_to_position(len(self.elements))
        elif self.current_insert_position > 0:
            # 向左移动一个位置
            self.move_input_to_position(self.current_insert_position - 1)
        
        # 移动后确保输入框可见
        self.ensure_input_visible()
        
    def move_input_right(self):
        """向右移动输入框"""
        if not self.elements:
            return
            
        if self.current_insert_position < len(self.elements):
            # 向右移动一个位置
            self.move_input_to_position(self.current_insert_position + 1)
        elif self.current_insert_position == len(self.elements):
            # 当前在最后一个元素后，移动到末尾
            self.move_input_to_position(-1)
        
        # 移动后确保输入框可见
        self.ensure_input_visible()

    def update_input_state(self):
        """根据元素数量更新输入框状态"""
        if not self.elements:
            # 没有元素时展开输入框并显示提示
            self.input_edit.set_expanded(True, "输入标签...")
        else:
            # 有元素时恢复收缩行为
            self.input_edit.set_expanded(False)

    def get_position_at_point(self, pos):
        """获取点击位置对应的插入位置"""
        # 空列表情况
        if not self.elements:
            return 0
            
        # 检查是否点击在第一个元素前面
        first_element_left = self.elements[0].pos().x()
        if pos.x() <= first_element_left:
            return 0
            
        # 检查是否点击在最后一个元素后面
        last_element = self.elements[-1]
        last_element_right = last_element.pos().x() + last_element.width()
        if pos.x() >= last_element_right:
            return -1
        
        # 检查元素之间的位置
        for i in range(len(self.elements) - 1):
            element_right = self.elements[i].pos().x() + self.elements[i].width()
            next_element_left = self.elements[i+1].pos().x()
            
            if element_right <= pos.x() <= next_element_left:
                # 点击在两个元素之间
                return i + 1
        
        return -1  # 默认在末尾
    
    def move_input_to_position(self, position):
        """移动输入框到指定位置"""
        # 从当前位置移除输入框和弹簧
        self.tag_layout.removeWidget(self.input_edit)
        
        # 移除原有弹簧 (如果有)
        item = self.tag_layout.itemAt(self.tag_layout.count() - 1)
        if item and item.spacerItem():
            self.tag_layout.removeItem(item)
        
        # 放置到新位置
        if position == -1:  # 末尾
            self.tag_layout.addWidget(self.input_edit)
        else:
            self.tag_layout.insertWidget(position, self.input_edit)
        
        # 重新添加弹簧
        self.tag_layout.addStretch(1)
        
        self.current_insert_position = position
        
        # 清空输入框内容（保持收缩状态）
        self.input_edit.clear()
        
        # 确保输入框可见
        QTimer.singleShot(10, lambda: self.ensure_input_visible())
    
    def ensure_input_visible(self):
        """确保输入框在可视区域内"""
        self.tag_scroll_area.ensureWidgetVisible(self.input_edit, 50, 0)
    
    def create_enhanced_tag(self, text, color):
        """创建增强版标签"""
        tag = EnhancedInputTagLabel(text, color, self.content_widget)
        
        # 连接标签的点击信号
        tag.leftClicked.connect(lambda t: self.handle_tag_left_clicked(t))
        tag.rightClicked.connect(lambda t: self.handle_tag_right_clicked(t))
        tag.centerClicked.connect(lambda t: self.remove_element(t))
        
        return tag
    
    def handle_tag_left_clicked(self, tag):
        """处理标签左侧点击事件"""
        index = self.elements.index(tag)
        self.move_input_to_position(index)
        self.input_edit.setFocus()
    
    def handle_tag_right_clicked(self, tag):
        """处理标签右侧点击事件"""
        index = self.elements.index(tag)
        self.move_input_to_position(index + 1)
        self.input_edit.setFocus()
    
    def add_tag_from_input(self):
        """从输入框添加标签"""
        if self.completer and self.completer.popup().isVisible():
            current_index = self.completer.popup().currentIndex()
            if current_index.isValid():  
                # 如果当前补全框有选中的项，说明是QCompleter的回车，忽略
                return  
                
        text = self.input_edit.text().strip()  
        
        # 检查是否是有效标签  
        if text in self.tag_library or text in self.operators:  
            self.add_element(text)  
            self.input_edit.clear() 
    
    def add_tag_from_completer(self, text):  
        """当从自动完成下拉框中选择标签时调用"""  
        if text in self.tag_library:
            self.add_element(text)
            QTimer.singleShot(0, self.input_edit.clear)
    
    def add_element(self, text):  
        """添加元素到当前输入框位置"""  
        try:
            if text == "'":
                if len(self.elements) == 0 or self.current_insert_position == 0:
                    color = 'gray'
                if self.current_insert_position != -1:
                    element_index = self.current_insert_position - 1
                else:
                    element_index = -1
                element = self.elements[element_index]
                color = element.color
            elif text in self.operators:
                color = 'gray'
            else:
                category = self.DictManage.query('tag', text, 'category')
                row = self.DictManage.query_category(category)[0]
                color = row[1]
        except:
            color = 'gray'
        
        # 创建标签
        tag = self.create_enhanced_tag(text, color)
        
        # 临时移除输入框
        self.tag_layout.removeWidget(self.input_edit)
        # 移除原有弹簧
        item = self.tag_layout.itemAt(self.tag_layout.count() - 1)
        if item and item.spacerItem():
            self.tag_layout.removeItem(item)
        
        # 在当前位置添加标签
        if self.current_insert_position == -1:
            # 在末尾添加
            self.tag_layout.addWidget(tag)
            self.elements.append(tag)
        else:
            # 在指定位置添加
            self.tag_layout.insertWidget(self.current_insert_position, tag)
            self.elements.insert(self.current_insert_position, tag)
            # 更新插入位置
            self.current_insert_position += 1
            
        # 重新添加输入框在当前位置
        if self.current_insert_position == -1:
            self.tag_layout.addWidget(self.input_edit)
        else:
            self.tag_layout.insertWidget(self.current_insert_position, self.input_edit)
            
        # 添加弹簧
        self.tag_layout.addStretch(1)

        # 清空输入框（保持收缩状态）
        self.input_edit.clear()
        self.input_edit.setFocus()
        self.ensure_input_visible()
        self.update_input_state()
    
    def remove_element(self, element):  
        """删除指定元素（标签或操作符）"""  
        if element in self.elements:
            index = self.elements.index(element)
            
            # 更新插入位置
            if self.current_insert_position > index:
                self.current_insert_position -= 1
            elif self.current_insert_position == -1 and index == len(self.elements) - 1:
                # 如果删除的是最后一个元素且输入框在末尾，保持输入框在末尾
                self.current_insert_position = -1
                
            # 从列表和布局中移除
            self.elements.remove(element)  
            self.tag_layout.removeWidget(element)  
            element.deleteLater()
            
            self.input_edit.setFocus()
        self.update_input_state()
    
    def remove_element_before_current(self):  
        """当输入框为空且按下退格键时，删除输入框前的元素"""
        if not self.elements:
            return
            
        if self.current_insert_position == -1 and self.elements:
            # 输入框在末尾，删除最后一个元素
            self.remove_element(self.elements[-1])
        elif self.current_insert_position > 0:
            # 删除输入框前的元素
            self.remove_element(self.elements[self.current_insert_position - 1])
    
    def clear(self):  
        """清除所有标签和操作符"""  
        # 临时移除输入框
        self.tag_layout.removeWidget(self.input_edit)
        
        # 移除原有弹簧
        item = self.tag_layout.itemAt(self.tag_layout.count() - 1)
        if item and item.spacerItem():
            self.tag_layout.removeItem(item)

        for element in self.elements[:]:
            self.tag_layout.removeWidget(element)  
            element.deleteLater()
        
        self.elements = []
        
        # 重新添加输入框在末尾
        self.tag_layout.addWidget(self.input_edit)
        self.tag_layout.addStretch(1)
        self.current_insert_position = -1

        # 清空输入框（保持收缩状态）
        self.input_edit.clear()
        self.input_edit.setFocus()
        self.update_input_state()
    
    def get_query(self):  
        """获取完整查询表达式"""  
        return ''.join([element.text for element in self.elements])