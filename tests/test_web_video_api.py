"""Video access, byte ranges and shared subtitle conversion over real HTTP requests."""

from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from flask import Flask

from web_app.blueprint.video import video_api_bp, video_page_bp


class WebVideoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.video = self.folder / '视频 空格.MP4'
        self.video.write_bytes(bytes(range(256)) * 4)
        self.sidecar = self.video.with_suffix('.srt')
        self.srt = '1\n00:00:01,000 --> 00:00:03,000\n<b>中文</b>\nA & B\n'
        self.allowed = {self.video.as_posix()}
        self.api = Mock()
        self.api.query.side_effect = lambda _kind, path, _target: ['tag'] if path in self.allowed else []
        root = Path(__file__).resolve().parents[1]
        self.app = Flask(__name__, template_folder=str(root / 'web_app/frontend/templates'))
        self.app.config.update(TESTING=True, SECRET_KEY='test', VIDEO_GET_USER_SETTING=lambda *_: 'test.db',
                               VIDEO_LOAD_TAGBASE=Mock(), VIDEO_TAGBASE_DATA_DICT={'test.db': self.api})
        self.app.add_url_rule('/login', 'login', lambda: 'login')
        self.app.register_blueprint(video_page_bp, url_prefix='/video')
        self.app.register_blueprint(video_api_bp, url_prefix='/api/video')
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session.update(logged_in=True, user_id=1)

    def get(self, endpoint, **kwargs):
        return self.client.get('/api/video/' + endpoint, query_string={'path': self.video.as_posix()}, **kwargs)

    def upload(self, content=None, name='手动.srt', headers=True):
        return self.client.post('/api/video/subtitles', data={
            'path': self.video.as_posix(), 'file': (BytesIO(content if content is not None else self.srt.encode()), name),
        }, headers={'X-Requested-With': 'XMLHttpRequest'} if headers else {})

    def test_page_and_stream_require_login(self):
        client = self.app.test_client()
        self.assertEqual(client.get('/video/player').status_code, 302)
        for endpoint in ('stream', 'subtitles'):
            response = client.get('/api/video/' + endpoint)
            self.assertEqual(response.status_code, 401)
            self.assertTrue(response.is_json)
        self.assertEqual(client.post('/api/video/subtitles').status_code, 401)
        page = self.client.get('/video/player')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'videoPlayer.js', page.data)
        self.assertIn('no-store', page.headers['Cache-Control'])

    def test_stream_full_range_suffix_head_and_invalid_range(self):
        for headers, expected, status in (({}, self.video.read_bytes(), 200),
                                         ({'Range': 'bytes=100-199'}, self.video.read_bytes()[100:200], 206),
                                         ({'Range': 'bytes=-32'}, self.video.read_bytes()[-32:], 206)):
            with self.get('stream', headers=headers) as response:
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.data, expected)
                self.assertEqual(response.mimetype, 'video/mp4')
                self.assertIn('private', response.headers['Cache-Control'])
                if status == 206:
                    self.assertIn('Content-Range', response.headers)
                    self.assertEqual(response.headers['Accept-Ranges'], 'bytes')
        with self.client.head('/api/video/stream', query_string={'path': self.video.as_posix()}) as response:
            self.assertEqual(response.data, b'')
            self.assertEqual(int(response.headers['Content-Length']), self.video.stat().st_size)
        self.assertEqual(self.get('stream', headers={'Range': 'bytes=2000-3000'}).status_code, 416)

    def test_parent_access_is_required_for_stream_sidecar_and_manual_subtitle(self):
        self.sidecar.write_text(self.srt, encoding='utf-8')
        self.allowed.clear()
        self.assertEqual(self.get('stream').status_code, 403)
        self.assertEqual(self.get('subtitles').status_code, 403)
        self.assertEqual(self.upload().status_code, 403)

    def test_invalid_missing_and_non_mp4_paths(self):
        for path in ('', 'relative.mp4', str(self.sidecar), 'bad\x00.mp4'):
            response = self.client.get('/api/video/stream', query_string={'path': path})
            self.assertEqual(response.status_code, 400)
        self.video.unlink()
        self.assertEqual(self.get('stream').status_code, 404)

    def test_sidecar_encodings_multiline_overlap_and_safe_vtt(self):
        text = self.srt + '\n2\n00:00:02,000 --> 00:00:04,500\n<img src=x> &lt;literal&gt;\n'
        for encoding in ('utf-8-sig', 'utf-16', 'gb18030'):
            self.sidecar.write_bytes(text.encode(encoding))
            response = self.get('subtitles')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json['exists'])
            content = response.json['content']
            self.assertTrue(content.startswith('WEBVTT\n\n'))
            self.assertIn('00:00:01.000 --> 00:00:03.000\n中文\nA &amp; B', content)
            self.assertIn('00:00:02.000 --> 00:00:04.500', content)
            self.assertIn('&lt;img src=x&gt;', content)
            self.assertNotIn('<img', content)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_missing_malformed_and_partial_subtitle(self):
        self.assertEqual(self.get('subtitles').json, {'exists': False})
        self.sidecar.write_text('broken', encoding='utf-8')
        self.assertEqual(self.get('subtitles').status_code, 422)
        self.sidecar.write_text(self.srt + '\nbroken', encoding='utf-8')
        response = self.get('subtitles')
        self.assertEqual(response.json['skipped_blocks'], 1)
        with self.get('stream') as response:
            self.assertEqual(response.status_code, 200)

    def test_manual_subtitle_is_converted_without_writing_files(self):
        response = self.upload(self.srt.encode('gb18030'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['name'], '手动.srt')
        self.assertIn('中文', response.json['content'])
        self.assertEqual(list(self.folder.iterdir()), [self.video])
        self.assertEqual(self.upload(name='bad.txt').status_code, 400)
        self.assertEqual(self.upload(headers=False).status_code, 403)
        self.assertEqual(self.upload(b'garbage').status_code, 422)

    def test_oversized_manual_and_sidecar_subtitles_are_rejected(self):
        with patch('web_app.blueprint.video.MAX_SUBTITLE_BYTES', 64):
            content = b'x' * 65
            self.assertEqual(self.upload(content).status_code, 413)
            self.sidecar.write_bytes(content)
            self.assertEqual(self.get('subtitles').status_code, 413)
            self.assertEqual(self.upload(b'x' * 70000).status_code, 413)


if __name__ == '__main__':
    unittest.main()
