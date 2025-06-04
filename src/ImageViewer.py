import sys  
import os  
from PyQt5.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene,   
                            QFileDialog, QLabel, QGraphicsOpacityEffect, QStatusBar,  
                            QVBoxLayout, QWidget, QShortcut, QPushButton)  
from PyQt5.QtGui import QPixmap, QImage, QPainter, QFont, QColor, QKeySequence, QCursor, QBrush
from PyQt5.QtCore import Qt, QRectF, QTimer, QPropertyAnimation, QEasingCurve
import concurrent.futures
import threading

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

class ImageViewer(QGraphicsView):  
    def __init__(self, parent=None):  
        super(ImageViewer, self).__init__(parent)  
        self.scene = QGraphicsScene(self)  
        self.setScene(self.scene)  
        
        # 设置渲染提示，提高显示质量  
        self.setRenderHint(QPainter.Antialiasing, True)  
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)  
        self.setRenderHint(QPainter.HighQualityAntialiasing, True)  
        
        # 设置视图变换优化  
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)  
        self.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing, True)  
        
        # 设置最佳质量的变换模式  
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)  
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)  

        # 隐藏水平和垂直滚动条
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 缩放级别列表（仅用于手动缩放）  
        self.zoom_levels = [1, 5, 7, 10, 15, 20, 25, 30, 36, 43, 50, 57, 66, 76, 87, 100,   
                           115, 132, 152, 175, 200, 231, 266, 306, 352, 405, 465, 535,   
                           615, 708, 814, 936, 1076, 1238, 1423, 1637, 1882, 2164,   
                           2500, 2850, 3200]  
        
        # 当前缩放级别索引（仅用于手动缩放）  
        self.current_zoom_index = self.zoom_levels.index(100)  # 初始为100%  
        
        # 当前实际缩放比例  
        self.current_zoom_factor = 1.0  # 初始为100%  
        
        # 图像项  
        self.pixmap_item = None  
        self.original_pixmap = None  
        self.original_image = None  # 存储原始QImage
        self.filter_lock = threading.Lock()
        
        # 追踪鼠标，用于拖动  
        self.setMouseTracking(True)  
        
        # 初始设置为无拖动模式，稍后根据图像大小更新  
        self.setDragMode(QGraphicsView.NoDrag)  
        
        # 适应窗口模式标志  
        self.fit_to_window = True  
        
        # 创建缩放指示器  
        self.zoom_indicator = ZoomIndicator(self)  
        self.zoom_indicator.hide()  
        
        # 当前是否使用预缩放图像模式  
        self.using_prescaled_image = False  

    def load_image(self, source):  
        """  
        加载图像  
        参数:  
            source: 可以是图像文件路径(str)或QPixmap对象  
        返回:  
            加载是否成功  
        """  
        # 清除当前场景中的内容  
        self.scene.clear()  
        
        # 根据source类型执行不同的加载逻辑  
        if isinstance(source, str):  
            # 源是文件路径  
            self.original_image = QImage(source)  
            if self.original_image.isNull():  
                return False  
            self.original_pixmap = QPixmap.fromImage(self.original_image)  
        elif isinstance(source, QPixmap):  
            # 源是QPixmap对象
            if source.isNull():
                return False
            self.original_pixmap = source  
            self.original_image = source.toImage()  # 转换为QImage存储  
        else:  
            # 既不是路径也不是QPixmap对象  
            return False  
        
        # 添加图像到场景  
        self.pixmap_item = self.scene.addPixmap(self.original_pixmap)  
        
        # 重置变换和标志  
        self.resetTransform()  
        self.using_prescaled_image = False  
        
        # 设置场景矩形  
        self.scene.setSceneRect(QRectF(self.pixmap_item.boundingRect()))  
        
        # 默认适应窗口显示  
        self.fit_image_to_window(show_indicator=False)  
        self.fit_to_window = True  
        
        # 更新拖动模式  
        self.update_drag_mode()  
        
        return True  

    def create_scaled_pixmap(self, scale_factor):  
        """创建指定缩放比例的图像 - 仅在缩小时使用"""  
        if self.original_image.isNull():  
            return QPixmap()  
            
        # 计算新尺寸  
        new_width = int(self.original_image.width() * scale_factor)  
        new_height = int(self.original_image.height() * scale_factor)  
        
        # 使用Qt.SmoothTransformation创建高质量缩放图像  
        scaled_image = self.original_image.scaled(  
            new_width, new_height,   
            Qt.KeepAspectRatio,   
            Qt.SmoothTransformation  
        )  
        
        return QPixmap.fromImage(scaled_image)  

    def wheelEvent(self, event):  
        """鼠标滚轮事件处理"""  
        if not self.pixmap_item or not self.original_image:  
            return  
        
        # 退出适应窗口模式  
        self.fit_to_window = False  
        
        # 获取鼠标位置在视图中的坐标  
        view_pos = event.pos()  
        
        # 获取鼠标位置在场景中的坐标（当前缩放下）  
        scene_pos = self.mapToScene(view_pos)  
        
        # 计算鼠标位置相对于图像的比例位置  
        img_rect = self.pixmap_item.boundingRect()  
        rel_x = (scene_pos.x() - img_rect.left()) / img_rect.width()  
        rel_y = (scene_pos.y() - img_rect.top()) / img_rect.height()  
        
        # 根据滚轮方向确定是放大还是缩小  
        steps = event.angleDelta().y() // 120  # 每120个单位为一步  
        
        # 更新缩放级别索引  
        new_index = min(max(0, self.current_zoom_index + steps), len(self.zoom_levels) - 1)  
        
        # 如果缩放级别没有变化，直接返回  
        if new_index == self.current_zoom_index:  
            return  
        
        # 保存当前缩放级别索引和计算缩放因子  
        self.current_zoom_index = new_index  
        zoom_percent = self.zoom_levels[self.current_zoom_index]  
        self.current_zoom_factor = zoom_percent / 100.0  
        
        # 确定是缩小还是放大  
        is_downscaling = self.current_zoom_factor <= 3.0  
        
        # 如果当前是缩小操作，使用预缩放图像以提高质量  
        if is_downscaling:  
            # 创建高质量缩放图像  
            scaled_pixmap = self.create_scaled_pixmap(self.current_zoom_factor)  
            
            # 更新场景中的图像  
            self.scene.removeItem(self.pixmap_item)  
            self.pixmap_item = self.scene.addPixmap(scaled_pixmap)  
            
            # 重置变换  
            self.resetTransform()  
            
            # 调整场景大小  
            self.scene.setSceneRect(QRectF(self.pixmap_item.boundingRect()))  
            
            # 标记为使用预缩放图像  
            self.using_prescaled_image = True  
            
        else:  # 放大操作，使用视图变换以避免内存溢出  
            # 如果之前使用了预缩放图像，需要还原到原始图像  
            if self.using_prescaled_image:  
                self.scene.removeItem(self.pixmap_item)  
                self.pixmap_item = self.scene.addPixmap(self.original_pixmap)  
                self.scene.setSceneRect(QRectF(self.pixmap_item.boundingRect()))  
                self.using_prescaled_image = False  
            
            # 重置变换并应用缩放  
            self.resetTransform()  
            self.scale(self.current_zoom_factor, self.current_zoom_factor)  
        
        # 计算新的鼠标位置对应的场景坐标和需要居中的位置  
        if is_downscaling or self.using_prescaled_image:  
            # 对于预缩放图像，需要基于缩放后的图像计算  
            new_scene_x = self.pixmap_item.boundingRect().left() + rel_x * self.pixmap_item.boundingRect().width()  
            new_scene_y = self.pixmap_item.boundingRect().top() + rel_y * self.pixmap_item.boundingRect().height()  
            
            view_width = self.viewport().width()  
            view_height = self.viewport().height()  
            center_x = new_scene_x - ((view_pos.x() - view_width/2))  
            center_y = new_scene_y - ((view_pos.y() - view_height/2))  
        else:  
            # 对于视图变换，使用原始比例位置计算  
            img_rect = self.pixmap_item.boundingRect()  
            new_scene_x = img_rect.left() + rel_x * img_rect.width()  
            new_scene_y = img_rect.top() + rel_y * img_rect.height()  
            
            view_width = self.viewport().width()  
            view_height = self.viewport().height()  
            center_x = new_scene_x - (view_pos.x() - view_width/2) / self.current_zoom_factor  
            center_y = new_scene_y - (view_pos.y() - view_height/2) / self.current_zoom_factor  
        
        # 居中到计算的位置  
        self.centerOn(center_x, center_y)  
        
        # 显示缩放指示器  
        self.show_zoom_indicator(zoom_percent)  
        
        # 更新拖动模式  
        self.update_drag_mode()  

    def show_zoom_indicator(self, zoom_percent):  
        """显示缩放比例指示器"""  
        # 更新并显示缩放指示器  
        self.zoom_indicator.show_zoom(zoom_percent)  
        
        # 调整指示器位置到视图中心  
        indicator_size = self.zoom_indicator.size()  
        x = (self.width() - indicator_size.width()) // 2  
        y = (self.height() - indicator_size.height()) // 2  
        self.zoom_indicator.move(x, y)  

    def resizeEvent(self, event):  
        """窗口大小变化事件处理"""  
        super(ImageViewer, self).resizeEvent(event)  
        
        if self.pixmap_item and self.fit_to_window:  
            self.fit_image_to_window()  
            
        # 更新拖动模式  
        self.update_drag_mode()  

    def fit_image_to_window(self, show_indicator=True):  
        """使图像适合窗口大小"""  
        if not self.pixmap_item or not self.original_image:  
            return  
        
        # 计算缩放因子以适应窗口  
        view_rect = self.viewport().rect()  
        img_width = self.original_image.width()  
        img_height = self.original_image.height()  
        
        h_factor = view_rect.width() / img_width  
        v_factor = view_rect.height() / img_height  
        factor = min(h_factor, v_factor)  
        
        # 更新当前实际缩放因子  
        self.current_zoom_factor = factor  
        
        # 确定是缩小还是放大  
        is_downscaling = factor <= 3.0  
        
        if is_downscaling:  
            # 创建适合窗口大小的高质量缩放图像  
            scaled_pixmap = self.create_scaled_pixmap(factor)  
            
            # 更新场景中的图像  
            self.scene.removeItem(self.pixmap_item)  
            self.pixmap_item = self.scene.addPixmap(scaled_pixmap)  
            
            # 重置变换  
            self.resetTransform()  
            
            # 标记为使用预缩放图像  
            self.using_prescaled_image = True  
        else:  
            # 如果之前使用了预缩放图像，需要还原到原始图像  
            if self.using_prescaled_image:  
                self.scene.removeItem(self.pixmap_item)  
                self.pixmap_item = self.scene.addPixmap(self.original_pixmap)  
                self.using_prescaled_image = False  
            
            # 重置变换并应用缩放  
            self.resetTransform()  
            self.scale(factor, factor)  
        
        # 调整场景大小  
        self.scene.setSceneRect(QRectF(self.pixmap_item.boundingRect()))  
        
        # 居中显示  
        self.centerOn(self.pixmap_item)  
        
        # 计算并显示精确的缩放百分比  
        zoom_percent = factor * 100
        if show_indicator:
            self.show_zoom_indicator(zoom_percent)  
        
        # 找到最接近的缩放级别（仅用于在退出自适应模式时作为参考）  
        closest_zoom = min(self.zoom_levels, key=lambda x: abs(x - zoom_percent))  
        self.current_zoom_index = self.zoom_levels.index(closest_zoom)  
        
        # 更新拖动模式  
        self.update_drag_mode()  

    def mouseDoubleClickEvent(self, event):  
        """双击鼠标切换适应窗口/原始大小模式"""  
        if not self.pixmap_item:  
            return  
        
        self.fit_to_window = not self.fit_to_window  
        
        if self.fit_to_window:  
            self.fit_image_to_window()  
        else:  
            # 退出自适应模式后设置为100%原始大小  
            self.current_zoom_index = self.zoom_levels.index(100)  # 设置为100%  
            self.current_zoom_factor = 1.0  
            
            # 如果之前使用了预缩放图像，需要还原到原始图像  
            if self.using_prescaled_image:  
                self.scene.removeItem(self.pixmap_item)  
                self.pixmap_item = self.scene.addPixmap(self.original_pixmap)  
                self.using_prescaled_image = False  
            
            # 重置变换  
            self.resetTransform()  
            
            # 调整场景大小  
            self.scene.setSceneRect(QRectF(self.pixmap_item.boundingRect()))  
            
            # 居中显示  
            self.centerOn(self.pixmap_item)  
            
            # 显示缩放指示器  
            self.show_zoom_indicator(100)  # 显示100%  
            
        # 更新拖动模式  
        self.update_drag_mode()  

    # 修改 mouseMoveEvent，让 QGraphicsView 能够处理拖动  
    def mouseMoveEvent(self, event):  
        # 先让 QGraphicsView 处理拖动  
        super(ImageViewer, self).mouseMoveEvent(event)  
        
        # 再将事件传递给父窗口（如果需要）  
        if self.parent():  
            self.parent().mouseMoveEvent(event)  
            
    def update_drag_mode(self):  
        """根据图像和视图大小决定是否启用拖动模式"""  
        if not self.pixmap_item:  
            return  
            
        # 获取当前视图的可见区域大小  
        view_rect = self.viewport().rect()  
        
        # 获取当前场景中图像的边界矩形  
        scene_rect = self.scene.sceneRect()  
        
        # 将场景矩形映射到视图坐标  
        mapped_rect = self.mapFromScene(scene_rect).boundingRect()  
        
        # 检查图像是否超出了视图区域  
        if mapped_rect.width() > view_rect.width() or mapped_rect.height() > view_rect.height():  
            # 图像尺寸大于视图，启用拖动  
            self.setDragMode(QGraphicsView.ScrollHandDrag)  
        else:  
            # 图像尺寸小于或等于视图，禁用拖动  
            self.setDragMode(QGraphicsView.NoDrag)   

