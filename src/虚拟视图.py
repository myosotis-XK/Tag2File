from PyQt5.QtWidgets import QWidget, QApplication, QScrollBar, QLabel
from PyQt5.QtCore import QPoint, QSize, QRect, Qt, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen, QFontMetrics
import sys
import os
from datetime import datetime

from .utils import *
from .MultithreadedLoading import *
from .DictManage import *
from .ImageViewer import *
from .FileSelectionComponent import FileSelectionComponent
import re
import os
import subprocess
import shutil
from PyQt5.QtWidgets import QWidget, QScrollArea, QLabel, QMenu, QAction, QVBoxLayout, QRubberBand, \
QApplication, QTextEdit, QPushButton, QFileIconProvider, QMessageBox, QDialog, QHBoxLayout, QRadioButton
from PyQt5.QtGui import QPixmap, QFont, QIcon, QPainter, QCursor, QDragEnterEvent, QDropEvent, QFontMetrics
from PyQt5.QtCore import Qt, QThreadPool, QPoint, QRect, QTimer, QFileInfo
import time
from functools import partial
from datetime import datetime
import concurrent.futures
from typing import Optional

default_value = {
    'SMALL_SIZE': 50,  # 小图标大小
    'MEDIUM_SIZE': 100,  # 中等图标大小
    'LARGE_SIZE': 250,  # 大图标大小
    'SPACING_RATE': 0.05,  # 图标间距比例
    'current_image_size':'mid',  # 默认图标大小
    'current_sort_key': 'date',  # 默认排序方式
    'current_sort_order': 'desc',  # 默认排序顺序
    'WINDOW_FRAMES': 60,  # 窗口帧数
    'SCROLL_DISTANCE_PER_SECOND': 500,  # 每秒滚动像素长度
    'LABEL_SPACING': 5,  # 标签间距
    'label_name_size': 20  # 文件名高度
}
init_config_section('FileShowArea', default_value)

default_value = {
    'acceptFloder': 'False',  # 是否接受文件夹
}
init_config_section('TagFileShowArea', default_value)
save_config()

def updateStyle(label, new_style_property):
    try:
        # 如果没有 objectName，则临时设置为 "styledLabel"
        is_temp_name = False
        if not label.objectName():
            label.setObjectName("styledLabel")
            is_temp_name = True  # 标记为临时设置的名字

        # 获取当前的样式表
        current_style = label.styleSheet()
        selector_prefix = f"#{label.objectName()}"
        
        # 查找样式是否包含当前对象的选择器
        if selector_prefix in current_style:
            # 只提取选择器内的内容
            inner_style_pattern = re.compile(rf'{selector_prefix}\s*\{{(.*?)\}}', re.DOTALL)
            match = re.search(inner_style_pattern, current_style)
            
            if match:
                inner_style = match.group(1).strip()  # 获取当前选择器内的样式
                property_name = new_style_property.split(":")[0].strip()
                property_pattern = re.compile(rf'{property_name}:.*?;')
                
                # 如果属性存在，替换它；否则，添加新的样式
                if re.search(property_pattern, inner_style):
                    inner_style = re.sub(property_pattern, new_style_property, inner_style)
                else:
                    inner_style += " " + new_style_property

                # 更新完整的样式
                updated_style = re.sub(inner_style_pattern, f'{selector_prefix} {{ {inner_style} }}', current_style)
            else:
                updated_style = f"{selector_prefix} {{ {new_style_property} }}"
        else:
            # 如果没有选择器，则直接添加选择器和新样式
            updated_style = f"{current_style} {selector_prefix} {{ {new_style_property} }}"

        # 设置更新后的样式
        label.setStyleSheet(updated_style)

        # 如果是临时设置的名字，则删除它
        if is_temp_name:
            label.setObjectName("")
    except Exception as e:
        print(e)

from enum import Enum, auto
class FileState(Enum):
    NORMAL = auto()
    SELECTED = auto()
    HANG = auto()

