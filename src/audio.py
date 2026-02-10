import sys
import os
import re

from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QPushButton, QWidget, QSlider, QLabel, QScrollArea, QStyle,
                             QStyleOptionSlider, QMessageBox, QMenu)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import Qt, QUrl, QPoint, QTime
from PyQt5.QtGui import QPainter, QColor, QMouseEvent

from .MarkerEditDialog import MarkerEditDialog
from .DictManage import DictManage
from .MarkerListPanel import MarkerListPanel
from .MarkerPresetManager import MarkerPresetManager

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
    def __init__(self, path):
        super().__init__()
        self.setWindowTitle("高级音频播放器")
        self.resize(500, 600)
        self.DictManage = DictManage()
        self.player = QMediaPlayer()
        self.path = path
        self.init_ui()

        # 连接信号
        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        self.player.stateChanged.connect(self.on_state_changed)
        self.slider.sliderMoved.connect(self.set_position)
        self.player.error.connect(self.on_player_error)

        # 连接标记列表面板信号
        self.marker_list_panel.marker_clicked.connect(self.on_marker_jump)
        self.marker_list_panel.marker_edited.connect(self.on_marker_changed)
        self.marker_list_panel.marker_deleted.connect(self.on_marker_changed)

    def init_ui(self):
        # 创建菜单栏
        menubar = self.menuBar()

        # 标记菜单
        marker_menu = menubar.addMenu("标记")

        # 管理预设动作
        manage_presets_action = marker_menu.addAction("📋 管理预设")
        manage_presets_action.triggered.connect(self.open_preset_manager)

        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QVBoxLayout(widget)

        # 主内容区域：歌词视图和标记列表并排显示
        content_layout = QHBoxLayout()

        # 左侧：歌词视图
        self.lrc_view = LrcView()
        content_layout.addWidget(self.lrc_view, 2)  # 占2份宽度

        # 右侧：标记列表面板
        self.marker_list_panel = MarkerListPanel()
        self.marker_list_panel.setMaximumWidth(350)  # 限制最大宽度
        content_layout.addWidget(self.marker_list_panel, 1)  # 占1份宽度

        layout.addLayout(content_layout)

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

        # 控制按钮
        btn_layout = QHBoxLayout()
        self.btn_play = QPushButton("▶ 播放")
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_play.setFixedHeight(35)
        btn_layout.addWidget(self.btn_play)

        # 音量控制
        volume_layout = QHBoxLayout()
        volume_label = QLabel("🔊")
        volume_label.setStyleSheet("font-size: 16px;")
        volume_layout.addWidget(volume_label)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setMaximumWidth(100)
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        volume_layout.addWidget(self.volume_slider)

        self.volume_label_value = QLabel("50%")
        self.volume_label_value.setStyleSheet("font-size: 12px; color: #555;")
        self.volume_label_value.setMinimumWidth(35)
        volume_layout.addWidget(self.volume_label_value)

        btn_layout.addLayout(volume_layout)
        layout.addLayout(btn_layout)

        # 设置初始音量
        self.player.setVolume(50)

        # 加载媒体
        self.load_media()

    def load_media(self):
        path = self.path
        if not os.path.exists(path):
            QMessageBox.warning(self, "文件错误", f"文件不存在:\n{path}")
            return

        try:
            self.player.setMedia(QMediaContent(QUrl.fromLocalFile(os.path.abspath(path))))

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
        """根据播放状态更新按钮文本"""
        if state == QMediaPlayer.PlayingState:
            self.btn_play.setText("⏸ 暂停")
        else:
            self.btn_play.setText("▶ 播放")

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
        self.volume_label_value.setText(f"{value}%")

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

    def on_marker_changed(self, marker_id):
        """标记被编辑或删除后刷新进度条显示"""
        # 重新加载标记数据到进度条
        self.slider._reload_markers()

    def open_preset_manager(self):
        """打开标记预设管理对话框"""
        dialog = MarkerPresetManager(self)
        dialog.exec_()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # 设置暗色调主题
    app.setStyle("Fusion")
    path = "" 
    player = ModernPlayer(path)
    player.show()
    sys.exit(app.exec_())