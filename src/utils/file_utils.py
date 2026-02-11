"""
文件工具模块
提供文件大小格式化、文件类型检测等功能
"""
import os
import mimetypes

def format_file_size(size_in_bytes: int) -> str:
    '''格式化文件大小
    :param size_in_bytes: 文件大小（字节）
    :return: 格式化后的文件大小字符串'''
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

def get_all_files(directory: str) -> list[str]:
    '''递归获取目录下所有文件路径
    :param directory: 目录路径
    :return: 所有文件路径列表'''
    directory = directory.replace('\\', '/')
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            file_path = os.path.join(root, filename).replace('\\', '/')
            files.append(file_path)
    return files

def get_file_type(file_path: str) -> str:
    '''获取文件类型
    :param file_path: 文件路径
    :return: 文件类型字符串, enum: "图片", "视频", "音频", "GIF", "其他"'''
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        if mime_type == 'image/gif':
            return "GIF"
        if mime_type.startswith('image'):
            return "图片"
        elif mime_type.startswith('video'):
            return "视频"
        elif mime_type.startswith('audio'):
            return "音频"
    return "其他"
