from PyQt5.QtCore import QRunnable, Qt, QPointF, QThreadPool
from PyQt5.QtGui import QPixmap, QPainterPath, QPen, QFont, QColor, QPainter
from PyQt5.QtWidgets import QLabel
from PIL import Image
import os
from .utils import get_cache_path, thumbnailExtractor
from .Iconsource import *

class StarImageLoader(QRunnable):
    def __init__(self, fathet, threadpool:QThreadPool, signalEmit, file_paths:list=None, use_cache=True):
        super().__init__()
        self.father = fathet
        self.image_size = fathet.image_size
        self.threadpool = threadpool
        if file_paths is None:
            file_paths = []
        self.file_paths = file_paths
        self.use_cache = use_cache
        self.runing = True
        self.signalEmit = signalEmit

    def change_current_pixmap_size(self, file_path):
        file_item = self.father.file_items[file_path]
        source = file_item.icon_source['current'].source
        if isinstance(source, QPixmap):
            pixmap = source.scaled(self.image_size, self.image_size, Qt.KeepAspectRatio)
            source = PixmapIcon(pixmap)
            file_item.icon_source['current'] = source
        label = self.father.labels.get(file_path)
        if label:
            icon_label = label.findChild(QLabel)
            file_item.apply(icon_label)

    def run(self):
        for file_path in self.file_paths:
            if not self.runing:
                break
            if (self.use_cache or not os.path.exists(file_path)) and self.check_cache(file_path):
                continue
            self.change_current_pixmap_size(file_path)
            loader = ImageLoader(self.father, file_path, self.signalEmit)
            self.threadpool.start(loader)

    def check_cache(self, file_path):
        # 检查内存缓存
        file_item = self.father.file_items[file_path]
        image_size = self.image_size
        if image_size in file_item.icon_source:
            self.updateLabelIcon(file_item)
            return True

        # 检查磁盘缓存
        cache_path = get_cache_path(file_path, image_size)
        if os.path.exists(cache_path):
            try:
                pixmap = QPixmap(cache_path)
                icon_source = PixmapIcon(pixmap)
                file_item.icon_source[image_size] = icon_source
                self.updateLabelIcon(file_item)
                return True
            except Exception as e:
                try:
                    print(f"缓存文件{cache_path}无法加载: {e}")
                    if os.path.exists(cache_path):  # 再次检查避免竞态条件  
                        os.remove(cache_path)  
                        print(f"已删除损坏的缓存文件: {cache_path}")  
                except Exception as del_err:  
                    print(f"错误缓存文件处理失败: {del_err}")

        return False

    def updateLabelIcon(self, file_item):
        file_path = file_item.file_path
        file_item.icon = True
        pixmap = file_item.icon_source[self.image_size].source
        if not os.path.exists(file_path):
            pixmap = self.draw_text_on_pixmap(pixmap, "文件不存在")
        file_item.icon_source['current'] = PixmapIcon(pixmap)

        label = self.father.labels.get(file_path)
        if label:
            icon_label = label.findChild(QLabel)
            file_item.apply(icon_label)

    @staticmethod
    def draw_text_on_pixmap(pixmap, text):
        pixmap = pixmap.copy()
        painter = QPainter(pixmap)
        
        # 应用半透明的暗色遮罩
        painter.fillRect(pixmap.rect(), QColor(0, 0, 0, 64))  # 黑色半透明遮罩

        rect = pixmap.rect()
        
        # 计算自适应的字体大小
        font_size = min(rect.width(), rect.height()) // 6
        font = QFont("Arial", font_size)
        font.setBold(True)
        painter.setFont(font)

        # 设置文字颜色和描边
        text_color = QColor("red")
        outline_color = QColor("black")

        # 计算文本边界以确保居中
        text_rect = painter.boundingRect(rect, Qt.AlignCenter, text)

        # 创建文字路径并居中
        path = QPainterPath()
        path.addText(QPointF(rect.center().x() - text_rect.width() / 2,
                            rect.center().y() + text_rect.height() / 4), font, text)

        # 先绘制白色轮廓
        painter.setPen(QPen(outline_color, font_size // 10))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

        # 再绘制红色文字
        painter.setPen(Qt.NoPen)
        painter.setBrush(text_color)
        painter.drawPath(path)

        painter.end()
        return pixmap

class ImageLoader(QRunnable):
    """负责加载单个文件图标的任务类"""
    def __init__(self, father, file_path:str, signalEmit):
        super().__init__()
        self.father = father
        self.image_size = father.image_size
        self.file_path = file_path
        self.signalEmit = signalEmit

    def run(self):
        try:
            file_path = self.file_path
            image_size = self.image_size
            source = None
            file_item = self.father.file_items[file_path]
            file_item.icon = True
            thumbnailSequence = thumbnailExtractor.extract_thumbnail(file_path, image_size)
            if thumbnailSequence:
                if thumbnailSequence.animated:
                    source = PixmapSequenceIcon(thumbnailSequence)
                else:
                    image = thumbnailSequence.frames[0]
                    source = PixmapIcon(image)
                    self.save_to_disk_cache(image)

            if source is None:
                source = get_file_init_icon_source(file_path, image_size)

            file_item.icon_source['current'] = source
            file_item.icon_source[image_size] = source
            if isinstance(source, PixmapIcon):
                label = self.father.labels.get(self.file_path)
                if label:
                    icon_label = label.findChild(QLabel, "icon_label")
                    file_item.apply(icon_label)
            elif isinstance(source, PixmapSequenceIcon):
                self.signalEmit.finished.emit(file_path)
            

        except Exception as e:
            print(f"加载文件 {self.file_path} 时出现错误: {e}")

    def save_to_disk_cache(self, image: Image.Image):
        """将图像保存到磁盘缓存"""
        cache_path = get_cache_path(self.file_path, self.image_size)
        image.save(cache_path, "PNG")