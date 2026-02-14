import sys
import os
import threading
import random
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QSlider, QLabel, QMessageBox, QShortcut, QSplitter)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import Qt, QUrl, QPoint
from PyQt5.QtGui import QKeySequence

from src.core.DictManage import DictManage
from .marker_list_panel import MarkerListPanel
from .marker_preset_manager import MarkerPresetManager
from .playlist_panel import PlaylistPanel
from .quick_marker_creator import QuickMarkerCreator
from .play_back_slider import format_time
from .dual_slider import DualSliderWidget
from .lrc_view import LrcView

class AudioPlayer(QWidget):
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

        # 连接歌词视图信号
        self.lrc_view.seek_requested.connect(self.on_lyric_seek)

        # 设置键盘快捷键
        self.setup_shortcuts()

        # 加载音频文件列表（在UI初始化之后）
        file_list = audio_files if audio_files else [path]
        self.load_audio_files(file_list, path)
        self.player.play()

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
        self.left_container.setMinimumWidth(400)
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
        self.volume_value_label = QLabel("100")
        self.volume_value_label.setAlignment(Qt.AlignCenter)
        self.volume_value_label.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        popup_layout.addWidget(self.volume_value_label)

        # 竖向滑块
        self.volume_slider_vertical = QSlider(Qt.Vertical)
        self.volume_slider_vertical.setRange(0, 100)
        self.volume_slider_vertical.setValue(100)
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
                if m.get('type') == 0:  # 点标记
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

    def on_lyric_seek(self, timestamp_ms):
        """歌词跳转到指定时间位置"""
        self.player.setPosition(timestamp_ms)

    def edit_marker(self, marker: dict):
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
            result['id'] = marker['id']
            try:
                # 更新数据库
                normalized_path = self.slider.marker_display.audio_file_path
                self.DictManage.update_audio_marker(
                    normalized_path,
                    marker['id'],
                    result
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
        # 左方向键 - 后退5秒
        self.shortcut_prev = QShortcut(QKeySequence(Qt.Key_Left), self)
        self.shortcut_prev.activated.connect(self.seek_backward)

        # 右方向键 - 前进5秒
        self.shortcut_next = QShortcut(QKeySequence(Qt.Key_Right), self)
        self.shortcut_next.activated.connect(self.seek_forward)

        # 空格键 - 播放/暂停
        self.shortcut_play = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.shortcut_play.activated.connect(self.toggle_play)

        # I键 - 标记开始时间（In点）
        self.shortcut_mark_in = QShortcut(QKeySequence(Qt.Key_I), self)
        self.shortcut_mark_in.activated.connect(self.mark_in_point)

        # O键 - 标记结束时间（Out点）
        self.shortcut_mark_out = QShortcut(QKeySequence(Qt.Key_O), self)
        self.shortcut_mark_out.activated.connect(self.mark_out_point)

        # M键 - 创建时间点标记（Marker）
        self.shortcut_mark_point = QShortcut(QKeySequence(Qt.Key_M), self)
        self.shortcut_mark_point.activated.connect(self.create_point_marker)

    def seek_backward(self):
        """后退5秒"""
        current_pos = self.player.position()
        new_pos = max(0, current_pos - 5000)  # 5秒 = 5000毫秒
        self.player.setPosition(new_pos)

    def seek_forward(self):
        """前进5秒"""
        current_pos = self.player.position()
        duration = self.player.duration()
        new_pos = min(duration, current_pos + 5000)  # 5秒 = 5000毫秒
        self.player.setPosition(new_pos)

    def mark_in_point(self):
        """标记开始时间（In点）- I键快捷键"""
        # 切换到标记面板（如果当前不在标记面板）
        self.switch_right_panel(0)

        # 获取当前播放时间
        current_ms = self.player.position()

        # 将当前时间同步到快速标记创建器的开始时间
        self.quick_marker_creator.start_time_input.set_from_milliseconds(current_ms)

    def mark_out_point(self):
        """标记结束时间（Out点）- O键快捷键"""
        # 切换到标记面板（如果当前不在标记面板）
        self.switch_right_panel(0)

        # 获取当前播放时间
        current_ms = self.player.position()

        # 将当前时间同步到快速标记创建器的结束时间
        self.quick_marker_creator.end_time_input.set_from_milliseconds(current_ms)

    def create_point_marker(self):
        """创建时间点标记 - M键快捷键"""
        if not self.slider.marker_display.audio_file_path:
            QMessageBox.warning(self, "错误", "未加载音频文件")
            return

        # 获取当前播放时间
        current_ms = self.player.position()

        # 获取预设列表
        presets = self.DictManage.get_all_marker_presets()

        # 打开编辑对话框创建点标记
        from .marker_edit_dialog import MarkerEditDialog

        # 创建一个点标记数据，预填充当前时间
        marker_data = {
            'type': 0,
            'time': current_ms,
            'label': '',
            'color': '#3498db',
            'preset_id': None
        }

        dialog = MarkerEditDialog(
            marker_data=marker_data,
            presets=presets,
            max_duration_ms=self.player.duration(),
            parent=self
        )

        if dialog.exec_() == MarkerEditDialog.Accepted:
            result = dialog.get_data()

            try:
                # 保存到数据库
                normalized_path = self.slider.marker_display.audio_file_path
                self.DictManage.add_audio_marker(normalized_path, result)

                # 刷新界面
                self.on_marker_changed()

            except Exception as e:
                QMessageBox.critical(self, "错误", f"创建标记失败:\n{str(e)}")

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