import os
import sys
import re
import cv2
import random
from PIL import Image, ImageSequence, UnidentifiedImageError
Image.MAX_IMAGE_PIXELS = 1_000_000_000
from io import BytesIO
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
import mimetypes
mimetypes.add_type("image/webp", ".webp")
import hashlib
import configparser
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication

def get_root():
    if getattr(sys, 'frozen', False):
        root = os.path.dirname(sys.executable)
        if len(root) >= 2 and root[1] == ":":
            root = root[0].lower() + root[1:]
    else:
        root = os.path.dirname(os.path.dirname(__file__))
    return root.replace('\\', '/')

root = get_root()

cache_dir = os.path.join(root, 'data', 'cache', 'image').replace('\\', '/')
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)
# 获取缓存文件路径
def get_cache_path(file_path: str, image_size: int):
    # 使用文件路径的哈希作为缓存文件名，以避免文件名冲突
    file_hash = hashlib.md5(file_path.encode()).hexdigest()
    return os.path.join(cache_dir, f"{file_hash}_{image_size}.png").replace('\\', '/')

config = configparser.ConfigParser()
config_path = os.path.join(root, 'config', 'config.ini')

def read_config():
    config.clear()  # Python3.2+；老版本可以：config._sections.clear()
    config.read(config_path, encoding='utf-8')

def save_config():
    """保存当前配置到文件"""
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # 使用临时文件写入，避免写入过程中出错导致原文件损坏
        temp_path = config_path + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as f:
            config.write(f)
        
        # 原子性替换原文件
        if os.path.exists(config_path):
            os.replace(temp_path, config_path)
        else:
            os.rename(temp_path, config_path)
            
    except Exception as e:
        print(f"保存配置文件失败: {e}")
        # 删除可能残留的临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)

def init_config_section(section, defaults):
    """优雅地初始化配置节和默认值"""
    if section not in config:
        config.add_section(section)
    for key, value in defaults.items():
        if key not in config[section]:
            config.set(section, key, str(value))

read_config()

def set_application_font():
    font = QFont()
    font.setFamily("Verdana")  # 首选 Verdana
    font.setStyleHint(QFont.SansSerif)  # 如果 Verdana 不可用，使用无衬线字体
    QApplication.setFont(font)

def normalize_path_lowercase(path):
    """确保Windows路径盘符小写"""
    if path and len(path) > 1 and path[1] == ':':
        return path[0].lower() + path[1:]
    return path

def get_available_filename(file_path):
    """确保文件名不重复"""
    base_name, extension = os.path.splitext(file_path)
    counter = 1
    while os.path.exists(file_path):
        file_path = f"{base_name}({counter}){extension}"
        counter += 1
    return file_path

#格式化文件大小
def format_file_size(size_in_bytes):
    if not isinstance(size_in_bytes, int):
        return size_in_bytes
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    elif size_in_bytes < 1024 ** 2:
        return f"{size_in_bytes / 1024:.2f} KB"
    elif size_in_bytes < 1024 ** 3:
        return f"{size_in_bytes / (1024 ** 2):.2f} MB"
    else:
        return f"{size_in_bytes / (1024 ** 3):.2f} GB"
    
#递归获取文件路径
def get_all_files(directory):
    directory = directory.replace('\\', '/') 
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            file_path = os.path.join(root, filename).replace('\\', '/')
            files.append(file_path)
    return files

def updateStyle(label, new_style_property:str):
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

import mimetypes
def get_file_type(file_path):
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        if mime_type.startswith('image'):
            return "图片"
        elif mime_type.startswith('video'):
            return "视频"
        elif mime_type.startswith('audio'):
            return "音频"
    return "其他"


# ——————————————————————————提取缩略图————————————————————————————————————

class ThumbnailSequence:
    """存储缩略图序列及其间隔时间"""
    def __init__(self, frames: list[Image.Image] | Image.Image, durations: list[int] = None):
        if isinstance(frames, Image.Image):
            frames = [frames]
        self.frames = frames
        self.durations = durations
        self.animated = len(frames) > 1

