"""Desktop MP4 playback using the same Qt multimedia backend as audio."""

import os
import random

# Qt caches plugin priority on first use. WMF avoids third-party DirectShow
# filters that burn same-name sidecars into frames before our subtitle switch.
if os.name == 'nt':
    os.environ.setdefault('QT_MULTIMEDIA_PREFERRED_PLUGINS', 'windowsmediafoundation')

from PyQt5.QtCore import QEvent, QSize, Qt, QTimer, QUrl
from PyQt5.QtGui import QColor, QDesktopServices, QIcon, QKeySequence
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMenu, QShortcut, QSplitter, QToolButton, QVBoxLayout, QWidget,
)

from src.utils.window_position import WindowPositionKeeper
from src.utils.path import root
from .player_controls import PLAYER_STYLE, SeekSlider, StatusLabel, player_icon
from .subtitles import load_srt
from .video_surface import VideoSurface


def mp4_files(paths):
    """Keep existing MP4 files in display order, without duplicate paths."""
    result, seen = [], set()
    for path in paths:
        path = os.path.abspath(os.path.normpath(path))
        key = os.path.normcase(path)
        if key not in seen and os.path.isfile(path) and os.path.splitext(path)[1].lower() == '.mp4':
            seen.add(key)
            result.append(path)
    return result


def format_time(milliseconds):
    seconds = max(0, milliseconds) // 1000
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f'{hours}:{minutes:02}:{seconds:02}' if hours else f'{minutes:02}:{seconds:02}'


