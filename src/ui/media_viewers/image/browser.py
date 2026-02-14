import os  
from PyQt5.QtWidgets import QMainWindow, QFileDialog, QShortcut 
from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import Qt

from .multi_viewer import MultiImageViewer

class ImageBrowser(QMainWindow):  
    """图片浏览器应用程序"""  
    def __init__(self):  
        super(ImageBrowser, self).__init__()  
        self.setWindowTitle("图片浏览器")  
        self.resize(1200, 900)  
        
        # 创建多图查看器  
        self.multi_viewer = MultiImageViewer()  
        self.setCentralWidget(self.multi_viewer)  
        
        # 设置菜单栏  
        self.create_menus()  
        
    def create_menus(self):  
        """创建菜单栏"""  
        # 文件菜单  
        menubar = self.menuBar()  
        file_menu = menubar.addMenu("文件")  

        # 添加视图菜单  
        view_menu = menubar.addMenu("视图")  
        
        # 沉浸模式动作  
        immersive_action = view_menu.addAction("沉浸模式 (F11)")  
        immersive_action.triggered.connect(self.toggle_immersive_mode)  # 连接到主窗口的方法 
        
        # 打开文件动作  
        open_action = file_menu.addAction("打开文件...")  
        open_action.triggered.connect(self.open_files)  
        
        # 打开文件夹动作  
        open_dir_action = file_menu.addAction("打开文件夹...")  
        open_dir_action.triggered.connect(self.open_directory)  
        
        # 退出动作  
        file_menu.addSeparator()  
        exit_action = file_menu.addAction("退出")  
        exit_action.triggered.connect(self.close)
    
    def open_files(self):  
        """打开多个图片文件"""  
        file_dialog = QFileDialog()  
        file_dialog.setFileMode(QFileDialog.ExistingFiles)  
        file_dialog.setNameFilter("图片文件 (*.jpg *.jpeg *.png *.bmp *.gif *.tiff *.webp)")  

        if file_dialog.exec_():  
            file_paths = file_dialog.selectedFiles()  
            if file_paths:  
                self.multi_viewer.load_image_files(file_paths)  
    
    def open_directory(self):  
        """打开文件夹中的所有图片"""  
        dir_path = QFileDialog.getExistingDirectory(self, "选择文件夹")  
        if dir_path:  
            # 获取目录中的所有文件  
            file_paths = []  
            for root, dirs, files in os.walk(dir_path):  
                for file in files:  
                    file_paths.append(os.path.join(root, file))  
            
            if file_paths:  
                self.multi_viewer.load_image_files(file_paths)  

    def toggle_immersive_mode(self):  
        """切换沉浸模式"""  
        # 将请求转发到multi_viewer  
        is_immersive = self.multi_viewer.toggle_immersive_mode()  
        
        # 根据沉浸模式状态隐藏/显示菜单栏  
        if is_immersive:  
            self.menuBar().hide()  
        else:  
            self.menuBar().show()  
            
        return is_immersive 
    
    def setup_shortcuts(self):  
        """设置全局快捷键"""  
        # F11切换沉浸模式  
        self.shortcut_immersive = QShortcut(QKeySequence(Qt.Key_F11), self)  
        self.shortcut_immersive.activated.connect(self.toggle_immersive_mode)  
        
        # F键也切换沉浸模式  
        self.shortcut_immersive_f = QShortcut(QKeySequence(Qt.Key_F), self)  
        self.shortcut_immersive_f.activated.connect(self.toggle_immersive_mode)

    def keyPressEvent(self, event):  
        """处理键盘事件"""  
        # 检查是否是F11或F键  
        if event.key() == Qt.Key_F11 or event.key() == Qt.Key_F:  
            self.toggle_immersive_mode()  
            event.accept()  
            return  
        
        super(ImageBrowser, self).keyPressEvent(event) 