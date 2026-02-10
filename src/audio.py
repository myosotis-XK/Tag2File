import sys
import os
import re

from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QWidget, QSlider, QLabel, QScrollArea, QStyle, QStyleOptionSlider)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import Qt, QUrl, QPoint, QRect, QTime
from PyQt5.QtGui import QPainter, QColor, QFont, QMouseEvent

# 格式化毫秒为 00:00 格式
def format_time(ms):
    time = QTime(0, 0).addMSecs(ms)
    return time.toString("mm:ss")

# --- 1. 增强版进度条 (支持时间预览与标记) ---
class MarkerSlider(QSlider):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setMouseTracking(True)
        self.markers = []
        self.snap_threshold = 15 
        
        # 顶层悬浮标签 (显示描述 + 时间)
        self.floating_label = QLabel(self, Qt.ToolTip) 
        self.floating_label.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        self.floating_label.setStyleSheet("""
            background-color: #34495e; 
            color: #ecf0f1; 
            padding: 5px 10px; 
            border-radius: 4px;
            font-family: 'Segoe UI', 'Microsoft YaHei';
            font-size: 11px;
        """)
        self.floating_label.hide()

    def set_markers(self, markers):
        self.markers = markers
        self.update()

    def _get_track_info(self):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        rect = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
        margin = 12
        return rect.left() + margin, rect.width() - margin * 2

    def _value_to_pixel(self, val):
        if self.maximum() <= 0: return 0
        offset, width = self._get_track_info()
        return int((val / self.maximum()) * width + offset)

    def _pixel_to_value(self, x):
        offset, width = self._get_track_info()
        if width <= 0: return 0
        ratio = (x - offset) / width
        return int(max(0, min(1, ratio)) * self.maximum())

    def mouseMoveEvent(self, event: QMouseEvent):
        curr_val = self._pixel_to_value(event.x())
        time_str = format_time(curr_val)
        display_text = f"🕒 {time_str}"
        
        # 检测是否悬停在标记点上
        if self.maximum() > 0:
            for m in self.markers:
                is_hover = False
                if "start" in m and "end" in m:
                    if self._value_to_pixel(m["start"]) <= event.x() <= self._value_to_pixel(m["end"]):
                        is_hover = True
                elif "time" in m:
                    if abs(self._value_to_pixel(m["time"]) - event.x()) < self.snap_threshold:
                        is_hover = True
                
                if is_hover:
                    display_text = f"{m.get('label', '')}\n{time_str}"
                    break
        
        self.floating_label.setText(display_text)
        self.floating_label.adjustSize()
        # 这里的坐标映射确保它浮在最顶层且位置跟随鼠标
        glob_pos = self.mapToGlobal(QPoint(event.x() - self.floating_label.width()//2, -45))
        self.floating_label.move(glob_pos)
        self.floating_label.show()
        
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.floating_label.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            click_x = event.x()
            target_val = self._pixel_to_value(click_x)
            
            # 智能吸附逻辑
            best_snap_val = None
            min_dist = self.snap_threshold
            for m in self.markers:
                pts = [m.get("time"), m.get("start")]
                for p in pts:
                    if p is not None:
                        dist = abs(self._value_to_pixel(p) - click_x)
                        if dist < min_dist:
                            min_dist = dist
                            best_snap_val = p
            
            final_val = best_snap_val if best_snap_val is not None else target_val
            self.setValue(final_val)
            self.sliderMoved.emit(final_val)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.maximum(): return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        for marker in self.markers:
            color = QColor(marker.get('color', '#3498db'))
            if "start" in marker and "end" in marker:
                x1, x2 = self._value_to_pixel(marker['start']), self._value_to_pixel(marker['end'])
                rect_color = QColor(color)
                rect_color.setAlpha(100)
                painter.setBrush(rect_color)
                painter.setPen(color)
                painter.drawRect(x1, 8, x2 - x1, self.height() - 16)
            elif "time" in marker:
                x = self._value_to_pixel(marker['time'])
                painter.setBrush(color)
                painter.setPen(Qt.NoPen)
                painter.drawRect(x - 2, 4, 4, self.height() - 8)
        painter.end()

# --- 2. 歌词视图 ---
class LrcView(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setAlignment(Qt.AlignCenter)
        self.setWidget(self.container)
        self.labels, self.lyrics_data, self.current_index = [], [], -1

    def load_lrc(self, file_path):
        self.clear()
        if not os.path.exists(file_path): return
        pattern = re.compile(r'\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)')
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    match = pattern.search(line)
                    if match:
                        m, s, ms, text = match.groups()
                        total_ms = int(m)*60000 + int(s)*1000 + int(ms.ljust(3, '0')[:3])
                        if text.strip():
                            lbl = QLabel(text.strip())
                            lbl.setAlignment(Qt.AlignCenter)
                            lbl.setStyleSheet("color: gray; font-size: 14px;")
                            self.layout.addWidget(lbl)
                            self.labels.append(lbl)
                            self.lyrics_data.append((total_ms, text.strip()))
        except: pass

    def update_position(self, ms):
        idx = -1
        for i, (t, _) in enumerate(self.lyrics_data):
            if t <= ms: idx = i
            else: break
        if idx != self.current_index and idx != -1:
            if self.current_index != -1:
                self.labels[self.current_index].setStyleSheet("color: gray; font-size: 14px;")
            self.labels[idx].setStyleSheet("color: #3498db; font-weight: bold; font-size: 18px;")
            self.ensureWidgetVisible(self.labels[idx], 150, 150)
            self.current_index = idx

    def clear(self):
        for i in reversed(range(self.layout.count())):
            self.layout.itemAt(i).widget().setParent(None)
        self.labels, self.lyrics_data, self.current_index = [], [], -1

# --- 3. 主窗口 ---
class ModernPlayer(QMainWindow):
    def __init__(self, path):
        super().__init__()
        self.setWindowTitle("高级音频播放器")
        self.resize(500, 600)
        self.player = QMediaPlayer()
        self.path = path
        self.init_ui()
        
        
        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        self.slider.sliderMoved.connect(self.set_position)

    def init_ui(self):
        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QVBoxLayout(widget)

        self.lrc_view = LrcView()
        layout.addWidget(self.lrc_view)

        self.slider = MarkerSlider(Qt.Horizontal)
        layout.addWidget(self.slider)

        btn_layout = QHBoxLayout()
        self.btn_play = QPushButton("播放/暂停")
        self.btn_play.clicked.connect(self.toggle_play)
        btn_layout.addWidget(self.btn_play)
        layout.addLayout(btn_layout)

        # 示例数据加载（请确保本地有对应的 mp3 文件）
        self.load_media() 

    def load_media(self):
        path = self.path
        if os.path.exists(path):
            self.player.setMedia(QMediaContent(QUrl.fromLocalFile(os.path.abspath(path))))
            self.lrc_view.load_lrc(path.replace(".wav", ".lrc"))
            # 模拟标记数据
            self.slider.set_markers([
                {"time": 15000, "color": "#e74c3c", "label": "🔥 精彩片段"},
                {"start": 40000, "end": 70000, "color": "#2ecc71", "label": "🎸 副歌阶段"}
            ])

    def toggle_play(self):
        if self.player.state() == QMediaPlayer.PlayingState: self.player.pause()
        else: self.player.play()

    def on_position_changed(self, ms):
        if not self.slider.isSliderDown():
            self.slider.setValue(ms)
        self.lrc_view.update_position(ms)

    def on_duration_changed(self, ms):
        self.slider.setRange(0, ms)

    def set_position(self, ms):
        self.player.setPosition(ms)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # 设置暗色调主题
    app.setStyle("Fusion")
    path = "" 
    player = ModernPlayer(path)
    player.show()
    sys.exit(app.exec_())