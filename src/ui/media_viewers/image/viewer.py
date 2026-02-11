import sys  
import os  
from PyQt5.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene,   
                            QFileDialog, QLabel, QGraphicsOpacityEffect, QStatusBar,  
                            QVBoxLayout, QWidget, QShortcut, QPushButton)  
from PyQt5.QtGui import QPixmap, QImage, QPainter, QFont, QColor, QKeySequence, QCursor, QBrush
from PyQt5.QtCore import Qt, QRectF, QTimer, QPropertyAnimation, QEasingCurve
import threading

from .components import ZoomIndicator

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

