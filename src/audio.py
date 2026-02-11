import sys
import os
import re
import threading
import random

from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QPushButton, QWidget, QSlider, QLabel, QScrollArea, QStyle,
                             QStyleOptionSlider, QMessageBox, QMenu, QShortcut)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import Qt, QUrl, QPoint, QTime
from PyQt5.QtGui import QPainter, QColor, QMouseEvent, QKeySequence

from .MarkerEditDialog import MarkerEditDialog
from .DictManage import DictManage
from .MarkerListPanel import MarkerListPanel
from .MarkerPresetManager import MarkerPresetManager
from .PlaylistPanel import PlaylistPanel

# 格式化毫秒为 00:00 格式
def format_time(ms):
    time = QTime(0, 0).addMSecs(ms)
    return time.toString("mm:ss")

# --- 1. 增强版进度条 (支持时间预览与标记) ---
class MarkerSlider(QSlider):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.DictManage = DictManage()
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

        # Ctrl 交互相关属性
        self.is_dragging_marker = False  # 是否正在拖拽标记
        self.dragging_marker_id = None   # 拖拽的标记ID
        self.drag_type = None            # 'start', 'end', 'body', 'point'
        self.is_creating_range = False   # 是否正在创建范围标记
        self.range_start_pos = None      # 范围起始位置（毫秒值）
        self.temp_range_marker = None    # 临时范围标记（拖动时显示）

        # 音频文件路径（用于保存标记到数据库）
        self.audio_file_path = None

    def set_markers(self, markers):
        self.markers = markers
        self.update()

    def set_audio_file_path(self, path):
        """设置音频文件路径（用于数据库操作）"""
        self.audio_file_path = path

    def _find_marker_at(self, x):
        """检测鼠标位置是否在标记上，返回 (marker, index) 或 (None, None)"""
        if self.maximum() <= 0:
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

    def _get_drag_type(self, x, marker):
        """判断拖拽类型（点/起点/终点/整体）"""
        if "time" in marker:
            return "point"

        # 范围标记
        start_x = self._value_to_pixel(marker["start"])
        end_x = self._value_to_pixel(marker["end"])

        # 边缘检测阈值
        edge_threshold = 8

        if abs(x - start_x) < edge_threshold:
            return "start"
        elif abs(x - end_x) < edge_threshold:
            return "end"
        else:
            return "body"

    def _open_marker_edit_dialog(self, marker_data=None):
        """打开标记编辑对话框"""
        # 获取预设列表
        presets = self.DictManage.get_all_marker_presets()

        dialog = MarkerEditDialog(marker_data=marker_data, presets=presets, parent=self)
        if dialog.exec_() == MarkerEditDialog.Accepted:
            return dialog.get_data()
        return None

    def _update_marker_position_preview(self, new_pos):
        """拖拽时实时更新标记位置预览"""
        if not self.dragging_marker_id:
            return

        # 找到被拖拽的标记
        for marker in self.markers:
            if marker.get('id') == self.dragging_marker_id:
                if self.drag_type == "point":
                    # 点标记：直接移动
                    marker['time'] = new_pos
                elif self.drag_type == "start":
                    # 范围标记起点：调整起点位置
                    marker['start'] = min(new_pos, marker['end'] - 100)  # 至少保留100ms宽度
                elif self.drag_type == "end":
                    # 范围标记终点：调整终点位置
                    marker['end'] = max(new_pos, marker['start'] + 100)
                elif self.drag_type == "body":
                    # 范围标记整体：平移
                    duration = marker['end'] - marker['start']
                    marker['start'] = new_pos
                    marker['end'] = new_pos + duration

                self.update()
                break

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

        # 处理标记拖拽（来自右键菜单的移动操作）
        if self.is_dragging_marker and self.dragging_marker_id is not None:
            # 正在拖拽标记，实时更新标记位置
            new_pos = self._pixel_to_value(event.x())
            self._update_marker_position_preview(new_pos)
            display_text = "拖拽标记中..."
        # Ctrl 交互：处理拖动创建范围标记
        elif event.modifiers() & Qt.ControlModifier:
            if self.is_creating_range and self.range_start_pos is not None:
                # 正在创建范围标记，显示临时范围
                end_pos = self._pixel_to_value(event.x())
                start = min(self.range_start_pos, end_pos)
                end = max(self.range_start_pos, end_pos)

                self.temp_range_marker = {
                    "start": start,
                    "end": end,
                    "color": "#3498db",
                    "label": "新建范围"
                }
                self.update()  # 重绘以显示临时范围
                display_text = f"📏 {format_time(start)} - {format_time(end)}"
        else:
            # 正常悬停：检测是否悬停在标记点上
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

    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件：完成标记创建或拖拽"""
        if event.button() == Qt.LeftButton:
            # 检查状态标志而不是 Ctrl 键，因为用户可能在释放鼠标前释放了 Ctrl
            if self.is_creating_range and self.range_start_pos is not None:
                # 完成范围标记创建
                end_pos = self._pixel_to_value(event.x())

                # 判断是点标记还是范围标记
                if abs(end_pos - self.range_start_pos) < 500:  # 小于500ms视为点击
                    # 创建点标记
                    marker_data = {
                        'type': 0,
                        'time': self.range_start_pos
                    }
                else:
                    # 创建范围标记
                    start = min(self.range_start_pos, end_pos)
                    end = max(self.range_start_pos, end_pos)
                    marker_data = {
                        'type': 1,
                        'start': start,
                        'end': end
                    }

                # 打开编辑对话框
                result = self._open_marker_edit_dialog(marker_data)
                if result and self.audio_file_path:
                    # 保存到数据库
                    normalized_path = self.audio_file_path

                    # 构建完整的标记数据
                    marker_to_save = marker_data.copy()
                    marker_to_save.update(result)

                    # 添加到数据库
                    self.DictManage.add_audio_marker(normalized_path, marker_to_save)

                    # 重新加载标记并刷新显示
                    self._reload_markers()

                # 清除临时状态
                self.is_creating_range = False
                self.range_start_pos = None
                self.temp_range_marker = None
                self.update()

            elif self.is_dragging_marker and self.dragging_marker_id is not None:
                # 完成标记拖拽，保存到数据库
                if self.audio_file_path:
                    normalized_path = self.audio_file_path

                    # 找到被拖拽的标记
                    for marker in self.markers:
                        if marker.get('id') == self.dragging_marker_id:
                            # 更新数据库
                            if marker.get('type') == 0:  # 点标记
                                self.DictManage.update_audio_marker(
                                    normalized_path,
                                    self.dragging_marker_id,
                                    time=marker['time']
                                )
                            else:  # 范围标记
                                self.DictManage.update_audio_marker(
                                    normalized_path,
                                    self.dragging_marker_id,
                                    start=marker['start'],
                                    end=marker['end']
                                )
                            break

                # 清除拖拽状态
                self.is_dragging_marker = False
                self.dragging_marker_id = None
                self.drag_type = None
                self.setMouseTracking(False)
                QApplication.restoreOverrideCursor()

        super().mouseReleaseEvent(event)

    def _reload_markers(self):
        """从数据库重新加载标记"""
        if not self.audio_file_path:
            return

        normalized_path = self.audio_file_path
        markers_data = self.DictManage.get_audio_markers(normalized_path)

        # 转换为 MarkerSlider 格式
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
        self.floating_label.hide()
        super().leaveEvent(event)

    def contextMenuEvent(self, event):
        """右键菜单事件"""
        click_x = event.x()
        marker, marker_idx = self._find_marker_at(click_x)

        menu = QMenu(self)

        if marker:
            # 在标记上右键：显示编辑、移动和删除选项
            edit_action = menu.addAction("📝 编辑标记")
            move_action = menu.addAction("🔄 移动标记")
            delete_action = menu.addAction("🗑️ 删除标记")

            action = menu.exec_(event.globalPos())

            if action == edit_action:
                self._edit_marker(marker)
            elif action == move_action:
                self._start_move_marker(marker, click_x)
            elif action == delete_action:
                self._delete_marker(marker)
        else:
            # 在空白处右键：显示创建点标记选项
            create_point_action = menu.addAction("➕ 在此创建点标记")

            action = menu.exec_(event.globalPos())

            if action == create_point_action:
                time_pos = self._pixel_to_value(click_x)
                marker_data = {
                    'type': 0,
                    'time': time_pos
                }
                result = self._open_marker_edit_dialog(marker_data)
                if result and self.audio_file_path:
                    normalized_path = self.audio_file_path

                    marker_to_save = marker_data.copy()
                    marker_to_save.update(result)

                    self.DictManage.add_audio_marker(normalized_path, marker_to_save)
                    self._reload_markers()

    def _start_move_marker(self, marker, click_x):
        """启动标记移动模式"""
        # 设置移动状态
        self.is_dragging_marker = True
        self.dragging_marker_id = marker.get('id')
        self.drag_type = self._get_drag_type(click_x, marker)

        # 提示用户
        QApplication.setOverrideCursor(Qt.SizeHorCursor)

        # 临时启用鼠标跟踪以实时更新
        self.setMouseTracking(True)

    def _edit_marker(self, marker):
        """编辑标记"""
        if not self.audio_file_path:
            return

        # 打开编辑对话框，预填充现有数据
        result = self._open_marker_edit_dialog(marker)
        if result:
            normalized_path = self.audio_file_path

            # 更新数据库
            self.DictManage.update_audio_marker(
                normalized_path,
                marker['id'],
                label=result['label'],
                color=result['color'],
                preset_id=result['preset_id']
            )

            # 重新加载标记
            self._reload_markers()

    def _delete_marker(self, marker):
        """删除标记"""
        if not self.audio_file_path:
            return

        normalized_path = self.audio_file_path

        # 从数据库删除
        self.DictManage.delete_audio_marker(normalized_path, marker['id'])

        # 重新加载标记
        self._reload_markers()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            click_x = event.x()

            # Ctrl 键交互：仅创建标记
            if event.modifiers() & Qt.ControlModifier:
                # 开始创建范围标记（如果拖动）或点标记（如果只是点击）
                self.is_creating_range = True
                self.range_start_pos = self._pixel_to_value(click_x)
                return  # 阻止默认滑块行为

            # 默认行为：播放位置跳转
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

        # 绘制已保存的标记
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

        # 绘制临时范围标记（Ctrl+拖动时显示）
        if self.temp_range_marker:
            color = QColor(self.temp_range_marker.get('color', '#3498db'))
            x1 = self._value_to_pixel(self.temp_range_marker['start'])
            x2 = self._value_to_pixel(self.temp_range_marker['end'])
            rect_color = QColor(color)
            rect_color.setAlpha(80)  # 更透明以区分临时标记
            painter.setBrush(rect_color)
            painter.setPen(Qt.DashLine)
            painter.setPen(color)
            painter.drawRect(x1, 8, x2 - x1, self.height() - 16)

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

# --- 3. 主窗口 ---
class ModernPlayer(QMainWindow):
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
        # 创建菜单栏
        menubar = self.menuBar()

        # 标记菜单
        marker_menu = menubar.addMenu("标记")

        # 显示标记列表动作
        show_markers_action = marker_menu.addAction("📋 显示标记列表")
        show_markers_action.triggered.connect(self.show_marker_list)

        # 管理预设动作
        manage_presets_action = marker_menu.addAction("⚙️ 管理预设")
        manage_presets_action.triggered.connect(self.open_preset_manager)

        widget = QWidget()
        self.setCentralWidget(widget)
        main_layout = QVBoxLayout(widget)

        # 创建标记列表面板（不添加到主布局，作为独立窗口）
        self.marker_list_panel = MarkerListPanel()
        self.marker_list_panel.setWindowFlags(Qt.Window)
        self.marker_list_panel.setWindowTitle("标记列表")
        self.marker_list_panel.resize(350, 500)

        # 创建水平布局容器（左侧内容区 + 播放列表）
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        # 左侧：歌词和控制区域的容器
        self.left_container = QWidget()
        self.left_container.setMinimumWidth(350)
        layout = QVBoxLayout(self.left_container)
        layout.setContentsMargins(0, 0, 0, 0)

        # 歌词视图
        self.lrc_view = LrcView()
        layout.addWidget(self.lrc_view)

        # 进度条
        self.slider = MarkerSlider(Qt.Horizontal)
        layout.addWidget(self.slider)

        # 时间显示标签
        time_layout = QHBoxLayout()
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("font-size: 12px; color: #555;")
        self.time_label.setAlignment(Qt.AlignCenter)
        time_layout.addWidget(self.time_label)
        layout.addLayout(time_layout)

        # 控制按钮区域 - 主流播放器样式
        control_layout = QHBoxLayout()
        control_layout.setSpacing(0)

        # 左侧占位符（与右侧播放列表按钮宽度相同，保持对称）
        left_spacer = QWidget()
        left_spacer.setFixedWidth(40)
        control_layout.addWidget(left_spacer)

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

        # 播放列表按钮（在右侧，与左侧占位符对称）
        self.btn_playlist = QPushButton("☰")
        self.btn_playlist.setFixedSize(40, 40)
        self.btn_playlist.setToolTip("播放列表")
        self.btn_playlist.clicked.connect(self.show_playlist)
        self.btn_playlist.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                border: none;
                border-radius: 20px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.1);
            }
        """)
        control_layout.addWidget(self.btn_playlist)

        layout.addLayout(control_layout)

        # 将左侧容器添加到水平布局
        content_layout.addWidget(self.left_container)

        # 右侧：播放列表面板（侧边展开，默认隐藏）
        self.playlist_panel = PlaylistPanel()
        self.playlist_panel.setFixedWidth(350)  # 固定宽度
        self.playlist_panel.hide()
        content_layout.addWidget(self.playlist_panel)

        # 将水平布局添加到主布局
        main_layout.addLayout(content_layout)

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
            self.marker_list_panel.set_audio_file_path(normalized_path)

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
        for marker in self.slider.markers:
            if marker.get('id') == marker_id:
                # 跳转到标记位置
                if marker.get('type') == 0:  # 点标记
                    self.player.setPosition(marker['time'])
                else:  # 范围标记，跳转到起点
                    self.player.setPosition(marker['start'])
                break

    def on_marker_changed(self):
        """标记被编辑或删除后刷新进度条显示"""
        # 重新加载标记数据到进度条
        self.slider._reload_markers()

    def show_marker_list(self):
        """显示标记列表面板"""
        self.marker_list_panel.show()
        self.marker_list_panel.raise_()
        self.marker_list_panel.activateWindow()

    def show_playlist(self):
        """切换播放列表的显示/隐藏"""
        if self.playlist_panel.isVisible():
            # 隐藏播放列表
            playlist_width = self.playlist_panel.width()

            # 隐藏面板
            self.playlist_panel.hide()

            # 缩小窗口宽度
            current_width = self.width()
            self.left_container.setFixedWidth(self.left_container.width())
            self.setFixedWidth(current_width - playlist_width - 10)
            self.left_container.setMinimumWidth(350)
            self.left_container.setMaximumWidth(16777215)
            self.setMinimumWidth(370)
            self.setMaximumWidth(16777215)

        else:
            self.playlist_panel.set_playlist(self.audio_files, self.current_index)
            playlist_width = 360  # 播放列表加间隔的固定宽度

            # 获取当前窗口几何信息
            current_width = self.width()
            current_x = self.x()

            # 获取屏幕可用宽度
            screen = QApplication.desktop().availableGeometry(self)
            screen_right = screen.x() + screen.width()

            # 计算新宽度
            new_width = current_width + playlist_width

            # 检查窗口右边界是否会超出屏幕
            if current_x + new_width <= screen_right:
                self.setFixedWidth(new_width)
                self.setMinimumWidth(720)
                self.setMaximumWidth(16777215)

            self.playlist_panel.show()
            

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