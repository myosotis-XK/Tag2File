import os
import sys
import re
import configparser
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication

def get_root():
    if getattr(sys, 'frozen', False):
        root = os.path.dirname(sys.executable)
    else:
        root = os.path.dirname(os.path.dirname(__file__))
    return root

root = get_root()
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
    