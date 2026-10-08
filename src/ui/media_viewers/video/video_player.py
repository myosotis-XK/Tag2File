"""Desktop MP4 playback using the same Qt multimedia backend as audio."""

import os

from PyQt5.QtCore import Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QKeySequence, QPalette
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QShortcut, QSlider, QSplitter, QVBoxLayout, QWidget,
)

from src.utils.window_position import WindowPositionKeeper


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


class VideoSurface(QVideoWidget):
    doubleClicked = pyqtSignal()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)


class VideoPlayer(QWidget):
    def __init__(self, path, video_files=None):
        super().__init__()
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(self.tr('视频播放器'))
        self.resize(1060, 660)
        self.video_files = mp4_files([*(video_files or []), path])
        self.current_index = -1
        self._failed = False
        self._closing = False
        self._was_maximized = False
        self.position_keeper = WindowPositionKeeper(self, 'video_player')
        self.player = QMediaPlayer(self)
        self._build_ui()
        self.player.setVideoOutput(self.video)
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
        self.setStyleSheet('''
            QWidget#video_player_root { background: #f4f7fb; color: #243447; }
            QPushButton { padding: 7px 12px; border: 1px solid #bfd0e0;
                          border-radius: 6px; background: #ffffff; }
            QPushButton:hover { background: #e4f0fc; }
            QPushButton:disabled { color: #9aa6b2; }
            QListWidget { background: white; border: 1px solid #d6e1ec; border-radius: 6px; }
            QListWidget::item { padding: 9px 6px; }
            QListWidget::item:selected { background: #d8ebff; color: #243447; }
        ''')
        layout = QVBoxLayout(self)
        self.splitter = QSplitter(Qt.Horizontal)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        self.video = VideoSurface()
        palette = self.video.palette()
        palette.setColor(QPalette.Window, Qt.black)
        self.video.setPalette(palette)
        self.video.setAutoFillBackground(True)
        self.video.setMinimumSize(320, 180)
        self.video.setAspectRatioMode(Qt.KeepAspectRatio)
        self.video.doubleClicked.connect(self.toggle_fullscreen)
        content_layout.addWidget(self.video, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        content_layout.addWidget(self.status)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 10000)
        self.slider.setEnabled(False)
        self.slider.sliderMoved.connect(self._preview_seek)
        self.slider.sliderReleased.connect(self._seek)
        content_layout.addWidget(self.slider)
        self.time_label = QLabel('00:00 / 00:00')
        content_layout.addWidget(self.time_label)
        controls = QHBoxLayout()
        self.previous_button = self._button('上一部', self.previous_video, controls)
        self.play_button = self._button('播放', self.toggle_play, controls)
        self.next_button = self._button('下一部', self.next_video, controls)
        controls.addStretch()
        controls.addWidget(QLabel(self.tr('音量')))
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(70)
        self.volume.setMaximumWidth(110)
        self.volume.setAccessibleName(self.tr('音量'))
        self.volume.valueChanged.connect(self.player.setVolume)
        controls.addWidget(self.volume)
        self.fullscreen_button = self._button('全屏', self.toggle_fullscreen, controls)
        content_layout.addLayout(controls)
        self.external_button = QPushButton(self.tr('使用系统播放器打开'))
        self.external_button.clicked.connect(self.open_external)
        content_layout.addWidget(self.external_button)
        self.splitter.addWidget(content)
        self.sidebar = QWidget()
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(8, 0, 0, 0)
        self.playlist_title = QLabel(self.tr('播放列表'))
        sidebar_layout.addWidget(self.playlist_title)
        self.playlist = QListWidget()
        self.playlist.setMinimumWidth(220)
        self.playlist.itemDoubleClicked.connect(
            lambda item: self.play_at(self.playlist.row(item)))
        sidebar_layout.addWidget(self.playlist)
        list_controls = QHBoxLayout()
        self._button('添加视频', self.add_videos, list_controls)
        self.remove_button = self._button('从列表移除', self.remove_selected, list_controls)
        sidebar_layout.addLayout(list_controls)
        hint = QLabel(self.tr('双击列表项播放 · 播完自动下一部\n空格：播放/暂停 · F11：全屏 · Esc：退出全屏'))
        hint.setWordWrap(True)
        sidebar_layout.addWidget(hint)
        self.splitter.addWidget(self.sidebar)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setSizes([750, 290])
        layout.addWidget(self.splitter)

    def _button(self, text, callback, layout):
        button = QPushButton(self.tr(text))
        button.setFocusPolicy(Qt.NoFocus)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def _refresh_playlist(self):
        self.playlist.clear()
        for index, path in enumerate(self.video_files):
            item = QListWidgetItem(('▶ ' if index == self.current_index else '') + os.path.basename(path))
            item.setToolTip(path)
            self.playlist.addItem(item)
        self.playlist.setCurrentRow(self.current_index)
        self.playlist_title.setText(self.tr('播放列表（{count}）').format(count=len(self.video_files)))
        title = self.tr('视频播放器')
        if self.current_index >= 0:
            title += f' - {os.path.basename(self.video_files[self.current_index])} ({self.current_index + 1}/{len(self.video_files)})'
        self.setWindowTitle(title)
        for button in (self.play_button, self.previous_button, self.next_button,
                       self.remove_button, self.external_button):
            button.setEnabled(bool(self.video_files))

    def play_at(self, index):
        if self._closing or not 0 <= index < len(self.video_files):
            return
        self.player.stop()
        self.current_index = index
        self._failed = False
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
        if self.video_files:
            self.play_at((self.current_index - 1) % len(self.video_files))

    def next_video(self):
        if self.video_files:
            self.play_at((self.current_index + 1) % len(self.video_files))

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
        self.play_button.setText(self.tr('暂停') if state == QMediaPlayer.PlayingState else self.tr('播放'))

    def _position_changed(self, position):
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

    def _media_status_changed(self, status):
        if self._closing or self.current_index < 0:
            return
        if status == QMediaPlayer.InvalidMedia:
            self._show_error(self.player.errorString())
        elif status == QMediaPlayer.EndOfMedia and not self._failed:
            if self.current_index + 1 < len(self.video_files):
                self.play_at(self.current_index + 1)
            else:
                self.status.setText(self.tr('播放列表已播完。'))

    def _playback_error(self, error):
        if error != QMediaPlayer.NoError and not self._closing and self.current_index >= 0:
            self._show_error(self.player.errorString())

    def _show_error(self, detail):
        self._failed = True
        self.player.stop()
        self.slider.setEnabled(False)
        self.status.setText(self.tr('无法播放此 MP4，文件可能损坏或当前系统不支持其编码。'
                                    '可使用系统播放器打开，或选择下一部。') + ('\n' + detail if detail else ''))

    def open_external(self):
        if self.current_index >= 0:
            self.player.pause()
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(self.video_files[self.current_index])):
                self.status.setText(self.tr('无法启动系统播放器，请检查默认应用设置。'))

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.exit_fullscreen()
        else:
            self._was_maximized = self.isMaximized()
            self.position_keeper.freeze_normal_position()
            self.sidebar.hide()
            self.external_button.hide()
            self.fullscreen_button.setText(self.tr('退出全屏'))
            self.showFullScreen()

    def exit_fullscreen(self):
        if self.isFullScreen():
            self.showMaximized() if self._was_maximized else self.showNormal()
            self.sidebar.show()
            self.external_button.show()
            self.fullscreen_button.setText(self.tr('全屏'))
            self.position_keeper.unfreeze_normal_position()

    def closeEvent(self, event):
        self._closing = True
        self.position_keeper.save_position()
        self.player.stop()
        self.player.setMedia(QMediaContent())
        super().closeEvent(event)
