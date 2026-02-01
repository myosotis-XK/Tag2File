from .utils import *
from .MultithreadedLoading import *
from .DictManage import *
from .ImageViewer import *
from .FileSelectionComponent import FileSelectionComponent
from .Iconsource import *
import os
import subprocess
import shutil
import random
from PyQt5.QtWidgets import QWidget, QScrollBar, QLabel, QMenu, QAction, QVBoxLayout, QRubberBand, \
QApplication, QTextEdit, QPushButton, QFileIconProvider, QMessageBox, QStyleOptionSlider, QInputDialog
from PyQt5.QtGui import QPixmap, QMovie, QFont, QIcon, QPainter, QCursor, QDragEnterEvent, QDropEvent, \
    QMouseEvent, QFontMetrics, QPalette, QColor
from PyQt5.QtCore import Qt, QThreadPool, QPoint, QRect, QSize, QTimer, QFileInfo
import time
from functools import partial
from datetime import datetime
from enum import Enum
from typing import Optional
import concurrent.futures
from natsort import natsort_keygen

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

from enum import Enum

class Border(Enum):
    NONE = "border: none;"
    BLUE = "border: 1px solid #99d1ff;"

class Background(Enum):
    TRANSPARENT = "background-color: transparent;"
    LIGHTBLUE = "background-color: #e5f3ff;"
    DARKBLUE = "background-color: #cde8ff;"

