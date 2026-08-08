import os

from PyQt5.QtCore import QPoint, QSize, Qt, QUrl
from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QShortcut,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.ui.ui_text import AudioPlayerText
from src.utils.path import root

from .audio_utils import format_time, marker_jump_position, normalize_audio_path
from .audio_theme import (
    ICON_BUTTON_STYLE,
    PLAY_BUTTON_STYLE,
    PLAYER_STYLE,
    SLIDER_STYLE,
    TAB_BUTTON_STYLE,
    VOLUME_POPUP_STYLE,
)
from .dual_slider import DualSliderWidget
from .lrc_view import LrcView
from .marker_edit_dialog import MarkerEditDialog
from .marker_list_panel import MarkerListPanel
from .marker_preset_manager import MarkerPresetManager
from .marker_store import MarkerStore
from .playlist_controller import AudioPlaylistController
from .playlist_panel import PlaylistPanel
from .quick_marker_creator import QuickMarkerCreator


AUDIO_ICON_DIR = os.path.join(root, "data", "icon", "audio")


class AudioPlayer(QWidget):
    def __init__(self, path, audio_files=None):
        super().__init__()
        self.window_title_prefix = self.tr(AudioPlayerText.WINDOW_TITLE)
        self.path = path
        self.play_mode = 0
        self.marker_store = MarkerStore()
        self.playlist_controller = AudioPlaylistController(current_file=path)
        self.player = QMediaPlayer()
        self.current_audio_path = None

        self.setObjectName("audio_player_root")
        self.setWindowTitle(self.window_title_prefix)
        self.resize(760, 620)
        self.init_ui()
        self.setup_shortcuts()
        self._connect_signals()

        file_list = audio_files if audio_files else [path]
        self.load_audio_files(file_list, path)
        if self.current_audio_path:
            self.player.play()

    def init_ui(self):
        self.setStyleSheet(PLAYER_STYLE)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(10)

        left_container = QWidget()
        left_container.setObjectName("audio_player_left_card")
        left_container.setMinimumWidth(400)
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(10)

        self.lrc_view = LrcView()
        left_layout.addWidget(self.lrc_view, 1)

        self.slider = DualSliderWidget()
        left_layout.addWidget(self.slider, 0)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setObjectName("audio_time_label")
        self.time_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.time_label, 0)

        left_layout.addLayout(self._build_controls())
        splitter.addWidget(left_container)

        right_panel = QWidget()
        right_panel.setObjectName("audio_player_right_card")
        right_panel.setMinimumWidth(300)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(8)

        switch_widget = QWidget()
        switch_widget.setObjectName("audio_player_tab_bar")
        switch_layout = QHBoxLayout()
        switch_layout.setContentsMargins(3, 3, 3, 3)
        switch_layout.setSpacing(4)
        switch_widget.setLayout(switch_layout)

        self.btn_show_markers = QPushButton(self.tr(AudioPlayerText.SHOW_MARKERS))
        self.btn_show_markers.setCheckable(True)
        self.btn_show_markers.setChecked(True)
        self.btn_show_markers.setFocusPolicy(Qt.NoFocus)
        self.btn_show_markers.setStyleSheet(TAB_BUTTON_STYLE)
        self.btn_show_markers.clicked.connect(lambda: self.switch_right_panel(0))
        switch_layout.addWidget(self.btn_show_markers)

        self.btn_show_playlist = QPushButton(self.tr(AudioPlayerText.SHOW_PLAYLIST))
        self.btn_show_playlist.setCheckable(True)
        self.btn_show_playlist.setFocusPolicy(Qt.NoFocus)
        self.btn_show_playlist.setStyleSheet(TAB_BUTTON_STYLE)
        self.btn_show_playlist.clicked.connect(lambda: self.switch_right_panel(1))
        switch_layout.addWidget(self.btn_show_playlist)
        right_layout.addWidget(switch_widget)

        self.quick_marker_creator = QuickMarkerCreator()
        self.marker_list_panel = MarkerListPanel()
        self.playlist_panel = PlaylistPanel()
        self.playlist_panel.hide()

        right_layout.addWidget(self.quick_marker_creator)
        right_layout.addWidget(self.marker_list_panel)
        right_layout.addWidget(self.playlist_panel)
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)

        self.volume_popup = QWidget(self, Qt.Popup | Qt.FramelessWindowHint)
        self.volume_popup.setStyleSheet(VOLUME_POPUP_STYLE)

        volume_layout = QVBoxLayout(self.volume_popup)
        volume_layout.setContentsMargins(10, 10, 10, 10)
        volume_layout.setSpacing(6)

        self.volume_value_label = QLabel("100")
        self.volume_value_label.setAlignment(Qt.AlignCenter)
        self.volume_value_label.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        volume_layout.addWidget(self.volume_value_label)

        self.volume_slider_vertical = QSlider(Qt.Vertical)
        self.volume_slider_vertical.setRange(0, 100)
        self.volume_slider_vertical.setValue(100)
        self.volume_slider_vertical.setFixedHeight(110)
        self.volume_slider_vertical.setStyleSheet(SLIDER_STYLE)
        volume_layout.addWidget(self.volume_slider_vertical, 0, Qt.AlignCenter)

        self.volume_popup.setFixedSize(72, 170)
        self.volume_popup.hide()
        self.player.setVolume(100)

    def _build_controls(self):
        control_layout = QHBoxLayout()
        control_layout.setSpacing(0)
        control_layout.addStretch()

        center_layout = QHBoxLayout()
        center_layout.setSpacing(8)

        self.btn_mode = self._create_icon_button("repeat", self.tr(AudioPlayerText.SEQUENTIAL_PLAY), self.toggle_play_mode)
        self.btn_previous = self._create_icon_button("previous", self.tr(AudioPlayerText.PREVIOUS_TRACK), self.play_previous)
        self.btn_play = self._create_icon_button("play", self.tr(AudioPlayerText.PLAY), self.toggle_play)
        self.btn_next = self._create_icon_button("next", self.tr(AudioPlayerText.NEXT_TRACK), self.play_next)
        self.btn_volume = self._create_icon_button("volume", self.tr(AudioPlayerText.VOLUME), self.toggle_volume_slider)
        self._set_play_button_style()

        for button in (
            self.btn_mode,
            self.btn_previous,
            self.btn_play,
            self.btn_next,
            self.btn_volume,
        ):
            center_layout.addWidget(button)

        control_layout.addLayout(center_layout)
        control_layout.addStretch()
        return control_layout

    def _create_icon_button(self, icon_name, tooltip, callback):
        button = QPushButton()
        button.setFixedSize(40, 40)
        button.setIconSize(QSize(20, 20))
        button.setToolTip(tooltip)
        button.setFocusPolicy(Qt.NoFocus)
        button.setStyleSheet(ICON_BUTTON_STYLE)
        self._set_button_icon(button, icon_name)
        button.clicked.connect(callback)
        return button

    def _set_play_button_style(self):
        self.btn_play.setFixedSize(46, 46)
        self.btn_play.setIconSize(QSize(22, 22))
        self.btn_play.setStyleSheet(PLAY_BUTTON_STYLE)

    def _set_button_icon(self, button, icon_name):
        icon_path = os.path.join(AUDIO_ICON_DIR, f"{icon_name}.svg")
        button.setIcon(QIcon(icon_path))

    def _connect_signals(self):
        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        self.player.stateChanged.connect(self.on_state_changed)
        self.player.error.connect(self.on_player_error)
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)

        self.slider.sliderMoved.connect(self.set_position)
        self.slider.marker_display.marker_edit_requested.connect(self.edit_marker)
        self.slider.marker_display.marker_delete_requested.connect(self.delete_marker)

        self.marker_list_panel.marker_clicked.connect(self.on_marker_jump)
        self.marker_list_panel.marker_edit_requested.connect(self.edit_marker)
        self.marker_list_panel.marker_delete_requested.connect(self.delete_marker)

        self.quick_marker_creator.marker_create_requested.connect(self.create_marker)
        self.playlist_panel.audio_selected.connect(self.on_playlist_audio_selected)
        self.playlist_panel.audio_remove_requested.connect(self.on_playlist_audio_removed)
        self.volume_slider_vertical.valueChanged.connect(self.on_volume_changed)
        self.lrc_view.seek_requested.connect(self.on_lyric_seek)

    def closeEvent(self, event):
        self.player.pause()
        return super().closeEvent(event)

    def setup_shortcuts(self):
        self.shortcut_prev = QShortcut(QKeySequence(Qt.Key_Left), self)
        self.shortcut_prev.activated.connect(self.seek_backward)

        self.shortcut_next = QShortcut(QKeySequence(Qt.Key_Right), self)
        self.shortcut_next.activated.connect(self.seek_forward)

        self.shortcut_play = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.shortcut_play.activated.connect(self.toggle_play)

        self.shortcut_mark_in = QShortcut(QKeySequence(Qt.Key_I), self)
        self.shortcut_mark_in.activated.connect(self.mark_in_point)

        self.shortcut_mark_out = QShortcut(QKeySequence(Qt.Key_O), self)
        self.shortcut_mark_out.activated.connect(self.mark_out_point)

        self.shortcut_mark_point = QShortcut(QKeySequence(Qt.Key_M), self)
        self.shortcut_mark_point.activated.connect(self.create_point_marker)

    def load_media(self, path=None):
        target_path = path or self.path
        self.path = target_path

        if not os.path.exists(target_path):
            QMessageBox.warning(
                self,
                self.tr(AudioPlayerText.FILE_ERROR),
                self.tr(AudioPlayerText.FILE_DOES_NOT_EXIST).format(path=target_path),
            )
            return False

        try:
            self.player.setMedia(QMediaContent(QUrl.fromLocalFile(os.path.abspath(target_path))))
            self.current_audio_path = normalize_audio_path(target_path)
            self.quick_marker_creator.set_audio_file_path(self.current_audio_path, self.player.duration())
            self.lrc_view.load_lrc(os.path.splitext(target_path)[0] + '.lrc')
            self.refresh_markers()
            self.update_title()
            return True
        except Exception as exc:
            QMessageBox.critical(
                self,
                self.tr(AudioPlayerText.LOAD_ERROR),
                self.tr(AudioPlayerText.UNABLE_TO_LOAD_MEDIA).format(error=exc),
            )
            return False

    def refresh_markers(self):
        markers = self.marker_store.get_markers(self.current_audio_path)
        self.slider.refresh_markers(markers)
        self.marker_list_panel.set_markers(markers)

    def _find_marker_by_id(self, marker_id):
        for marker in self.slider.marker_display.markers:
            if marker.get('id') == marker_id:
                return marker
        return None

    def toggle_play(self):
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def on_state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self._set_button_icon(self.btn_play, "pause")
            self.btn_play.setToolTip(self.tr(AudioPlayerText.PAUSE))
        else:
            self._set_button_icon(self.btn_play, "play")
            self.btn_play.setToolTip(self.tr(AudioPlayerText.PLAY))

    def on_position_changed(self, ms):
        if not self.slider.isSliderDown():
            self.slider.setValue(ms)
        self.lrc_view.update_position(ms)
        self.update_time_label(ms, self.player.duration())

    def on_duration_changed(self, ms):
        self.slider.setRange(0, ms)
        self.quick_marker_creator.set_audio_file_path(self.current_audio_path, ms)
        self.update_time_label(self.player.position(), ms)

    def update_time_label(self, current_ms, total_ms):
        self.time_label.setText(f"{format_time(current_ms)} / {format_time(total_ms)}")

    def set_position(self, ms):
        self.player.setPosition(ms)

    def on_volume_changed(self, value):
        self.player.setVolume(value)
        self.volume_value_label.setText(str(value))
        if value == 0:
            self._set_button_icon(self.btn_volume, "mute")
        elif value < 50:
            self._set_button_icon(self.btn_volume, "volume_low")
        else:
            self._set_button_icon(self.btn_volume, "volume")

    def on_player_error(self, *_args):
        QMessageBox.critical(self, self.tr(AudioPlayerText.PLAYBACK_ERROR), self.player.errorString())

    def on_marker_jump(self, marker_id):
        marker = self._find_marker_by_id(marker_id)
        if marker:
            self.player.setPosition(marker_jump_position(marker))

    def on_lyric_seek(self, timestamp_ms):
        self.player.setPosition(timestamp_ms)

    def create_marker(self, marker_data):
        if not self.current_audio_path:
            QMessageBox.warning(self, self.tr(AudioPlayerText.LOAD_ERROR), self.tr(AudioPlayerText.NO_AUDIO_FILE_LOADED))
            return

        try:
            self.marker_store.add_marker(self.current_audio_path, marker_data)
            self.refresh_markers()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self.tr(AudioPlayerText.LOAD_ERROR),
                self.tr(AudioPlayerText.CREATE_MARKER_FAILED).format(error=exc),
            )

    def edit_marker(self, marker):
        if not self.current_audio_path:
            return False

        dialog = MarkerEditDialog(
            marker_data=marker,
            presets=self.marker_store.get_presets(),
            max_duration_ms=self.player.duration(),
            parent=self,
        )
        if dialog.exec_() != MarkerEditDialog.Accepted:
            return False

        try:
            self.marker_store.update_marker(self.current_audio_path, marker['id'], dialog.get_data())
            self.refresh_markers()
            return True
        except Exception as exc:
            QMessageBox.critical(
                self,
                self.tr(AudioPlayerText.LOAD_ERROR),
                self.tr(AudioPlayerText.UPDATE_MARKER_FAILED).format(error=exc),
            )
            return False

    def delete_marker(self, marker_id):
        if not self.current_audio_path:
            return

        try:
            self.marker_store.delete_marker(self.current_audio_path, marker_id)
            self.refresh_markers()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self.tr(AudioPlayerText.LOAD_ERROR),
                self.tr(AudioPlayerText.DELETE_MARKER_FAILED).format(error=exc),
            )

    def switch_right_panel(self, panel_index):
        show_markers = panel_index == 0
        self.btn_show_markers.setChecked(show_markers)
        self.btn_show_playlist.setChecked(not show_markers)
        self.quick_marker_creator.setVisible(show_markers)
        self.marker_list_panel.setVisible(show_markers)
        self.playlist_panel.setVisible(not show_markers)
        if not show_markers:
            self.playlist_panel.set_playlist(
                self.playlist_controller.audio_files,
                self.playlist_controller.current_index,
            )

    def toggle_volume_slider(self):
        if self.volume_popup.isVisible():
            self.volume_popup.hide()
            return

        button_global_pos = self.btn_volume.mapToGlobal(QPoint(0, 0))
        popup_x = button_global_pos.x() - (self.volume_popup.width() - self.btn_volume.width()) // 2
        popup_y = button_global_pos.y() - self.volume_popup.height() - 10
        self.volume_popup.move(popup_x, popup_y)
        self.volume_popup.show()

    def toggle_play_mode(self):
        self.play_mode = (self.play_mode + 1) % 3
        if self.play_mode == 0:
            self._set_button_icon(self.btn_mode, "repeat")
            self.btn_mode.setToolTip(self.tr(AudioPlayerText.SEQUENTIAL_PLAY))
        elif self.play_mode == 1:
            self._set_button_icon(self.btn_mode, "shuffle")
            self.btn_mode.setToolTip(self.tr(AudioPlayerText.SHUFFLE_PLAY))
        else:
            self._set_button_icon(self.btn_mode, "repeat_one")
            self.btn_mode.setToolTip(self.tr(AudioPlayerText.REPEAT_ONE))

    def on_playlist_audio_selected(self, index):
        if self.play_audio_at_index(index):
            self.player.play()

    def on_playlist_audio_removed(self, index):
        result = self.playlist_controller.remove_at(index)
        self.playlist_panel.set_playlist(
            self.playlist_controller.audio_files,
            self.playlist_controller.current_index,
        )
        self.update_title()

        if result['removed_current']:
            if result['next_index'] >= 0:
                self.play_audio_at_index(result['next_index'])
                self.player.play()
            else:
                self.player.stop()
                self.current_audio_path = None
                self.slider.refresh_markers([])
                self.marker_list_panel.set_markers([])
                self.lrc_view.clear()
                self.update_title()

    def open_preset_manager(self):
        MarkerPresetManager(self).exec_()

    def seek_backward(self):
        self.player.setPosition(max(0, self.player.position() - 5000))

    def seek_forward(self):
        self.player.setPosition(min(self.player.duration(), self.player.position() + 5000))

    def mark_in_point(self):
        self.switch_right_panel(0)
        self.quick_marker_creator.start_time_input.set_from_milliseconds(self.player.position())

    def mark_out_point(self):
        self.switch_right_panel(0)
        self.quick_marker_creator.end_time_input.set_from_milliseconds(self.player.position())

    def create_point_marker(self):
        if not self.current_audio_path:
            QMessageBox.warning(self, self.tr(AudioPlayerText.LOAD_ERROR), self.tr(AudioPlayerText.NO_AUDIO_FILE_LOADED))
            return

        dialog = MarkerEditDialog(
            marker_data={
                'type': 0,
                'time': self.player.position(),
                'label': '',
                'color': '#3498db',
                'preset_id': None,
            },
            presets=self.marker_store.get_presets(),
            max_duration_ms=self.player.duration(),
            parent=self,
        )
        if dialog.exec_() != MarkerEditDialog.Accepted:
            return

        try:
            self.marker_store.add_marker(self.current_audio_path, dialog.get_data())
            self.refresh_markers()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self.tr(AudioPlayerText.LOAD_ERROR),
                self.tr(AudioPlayerText.CREATE_MARKER_FAILED).format(error=exc),
            )

    def play_previous(self):
        previous_index = self.playlist_controller.get_previous_index(self.play_mode)
        if previous_index >= 0 and self.play_audio_at_index(previous_index):
            self.player.play()

    def play_next(self):
        next_index = self.playlist_controller.get_next_index(self.play_mode)
        if next_index >= 0 and self.play_audio_at_index(next_index):
            self.player.play()

    def on_media_status_changed(self, status):
        if status != QMediaPlayer.EndOfMedia:
            return

        if self.play_mode == 2:
            self.player.setPosition(0)
            self.player.play()
        else:
            self.play_next()

    def load_audio_files(self, file_paths, show_file_path=None):
        selected_index = self.playlist_controller.set_playlist(file_paths, show_file_path or self.path)
        self.playlist_panel.set_playlist(
            self.playlist_controller.audio_files,
            self.playlist_controller.current_index,
        )

        if selected_index >= 0:
            self.play_audio_at_index(selected_index)
        else:
            self.current_audio_path = None
            self.slider.refresh_markers([])
            self.marker_list_panel.set_markers([])
            self.update_title()

    def play_audio_at_index(self, index):
        if not self.playlist_controller.set_current_index(index):
            return False

        file_path = self.playlist_controller.get_current_file()
        if not self.load_media(file_path):
            return False

        self.playlist_panel.update_current_index(index)
        return True

    def update_title(self):
        self.setWindowTitle(self.playlist_controller.build_title(self.window_title_prefix))
