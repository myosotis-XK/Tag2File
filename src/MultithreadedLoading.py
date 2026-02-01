from PyQt5.QtCore import QRunnable, Qt, QPointF, QThreadPool
from PyQt5.QtGui import QPixmap, QPainterPath, QPen, QFont, QColor, QPainter, QImage
from PyQt5.QtWidgets import QLabel
from PIL import Image
import os
from .utils import get_cache_path, thumbnailExtractor
from .Iconsource import *

class StarImageLoader(QRunnable):
    def __init__(self, fathet, threadpool:QThreadPool, file_paths:list=None, use_cache=True):
        super().__init__()
        self.father = fathet
        self.threadpool = threadpool
        if file_paths is None:
            file_paths = []
        self.file_paths = file_paths
        self.use_cache = use_cache
        self.runing = True

    def change_pixmap_size(self, file_path):
        file_item = self.father.file_items[file_path]
        pixmap = file_item.icon_source['current'].source
        pixmap = pixmap.scaled(self.father.image_size, self.father.image_size, Qt.KeepAspectRatio)
        file_item.icon_source['current'] = PixmapIcon(pixmap)
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
            self.change_pixmap_size(file_path)
            loader = ImageLoader(self.father, file_path)
            self.threadpool.start(loader)

    def check_cache(self, file_path):
        file_item = self.father.file_items[file_path]
        image_size = self.father.image_size
        if image_size in file_item.icon_source:
            pixmap = file_item.icon_source[image_size].source
            self.updateLabelIcon(pixmap, file_path)
            return True

        # 检查磁盘缓存
        cache_path = get_cache_path(file_path, image_size)
        if os.path.exists(cache_path):
            try:
                pixmap = QPixmap(cache_path)
            except Exception as e:
                try:  
                    # 考虑记录删除的情况  
                    if os.path.exists(cache_path):  # 再次检查避免竞态条件  
                        os.remove(cache_path)  
                        print(f"已删除损坏的缓存文件: {cache_path}")  
                except Exception as del_err:  
                    print(f"无法删除损坏的缓存: {del_err}")  
                    pass
                pixmap = None
            self.updateLabelIcon(pixmap, file_path)
            return True
        if not os.path.exists(file_path):
            pixmap = QPixmap(self.father.image_size, self.father.image_size)
            pixmap.fill(Qt.transparent)
            self.updateLabelIcon(pixmap, file_path)

        return False

    def updateLabelIcon(self, pixmap, file_path):
        file_item = self.father.file_items[file_path]
        file_item.icon = True
        file_item.icon_source[self.father.image_size] = PixmapIcon(pixmap)
        if not os.path.exists(file_path):
            if not pixmap:
                pixmap = QPixmap(self.father.image_size, self.father.image_size)
                pixmap.fill(Qt.transparent)
            pixmap = self.draw_text_on_pixmap(pixmap, "文件不存在")
        if pixmap:
            file_item.icon_source['current'] = PixmapIcon(pixmap)
            label = self.father.labels.get(file_path)
            if label:
                icon_label = label.findChild(QLabel)
                file_item.apply(icon_label)
        else:
            self.change_pixmap_size(file_path)

    def draw_text_on_pixmap(self, pixmap, text):
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

    def __init__(self, father, file_path:str):
        super().__init__()
        self.father = father
        self.max_size = father.image_size
        self.file_path = file_path
    def run(self):
        try:
            pixmap = None
            file_item = self.father.file_items[self.file_path]
            file_item.icon = True
            pil_image = thumbnailExtractor.extract_thumbnail(self.file_path, self.max_size)
            if pil_image:
                pixmap = self.pil_to_pixmap(pil_image)
            if pixmap:
                file_item.icon_source['current'] = PixmapIcon(pixmap)
                label = self.father.labels.get(self.file_path)
                if label:
                    icon_label = label.findChild(QLabel, "icon_label")
                    file_item.apply(icon_label)
                # 将缩略图存入缓存
                self.save_to_disk_cache(pixmap)
            file_item.icon_source[self.max_size] = PixmapIcon(pixmap)

        except Exception as e:
            print(f"加载文件 {self.file_path} 时出现错误: {e}")

    def pil_to_pixmap(self, pil_image: Image.Image) -> QPixmap:
        """将 PIL Image 转换为 QPixmap"""
        try:
            if pil_image.mode != 'RGBA':
                pil_image = pil_image.convert('RGBA')
            qimage = QImage(
                pil_image.tobytes(),
                pil_image.width,
                pil_image.height,
                pil_image.width * 4,
                QImage.Format_RGBA8888
            )
            return QPixmap.fromImage(qimage)
        except Exception as e:
            print(f"转换 PIL 到 QPixmap 失败: {e}")
            return None

    def save_to_disk_cache(self, pixmap):
        cache_path = get_cache_path(self.file_path, self.max_size)
        pixmap.save(cache_path, "PNG")