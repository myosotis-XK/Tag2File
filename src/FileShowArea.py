from .utils import *
from .MultithreadedLoading import *
from .DictManage import *
from .ImageViewer import *
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

if 'FileShowArea' not in config:
    config.add_section('FileShowArea')
if 'TagFileShowArea' not in config:
    config.add_section('TagFileShowArea')
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


class FileShowArea(QScrollArea):
    def __init__(self, file_paths=None):
        super().__init__()
        self.DictManage = DictManage()
        self.relation_graph = self.DictManage.relation_graph

        self.child_widget = []
        self.image_viewers = []
        self.cache_dir = os.path.join(root, 'data', 'cache', 'image')
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        # 读取配置文件
        # 图标大小
        self.SMALL_SIZE = config.getint('FileShowArea', 'SMALL_SIZE', fallback=50)
        self.MEDIUM_SIZE = config.getint('FileShowArea', 'MEDIUM_SIZE', fallback=100)
        self.LARGE_SIZE = config.getint('FileShowArea', 'LARGE_SIZE', fallback=250)
        # 布局间隔比例
        self.SPACING_RATE = config.getfloat('FileShowArea', 'SPACING_RATE', fallback=0.05)  # 间隔比率
        # 默认设置
        self.current_image_size = config.get('FileShowArea', 'current_image_size', fallback='mid')  # 默认图标大小
        self.current_sort_key = config.get('FileShowArea', 'current_sort_key', fallback='date')  # 默认排序方式
        self.current_sort_order = config.get('FileShowArea', 'current_sort_order', fallback='desc')  # 默认排序顺序
        # 界面参数
        self.WINDOW_FRAMES = config.getint('FileShowArea', 'WINDOW_FRAMES', fallback=60)  # 界面帧数
        self.SCROLL_DISTANCE_PER_SECOND = config.getint('FileShowArea', 'SCROLL_DISTANCE_PER_SECOND', fallback=500)  # 每秒滚动像素长度
        self.SCROLL_DISTANCE_PER_FRAME = self.SCROLL_DISTANCE_PER_SECOND / self.WINDOW_FRAMES  # 每秒滚动像素长度
        # 布局标签相关
        self.LABEL_SPACING = config.getint('FileShowArea', 'LABEL_SPACING', fallback=5)  # 标签间距
        self.label_name_size = config.getint('FileShowArea', 'label_name_size', fallback=20)  # 文件名高度

        self.labels = {}
        self.label_cache = {}
        self.labels_rect = {}  # {(row, col):(label_rect, file_path)}
        self.select_labels_keys = set()  # 选中label键
        self.ctrl_select_labels_keys = set()  # ctrl选中label键
        self.now_select_label_key = None  # 当前选中label_key
        self.visible_labels_keys = set()  # 可见label键
        self.MousePress = False  # 鼠标按压标记

        self.ctrl_key_pressed = False  # 控制键标记

        image_size_dict = {
            'small': self.SMALL_SIZE,
            'mid': self.MEDIUM_SIZE,
            'large': self.LARGE_SIZE
        }
        self.image_size = image_size_dict[self.current_image_size]
        self.LABEL_INNER_SPACING = int(self.image_size * self.SPACING_RATE) # 标签内间距
        self.label_size = self.image_size + 2*self.LABEL_INNER_SPACING #标签大小
        self.mouseMove = False
        self.now_hang_label = None
        
        self.auto_scroll_timer = QTimer(self)
        self.auto_scroll_timer.setInterval(round(1000/self.WINDOW_FRAMES))
        self.verticalScrollBar().valueChanged.connect(self.on_scroll)

        if file_paths is None:
            file_paths = []
        self.file_paths = file_paths
        self.startLoadingImagesThreadpool = QThreadPool()
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(1)
        self.threadpool0 = QThreadPool()
        # self.threadpool0.setMaxThreadCount(4)
        self.image_cache = {self.SMALL_SIZE: {}, self.MEDIUM_SIZE: {}, self.LARGE_SIZE: {}}  # 缓存字典
        self.initFileView()
        self.createFileLabels()
        self.setSortKeyAndOrder(self.current_sort_key, self.current_sort_order)

    def initFileView(self):
        # 创建一个滚动区域
        self.setWidgetResizable(True)
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("""  
            QWidget {  
                background-color: white;
            }  
        """)  
        self.setWidget(self.content_widget)

        # 绑定鼠标事件
        self.content_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.content_widget.customContextMenuRequested.connect(self.showContextMenu) 
        self.content_widget.mousePressEvent = self.mousePressEvent
        self.content_widget.mouseMoveEvent = self.mouseMoveEvent
        self.content_widget.setMouseTracking(True)
        self.content_widget.mouseReleaseEvent = self.mouseReleaseEvent

        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self.content_widget)  
        self.origin = QPoint()


    #——————————————————————重写方法————————————————————————

    #监控界面大小变化
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updateLayout()

    def closeEvent(self, event):
        # 清空图片加载任务
        while self.startLoadingImagesThreadpool.activeThreadCount() > 0:
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


    #——————————————————————辅助方法————————————————————————

    #绘制黑点
    def create_black_dot(self,size):
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
    def isMouseOnThumbnail(self, mouse_pos, label):
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

    #递归获取文件路径
    def get_all_files(slef, directory):
        directory = directory.replace('\\', '/') 
        files = []
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                file_path = os.path.join(root, filename).replace('\\', '/')
                files.append(file_path)
        return files

    #格式化文件大小
    def format_file_size(self,size_in_bytes):
        if size_in_bytes < 1024:
            return f"{size_in_bytes} B"
        elif size_in_bytes < 1024 ** 2:
            return f"{size_in_bytes / 1024:.2f} KB"
        elif size_in_bytes < 1024 ** 3:
            return f"{size_in_bytes / (1024 ** 2):.2f} MB"
        else:
            return f"{size_in_bytes / (1024 ** 3):.2f} GB"

    # 获取区域内label
    def get_rect_label(self, rect):
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

    # 获取缓存文件路径
    def get_cache_path(self, file_path):
        # 使用文件路径的哈希作为缓存文件名，以避免文件名冲突
        file_hash = hashlib.md5(file_path.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{file_hash}_{self.image_size}.png")
    
    # 鼠标进入标签时改变背景颜色
    def setBackgroundColorOnEnter(self, event, label):
        if label.file_path not in self.select_labels_keys:
            updateStyle(label, "background-color: #e5f3ff;")
        else:
            updateStyle(label, "border: 1px solid #99d1ff;")
        self.now_hang_label = label

    # 鼠标离开标签时重置背景颜色
    def resetBackgroundColorOnLeave(self, event, label):
        if label.file_path not in self.select_labels_keys:
            updateStyle(label, "background-color: transparent;")
        else:
            if label != self.labels.get(self.now_select_label_key):
                updateStyle(label, "border: none;")
        self.now_hang_label = None


    #——————————————————————基础功能————————————————————————

    def calculate_name_height(self, file_name, label_width, max_lines, font):
        """
        计算文件名标签的高度，但不超过最大允许高度
        :param file_name: 文件名（字符串）
        :param label_width: 标签的宽度（整数，像素）
        :param max_lines: 最大行数（整数）
        :param font: 用于计算的字体对象（QFont）
        :return: 文件名标签的高度（整数，像素）
        """
        font_metrics = QFontMetrics(font)
        single_line_height = font_metrics.lineSpacing()  # 每行高度
        text_width = font_metrics.horizontalAdvance(file_name)  # 文本总宽度
        num_lines = max(1, (text_width // label_width) + 1)  # 计算需要的行数
        total_lines = min(num_lines, max_lines)  # 限制最大行数
        name_height = total_lines * single_line_height  # 总高度
        return name_height + self.LABEL_INNER_SPACING

    def _createFileLabel(self, file_path):
        # 创建标签
        label = QLabel()
        label.setObjectName("file_label")

        # 获取文件图标
        file_extension = os.path.splitext(file_path)[1]
        try:
            pixmap = self.image_cache[file_extension]
        except:
            icon_provider = QFileIconProvider()
            file_icon = icon_provider.icon(QFileInfo(file_path))
            pixmap = file_icon.pixmap(self.image_size, self.image_size)
            # 将图标添加到缓存
            self.image_cache[file_extension] = pixmap


        # 缩放图标，并保持宽高比
        scaled_pixmap = pixmap.scaled(self.image_size, self.image_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # 创建显示图标的 QLabel
        icon_label = QLabel(label)
        icon_label.setStyleSheet("background-color: transparent;")
        icon_label.setObjectName("icon_label")
        icon_label.file_path = file_path
        icon_label.setFixedSize(self.image_size, self.image_size)
        icon_label.setPixmap(scaled_pixmap)
        icon_label.setAlignment(Qt.AlignHCenter | Qt.AlignBottom)
        icon_label.move(self.LABEL_INNER_SPACING, self.LABEL_INNER_SPACING)

        # 创建显示文件名的 QLabel
        file_name_label = QLabel(label)
        file_name_label.setStyleSheet("background-color: transparent;")
        file_name_label.setObjectName("file_name_label")
        file_name_label.setWordWrap(True)
        file_name_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        file_name = os.path.basename(file_path)  # 获取文件名
        file_name_label.setText('\u200B'.join(file_name))

        # 计算文件名标签的高度，但不超过最大允许高度
        name_height = self.calculate_name_height(file_name, self.label_size, 3, QApplication.font())
        # 设置文件名标签的大小和位置
        file_name_label.setFixedSize(self.label_size - 4, name_height)
        file_name_label.move(2, self.label_size)

        file_name_label.file_path = file_path

        # 设置标签固定大小
        label.setFixedSize(self.label_size, self.label_size + name_height)

        # 添加文件属性
        label.icon = False
        label.file_path = file_path
        label.file_name = file_name
        if os.path.exists(file_path):
            file_size_bytes  = os.path.getsize(file_path)
            label.file_size_bytes = file_size_bytes
            label.file_size = self.format_file_size(file_size_bytes)
            file_date_timestamp = os.path.getmtime(file_path)
            file_date = datetime.fromtimestamp(file_date_timestamp).strftime('%Y年%m月%d日，%H:%M:%S')
            label.file_date = file_date

            label.mouseDoubleClickEvent = partial(self.openFile, file_path=file_path)
        else:
            label.file_size_bytes = 0
            label.file_size = "文件不存在"
            label.file_date = "文件不存在"

        #绑定标签操作
        #左击
        label.mousePressEvent = partial(self.onLabelLeftClick, label=label)
        #右击
        label.setContextMenuPolicy(Qt.CustomContextMenu)
        label.customContextMenuRequested.connect(partial(self.showLabelMenu, label=label))
        # 绑定鼠标进入和离开的事件
        label.enterEvent = partial(self.setBackgroundColorOnEnter, label=label)
        label.leaveEvent = partial(self.resetBackgroundColorOnLeave, label=label)
        label.setParent(self.content_widget)
        label.hide()
        return label

    # 创建文件标签
    def createFileLabels(self, file_paths=None, use_cache=True):
        if file_paths is None:
            file_paths = self.file_paths
        for file_path in file_paths[:]:
            if use_cache and file_path in self.label_cache:
                label = self.label_cache[file_path]
                self.labels[file_path] = label
                continue
            # 创建标签
            label = self._createFileLabel(file_path)
            #添加标签
            if file_path in self.labels:
                # 如果标签已存在，先清除控件
                self.labels[file_path].deleteLater()
            self.labels[file_path] = label
        self.label_cache.update(self.labels)

    # 开始加载文件缩略图
    def startLoadingImages(self, threadpool, file_paths=None, use_cache=True):
        if file_paths is None:
            file_paths = self.file_paths.copy()
        if threadpool == self.threadpool0:
            for file_path in file_paths[:]:
                if self.labels[file_path].icon:
                    file_paths.remove(file_path)
        if len(file_paths) > 0:
            loder = StarImageLoader(self, threadpool, file_paths, use_cache)
            self.startLoadingImagesThreadpool.start(loder)

    # 更新布局
    def updateLayout(self):
        # 计算列数
        area_width = self.viewport().width() - 4*self.LABEL_SPACING # 保证左端至少有4倍间距的空白
        num_columns = max(1, 1 + (area_width - self.label_size) // (self.label_size + self.LABEL_SPACING))
        total_labels = len(self.labels)  # 获取标签数量
        if num_columns > total_labels or num_columns == 1:
            HORIZONTAL_SPACING = self.LABEL_SPACING
        else:
            HORIZONTAL_SPACING = round((area_width - num_columns * self.label_size) / num_columns)
        self.HORIZONTAL_SPACING = HORIZONTAL_SPACING
        row = -1
        # 计算label位置
        file_name_height_all = 0
        old_row = 0
        max_file_name_height = 0
        for index in range(total_labels):
            file_path = self.file_paths[index]
            label = self.labels[file_path]
            file_name_height = label.height() - self.label_size
            if file_name_height > max_file_name_height:
                max_file_name_height = file_name_height
            row = index // num_columns  # 计算当前行
            col = index % num_columns  # 计算当前列

            if row != old_row: # 当行数发生变化时，重新统计行最大文件名高度
                file_name_height_all += max_file_name_height
                max_file_name_height = 0
                old_row = row

            x = 4*self.LABEL_SPACING + col * (self.label_size + HORIZONTAL_SPACING)  # 计算x位置
            y = 2*self.LABEL_SPACING + row * (self.label_size + self.LABEL_SPACING) + file_name_height_all # 计算y位置

            label.pos = QPoint(x,y)
            label_rect = QRect(label.pos, label.size())
            self.labels_rect[(row,col)] = (label_rect, file_path)
        self.max_col = min(num_columns, total_labels)
        self.max_row = row + 1
        file_name_height_all += max_file_name_height
        self.content_widget.setMinimumSize(0, 4*self.LABEL_SPACING + self.max_row * (self.label_size + self.LABEL_SPACING) + file_name_height_all)
        self.lazy_load()

    # 改变显示文件
    def changeFile(self, file_paths=None):
        if file_paths is None:
            file_paths = []
        while self.startLoadingImagesThreadpool.activeThreadCount() > 0:
            time.sleep(0.1)
        self.threadpool.clear()
        self.threadpool0.clear()
        while self.threadpool.activeThreadCount() > 0:
            time.sleep(0.1)
        while self.threadpool0.activeThreadCount() > 0:
            time.sleep(0.1)
        hide_label_paths = list(set(self.file_paths) - set(file_paths))
        # QTimer.singleShot(0, lambda: [label.deleteLater() for label in old_labels])
        for visible_label_key in self.visible_labels_keys:
            label = self.labels[visible_label_key]
            label.hide()
        for hide_label_path in hide_label_paths:
            label = self.labels[hide_label_path]
            updateStyle(label, "border: none;")
            updateStyle(label, "background-color: transparent;")
            self.labels.pop(hide_label_path)
            self.select_labels_keys.discard(hide_label_path)
        if self.now_select_label_key is not None and self.now_select_label_key in hide_label_paths:
            self.now_select_label_key = None
        self.labels_rect.clear()
        self.ctrl_select_labels_keys.clear()
        self.visible_labels_keys.clear()

        new_file_paths = list(set(file_paths) - set(self.file_paths))
        self.file_paths = file_paths
        if len(new_file_paths) != 0:
            self.createFileLabels(new_file_paths)
        self.setSortKeyAndOrder(self.current_sort_key, self.current_sort_order)
        self.changeThumbnailSize(self.image_size)

    # 懒加载
    def lazy_load(self):
        self.threadpool0.clear()
        viewport = self.viewport()
        # 计算self.content_widget可见范围
        visible_rect = QRect(self.content_widget.mapFrom(self, viewport.rect().topLeft()), viewport.size())
        visible_labels_keys = self.get_rect_label(visible_rect)
        # 隐藏不可见label
        no_visible_labels_keys = self.visible_labels_keys - visible_labels_keys
        for no_visible_label_key in no_visible_labels_keys:
            self.labels[no_visible_label_key].hide()
        # 移动并显示可见label
        for visible_label_key in visible_labels_keys:
            label = self.labels[visible_label_key]
            label.move(label.pos)
            label.show()
        self.visible_labels_keys = visible_labels_keys
        self.startLoadingImages(self.threadpool0, list(visible_labels_keys))


    #——————————————————————框选文件————————————————————————

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.MousePress = True
            if not event.modifiers() & Qt.ControlModifier:
                for select_label_key in self.select_labels_keys:
                    updateStyle(self.labels[select_label_key], "background-color: transparent;")# 重置标签样式
                self.select_labels_keys.clear()
            # 如果按下ctrl
            else:
                self.now_select_labels_keys = self.select_labels_keys.copy() #记录按下ctrl时的文件选取状态
            self.origin = event.pos()

    def mouseMoveEvent(self, event):
        if self.MousePress:
            if event.buttons() & Qt.LeftButton:
                self.rubber_band.show() 
                # 设置橡皮筋框选的几何形状
                # QRect(self.origin, event.pos()) 创建一个矩形，从起点 `self.origin` 到当前鼠标位置 `event.pos()`
                # .normalized() 确保矩形是标准化的（即左上角为起点，右下角为终点），防止起点与终点位置不同导致的问题
                self.rubber_band.setGeometry(QRect(self.origin, event.pos()).normalized())
                # 获取橡皮筋的当前几何形状，用于后续操作
                self.selectLabelsInRect(self.rubber_band.geometry(), event.modifiers())
                mouse_pos_in_scroll_area = self.content_widget.mapToParent(event.pos())
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

    # 选中区域内的label
    def selectLabelsInRect(self, rubber_rect, modifiers):
        select_labels_keys = self.get_rect_label(rubber_rect)
        # 如果没按ctrl
        if not modifiers & Qt.ControlModifier:
            # 恢复未选中标签状态
            no_select_labels_keys = self.select_labels_keys - select_labels_keys 
            for no_select_label_key in no_select_labels_keys:
                updateStyle(self.labels[no_select_label_key], "background-color: transparent;")
            # 改变新增选中标签状态
            add_select_labels_keys = select_labels_keys - self.select_labels_keys
            for add_select_label_key in add_select_labels_keys:  
                updateStyle(self.labels[add_select_label_key], "background-color: #cde8ff;") # 高亮选中标签
            self.select_labels_keys = select_labels_keys
        # 如果按下ctrl
        else:
            # 恢复未选中标签状态
            no_ctrl_select_labels_keys = self.ctrl_select_labels_keys - select_labels_keys 
            for no_ctrl_select_label_key in no_ctrl_select_labels_keys:
                self.recover_label_select_status(self.labels[no_ctrl_select_label_key])
            # 改变新增选中标签状态
            add_ctrl_select_labels_keys = select_labels_keys - self.ctrl_select_labels_keys
            for add_ctrl_select_label_key in add_ctrl_select_labels_keys:
                self.change_label_select_status(self.labels[add_ctrl_select_label_key])
            self.ctrl_select_labels_keys = select_labels_keys

    # 切换状态
    def change_label_select_status(self, label):
        if label.file_path in self.now_select_labels_keys:
            updateStyle(label, "background-color: transparent;")
            self.select_labels_keys.discard(label.file_path)
        elif label.file_path not in self.now_select_labels_keys:
            updateStyle(label, "background-color: #cde8ff;")
            self.select_labels_keys.add(label.file_path)
    #恢复状态
    def recover_label_select_status(self, label):
        if label.file_path in self.now_select_labels_keys:
            updateStyle(label, "background-color: #cde8ff;")
            self.select_labels_keys.add(label.file_path)
        else :
            updateStyle(label, "background-color: transparent;")
            self.select_labels_keys.discard(label.file_path)
        
    #自动滚动
    def autoScroll(self, mouse_pos, auto=False):
        scroll_area_rect = self.rect()
        # 检查边缘位置和移动方向来决定是否滚动
        if mouse_pos.y() < scroll_area_rect.top():
            movement_scale = max(0.5, (mouse_pos.y() - scroll_area_rect.top())/50) # 计算滚动倍率
            move_value = round(movement_scale * self.SCROLL_DISTANCE_PER_FRAME) # 计算移动距离
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - move_value)  # 向上滚动
        elif mouse_pos.y() > scroll_area_rect.bottom():
            movement_scale = max(0.5, (mouse_pos.y() - scroll_area_rect.bottom())/50)
            move_value = round(movement_scale * self.SCROLL_DISTANCE_PER_FRAME)
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() + move_value)  # 向下滚动
        if mouse_pos.x() < scroll_area_rect.left():
            movement_scale = max(0.5, (mouse_pos.x() - scroll_area_rect.left())/50)
            move_value = round(movement_scale * self.SCROLL_DISTANCE_PER_FRAME)
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - move_value)  # 向左滚动
        elif mouse_pos.x() > scroll_area_rect.right():
            movement_scale = max(0.5, (mouse_pos.x() - scroll_area_rect.right())/50)
            move_value = round(movement_scale * self.SCROLL_DISTANCE_PER_FRAME)
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + move_value)  # 向右滚动

        if not auto:
            try:
                self.auto_scroll_timer.timeout.disconnect()
            except TypeError:
                pass
            self.auto_scroll_timer.timeout.connect(lambda: self.autoScroll(mouse_pos, True))
            if not self.auto_scroll_timer.isActive():
                self.auto_scroll_timer.start()

    def on_scroll(self, value):
        self.lazy_load()
        global_pos = QCursor.pos()
        local_pos = self.mapFromGlobal(global_pos)
        widget_pos = self.content_widget.mapFrom(self, local_pos)
        label = self.content_widget.childAt(widget_pos)
        if label and self.labels[label.file_path] != label: # 如果存在label并且是不是父label(是icon_label或file_name_label)
            label = label.parent() # 获取父label
        if label != self.now_hang_label:
            if self.now_hang_label:
                self.resetBackgroundColorOnLeave(value, self.now_hang_label)
            if label:
                if label.file_path not in self.select_labels_keys:
                    updateStyle(label, "background-color: #e5f3ff;")
                self.now_hang_label = label

        if self.MousePress:
            # 将pos修正到widget内
            x = max(1, min(local_pos.x(), self.width() - 1))
            y = max(1, min(local_pos.y(), self.height() - 1))
            widget_pos = self.content_widget.mapFrom(self, QPoint(x, y))
            self.rubber_band.setGeometry(QRect(self.origin, widget_pos).normalized())
            self.selectLabelsInRect(self.rubber_band.geometry(), QApplication.keyboardModifiers())
        self.update()


    #————————————————————右键菜单显示——————————————————————

    def showContextMenu(self, pos):
        for select_label_key in self.select_labels_keys:
            updateStyle(self.labels[select_label_key], "background-color: transparent;")# 重置标签样式
        self.select_labels_keys.clear()
        context_menu = QMenu(self)
        self.addViewMenu(context_menu)  # 添加查看菜单
        self.addSortMenu(context_menu)   # 添加排序菜单
        select_all_action = QAction("全选", self)  
        select_all_action.triggered.connect(self.select_all_file)
        context_menu.addAction(select_all_action)

        scroll_area_global_pos = self.mapToGlobal(QPoint(0, 0))
        pos = self.content_widget.mapToParent(pos)
        global_pos = scroll_area_global_pos + pos
        context_menu.exec_(global_pos)

    def addViewMenu(self, context_menu):
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

    def addSortMenu(self, context_menu):
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

        sort_menu.addAction(name_action)
        sort_menu.addAction(size_action)
        sort_menu.addAction(date_action)

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

    # 全选
    def select_all_file(self):
        self.select_labels_keys = set(self.file_paths)
        for label in self.labels.values():
            updateStyle(label, "background-color: #cde8ff;")


    #————————————————————右键菜单功能——————————————————————

    #改变缩略图大小
    def changeThumbnailSize(self, size, level=None):
        if level is not None:
            self.current_image_size = level
            config.set('FileShowArea', 'current_image_size', level)  # 更新config对象
            save_config()
        self.image_size = size
        self.LABEL_INNER_SPACING = int(size * self.SPACING_RATE)
        self.label_size = self.image_size + 2*self.LABEL_INNER_SPACING
        while self.startLoadingImagesThreadpool.activeThreadCount() > 0:
            time.sleep(0.1)
        self.threadpool.clear()  # 清空当前线程池中的任务
        font = QFont()
        font.setFamily("Verdana")  # 首选 Verdana
        font.setStyleHint(QFont.SansSerif)  # 如果 Verdana 不可用，使用无衬线字体
        for label in self.labels.values():
            if label.width() == self.label_size:
                continue
            label.icon = False
            file_name_label = label.findChild(QLabel, "file_name_label")
            file_name = file_name_label.text()
            name_height = self.calculate_name_height(file_name, self.label_size, 3, font)
            label.setFixedSize(self.label_size, self.label_size + name_height)
            file_name_label.setFixedSize(self.label_size - 4, name_height)
            file_name_label.move(2, self.label_size)
            icon_label = label.findChild(QLabel, "icon_label")
            icon_label.move(self.LABEL_INNER_SPACING, self.LABEL_INNER_SPACING)
            icon_label.setFixedSize(self.image_size, self.image_size)
            pixmap = icon_label.pixmap()
            resized_pixmap = pixmap.scaled(self.image_size, self.image_size, Qt.KeepAspectRatio)  # 调整宽高
            icon_label.setPixmap(resized_pixmap)
        self.updateLayout()
        self.startLoadingImages(self.threadpool)  # 重新加载当前文件夹中的图片
    
    #改变排序方式
    def setSortKeyAndOrder(self, action, value):
        if action == "key":
            self.current_sort_key = value
            config.set('FileShowArea', 'current_sort_key', value)  # 更新config对象
        if action == "order":
            self.current_sort_order = value  # 更新当前排序顺序
            config.set('FileShowArea', 'current_sort_order', value)  # 更新config对象
        save_config()  # 保存配置

        if self.current_sort_key == "name":
            self.file_paths.sort(key=lambda path: self.labels[path].file_name, reverse=(self.current_sort_order == "desc"))
        elif self.current_sort_key == "size":
            self.file_paths.sort(key=lambda path: self.labels[path].file_size_bytes, reverse=(self.current_sort_order == "desc"))
        elif self.current_sort_key == "date":
            self.file_paths.sort(key=lambda path: self.labels[path].file_date, reverse=(self.current_sort_order == "desc"))

        self.updateLayout()  # 更新布局以反映新的顺序
        while self.startLoadingImagesThreadpool.activeThreadCount() > 0:
            time.sleep(0.1)
        self.threadpool.clear()
        self.startLoadingImages(self.threadpool)


    #————————————————————文件相关功能——————————————————————
    
    #左击选中
    def onLabelLeftClick(self, event, label):
        if event.button() == Qt.LeftButton:
            if event.modifiers() & Qt.ControlModifier:
                self.now_select_labels_keys = self.select_labels_keys.copy() # 快照
                self.change_label_select_status(label)
            else:
                for select_label_key in self.select_labels_keys:
                    updateStyle(self.labels[select_label_key], "background-color: transparent;")# 重置标签样式
                self.select_labels_keys.clear()
                updateStyle(label, "background-color: #cde8ff;")
                self.select_labels_keys.add(label.file_path)
            if self.now_select_label_key is not None:
                updateStyle(self.labels.get(self.now_select_label_key), "border: none;")
            self.now_select_label_key = label.file_path
            updateStyle(label, "border: 1px solid #99d1ff;")
            # if not self.isMouseOnThumbnail(event.pos(), label): # 如果鼠标不在缩略图上
            self.MousePress = True
            parent_pos = label.mapTo(self.content_widget, event.pos())
            self.origin = parent_pos

    # 双击打开文件
    def openFile(self, event, file_path, default=False):  
        # 支持的图片格式  
        supported_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp']  
        
        # 检查文件扩展名  
        ext = os.path.splitext(file_path)[1].lower()  
        
        if not default and ext in supported_formats:  
            # 文件是图片，使用MultiImageViewer显示
            image_viewer = MultiImageViewer()  # 保存为实例变量以防止被垃圾回收
            self.image_viewers.append(image_viewer)
            image_viewer.destroyed.connect(lambda: self.image_viewers.remove(image_viewer))
            image_files = []
            # 筛选有效图片文件  
            for image_path in self.file_paths:  
                # 检查文件是否存在  
                if not os.path.exists(image_path):  
                    continue  
                    
                # 检查文件扩展名  
                ext = os.path.splitext(image_path)[1].lower()  
                if ext in supported_formats:  
                    image_files.append(image_path) 
            image_viewer.load_image_files(image_files)  
            
            # 找到当前文件在列表中的索引  
            try:  
                index = image_files.index(file_path)  
                image_viewer.show_image_at_index(index)  
            except ValueError:  
                # 如果file_path不在列表中（异常情况），显示第一张  
                print(f"警告：文件 {file_path} 不在文件列表中")  
                
            # 显示图片查看器  
            image_viewer.show()  
        else:  
            # 非图片文件，使用默认应用打开  
            try:  
                os.startfile(file_path)  
            except Exception as e:  
                print(f"无法打开文件 {file_path}: {e}")  
        
    # 右键菜单
    def showLabelMenu(self, pos, label):
        if label.file_path not in self.select_labels_keys: # 如果label未被选中
            for select_label_key in self.select_labels_keys:
                updateStyle(self.labels[select_label_key], "background-color: transparent;")# 重置标签样式
            self.select_labels_keys.clear()
            if not self.isMouseOnThumbnail(pos, label):
                parent_pos = label.mapTo(self.content_widget, pos)
                self.content_widget.customContextMenuRequested.emit(parent_pos)
                return

        updateStyle(label, "background-color: #cde8ff;")
        self.select_labels_keys.add(label.file_path)
        if self.now_select_label_key is not None:
            updateStyle(self.labels.get(self.now_select_label_key), "border: none;")
        self.now_select_label_key = label.file_path
        updateStyle(label, "border: 1px solid #99d1ff;")
        context_menu = QMenu(self)
        properties_action = QAction("属性", self)
        properties_action.triggered.connect(lambda: self.displayImageProperties(label))
        context_menu.addAction(properties_action)


        if os.path.exists(label.file_path):
            file_menu = context_menu.addMenu("文件操作")

            open_file_action = QAction("系统默认方式打开", self)
            open_file_action.triggered.connect(lambda: self.openFile(None, label.file_path, default=True))
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
            self.DictManage.save_notify()
            self.labels_rect.clear()
            self.visible_labels_keys.clear()
            self.updateLayout()

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
                self.DictManage.rename_entity('file', file_path, target_path)
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
            # 分离文件名和扩展名（适用于文件，文件夹没有扩展名）
            name, ext = os.path.splitext(base_name)
            counter = 1
            # 循环生成新的名称，直到找到不存在的路径
            while os.path.exists(target_path):
                new_name = f"{name}_{counter}{ext}"  # 在文件名后加数字后缀
                target_path = os.path.join(target_folder, new_name).replace('\\', '/')
                counter += 1

        # 如果是文件夹，创建新文件夹
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
        file_paths = self.get_all_files(target_folder)
        for file_path in file_paths:
            old_file_path = file_path.replace(target_folder, parent_path)
            # 修改文件路径
            self.DictManage.rename_entity('file', old_file_path, file_path)


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
                self.DictManage.delete_entity('file', file_path)
                if os_delete and os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"删除文件 {file_path} 时出错: {e}")
        self.DictManage.save_notify()

    # 刷新
    def refresh(self):
        # 不使用缓存加载
        self.createFileLabels(list(self.select_labels_keys), use_cache=False)
        self.startLoadingImages(self.threadpool0, use_cache=False)
        self.updateLayout()


    # 选中所有失效文件
    def selectAllUnvalidFile(self):
        for file_path in self.select_labels_keys:
            label = self.labels[file_path]
            updateStyle(label, "background-color: transparent;")
        self.select_labels_keys.clear()
        for file_path in self.file_paths:
            if not os.path.exists(file_path):
                self.select_labels_keys.add(file_path)
                label = self.labels[file_path]
                updateStyle(label, "background-color: #cde8ff;")

    # 文件修复
    def repairFile(self):
        # 选择文件所在文件夹
        options = QFileDialog.Options()
        options |= QFileDialog.ShowDirsOnly
        folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹", options=options)
        if not folder_path:
            return
        # 递归遍历文件夹中的所有文件的文件名
        
        fileName2filePath = {}
        for root, dirs, files in os.walk(folder_path):
            for file in files+dirs:
                file_path = os.path.join(root, file).replace('\\', '/')
                if file in fileName2filePath:
                    fileName2filePath[file].append(file_path)
                else:
                    fileName2filePath[file] = [file_path]

        # 创建对话框窗口
        dialog = QDialog(self)
        dialog.setWindowTitle("选择修复文件")
        dialog.resize(800, 600)
        
        # 主布局
        main_layout = QVBoxLayout(dialog)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        # 按钮布局
        button_layout = QHBoxLayout()
        confirm_button = QPushButton("确认修复")
        cancel_button = QPushButton("取消")
        button_layout.addWidget(confirm_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)
        font = QFont()
        font.setFamily("Verdana")  # 首选 Verdana
        font.setStyleHint(QFont.SansSerif)  # 如果 Verdana 不可用，使用无衬线字体
        # 为每个失效文件创建选择界面
        for file in self.select_labels_keys:
            if os.path.exists(file):
                continue
                
            file_name = os.path.basename(file)
            if file_name in fileName2filePath:
                # 创建分组标题
                group_label = QLabel(f"修复文件: {file_name}")
                group_label.setStyleSheet("font-weight: bold; background-color: #f0f0f0; padding: 5px;")
                scroll_layout.addWidget(group_label)
                
                # 创建水平布局的容器
                container = QWidget()
                layout = QHBoxLayout(container)
                layout.setSpacing(10)
                
                # 为每个候选文件创建显示项
                for candidate_path in fileName2filePath[file_name]:
                    # 创建垂直布局的文件项
                    file_widget = QWidget()
                    file_layout = QVBoxLayout(file_widget)
                    file_layout.setAlignment(Qt.AlignCenter)
                    
                    # 图片预览
                    # image_label = self._createFileLabel(file_path, font)
                    image_label = QLabel()
                    image_label.setAlignment(Qt.AlignCenter)
                    # image_label.setStyleSheet("border: 1px solid #ccc;")
                    image_label.setFixedSize(200, 200)
                    
                    # 加载图片缩略图
                    pixmap = QPixmap(candidate_path)
                    pixmap = pixmap.scaled(self.image_size, self.image_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    if not pixmap.isNull():
                        image_label.setPixmap(pixmap)
                    
                    # 文件路径标签
                    path_label = QLabel(os.path.dirname(candidate_path))
                    path_label.setAlignment(Qt.AlignCenter)
                    path_label.setStyleSheet("font-size: 11px; color: #666;")
                    path_label.setWordWrap(True)
                    path_label.setMaximumWidth(200)
                    
                    # 选择按钮
                    select_button = QRadioButton("选择此文件")
                    select_button.candidate_path = candidate_path
                    select_button.original_path = file
                    if candidate_path == fileName2filePath[file_name][0]:
                        select_button.setChecked(True)
                    
                    # 添加到布局
                    file_layout.addWidget(image_label)
                    file_layout.addWidget(path_label)
                    file_layout.addWidget(select_button, alignment=Qt.AlignCenter)
                    
                    layout.addWidget(file_widget)
                layout.addStretch()
                # 添加到滚动区域
                scroll_layout.addWidget(container)
        
        # 右侧添加弹簧
        # scroll_layout.addStretch()
        
        # 按钮信号连接
        def on_confirm():
            # 查找所有选中的单选按钮
            for widget in scroll_content.findChildren(QRadioButton):
                if widget.isChecked():
                    # 执行修复操作
                    self.DictManage.rename_entity('file', widget.original_path, widget.candidate_path)
            self.DictManage.save_notify()
            dialog.accept()
            
        confirm_button.clicked.connect(on_confirm)
        cancel_button.clicked.connect(dialog.reject)
        
        dialog.exec_()


    # 打开文件所在位置
    def openFolderAction(self, label):
        file_path = label.file_path
        file_path = file_path.replace('/', '\\')
        subprocess.Popen(f'explorer /select,"{file_path}"')

    #显示图片属性
    def displayImageProperties(self, label):
        # 创建一个自定义窗口
        widget = QWidget()
        self.child_widget.append(widget)
        widget.destroyed.connect(lambda: self.child_widget.remove(widget))
        widget.setWindowTitle(f"{label.file_name} 属性")
        widget.resize(500, 300)

        # 创建一个文本编辑器，显示文件属性
        text_edit = QTextEdit(widget)
        text_edit.setReadOnly(True)  # 设置为只读

        # 设置字体
        font = QFont("Arial", 12)  # 使用 Arial 字体，大小为 12
        text_edit.setFont(font)

        # 获取文件标签
        tags = self.relation_graph['file'].get(label.file_path, {}).get('tag', set())
        tags_str = ", ".join(list(tags)) if tags else "无标签"

        # 显示文件信息
        message = (
            f"<b>文件名:</b>&nbsp; {label.file_name}<br><br>"
            f"<b>文件路径: </b>&nbsp; {label.file_path}<br><br>"
            f"<b>文件大小: </b>&nbsp; {label.file_size}<br><br>"
            f"<b>修改时间: </b>&nbsp; {label.file_date}<br><br>"
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



class MainFileShowArea(FileShowArea):
    def __init__(self, MainWindow, file_paths=None):
        super().__init__(file_paths)
        self.MainWindow = MainWindow

    def showLabelMenu(self, pos, label):
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
    def __init__(self, file_paths=None):
        super().__init__(file_paths)
        self.setAcceptDrops(True)
        self.acceptFloder = config.getboolean('TagFileShowArea', 'acceptFloder', fallback=False)

    def showLabelMenu(self, pos, label):
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
            self.labels[select_label_key].setParent(None)
            self.labels.pop(select_label_key)
            self.file_paths.remove(select_label_key)
            self.visible_labels_keys.discard(select_label_key)
            self.labels_rect.clear()
        self.select_labels_keys.clear()
        if len(self.file_paths) == 0:
            self.now_select_label_key = None
        else:
            self.now_select_label_key = self.labels[self.file_paths[0]].file_path
        self.now_hang_label = None
        self.updateLayout()



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
                    file_paths += self.get_all_files(path)
                else:
                    file_paths.append(path)
        else:
            file_paths = paths
        self.file_paths += file_paths
        self.createFileLabels(file_paths)
        self.updateLayout()
        self.startLoadingImages(self.threadpool, file_paths)