class ImageViewerMain(ImageViewer):  # 扩展现有的ImageViewer类  
    def __init__(self, parent=None):  
        super(ImageViewerMain, self).__init__(parent)  
        
        # 添加沉浸模式标志  
        self.immersive_mode = False  
        
    def toggle_immersive_mode(self):  
        """切换沉浸模式"""  
        if not self.pixmap_item or not self.original_image:  
            return  
            
        self.immersive_mode = not self.immersive_mode  
        
        if self.immersive_mode:  
            # 进入沉浸模式  
            self.enter_immersive_mode()  
        else:  
            # 退出沉浸模式  
            self.exit_immersive_mode()  
    
    def enter_immersive_mode(self):  
        """进入沉浸模式"""  
        # 保存当前窗口状态  
        self.parent_window = self.window()  
        self.prev_window_state = self.parent_window.windowState()  
        
        # 设置全屏  
        self.parent_window.showFullScreen()  
        
        # 设置纯黑背景  
        self.scene.setBackgroundBrush(QBrush(QColor(55, 55, 55)))  
        
        # 适应图片到窗口大小  
        self.fit_image_to_window(show_indicator=False)  
        
    def exit_immersive_mode(self):  
        """退出沉浸模式"""  
        # 如果有父窗口，恢复其之前的窗口状态  
        if hasattr(self, 'parent_window') and self.parent_window:  
            self.parent_window.setWindowState(self.prev_window_state)  
        
        # 适应图片到窗口大小  
        self.fit_image_to_window(show_indicator=False)  
        
    def keyPressEvent(self, event):  
        """键盘事件处理"""  
        # 处理Escape键退出沉浸模式  
        if event.key() == Qt.Key_Escape and self.immersive_mode:  
            self.toggle_immersive_mode()  
            event.accept()  
        else:  
            super(ImageViewerMain, self).keyPressEvent(event)  


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
        self.image_files = []  # 有效图片文件列表  
        self.current_index = -1  # 当前图片索引  
        
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
        supported_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp']

        if not os.path.exists(file_path):  
            with self.filter_lock:
                self.image_files.pop(file_path)
        # 检查文件扩展名  
        ext = os.path.splitext(file_path)[1].lower()  
        if ext not in supported_formats:
            with self.filter_lock:
                self.image_files.pop(file_path)

    def load_image_files(self, file_paths, show_file_path=None):  
        """加载图片文件列表，过滤非图片文件"""
        self.image_files = file_paths
        BATCH_SIZE = 100
        batches = [file_paths[i:i + BATCH_SIZE] for i in range(0, len(file_paths), BATCH_SIZE)]
        def process_batch(batch):
            for path in batch:
                self._filter_file(path)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(process_batch, batch) for batch in batches]
            concurrent.futures.wait(futures)
        # 重置索引  
        self.current_index = -1  
        
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
                # 显示导航按钮一秒，然后淡出  

                QTimer.singleShot(1000, self.check_button_visibility)  
            else:  
                self.statusBar.showMessage("没有找到有效的图片文件") 

        self.prev_button.show_button()  
        self.next_button.show_button()  
    
    def show_image_at_index(self, index):  
        """显示指定索引的图片"""  
        if not self.image_files or index < 0 or index >= len(self.image_files):  
            return False  
            
        # 加载并显示图片  
        file_path = self.image_files[index]  
        if self.image_viewer.load_image(file_path):  
            self.current_index = index  
            self.update_status_info()  
            return True  
        else:  
            # 如果加载失败，从列表中移除该文件  
            self.image_files.pop(index)  
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
            
        next_index = (self.current_index + 1) % len(self.image_files)  
        self.show_image_at_index(next_index)  
    
    def show_previous_image(self):  
        """显示上一张图片"""  
        if not self.image_files:  
            return  
            
        prev_index = (self.current_index - 1) % len(self.image_files)  
        self.show_image_at_index(prev_index)  
    
    def update_status_info(self):  
        """更新状态栏信息"""  
        if self.current_index >= 0 and self.image_files:  
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
        print(111)
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


if __name__ == '__main__':  
    app = QApplication(sys.argv)  
    browser = ImageBrowser()  
    browser.show()  
    sys.exit(app.exec_())