class FileItem():
    def __init__(self, file_path, label_size, LABEL_INNER_SPACING):
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)

        self.LABEL_INNER_SPACING = LABEL_INNER_SPACING
        name_height = self.calculate_name_height(self.file_name, label_size, 3, QApplication.font())
        self.label_size = QRect(label_size, label_size + name_height)
        self.label_rect: Optional[QRect] = None

        if os.path.exists(file_path):
            file_size_bytes = os.path.getsize(file_path)
            self.file_size_bytes = file_size_bytes
            file_date_timestamp = os.path.getmtime(file_path)
            file_date = datetime.fromtimestamp(file_date_timestamp).strftime('%Y年%m月%d日，%H:%M:%S')
            self.file_date = file_date
        else:
            self.file_size_bytes = 0
            self.file_date = "文件不存在"

        self.pixmap: Optional[QPixmap] = None
        self.state = FileState.NORMAL

    # 计算文件名标签的高度
    def calculate_name_height(self, file_name, label_width, max_lines, font):
        font_metrics = QFontMetrics(font)
        single_line_height = font_metrics.lineSpacing()  # 每行高度
        text_width = font_metrics.horizontalAdvance(file_name)  # 文本总宽度
        num_lines = max(1, (text_width // label_width) + 1)  # 计算需要的行数
        total_lines = min(num_lines, max_lines)  # 限制最大行数
        name_height = total_lines * single_line_height  # 总高度
        return name_height + self.LABEL_INNER_SPACING



class VirtualViewport(QWidget):
    def __init__(self, file_paths=None):
        super().__init__()

        self._content_size = QSize(1000, 200000)  # 内容区改大点方便测试横向滚动
        self._offset = QPoint(0, 0)

        # 纵向滚动条
        self.v_scroll = QScrollBar(Qt.Vertical, self)
        self.v_scroll.valueChanged.connect(self.on_v_scroll)

        # 横向滚动条
        self.h_scroll = QScrollBar(Qt.Horizontal, self)
        self.h_scroll.valueChanged.connect(self.on_h_scroll)

        self.DictManage = DictManage()
        self.relation_graph = self.DictManage.relation_graph

        self.cache_dir = os.path.join(root, 'data', 'cache', 'image').replace('\\', '/')
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        # 读取配置文件
            # 图标大小
        self.SMALL_SIZE = config.getint('FileShowArea', 'SMALL_SIZE', fallback=50)
        self.MEDIUM_SIZE = config.getint('FileShowArea', 'MEDIUM_SIZE', fallback=100)
        self.LARGE_SIZE = config.getint('FileShowArea', 'LARGE_SIZE', fallback=250)
            # 默认设置
        self.current_image_size = config.get('FileShowArea', 'current_image_size', fallback='mid')  # 默认图标大小
        self.current_sort_key = config.get('FileShowArea', 'current_sort_key', fallback='date')  # 默认排序方式
        self.current_sort_order = config.get('FileShowArea', 'current_sort_order', fallback='desc')  # 默认排序顺序
            # 界面参数
        self.WINDOW_FRAMES = config.getint('FileShowArea', 'WINDOW_FRAMES', fallback=60)  # 界面帧数
        self.SCROLL_DISTANCE_PER_SECOND = config.getint('FileShowArea', 'SCROLL_DISTANCE_PER_SECOND', fallback=500)  # 每秒滚动像素长度
        self.SCROLL_DISTANCE_PER_FRAME = self.SCROLL_DISTANCE_PER_SECOND / self.WINDOW_FRAMES  # 每秒滚动像素长度
            # 布局标签相关
        self.SPACING_RATE = config.getfloat('FileShowArea', 'SPACING_RATE', fallback=0.05)  # 间隔比率
        self.LABEL_SPACING = config.getint('FileShowArea', 'LABEL_SPACING', fallback=5)  # 标签间距
        self.label_name_size = config.getint('FileShowArea', 'label_name_size', fallback=20)  # 文件名高度

        image_size_dict = {
            'small': self.SMALL_SIZE,
            'mid': self.MEDIUM_SIZE,
            'large': self.LARGE_SIZE
        }
        self.image_size = image_size_dict[self.current_image_size]
        self.LABEL_INNER_SPACING = int(self.image_size * self.SPACING_RATE) # 标签内间距
        self.label_size = self.image_size + 2*self.LABEL_INNER_SPACING #标签大小

        # 文件相关变量
        if file_paths is None:
            file_paths = []
        self.file_paths:list = file_paths # 窗口中的所有文件
        self.file_items:dict[str, FileItem] = dict()
        self.label_pool:list[QLabel] = []  # 空闲 QLabel 对象池
        self.active_labels:dict[str, QLabel] = dict()  # 当前屏幕可见，映射 file_path -> QLabel

        self.labels_rect:dict[tuple[int, int], tuple[QRect, str]] = dict()  # {(row, col):(label_rect, file_path)}
        self.visible_labels_keys:set = set()  # 可见label键
        self.select_labels_keys = set()  # 选中label键
        self.ctrl_select_labels_keys = set()  # ctrl选中label键
        self.now_select_label_key:Optional[str] = None  # 当前选中label_key
        self.now_hang_label:Optional[QLabel] = None  # 当前悬停label

        self.label_cache = {} # 文件label缓存
        self.image_cache = {self.SMALL_SIZE: {}, self.MEDIUM_SIZE: {}, self.LARGE_SIZE: {}}  # 缩略图缓存

        # 标记
        self.MousePress = False  # 鼠标按压标记
        self.ctrl_key_pressed = False  # 控制键标记
        self.mouseMove = False  # 鼠标移动标记

        # 子窗口
        self.child_widget = []
        self.image_viewers = []

        # 定时器
        self.auto_scroll_timer = QTimer(self)
        self.auto_scroll_timer.setInterval(round(1000/self.WINDOW_FRAMES))
        self.v_scroll.valueChanged.connect(self.on_scroll)

        # 线程池
        self.startLoadingImagesThreadpool = QThreadPool()
        self.threadpool = QThreadPool()
        self.starImageLoader = None
        self.threadpool.setMaxThreadCount(1)
        self.threadpool0 = QThreadPool()
        # self.threadpool0.setMaxThreadCount(4)
        
        self.initFileView()
        self.update_scrollbars()
        self.createFileLabels()
        self.setSortKeyAndOrder(self.current_sort_key, self.current_sort_order)

    def _createFileLabel(self, file_path):
        # 创建标签
        label = QLabel()
        label.setObjectName("file_label")

        # 创建显示图标的 QLabel
        icon_label = QLabel(label)
        icon_label.setObjectName("icon_label")

        # 创建显示文件名的 QLabel
        file_name_label = QLabel(label)
        file_name_label.setObjectName("file_name_label")

        label.icon = False
        label.file_path = file_path
        #绑定标签操作
        label.mouseDoubleClickEvent = partial(self.openFile, file_path=file_path) # 双击
        label.mousePressEvent = partial(self.onLabelLeftClick, label=label) # 左击
        # 右击菜单
        label.setContextMenuPolicy(Qt.CustomContextMenu) 
        label.customContextMenuRequested.connect(partial(self.showLabelMenu, label=label))
        # 绑定鼠标进入和离开的事件
        label.enterEvent = partial(self.setBackgroundColorOnEnter, label=label)
        label.leaveEvent = partial(self.resetBackgroundColorOnLeave, label=label)
        label.setParent(self.content_widget)
        label.hide()
        return label


    def update_scrollbars(self):
        w, h = self.width(), self.height()
        cw, ch = self._content_size.width(), self._content_size.height()

        self.v_scroll.setGeometry(w - 15, 0, 15, h - 15)
        self.v_scroll.setMinimum(0)
        self.v_scroll.setMaximum(max(0, ch - h))
        self.v_scroll.setPageStep(h)
        self.v_scroll.setValue(self._offset.y())

        self.h_scroll.setGeometry(0, h - 15, w - 15, 15)
        self.h_scroll.setMinimum(0)
        self.h_scroll.setMaximum(max(0, cw - w))
        self.h_scroll.setPageStep(w)
        self.h_scroll.setValue(self._offset.x())

    def resizeEvent(self, event):
        self.update_scrollbars()

    def on_v_scroll(self, value):
        self._offset.setY(value)
        self.update()

    def on_h_scroll(self, value):
        self._offset.setX(value)
        self.update()

    def wheelEvent(self, event):
        # 如果需要，按住Shift滚轮控制横向滚动示例：
        if event.modifiers() & Qt.ShiftModifier:
            delta_x = event.angleDelta().y() // 2
            new_val_x = self.h_scroll.value() - delta_x
            new_val_x = max(0, min(self.h_scroll.maximum(), new_val_x))
            self.h_scroll.setValue(new_val_x)
            return

        # 竖直滚轮默认控制纵向滚动
        delta = event.angleDelta().y() // 2
        new_val = self.v_scroll.value() - delta
        new_val = max(0, min(self.v_scroll.maximum(), new_val))
        self.v_scroll.setValue(new_val)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.rubber_band_origin = event.pos() + self._offset
            self.rubber_band_rect = QRect(self.rubber_band_origin, QSize())
            self.update()

    def mouseMoveEvent(self, event):
        if self.rubber_band_origin is not None:
            self.autoScroll(event.pos())
            current_pos = event.pos() + self._offset
            self.rubber_band_rect = QRect(self.rubber_band_origin, current_pos).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rubber_band_rect is not None:
            print(f"选中区域（内容坐标）：{self.rubber_band_rect}")
            self.rubber_band_origin = None
            self.rubber_band_rect = None
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.white)

        visible_rect = QRect(self._offset, self.size())
        self.updateLayout(painter, visible_rect)

        if self.rubber_band_rect is not None:
            pen = QPen(Qt.blue, 2, Qt.DashLine)
            painter.setPen(pen)
            brush = QColor(0, 0, 255, 50)
            painter.setBrush(brush)
            view_rect = QRect(
                self.rubber_band_rect.left() - self._offset.x(),
                self.rubber_band_rect.top() - self._offset.y(),
                self.rubber_band_rect.width(),
                self.rubber_band_rect.height()
            )
            painter.drawRect(view_rect)

    def sizeHint(self):
        return QSize(600, 400)
    
    #自动滚动
    def autoScroll(self, mouse_pos, auto=False):
        scroll_area_rect = self.rect()
        # 检查边缘位置和移动方向来决定是否滚动
        if mouse_pos.y() < scroll_area_rect.top():
            movement_scale = max(0.5, (mouse_pos.y() - scroll_area_rect.top())/50) # 计算滚动倍率
            move_value = round(movement_scale * self.SCROLL_DISTANCE_PER_FRAME) # 计算移动距离
            self.v_scroll.setValue(self.v_scroll.value() - move_value)  # 向上滚动
        elif mouse_pos.y() > scroll_area_rect.bottom():
            movement_scale = max(0.5, (mouse_pos.y() - scroll_area_rect.bottom())/50)
            move_value = round(movement_scale * self.SCROLL_DISTANCE_PER_FRAME)
            self.v_scroll.setValue(self.v_scroll.value() + move_value)  # 向下滚动

        if mouse_pos.x() < scroll_area_rect.left():
            movement_scale = max(0.5, (mouse_pos.x() - scroll_area_rect.left())/50)
            move_value = round(movement_scale * self.SCROLL_DISTANCE_PER_FRAME)
            self.h_scroll.setValue(self.h_scroll.value() - move_value)  # 向左滚动
        elif mouse_pos.x() > scroll_area_rect.right():
            movement_scale = max(0.5, (mouse_pos.x() - scroll_area_rect.right())/50)
            move_value = round(movement_scale * self.SCROLL_DISTANCE_PER_FRAME)
            self.h_scroll.setValue(self.h_scroll.value() + move_value)  # 向右滚动

        if not auto:
            try:
                self.auto_scroll_timer.timeout.disconnect()
            except TypeError:
                pass
            self.auto_scroll_timer.timeout.connect(lambda: self.autoScroll(mouse_pos, True))
            if not self.auto_scroll_timer.isActive():
                self.auto_scroll_timer.start()


    def updateLayout(self):
        area_width = self.width() - 4 * self.LABEL_SPACING
        num_columns = max(1, 1 + (area_width - self.label_size) // (self.label_size + self.LABEL_SPACING))
        total_files = len(self.file_paths)

        if num_columns > total_files or num_columns == 1:
            HORIZONTAL_SPACING = self.LABEL_SPACING
        else:
            HORIZONTAL_SPACING = round((area_width - num_columns * self.label_size) / num_columns)
        self.HORIZONTAL_SPACING = HORIZONTAL_SPACING

        self.labels_rect.clear()
        file_name_height_all = 0
        max_file_name_height = 0
        old_row = 0

        for idx, file_path in enumerate(self.file_paths):
            item = self.file_items[file_path]
            label_height = item.label_size.height()
            file_name_height = label_height - self.label_size

            if file_name_height > max_file_name_height:
                max_file_name_height = file_name_height

            row = idx // num_columns
            col = idx % num_columns

            if row != old_row:
                file_name_height_all += max_file_name_height
                max_file_name_height = 0
                old_row = row

            x = 4 * self.LABEL_SPACING + col * (self.label_size + HORIZONTAL_SPACING)
            y = 2 * self.LABEL_SPACING + row * (self.label_size + self.LABEL_SPACING) + file_name_height_all

            rect = QRect(QPoint(x, y), item.label_size)
            item.label_rect = rect
            self.labels_rect[(row, col)] = (rect, file_path)

        self.max_col = min(num_columns, total_files)
        self.max_row = row + 1

        file_name_height_all += max_file_name_height
        total_height = 4 * self.LABEL_SPACING + self.max_row * (self.label_size + self.LABEL_SPACING) + file_name_height_all
        self._content_size = QSize(self.width(), total_height)
        self.update_scrollbars()
        self.lazy_load()

    def lazy_load(self):
        # 当前视口区域，注意是内容坐标（加上偏移）
        visible_rect = QRect(self._offset, self.size())

        # 获取当前区域内需要显示的文件路径
        visible_file_paths = self.get_rect_label(visible_rect)

        # 隐藏并回收不在视口中的控件
        old_visible = set(self.active_labels.keys())
        no_longer_visible = old_visible - visible_file_paths
        for file_path in no_longer_visible:
            label = self.active_labels.pop(file_path)
            label.hide()
            self.label_pool.append(label)

        # 显示当前新进入视口的控件
        for file_path in visible_file_paths - old_visible:
            item = self.file_items[file_path]
            target_rect = item.label_rect
            if target_rect is None:
                continue

            if self.label_pool:
                label = self.label_pool.pop()
            else:
                # 新建一个带子控件的容器label
                label = self._createFileLabel(file_path)

            # 设置icon_label图标
            pixmap = item.pixmap if item.pixmap else QPixmap("默认图标路径")  # 或None
            label.findChild(QLabel, "icon_label").setPixmap(pixmap)

            # 设置文件名
            label.findChild(QLabel, "file_name_label").setText(item.file_name)

            label.resize(target_rect.size())
            label.move(target_rect.topLeft() - self._offset)
            label.show()

            self.active_labels[file_path] = label


   # 获取区域内label
    def get_rect_label(self, rect:QRect):
        labels_keys = set()
        if len(self.labels_rect) == 0:
            return labels_keys
        begin_pos = rect.topLeft()
        end_pos = rect.bottomRight()
        # 计算开始行
        begin_row = begin_pos.y() // (self.label_size + self.LABEL_SPACING)
        begin_row = max(0, min(begin_row, self.max_row-1))
            # 寻找鼠标下方离鼠标最近的底部所在行
        while begin_row != 0 and self.labels_rect.get((begin_row-1, 0))[0].bottomRight().y() > begin_pos.y():
            begin_row -= 1
            # 当处在最后一行之外，越过
        if self.labels_rect.get((begin_row, 0))[0].bottomRight().y() < begin_pos.y():
            begin_row += 1
        # 计算结束行
        end_row = end_pos.y() // (self.label_size + self.LABEL_SPACING)
        end_row = max(0, min(end_row, self.max_row-1))
            # 寻找鼠标下方离鼠标最近的顶部所在行 
        while end_row != 0 and self.labels_rect.get((end_row-1, 0))[0].topLeft().y() > end_pos.y():
            end_row -= 1
            # 当没处在最后一行之外时上移一行
        if self.labels_rect.get((end_row, 0))[0].topLeft().y() > end_pos.y():
            end_row -= 1

        # 计算开始列
        begin_col = begin_pos.x() // (self.label_size + self.LABEL_SPACING)
        begin_col = max(0, min(begin_col, self.max_col-1))
            # 寻找鼠标右方离鼠标最近的右边所在列
        while begin_col != 0 and self.labels_rect.get((0, begin_col-1))[0].bottomRight().x() > begin_pos.x():
            begin_col -= 1
            # 当处在最后一列之外，越过
        if self.labels_rect.get((0, begin_col))[0].bottomRight().x() < begin_pos.x():
            begin_col += 1
        # 计算结束列
        end_col = end_pos.x() // (self.label_size + self.LABEL_SPACING)
        end_col = max(0, min(end_col, self.max_col-1))
            # 寻找鼠标右方离鼠标最近的左边所在行列
        while end_col != 0 and self.labels_rect.get((0, end_col-1))[0].topLeft().x() > end_pos.x():
            end_col -= 1
            # 当没处在最后一列之外时左移一列
        if self.labels_rect.get((0, end_col))[0].topLeft().x() > end_pos.x():
            end_col -= 1

        # 选择标签
        for row in range(begin_row,end_row+1):
            for col in range(begin_col,end_col+1):
                label = self.labels_rect.get((row, col))
                if label:
                    labels_keys.add(label[1])
        return labels_keys




if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = VirtualViewport()
    w.resize(800, 600)
    w.show()
    sys.exit(app.exec_())
