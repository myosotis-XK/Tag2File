from src.utils import set_application_font
from src import StartTask
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
import sys
import multiprocessing
# 导入Flask应用
from web_app.flask_app import app as flask_app
import threading
def start_flask_server_thread():
    flask_thread = threading.Thread(
        target=lambda: flask_app.run(host='0.0.0.0', port=10252, threaded=True, debug=False, use_reloader=False)
    )
    flask_thread.daemon = True
    flask_thread.start()

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
    from src import MainWindow
    viewer = MainWindow.Tag2File()
    start_task_processing()
    start_flask_server_thread()

    sys.exit(app.exec_())