class ThumbnailExtractor:
    """通用的缩略图提取工具"""
    
    def __init__(self):
        pass
    
    def extract_thumbnail(self, file_path: str, image_size: int) -> ThumbnailSequence:
        """从文件提取缩略图，统一返回 PIL.Image 对象"""
        try:
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                return None
            
            thumbnail_image = None

            if mime_type == 'image/gif':
                frames, durations = self._extract_gif(file_path)
                if len(frames) == 0:
                    return None
                for frame in frames:
                    frame.thumbnail((image_size, image_size), Image.Resampling.LANCZOS)
                return ThumbnailSequence(frames, durations)
            elif mime_type.startswith('image'):
                thumbnail_image = self._extract_image(file_path)
            elif mime_type == 'audio/mpeg':
                thumbnail_image = self._extract_mp3_cover(file_path)
            elif mime_type.startswith('video/'):
                thumbnail_image = self._extract_video_frame(file_path)
            else:
                return None
            
            if thumbnail_image:
                thumbnail_image.thumbnail((image_size, image_size), Image.Resampling.LANCZOS)
                return ThumbnailSequence(thumbnail_image)
        
        except Exception as e:
            print(f"提取缩略图失败 {file_path}: {e}")
            return None
    
    def _extract_image(self, file_path: str) -> Image.Image:
        """提取图片文件的缩略图"""
        try:
            with Image.open(file_path) as img:
                # 移除 ICC 配置以减少警告
                if 'icc_profile' in img.info:
                    img.info.pop('icc_profile')
                return img.copy()
        except (UnidentifiedImageError, OSError) as e:
            print(f"无法打开图像文件 {file_path}: {e}")
            return None
        
    def _extract_gif(self, file_path: str) -> tuple[list[Image.Image], list[int]]:
        """提取 GIF 所有帧 + 帧间隔"""

        frames: list[Image.Image] = []
        durations: list[int] = []

        try:
            with Image.open(file_path) as gif:

                for frame in ImageSequence.Iterator(gif):
                    frame = frame.convert("RGBA")

                    frames.append(frame.copy())

                    # duration 单位是 ms
                    durations.append(frame.info.get("duration", 100))
            return frames, durations

        except Exception as e:
            print(f"GIF 提取失败 {file_path}: {e}")
            return [], []
    
    def _extract_mp3_cover(self, file_path: str) -> Image.Image:
        """提取 MP3 封面"""
        try:
            audio = MP3(file_path, ID3=ID3)
            if audio.tags:
                for tag in audio.tags.keys():
                    if tag.startswith('APIC:'):
                        apic = audio.tags[tag]
                        img_data = BytesIO(apic.data)
                        with Image.open(img_data) as img:
                            return img.copy()
        except Exception as e:
            print(f"提取 MP3 封面失败 {file_path}: {e}")
            return None
    
    def _extract_video_frame(self, file_path: str) -> Image.Image:
        """从视频中提取关键帧"""
        video = None
        try:
            video = cv2.VideoCapture(file_path)
            if not video.isOpened():
                return None
            
            total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # 先尝试读取第 1 帧
            success, frame = video.read()
            # 如果第 1 帧是黑屏或模糊，尝试读取中间帧
            if not success or frame.mean() < 10:
                target_frame = self._select_smart_frame(video, total_frames)
                video.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                success, frame = video.read()
            
            if not success:
                video.set(cv2.CAP_PROP_POS_FRAMES, 5) # 跳过前几帧
                for _ in range(10): # 连续尝试读 10 帧，直到有一帧成功
                    success, frame = video.read()
                    if success: break
            
            # 转换为 PIL Image
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(frame_rgb)
            return pil_img
            
        except Exception as e:
            print(f"提取视频帧失败 {file_path}: {e}")
            return None
        finally:
            if video:
                video.release()
    
    def _select_smart_frame(self, video_cap, total_frames: int) -> int:
        """智能选择视频帧位置"""
        if total_frames <= 10:
            return 0
        
        # 策略：避开前10%的黑屏和最后20%的字幕
        start_frame = int(total_frames * 0.1)
        end_frame = int(total_frames * 0.5)
        
        # 确保有足够的范围
        if end_frame - start_frame < 10:
            return total_frames // 2
        
        return random.randint(start_frame, end_frame)
    
thumbnailExtractor = ThumbnailExtractor()