import os
import re
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QCursor

class ClickableLabel(QLabel):
    """可点击的歌词标签"""
    clicked = pyqtSignal(int)  # 发送时间戳(ms)

    def __init__(self, text, timestamp_ms, parent=None):
        super().__init__(text, parent)
        self.timestamp_ms = timestamp_ms
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.is_current = False  # 是否为当前播放的歌词
        # 固定高度以防止跳动
        self.setMinimumHeight(35)
        self.setMaximumHeight(35)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.timestamp_ms)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        """鼠标悬停效果"""
        if not self.is_current:
            self.setStyleSheet("color: #2980b9; font-size: 14px; background-color: rgba(52, 152, 219, 0.1); padding: 5px; border-radius: 3px;")
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开效果"""
        if not self.is_current:
            self.setStyleSheet("color: gray; font-size: 14px;")
        super().leaveEvent(event)

class LrcView(QScrollArea):
    seek_requested = pyqtSignal(int)  # 请求跳转到指定位置(ms)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setAlignment(Qt.AlignCenter)
        self.setWidget(self.container)
        self.labels, self.lyrics_data, self.current_index = [], [], -1

        # 自动滚动控制
        self.auto_scroll_enabled = True
        self.is_auto_scrolling = False  # 标记当前是否正在自动滚动
        self.scroll_disable_timer = QTimer()
        self.scroll_disable_timer.setSingleShot(True)
        self.scroll_disable_timer.timeout.connect(self._enable_auto_scroll)

        # 监听滚动条操作（仅检测用户手动拖动）
        self.verticalScrollBar().sliderPressed.connect(self._on_user_scroll_start)
        self.verticalScrollBar().sliderReleased.connect(self._on_user_scroll_end)

    def load_lrc(self, file_path):
        self.clear()
        if not os.path.exists(file_path):
            return

        # 支持多种歌词格式: [mm:ss.ms], [mm:ss], [hh:mm:ss.ms]
        patterns = [
            re.compile(r'\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)'),  # [mm:ss.ms]
            re.compile(r'\[(\d{2}):(\d{2})\](.*)'),             # [mm:ss]
            re.compile(r'\[(\d{2}):(\d{2}):(\d{2})\.(\d{2,3})\](.*)'),  # [hh:mm:ss.ms]
        ]

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    matched = False
                    # 尝试第一种格式 [mm:ss.ms]
                    match = patterns[0].search(line)
                    if match:
                        m, s, ms, text = match.groups()
                        total_ms = int(m)*60000 + int(s)*1000 + int(ms.ljust(3, '0')[:3])
                        matched = True
                    else:
                        # 尝试第二种格式 [mm:ss]
                        match = patterns[1].search(line)
                        if match:
                            m, s, text = match.groups()
                            total_ms = int(m)*60000 + int(s)*1000
                            matched = True
                        else:
                            # 尝试第三种格式 [hh:mm:ss.ms]
                            match = patterns[2].search(line)
                            if match:
                                h, m, s, ms, text = match.groups()
                                total_ms = int(h)*3600000 + int(m)*60000 + int(s)*1000 + int(ms.ljust(3, '0')[:3])
                                matched = True

                    if matched and text.strip():
                        lbl = ClickableLabel(text.strip(), total_ms)
                        lbl.setAlignment(Qt.AlignCenter)
                        lbl.setStyleSheet("color: gray; font-size: 14px;")
                        lbl.clicked.connect(self._on_lyric_clicked)
                        self.layout.addWidget(lbl)
                        self.labels.append(lbl)
                        self.lyrics_data.append((total_ms, text.strip()))
        except (UnicodeDecodeError, IOError) as e:
            print(f"歌词加载失败: {e}")
        except Exception as e:
            print(f"歌词解析错误: {e}")

    def update_position(self, ms):
        idx = -1
        for i, (t, _) in enumerate(self.lyrics_data):
            if t <= ms: idx = i
            else: break
        # 只在索引真正改变时才更新样式，优化性能
        if idx != self.current_index:
            # 恢复上一句歌词的样式
            if self.current_index != -1 and self.current_index < len(self.labels):
                self.labels[self.current_index].is_current = False
                self.labels[self.current_index].setStyleSheet("color: gray; font-size: 14px;")
            # 高亮当前歌词
            if idx != -1 and idx < len(self.labels):
                self.labels[idx].is_current = True
                self.labels[idx].setStyleSheet("color: #3498db; font-weight: bold; font-size: 18px;")
                # 仅在启用自动滚动时才滚动
                if self.auto_scroll_enabled:
                    self.is_auto_scrolling = True
                    self._scroll_to_center(self.labels[idx])
                    QTimer.singleShot(100, self._reset_auto_scroll_flag)  # 延迟重置标志
            self.current_index = idx

    def _scroll_to_center(self, widget):
        """将指定的widget滚动到视口中心位置"""
        # 获取widget在容器中的位置
        widget_pos = widget.pos().y()
        widget_height = widget.height()

        # 获取滚动区域的高度
        viewport_height = self.viewport().height()

        # 计算使widget居中的滚动值
        # widget中心应该在视口中心，即 widget_pos + widget_height/2 = scrollbar_value + viewport_height/2
        target_scroll = widget_pos + widget_height / 2 - viewport_height / 2

        # 设置滚动条值
        self.verticalScrollBar().setValue(int(target_scroll))

    def _reset_auto_scroll_flag(self):
        """重置自动滚动标志"""
        self.is_auto_scrolling = False

    def _on_lyric_clicked(self, timestamp_ms):
        """歌词被点击时发出跳转请求"""
        self.seek_requested.emit(timestamp_ms)

    def _on_user_scroll_start(self):
        """用户开始手动拖动滚动条"""
        self.auto_scroll_enabled = False

    def _on_user_scroll_end(self):
        """用户结束拖动滚动条，5秒后重新启用自动滚动"""
        self.scroll_disable_timer.start(5000)

    def wheelEvent(self, event):
        """鼠标滚轮滚动时禁用自动滚动"""
        super().wheelEvent(event)
        if not self.is_auto_scrolling:  # 只有非自动滚动时才禁用
            self.auto_scroll_enabled = False
            self.scroll_disable_timer.start(5000)

    def _enable_auto_scroll(self):
        """重新启用自动滚动"""
        self.auto_scroll_enabled = True

    def clear(self):
        for i in reversed(range(self.layout.count())):
            self.layout.itemAt(i).widget().setParent(None)
        self.labels, self.lyrics_data, self.current_index = [], [], -1