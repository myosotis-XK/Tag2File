import re
from PyQt5.QtWidgets import QLabel, QTreeWidget
from PyQt5.QtCore import Qt, QRect, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPainter, QColor

class CategoryTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setIndentation(15)
        self.setAnimated(True)
        self.setStyleSheet("""
            QTreeWidget::item {
                border: none;
                padding: 2px;
                height: 25px;
            }
            QTreeWidget::item:hover {
                background-color: transparent;
            }
            QTreeWidget::item:selected {
                background-color: transparent;
                color: palette(text);
            }
        """)
        
        self.horizontalScrollBar().valueChanged.connect(self.onHorizontalScrollBarChange)

        # 信号连接
        self.clicked.connect(lambda index: self.adjustColumnWidth())
        self.expanded.connect(lambda index: self.adjustColumnWidth())
        self.collapsed.connect(lambda index: self.adjustColumnWidth())

        # 滚动条初始值
        self._is_adjusting = False
        self._last_scroll_position = 0

    def mousePressEvent(self, event):
        index = self.indexAt(event.pos())
        if index.isValid():
            item = self.itemAt(event.pos())
            if item and item.childCount() > 0:  # 如果是类别项（有子项）
                if event.pos().x() < self.indentation():  # 点击展开/折叠箭头
                    super().mousePressEvent(event)
                else:  # 点击类别本身
                    self.setCurrentItem(item)
                    if item.isExpanded():
                        self.collapseItem(item)
                    else:
                        self.expandItem(item)
            else:  # 如果是标签项
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def currentChanged(self, current, previous):
        super().currentChanged(current, previous)
        self.updateItemColor(self.itemFromIndex(current))
        self.updateItemColor(self.itemFromIndex(previous))

    def updateItemColor(self, item):
        if item:
            item.setForeground(0, self.palette().color(self.palette().Text))

    def adjustColumnWidth(self):
        """
        调整列宽使其根据内容自适应，并保持滚动条位置。
        """
        if self._is_adjusting:
            return  # 防止递归触发

        self._is_adjusting = True
        self._last_scroll_position = self.horizontalScrollBar().value()

        # 使用 QTimer 延迟调整，确保宽度调整完成后再同步滚动条
        QTimer.singleShot(0, self._applyColumnAdjustment)

    def _applyColumnAdjustment(self):
        """
        实际应用列宽调整的逻辑。
        """
        self.resizeColumnToContents(0)
        self.horizontalScrollBar().setValue(self._last_scroll_position)
        self._is_adjusting = False

    def onHorizontalScrollBarChange(self, value):
        """
        滚动条值发生变化时触发。
        """
        if self._is_adjusting:
            self.horizontalScrollBar().setValue(self._last_scroll_position)