class VideoPlayer(QWidget):
    def __init__(self, path, video_files=None):
        super().__init__()
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(self.tr('视频播放器'))
        self.resize(1060, 660)
        self.video_files = mp4_files([*(video_files or []), path])
        self.current_index = -1
        self.play_mode = 0
        self._failed = False
        self._closing = False
        self._was_maximized = False
        self._window_playlist_visible = False
        self._playlist_width = 280
        self._last_volume = 70
        self.controls_timer = QTimer(self)
        self.controls_timer.setSingleShot(True)
        self.controls_timer.setInterval(2500)
        self.controls_timer.timeout.connect(self._hide_controls)
        self.subtitle_track = None
        self._subtitle_overrides = {}
        self.position_keeper = WindowPositionKeeper(self, 'video_player')
        self.player = QMediaPlayer(self)
        self.player.setNotifyInterval(50)
        self._build_ui()
        self.player.setVideoOutput(self.video.video_item)
        self.player.setVolume(self.volume.value())
        self.player.stateChanged.connect(self._state_changed)
        self.player.positionChanged.connect(self._position_changed)
        self.player.durationChanged.connect(self._duration_changed)
        self.player.seekableChanged.connect(self._seekable_changed)
        self.player.mediaStatusChanged.connect(self._media_status_changed)
        self.player.error.connect(self._playback_error)
        self._shortcuts = []
        for key, callback in (
            ('Space', self.toggle_play), ('F11', self.toggle_fullscreen),
            ('Escape', self.exit_fullscreen),
            ('Ctrl+Left', self.previous_video), ('Ctrl+Right', self.next_video),
            ('Ctrl+L', self.toggle_playlist), ('Ctrl+O', self.add_videos),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)
        self._refresh_playlist()
        target = os.path.normcase(os.path.abspath(path))
        index = next((i for i, item in enumerate(self.video_files)
                      if os.path.normcase(item) == target), 0)
        if self.video_files:
            self.play_at(index)
        else:
            self.status.setText(self.tr('没有可播放的 MP4 文件，请添加视频。'))

    def _build_ui(self):
        self.setObjectName('video_player_root')
        self.setStyleSheet(PLAYER_STYLE)
        self.setWindowIcon(QIcon(os.path.join(root, 'data', 'icon', 'app', 'favicon.ico')))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.setChildrenCollapsible(False)
        self.content = QWidget()
        self.content.setObjectName('video_content')
        self.content.setMinimumWidth(600)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.video = VideoSurface()
        self.video.setMinimumSize(320, 180)
        self.video.doubleClicked.connect(self.toggle_fullscreen)
        self.content_layout.addWidget(self.video, 1)
        self.status = StatusLabel()
        self.status.setObjectName('playback_status')
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        self.status.hide()
        self.content_layout.addWidget(self.status)

        self.control_bar = QWidget(self.content)
        self.control_bar.setObjectName('transport')
        transport = QVBoxLayout(self.control_bar)
        transport.setContentsMargins(16, 4, 16, 12)
        transport.setSpacing(6)
        self.slider = SeekSlider(Qt.Horizontal)
        self.slider.setRange(0, 10000)
        self.slider.setFixedHeight(18)
        self.slider.setAccessibleName(self.tr('播放进度'))
        self.slider.setToolTip(self.tr('播放进度（← 后退 5 秒 / → 前进 5 秒）'))
        self.slider.setEnabled(False)
        self.slider.sliderMoved.connect(self._preview_seek)
        self.slider.sliderReleased.connect(self._seek)
        self.slider.actionTriggered.connect(lambda: QTimer.singleShot(0, self._seek))
        transport.addWidget(self.slider)
        controls = QHBoxLayout()
        controls.setSpacing(6)
        self.mode_button = self._button('repeat', '顺序播放（点击切换）', self.toggle_play_mode, controls)
        self.previous_button = self._button('previous', '上一部 (Ctrl+←)', self.previous_video, controls)
        self.play_button = self._button('play', '播放 (空格)', self.toggle_play, controls)
        self.play_button.setObjectName('play_button')
        self.play_button.setFixedSize(48, 48)
        self.play_button.setIconSize(QSize(26, 26))
        self.next_button = self._button('next', '下一部 (Ctrl+→)', self.next_video, controls)
        self.time_label = QLabel('00:00 / 00:00')
        self.time_label.setObjectName('time_label')
        self.time_label.setMinimumWidth(104)
        controls.addSpacing(6)
        controls.addWidget(self.time_label)
        controls.addStretch()
        self.mute_button = self._button('volume', '静音', self.toggle_mute, controls)
        self.volume = SeekSlider(Qt.Horizontal)
        self.volume.setObjectName('volume_slider')
        self.volume.setRange(0, 100)
        self.volume.setValue(70)
        self.volume.setFixedSize(80, 18)
        self.volume.setAccessibleName(self.tr('音量'))
        self.volume.setToolTip(self.tr('音量'))
        self.volume.valueChanged.connect(self._volume_changed)
        controls.addWidget(self.volume)
        controls.addSpacing(6)

        self.subtitle_menu = self._menu()
        self.subtitle_status = self.subtitle_menu.addAction(self.tr('未加载字幕'))
        self.subtitle_status.setEnabled(False)
        self.subtitle_menu.addSeparator()
        self.subtitle_load_action = self.subtitle_menu.addAction(self.tr('加载 SRT 字幕…'), self.choose_subtitle)
        self.subtitle_enabled = self.subtitle_menu.addAction(self.tr('显示字幕'))
        self.subtitle_enabled.setCheckable(True)
        self.subtitle_enabled.setChecked(True)
        self.subtitle_enabled.setEnabled(False)
        self.subtitle_enabled.toggled.connect(lambda: self._update_subtitle(self.player.position()))
        self.subtitle_button = self._button('subtitles', '字幕', None, controls)
        self.subtitle_button.setMenu(self.subtitle_menu)
        self.subtitle_button.setPopupMode(QToolButton.InstantPopup)
        self.playlist_button = self._button('playlist', '播放列表 (Ctrl+L)', None, controls)
        self.playlist_button.setCheckable(True)
        self.playlist_button.toggled.connect(self.set_playlist_visible)
        self.more_menu = self._menu()
        self.more_menu.addAction(self.tr('添加视频…'), self.add_videos)
        self.external_action = self.more_menu.addAction(self.tr('使用系统播放器打开'), self.open_external)
        self.more_button = self._button('more', '更多', None, controls)
        self.more_button.setMenu(self.more_menu)
        self.more_button.setPopupMode(QToolButton.InstantPopup)
        self.fullscreen_button = self._button('fullscreen', '全屏 (F11)', self.toggle_fullscreen, controls)
        transport.addLayout(controls)
        self.content_layout.addWidget(self.control_bar)
        self.splitter.addWidget(self.content)

        self.sidebar = QWidget()
        self.sidebar.setObjectName('playlist_sidebar')
        self.sidebar.setMinimumWidth(250)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(12, 10, 8, 12)
        sidebar_layout.setSpacing(8)
        header = QHBoxLayout()
        self.playlist_title = QLabel(self.tr('播放列表'))
        self.playlist_title.setObjectName('playlist_title')
        header.addWidget(self.playlist_title)
        header.addStretch()
        self._button('add', '添加视频', self.add_videos, header)
        self._button('close', '收起播放列表', lambda: self.set_playlist_visible(False), header)
        sidebar_layout.addLayout(header)
        self.playlist_meta = QLabel()
        self.playlist_meta.setObjectName('playlist_meta')
        sidebar_layout.addWidget(self.playlist_meta)
        self.playlist = QListWidget()
        self.playlist.setTextElideMode(Qt.ElideRight)
        self.playlist.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.playlist.setUniformItemSizes(True)
        self.playlist.setContextMenuPolicy(Qt.CustomContextMenu)
        self.playlist.customContextMenuRequested.connect(self._playlist_context_menu)
        self.playlist.itemDoubleClicked.connect(lambda item: self.play_at(self.playlist.row(item)))
        sidebar_layout.addWidget(self.playlist)
        self.splitter.addWidget(self.sidebar)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setSizes([780, 280])
        self.sidebar.hide()
        layout.addWidget(self.splitter)
        for widget in [self, *self.findChildren(QWidget)]:
            widget.setMouseTracking(True)
            widget.installEventFilter(self)

    def _button(self, icon, tooltip, callback, layout):
        button = QToolButton()
        button.setIcon(player_icon(icon))
        button.setIconSize(QSize(22, 22))
        button.setFixedSize(36, 36)
        button.setToolTip(self.tr(tooltip))
        button.setAccessibleName(self.tr(tooltip))
        button.setFocusPolicy(Qt.NoFocus)
        if callback:
            button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def _menu(self):
        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        menu.aboutToShow.connect(self._show_controls)
        menu.aboutToHide.connect(lambda: QTimer.singleShot(0, self._show_controls))
        return menu

    def _playlist_context_menu(self, point):
        item = self.playlist.itemAt(point)
        if not item:
            return
        self.playlist.setCurrentItem(item)
        path = self.video_files[self.playlist.row(item)]
        menu = self._menu()
        play_action = menu.addAction(self.tr('播放'))
        remove_action = menu.addAction(self.tr('从列表移除'))
        action = menu.exec_(self.playlist.viewport().mapToGlobal(point))
        if path in self.video_files:
            index = self.video_files.index(path)
            if action == play_action:
                self.play_at(index)
            elif action == remove_action:
                self.playlist.setCurrentRow(index)
                self.remove_selected()
        menu.deleteLater()

    def _refresh_playlist(self):
        self.playlist.clear()
        for index, path in enumerate(self.video_files):
            item = QListWidgetItem(f'{index + 1:02d}   {os.path.basename(path)}')
            item.setToolTip(path)
            item.setSizeHint(QSize(0, 44))
            if index == self.current_index:
                item.setIcon(player_icon('playing', '#48a6ff'))
                item.setForeground(QColor('#60b3ff'))
            self.playlist.addItem(item)
        self.playlist.setCurrentRow(self.current_index)
        self.playlist_title.setText(self.tr('播放列表（{count}）').format(count=len(self.video_files)))
        self.playlist_meta.setText(self.tr('正在播放 · {index} / {count}').format(
            index=self.current_index + 1, count=len(self.video_files)))
        title = self.tr('视频播放器')
        if self.current_index >= 0:
            title += f' - {os.path.basename(self.video_files[self.current_index])} ({self.current_index + 1}/{len(self.video_files)})'
        self.setWindowTitle(title)
        for button in (self.play_button, self.previous_button, self.next_button,
                       self.external_action, self.subtitle_load_action):
            button.setEnabled(bool(self.video_files))

    def play_at(self, index):
        if self._closing or not 0 <= index < len(self.video_files):
            return
        self.player.stop()
        self.current_index = index
        self._failed = False
        self._clear_subtitles()
        self.status.clear()
        self.slider.setValue(0)
        self.slider.setEnabled(False)
        self.time_label.setText('00:00 / 00:00')
        self._refresh_playlist()
        path = self.video_files[index]
        if not os.path.isfile(path):
            self.player.setMedia(QMediaContent())
            self._show_error(self.tr('文件不存在或已移动。'))
            return
        self.player.setMedia(QMediaContent(QUrl.fromLocalFile(path)))
        self._load_video_subtitles(path)
        if not self._failed:
            self.player.play()

    def toggle_play(self):
        if self.current_index < 0:
            return
        if self._failed:
            self.play_at(self.current_index)
        elif self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            if self.player.mediaStatus() == QMediaPlayer.EndOfMedia:
                self.status.clear()
                self.player.setPosition(0)
            self.player.play()

    def previous_video(self):
        self._play_adjacent(-1)

    def next_video(self):
        self._play_adjacent(1)

    def _play_adjacent(self, direction):
        if self.video_files:
            if self.play_mode == 1 and len(self.video_files) > 1:
                index = random.choice([i for i in range(len(self.video_files)) if i != self.current_index])
            else:
                index = (self.current_index + direction) % len(self.video_files)
            self.play_at(index)

    def toggle_play_mode(self):
        self.play_mode = (self.play_mode + 1) % 3
        modes = (
            ('repeat', self.tr('顺序播放（点击切换）')),
            ('shuffle', self.tr('随机播放（点击切换）')),
            ('repeat_one', self.tr('单个循环（点击切换）')),
        )
        icon, tooltip = modes[self.play_mode]
        self.mode_button.setIcon(player_icon(icon))
        self.mode_button.setToolTip(tooltip)
        self.mode_button.setAccessibleName(tooltip)

    def add_videos(self):
        paths, _ = QFileDialog.getOpenFileNames(self, self.tr('添加视频'), '', 'MP4 (*.mp4 *.MP4)')
        self.video_files = self._append_files(paths)
        self._refresh_playlist()
        if self.current_index < 0 and self.video_files:
            self.play_at(0)

    def _append_files(self, paths):
        # Retain vanished queue entries so the current index cannot shift during playback.
        seen = {os.path.normcase(path) for path in self.video_files}
        return self.video_files + [path for path in mp4_files(paths) if os.path.normcase(path) not in seen]

    def remove_selected(self):
        index = self.playlist.currentRow()
        if index < 0:
            return
        removing_current = index == self.current_index
        self.video_files.pop(index)
        if not self.video_files:
            self.current_index = -1
            self._clear_subtitles()
            self.player.stop()
            self.player.setMedia(QMediaContent())
            self.slider.setValue(0)
            self.slider.setEnabled(False)
            self.time_label.setText('00:00 / 00:00')
            self.status.setText(self.tr('播放列表为空，请添加视频。'))
        elif removing_current:
            self.play_at(min(index, len(self.video_files) - 1))
        elif index < self.current_index:
            self.current_index -= 1
        self._refresh_playlist()

    def _state_changed(self, state):
        playing = state == QMediaPlayer.PlayingState
        self.play_button.setIcon(player_icon('pause' if playing else 'play'))
        self.play_button.setToolTip(self.tr('暂停 (空格)') if playing else self.tr('播放 (空格)'))
        self.play_button.setAccessibleName(self.play_button.toolTip())
        self._show_controls()

    def _volume_changed(self, value):
        self.player.setVolume(value)
        if value:
            self._last_volume = value
        self.mute_button.setIcon(player_icon('volume' if value else 'mute'))
        self.mute_button.setToolTip(self.tr('静音') if value else self.tr('恢复音量'))
        self.mute_button.setAccessibleName(self.mute_button.toolTip())

    def toggle_mute(self):
        self.volume.setValue(0 if self.volume.value() else self._last_volume)

    def _position_changed(self, position):
        self._update_subtitle(position)
        if not self.slider.isSliderDown():
            duration = self.player.duration()
            self.slider.setValue(round(position * 10000 / duration) if duration else 0)
            self.time_label.setText(f'{format_time(position)} / {format_time(duration)}')

    def _duration_changed(self, duration):
        self._seekable_changed(self.player.isSeekable())
        self._position_changed(self.player.position())

    def _seekable_changed(self, seekable):
        self.slider.setEnabled(seekable and self.player.duration() > 0 and not self._failed)

    def _preview_seek(self, value):
        duration = self.player.duration()
        self.time_label.setText(f'{format_time(round(value * duration / 10000))} / {format_time(duration)}')

    def _seek(self):
        if self.player.isSeekable() and not self._failed:
            self.player.setPosition(round(self.slider.value() * self.player.duration() / 10000))

    def _seek_by(self, milliseconds):
        duration = self.player.duration()
        if self.current_index < 0 or self._failed or not self.player.isSeekable() or duration <= 0:
            return
        self.player.setPosition(min(duration, max(0, self.player.position() + milliseconds)))
        self._show_controls()

    def _media_status_changed(self, status):
        if self._closing or self.current_index < 0:
            return
        if status == QMediaPlayer.InvalidMedia:
            self._show_error(self.player.errorString())
        elif status == QMediaPlayer.EndOfMedia and not self._failed:
            if self.play_mode == 2:
                self.play_at(self.current_index)
            else:
                self.next_video()

    def _playback_error(self, error):
        if error != QMediaPlayer.NoError and not self._closing and self.current_index >= 0:
            self._show_error(self.player.errorString())

    def _show_error(self, detail):
        self._failed = True
        self.video.set_subtitle('')
        self.player.stop()
        self.slider.setEnabled(False)
        self.status.setText(self.tr('无法播放此 MP4，文件可能损坏或当前系统不支持其编码。'
                                    '可在“更多”菜单中使用系统播放器打开，或选择下一部。') + ('\n' + detail if detail else ''))

    def open_external(self):
        if self.current_index >= 0:
            self.player.pause()
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(self.video_files[self.current_index])):
                self.status.setText(self.tr('无法启动系统播放器，请检查默认应用设置。'))

    def _clear_subtitles(self):
        self.subtitle_track = None
        self.video.set_subtitle('')
        self.subtitle_enabled.setEnabled(False)
        self.subtitle_status.setText(self.tr('未加载字幕'))
        self.subtitle_status.setToolTip('')
        self._update_subtitle_icon()

    def _load_video_subtitles(self, video_path):
        path = self._subtitle_overrides.get(video_path, os.path.splitext(video_path)[0] + '.srt')
        if os.path.isfile(path) or video_path in self._subtitle_overrides:
            self.load_subtitle(path)
        else:
            self.subtitle_status.setText(self.tr('未找到同名 SRT'))

    def load_subtitle(self, path):
        try:
            track = load_srt(path)
        except (OSError, UnicodeError, ValueError) as exc:
            # A malformed sidecar must never prevent the video itself from playing.
            message = self.tr('字幕加载失败，保留当前字幕') if self.subtitle_track else self.tr('字幕加载失败')
            self.subtitle_status.setText(message)
            self.subtitle_status.setToolTip(str(exc))
            return False
        self.subtitle_track = track
        self.subtitle_enabled.setEnabled(True)
        text = os.path.basename(path)
        if track.skipped_blocks:
            text += self.tr('（已跳过 {count} 个无效段落）').format(count=track.skipped_blocks)
        self.subtitle_status.setText(text)
        self.subtitle_status.setToolTip(os.path.abspath(path))
        self._update_subtitle(self.player.position())
        return True

    def choose_subtitle(self):
        if self.current_index < 0:
            return
        video_path = self.video_files[self.current_index]
        path, _ = QFileDialog.getOpenFileName(self, self.tr('加载 SRT 字幕'),
                                            os.path.dirname(video_path), 'SRT (*.srt *.SRT)')
        # The playlist can advance while the native file dialog runs its event loop.
        if self.current_index < 0 or self.video_files[self.current_index] != video_path:
            return
        if path and self.load_subtitle(path):
            self._subtitle_overrides[video_path] = path
            self.subtitle_enabled.setChecked(True)

    def _update_subtitle(self, position):
        text = ''
        if (self.subtitle_track and self.subtitle_enabled.isChecked() and not self._failed
                and not self._closing and self.current_index >= 0
                and self.player.mediaStatus() != QMediaPlayer.EndOfMedia):
            text = self.subtitle_track.text_at(position)
        self.video.set_subtitle(text)
        self._update_subtitle_icon()

    def _update_subtitle_icon(self):
        enabled = bool(self.subtitle_track and self.subtitle_enabled.isChecked())
        if getattr(self, '_subtitle_icon_enabled', None) != enabled:
            self._subtitle_icon_enabled = enabled
            self.subtitle_button.setIcon(player_icon('subtitles', '#48a6ff' if enabled else '#e8ebf1'))

    def toggle_playlist(self):
        self.set_playlist_visible(not self.playlist_button.isChecked())

    def set_playlist_visible(self, visible):
        if not visible and not self.sidebar.isHidden():
            self._playlist_width = max(250, self.splitter.sizes()[1])
        self.sidebar.setVisible(visible)
        self.playlist_button.blockSignals(True)
        self.playlist_button.setChecked(visible)
        self.playlist_button.blockSignals(False)
        if visible:
            self.splitter.setSizes([max(600, self.width() - self._playlist_width), self._playlist_width])
        self._show_controls()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.exit_fullscreen()
        else:
            self._was_maximized = self.isMaximized()
            self._window_playlist_visible = self.playlist_button.isChecked()
            self.position_keeper.freeze_normal_position()
            self.set_playlist_visible(False)
            self.content_layout.removeWidget(self.control_bar)
            self.fullscreen_button.setIcon(player_icon('restore'))
            self.fullscreen_button.setToolTip(self.tr('退出全屏 (Esc)'))
            self.showFullScreen()
            self._show_controls()

    def exit_fullscreen(self):
        if self.isFullScreen():
            self.controls_timer.stop()
            self.showMaximized() if self._was_maximized else self.showNormal()
            self.content_layout.addWidget(self.control_bar)
            self.control_bar.show()
            self.video.viewport().unsetCursor()
            self.video.set_bottom_inset(0)
            self.set_playlist_visible(self._window_playlist_visible)
            self.fullscreen_button.setIcon(player_icon('fullscreen'))
            self.fullscreen_button.setToolTip(self.tr('全屏 (F11)'))
            self.position_keeper.unfreeze_normal_position()

    def _layout_fullscreen_controls(self):
        if self.isFullScreen():
            rect = self.video.geometry()
            height = self.control_bar.sizeHint().height()
            self.control_bar.setGeometry(rect.x(), rect.bottom() + 1 - height, rect.width(), height)
            self.control_bar.raise_()
            self.video.set_bottom_inset(height + 12 if not self.control_bar.isHidden() else 0)

    def _show_controls(self):
        if self._closing or not hasattr(self, 'control_bar'):
            return
        self.control_bar.show()
        self.video.viewport().unsetCursor()
        self._layout_fullscreen_controls()
        if self.isFullScreen() and self.player.state() == QMediaPlayer.PlayingState:
            self.controls_timer.start()
        else:
            self.controls_timer.stop()

    def _hide_controls(self):
        if not self.isFullScreen() or self.player.state() != QMediaPlayer.PlayingState:
            return
        if (self.control_bar.underMouse() or (not self.sidebar.isHidden() and self.sidebar.underMouse())
                or self.slider.isSliderDown() or self.volume.isSliderDown()
                or QApplication.activePopupWidget() or QApplication.activeModalWidget()):
            self.controls_timer.start()
            return
        self.control_bar.hide()
        self.video.viewport().setCursor(Qt.BlankCursor)
        self.video.set_bottom_inset(0)

    def eventFilter(self, watched, event):
        # Handle the focused progress slider as well as the video and playlist.
        # The volume slider and open menus/dialogs keep their own arrow controls.
        if (event.type() == QEvent.KeyPress and event.modifiers() == Qt.NoModifier
                and event.key() in (Qt.Key_Left, Qt.Key_Right)
                and watched is not self.volume and not isinstance(watched, QMenu)
                and not QApplication.activePopupWidget() and not QApplication.activeModalWidget()):
            self._seek_by(-5000 if event.key() == Qt.Key_Left else 5000)
            event.accept()
            return True
        if event.type() in (QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.KeyPress):
            self._show_controls()
        elif event.type() == QEvent.Resize and watched is getattr(self, 'video', None):
            self._layout_fullscreen_controls()
        elif event.type() == QEvent.WindowDeactivate:
            self._show_controls()
        return super().eventFilter(watched, event)

    def showEvent(self, event):
        super().showEvent(event)
        if os.name == 'nt' and QApplication.platformName() == 'windows':
            # Style this window's native title bar without replacing its system controls.
            import ctypes
            try:
                enabled = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    ctypes.c_void_p(int(self.winId())), 20, ctypes.byref(enabled), ctypes.sizeof(enabled))
            except (OSError, AttributeError):
                pass

    def closeEvent(self, event):
        self._closing = True
        self.controls_timer.stop()
        self.video.set_subtitle('')
        self.position_keeper.save_position()
        self.player.stop()
        self.player.setMedia(QMediaContent())
        super().closeEvent(event)
