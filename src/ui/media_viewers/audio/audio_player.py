import sys
import os
import re
import threading
import random

from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QSlider, QLabel, QScrollArea, QStyle,
                             QStyleOptionSlider, QMessageBox, QMenu, QShortcut, QSplitter)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import Qt, QUrl, QPoint, QTime, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QMouseEvent, QKeySequence

from .marker_edit_dialog import MarkerEditDialog
from src.core.DictManage import DictManage
from .marker_list_panel import MarkerListPanel
from .marker_preset_manager import MarkerPresetManager
from .playlist_panel import PlaylistPanel
from .quick_marker_creator import QuickMarkerCreator

# 格式化毫秒为 00:00 格式
def format_time(ms):
    time = QTime(0, 0).addMSecs(ms)
    return time.toString("mm:ss")

# --- 1. 播放进度条 (纯播放控制，无吸附) ---
class PlaybackSlider(QSlider):
    """播放进度条 - 负责播放位置控制和时间设置"""

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setMouseTracking(True)

        # 快速标记创建器引用（用于设置时间）
        self.quick_marker_creator = None

        # 顶层悬浮标签 (显示时间)
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

    def set_quick_marker_creator(self, creator):
        """设置快速标记创建器引用"""
        self.quick_marker_creator = creator

    def _get_track_info(self):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        rect = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
        margin = 12
        return rect.left() + margin, rect.width() - margin * 2

    def _pixel_to_value(self, x):
        offset, width = self._get_track_info()
        if width <= 0: return 0
        ratio = (x - offset) / width
        return int(max(0, min(1, ratio)) * self.maximum())

    def mouseMoveEvent(self, event: QMouseEvent):
        """显示时间预览"""
        curr_val = self._pixel_to_value(event.x())
        time_str = format_time(curr_val)
        display_text = f"🕒 {time_str}"

        self.floating_label.setText(display_text)
        self.floating_label.adjustSize()
        glob_pos = self.mapToGlobal(QPoint(event.x() - self.floating_label.width()//2, -45))
        self.floating_label.move(glob_pos)
        self.floating_label.show()

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.floating_label.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """点击进度条跳转到对应位置"""
        if event.button() == Qt.LeftButton:
            click_x = event.x()
            target_val = self._pixel_to_value(click_x)

            self.setValue(target_val)
            self.sliderMoved.emit(target_val)

        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        """右键菜单：设置开始/结束时间"""
        if not self.quick_marker_creator:
            return

        click_x = event.x()
        menu = QMenu(self)

        set_start_time_action = menu.addAction("⏱️ 设置为开始时间")
        set_end_time_action = menu.addAction("⏱️ 设置为结束时间")

        action = menu.exec_(event.globalPos())

        if action == set_start_time_action:
            time_pos = self._pixel_to_value(click_x)
            self.quick_marker_creator.start_time_input.set_from_milliseconds(time_pos)
        elif action == set_end_time_action:
            time_pos = self._pixel_to_value(click_x)
            self.quick_marker_creator.end_time_input.set_from_milliseconds(time_pos)


# --- 2. 标记显示区域 (纯显示，可点击跳转) ---
class MarkerDisplayWidget(QWidget):
    """标记显示组件 - 负责标记显示、编辑和跳转"""

    # 信号：当点击标记跳转时发出
    markerJumped = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.DictManage = DictManage()
        self.setMouseTracking(True)
        self.markers = []
        self.snap_threshold = 15
        self.duration_ms = 0  # 音频总时长

        # 设置固定高度
        self.setFixedHeight(30)

        # 设置样式
        self.setStyleSheet("""
            MarkerDisplayWidget {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 3px;
            }
        """)

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

        # 音频文件路径（用于保存标记到数据库）
        self.audio_file_path = None

        # 标记列表面板引用（需要从外部设置）
        self.marker_list_panel = None

        # 主窗口引用（用于调用统一的编辑方法）
        self.main_window = None

    def set_duration(self, duration_ms):
        """设置音频总时长"""
        self.duration_ms = duration_ms
        self.update()

    def set_markers(self, markers):
        """设置标记数据"""
        self.markers = markers
        self.update()

    def set_audio_file_path(self, path):
        """设置音频文件路径（用于数据库操作）"""
        self.audio_file_path = path

    def set_marker_list_panel(self, panel):
        """设置标记列表面板引用"""
        self.marker_list_panel = panel

    def set_main_window(self, window):
        """设置主窗口引用"""
        self.main_window = window

    def _value_to_pixel(self, val):
        """将时间值转换为像素位置"""
        if self.duration_ms <= 0:
            return 0
        return int((val / self.duration_ms) * self.width())

    def _pixel_to_value(self, x):
        """将像素位置转换为时间值"""
        if self.width() <= 0:
            return 0
        ratio = x / self.width()
        return int(max(0, min(1, ratio)) * self.duration_ms)

    def _find_marker_at(self, x):
        """检测鼠标位置是否在标记上，返回 (marker, index) 或 (None, None)"""
        if self.duration_ms <= 0:
            return None, None

        for i, marker in enumerate(self.markers):
            if "start" in marker and "end" in marker:
                # 范围标记
                x1 = self._value_to_pixel(marker["start"])
                x2 = self._value_to_pixel(marker["end"])
                if x1 <= x <= x2:
                    return marker, i
            elif "time" in marker:
                # 点标记
                marker_x = self._value_to_pixel(marker["time"])
                if abs(marker_x - x) < self.snap_threshold:
                    return marker, i

        return None, None

    def _find_markers_at(self, x):
        """检测鼠标位置是否在标记上，返回所有重叠的标记列表"""
        if self.duration_ms <= 0:
            return []

        overlapping_markers = []
        for marker in self.markers:
            if "start" in marker and "end" in marker:
                # 范围标记
                x1 = self._value_to_pixel(marker["start"])
                x2 = self._value_to_pixel(marker["end"])
                if x1 <= x <= x2:
                    overlapping_markers.append(marker)
            elif "time" in marker:
                # 点标记
                marker_x = self._value_to_pixel(marker["time"])
                if abs(marker_x - x) < self.snap_threshold:
                    overlapping_markers.append(marker)

        return overlapping_markers

    def _open_marker_edit_dialog(self, marker_data=None):
        """打开标记编辑对话框"""
        # 获取预设列表
        presets = self.DictManage.get_all_marker_presets()

        dialog = MarkerEditDialog(
            marker_data=marker_data,
            presets=presets,
            max_duration_ms=self.duration_ms,
            parent=self
        )
        if dialog.exec_() == MarkerEditDialog.Accepted:
            return dialog.get_data()
        return None

    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件 - 显示标记信息"""
        # 获取鼠标位置上的所有重叠标记
        overlapping_markers = self._find_markers_at(event.x())

        if overlapping_markers:
            # 构建显示文本，显示所有重叠标记的信息
            display_lines = []
            for m in overlapping_markers:
                if m.get('type') == 0:  # 点标记
                    time_str = format_time(m['time'])
                    display_lines.append(f"{m.get('label', '')} - {time_str}")
                else:  # 范围标记
                    start_str = format_time(m['start'])
                    end_str = format_time(m['end'])
                    display_lines.append(f"{m.get('label', '')} - {start_str}~{end_str}")

            display_text = "\n".join(display_lines)

            self.floating_label.setText(display_text)
            self.floating_label.adjustSize()
            glob_pos = self.mapToGlobal(QPoint(event.x() - self.floating_label.width()//2, -45))
            self.floating_label.move(glob_pos)
            self.floating_label.show()
        else:
            # 如果没有悬停在标记上，隐藏提示
            self.floating_label.hide()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件"""
        super().mouseReleaseEvent(event)

    def _reload_markers(self):
        """从数据库重新加载标记"""
        if not self.audio_file_path:
            return

        normalized_path = self.audio_file_path
        markers_data = self.DictManage.get_audio_markers(normalized_path)

        # 转换为标记格式
        self.markers = []
        for m in markers_data:
            if m['type'] == 0:  # 点标记
                self.markers.append({
                    'id': m['id'],
                    'type': 0,
                    'time': m['time'],
                    'color': m['color'],
                    'label': m['label']
                })
            else:  # 范围标记
                self.markers.append({
                    'id': m['id'],
                    'type': 1,
                    'start': m['start'],
                    'end': m['end'],
                    'color': m['color'],
                    'label': m['label']
                })

        self.update()

    def leaveEvent(self, event):
        """鼠标离开事件"""
        self.floating_label.hide()
        super().leaveEvent(event)

    def contextMenuEvent(self, event):
        """右键菜单事件 - 只在标记上右键时显示"""
        click_x = event.x()
        marker, marker_idx = self._find_marker_at(click_x)

        if marker:
            # 在标记上右键：显示编辑和删除选项
            menu = QMenu(self)
            edit_action = menu.addAction("📝 编辑标记")
            delete_action = menu.addAction("🗑️ 删除标记")

            action = menu.exec_(event.globalPos())

            if action == edit_action:
                # 调用主窗口的统一编辑方法
                if self.main_window:
                    self.main_window.edit_marker(marker)
            elif action == delete_action:
                self._delete_marker(marker)

    def _edit_marker(self, marker):
        """编辑标记"""
        if not self.audio_file_path:
            return

        # 打开编辑对话框，预填充现有数据
        result = self._open_marker_edit_dialog(marker)
        if result:
            normalized_path = self.audio_file_path

            # 构建更新参数
            update_params = {
                'label': result['label'],
                'color': result['color'],
                'preset_id': result['preset_id']
            }

            # 根据标记类型添加时间参数
            if result['type'] == 0:  # 点标记
                update_params['time'] = result['time']
                update_params['start'] = None
                update_params['end'] = None
            else:  # 范围标记
                update_params['start'] = result['start']
                update_params['end'] = result['end']
                update_params['time'] = None

            # 更新数据库
            self.DictManage.update_audio_marker(
                normalized_path,
                marker['id'],
                **update_params
            )

            # 重新加载标记
            self._reload_markers()

            # 刷新标记列表面板
            if self.marker_list_panel:
                self.marker_list_panel.load_markers()

            return True
        return False

    def _delete_marker(self, marker):
        """删除标记"""
        if not self.audio_file_path:
            return

        normalized_path = self.audio_file_path

        # 从数据库删除
        self.DictManage.delete_audio_marker(normalized_path, marker['id'])

        # 重新加载标记
        self._reload_markers()

        # 刷新标记列表面板
        if self.marker_list_panel:
            self.marker_list_panel.load_markers()

    def mousePressEvent(self, event: QMouseEvent):
        """点击标记跳转到对应位置"""
        if event.button() == Qt.LeftButton:
            click_x = event.x()
            overlapping_markers = self._find_markers_at(click_x)

            if overlapping_markers:
                # 获取鼠标点击位置对应的时间
                click_time = self._pixel_to_value(click_x)

                # 如果有多个重叠标记，跳转到开始时间距离鼠标点击位置最近的那个
                closest_marker = None
                min_distance = float('inf')

                for marker in overlapping_markers:
                    # 获取标记的开始时间
                    if marker.get('type') == 0:  # 点标记
                        marker_start = marker['time']
                    else:  # 范围标记
                        marker_start = marker['start']

                    # 计算距离鼠标点击位置的距离
                    distance = abs(marker_start - click_time)

                    if distance < min_distance:
                        min_distance = distance
                        closest_marker = marker

                # 跳转到最近的标记
                if closest_marker:
                    if closest_marker.get('type') == 0:  # 点标记
                        target_val = closest_marker['time']
                    else:  # 范围标记，跳转到起点
                        target_val = closest_marker['start']

                    # 发出跳转信号
                    self.markerJumped.emit(target_val)

        super().mousePressEvent(event)

    def paintEvent(self, event):
        """绘制标记显示区域"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制背景
        painter.fillRect(self.rect(), QColor("#f5f5f5"))

        # 绘制边框
        painter.setPen(QColor("#ddd"))
        painter.drawRoundedRect(0, 0, self.width() - 1, self.height() - 1, 3, 3)

        if not self.duration_ms or not self.markers:
            painter.end()
            return

        # 绘制标记
        for marker in self.markers:
            color = QColor(marker.get('color', '#3498db'))
            if "start" in marker and "end" in marker:
                # 范围标记
                x1 = self._value_to_pixel(marker['start'])
                x2 = self._value_to_pixel(marker['end'])
                rect_color = QColor(color)
                rect_color.setAlpha(100)
                painter.setBrush(rect_color)
                painter.setPen(color)
                painter.drawRect(x1, 8, x2 - x1, self.height() - 16)
            elif "time" in marker:
                # 点标记
                x = self._value_to_pixel(marker['time'])
                painter.setBrush(color)
                painter.setPen(Qt.NoPen)
                painter.drawRect(x - 2, 4, 4, self.height() - 8)

        painter.end()


# --- 3. 双进度条容器 ---
class DualSliderWidget(QWidget):
    """双进度条容器 - 上方标记显示区，下方播放进度条"""

    # 信号：当播放进度条被拖动时发出
    sliderMoved = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)

        # 标记显示区域（上）
        self.marker_display = MarkerDisplayWidget()
        self.layout.addWidget(self.marker_display)

        # 播放进度条（下）
        self.playback_slider = PlaybackSlider(Qt.Horizontal)
        self.layout.addWidget(self.playback_slider)

        # 连接信号
        self.marker_display.markerJumped.connect(self._on_marker_jumped)
        self.playback_slider.sliderMoved.connect(self.sliderMoved.emit)

    def _on_marker_jumped(self, position):
        """标记跳转时同步播放进度条并发出信号"""
        self.playback_slider.setValue(position)
        self.sliderMoved.emit(position)

    def setRange(self, min_val, max_val):
        """设置播放进度条的范围和标记区域的时长"""
        self.playback_slider.setRange(min_val, max_val)
        self.marker_display.set_duration(max_val)

    def setValue(self, value):
        """设置播放进度条的值"""
        self.playback_slider.setValue(value)

    def isSliderDown(self):
        """检查播放进度条是否被按下"""
        return self.playback_slider.isSliderDown()

    def set_markers(self, markers):
        """设置标记数据"""
        self.marker_display.set_markers(markers)

        # 根据标记数量控制标记显示区域的可见性
        if markers:
            self.marker_display.show()
        else:
            self.marker_display.hide()

    def set_audio_file_path(self, path):
        """设置音频文件路径"""
        self.marker_display.set_audio_file_path(path)

    def set_quick_marker_creator(self, creator):
        """设置快速标记创建器引用"""
        self.playback_slider.set_quick_marker_creator(creator)

    def set_marker_list_panel(self, panel):
        """设置标记列表面板引用"""
        self.marker_display.set_marker_list_panel(panel)

    def _reload_markers(self):
        """重新加载标记"""
        self.marker_display._reload_markers()

        # 更新可见性
        if self.marker_display.markers:
            self.marker_display.show()
        else:
            self.marker_display.hide()


# --- 4. 歌词视图 ---
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
                        lbl = QLabel(text.strip())
                        lbl.setAlignment(Qt.AlignCenter)
                        lbl.setStyleSheet("color: gray; font-size: 14px;")
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
            if self.current_index != -1 and self.current_index < len(self.labels):
                self.labels[self.current_index].setStyleSheet("color: gray; font-size: 14px;")
            if idx != -1 and idx < len(self.labels):
                self.labels[idx].setStyleSheet("color: #3498db; font-weight: bold; font-size: 18px;")
                self.ensureWidgetVisible(self.labels[idx], 150, 150)
            self.current_index = idx

    def clear(self):
        for i in reversed(range(self.layout.count())):
            self.layout.itemAt(i).widget().setParent(None)
        self.labels, self.lyrics_data, self.current_index = [], [], -1

# --- 3. 音频播放器窗口 ---
class ModernPlayer(QWidget):
    def __init__(self, path, audio_files=None):
        super().__init__()
        self.setWindowTitle("高级音频播放器")
        self.resize(500, 600)
        self.DictManage = DictManage()
        self.player = QMediaPlayer()
        self.path = path

        # 播放列表相关
        self.filter_lock = threading.Lock()
        self.audio_files = []  # 有效音频文件列表
        self.current_index = -1  # 当前音频索引
        self.current_file = path  # 当前音频文件路径

        # 播放模式：0=顺序播放，1=随机播放，2=单曲循环
        self.play_mode = 0

        self.init_ui()

        # 连接信号
        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        self.player.stateChanged.connect(self.on_state_changed)
        self.slider.sliderMoved.connect(self.set_position)
        self.player.error.connect(self.on_player_error)
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)

        # 连接标记列表面板信号
        self.marker_list_panel.marker_clicked.connect(self.on_marker_jump)
        self.marker_list_panel.marker_edited.connect(self.on_marker_changed)
        self.marker_list_panel.marker_deleted.connect(self.on_marker_changed)

        # 连接播放列表面板信号
        self.playlist_panel.audio_selected.connect(self.on_playlist_audio_selected)
        # self.playlist_panel.set_playlist(self.audio_files, self.current_index)

        # 设置键盘快捷键
        self.setup_shortcuts()

        # 加载音频文件列表（在UI初始化之后）
        file_list = audio_files if audio_files else [path]
        self.load_audio_files(file_list, path)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 创建水平分割器（左侧内容区 + 右侧面板）
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #ddd;
            }
        """)

        # 左侧：歌词和控制区域的容器
        self.left_container = QWidget()
        self.left_container.setMinimumWidth(350)
        layout = QVBoxLayout(self.left_container)
        layout.setContentsMargins(10, 10, 10, 10)

        # 歌词视图
        self.lrc_view = LrcView()
        layout.addWidget(self.lrc_view)

        # 进度条（双进度条组件）
        self.slider = DualSliderWidget()
        layout.addWidget(self.slider)

        # 时间显示标签
        time_layout = QHBoxLayout()
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("font-size: 12px; color: #555;")
        self.time_label.setAlignment(Qt.AlignCenter)
        time_layout.addWidget(self.time_label)
        layout.addLayout(time_layout)

        # 控制按钮区域 - 居中布局
        control_layout = QHBoxLayout()
        control_layout.setSpacing(0)

        # 左侧弹簧 - 推动中央按钮组居中
        control_layout.addStretch()

        # 中央：所有主要控制按钮组（模式、上一首、播放、下一首、音量）
        central_controls_layout = QHBoxLayout()
        central_controls_layout.setSpacing(5)

        # 播放模式按钮
        self.btn_mode = QPushButton("🔁")
        self.btn_mode.setFixedSize(40, 40)
        self.btn_mode.setToolTip("顺序播放")
        self.btn_mode.clicked.connect(self.toggle_play_mode)
        self.btn_mode.setStyleSheet("""
            QPushButton {
                font-size: 22px;
                border: none;
                border-radius: 20px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.1);
            }
        """)
        central_controls_layout.addWidget(self.btn_mode)

        # 上一首按钮
        self.btn_previous = QPushButton("⏮")
        self.btn_previous.setFixedSize(40, 40)
        self.btn_previous.setToolTip("上一首")
        self.btn_previous.clicked.connect(self.play_previous)
        self.btn_previous.setStyleSheet("""
            QPushButton {
                font-size: 22px;
                border: none;
                border-radius: 20px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.1);
            }
        """)
        central_controls_layout.addWidget(self.btn_previous)

        # 播放/暂停按钮
        self.btn_play = QPushButton("▶️")
        self.btn_play.setFixedSize(40, 40)
        self.btn_play.setToolTip("播放")
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_play.setStyleSheet("""
            QPushButton {
                font-size: 22px;
                border: none;
                border-radius: 20px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.1);
            }
        """)
        central_controls_layout.addWidget(self.btn_play)

        # 下一首按钮
        self.btn_next = QPushButton("⏭")
        self.btn_next.setFixedSize(40, 40)
        self.btn_next.setToolTip("下一首")
        self.btn_next.clicked.connect(self.play_next)
        self.btn_next.setStyleSheet("""
            QPushButton {
                font-size: 22px;
                border: none;
                border-radius: 20px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.1);
            }
        """)
        central_controls_layout.addWidget(self.btn_next)

        # 音量按钮
        self.btn_volume = QPushButton("🔊")
        self.btn_volume.setFixedSize(40, 40)
        self.btn_volume.setToolTip("音量")
        self.btn_volume.clicked.connect(self.toggle_volume_slider)
        self.btn_volume.setStyleSheet("""
            QPushButton {
                font-size: 22px;
                border: none;
                border-radius: 20px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.1);
            }
        """)
        central_controls_layout.addWidget(self.btn_volume)

        control_layout.addLayout(central_controls_layout)

        # 右侧弹簧 - 推动中央按钮组居中
        control_layout.addStretch()

        layout.addLayout(control_layout)

        # 将左侧容器添加到分割器
        splitter.addWidget(self.left_container)

        # 右侧：面板容器（标记列表 + 播放列表切换）
        right_panel = QWidget()
        right_panel.setMinimumWidth(280)
        right_panel_layout = QVBoxLayout(right_panel)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        right_panel_layout.setSpacing(0)

        # 切换按钮区域
        switch_layout = QHBoxLayout()
        switch_layout.setContentsMargins(0, 0, 0, 0)
        switch_layout.setSpacing(0)

        # 标记列表按钮
        self.btn_show_markers = QPushButton("📋 标记")
        self.btn_show_markers.setCheckable(True)
        self.btn_show_markers.setChecked(True)
        self.btn_show_markers.clicked.connect(lambda: self.switch_right_panel(0))
        self.btn_show_markers.setStyleSheet("""
            QPushButton {
                padding: 8px;
                border: none;
                background-color: transparent;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.05);
            }
            QPushButton:checked {
                background-color: rgba(52, 152, 219, 0.1);
                border-bottom: 2px solid #3498db;
                font-weight: bold;
            }
        """)
        switch_layout.addWidget(self.btn_show_markers)

        # 播放列表按钮
        self.btn_show_playlist = QPushButton("☰ 播放列表")
        self.btn_show_playlist.setCheckable(True)
        self.btn_show_playlist.setChecked(False)
        self.btn_show_playlist.clicked.connect(lambda: self.switch_right_panel(1))
        self.btn_show_playlist.setStyleSheet("""
            QPushButton {
                padding: 8px;
                border: none;
                background-color: transparent;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.05);
            }
            QPushButton:checked {
                background-color: rgba(52, 152, 219, 0.1);
                border-bottom: 2px solid #3498db;
                font-weight: bold;
            }
        """)
        switch_layout.addWidget(self.btn_show_playlist)

        right_panel_layout.addLayout(switch_layout)

        # 创建标记列表面板
        self.marker_list_panel = MarkerListPanel()

        # 创建快速标记创建区域
        self.quick_marker_creator = QuickMarkerCreator()
        self.quick_marker_creator.marker_created.connect(self.on_marker_changed)

        # 创建播放列表面板
        self.playlist_panel = PlaylistPanel()

        # 将组件添加到布局（初始只显示播放列表）
        right_panel_layout.addWidget(self.quick_marker_creator)
        right_panel_layout.addWidget(self.marker_list_panel)
        right_panel_layout.addWidget(self.playlist_panel)
        self.playlist_panel.hide()

        splitter.addWidget(right_panel)

        # 设置分割器初始比例（左侧占2/3，右侧占1/3）
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        # 将分割器添加到主布局
        main_layout.addWidget(splitter)

        # 创建弹出音量面板
        self.volume_popup = QWidget(self, Qt.Popup | Qt.FramelessWindowHint)
        self.volume_popup.setStyleSheet("""
            QWidget {
                background-color: rgba(52, 62, 78, 0.95);
                border-radius: 8px;
                padding: 6px 10px 6px 10px;
            }
        """)

        popup_layout = QVBoxLayout(self.volume_popup)
        popup_layout.setContentsMargins(0, 0, 0, 0)
        popup_layout.setSpacing(2)

        # 音量值标签
        self.volume_value_label = QLabel("50")
        self.volume_value_label.setAlignment(Qt.AlignCenter)
        self.volume_value_label.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        popup_layout.addWidget(self.volume_value_label)

        # 竖向滑块
        self.volume_slider_vertical = QSlider(Qt.Vertical)
        self.volume_slider_vertical.setRange(0, 100)
        self.volume_slider_vertical.setValue(50)
        self.volume_slider_vertical.setFixedHeight(110)
        self.volume_slider_vertical.valueChanged.connect(self.on_volume_changed)
        popup_layout.addWidget(self.volume_slider_vertical, 0, Qt.AlignCenter)

        # 底部留白空间
        popup_layout.addSpacing(15)

        self.volume_popup.setFixedSize(65, 165)
        self.volume_popup.hide()

        # 设置初始音量
        self.player.setVolume(50)

    def closeEvent(self, a0):
        self.player.pause()
        return super().closeEvent(a0)

    def load_media(self, path=None):
        if path is None:
            path = self.path
        else:
            self.path = path

        if not os.path.exists(path):
            QMessageBox.warning(self, "文件错误", f"文件不存在:\n{path}")
            return

        try:
            self.player.setMedia(QMediaContent(QUrl.fromLocalFile(os.path.abspath(path))))

            # 更新窗口标题显示当前播放的文件
            file_name = os.path.basename(path)
            total_files = len(self.audio_files)
            self.setWindowTitle(f"高级音频播放器 - {file_name} ({self.current_index + 1}/{total_files})")

            # 通用的歌词文件路径处理，支持所有音频格式
            lrc_path = os.path.splitext(path)[0] + '.lrc'
            self.lrc_view.load_lrc(lrc_path)

            # 从数据库加载标记数据
            normalized_path = path.replace('\\', '/')

            # 设置音频文件路径（用于后续创建标记）
            self.slider.set_audio_file_path(normalized_path)
            self.slider.set_quick_marker_creator(self.quick_marker_creator)
            self.slider.set_marker_list_panel(self.marker_list_panel)
            self.slider.marker_display.set_main_window(self)  # 设置主窗口引用
            self.marker_list_panel.set_audio_file_path(normalized_path)
            self.marker_list_panel.set_main_window(self)  # 设置主窗口引用
            self.quick_marker_creator.set_audio_file_path(normalized_path)

            # 加载已有标记
            markers_data = self.DictManage.get_audio_markers(normalized_path)

            # 转换为 MarkerSlider 格式
            markers = []
            for m in markers_data:
                if m['type'] == 0:  # 点标记
                    markers.append({
                        'id': m['id'],
                        'type': 0,
                        'time': m['time'],
                        'color': m['color'],
                        'label': m['label']
                    })
                else:  # 范围标记
                    markers.append({
                        'id': m['id'],
                        'type': 1,
                        'start': m['start'],
                        'end': m['end'],
                        'color': m['color'],
                        'label': m['label']
                    })

            self.slider.set_markers(markers)
        except Exception as e:
            QMessageBox.critical(self, "加载错误", f"无法加载媒体文件:\n{str(e)}")

    def toggle_play(self):
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def on_state_changed(self, state):
        """根据播放状态更新按钮图标"""
        if state == QMediaPlayer.PlayingState:
            self.btn_play.setText("⏸")
            self.btn_play.setToolTip("暂停")
        else:
            self.btn_play.setText("▶️")
            self.btn_play.setToolTip("播放")

    def on_position_changed(self, ms):
        if not self.slider.isSliderDown():
            self.slider.setValue(ms)
        self.lrc_view.update_position(ms)
        # 更新时间显示
        self.update_time_label(ms, self.player.duration())

    def on_duration_changed(self, ms):
        self.slider.setRange(0, ms)
        self.update_time_label(self.player.position(), ms)

        # 设置快速标记创建器的最大时长限制
        self.quick_marker_creator.start_time_input.set_max_duration(ms)
        self.quick_marker_creator.end_time_input.set_max_duration(ms)

        # 设置标记列表面板的最大时长限制
        self.marker_list_panel.set_max_duration(ms)

    def update_time_label(self, current_ms, total_ms):
        """更新时间显示标签"""
        current_time = format_time(current_ms)
        total_time = format_time(total_ms)
        self.time_label.setText(f"{current_time} / {total_time}")

    def set_position(self, ms):
        self.player.setPosition(ms)

    def on_volume_changed(self, value):
        """音量改变时的回调"""
        self.player.setVolume(value)

        # 更新音量值标签
        self.volume_value_label.setText(str(value))

        # 更新音量按钮图标
        if value == 0:
            self.btn_volume.setText("🔇")
        elif value < 50:
            self.btn_volume.setText("🔉")
        else:
            self.btn_volume.setText("🔊")

    def on_player_error(self):
        """播放器错误处理"""
        error_msg = self.player.errorString()
        QMessageBox.critical(self, "播放错误", f"播放器遇到错误:\n{error_msg}")

    def on_marker_jump(self, marker_id):
        """跳转到标记位置"""
        # 从标记列表中查找对应标记的时间位置
        for marker in self.slider.marker_display.markers:
            if marker.get('id') == marker_id:
                # 跳转到标记位置
                if marker.get('type') == 0:  # 点标记
                    self.player.setPosition(marker['time'])
                else:  # 范围标记，跳转到起点
                    self.player.setPosition(marker['start'])
                break

    def edit_marker(self, marker):
        """
        统一的标记编辑方法
        供 MarkerDisplayWidget 和 MarkerListPanel 调用

        :param marker: 标记数据字典
        :return: 是否编辑成功
        """
        if not hasattr(self, 'slider') or not self.slider.marker_display.audio_file_path:
            return False

        # 获取预设列表
        presets = self.DictManage.get_all_marker_presets()

        # 打开编辑对话框
        from .marker_edit_dialog import MarkerEditDialog
        dialog = MarkerEditDialog(
            marker_data=marker,
            presets=presets,
            max_duration_ms=self.player.duration(),
            parent=self
        )

        if dialog.exec_() == MarkerEditDialog.Accepted:
            result = dialog.get_data()

            try:
                # 构建更新参数
                update_params = {
                    'label': result['label'],
                    'color': result['color'],
                    'preset_id': result['preset_id']
                }

                # 根据标记类型添加时间参数
                if result['type'] == 0:  # 点标记
                    update_params['time'] = result['time']
                    update_params['start'] = None
                    update_params['end'] = None
                else:  # 范围标记
                    update_params['start'] = result['start']
                    update_params['end'] = result['end']
                    update_params['time'] = None

                # 更新数据库
                normalized_path = self.slider.marker_display.audio_file_path
                self.DictManage.update_audio_marker(
                    normalized_path,
                    marker['id'],
                    **update_params
                )

                # 刷新界面
                self.on_marker_changed()

                return True

            except Exception as e:
                QMessageBox.critical(self, "错误", f"更新标记失败:\n{str(e)}")
                return False

        return False

    def on_marker_changed(self):
        """标记被编辑或删除后刷新进度条显示"""
        # 重新加载标记数据到进度条
        self.slider._reload_markers()
        # 刷新标记列表面板
        self.marker_list_panel.load_markers()

    def switch_right_panel(self, panel_index):
        """切换右侧面板显示
        Args:
            panel_index: 0=标记列表, 1=播放列表
        """
        if panel_index == 0:
            # 显示标记列表
            self.btn_show_markers.setChecked(True)
            self.btn_show_playlist.setChecked(False)
            self.quick_marker_creator.show()
            self.marker_list_panel.show()
            self.playlist_panel.hide()
        else:
            # 显示播放列表
            self.btn_show_markers.setChecked(False)
            self.btn_show_playlist.setChecked(True)
            self.quick_marker_creator.hide()
            self.marker_list_panel.hide()
            self.playlist_panel.show()
            # 更新播放列表
            self.playlist_panel.set_playlist(self.audio_files, self.current_index)

    def toggle_volume_slider(self):
        """切换音量面板的显示/隐藏"""
        if self.volume_popup.isVisible():
            self.volume_popup.hide()
        else:
            # 计算弹出位置（音量按钮正上方）
            btn_global_pos = self.btn_volume.mapToGlobal(QPoint(0, 0))
            popup_x = btn_global_pos.x() - (self.volume_popup.width() - self.btn_volume.width()) // 2
            popup_y = btn_global_pos.y() - self.volume_popup.height() - 10
            self.volume_popup.move(popup_x, popup_y)
            self.volume_popup.show()

    def toggle_play_mode(self):
        """切换播放模式：顺序播放 -> 随机播放 -> 单曲循环"""
        self.play_mode = (self.play_mode + 1) % 3

        if self.play_mode == 0:
            # 顺序播放
            self.btn_mode.setText("🔁")
            self.btn_mode.setToolTip("顺序播放")
        elif self.play_mode == 1:
            # 随机播放
            self.btn_mode.setText("🔀")
            self.btn_mode.setToolTip("随机播放")
        else:
            # 单曲循环
            self.btn_mode.setText("🔂")
            self.btn_mode.setToolTip("单曲循环")

    def on_playlist_audio_selected(self, index):
        """播放列表中选择了某个音频"""
        self.play_audio_at_index(index)
        self.player.play()

    def open_preset_manager(self):
        """打开标记预设管理对话框"""
        dialog = MarkerPresetManager(self)
        dialog.exec_()

    def setup_shortcuts(self):
        """设置键盘快捷键"""
        # 左方向键 - 上一首
        self.shortcut_prev = QShortcut(QKeySequence(Qt.Key_Left), self)
        self.shortcut_prev.activated.connect(self.play_previous)

        # 右方向键 - 下一首
        self.shortcut_next = QShortcut(QKeySequence(Qt.Key_Right), self)
        self.shortcut_next.activated.connect(self.play_next)

        # 空格键 - 播放/暂停
        self.shortcut_play = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.shortcut_play.activated.connect(self.toggle_play)

    def play_previous(self):
        """播放上一首（根据播放模式）"""
        if not self.audio_files or len(self.audio_files) == 0:
            return

        with self.filter_lock:
            # 同步当前索引（防止文件列表被过滤后索引错位）
            if self.current_index >= len(self.audio_files) or self.audio_files[self.current_index] != self.current_file:
                try:
                    self.current_index = self.audio_files.index(self.current_file)
                except:
                    self.current_index = 0

            # 根据播放模式计算上一首的索引
            if self.play_mode == 0:
                # 顺序播放：循环到上一首
                prev_index = (self.current_index - 1) % len(self.audio_files)
            elif self.play_mode == 1:
                # 随机播放：随机选择（排除当前歌曲）
                if len(self.audio_files) > 1:
                    candidates = list(range(len(self.audio_files)))
                    candidates.remove(self.current_index)
                    prev_index = random.choice(candidates)
                else:
                    prev_index = self.current_index
            else:
                # 单曲循环（play_mode == 2）：允许手动切换
                prev_index = (self.current_index - 1) % len(self.audio_files)

        # 播放上一首
        self.play_audio_at_index(prev_index)
        self.player.play()

    def play_next(self):
        """播放下一首（根据播放模式）"""
        if not self.audio_files or len(self.audio_files) == 0:
            return

        with self.filter_lock:
            # 同步当前索引（防止文件列表被过滤后索引错位）
            if self.current_index >= len(self.audio_files) or self.audio_files[self.current_index] != self.current_file:
                try:
                    self.current_index = self.audio_files.index(self.current_file)
                except:
                    self.current_index = 0

            # 根据播放模式计算下一首的索引
            if self.play_mode == 0:
                # 顺序播放
                next_index = (self.current_index + 1) % len(self.audio_files)
            elif self.play_mode == 1:
                # 随机播放
                if len(self.audio_files) > 1:
                    candidates = list(range(len(self.audio_files)))
                    candidates.remove(self.current_index)
                    next_index = random.choice(candidates)
                else:
                    next_index = self.current_index
            else:
                # 单曲循环（play_mode == 2）：允许手动切换到下一首
                next_index = (self.current_index + 1) % len(self.audio_files)

        # 播放下一首
        self.play_audio_at_index(next_index)
        self.player.play()

    def on_media_status_changed(self, status):
        """媒体状态改变时的回调"""
        # 当当前音频播放结束时，根据播放模式处理
        if status == QMediaPlayer.EndOfMedia:
            if self.play_mode == 2:
                # 单曲循环：重新播放当前歌曲
                self.player.setPosition(0)
                self.player.play()
            else:
                # 顺序播放或随机播放：播放下一首
                self.play_next()

    def _filter_file(self, file_path):
        """过滤文件列表，仅保留音频文件"""
        supported_formats = ['.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.wma', '.ape']

        if not os.path.exists(file_path):
            with self.filter_lock:
                try:
                    self.audio_files.remove(file_path)
                except:
                    pass
            return

        # 检查文件扩展名
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in supported_formats:
            with self.filter_lock:
                try:
                    self.audio_files.remove(file_path)
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
        if not self.audio_files and self.current_index == -1:
            self.setWindowTitle("高级音频播放器 - 正在加载...")
        else:
            self.update_title()

    def load_audio_files(self, file_paths: list, show_file_path=None):
        """加载音频文件列表，过滤非音频文件"""
        if self.current_index != -1 and show_file_path is None:
            show_file_path = self.audio_files[self.current_index]

        # 初始化文件列表
        self.audio_files = file_paths.copy()

        # 在后台线程中执行过滤
        self._start_background_filtering(file_paths)

        if show_file_path is not None:
            try:
                index = self.audio_files.index(show_file_path)
                self.play_audio_at_index(index)
            except:
                pass

        if self.current_index == -1:
            # 如果有有效音频，播放第一首
            if self.audio_files:
                self.play_audio_at_index(0)
            else:
                self.setWindowTitle("高级音频播放器 - 正在加载...")

    def play_audio_at_index(self, index):
        """播放指定索引的音频"""
        if not self.audio_files or index < 0 or index >= len(self.audio_files):
            return False

        # 加载并播放音频
        file_path = self.audio_files[index]
        self.current_file = file_path
        self.current_index = index
        self.load_media(file_path)

        # 更新播放列表面板的当前索引
        if hasattr(self, 'playlist_panel'):
            self.playlist_panel.update_current_index(index)

        return True

    def update_title(self):
        """更新窗口标题"""
        if self.current_index >= 0 and self.audio_files:
            with self.filter_lock:
                # 同步当前索引
                if self.current_index >= len(self.audio_files) or self.audio_files[self.current_index] != self.current_file:
                    try:
                        self.current_index = self.audio_files.index(self.current_file)
                    except:
                        self.current_index = 0

            file_name = os.path.basename(self.current_file)
            total_files = len(self.audio_files)
            self.setWindowTitle(f"高级音频播放器 - {file_name} ({self.current_index + 1}/{total_files})")
        else:
            self.setWindowTitle("高级音频播放器")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # 设置暗色调主题
    app.setStyle("Fusion")
    path = "" 
    player = ModernPlayer(path)
    player.show()
    sys.exit(app.exec_())