class FileItem():
    font_metrics = QFontMetrics(QApplication.font())
    single_line_height = font_metrics.lineSpacing()
    SPACING_RATE = config.getfloat('FileShowArea', 'SPACING_RATE', fallback=0.05)

    def __init__(self, file_path:str, file_size_bytes: int, file_date: float, label_width: int):
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)

        self.label_width = label_width
        self.label_pos = (0, 0)
        self.update_label_size()

        self.file_size_bytes = file_size_bytes
        self.file_date = file_date

        self.icon: bool = False
        self.icon_source: dict[str, IconSource] = None

        self.specifid = 0
        self.selected = 0
        self.hover = 0

        self.border = Border.NONE
        self.background = Background.TRANSPARENT

    def update_label_size(self, label_width: int=None):
        if label_width is None:
            label_width = self.label_width
        else:
            self.label_width = label_width
        self.name_height = self.calculate_name_height(self.file_name, label_width, 3)
        self.label_size = (label_width, label_width + self.name_height)

    # 计算文件名标签的高度
    def calculate_name_height(self, file_name: str, label_width: int, max_lines: int) -> int:
        text_width = self.font_metrics.horizontalAdvance(file_name)  # 文本总宽度
        num_lines = max(1, (text_width // (label_width-4)) + 1)  # 计算需要的行数
        total_lines = min(num_lines, max_lines)  # 限制最大行数
        name_height = total_lines * self.single_line_height  # 总高度
        return name_height + int(label_width*self.SPACING_RATE)
    
    def apply(self, label: QLabel, key='current'):
        icon = self.icon_source.get(key)
        if icon:
            icon.apply(label)


class FileShowArea(QWidget):
    file_status_map = {  # 指定, 选中, 悬停  specifid, selected, hover
        (0,0,0): (Border.NONE, Background.TRANSPARENT),
        (0,0,1): (Border.NONE, Background.LIGHTBLUE),
        (0,1,0): (Border.NONE, Background.DARKBLUE),
        (0,1,1): (Border.BLUE, Background.DARKBLUE),
        (1,0,0): (Border.BLUE, Background.TRANSPARENT),
        (1,0,1): (Border.BLUE, Background.LIGHTBLUE),
        (1,1,0): (Border.BLUE, Background.DARKBLUE),
        (1,1,1): (Border.BLUE, Background.DARKBLUE),
    }
    def __init__(self, file_paths: list=None):
        super().__init__()
        self.DictManage = DictManage()

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
        self.label_width: int = self.image_size + 2*self.LABEL_INNER_SPACING #标签大小

        # 文件相关变量
        if file_paths is None:
            file_paths = []
        self.file_paths: list = file_paths # 窗口中的所有文件
        self.file_items: dict[str, FileItem] = dict()
        self.file_items_cache: dict[str, FileItem] = dict()
        self.label_pool: list[QLabel] = []
        self.labels: dict[str, QLabel] = dict()
        self.labels_rect: list[list[tuple[tuple[int, int], tuple[int, int], str]]] = []  # [(row, col):(label_pos, label_size, file_path)]
        self.visible_labels_keys = set()  # 可见label键
        self.select_labels_keys = set()  # 选中label键
        self.ctrl_select_labels_keys = set()  # ctrl选中label键
        self.now_select_label_key: Optional[str] = None  # 当前选中label_key
        self.now_hang_file: Optional[str] = None  # 当前悬停label

        self.extension_icon: dict[str, dict[str, QPixmap]] = {self.SMALL_SIZE: {}, self.MEDIUM_SIZE: {}, self.LARGE_SIZE: {}}  # 缩略图缓存

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

        # 线程池
        self.startLoadingImagesThreadpool = QThreadPool()
        self.threadpool = QThreadPool()
        self.starImageLoader = None
        self.threadpool.setMaxThreadCount(1)
        self.threadpool0 = QThreadPool()
        # self.threadpool0.setMaxThreadCount(4)
        
        self.initFileView()
        self.update_scrollbars()
        file_meta_datas = [(file_path, 0, 0) for file_path in self.file_paths]
        self.createFileItem(file_meta_datas)
        self._sort_files()

    def initFileView(self):
        # 创建一个滚动区域
        self.setAutoFillBackground(True)
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(255, 255, 255))
        self.setPalette(palette)

        self._content_size = QSize(1000, 2000)
        self._offset = QPoint(0, 0)

        # 纵向滚动条
        self.v_scroll = QScrollBar(Qt.Vertical, self)
        self.v_scroll.setFixedWidth(15)
        self.v_scroll.valueChanged.connect(self.on_v_scroll)

        # 横向滚动条
        self.h_scroll = QScrollBar(Qt.Horizontal, self)
        self.h_scroll.setFixedHeight(15)
        self.h_scroll.valueChanged.connect(self.on_h_scroll)

        # 填充corner
        self.corner = QWidget(self)
        scrollbar = self.v_scroll
        # 获取背景槽颜色（滑槽 background）
        option = QStyleOptionSlider()
        scrollbar.initStyleOption(option)
        bg_color = scrollbar.style().standardPalette().color(QPalette.Button)
        self.corner.setStyleSheet(f"background-color: {bg_color.name()};")

        # 绑定鼠标事件
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu) 
        self.mousePressEvent = self.mousePressEvent
        self.mouseMoveEvent = self.mouseMoveEvent
        self.setMouseTracking(True)
        self.mouseReleaseEvent = self.mouseReleaseEvent

        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)  
        self.origin = QPoint()

    #——————————————————————重写方法————————————————————————

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updateLayout()

    def wheelEvent(self, event):
        delta = event.angleDelta()
        if delta.y() != 0:
            self.v_scroll.setValue(
                self.v_scroll.value() - int(delta.y() * 0.5)
            )

        if delta.x() != 0:
            self.h_scroll.setValue(
                self.h_scroll.value() - int(delta.x() * 0.5)
            )

    def closeEvent(self, event):
        # 清空图片加载任务
        while self.startLoadingImagesThreadpool.activeThreadCount() > 0:
            self.starImageLoader.runing = False
            time.sleep(0.1)
        self.threadpool.clear()
        self.threadpool0.clear()
        for widget in self.child_widget:
            widget.close()
        while self.threadpool.activeThreadCount() > 0:
            time.sleep(0.1)
        while self.threadpool0.activeThreadCount() > 0:
            time.sleep(0.1)
        # 调用父类的 closeEvent 以确保主窗口正常关闭
        for image_viewer in self.image_viewers:
            image_viewer.close()
        super().closeEvent(event)


    #——————————————————————基础功能————————————————————————

    # 改变显示文件
    def changeFile(self, file_meta_datas: list[tuple[str, int, float]]=None, recover=False):
        '''
        改变显示文件
        :param file_paths: 新的文件元数据列表
        :param recover: 是否恢复滚动条位置
        '''
        if file_meta_datas is None:
            file_meta_datas = []

        file_paths = [file_meta_data[0] for file_meta_data in file_meta_datas]

        # 线程处理
        while self.startLoadingImagesThreadpool.activeThreadCount() > 0:
            if self.starImageLoader:
                self.starImageLoader.runing = False
            time.sleep(0.1)
        self.threadpool.clear()
        self.threadpool0.clear()
        while self.threadpool.activeThreadCount() > 0:
            time.sleep(0.1)
        while self.threadpool0.activeThreadCount() > 0:
            time.sleep(0.1)

        del_file_paths = set(self.file_paths) - set(file_paths)
        for file_path in del_file_paths:
            del self.file_items[file_path]

        self.select_labels_keys -= del_file_paths
        if self.now_select_label_key in del_file_paths:
            self.now_select_label_key = None

        # 初始化变量
        for file_path in list(self.labels.keys()):
            self.recycleFileLabel(file_path)
        self.ctrl_select_labels_keys.clear()
        self.visible_labels_keys.clear()
        new_file_paths = set(file_paths) - set(self.file_paths)
        self.file_paths = file_paths
        if len(new_file_paths) != 0:
            new_file_meta_datas = []
            for file_meta_data in file_meta_datas:
                if file_meta_data[0] in new_file_paths:
                    new_file_meta_datas.append(file_meta_data)
            self.createFileItem(new_file_meta_datas)
        self._sort_files()
        self.changeThumbnailSize(self.image_size)
        # 重置滚动条位置
        if not recover:
            self.v_scroll.setValue(0)


    # 创建文件对象
    def createFileItem(self, file_meta_datas: list[tuple[str, int, float]]):
        '''
        创建文件对象
        :param file_paths: 新的文件路径列表
        '''
        # 使用多线程添加文件属性
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(self._createFileItem, file_meta_data) for file_meta_data in file_meta_datas]
            concurrent.futures.wait(futures)

    def _createFileItem(self, file_path_meta_data: tuple[str, int, float]):
        file_path = file_path_meta_data[0]
        if file_path in self.file_items_cache:
            file_item = self.file_items_cache[file_path]
            file_item.specifid = 0
            file_item.selected = 0
            file_item.hover = 0
            self.set_file_css(file_item)
            if file_item.label_width != self.label_width:
                file_item.update_label_size(self.label_width)
            self.file_items[file_path] = file_item
            return
        file_item = FileItem(file_path, file_path_meta_data[1], file_path_meta_data[2], self.label_width)
        # 获取文件图标
        file_extension = os.path.splitext(file_path)[1]
        try:
            pixmap = self.extension_icon[self.image_size][file_extension]
        except KeyError:
            icon_provider = QFileIconProvider()
            file_icon = icon_provider.icon(QFileInfo(file_path))
            pixmap = file_icon.pixmap(self.image_size, self.image_size)
            # 缩放图标，并保持宽高比
            pixmap = pixmap.scaled(self.image_size, self.image_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            # 将图标添加到缓存
            if self.image_size not in self.extension_icon:
                self.extension_icon[self.image_size] = {}
            self.extension_icon[self.image_size][file_extension] = pixmap
        file_item.icon_source = {'current': PixmapIcon(pixmap)}
        self.file_items[file_path] = file_item
        self.file_items_cache[file_path] = file_item

    # 创建文件标签
    def createFileLabel(self):
        '''
        创建文件标签
        :return: 文件标签
        '''
        label = QLabel()
        label.setObjectName("file_label")

        # 创建显示图标的 QLabel
        icon_label = QLabel(label)
        icon_label.setObjectName("icon_label")
        icon_label.setStyleSheet("background-color: transparent;")
        icon_label.setFixedSize(self.image_size, self.image_size)
        icon_label.setAlignment(Qt.AlignHCenter | Qt.AlignBottom)
        icon_label.move(self.LABEL_INNER_SPACING, self.LABEL_INNER_SPACING)

        # 创建显示文件名的 QLabel
        file_name_label = QLabel(label)
        file_name_label.setObjectName("file_name_label")
        file_name_label.setStyleSheet("background-color: transparent;")
        file_name_label.setWordWrap(True)
        file_name_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        # 设置文件名标签的大小和位置
        file_name_label.setFixedWidth(self.label_width - 4)
        file_name_label.move(2, self.label_width)

        #绑定标签操作
        label.mouseDoubleClickEvent = partial(self.openFile, label=label) # 双击
        label.mousePressEvent = partial(self.onLabelLeftClick, label=label) # 左击
        # 右击菜单
        label.setContextMenuPolicy(Qt.CustomContextMenu) 
        label.customContextMenuRequested.connect(partial(self.showLabelMenu, label=label))
        # 绑定鼠标进入和离开的事件
        label.enterEvent = partial(self.setBackgroundColorOnEnter, label=label)
        label.leaveEvent = self.resetBackgroundColorOnLeave
        label.setParent(self)
        label.hide()
        return label

    # 加载文件缩略图
    def startLoadingImages(self, threadpool:QThreadPool, file_paths:list=None, use_cache=True):
        '''
        开始加载输入文件缩略图
        :param threadpool: 线程池
        :param file_paths: 文件路径列表, None时加载所有文件
        :param use_cache: 是否使用缓存
        '''
        if file_paths is None:
            file_paths = self.file_paths.copy()
        if threadpool is self.threadpool:
            if self.starImageLoader:
                self.starImageLoader.runing = False
            self.threadpool.clear()
            self.starImageLoader = StarImageLoader(self, threadpool, file_paths, use_cache)
            self.startLoadingImagesThreadpool.start(self.starImageLoader)
        if threadpool is self.threadpool0:
            if use_cache:
                for file_path in file_paths[:]:
                    if self.file_items[file_path].icon:
                        file_paths.remove(file_path)
            if len(file_paths) > 0:
                starImageLoader = StarImageLoader(self, threadpool, file_paths, use_cache)
                self.startLoadingImagesThreadpool.start(starImageLoader)

    # 设置文件标签
    def setFileQLabel(self, file_path: str):
        '''
        设置文件标签
        :param file_path: 文件路径
        '''
        if file_path not in self.file_items:
            return

        if not self.label_pool:
            label = self.createFileLabel()
            self.label_pool.append(label)

        file_item = self.file_items[file_path]
        label = self.label_pool.pop()
        icon_label = label.findChild(QLabel, "icon_label")
        file_name_label = label.findChild(QLabel, "file_name_label")

        label.file_path = file_path
        icon_label.file_path = file_path
        file_name_label.file_path = file_path
        
        file_item.apply(icon_label)

        file_name_label.setText('\u200B'.join(file_item.file_name))
        file_name_label.setFixedHeight(file_item.name_height)
        
        label.setFixedSize(QSize(file_item.label_size[0], file_item.label_size[1]))
        label.move(QPoint(file_item.label_pos[0], file_item.label_pos[1]) - self._offset)
        style = f"""
        QLabel#{label.objectName()} {{
            {file_item.border.value}
            {file_item.background.value}
        }}
        """
        label.setStyleSheet(style)
        label.show()
        self.labels[file_path] = label

    # 更新布局
    def updateLayout(self):
        '''
        更新布局
        '''
        total_files = len(self.file_items)  # 获取标签数量

        fixed_width = 4*self.LABEL_SPACING + self.v_scroll.width() # 保证左端至少有4倍间距的空白
        area_width = self.width() - fixed_width 
        num_columns = max(1, 1 + (area_width - self.label_width) // (self.label_width + self.LABEL_SPACING))
        num_rows = (total_files + num_columns - 1) // num_columns

        self.labels_rect = [
            [None for _ in range(num_columns)] 
            for _ in range(num_rows)
        ]

        if num_columns > total_files or num_columns == 1:
            HORIZONTAL_SPACING = self.LABEL_SPACING
        else:
            HORIZONTAL_SPACING = round((area_width - num_columns * self.label_width) / num_columns)
        self.HORIZONTAL_SPACING = HORIZONTAL_SPACING

        # 计算label位置
        col_width = self.label_width + HORIZONTAL_SPACING
        row_height = self.label_width + self.LABEL_SPACING
        x_offset = 4 * self.LABEL_SPACING
        y_offset = 2 * self.LABEL_SPACING
        x_offsets = [x_offset + c * col_width for c in range(num_columns)]
        y_offsets = [y_offset + r * row_height for r in range(num_rows)]

        index = 0
        file_name_height_all = 0
        for row in range(num_rows-1):
            max_file_name_height = 0  # 每行最大文件名高度
            for col in range(num_columns):
                file_path = self.file_paths[index]
                file_item = self.file_items[file_path]
                # 记录最大文件名高度
                name_height = file_item.name_height
                if name_height > max_file_name_height:
                    max_file_name_height = name_height

                x = x_offsets[col]
                y = y_offsets[row] + file_name_height_all
                file_item.label_pos = (x, y)
                self.labels_rect[row][col] = (file_item.label_pos, file_item.label_size, file_path)
                index += 1  # 下一个文件
            # 每行循环结束累加最大 name_height
            file_name_height_all += max_file_name_height
        # 最后一行
        last_row_index = num_rows - 1
        last_row_cols = total_files - index
        max_file_name_height = 0
        for col in range(last_row_cols):
            file_path = self.file_paths[index]
            file_item = self.file_items[file_path]
            if file_item.name_height > max_file_name_height:
                max_file_name_height = file_item.name_height
            x = x_offsets[col]
            y = y_offsets[last_row_index] + file_name_height_all
            file_item.label_pos = (x, y)
            self.labels_rect[last_row_index][col] = (file_item.label_pos, file_item.label_size, file_path)
            index += 1
        file_name_height_all += max_file_name_height

        self.max_col = min(num_columns, total_files)
        self.max_row = num_rows
        file_name_height_all += max_file_name_height
        content_width = max(self.width(), self.label_width + fixed_width)
        content_height = 4*self.LABEL_SPACING + self.max_row * (self.label_width + self.LABEL_SPACING) + file_name_height_all + self.h_scroll.height()
        self._content_size = QSize(content_width, content_height)
        if self._offset.y() > self._content_size.height() - self.height():
            self._offset.setY(max(0, self._content_size.height() - self.height()))
        self.update_scrollbars()
        self.lazy_load()

    # 懒加载
    def lazy_load(self):
        self.threadpool0.clear()
        # 计算self.content_widget可见范围
        visible_rect = QRect(self._offset, self._offset + self.rect().bottomRight())
        visible_labels_keys = self.get_rect_label(visible_rect)
        # 隐藏不可见label
        no_visible_labels_keys = self.visible_labels_keys - visible_labels_keys
        for no_visible_label_key in no_visible_labels_keys:
            if no_visible_label_key in self.labels:
                self.recycleFileLabel(no_visible_label_key)
        # 移动并显示可见label
        for visible_label_key in visible_labels_keys:
            if visible_label_key not in self.labels:
                self.setFileQLabel(visible_label_key)
            else:
                file_item = self.file_items[visible_label_key]
                label = self.labels[visible_label_key]
                label.move(QPoint(file_item.label_pos[0], file_item.label_pos[1]) - self._offset)
                label.show()
        self.visible_labels_keys = visible_labels_keys
        self.startLoadingImages(self.threadpool0, list(visible_labels_keys))
        self.v_scroll.raise_()
        self.h_scroll.raise_()
        self.corner.raise_()


    # 框选文件功能
    def mousePressEvent(self, event):
        self.setFocus()
        if event.button() != Qt.LeftButton:
            return

        self.MousePress = True
        if not event.modifiers() & Qt.ControlModifier:
            for select_label_key in self.select_labels_keys:
                file_item = self.file_items[select_label_key]
                file_item.selected = 0
                self.set_file_css(file_item)
            self.select_labels_keys.clear()
        # 如果按下ctrl
        else:
            self.select_labels_keys_snapshot = self.select_labels_keys.copy() #记录按下ctrl时的文件选取状态
        self.origin = event.pos() + self._offset

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.MousePress:
            if event.buttons() & Qt.LeftButton:
                # 设置橡皮筋框选的几何形状
                # QRect(self.origin, event.pos()) 创建一个矩形，从起点 `self.origin` 到当前鼠标位置 `event.pos()`
                # .normalized() 确保矩形是标准化的（即左上角为起点，右下角为终点），防止起点与终点位置不同导致的问题
                self.rubber_band.setGeometry(QRect(self.origin - self._offset, event.pos()).normalized())
                self.rubber_band.show() 
                self.selectLabelsInRect(QRect(self.origin, event.pos() + self._offset).normalized(), event.modifiers())
                mouse_pos_in_scroll_area = event.pos()
                scroll_area_rect = self.rect()
                if scroll_area_rect.contains(mouse_pos_in_scroll_area):
                    self.auto_scroll_timer.stop()
                else:
                    self.autoScroll(mouse_pos_in_scroll_area)
            else:
                self.mouseReleaseEvent(event)

    def mouseReleaseEvent(self, event):
        if self.MousePress:
            if event.button() == Qt.LeftButton:
                self.rubber_band.hide()
        self.auto_scroll_timer.stop()
        self.MousePress = False
        self.ctrl_select_labels_keys.clear()

    def selectLabelsInRect(self, rubber_rect: QRect, modifiers):
        select_labels_keys = self.get_rect_label(rubber_rect)
        # 如果没按ctrl
        if not modifiers & Qt.ControlModifier:
            # 恢复未选中标签状态
            no_select_labels_keys = self.select_labels_keys - select_labels_keys 
            for no_select_label_key in no_select_labels_keys:
                file_item = self.file_items[no_select_label_key]
                file_item.selected = 0
                self.set_file_css(file_item)
            # 改变新增选中标签状态
            add_select_labels_keys = select_labels_keys - self.select_labels_keys
            for add_select_label_key in add_select_labels_keys:
                file_item = self.file_items[add_select_label_key]
                file_item.selected = 1
                self.set_file_css(file_item)
            self.select_labels_keys = select_labels_keys
        # 如果按下ctrl
        else:
            # 恢复未选中标签状态
            no_ctrl_select_labels_keys = self.ctrl_select_labels_keys - select_labels_keys 
            for key in no_ctrl_select_labels_keys:
                should_select = (key in self.select_labels_keys_snapshot)
                self.update_label_select_status(key, should_select)

            # 改变新增选中标签状态
            add_ctrl_select_labels_keys = select_labels_keys - self.ctrl_select_labels_keys
            for key in add_ctrl_select_labels_keys:
                should_select = not (key in self.select_labels_keys_snapshot)
                self.update_label_select_status(key, should_select)

            self.ctrl_select_labels_keys = select_labels_keys

    def update_label_select_status(self, file_path: str, should_select: bool):
        """
        更新file的选中状态
        """
        file_item = self.file_items[file_path]

        if should_select:
            self.select_labels_keys.add(file_path)
            file_item.selected = 1
        else:
            self.select_labels_keys.discard(file_path)
            file_item.selected = 0

        self.set_file_css(file_item)


    # 滚动条实现
    def on_v_scroll(self, value):
        self._offset.setY(value)
        self.on_scroll(value)

    def on_h_scroll(self, value):
        self._offset.setX(value)
        self.on_scroll(value)

    def on_scroll(self, value):
        self.lazy_load()
        global_pos = QCursor.pos()
        local_pos = self.mapFromGlobal(global_pos)
        if self.MousePress: # 如果鼠标按下，手动处理橡皮框
            # 将pos修正到widget内
            x = max(1, min(local_pos.x(), self.width() - 1))
            y = max(1, min(local_pos.y(), self.height() - 1))
            widget_pos = self.mapFrom(self, QPoint(x, y))
            self.rubber_band.setGeometry(QRect(self.origin - self._offset, widget_pos).normalized())
            self.rubber_band.show()
            self.selectLabelsInRect(QRect(self.origin, widget_pos + self._offset).normalized(), QApplication.keyboardModifiers())
        else: # 否则，手动处理标签进入和离开事件
            # widget_pos = self.mapFrom(self, local_pos)
            label = self.childAt(local_pos)
            if isinstance(label, QLabel):
                file_path = label.file_path
                label = self.labels[file_path]
            else:
                file_path = None
            if file_path != self.now_hang_file:
                if self.now_hang_file:
                    self.resetBackgroundColorOnLeave(value)
                if isinstance(label, QLabel):
                    self.setBackgroundColorOnEnter(value, label)
        self.update()

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
        self.corner.setGeometry(w - 15, h - 15, 15, 15)

    # 自动滚动
    def autoScroll(self, mouse_pos: QPoint, auto=False):
        '''
        自动滚动
        :param mouse_pos: 鼠标位置
        :param auto: 是否启动自动滚动定时器
        '''
        scroll_area_rect = self.rect()
        # 检查边缘位置和移动方向来决定是否滚动
        if mouse_pos.y() < scroll_area_rect.top():
            movement_scale = max(0.5, -(mouse_pos.y() - scroll_area_rect.top())/50) # 计算滚动倍率
            move_value = round(movement_scale * self.SCROLL_DISTANCE_PER_FRAME) # 计算移动距离
            self.v_scroll.setValue(self.v_scroll.value() - move_value)  # 向上滚动
        elif mouse_pos.y() > scroll_area_rect.bottom():
            movement_scale = max(0.5, (mouse_pos.y() - scroll_area_rect.bottom())/50)
            move_value = round(movement_scale * self.SCROLL_DISTANCE_PER_FRAME)
            self.v_scroll.setValue(self.v_scroll.value() + move_value)  # 向下滚动

        # if mouse_pos.x() < scroll_area_rect.left():
        #     movement_scale = max(0.5, (mouse_pos.x() - scroll_area_rect.left())/50)
        #     move_value = round(movement_scale * self.SCROLL_DISTANCE_PER_FRAME)
        #     self.h_scroll.setValue(self.h_scroll.value() - move_value)  # 向左滚动
        # elif mouse_pos.x() > scroll_area_rect.right():
        #     movement_scale = max(0.5, (mouse_pos.x() - scroll_area_rect.right())/50)
        #     move_value = round(movement_scale * self.SCROLL_DISTANCE_PER_FRAME)
        #     self.h_scroll.setValue(self.h_scroll.value() + move_value)  # 向右滚动

        if not auto:
            try:
                self.auto_scroll_timer.timeout.disconnect()
            except TypeError:
                pass
            self.auto_scroll_timer.timeout.connect(lambda: self.autoScroll(mouse_pos, True))
            if not self.auto_scroll_timer.isActive():
                self.auto_scroll_timer.start()


    #————————————————————右键菜单显示——————————————————————

    def showContextMenu(self, pos: QPoint):

        for select_label_key in self.select_labels_keys:
            file_item = self.file_items[select_label_key]
            file_item.selected = 0
            self.set_file_css(file_item)
        self.select_labels_keys.clear()
        context_menu = QMenu(self)
        self.addViewMenu(context_menu)  # 添加查看菜单
        self.addSortMenu(context_menu)   # 添加排序菜单
        select_all_action = QAction("全选", self)  
        select_all_action.triggered.connect(self.select_all_file)
        context_menu.addAction(select_all_action)

        scroll_area_global_pos = self.mapToGlobal(QPoint(0, 0))
        global_pos = scroll_area_global_pos + pos
        context_menu.exec_(global_pos)

    def addViewMenu(self, context_menu: QMenu):
        view_menu = context_menu.addMenu("查看")

        small_action = QAction("小图标", self)  
        small_action.triggered.connect(lambda: self.changeThumbnailSize(self.SMALL_SIZE, 'small'))
        if self.current_image_size == "small":
            small_action.setIcon(QIcon(self.create_black_dot(6)))

        medium_action = QAction("中等图标", self)  
        medium_action.triggered.connect(lambda: self.changeThumbnailSize(self.MEDIUM_SIZE, 'mid'))  
        if self.current_image_size == "mid":
            medium_action.setIcon(QIcon(self.create_black_dot(6)))

        large_action = QAction("大图标", self)  
        large_action.triggered.connect(lambda: self.changeThumbnailSize(self.LARGE_SIZE, 'large'))
        if self.current_image_size == "large":
            large_action.setIcon(QIcon(self.create_black_dot(6)))

        view_menu.addAction(small_action)  
        view_menu.addAction(medium_action)  
        view_menu.addAction(large_action) 

    def addSortMenu(self, context_menu: QMenu):
        # 添加排序选项
        sort_menu = context_menu.addMenu("排序")
        name_action = QAction("按文件名", self)
        name_action.triggered.connect(lambda: self.setSortKeyAndOrder("key","name"))
        if self.current_sort_key == "name":
            name_action.setIcon(QIcon(self.create_black_dot(6)))

        size_action = QAction("按文件大小", self)
        size_action.triggered.connect(lambda: self.setSortKeyAndOrder("key","size"))
        if self.current_sort_key == "size":
            size_action.setIcon(QIcon(self.create_black_dot(6)))

        date_action = QAction("按修改日期", self)
        date_action.triggered.connect(lambda: self.setSortKeyAndOrder("key","date"))
        if self.current_sort_key == "date":
            date_action.setIcon(QIcon(self.create_black_dot(6)))

        random_action = QAction("随机排序", self)
        random_action.triggered.connect(lambda: self.setSortKeyAndOrder("key","random"))
        if self.current_sort_key == "random":
            random_action.setIcon(QIcon(self.create_black_dot(6)))

        sort_menu.addAction(name_action)
        sort_menu.addAction(size_action)
        sort_menu.addAction(date_action)
        sort_menu.addAction(random_action)

        #添加分割线
        sort_menu.addSeparator()

        # 添加升序、降序选项
        asc_action = QAction("升序", self)
        asc_action.triggered.connect(lambda: self.setSortKeyAndOrder("order","asc"))
        if self.current_sort_order == "asc":
            asc_action.setIcon(QIcon(self.create_black_dot(6)))

        desc_action = QAction("降序", self)
        desc_action.triggered.connect(lambda: self.setSortKeyAndOrder("order", "desc"))
        if self.current_sort_order == "desc":
            desc_action.setIcon(QIcon(self.create_black_dot(6)))

        sort_menu.addAction(asc_action)
        sort_menu.addAction(desc_action)


    #————————————————————右键菜单功能——————————————————————

    # 改变缩略图大小
    def changeThumbnailSize(self, size: int, level=None):
        if level is not None:
            self.current_image_size = level
            config.set('FileShowArea', 'current_image_size', level)  # 更新config对象
            save_config()
        self.image_size = size
        self.LABEL_INNER_SPACING = int(self.image_size * self.SPACING_RATE)
        self.label_width = self.image_size + 2*self.LABEL_INNER_SPACING
        while self.startLoadingImagesThreadpool.activeThreadCount() > 0:
            self.starImageLoader.runing = False
            time.sleep(0.1)
        self.threadpool.clear()  # 清空当前线程池中的任务

        for file_path in list(self.labels.keys()):
            self.recycleFileLabel(file_path)

        for label in self.label_pool:
            icon_label = label.findChild(QLabel, "icon_label")
            icon_label.setFixedSize(self.image_size, self.image_size)
            icon_label.move(self.LABEL_INNER_SPACING, self.LABEL_INNER_SPACING)
            file_name_label = label.findChild(QLabel, "file_name_label")
            file_name_label.setFixedWidth(self.label_width - 4)
            file_name_label.move(2, self.label_width)

        for file_item in self.file_items.values():
            file_item.icon = False
            file_item.update_label_size(self.label_width)

        self.updateLayout()
        while self.threadpool.activeThreadCount() > 0:
            time.sleep(0.1)        
        self.startLoadingImages(self.threadpool)  # 重新加载当前文件夹中的图片
  
    # 改变排序方式
    def setSortKeyAndOrder(self, action: str, value: str):
        if action == "key":
            self.current_sort_key = value
            config.set('FileShowArea', 'current_sort_key', value)  # 更新config对象
            self._sort_files()
        if action == "order":
            if value != self.current_sort_order:
                self.current_sort_order = value  # 更新当前排序顺序
                self.file_paths.reverse()  # 反转文件路径列表
                config.set('FileShowArea', 'current_sort_order', value)  # 更新config对象
            save_config()  # 保存配置

        self.updateLayout()  # 更新布局以反映新的顺序
        self.threadpool.clear()
        self.startLoadingImages(self.threadpool)

    def _sort_files(self, file_paths: list=None):
        if file_paths is None:
            file_paths = self.file_paths
        if self.current_sort_key == "name":
            # 自然排序
            nkey = natsort_keygen(key=lambda path: self.file_items[path].file_name)
            file_paths.sort(
                key=nkey,
                reverse=(self.current_sort_order == "desc")
            )

            ## windows api
            # import ctypes
            # from functools import cmp_to_key
            # cmp_func = ctypes.windll.shlwapi.StrCmpLogicalW
            # def windows_cmp(a, b):
            #     return cmp_func(a, b)
            # file_paths.sort(
            #     key=cmp_to_key(lambda a, b: cmp_func(
            #         self.file_items[a].file_name,
            #         self.file_items[b].file_name
            #     )),
            #     reverse=(self.current_sort_order == "desc")
            # )
        elif self.current_sort_key == "size":
            file_paths.sort(key=lambda path: self.file_items[path].file_size_bytes, reverse=(self.current_sort_order == "desc"))
        elif self.current_sort_key == "date":
            file_paths.sort(key=lambda path: self.file_items[path].file_date, reverse=(self.current_sort_order == "desc"))
        elif self.current_sort_key == "random":
            random.shuffle(file_paths)

    # 全选
    def select_all_file(self):
        self.select_labels_keys = set(self.file_paths)
        for file_item in self.file_items.values():
            file_item.selected = 1
            self.set_file_css(file_item)


    #————————————————————文件相关功能——————————————————————
    
    #左击选中
    def onLabelLeftClick(self, event: QMouseEvent, label: QLabel):
        if event.button() != Qt.LeftButton:
            return

        file_path = label.file_path
        event_file_item = self.file_items[file_path]
        if event.modifiers() & Qt.ControlModifier:
            self.select_labels_keys_snapshot = self.select_labels_keys.copy() # 快照
            should_select = not (file_path in self.select_labels_keys_snapshot)
            self.update_label_select_status(file_path, should_select)
        else:
            event_file_item.selected = 1
            for select_label_key in self.select_labels_keys:
                if select_label_key == file_path:
                    continue
                file_item = self.file_items[select_label_key]
                file_item.selected = 0
                self.set_file_css(file_item)
            self.select_labels_keys.clear()
            self.select_labels_keys.add(file_path)
        if self.now_select_label_key is not None:
            file_item = self.file_items[self.now_select_label_key]
            file_item.specifid = 0
            self.set_file_css(file_item)
        self.now_select_label_key = file_path
        event_file_item.specifid = 1
        self.set_file_css(event_file_item)
        # if not self.isMouseOnThumbnail(event.pos(), label): # 如果鼠标不在缩略图上
        self.MousePress = True
        parent_pos = label.mapTo(self, event.pos())
        self.origin = parent_pos + self._offset

    # 双击打开文件
    def openFile(self, event, label: QLabel, default=False):
        file_path = label.file_path
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "文件不存在", f"无法打开文件：\n{file_path}\n文件已不存在。")
            return
        # 支持的图片格式  
        supported_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']  
        
        # 检查文件扩展名  
        ext = os.path.splitext(file_path)[1].lower()  
        
        if not default and ext in supported_formats:  
            # 文件是图片，使用MultiImageViewer显示
            image_viewer = MultiImageViewer()  # 保存为实例变量以防止被垃圾回收
            self.image_viewers.append(image_viewer)
            image_viewer.destroyed.connect(lambda: self.image_viewers.remove(image_viewer))
            image_viewer.load_image_files(self.file_paths.copy(), file_path)
            image_viewer.show()
        else:  
            # 非图片文件，使用默认应用打开  
            try:  
                os.startfile(file_path)  
            except Exception as e:  
                QMessageBox.critical(self, "打开文件失败", f"无法打开文件：\n{file_path}\n错误：{e}")
        
    # 右键菜单
    def showLabelMenu(self, pos: QPoint, label: QLabel):
        file_path = label.file_path
        if file_path not in self.select_labels_keys: # 如果label未被选中
            for select_label_key in self.select_labels_keys:
                file_item = self.file_items[select_label_key]
                file_item.selected = 0
                self.set_file_css(file_item)
            self.select_labels_keys.clear()
            if not self.isMouseOnThumbnail(pos, label):
                parent_pos = label.mapTo(self, pos)
                self.customContextMenuRequested.emit(parent_pos)
                return
        if self.now_select_label_key is not None:
            file_item = self.file_items[self.now_select_label_key]
            file_item.specifid = 0
            self.set_file_css(file_item)

        self.select_labels_keys.add(file_path)
        file_item = self.file_items[file_path]
        file_item.selected = 1

        self.now_select_label_key = file_path
        file_item.specifid = 1
        self.set_file_css(file_item)

        context_menu = QMenu(self)
        properties_action = QAction("属性", self)
        properties_action.triggered.connect(lambda: self.displayImageProperties(file_path))
        context_menu.addAction(properties_action)


        if os.path.exists(label.file_path):
            file_menu = context_menu.addMenu("文件操作")

            open_file_action = QAction("系统默认方式打开", self)
            open_file_action.triggered.connect(lambda: self.openFile(None, label, default=True))
            file_menu.addAction(open_file_action)

            open_folder_action = QAction("打开文件所在位置", self)
            open_folder_action.triggered.connect(lambda: self.openFolderAction(label))
            file_menu.addAction(open_folder_action)

            copy_file_action = QAction("复制", self)
            copy_file_action.triggered.connect(lambda: self.changeFilePathMessageBox(label, "复制"))
            file_menu.addAction(copy_file_action)

            move_file_action = QAction("剪切", self)
            move_file_action.triggered.connect(lambda: self.changeFilePathMessageBox(label, "剪切"))
            file_menu.addAction(move_file_action)

            rename_file_action = QAction("重命名", self)
            rename_file_action.triggered.connect(lambda: self.renameFile(label))
            file_menu.addAction(rename_file_action)

            delete_file_action = QAction("删除", self)
            delete_file_action.triggered.connect(lambda: self.confirmDelete(os_delete=True))
            file_menu.addAction(delete_file_action)
        else:
            select_all_unvalid_file_action = QAction("选中所有失效文件", self)
            select_all_unvalid_file_action.triggered.connect(self.selectAllUnvalidFile)
            context_menu.addAction(select_all_unvalid_file_action)

            repair_file_action = QAction("修复文件", self)
            repair_file_action.triggered.connect(self.repairFile)
            context_menu.addAction(repair_file_action)

        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(self.refresh)
        context_menu.addAction(refresh_action)

        delete_file_from_base_action = QAction("从库中删除", self)
        delete_file_from_base_action.triggered.connect(self.confirmDelete)
        context_menu.addAction(delete_file_from_base_action)

        label_global_pos = label.mapToGlobal(QPoint(0, 0)) # 获取标签的全局位置
        global_pos = label_global_pos + pos # 计算菜单弹出位置
        return context_menu, global_pos


    # 移动文件对话框
    def changeFilePathMessageBox(self, label, file_action):
        file_path = label.file_path
        parent_path = os.path.dirname(file_path)
        # 创建一个文件对话框，用于选择目标文件夹
        options = QFileDialog.Options()
        options |= QFileDialog.ShowDirsOnly
        target_folder = QFileDialog.getExistingDirectory(self, "选择目标文件夹", parent_path, options=options)

        if target_folder:
            if file_action == "剪切":
                move_tags = True
            elif file_action == "复制":
                # 创建一个消息框，询问是否移动标签
                message_box = QMessageBox(self)
                message_box.setIcon(QMessageBox.Question)
                message_box.setWindowTitle("提示")
                message_box.setText("是否移动标签？")
                message_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                # 显示消息框
                message_box.exec_()
                move_tags = (message_box.result() == QMessageBox.Yes)


            error_messages = self.changeFilePath(target_folder, file_action, move_tags)

            if len(error_messages) == 0:
                # 显示“添加成功”的消息框
                message_box = QMessageBox(self)
                message_box.setIcon(QMessageBox.Information)
                message_box.setWindowTitle("提示")
                message_box.setText(f"{file_action}成功！")
                message_box.setStandardButtons(QMessageBox.Ok)
                # 让消息框在0.5秒后自动关闭
                QTimer.singleShot(500, message_box.close)
            else:
                # 显示错误消息的消息框
                message_box = QMessageBox(self)
                message_box.setIcon(QMessageBox.Critical)
                message_box.setWindowTitle("错误")
                message_box.setText("以下文件处理失败：\n\n" + "\n".join(error_messages))
                message_box.setStandardButtons(QMessageBox.Ok)
            # 显示消息框
            message_box.exec_()
            self.DictManage.notify_observers()

    # 修改文件位置
    def changeFilePath(self, target_folder, file_action, move_tags):
        # 按深度降序排序，优先处理子文件夹
        sorted_paths = sorted(
            self.select_labels_keys,
            key=lambda path: len(os.path.normpath(path).split(os.path.sep)),
            reverse=True
        )
        error_messages = []
        for file_path in sorted_paths:
            try:
                if not os.path.exists(file_path):
                    continue
                target_path = self.shutil_add_rename(file_path, target_folder, file_action)
                if not move_tags:
                    continue
                self.DictManage.rename_file(file_path, target_path)
                if os.path.isdir(target_path):
                    self.changeFolderAllFilePath(file_path, target_path)                
            except Exception as e:
                error_message = f"处理文件 {file_path} 时出错: {e}"
                error_messages.append(error_message)
                print(error_message)
        return error_messages

    # 移动文件或文件夹到目标路径
    def shutil_add_rename(self, file_path, target_folder, file_action):
        # 获取文件/文件夹的原始名称
        base_name = os.path.basename(file_path)
        target_path = os.path.join(target_folder, base_name).replace('\\', '/')

        # 如果目标路径已存在，生成新名称
        if os.path.exists(target_path):
            target_path = get_available_filename(target_path)

        # 移动文件或文件夹到目标路径
        if file_action == "剪切":
            shutil.move(file_path, target_path)
        elif file_action == "复制":
            if os.path.isdir(file_path):
                shutil.copytree(file_path, target_path)
            else:
                shutil.copy(file_path, target_path)
        print(f"{file_path} 已成功{file_action}到 {target_path}")
        return target_path

    # 修改文件夹内的所有文件
    def changeFolderAllFilePath(self, parent_path, target_folder):
        file_paths = get_all_files(target_folder)
        for file_path in file_paths:
            old_file_path = file_path.replace(target_folder, parent_path)
            # 修改文件路径
            self.DictManage.rename_file(old_file_path, file_path)


    # 重命名文件函数
    def renameFile(self,  label: QLabel):
        file_path = label.file_path
        new_name = QInputDialog.getText(self, '重命名文件', '请输入新文件名:', text=os.path.basename(file_path))[0]
        if not new_name:
            return
        new_file_path = os.path.join(os.path.dirname(file_path), new_name).replace('\\', '/')
        if os.path.exists(new_file_path):
            QMessageBox.warning(self, '重命名失败', f'目标路径 {new_file_path} 已存在！')
            return
        os.rename(file_path, new_file_path)
        self.DictManage.rename_file(file_path, new_file_path)
        self.DictManage.notify_observers()

    # 确认删除文件函数
    def confirmDelete(self, os_delete=False):
        if os_delete:
            message = '确定要删除选中的文件吗？此操作将在系统层删除文件！'
        else:
            message = '确定要从库中删除选中的文件吗？'
        # 创建确认对话框
        reply = QMessageBox.question(self, '确认删除', 
                                   message,
                                   QMessageBox.Yes | QMessageBox.No, 
                                   QMessageBox.No)
        
        # 如果用户点击Yes，执行删除操作
        if reply == QMessageBox.Yes:
            self.deleteFile(os_delete=os_delete)

    # 删除文件函数
    def deleteFile(self, os_delete=False):
        delete_files = self.select_labels_keys
        for file_path in delete_files:
            try:
                self.DictManage.delete_file(file_path, notify=False)
                if os_delete and os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"删除文件 {file_path} 时出错: {e}")
        self.DictManage.notify_observers()

    # 刷新
    def refresh(self):
        # 不使用缓存加载
        file_meta_datas = []
        for file_path in self.select_labels_keys:
            self.file_items.pop(file_path)
            self.file_items_cache.pop(file_path)
            st = os.stat(file_path)
            size_bytes = st.st_size
            mtime = st.st_mtime
            file_meta_datas.append((file_path, size_bytes, mtime))
            if file_path in self.labels:
                self.recycleFileLabel(file_path)
        self.createFileItem(file_meta_datas)
        self.startLoadingImages(self.threadpool0, list(self.select_labels_keys), use_cache=False)
        self.select_labels_keys.clear()
        self.updateLayout()


    # 选中所有失效文件
    def selectAllUnvalidFile(self):
        for file_path in self.select_labels_keys:
            file_item = self.file_items[file_path]
            file_item.selected = 0
            self.set_file_css(file_item)
        self.select_labels_keys.clear()
        for file_path in self.file_paths:
            if not os.path.exists(file_path):
                self.select_labels_keys.add(file_path)
                file_item = self.file_items[file_path]
                file_item.selected = 1
                self.set_file_css(file_item)

    # 修复文件
    def repairFile(self):
        # 1. 选择文件所在文件夹
        options = QFileDialog.Options()
        options |= QFileDialog.ShowDirsOnly
        folder_path = QFileDialog.getExistingDirectory(self, "选择候选文件文件夹", options=options)
        if not folder_path:
            return

        # 2. 递归遍历文件夹中的所有文件和目录，构建文件名到路径的映射
        # 注意：这里会包含目录，如果你的修复只针对文件，可能需要进一步过滤
        fileName2filePath = {}
        for root, dirs, files in os.walk(folder_path):
            for item in files + dirs: # 遍历文件和目录
                file_path = os.path.join(root, item).replace('\\', '/')
                if item in fileName2filePath:
                    fileName2filePath[item].append(file_path)
                else:
                    fileName2filePath[item] = [file_path]
        
        # 3. 准备 FileSelectionComponent 所需的输入数据
        repair_file_groups = []
        repair_group_titles = []
        original_file_paths_for_mapping = [] # 用于映射最终选择结果到原始失效文件

        for original_missing_file_path in self.select_labels_keys:
            # 仅处理当前不存在的文件
            if os.path.exists(original_missing_file_path):
                continue
            
            file_name = os.path.basename(original_missing_file_path)
            candidate_paths = fileName2filePath.get(file_name, [])

            # 即使没有候选文件，也要为这个失效文件创建一个组，让用户知道其状态
            repair_file_groups.append(candidate_paths) 
            repair_group_titles.append(f"修复: '{file_name}' (原路径: {original_missing_file_path})")
            original_file_paths_for_mapping.append(original_missing_file_path) 

        # 如果没有需要修复的文件组（所有 select_labels_keys 中的文件都存在或没有找到候选），则提示并返回
        if not repair_file_groups:
            QMessageBox.information(self, "信息", "当前没有需要修复的失效文件。")
            return

        # 4. 定义初始选择处理函数：在修复场景下，通常会默认选择每个组的第一个文件
        def repair_initial_selector(group_files_list):
            if group_files_list:
                return [group_files_list[0]] # 默认选择第一个
            return []

        # 5. 创建并显示 FileSelectionComponent
        self.repair_dialog = FileSelectionComponent(
            parent=self, # 父窗口设为 self，使其成为模态对话框
            file_groups=repair_file_groups,
            selection_type='single', # 修复通常是单选一个最佳匹配
            image_size=180, # 调整图片大小以适应更多信息
            group_titles=repair_group_titles,
            initial_selection_handler=repair_initial_selector
        )

        # 6. 连接组件的 result_selected 信号到处理槽函数
        def handle_repair_selection(selected_groups_2d):
            print("\n--- 收到 FileSelectionComponent 的修复选择结果 ---")
            for i, group_selection in enumerate(selected_groups_2d):
                if i < len(original_file_paths_for_mapping):
                    original_path_to_repair = original_file_paths_for_mapping[i]
                    if group_selection:
                        # 修复场景下，每个组只应选择一个文件
                        selected_candidate_path = group_selection[0] 
                        print(f"准备修复: '{original_path_to_repair}' -> 使用: '{selected_candidate_path}'")
                        # 执行实际的文件修复操作
                        self.DictManage.rename_file(original_path_to_repair, selected_candidate_path)
                    else:
                        print(f"文件 '{original_path_to_repair}' 未选择修复文件，跳过。")
                else:
                    print(f"警告: 结果中包含未知组索引 {i}: {group_selection}")
            
            self.DictManage.notify_observers()
            QMessageBox.information(self, "修复完成", "所有文件修复操作已处理。")

        self.repair_dialog.result_selected.connect(handle_repair_selection)

        self.repair_dialog.show()


    # 打开文件所在位置
    def openFolderAction(self, label):
        file_path = label.file_path
        file_path = file_path.replace('/', '\\')
        subprocess.Popen(f'explorer /select,"{file_path}"')

    #显示图片属性
    def displayImageProperties(self, file_path:str):
        file_item = self.file_items[file_path]

        # 创建一个自定义窗口
        widget = QWidget()
        self.child_widget.append(widget)
        widget.destroyed.connect(lambda: self.child_widget.remove(widget))
        widget.setWindowTitle(f"{file_item.file_name} 属性")
        widget.resize(500, 300)

        # 创建一个文本编辑器，显示文件属性
        text_edit = QTextEdit(widget)
        text_edit.setReadOnly(True)  # 设置为只读

        # 设置字体
        font = QFont("Arial", 12)  # 使用 Arial 字体，大小为 12
        text_edit.setFont(font)

        # 获取文件标签
        tags = self.DictManage.query('file', file_path, 'tag')
        tags_str = ", ".join(list(tags)) if tags else "无标签"

        # 显示文件信息
        message = (
            f"<b>文件名:</b>&nbsp; {file_item.file_name}<br><br>"
            f"<b>文件路径: </b>&nbsp; {file_item.file_path}<br><br>"
            f"<b>文件大小: </b>&nbsp; {format_file_size(file_item.file_size_bytes)}<br><br>"
            f"<b>修改时间: </b>&nbsp; {datetime.fromtimestamp(file_item.file_date).strftime('%Y年%m月%d日，%H:%M:%S')}<br><br>"
            f"<b>文件标签: </b>&nbsp; {tags_str}"
        )
        text_edit.setHtml(message)

        # 创建确认按钮
        ok_button = QPushButton("确定", widget)
        ok_button.clicked.connect(widget.close)  # 使用 widget.close() 关闭窗口

        # 布局设置
        layout = QVBoxLayout(widget)
        layout.addWidget(text_edit)
        layout.addWidget(ok_button)

        widget.setLayout(layout)

        # 获取鼠标当前位置
        mouse_position = QCursor.pos()
        # 获取屏幕的可用几何尺寸
        screen_geometry = QApplication.desktop().availableGeometry()
        # 计算窗口显示的位置，确保完全显示在屏幕内
        x = mouse_position.x() - 250
        y = mouse_position.y() - 150
        if x + widget.width() > screen_geometry.right():
            x = screen_geometry.right() - widget.width() - 30
        if y + widget.height() > screen_geometry.bottom():
            y = screen_geometry.bottom() - widget.height() - 50
        if x < screen_geometry.left():
            x = screen_geometry.left() + 30
        if y < screen_geometry.top():
            y = screen_geometry.top() + 30
        # 设置窗口位置
        widget.move(x, y)
        # 显示窗口
        widget.show()


    #——————————————————————辅助方法————————————————————————

    def recycleFileLabel(self, file_path):
        """将单个文件标签从显示中移除并放回标签池"""
        label = self.labels.pop(file_path)
        label.hide()
        self.label_pool.append(label)

    #绘制黑点
    def create_black_dot(self, size: int):
        # 创建一个正方形的 QPixmap
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)  # 填充透明背景
        painter = QPainter(pixmap)
        
        # 使用 setRenderHint 确保抗锯齿效果
        painter.setRenderHint(QPainter.Antialiasing)  
        painter.setBrush(Qt.black)  # 设置黑色填充
        painter.drawEllipse(0, 0, size, size)  # 绘制圆形
        painter.end()
        return pixmap

    #判断鼠标是否点击在缩略图上
    def isMouseOnThumbnail(self, mouse_pos: QPoint, label: QLabel):
        # 获取缩略图和标签的尺寸
        icon_label = label.findChild(QLabel, "icon_label")
        pixmap = icon_label.pixmap()
        if pixmap is None:
            return True
        
        pixmap_size = pixmap.size()

        # 计算缩略图的偏移量以居中显示
        offset_x = (self.image_size - pixmap_size.width()) // 2
        offset_y = self.image_size - pixmap_size.height()

        # 确定缩略图的显示区域
        thumbnail_rect = QRect(offset_x + self.LABEL_INNER_SPACING, offset_y + self.LABEL_INNER_SPACING, pixmap_size.width(), pixmap_size.height())
        # 检查鼠标位置是否在缩略图范围内
        return thumbnail_rect.contains(mouse_pos)

    # 获取区域内label
    def get_rect_label(self, rect: QRect):
        file_paths: set[str] = set()
        if len(self.labels_rect) == 0:
            return file_paths
        begin_pos = rect.topLeft()
        end_pos = rect.bottomRight()
        # 计算开始行
        begin_row = begin_pos.y() // (self.label_width + self.LABEL_SPACING)
        begin_row = max(0, min(begin_row, self.max_row-1))
            # 寻找鼠标下方离鼠标最近的底部所在行
        while begin_row != 0 and self.labels_rect[begin_row-1][0][0][1] + self.labels_rect[begin_row-1][0][1][1] > begin_pos.y():
            begin_row -= 1
            # 当处在最后一行之外，越过
        if self.labels_rect[begin_row][0][0][1] + self.labels_rect[begin_row][0][1][1] < begin_pos.y():
            begin_row += 1
        # 计算结束行
        end_row = end_pos.y() // (self.label_width + self.LABEL_SPACING)
        end_row = max(0, min(end_row, self.max_row-1))
            # 寻找鼠标下方离鼠标最近的顶部所在行 
        while end_row != 0 and self.labels_rect[end_row-1][0][0][1] > end_pos.y():
            end_row -= 1
            # 当没处在最后一行之外时上移一行
        if self.labels_rect[end_row][0][0][1] > end_pos.y():
            end_row -= 1

        # 计算开始列
        begin_col = begin_pos.x() // (self.label_width + self.LABEL_SPACING)
        begin_col = max(0, min(begin_col, self.max_col-1))
            # 寻找鼠标右方离鼠标最近的右边所在列
        while begin_col != 0 and self.labels_rect[0][begin_col-1][0][0] + self.labels_rect[0][begin_col-1][1][0] > begin_pos.x():
            begin_col -= 1
            # 当处在最后一列之外，越过
        if self.labels_rect[0][begin_col][0][0] + self.labels_rect[0][begin_col][1][0] < begin_pos.x():
            begin_col += 1
        # 计算结束列
        end_col = end_pos.x() // (self.label_width + self.LABEL_SPACING)
        end_col = max(0, min(end_col, self.max_col-1))
            # 寻找鼠标右方离鼠标最近的左边所在行列
        while end_col != 0 and self.labels_rect[0][end_col-1][0][0] > end_pos.x():
            end_col -= 1
            # 当没处在最后一列之外时左移一列
        if self.labels_rect[0][end_col][0][0] > end_pos.x():
            end_col -= 1

        # 选择标签
        for row in range(begin_row,end_row+1):
            for col in range(begin_col,end_col+1):
                label = self.labels_rect[row][col]
                if label:
                    file_paths.add(label[2])
        return file_paths
    
    # 设置文件css
    def set_file_css(self, file_item: FileItem):
        border, background = self.file_status_map.get((file_item.specifid, file_item.selected, file_item.hover))
        label = self.labels.get(file_item.file_path)
        if border != file_item.border or background != file_item.background:
            file_item.border = border
            file_item.background = background
            if label:
                style = f"""
                QLabel#{label.objectName()} {{
                    {file_item.border.value}
                    {file_item.background.value}
                }}
                """
                label.setStyleSheet(style)

    # 鼠标进入标签时改变背景颜色
    def setBackgroundColorOnEnter(self, event, label: QLabel):
        file_path = label.file_path
        if self.now_hang_file and file_path != self.now_hang_file:
            self.resetBackgroundColorOnLeave(event)
        file_item = self.file_items[file_path]
        self.now_hang_file = file_path
        file_item.hover = 1
        self.set_file_css(file_item)

    # 鼠标离开标签时重置背景颜色
    def resetBackgroundColorOnLeave(self, event):
        if self.now_hang_file in self.file_items:
            file_item = self.file_items[self.now_hang_file]
            file_item.hover = 0
            self.set_file_css(file_item)
        self.now_hang_file = None




