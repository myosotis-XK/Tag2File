from PyQt5.QtWidgets import QLabel, QGraphicsOpacityEffect
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve

class ZoomIndicator(QLabel):  
    """缩放指示器，用于显示当前缩放比例"""  
    def __init__(self, parent=None):  
        super(ZoomIndicator, self).__init__(parent)  
        # 设置标签样式  
        self.setAlignment(Qt.AlignCenter)  
        self.setStyleSheet("""  
            background-color: rgba(0, 0, 0, 120);  
            color: white;  
            border-radius: 5px;  
            padding: 5px 10px;  
        """)  
        
        # 设置字体  
        font = QFont()  
        font.setBold(True)  
        font.setPointSize(14)  
        self.setFont(font)  
        
        # 设置初始不可见  
        self.setVisible(False)  
        
        # 创建透明度效果  
        self.opacity_effect = QGraphicsOpacityEffect(self)  
        self.opacity_effect.setOpacity(1.0)  
        self.setGraphicsEffect(self.opacity_effect)  
        
        # 创建动画  
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")  
        self.fade_animation.setDuration(800)  # 800毫秒淡出  
        self.fade_animation.setStartValue(0.7)  
        self.fade_animation.setEndValue(0.0)  
        self.fade_animation.setEasingCurve(QEasingCurve.OutCubic)  
        
        # 创建计时器  
        self.timer = QTimer(self)  
        self.timer.setSingleShot(True)  
        self.timer.timeout.connect(self.start_fade_out)  
    
    def show_zoom(self, zoom_level):  
        """显示缩放级别"""  
        # 设置文本 - 如果是浮点数，显示一位小数  
        if isinstance(zoom_level, float):  
            text = f"{zoom_level:.1f}%"  
        else:  
            text = f"{zoom_level}%"  
            
        self.setText(text)  
        
        # 调整大小  
        self.adjustSize()  
        
        # 停止任何正在进行的动画和计时器  
        self.fade_animation.stop()  
        self.timer.stop()  
        
        # 重置透明度  
        self.opacity_effect.setOpacity(0.7)  
        
        # 显示标签  
        self.setVisible(True)  
        
        # 启动计时器，0.5秒后开始淡出  
        self.timer.start(500)  
    
    def start_fade_out(self):  
        """开始淡出动画"""  
        self.fade_animation.start()  
        # 动画结束后隐藏  
        self.fade_animation.finished.connect(lambda: self.setVisible(False))  

    def wheelEvent(self, event):  
        """将滚轮事件传递给父窗口"""  
        # 将事件传递给父窗口处理，忽略自身的滚轮事件  
        if self.parent():  
            self.parent().wheelEvent(event)  
        # 不调用super().wheelEvent(event)，以防止标签本身处理滚轮事件 

    def mouseDoubleClickEvent(self, event): 
        """将双击事件传递给父窗口"""  
        # 将事件传递给父窗口处理，忽略自身的双击事件  
        if self.parent():  
            self.parent().mouseDoubleClickEvent(event)  
        # 不调用super().wheelEvent(event)，以防止标签本身处理双击事件 



class NavButton(QLabel):  
    """导航按钮，当鼠标靠近时显示"""  
    def __init__(self, parent=None, is_next=True):  
        super(NavButton, self).__init__(parent)  
        
        # 设置按钮尺寸  
        self.setFixedSize(50, 80)  
        
        # 设置鼠标样式  
        self.setCursor(Qt.PointingHandCursor)  
        
        # 创建透明度效果  
        self.opacity_effect = QGraphicsOpacityEffect(self)  
        self.opacity_effect.setOpacity(0.0)  # 默认完全透明  
        self.setGraphicsEffect(self.opacity_effect)  
        
        # 创建动画  
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")  
        self.fade_animation.setDuration(200)  # 200毫秒  
        
        # 方向标志  
        self.is_next = is_next  
        
        # 设置样式  
        self.setStyleSheet("""  
            background-color: rgba(0, 0, 0, 120);  
            border-radius: 5px;  
            color: white;  
        """)  
        
        # 设置按钮文本和对齐方式  
        direction = ">" if is_next else "<"  
        self.setText(direction)  
        self.setAlignment(Qt.AlignCenter)  
        
        # 设置字体  
        font = QFont()  
        font.setBold(True)  
        font.setPointSize(20)  
        self.setFont(font)  
        
        # 默认隐藏  
        self.setVisible(False)  
        
        # 鼠标是否在按钮上的标志  
        self.mouse_over = False  
    
    def show_button(self):  
        """显示按钮"""  
        if not self.isVisible():  
            self.setVisible(True)  
        
        # 设置动画  
        self.fade_animation.setStartValue(self.opacity_effect.opacity())  
        self.fade_animation.setEndValue(0.8)  
        self.fade_animation.start()  
    
    def hide_button(self):  
        """隐藏按钮"""  
        # 如果鼠标在按钮上，不隐藏  
        if self.mouse_over:  
            return  
            
        # 设置动画  
        self.fade_animation.setStartValue(self.opacity_effect.opacity())  
        self.fade_animation.setEndValue(0.0)  
        self.fade_animation.start()  
        
        # 动画结束后隐藏按钮  
        self.fade_animation.finished.connect(lambda: self.setVisible(False) if self.opacity_effect.opacity() < 0.1 else None)  
    
    def enterEvent(self, event):  
        """鼠标进入事件"""  
        # 标记鼠标在按钮上  
        self.mouse_over = True  
        
        # 确保按钮显示  
        self.show_button()  
        
        super(NavButton, self).enterEvent(event)  
    
    def leaveEvent(self, event):  
        """鼠标离开事件"""  
        # 标记鼠标不在按钮上  
        self.mouse_over = False  
        
        # 如果父窗口有定时隐藏的计时器，重新启动它  
        if hasattr(self.parent(), 'mouse_timer'):  
            self.parent().mouse_timer.start(300)  
            
        super(NavButton, self).leaveEvent(event)  
    
    def mousePressEvent(self, event):  
        """鼠标点击事件"""  
        if self.parent():  
            if self.is_next:  
                self.parent().show_next_image()  
            else:  
                self.parent().show_previous_image()  
        event.accept()  

