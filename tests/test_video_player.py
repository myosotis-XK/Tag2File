"""Queue behavior and player lifecycle, independent of installed video codecs."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import QEvent, QObject, QPoint, Qt, pyqtSignal
from PyQt5.QtMultimedia import QMediaPlayer
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest

from src.ui.media_viewers.video.video_player import VideoPlayer, mp4_files


class FakePlayer(QObject):
    PlayingState = QMediaPlayer.PlayingState
    NoError = QMediaPlayer.NoError
    EndOfMedia = QMediaPlayer.EndOfMedia
    InvalidMedia = QMediaPlayer.InvalidMedia
    stateChanged = pyqtSignal(int)
    positionChanged = pyqtSignal(int)
    durationChanged = pyqtSignal(int)
    seekableChanged = pyqtSignal(bool)
    mediaStatusChanged = pyqtSignal(int)
    error = pyqtSignal(int)

    def __init__(self, parent):
        super().__init__(parent)
        self.current_state = QMediaPlayer.StoppedState
        self.current_position = 0
        self.current_media = None
        self.status = QMediaPlayer.LoadedMedia
        self.loads = 0

    def setVideoOutput(self, output):
        pass

    def setNotifyInterval(self, interval):
        self.notify_interval = interval

    def setVolume(self, volume):
        self.volume = volume

    def setMedia(self, media):
        self.current_media = media
        self.loads += 1
        self.current_position = 0
        self.status = QMediaPlayer.LoadedMedia

    def play(self):
        self.current_state = QMediaPlayer.PlayingState
        self.stateChanged.emit(self.current_state)

    def pause(self):
        self.current_state = QMediaPlayer.PausedState
        self.stateChanged.emit(self.current_state)

    def stop(self):
        self.current_state = QMediaPlayer.StoppedState
        self.stateChanged.emit(self.current_state)

    def state(self):
        return self.current_state

    def position(self):
        return self.current_position

    def setPosition(self, value):
        self.current_position = value
        self.positionChanged.emit(value)

    def duration(self):
        return 120000

    def isSeekable(self):
        return True

    def mediaStatus(self):
        return self.status

    def errorString(self):
        return 'Unsupported codec'

    def finish(self):
        self.status = QMediaPlayer.EndOfMedia
        self.stop()
        self.mediaStatusChanged.emit(self.status)


class VideoPlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.paths = [str(Path(self.temp.name) / name) for name in ('一.mp4', 'two.MP4', 'three.mp4')]
        for path in self.paths:
            Path(path).touch()
        self.patch = patch('src.ui.media_viewers.video.video_player.QMediaPlayer', FakePlayer)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.window = VideoPlayer(self.paths[1], self.paths)
        self.addCleanup(self.close_window)

    def close_window(self):
        self.window.close()
        self.app.processEvents()

    def test_filter_keeps_order_and_rejects_duplicates_directories_and_missing_files(self):
        directory = Path(self.temp.name) / 'folder.mp4'
        directory.mkdir()
        other = Path(self.temp.name) / 'sound.mp3'
        other.touch()
        self.assertEqual(mp4_files([self.paths[2], str(directory), self.paths[0],
                                   self.paths[2], str(other), 'missing.mp4']),
                         [self.paths[2], self.paths[0]])

    def test_selected_video_and_double_click_switch(self):
        self.assertEqual(self.window.current_index, 1)
        self.assertEqual(self.window.player.current_media.canonicalUrl().toLocalFile(), self.paths[1].replace('\\', '/'))
        self.window.playlist.itemDoubleClicked.emit(self.window.playlist.item(0))
        self.assertEqual(self.window.current_index, 0)
        self.assertEqual(self.window.player.state(), QMediaPlayer.PlayingState)

    def test_sequential_end_advances_and_wraps_like_audio(self):
        self.assertEqual(self.window.play_mode, 0)
        self.window.player.finish()
        self.assertEqual(self.window.current_index, 2)
        self.assertEqual(self.window.player.state(), QMediaPlayer.PlayingState)
        self.window.player.finish()
        self.assertEqual(self.window.current_index, 0)
        self.assertEqual(self.window.player.position(), 0)
        self.assertEqual(self.window.player.state(), QMediaPlayer.PlayingState)
        self.assertEqual(self.window.status.text(), '')

    def test_mode_button_cycles_without_changing_current_playback(self):
        self.window.player.setPosition(42000)
        self.window.toggle_play()
        loads = self.window.player.loads
        for mode, label in ((1, '随机播放'), (2, '单个循环'), (0, '顺序播放')):
            self.window.mode_button.click()
            self.assertEqual(self.window.play_mode, mode)
            self.assertIn(label, self.window.mode_button.toolTip())
            self.assertEqual(self.window.mode_button.accessibleName(), self.window.mode_button.toolTip())
            self.assertEqual(self.window.player.loads, loads)
            self.assertEqual(self.window.current_index, 1)
            self.assertEqual(self.window.player.position(), 42000)
            self.assertEqual(self.window.player.state(), QMediaPlayer.PausedState)

    def test_shuffle_end_and_manual_navigation_exclude_current_video(self):
        self.window.toggle_play_mode()
        with patch('src.ui.media_viewers.video.video_player.random.choice',
                   side_effect=lambda choices: choices[-1]) as choose:
            for navigate in (self.window.player.finish, self.window.next_video, self.window.previous_video):
                previous = self.window.current_index
                navigate()
                self.assertEqual(choose.call_args.args[0], [i for i in range(3) if i != previous])
                self.assertNotEqual(self.window.current_index, previous)
                self.assertEqual(self.window.player.state(), QMediaPlayer.PlayingState)
                self.assertEqual(self.window.player.position(), 0)

    def test_repeat_one_restarts_subtitles_and_still_allows_manual_navigation(self):
        self.write_subtitle()
        self.window.play_at(1)
        self.window.toggle_play_mode()
        self.window.toggle_play_mode()
        self.window.player.setPosition(2000)
        self.assertEqual(self.window.video.subtitle_text, '你好\nHello')
        self.window.player.finish()
        self.assertEqual(self.window.current_index, 1)
        self.assertEqual(self.window.player.position(), 0)
        self.assertEqual(self.window.player.state(), QMediaPlayer.PlayingState)
        self.assertEqual(self.window.video.subtitle_text, '')
        self.window.player.setPosition(2000)
        self.assertEqual(self.window.video.subtitle_text, '你好\nHello')
        self.window.next_video()
        self.assertEqual(self.window.current_index, 2)
        self.window.next_video()
        self.assertEqual(self.window.current_index, 0)
        self.window.previous_video()
        self.assertEqual(self.window.current_index, 2)

    def test_all_modes_handle_single_video_and_empty_queue(self):
        while len(self.window.video_files) > 1:
            self.window.playlist.setCurrentRow(0)
            self.window.remove_selected()
        with patch('src.ui.media_viewers.video.video_player.random.choice') as choose:
            for _ in range(3):
                self.window.player.setPosition(10000)
                self.window.player.finish()
                self.assertEqual(self.window.current_index, 0)
                self.assertEqual(self.window.player.position(), 0)
                self.assertEqual(self.window.player.state(), QMediaPlayer.PlayingState)
                self.window.toggle_play_mode()
            self.window.remove_selected()
            loads = self.window.player.loads
            for _ in range(3):
                self.window.player.finish()
                self.window.next_video()
                self.window.previous_video()
                self.assertEqual(self.window.current_index, -1)
                self.assertEqual(self.window.player.loads, loads)
                self.assertEqual(self.window.player.state(), QMediaPlayer.StoppedState)
                self.window.toggle_play_mode()
            choose.assert_not_called()

    def test_failed_media_does_not_loop_or_shuffle_on_end(self):
        for _ in range(3):
            self.window.play_at(1)
            self.window.player.error.emit(QMediaPlayer.FormatError)
            loads = self.window.player.loads
            self.window.player.finish()
            self.assertEqual(self.window.current_index, 1)
            self.assertEqual(self.window.player.loads, loads)
            self.assertEqual(self.window.player.state(), QMediaPlayer.StoppedState)
            self.window.toggle_play_mode()

    def test_manual_navigation_wraps(self):
        self.window.play_at(0)
        self.window.previous_video()
        self.assertEqual(self.window.current_index, 2)
        self.window.next_video()
        self.assertEqual(self.window.current_index, 0)

    def test_remove_before_current_preserves_media_then_remove_current_plays_neighbor(self):
        media = self.window.player.current_media
        self.window.playlist.setCurrentRow(0)
        self.window.remove_selected()
        self.assertEqual(self.window.current_index, 0)
        self.assertIs(self.window.player.current_media, media)
        self.window.remove_selected()
        self.assertEqual(self.window.video_files, [self.paths[2]])
        self.assertEqual(self.window.player.state(), QMediaPlayer.PlayingState)
        self.assertTrue(all(Path(path).exists() for path in self.paths))

    def test_empty_queue_stops_and_can_be_refilled(self):
        for _ in range(3):
            self.window.remove_selected()
        self.assertEqual(self.window.current_index, -1)
        self.assertTrue(self.window.player.current_media.isNull())
        self.assertFalse(self.window.play_button.isEnabled())
        with patch('src.ui.media_viewers.video.video_player.QFileDialog.getOpenFileNames',
                   return_value=([self.paths[2]], '')):
            self.window.add_videos()
        self.assertEqual(self.window.current_index, 0)
        self.assertEqual(self.window.player.state(), QMediaPlayer.PlayingState)

    def test_append_deduplicates_without_restarting_or_shifting_current(self):
        loads = self.window.player.loads
        Path(self.paths[0]).unlink()
        new_path = str(Path(self.temp.name) / 'four.mp4')
        Path(new_path).touch()
        with patch('src.ui.media_viewers.video.video_player.QFileDialog.getOpenFileNames',
                   return_value=([self.paths[1], new_path, new_path], '')):
            self.window.add_videos()
        self.assertEqual(self.window.current_index, 1)
        self.assertEqual(self.window.video_files, self.paths + [new_path])
        self.assertEqual(self.window.player.loads, loads)

    def test_error_stops_without_skipping_and_next_video_recovers(self):
        self.window.player.error.emit(QMediaPlayer.FormatError)
        self.assertEqual(self.window.current_index, 1)
        self.assertTrue(self.window._failed)
        self.assertIn('系统播放器', self.window.status.text())
        self.assertFalse(self.window.slider.isEnabled())
        self.window.next_video()
        self.assertFalse(self.window._failed)
        self.assertEqual(self.window.current_index, 2)

    def test_deleted_file_does_not_keep_playing_previous_video(self):
        Path(self.paths[2]).unlink()
        self.window.next_video()
        self.assertTrue(self.window.player.current_media.isNull())
        self.assertTrue(self.window._failed)
        self.assertIn('不存在', self.window.status.text())

    def test_seek_and_pause(self):
        self.window.toggle_play()
        self.assertEqual(self.window.player.state(), QMediaPlayer.PausedState)
        self.window._duration_changed(120000)
        self.assertTrue(self.window.slider.isEnabled())
        self.window.slider.setValue(5000)
        self.window.slider.sliderReleased.emit()
        self.assertEqual(self.window.player.position(), 60000)
        self.assertEqual(self.window.time_label.text(), '01:00 / 02:00')

    def test_fullscreen_restores_sidebar(self):
        self.window.show()
        self.assertTrue(self.window.sidebar.isHidden())
        self.assertFalse(self.window.playlist_button.isChecked())
        self.window.toggle_playlist()
        self.assertFalse(self.window.sidebar.isHidden())
        self.window.toggle_fullscreen()
        self.assertTrue(self.window.isFullScreen())
        self.assertTrue(self.window.sidebar.isHidden())
        self.window.exit_fullscreen()
        self.assertFalse(self.window.isFullScreen())
        self.assertFalse(self.window.sidebar.isHidden())

    def test_arrow_keys_seek_five_seconds_with_focused_progress_and_keep_pause(self):
        self.window.show()
        self.window.activateWindow()
        self.app.processEvents()
        self.window.toggle_play()
        self.window._duration_changed(120000)
        for target in (self.window.video.viewport(), self.window.slider, self.window.playlist):
            self.window.player.setPosition(12000)
            QTest.keyClick(target, Qt.Key_Left)
            self.assertEqual(self.window.player.position(), 7000)
            QTest.keyClick(target, Qt.Key_Right)
            self.assertEqual(self.window.player.position(), 12000)
        self.window.player.setPosition(2000)
        QTest.keyClick(self.window.slider, Qt.Key_Left)
        self.assertEqual(self.window.player.position(), 0)
        self.window.player.setPosition(118000)
        QTest.keyClick(self.window.slider, Qt.Key_Right)
        self.assertEqual(self.window.player.position(), 120000)
        self.assertEqual(self.window.player.state(), QMediaPlayer.PausedState)
        self.assertEqual(self.window.current_index, 1)
        volume = self.window.volume.value()
        QTest.keyClick(self.window.volume, Qt.Key_Right)
        self.assertGreater(self.window.volume.value(), volume)
        self.assertEqual(self.window.player.position(), 120000)
        QTest.keyClick(self.window, Qt.Key_Right, Qt.ControlModifier)
        self.assertEqual(self.window.current_index, 2)

    def test_step_ignores_unavailable_or_failed_video(self):
        self.window.player.setPosition(12000)
        self.window._failed = True
        self.window._seek_by(5000)
        self.assertEqual(self.window.player.position(), 12000)
        self.window._failed = False
        with patch.object(self.window.player, 'isSeekable', return_value=False):
            self.window._seek_by(-5000)
        with patch.object(self.window.player, 'duration', return_value=0):
            self.window._seek_by(-5000)
        self.assertEqual(self.window.player.position(), 12000)

    def test_playlist_starts_collapsed_and_stays_collapsed_after_fullscreen(self):
        self.window.show()
        self.window.toggle_fullscreen()
        self.window.exit_fullscreen()
        self.assertTrue(self.window.sidebar.isHidden())
        self.assertFalse(self.window.playlist_button.isChecked())
        self.assertFalse(self.window.control_bar.isHidden())

    def test_fullscreen_controls_hide_reveal_and_keep_caption_clear(self):
        self.write_subtitle()
        self.window.play_at(1)
        self.window.show()
        self.window.player.setPosition(2000)
        self.window.toggle_fullscreen()
        self.app.processEvents()
        self.assertTrue(self.window.controls_timer.isActive())
        self.assertGreater(self.window.video.bottom_inset, 0)
        with patch.object(self.window.control_bar, 'underMouse', return_value=False), \
                patch.object(self.window.sidebar, 'underMouse', return_value=False):
            self.window._hide_controls()
        self.assertTrue(self.window.control_bar.isHidden())
        self.assertEqual(self.window.video.bottom_inset, 0)
        self.assertEqual(self.window.video.subtitle_text, '你好\nHello')
        self.window.eventFilter(self.window.video.viewport(), QEvent(QEvent.MouseMove))
        self.assertFalse(self.window.control_bar.isHidden())
        self.assertGreater(self.window.video.bottom_inset, 0)
        self.window.toggle_play()
        self.window._hide_controls()
        self.assertFalse(self.window.control_bar.isHidden())
        self.assertFalse(self.window.controls_timer.isActive())

    def test_timeline_click_seeks_and_mute_restores_previous_volume(self):
        self.window.show()
        self.window._duration_changed(120000)
        self.app.processEvents()
        slider = self.window.slider
        QTest.mouseClick(slider, Qt.LeftButton, pos=QPoint(slider.width() * 3 // 4, slider.height() // 2))
        self.assertAlmostEqual(self.window.player.position(), 90000, delta=2000)
        self.window.volume.setValue(42)
        self.window.toggle_mute()
        self.assertEqual(self.window.player.volume, 0)
        self.window.toggle_mute()
        self.assertEqual(self.window.player.volume, 42)

    def test_subtitle_menu_has_working_load_and_toggle_actions(self):
        path = self.write_subtitle()
        self.window.player.setPosition(2000)
        with patch('src.ui.media_viewers.video.video_player.QFileDialog.getOpenFileName',
                   return_value=(str(path), '')):
            self.window.subtitle_load_action.trigger()
        self.assertEqual(self.window.video.subtitle_text, '你好\nHello')
        self.window.subtitle_enabled.trigger()
        self.assertEqual(self.window.video.subtitle_text, '')
        self.assertIn(self.window.subtitle_enabled, self.window.subtitle_menu.actions())

    def test_close_releases_media_and_ignores_end_event(self):
        # Keep the object alive to inspect its state after closeEvent.
        self.window.setAttribute(Qt.WA_DeleteOnClose, False)
        self.window.close()
        self.assertTrue(self.window.player.current_media.isNull())
        loads = self.window.player.loads
        self.window.player.finish()
        self.assertEqual(self.window.player.loads, loads)

    def test_file_grid_routes_mp4_and_retains_system_open_option(self):
        from src.ui.FileShowArea import FileShowArea

        grid = Mock()
        grid.image_viewers = []
        grid.get_files.return_value = self.paths
        label = Mock(file_path=self.paths[1])
        with patch('src.ui.FileShowArea.VideoPlayer') as create_player, \
                patch('src.ui.FileShowArea.os.startfile') as open_system:
            FileShowArea.openFile(grid, None, label)
            create_player.assert_called_once_with(self.paths[1], self.paths)
            self.assertEqual(grid.image_viewers, [create_player.return_value])
            create_player.return_value.show.assert_called_once()
            open_system.assert_not_called()
            # The destruction callback releases the grid's reference.
            create_player.return_value.destroyed.connect.call_args.args[0]()
            self.assertEqual(grid.image_viewers, [])
            FileShowArea.openFile(grid, None, label, default=True)
            open_system.assert_called_once_with(self.paths[1])

    def write_subtitle(self, index=1, text=None):
        path = Path(self.paths[index]).with_suffix('.srt')
        path.write_text(text or '1\n00:00:01,000 --> 00:00:03,000\n你好\nHello\n', encoding='utf-8')
        return path

    def test_auto_subtitle_load_pause_seek_and_end_boundaries(self):
        self.write_subtitle()
        self.window.play_at(1)
        self.assertIsNotNone(self.window.subtitle_track)
        self.assertEqual(self.window.player.notify_interval, 50)
        self.window.player.setPosition(999)
        self.assertEqual(self.window.video.subtitle_text, '')
        self.window.player.setPosition(1000)
        self.assertEqual(self.window.video.subtitle_text, '你好\nHello')
        self.window.toggle_play()
        self.assertEqual(self.window.video.subtitle_text, '你好\nHello')
        self.window.player.setPosition(3000)
        self.assertEqual(self.window.video.subtitle_text, '')
        self.window.player.setPosition(2000)
        self.assertEqual(self.window.video.subtitle_text, '你好\nHello')
        self.window.player.setPosition(0)
        self.assertEqual(self.window.video.subtitle_text, '')

    def test_subtitle_disabled_across_video_switches_and_reenabled_at_current_position(self):
        self.write_subtitle()
        self.write_subtitle(index=2)
        self.window.play_at(1)
        self.window.player.setPosition(2000)
        self.window.subtitle_enabled.setChecked(False)
        self.assertEqual(self.window.video.subtitle_text, '')
        self.window.next_video()
        self.window.player.setPosition(2000)
        self.assertEqual(self.window.video.subtitle_text, '')
        self.window.subtitle_enabled.setChecked(True)
        self.assertEqual(self.window.video.subtitle_text, '你好\nHello')

    def test_video_without_subtitles_clears_previous_caption(self):
        self.write_subtitle()
        self.window.play_at(1)
        self.window.player.setPosition(2000)
        self.window.next_video()
        self.assertIsNone(self.window.subtitle_track)
        self.assertEqual(self.window.video.subtitle_text, '')
        self.assertFalse(self.window.subtitle_enabled.isEnabled())

    def test_manual_subtitle_selection_is_remembered_for_video_in_this_window(self):
        path = self.write_subtitle(index=0)
        self.window.player.setPosition(2000)
        self.window.subtitle_enabled.setChecked(False)
        with patch('src.ui.media_viewers.video.video_player.QFileDialog.getOpenFileName',
                   return_value=(str(path), '')):
            self.window.choose_subtitle()
        self.assertEqual(self.window.video.subtitle_text, '你好\nHello')
        self.window.next_video()
        self.window.previous_video()
        self.window.player.setPosition(2000)
        self.assertEqual(self.window.video.subtitle_text, '你好\nHello')
        self.assertEqual(self.window.subtitle_status.text(), path.name)

    def test_malformed_sidecar_does_not_block_playback_or_keep_stale_text(self):
        self.write_subtitle()
        self.write_subtitle(index=2, text='not an SRT file')
        self.window.play_at(1)
        self.window.player.setPosition(2000)
        self.window.next_video()
        self.assertEqual(self.window.player.state(), QMediaPlayer.PlayingState)
        self.assertEqual(self.window.video.subtitle_text, '')
        self.assertIsNone(self.window.subtitle_track)
        self.assertIn('失败', self.window.subtitle_status.text())

    def test_failed_manual_load_keeps_existing_subtitle(self):
        self.write_subtitle()
        self.window.play_at(1)
        self.window.player.setPosition(2000)
        self.assertFalse(self.window.load_subtitle(str(Path(self.temp.name) / 'missing.srt')))
        self.assertEqual(self.window.video.subtitle_text, '你好\nHello')
        self.assertIn('保留当前字幕', self.window.subtitle_status.text())

    def test_file_dialog_does_not_attach_old_videos_subtitles_after_auto_advance(self):
        path = self.write_subtitle()
        def advance_in_dialog(*args):
            self.window.next_video()
            return str(path), ''
        with patch('src.ui.media_viewers.video.video_player.QFileDialog.getOpenFileName',
                   side_effect=advance_in_dialog):
            self.window.choose_subtitle()
        self.assertIsNone(self.window.subtitle_track)
        self.assertEqual(self.window._subtitle_overrides, {})

    def test_caption_clears_on_playback_error_end_and_empty_queue(self):
        self.write_subtitle(index=2)
        self.window.play_at(2)
        self.window.player.setPosition(2000)
        self.window.player.error.emit(QMediaPlayer.FormatError)
        self.assertEqual(self.window.video.subtitle_text, '')
        self.window.play_at(2)
        self.window.player.setPosition(2000)
        self.window.player.finish()
        self.assertEqual(self.window.video.subtitle_text, '')
        for _ in range(3):
            self.window.remove_selected()
        self.assertIsNone(self.window.subtitle_track)
        self.assertEqual(self.window.video.subtitle_text, '')

    def test_caption_keeps_text_and_stays_in_video_bounds_through_fullscreen(self):
        self.write_subtitle()
        self.window.play_at(1)
        self.window.show()
        self.window.player.setPosition(2000)
        self.app.processEvents()
        self.window.toggle_fullscreen()
        self.app.processEvents()
        self.assertEqual(self.window.video.subtitle_text, '你好\nHello')
        self.assertTrue(self.window.video.sceneRect().contains(self.window.video.caption_item.sceneBoundingRect()))
        self.window.exit_fullscreen()
        self.app.processEvents()
        self.assertEqual(self.window.video.subtitle_text, '你好\nHello')
        self.assertTrue(self.window.video.sceneRect().contains(self.window.video.caption_item.sceneBoundingRect()))


if __name__ == '__main__':
    unittest.main()