class TagLabel(QLabel):
    def __init__(self, text, count, color=QColor(0, 120, 215), parent=None):
        super().__init__(parent)
        self.father = parent
        self.tag = text
        self.color = color
        self.count = self.format_count(count)
        self.setStyleSheet("border: none; padding: 0px; margin: 2px;")
        # 设置标签字体
        font = QFont("Verdana", 14)
        font.setStyleHint(QFont.SansSerif)
        self.setFont(font)

        font = QFont()
        font.setPointSize(16)
        self.setFont(font)
        
        self.hovered = False
        self.tag_width = 0
        self.setMouseTracking(True)

    def format_count(self, count):
        if count == '':
            return str(count)
        elif count >= 1000000:
            return f"{count/1000000:.1f}M"
        elif count >= 1000:
            return f"{count/1000:.1f}k"
        else:
            return str(count)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self.font())
        
        # 设置悬停时的颜色
        if self.hovered:
            painter.setPen(self.get_highlight_color())
        else:
            painter.setPen(self.color)
        
        # 绘制标签文本
        fm = painter.fontMetrics()
        y = (self.height() + fm.ascent() - fm.descent()) // 2
        painter.drawText(0, y, self.tag)

        # 绘制文件数量
        painter.setPen(QColor(140, 140, 140))
        count_text = f" {self.count}"
        painter.drawText(painter.fontMetrics().width(self.tag), y, count_text)

        # 更新标签文本宽度
        self.tag_width = painter.fontMetrics().width(self.tag)

    def get_highlight_color(self):
        r, g, b = self.color.red(), self.color.green(), self.color.blue()
        
        # 增加亮度
        r = min(r + 20 + (255 - r) // 3, 255)
        g = min(g + 20 + (255 - g) // 3, 255)
        b = min(b + 20 + (255 - b) // 3, 255)
        
        # 降低饱和度（向白色靠拢）
        r = r + (255 - r) // 16
        g = g + (255 - g) // 16
        b = b + (255 - b) // 16
        
        return QColor(r, g, b)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.x() <= self.tag_width:
            self.father.onTagClick(self.tag)

    def enterEvent(self, event):
        self.update_hover_state(event.pos())

    def leaveEvent(self, event):
        self.hovered = False
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def mouseMoveEvent(self, event):
        self.update_hover_state(event.pos())

    def update_hover_state(self, pos):
        was_hovered = self.hovered
        self.hovered = pos.x() <= self.tag_width
        
        if self.hovered:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        
        if was_hovered != self.hovered:
            self.update()

    def sizeHint(self):
        fm = self.fontMetrics()
        width = fm.width(self.tag + f" {self.count}") + 25
        height = fm.height()
        return QRect(0, 0, width, height).size()


class SpecialTagLabel(TagLabel):
    checkStateChanged = pyqtSignal(str, bool)  # 信号：标签名，是否选中

    def __init__(self, text, color, parent=None):
        super().__init__(text, '', color, parent)
        self.isChecked = True
        self.checkbox_size = 15  # 勾选框的大小
        self.checkbox_rect = QRect(0,0,0,0)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self.font())

        # 计算勾选框的位置，使其垂直居中
        checkbox_y = 3*(self.height() - self.checkbox_size) // 4
        self.checkbox_rect = QRect(2, checkbox_y, self.checkbox_size, self.checkbox_size)

        # 绘制勾选框
        painter.drawRect(self.checkbox_rect)
        if self.isChecked:
            painter.fillRect(self.checkbox_rect.adjusted(3, 3, -3, -3), QColor(0, 0, 0))

        # 设置悬停时的颜色
        if self.hovered:
            painter.setPen(self.get_highlight_color())
        else:
            painter.setPen(self.color)
        
        # 绘制标签文本，考虑勾选框的宽度
        checkbox_width = self.checkbox_size + 5  # 额外的5像素作为间距
        fm = painter.fontMetrics()
        y = (self.height() + fm.ascent() - fm.descent()) // 2
        painter.drawText(checkbox_width, y, self.tag)
        
        # 绘制文件数量（始终为黑色）
        painter.setPen(QColor(140, 140, 140))
        count_text = f" {self.count}"
        painter.drawText(checkbox_width + painter.fontMetrics().width(self.tag), y, count_text)

        # 更新标签文本宽度
        self.tag_width = painter.fontMetrics().width(self.tag) + checkbox_width
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.checkbox_rect.contains(event.pos()):
                # 切换勾选状态
                self.isChecked = not self.isChecked
                self.update()  # 重绘标签
                self.checkStateChanged.emit(self.tag, self.isChecked)
            elif event.x() > self.checkbox_rect.right() and event.x() <= self.tag_width:
                # 原有的标签点击行为
                self.father.onTagClick(self.tag)

    def update_hover_state(self, pos):
        was_hovered = self.hovered
        # 检查鼠标是否在文本区域（不包括勾选框）
        text_area_start = self.checkbox_rect.right() + 5  # 5像素的间距
        self.hovered = pos.x() > text_area_start and pos.x() <= self.tag_width
        if self.hovered:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        
        if was_hovered != self.hovered:
            self.update()

    def sizeHint(self):
        fm = self.fontMetrics()
        width = fm.width(self.tag) + self.checkbox_size + 30
        height = fm.height()
        return QRect(0, 0, width, height).size()

class InputTagLabel(QLabel):
    def __init__(self, text, color, parent=None, ):  
        super().__init__(text, parent)  
        self.text = text  
        # 从 color 生成背景色和边框色  
        self.color = QColor(color)  
        self._setup_ui()  
    
    def _setup_ui(self):  
        # 计算背景色和边框色  
        bg_color = self.color.name()  
        darker_color = QColor(self.color)  
        darker_color.setHsv(self.color.hue(), self.color.saturation(), int(self.color.value() * 0.7))  
        border_color = darker_color.name()  
        lighter_bg = self.color.lighter(110).name()  
        
        # 设置标签样式  
        self.setStyleSheet(f"""  
            QLabel {{  
                background-color: {bg_color};  
                color: #333333;  
                border: 1px solid {border_color};  
                padding: px 0px;
                font: 14px;  
            }}  
            QLabel:hover {{  
                background-color: {lighter_bg};  
                border-color: #c0c0c0;  
            }}  
        """)  
        self.setCursor(Qt.PointingHandCursor) 
    
    def wheelEvent(self, event):
        # 传递滚动事件给父级
        self.parent().wheelEvent(event)

from .utils import *
class Tag:
    def __init__(self, tag):
        self.tag = tag # 保存集合名字符串
        self.Complement = False
    # 重载集合交操作
    def __and__(self, other):
        if self.Complement == True and other.Complement == True: # A'∩B' = A'-B = (A∪B)'
            return (Tag(f"({self.tag} | {other.tag})")).Change_Complement()
        if self.Complement == True: # A'∩B = B-A
            return Tag(f"({other.tag} - {self.tag})")
        elif other.Complement == True: # A∩B' = A-B
            return Tag(f"({self.tag} - {other.tag})")
        else: # A∩B
            return Tag(f"({self.tag} & {other.tag})")

    # 重载集合并操作
    def __or__(self, other):
        if self.Complement and other.Complement:  # A'∪B' = (A∩B)'
            return (Tag(f"({self.tag} & {other.tag})")).Change_Complement()
        if self.Complement:  # A'∪B = (B-A)'
            return (Tag(f"({other.tag} - {self.tag})")).Change_Complement()
        elif other.Complement:  # A∪B' = (A-B)'
            return (Tag(f"({self.tag} - {other.tag})")).Change_Complement()
        else:  # A∪B
            return Tag(f"({self.tag} | {other.tag})")

    # 重载集合差操作
    def __sub__(self, other):
        if other.Complement:  # A-B' = A∩B
            return Tag(f"({self.tag} & {other.tag})")
        elif self.Complement:  # A'-B = (A∪B)'
            return (Tag(f"({self.tag} | {other.tag})")).Change_Complement()
        else:  # A-B
            return Tag(f"({self.tag} - {other.tag})")
        
    def __str__(self):
        operators = r'[|&\-\(\)]'
        expression = self.tag
        tokens = re.split(f'({operators})', expression)
        # 清理和处理标记
        cleaned_tokens = []
        for token in tokens:
            token = token.strip()
            if token:
                if token not in ['|', '&', '(', ')', "-"]:
                    # 处理集合名
                    cleaned_tokens.append(f"DictManage.query('tag', '{token}', 'file')")
                else:
                    cleaned_tokens.append(token)
        # 重建表达式
        final_expression = ''.join(cleaned_tokens)
        return final_expression

    def __repr__(self):
        return self.__str__()
    
    def Change_Complement(self):
        self.Complement = not self.Complement
        return self


def parse_set_expression(expression) -> Tag:
    # 定义运算符模式，包括补集
    operators = r'[∩∪\(\)\']'
    
    # 用于存储Tag实例的字典
    tag_dict = {}
    
    # 分割表达式
    tokens = re.split(f'({operators})', expression)
    # 清理和处理标记
    cleaned_tokens = []
    for token in tokens:
        token = token.strip()
        if token:
            if token not in ['∩', '∪', '(', ')', "'"]:
                # 处理集合名
                if token not in tag_dict:
                    tag_dict[token] = Tag(token)
                cleaned_tokens.append(f"tag_dict['{token}']")
            elif token == "'":
                # 处理补集
                cleaned_tokens.append(".Change_Complement()")
            else:
                cleaned_tokens.append('&' if token == '∩' else '|' if token == '∪' else token)
    # 重建表达式
    final_expression = ''.join(cleaned_tokens)
    try:
        result = eval(final_expression)

    except Exception as e:
        print(f"表达式解析错误: {e}")
        result = False
    return result

# 自定义表达式解析，不使用eval
# def parse_set_expression_stack(expression):
#     """
#     将集合表达式解析为 Tag 对象，支持 ∩ ∪ - ' () 
#     """
#     # 定义运算符优先级
#     precedence = {'-': 3, '∩': 2, '∪': 1, '(': 0}
    
#     # token化
#     token_pattern = r"[∩∪\-\(\)']|[A-Za-z_][A-Za-z0-9_]*"
#     tokens = re.findall(token_pattern, expression)
    
#     # 字典缓存 Tag 对象
#     tag_dict = {}
    
#     # 栈
#     op_stack = []
#     value_stack = []
    
#     def apply_operator(op):
#         """弹出 value_stack 顶两个元素，应用运算符，再压回栈"""
#         if op == "'":  # 补集
#             val = value_stack.pop()
#             value_stack.append(val.Change_Complement())
#         else:
#             right = value_stack.pop()
#             left = value_stack.pop()
#             if op == '∩':
#                 value_stack.append(left & right)
#             elif op == '∪':
#                 value_stack.append(left | right)
#             elif op == '-':
#                 value_stack.append(left - right)
    
#     for token in tokens:
#         if re.match(r"[A-Za-z_][A-Za-z0-9_]*", token):  # 集合名
#             if token not in tag_dict:
#                 tag_dict[token] = Tag(token)
#             value_stack.append(tag_dict[token])
#         elif token == '(':
#             op_stack.append(token)
#         elif token == ')':
#             while op_stack and op_stack[-1] != '(':
#                 apply_operator(op_stack.pop())
#             op_stack.pop()  # 弹出 '('
#         elif token == "'":  # 补集，优先级最高
#             apply_operator(token)
#         elif token in precedence:
#             while op_stack and precedence[op_stack[-1]] >= precedence[token]:
#                 apply_operator(op_stack.pop())
#             op_stack.append(token)
#         else:
#             raise ValueError(f"未知 token: {token}")
    
#     # 处理剩余操作符
#     while op_stack:
#         apply_operator(op_stack.pop())
    
#     if len(value_stack) != 1:
#         raise ValueError("表达式解析错误")
    
#     return value_stack[0]


# 获取tag对应文件路径
def get_tag_files(tag_expression: str, DictManage, special_tags_status: list[tuple[str, int]]=None) -> list[tuple[str, int, float]]:
    result_tag = parse_set_expression(tag_expression)
    if not result_tag:
        return False
    result_files: set[tuple[str, int, float]] = eval(str(result_tag))
    if result_tag.Complement: # 如果结果是补集，则取所有文件的补集
        all_files: set[tuple[str, int, float]] = DictManage.get_all_files()
        result_files = all_files - result_files
    # 处理特殊tag
    if special_tags_status is None:
        special_tags_status: list[tuple[str, int]] = DictManage.get_all_special_tags_status()
    for spcial_tag, ischecked in special_tags_status:
        if not ischecked:
            if spcial_tag in ["图片","视频","音频","其他"]:
                result_files = {file_item for file_item in result_files if get_file_type(file_item[0]) != spcial_tag}
            else:
                result_files = result_files - DictManage.query('tag', spcial_tag, 'file')

    return list(result_files)


if __name__ == "__main__":
    # 更多示例
    expressions = [
        # "Big Set1 ∩ (Small Set2 ∪ Medium Set3')",
        # "(集合A ∩ 集合B) ∪ 集合C'",
        # "H' ∪ (A ∩ (B ∪ C') ∩ (D ∩ E'))'"
    ]

    for expr in expressions:
        result = parse_set_expression(expr)
        print(f"表达式: {expr}")
        print(f"解析结果: {result.tag}")
        print(f"python表达式: {result}\n")