from src.utils import set_application_font
from src import MainWindow, StartTask
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
import sys
import multiprocessing

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
    app = QApplication(sys.argv)
    if hasattr(QApplication, 'setAttribute'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    set_application_font()
    viewer = MainWindow.Tag2File()
    start_task_processing()

    sys.exit(app.exec_())