from src.utils import set_application_font
from src import MainWindow, StartTask
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
import sys
import multiprocessing

import logging
import warnings

# 配置日志
logging.basicConfig(level=logging.ERROR)

# 过滤 libpng 警告
warnings.filterwarnings("ignore", category=UserWarning, message=".*libpng warning: iCCP: known incorrect sRGB profile.*")

def start_task_processing():  
    """启动缓存管理进程"""  
    # 使用多进程启动缓存管理  
    cache_manager = multiprocessing.Process(  
        target=StartTask.start_task,
        daemon=True
    )  
    cache_manager.start()  
    print(f"缓存管理进程已启动 (PID: {cache_manager.pid})")

if __name__ == '__main__':
    multiprocessing.freeze_support()  # 支持 Windows 下的多进程启动

    if hasattr(QApplication, 'setAttribute'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    set_application_font()
    viewer = MainWindow.Tag2File()
    start_task_processing()

    sys.exit(app.exec_())