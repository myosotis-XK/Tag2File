import os
from PIL import Image
from PyQt5.QtCore import QRunnable, Qt, QThreadPool
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QLabel

from src.utils import get_cache_path, thumbnailExtractor
from src.models import PixmapIcon, PixmapSequenceIcon, get_file_init_icon, draw_text_on_pixmap

class StarImageLoader(QRunnable):
    def __init__(self, fathet, threadpool:QThreadPool, file_paths:list=None, use_cache=True):
        super().__init__()
        self.father = fathet
        self.image_size = fathet.image_size
        self.signalEmit = fathet.signalEmit
        self.threadpool = threadpool
        if file_paths is None:
            file_paths = []
        self.file_paths = file_paths
        self.use_cache = use_cache

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
        father = self.father
        signalEmit = self.signalEmit
        threadpool = self.threadpool
        use_cache = self.use_cache
        change_current_pixmap_size = self.change_current_pixmap_size
        check_cache = self.check_cache

        for file_path in self.file_paths:
            if (use_cache or not os.path.exists(file_path)) and check_cache(file_path):
                continue
            change_current_pixmap_size(file_path)
            loader = ImageLoader(father, file_path, signalEmit)
            threadpool.start(loader)

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
        icon = file_item.icon_source[self.image_size]
        if isinstance(icon, PixmapSequenceIcon):
            file_item.icon_source['current'] = icon
            self.signalEmit.finished.emit(file_path)
            return
        pixmap = icon.source
        if not os.path.exists(file_path):
            pixmap = draw_text_on_pixmap(pixmap, "文件不存在")
        file_item.icon_source['current'] = PixmapIcon(pixmap)

        label = self.father.labels.get(file_path)
        if label:
            icon_label = label.findChild(QLabel)
            file_item.apply(icon_label)

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
            icon = None
            file_item = self.father.file_items[file_path]
            file_item.icon = True
            thumbnailSequence = thumbnailExtractor.extract_thumbnail(file_path, image_size)
            if thumbnailSequence:
                if thumbnailSequence.animated:
                    icon = PixmapSequenceIcon(thumbnailSequence)
                else:
                    image = thumbnailSequence.frames[0]
                    icon = PixmapIcon(image)
                    self.save_to_disk_cache(image)

            if icon is None:
                icon = get_file_init_icon(file_path, image_size)
                if not os.path.exists(file_path):
                    icon = PixmapIcon(draw_text_on_pixmap(icon.source, "文件不存在"))

            file_item.icon_source['current'] = icon
            file_item.icon_source[image_size] = icon
            self.signalEmit.finished.emit(file_path)
        except KeyError:
            pass
        except Exception as e:
            print(f"加载文件 {self.file_path} 时出现错误: {e}")

    def save_to_disk_cache(self, image: Image.Image):
        """将图像保存到磁盘缓存"""
        cache_path = get_cache_path(self.file_path, self.image_size)
        image.save(cache_path, "PNG")