"""
路径处理模块
提供路径规范化、根目录获取等功能
"""
import os
import sys

def get_root() -> str:
    '''获取项目根目录
    :return: 项目根目录路径, 左斜杠分隔'''
    if getattr(sys, 'frozen', False):
        root = os.path.dirname(sys.executable)
        if len(root) >= 2 and root[1] == ":":
            root = root[0].lower() + root[1:]
    else:
        root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return root.replace('\\', '/')

root = get_root()

def normalize_path_lowercase(path: str) -> str:
    '''确保Windows路径盘符小写
    :param path: 输入路径
    :return: 规范化后的路径'''
    if path and len(path) > 1 and path[1] == ':':
        return path[0].lower() + path[1:]
    return path

def get_available_filename(file_path: str) -> str:
    '''确保文件名不重复
    :param file_path: 输入文件路径
    :return: 不重复的文件名, 格式为: 原文件名(数字).扩展名'''
    base_name, extension = os.path.splitext(file_path)
    counter = 1
    while os.path.exists(file_path):
        file_path = f"{base_name}({counter}){extension}"
        counter += 1
    return file_path
