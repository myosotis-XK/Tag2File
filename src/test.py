import os
import time
import concurrent.futures
from PyQt5.QtWidgets import QLabel, QFileIconProvider, QApplication
from PyQt5.QtCore import Qt, QFileInfo
from functools import partial

# 模拟上下文环境变量
image_size = 64
label_size = 100
LABEL_INNER_SPACING = 2
image_cache = {}
files_info = {}

# 模拟槽函数（空实现）
def dummy(*args, **kwargs): pass

def create_file_label(file_path, content_widget=None):
    label = QLabel()
    label.setObjectName("file_label")

    icon_label = QLabel(label)
    icon_label.setObjectName("icon_label")

    file_name_label = QLabel(label)
    file_name_label.setObjectName("file_name_label")

    label.icon = False
    label.file_path = file_path

    label.mouseDoubleClickEvent = partial(dummy, file_path=file_path)
    label.mousePressEvent = partial(dummy, label=label)
    label.setContextMenuPolicy(Qt.CustomContextMenu)
    label.customContextMenuRequested.connect(partial(dummy, label=label))
    label.enterEvent = partial(dummy, label=label)
    label.leaveEvent = partial(dummy, label=label)

    if content_widget:
        label.setParent(content_widget)

    label.hide()
    return label

def add_file_attributes(label):
    file_path = label.file_path
    file_extension = os.path.splitext(file_path)[1]

    try:
        pixmap = image_cache[file_extension]
    except:
        icon_provider = QFileIconProvider()
        file_icon = icon_provider.icon(QFileInfo(file_path))
        pixmap = file_icon.pixmap(image_size, image_size)
        pixmap = pixmap.scaled(image_size, image_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        image_cache[file_extension] = pixmap

    icon_label = label.findChild(QLabel, "icon_label")
    icon_label.setStyleSheet("background-color: transparent;")
    icon_label.setPixmap(pixmap)
    icon_label.setFixedSize(image_size, image_size)
    icon_label.setAlignment(Qt.AlignHCenter | Qt.AlignBottom)
    icon_label.move(LABEL_INNER_SPACING, LABEL_INNER_SPACING)

    file_name_label = label.findChild(QLabel, "file_name_label")
    file_name_label.setStyleSheet("background-color: transparent;")
    file_name_label.setWordWrap(True)
    file_name_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    file_name_label.setText(os.path.basename(file_path))

    name_height = 20  # mock
    file_name_label.setFixedSize(label_size - 4, name_height)
    file_name_label.move(2, label_size)

    if os.path.exists(file_path):
        label.file_size_bytes = files_info.get(file_path, {}).get('file_size_bytes', 0)
        label.file_date = files_info.get(file_path, {}).get('file_date', '')
    else:
        label.file_size_bytes = 0
        label.file_date = "文件不存在"

    label.setFixedSize(label_size, label_size + name_height)
    label.file_name = os.path.basename(file_path)
    label.icon = False

def get_all_files(directory):
    directory = directory.replace('\\', '/') 
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            file_path = os.path.join(root, filename).replace('\\', '/')
            files.append(file_path)
    return files


if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)

    test_files = get_all_files(r'E:\新建文件夹\图片\AI')

    start = time.perf_counter()

    labels = [create_file_label(f) for f in test_files]

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(add_file_attributes, label) for label in labels]
        concurrent.futures.wait(futures)

    end = time.perf_counter()
    print(f"创建并设置 {len(test_files)} 个标签耗时: {end - start:.2f} 秒")
