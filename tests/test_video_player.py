"""Queue behavior and player lifecycle, independent of installed video codecs."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtMultimedia import QMediaPlayer
from PyQt5.QtWidgets import QApplication

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

    def test_end_advances_but_stops_at_last_video(self):
        self.window.player.finish()
        self.assertEqual(self.window.current_index, 2)
        self.assertEqual(self.window.player.state(), QMediaPlayer.PlayingState)
        self.window.player.finish()
        self.assertEqual(self.window.current_index, 2)
        self.assertEqual(self.window.player.state(), QMediaPlayer.StoppedState)
        self.assertIn('已播完', self.window.status.text())
        self.window.toggle_play()
        self.assertEqual(self.window.player.position(), 0)
        self.assertEqual(self.window.player.state(), QMediaPlayer.PlayingState)
        self.assertEqual(self.window.status.text(), '')

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
        self.window.toggle_fullscreen()
        self.assertTrue(self.window.isFullScreen())
        self.assertTrue(self.window.sidebar.isHidden())
        self.window.exit_fullscreen()
        self.assertFalse(self.window.isFullScreen())
        self.assertFalse(self.window.sidebar.isHidden())

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


if __name__ == '__main__':
    unittest.main()
