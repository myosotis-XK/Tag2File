"""
缩略图提取模块
支持图片、GIF、视频、音频封面的缩略图提取和缓存
"""
import os
import cv2
import random
import numpy as np
from PIL import Image, ImageSequence, UnidentifiedImageError
Image.MAX_IMAGE_PIXELS = 1_000_000_000
from io import BytesIO
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
import mimetypes
mimetypes.add_type("image/webp", ".webp")
import hashlib
from .path import root

cache_dir = os.path.join(root, 'data', 'cache', 'image').replace('\\', '/')
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

# 获取缓存文件路径
def get_cache_path(file_path: str, image_size: int):
    # 使用文件路径的哈希作为缓存文件名，以避免文件名冲突
    file_hash = hashlib.md5(file_path.encode()).hexdigest()
    return os.path.join(cache_dir, f"{file_hash}_{image_size}.png").replace('\\', '/')


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

    @staticmethod
    def _extract_gif(file_path: str) -> tuple[list[Image.Image], list[int]]:
        """提取 GIF 所有帧 + 帧间隔"""

        frames: list[Image.Image] = []
        durations: list[int] = []

        try:
            with Image.open(file_path) as gif:

                for frame in ImageSequence.Iterator(gif):
                    frame = frame.convert("RGBA")

                    frames.append(frame.copy())
                    duration = frame.info.get("duration")
                    if duration is None or duration == 0:
                        duration = 80
                    durations.append(duration)
            return frames, durations

        except Exception as e:
            print(f"GIF 提取失败 {file_path}: {e}")
            return [], []

    @staticmethod
    def _extract_mp3_cover(file_path: str) -> Image.Image:
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

    @staticmethod
    def _extract_video_frame(file_path: str) -> Image.Image:
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
            total = frame.size
            black_pixels = np.count_nonzero(frame < 10)
            white_pixels = np.count_nonzero(frame > 245)
            bw_ratio = (black_pixels + white_pixels) / total
            if not success or bw_ratio >= 0.8:
                # 策略：从10%到50%的时间范围中随机选择
                start_frame = int(total_frames * 0.1)
                end_frame = int(total_frames * 0.5)
                target_frame = random.randint(start_frame, end_frame)

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


def is_mostly_black_and_white(frame, threshold=0.8):
    """检测帧是否主要为黑白色"""
    # 转灰度
    if frame.ndim == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame

    total = gray.size

    black_pixels = np.count_nonzero(gray < 10)
    white_pixels = np.count_nonzero(gray > 245)

    bw_ratio = (black_pixels + white_pixels) / total

    return bw_ratio >= threshold

# 创建全局缩略图提取器实例
thumbnailExtractor = ThumbnailExtractor()
