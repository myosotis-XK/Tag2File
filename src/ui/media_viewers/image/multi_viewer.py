import os  
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QStatusBar,  
                            QVBoxLayout, QWidget, QShortcut, QPushButton)  
from PyQt5.QtGui import QKeySequence, QCursor
from PyQt5.QtCore import Qt, QTimer
import threading

from .viewer import ImageViewerMain
from .components import NavButton

class MultiImageViewer(QMainWindow):  
    """多图片查看器，支持通过左右键和按钮切换图片"""  
    def __init__(self):  
        super(MultiImageViewer, self).__init__()  
        self.setWindowTitle("图片查看器")  
        self.resize(1000, 800)  
        
        # 创建中心部件和布局  
        central_widget = QWidget()  
        self.setCentralWidget(central_widget)  
        layout = QVBoxLayout(central_widget)  
        layout.setContentsMargins(0, 0, 0, 0)  # 移除布局边距  
        
        # 创建图片查看器  
        self.image_viewer = ImageViewerMain()  
        layout.addWidget(self.image_viewer)  
        
        # 创建状态栏，显示当前图片信息  
        self.statusBar = QStatusBar()  
        self.setStatusBar(self.statusBar)  
        
        # 图片信息标签  
        self.info_label = QLabel()  
        self.info_label.setAlignment(Qt.AlignLeft)  
        self.statusBar.addWidget(self.info_label, 1)  
        
        # 导航信息标签  
        self.nav_label = QLabel()  
        self.nav_label.setAlignment(Qt.AlignRight)  
        self.statusBar.addPermanentWidget(self.nav_label)  
        
        # 创建导航按钮  
        self.prev_button = NavButton(self, is_next=False)  
        self.next_button = NavButton(self, is_next=True)

        # 创建关闭按钮 (使用QPushButton替代QLabel)
        self.close_button = QPushButton("×", self)
        self.close_button.setFocusPolicy(Qt.NoFocus)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 120);
                color: white;
                border-radius: 15px;
                font-size: 24px;
                padding: 5px 15px;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(50, 50, 50, 120);
            }
        """)
        self.close_button.setFixedSize(40, 40)
        self.close_button.clicked.connect(self.close)
        screen_rect = QApplication.desktop().screenGeometry()
        self.close_button.move(screen_rect.width() - self.close_button.width() - 10, 10)
        self.close_button.hide()  # 默认隐藏

        # 文件列表和当前索引  
        self.filter_lock = threading.Lock()
        self.image_files = []  # 有效图片文件列表  
        self.current_index = -1  # 当前图片索引  
        self.current_file = ""  # 当前图片文件路径
        
        # 设置键盘快捷键  
        self.setup_shortcuts()  
        
        # 创建计时器，用于检测鼠标是否移动  
        self.mouse_timer = QTimer(self)  
        self.mouse_timer.setSingleShot(True)  
        self.mouse_timer.timeout.connect(self.check_button_visibility)  
        
        # 启用鼠标跟踪  
        self.setMouseTracking(True)  
        central_widget.setMouseTracking(True)  
        self.image_viewer.setMouseTracking(True)  
        self.image_viewer.viewport().setMouseTracking(True)  
        
        # 更新按钮位置  
        self.update_button_positions()  

    def resizeEvent(self, event):  
        """窗口大小变化事件"""  
        super(MultiImageViewer, self).resizeEvent(event)  
        self.update_button_positions()  
    
    def update_button_positions(self):  
        """更新按钮位置"""  
        # 左边按钮位置  
        self.prev_button.move(10, (self.height() - self.prev_button.height()) // 2)  
        
        # 右边按钮位置  
        self.next_button.move(self.width() - self.next_button.width() - 10,   
                             (self.height() - self.next_button.height()) // 2)  
    
    def mouseMoveEvent(self, event):  
        """鼠标移动事件"""  
        super(MultiImageViewer, self).mouseMoveEvent(event)  
        
        # 重置计时器  
        self.mouse_timer.start(300)  # 300毫秒后检查按钮可见性  
        
        # 获取鼠标位置  
        pos = event.pos()  
        self.check_mouse_position(pos)  
    
    def check_mouse_position(self, pos):  
        """检查鼠标位置，决定是否显示按钮"""  
        # 检查是否有图片加载  
        if not self.image_files:  
            return  
            
        # 沉浸模式下显示关闭按钮
        if self.image_viewer.immersive_mode:
            # 检查鼠标是否在右上角区域
            if pos.x() > (self.width() - 100) and pos.y() < 50:
                self.close_button.show()
            else:
                self.close_button.hide()

        # 检查鼠标是否在左侧区域  
        if pos.x() < 100:  # 左侧100像素宽度区域  
            self.prev_button.show_button()  
        else:  
            # 仅在鼠标不在按钮上时隐藏  
            if not self.prev_button.mouse_over:  
                self.prev_button.hide_button()  
            
        # 检查鼠标是否在右侧区域  
        if pos.x() > (self.width() - 100):  # 右侧100像素宽度区域  
            self.next_button.show_button()  
        else:  
            # 仅在鼠标不在按钮上时隐藏  
            if not self.next_button.mouse_over:  
                self.next_button.hide_button()  
    
    def check_button_visibility(self):  
        """检查按钮可见性"""  
        # 当鼠标停止移动一段时间后，隐藏所有按钮（除非鼠标在按钮上）  
        if not self.prev_button.mouse_over:  
            self.prev_button.hide_button()  
            
        if not self.next_button.mouse_over:  
            self.next_button.hide_button()  
        
    def setup_shortcuts(self):  
        """设置键盘快捷键"""  
        # 左方向键 - 上一张图片  
        self.shortcut_prev = QShortcut(QKeySequence(Qt.Key_Left), self)  
        self.shortcut_prev.activated.connect(self.show_previous_image)  
        
        # 右方向键 - 下一张图片  
        self.shortcut_next = QShortcut(QKeySequence(Qt.Key_Right), self)  
        self.shortcut_next.activated.connect(self.show_next_image)  

        # F11切换沉浸模式  
        self.shortcut_immersive = QShortcut(QKeySequence(Qt.Key_F11), self)  
        self.shortcut_immersive.activated.connect(self.toggle_immersive_mode)  
        
        # F键也切换沉浸模式  
        self.shortcut_immersive_f = QShortcut(QKeySequence(Qt.Key_F), self)  
        self.shortcut_immersive_f.activated.connect(self.toggle_immersive_mode)

    def keyPressEvent(self, event):  
        """键盘事件处理"""  
        # 检查是否是F11或F键  
        if event.key() == Qt.Key_F11 or event.key() == Qt.Key_F:  
            # 将事件传递给父窗口  
            if self.parent():  
                self.parent().keyPressEvent(event)  
            return  
            
        # 对于其他按键，正常处理  
        super(MultiImageViewer, self).keyPressEvent(event) 

    def toggle_immersive_mode(self):  
        """切换沉浸模式并返回当前状态"""  
        self.image_viewer.toggle_immersive_mode()  
        
        # 在沉浸模式下隐藏/显示状态栏和导航按钮  
        if self.image_viewer.immersive_mode:  
            self.statusBar.hide()  
            self.prev_button.hide()  
            self.next_button.hide()  
        else:  
            self.statusBar.show()  
            # 重置导航按钮可见性  
            self.check_mouse_position(self.mapFromGlobal(QCursor.pos()))  
            
        return self.image_viewer.immersive_mode 

    def _filter_file(self, file_path):
        """过滤文件列表，仅保留图片文件"""
        supported_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp', '.avif']

        if not os.path.exists(file_path):  
            with self.filter_lock:
                try:
                    self.image_files.remove(file_path)
                except:
                    pass
            return
        # 检查文件扩展名  
        ext = os.path.splitext(file_path)[1].lower()  
        if ext not in supported_formats:
            with self.filter_lock:
                try:
                    self.image_files.remove(file_path)
                except:
                    pass

    def _start_background_filtering(self, file_paths):
        """在后台线程中执行文件过滤"""
        def filter_task():
            BATCH_SIZE = 10000
            batches = [file_paths[i:i + BATCH_SIZE] for i in range(0, len(file_paths), BATCH_SIZE)]
            for batch in batches:
                for path in batch:
                    self._filter_file(path)
                # 每处理完一个批次，更新UI
                self._update_filter_results()
        
        # 创建并启动线程
        self.filter_thread = threading.Thread(target=filter_task, daemon=True)
        self.filter_thread.start()

    def _update_filter_results(self):
        """在主线程中更新过滤结果"""
        if not self.image_files and self.current_index == -1:
            self.statusBar.showMessage("正在加载图片...")
        else:
            self.update_status_info()

    # 修改load_image_files方法
    def load_image_files(self, file_paths: list, show_file_path=None):  
        """加载图片文件列表，过滤非图片文件"""
        if self.current_index != -1 and show_file_path is None:
            show_file_path = self.image_files[self.current_index]
        
        # 初始化文件列表
        self.image_files = file_paths
        
        # 在后台线程中执行过滤
        self._start_background_filtering(file_paths)
        
        if not show_file_path is None:
            try:
                index = self.image_files.index(show_file_path)  
                self.show_image_at_index(index)
            except:
                pass
        
        if self.current_index == -1:
            # 如果有有效图片，显示第一张
            if self.image_files:  
                self.show_image_at_index(0)  
                QTimer.singleShot(1000, self.check_button_visibility)  
            else:  
                self.statusBar.showMessage("正在加载图片...")
        
        # 显示导航按钮一秒，然后淡出 
        self.prev_button.show_button()  
        self.next_button.show_button()
    
    def show_image_at_index(self, index):  
        """显示指定索引的图片"""  
        if not self.image_files or index < 0 or index >= len(self.image_files):  
            return False  
            
        # 加载并显示图片  
        file_path = self.image_files[index]  
        self.current_file = file_path
        if self.image_viewer.load_image(file_path):  
            self.current_index = index  
            self.update_status_info()  
            return True  
        else:  
            # 如果加载失败，从列表中移除该文件  
            try:
                self.image_files.remove(file_path)
            except:
                pass
            # 如果还有其他图片，尝试加载当前索引的图片  
            if self.image_files:  
                # 确保索引在有效范围内  
                new_index = min(index, len(self.image_files) - 1)  
                return self.show_image_at_index(new_index)  
            else:  
                self.current_index = -1  
                self.update_status_info()  
                return False  
    
    def show_next_image(self):  
        """显示下一张图片"""  
        if not self.image_files:  
            return  
        with self.filter_lock:
            if self.current_index >= len(self.image_files) or self.image_files[self.current_index] != self.current_file:
                self.current_index = self.image_files.index(self.current_file)
            next_index = (self.current_index + 1) % len(self.image_files)  
            self.show_image_at_index(next_index)  
    
    def show_previous_image(self):  
        """显示上一张图片"""  
        if not self.image_files:  
            return  
        with self.filter_lock:
            if self.current_index >= len(self.image_files) or self.image_files[self.current_index] != self.current_file:
                self.current_index = self.image_files.index(self.current_file)
            prev_index = (self.current_index - 1) % len(self.image_files)  
            self.show_image_at_index(prev_index)  
    
    def update_status_info(self):  
        """更新状态栏信息"""  
        if self.current_index >= 0 and self.image_files:  
            if self.current_index >= len(self.image_files) or self.image_files[self.current_index] != self.current_file:
                self.current_index = self.image_files.index(self.current_file)
            # 获取当前图片文件路径和文件名  
            file_path = self.image_files[self.current_index]  
            file_name = os.path.basename(file_path)  
            
            # 获取图片尺寸  
            if self.image_viewer.original_image:  
                width = self.image_viewer.original_image.width()  
                height = self.image_viewer.original_image.height()  
                size_info = f"{width} × {height}"  
            else:  
                size_info = "未知尺寸"  
                
            # 更新信息标签  
            self.info_label.setText(f"{file_name} | {size_info}")  
            
            # 更新导航标签  
            total = len(self.image_files)  
            nav_text = f"{self.current_index + 1} / {total}"  
            self.nav_label.setText(nav_text)  
        else:  
            self.info_label.setText("无图片")  
            self.nav_label.setText("")  