class MainFileShowArea(FileShowArea):
    def __init__(self, MainWindow, file_paths: list=None):
        super().__init__(file_paths)
        self.MainWindow = MainWindow

    def showLabelMenu(self, pos: QPoint, label: QLabel):
        result = super().showLabelMenu(pos, label)
        if result is None:
            return
        context_menu, global_pos = result

        tag_action = QAction("管理标签", self)
        tag_action.triggered.connect(lambda: self.chargeTag())
        # 添加至菜单第一位
        context_menu.insertAction(context_menu.actions()[0], tag_action)

        context_menu.exec_(global_pos)

    def chargeTag(self):
        self.MainWindow.showTagView(None, list(self.select_labels_keys))

class TagFileShowArea(FileShowArea):
    def __init__(self, file_paths: list=None):
        self.prompt_label = QLabel("请拖入文件或文件夹")
        self.prompt_label.setAlignment(Qt.AlignCenter)
        self.prompt_label.setStyleSheet("""
            color: gray;
            font-size: 16px;
        """)
        self.prompt_label.hide()  # 初始隐藏

        super().__init__(file_paths)

        self.prompt_label.setParent(self)

        self.setAcceptDrops(True)
        self.acceptFloder = config.getboolean('TagFileShowArea', 'acceptFloder', fallback=False)

    def showLabelMenu(self, pos: QPoint, label: QLabel):
        result = super().showLabelMenu(pos, label)
        # 检查返回值是否为 None，只有在不是 None 时才进行赋值
        if result is None:
            return
        context_menu, global_pos = result
        tag_action = QAction("移除", self)
        tag_action.triggered.connect(lambda: self.removeFile())
        context_menu.addAction(tag_action)
        context_menu.exec_(global_pos)

    def removeFile(self):
        for select_label_key in self.select_labels_keys:
            if select_label_key in self.labels:
                self.recycleFileLabel(select_label_key)
            self.file_paths.remove(select_label_key)
            self.file_items.pop(select_label_key)
            self.visible_labels_keys.discard(select_label_key)
        self.select_labels_keys.clear()
        if len(self.file_paths) == 0:
            self.now_select_label_key = None
        else:
            self.now_select_label_key = self.file_paths[0]
        self.now_hang_file = None
        self.updateLayout()

    def updateLayout(self):
        super().updateLayout()
        if len(self.file_paths) == 0:
            parent_width = self.width()
            parent_height = self.height()
            label_width = self.prompt_label.width()
            label_height = self.prompt_label.height()
            self.prompt_label.move(
                (parent_width - label_width) // 2,
                (parent_height - label_height) // 2
            )
            self.prompt_label.show()  # 显示提示标签
        else:
            self.prompt_label.hide()  # 隐藏提示标签


     #————————————————————拖入文件——————————————————————
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        # 检查拖入的内容是否为文件
        if event.mimeData().hasUrls():
            event.acceptProposedAction()  # 接受拖放操作

    def dropEvent(self, event: QDropEvent):
        # 获取拖入的文件路径
        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls]
        file_paths = []
        if not self.acceptFloder:
            for path in paths:
                if os.path.isdir(path):
                    file_paths += get_all_files(path)
                else:
                    file_paths.append(path)
        else:
            file_paths = paths
        file_paths = list(set(file_paths) - set(self.file_paths))
        self.file_paths += file_paths
        file_meta_datas = [(file_path, 0, 0) for file_path in file_paths]
        self.createFileItem(file_meta_datas)
        self._sort_files()
        self.updateLayout()