from PyQt5.QtCore import QRunnable, Qt, QPointF
from PyQt5.QtGui import QPixmap, QPainterPath, QPen, QFont, QColor, QPainter, QImage
from PyQt5.QtWidgets import QLabel
from PIL import Image, UnidentifiedImageError
from io import BytesIO
import os
from mutagen.mp3 import MP3  
from mutagen.id3 import ID3
from mutagen.mp4 import MP4, MP4Cover
import cv2
import hashlib
import mimetypes
import time


class StarImageLoader(QRunnable):
    def __init__(self, fathet, threadpool, file_paths=None, use_cache=True):
        super().__init__()
        self.father = fathet
        self.threadpool = threadpool
        if file_paths is None:
            file_paths = []
        self.file_paths = file_paths
        self.use_cache = use_cache
        self.runing = True

    def run(self):
        for file_path in self.file_paths:
            if not self.runing:
                break
            if (self.use_cache or not os.path.exists(file_path)) and self.check_cache(file_path):
                continue
            loader = ImageLoader(self.father, file_path)
            self.threadpool.start(loader)

    def check_cache(self, file_path):
        # 检查缓存中是否存在该尺寸的缩略图
        if file_path in self.father.image_cache[self.father.image_size]:
            # 如果存在，则直接更新图标
            pixmap = self.father.image_cache[self.father.image_size][file_path]
            if pixmap:
                self.updateLabelIcon(pixmap, file_path)
                time.sleep(0.01)
            return True
        # 检查磁盘缓存
        cache_path = self.father.get_cache_path(file_path)
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
            if pixmap:
                self.updateLabelIcon(pixmap, file_path)
                time.sleep(0.01)
            return True
        return False

    def updateLabelIcon(self, pixmap, file_path):
        if pixmap is None:
            pixmap = QPixmap(self.father.image_size, self.father.image_size)
        label = self.father.labels[file_path]
        file_item = self.father.file_items[file_path]
        file_item.icon = True
        icon_label = label.findChild(QLabel)
        self.father.image_cache[self.father.image_size][label.file_path] = pixmap
        if not os.path.exists(file_path):
            pixmap = self.draw_text_on_pixmap(pixmap, "文件不存在")
        icon_label.setPixmap(pixmap)
        file_item.pixmap['current'] = pixmap

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

    def __init__(self, father, file_path):
        super().__init__()
        self.father = father
        self.max_size = father.image_size
        self.file_path = file_path
        self.cache_dir = father.cache_dir
    def run(self):
        try:
            pixmap = None
            mime_type, _ = mimetypes.guess_type(self.file_path)
            if mime_type:
                if mime_type.startswith('image'):
                    pixmap = self.loadImageFile()
                elif mime_type == 'audio/mpeg':
                    pixmap = self.loadMp3Cover()
                elif mime_type == 'video/mp4':
                    pixmap = self.loadMp4Cover()
            label = self.father.labels[self.file_path]
            file_item = self.father.file_items[self.file_path]
            file_item.icon = True
            icon_label = label.findChild(QLabel)
            if pixmap:
                # 将图片按 image_size 的大小缩放，但保持原始比例  
                pixmap = pixmap.scaled(self.max_size, self.max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                icon_label.setPixmap(pixmap)
                file_item.pixmap['current'] = pixmap
                # 将缩略图存入缓存
                self.save_to_disk_cache(pixmap)
            self.father.image_cache[self.max_size][label.file_path] = pixmap

        except Exception as e:
            print(f"加载文件 {self.file_path} 时出现错误: {e}")

    def get_cache_path(self):
        # 使用文件路径的哈希作为缓存文件名，以避免文件名冲突
        file_hash = hashlib.md5(self.file_path.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{file_hash}_{self.max_size}.png")

    def save_to_disk_cache(self, pixmap):
        cache_path = self.get_cache_path()
        pixmap.save(cache_path, "PNG")

    def loadImageFile(self):
        """处理图片文件"""
        try:
            # 高速
            # # 创建 QImageReader 实例
            # image_reader = QImageReader(self.file_path)
            # image_reader.setAutoTransform(True)
            # # 获取图像的原始宽度和高度
            # original_width = image_reader.size().width()
            # original_height = image_reader.size().height()
            
            # # 计算缩略图尺寸，保持长宽比
            # if original_width > original_height:
            #     # 如果宽度大于高度，缩放宽度到 max_size
            #     new_width = self.max_size
            #     new_height = int((self.max_size / original_width) * original_height)
            # else:
            #     # 如果高度大于宽度，缩放高度到 max_size
            #     new_height = self.max_size
            #     new_width = int((self.max_size / original_height) * original_width)
            # # 设置缩放后的尺寸
            # image_reader.setScaledSize(QSize(new_width, new_height))
            # return QPixmap.fromImage(image_reader.read())

            # 流畅
            with Image.open(self.file_path) as img:
                img.thumbnail((self.max_size, self.max_size))
                if 'icc_profile' in img.info:
                    del img.info['icc_profile']
                img_byte_array = BytesIO()
                img.save(img_byte_array, format='PNG')
                img_byte_array.seek(0)
                pixmap = QPixmap()
                pixmap.loadFromData(img_byte_array.getvalue())
                return pixmap

        except (UnidentifiedImageError, OSError) as e:
            print(f"无法打开图像文件 {self.file_path}: {e}")
            return None

    def loadMp3Cover(self):
        """处理 MP3 文件并提取封面"""
        try:
            audio = MP3(self.file_path, ID3=ID3)
            if audio:
                for tag in audio.tags.keys():
                    if tag.startswith('APIC:'):
                        apic = audio.tags[tag]
                        img_byte_array = BytesIO(apic.data)
                        pixmap = QPixmap()
                        pixmap.loadFromData(img_byte_array.getvalue())
                        return pixmap
        except Exception as e:
            print(f"提取 MP3 封面失败 {self.file_path}: {e}")
            return None

    def loadMp4Cover(self):  
        """处理 MP4 文件并提取封面为 QPixmap"""  
        try:  
            # 使用 OpenCV 打开视频文件  
            video = cv2.VideoCapture(self.file_path)  
            
            # 检查视频是否成功打开  
            if not video.isOpened():  
                print(f"无法打开视频文件 {self.file_path}")  
                return None  
            
            # 读取第一帧  
            success, frame = video.read()  
            
            if success:  
                # 将 OpenCV 的 BGR 格式转换为 RGB  
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  
                
                # 将 numpy 数组转换为 QImage  
                height, width, channels = frame_rgb.shape  
                bytes_per_line = channels * width  
                q_img = QImage(frame_rgb.data, width, height, bytes_per_line, QImage.Format_RGB888)  
                
                # 转换为 QPixmap  
                pixmap = QPixmap.fromImage(q_img)  
                
                # 释放视频资源  
                video.release()  
                
                return pixmap  
            else:  
                print(f"无法读取视频帧 {self.file_path}")  
                return None  
                
        except Exception as e:  
            print(f"提取 MP4 封面失败 {self.file_path}: {e}")  
            return None  
    # def loadMp4Cover(self):
    #     """处理 MP4 文件并提取封面为 QPixmap"""
    #     try:
    #         video = MP4(self.file_path)
    #         covers = video.get('covr')

    #         if covers:
    #             cover = covers[0]  # 选择第一个封面
    #             image_format = 'jpeg' if cover.imageformat == MP4Cover.FORMAT_JPEG else 'png'

    #             # 使用BytesIO创建图像的字节流
    #             img_byte_array = BytesIO(cover)
    #             pixmap = QPixmap()
    #             if image_format == 'jpeg':
    #                 pixmap.loadFromData(img_byte_array.getvalue(), "JPEG")    
    #             else:
    #                 pixmap.loadFromData(img_byte_array.getvalue(), "PNG")     
    #             return pixmap
    #         else:
    #             return None

    #     except Exception as e:
    #         print(f"提取 MP4 封面失败 {self.file_path}: {e}")
    #         return None