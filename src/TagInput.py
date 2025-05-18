from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
                             QPushButton, QFrame, QLineEdit, QCompleter)  
from PyQt5.QtCore import Qt, pyqtSignal, QTimer 
from .TagClass import InputTagLabel

class HScrollArea(QScrollArea):
    def __init__(self):
        super().__init__()

    def wheelEvent(self, event):
        # 判断是水平滚动
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
                    padding: 2px 5px;  /* 更窄的内边距 */  
                    margin: 2px;  
                    font-size: 16px;  
                    font-weight: bold;  
                    min-width: 20px;  /* 减小最小宽度 */  
                    max-width: 25px;  /* 限制最大宽度 */  
                }  
                QPushButton:hover {  
                    background-color: #7f8c8d;  
                }  
            """)  
            self.setFixedHeight(30)  
            self.setFixedWidth(25)  # 固定宽度更窄  
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

# 自定义输入框类，处理退格键  
class TagInputLineEdit(QLineEdit):  
    backspaceEmpty = pyqtSignal()  # 信号：当输入框为空时按下退格键  
    
    def __init__(self):  
        super().__init__()  
        
    def keyPressEvent(self, event):  
        # 当输入框为空且用户按下退格键时，发出信号  
        if event.key() == Qt.Key_Backspace and not self.text():  
            self.backspaceEmpty.emit()  
        else:  
            super().keyPressEvent(event)  

class TagInputWidget(QWidget):  
    """标签输入控件"""  
    
    def __init__(self, relation_graph, parent=None):  
        super().__init__(parent)  
        
        # 预定义的标签库
        self.relation_graph = relation_graph 
        self.tag_library = self.relation_graph['tag'].keys()
        
        # 操作符列表  
        self.operators = [' ∩ ', ' ∪ ', "'", '(', ')']  
        
        self.init_ui()  
        
    def init_ui(self):  
        self.setFixedHeight(70)
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
        # 输入区域的流式布局
        self.tag_scroll_area = HScrollArea()
        self.tag_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # 隐藏水平滚动条
        self.tag_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tag_scroll_area.setStyleSheet("""  
            QScrollArea {  
                border: none;  
                padding: 0px;  
                background-color: transparent;  
            }  
        """)
        self.tag_scroll_area.setWidgetResizable(True)
        content_widget = QWidget()
        content_widget.setStyleSheet("""  
            QWidget {  
                border: none;  
                padding: 0px;  
                background-color: transparent;  
            }  
        """) 
        self.tag_scroll_area.setWidget(content_widget)
        self.tag_layout = QHBoxLayout(content_widget)  
        self.tag_layout.setContentsMargins(0, 0, 0, 0)  
        self.tag_layout.setSpacing(0)  
        self.tag_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  
        
        # 使用自定义输入框  
        self.input_edit = TagInputLineEdit()
        self.input_edit.setPlaceholderText("输入标签")
        # self.input_edit.setFixedHeight(30)
        self.input_edit.setStyleSheet("""  
            QLineEdit {  
                border: none;  
                padding: 0px;  
                background-color: transparent;  
            }  
        """)  
        
        # 连接退格键信号  
        self.input_edit.backspaceEmpty.connect(self.remove_last_element)  
        
        # 设置自动完成  
        self.completer = QCompleter(self.tag_library)  
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
            btn.clicked.connect(lambda _, o=op: self.add_operator(o))  
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
        
        # 添加到标签布局  
        input_layout = QHBoxLayout(self.input_container)
        input_layout.addWidget(self.input_edit, 1)
        input_layout.addWidget(self.tag_scroll_area, 3)
        
        # 将所有组件添加到主布局  
        self.layout.addWidget(self.input_container)  
        self.layout.addLayout(self.operator_layout)
        
        # 设置事件处理  
        self.input_edit.returnPressed.connect(self.add_tag_from_input)
        
        # 手动连接completer的activated信号  
        self.completer.activated.connect(self.add_tag_from_completer) 
        
        # 标签和操作符列表  
        self.elements = []  
    
    def add_tag_from_input(self):
        """从输入框添加标签"""
        if self.completer and self.completer.popup().isVisible():
            current_index = self.completer.popup().currentIndex()
            if current_index.isValid():  
                # 如果当前补全框有选中的项，说明是QCompleter的回车，忽略
                return  
        text = self.input_edit.text().strip()  
        
        # 检查是否是有效标签  
        if text in self.tag_library:  
            self.add_tag(text)  
            self.input_edit.clear()  
        elif text in [op.strip() for op in self.operators]:  
            self.add_operator(' ' + text + ' ' if text in ['∩', '∪'] else text)  
            self.input_edit.clear()  
    
    def add_tag_from_completer(self, text):  
        """当从自动完成下拉框中选择标签时调用"""  
        if text in self.tag_library:
            self.add_tag(text)
            QTimer.singleShot(0, self.input_edit.clear)
    
    def add_tag(self, text):  
        """添加标签"""  
        # 创建标签按钮
        try:
            category = list(self.relation_graph['tag'][text]['category'])[0]
            color = self.relation_graph['category'][category]['tagColor']
        except:
            color = None
        tag = InputTagLabel(text, color, self.tag_scroll_area)
        tag.mousePressEvent = lambda event, tag=tag: self.remove_element(tag) if event.button() == Qt.LeftButton else None
        
        self.tag_layout.addWidget(tag)
        
        # 保存标签引用  
        self.elements.append(tag)  
        
        # 焦点回到输入框  
        self.input_edit.setFocus()  
    
    def add_operator(self, op_text):  
        """添加操作符"""  
        # 创建操作符按钮，特殊处理括号  
        stripped_text = op_text.strip()  
        op = InputTagLabel(stripped_text, color='gray')  # 使用OperatorButton中为括号定制的样式   
        op.mousePressEvent = lambda event, op=op: self.remove_element(op) if event.button() == Qt.LeftButton else None
        
        # 将操作符添加到布局 
        self.tag_layout.addWidget(op) 
        
        # 保存操作符引用  
        self.elements.append(op)  
        
        # 焦点回到输入框  
        self.input_edit.setFocus()  
    
    def remove_element(self, element):  
        """删除元素（标签或操作符）"""  
        if element in self.elements:  
            self.elements.remove(element)  
            self.tag_layout.removeWidget(element)  
            element.deleteLater()  
    
    def remove_last_element(self):  
        """当输入框为空且按下退格键时，删除最后一个元素"""  
        if self.elements:  
            last_element = self.elements[-1]  
            self.remove_element(last_element)  
    
    def clear(self):  
        """清除所有标签和操作符"""  
        for element in self.elements[:]:  # 使用副本进行迭代  
            self.remove_element(element)  
    
    def get_query(self):  
        """获取完整查询表达式"""  
        return ''.join([element.text for element in self.elements])  