"""加载 Qt 原生图片，并为 AVIF 提供 Pillow 解码。"""

import os

import pillow_avif  # 注册项目已有的 AVIF 解码插件
from PIL import Image, ImageOps
from PyQt5.QtGui import QImage, QPixmap


def load_qimage(file_path):
    image = QImage(file_path)
    if not image.isNull() or os.path.splitext(file_path)[1].lower() != ".avif":
        return image

    try:
        with Image.open(file_path) as source:
            decoded = ImageOps.exif_transpose(source).convert("RGBA")
            data = decoded.tobytes()
            # copy() 让 QImage 持有自己的像素数据，避免引用临时缓冲区。
            return QImage(
                data, decoded.width, decoded.height,
                decoded.width * 4, QImage.Format_RGBA8888,
            ).copy()
    except (OSError, ValueError):
        return QImage()


def load_pixmap(file_path):
    return QPixmap.fromImage(load_qimage(file_path))
