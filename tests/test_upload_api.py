"""Exercise uploads against a real temporary filesystem and Flask multipart requests."""

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask
from werkzeug.datastructures import FileStorage

from web_app.blueprint.upload import upload_api_bp


class UploadAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SECRET_KEY='test')
        self.app.register_blueprint(upload_api_bp)

    def client(self, logged_in=True):
        client = self.app.test_client()
        if logged_in:
            with client.session_transaction() as session:
                session['logged_in'] = True
        return client

    def upload(self, filename='文件.txt', content=b'hello', folder=None, logged_in=True, headers=True):
        return self.client(logged_in).post('/upload_file', data={
            'folder_path': str(self.folder) if folder is None else folder,
            'file': (BytesIO(content), filename),
        }, headers={'X-Requested-With': 'XMLHttpRequest'} if headers else {})

    def test_upload_preserves_unicode_filename_and_binary_content(self):
        content = bytes(range(256)) * 1024
        response = self.upload('中文 文件.bin', content)
        self.assertEqual(response.status_code, 201)
        self.assertEqual((self.folder / '中文 文件.bin').read_bytes(), content)
        self.assertEqual(response.json['file_path'], (self.folder / '中文 文件.bin').as_posix())

    def test_empty_file_is_supported(self):
        self.assertEqual(self.upload(content=b'').status_code, 201)
        self.assertEqual((self.folder / '文件.txt').stat().st_size, 0)

    def test_existing_file_and_directory_are_never_overwritten(self):
        (self.folder / 'existing.txt').write_bytes(b'original')
        (self.folder / 'subfolder').mkdir()
        for name in ('existing.txt', 'subfolder'):
            self.assertEqual(self.upload(name).status_code, 409)
        self.assertEqual((self.folder / 'existing.txt').read_bytes(), b'original')
        self.assertTrue((self.folder / 'subfolder').is_dir())

    def test_parallel_uploads_cannot_overwrite_each_other(self):
        payloads = [b'A' * 10000, b'B' * 10000]
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(lambda content: self.upload(content=content), payloads))
        self.assertEqual(sorted(r.status_code for r in responses), [201, 409])
        winner = next(i for i, response in enumerate(responses) if response.status_code == 201)
        self.assertEqual((self.folder / '文件.txt').read_bytes(), payloads[winner])

    def test_paths_and_windows_special_names_are_rejected(self):
        for name in ('', '.', '..', '../escape.txt', '..\\escape.txt', '/absolute.txt',
                     'C:\\absolute.txt', 'file:stream', 'CON.txt', 'LPT1', 'COM¹.txt',
                     'bad?', 'bad*', 'trailing.', 'trailing ', 'bad\x01.txt'):
            with self.subTest(name=name):
                self.assertEqual(self.upload(name).status_code, 400)
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_invalid_destinations_and_missing_file(self):
        self.assertEqual(self.upload(folder='').status_code, 400)
        self.assertEqual(self.upload(folder='relative').status_code, 400)
        self.assertEqual(self.upload(folder=str(self.folder / 'missing')).status_code, 404)
        (self.folder / 'file').touch()
        self.assertEqual(self.upload(folder=str(self.folder / 'file')).status_code, 404)
        response = self.client().post('/upload_file', data={'folder_path': str(self.folder)},
                                      headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(response.status_code, 400)

    def test_login_and_custom_header_are_required(self):
        response = self.upload(logged_in=False)
        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.is_json)
        self.assertEqual(self.upload(headers=False).status_code, 403)
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_failed_write_removes_partial_file_and_can_be_retried(self):
        def failed_save(storage, destination, *args, **kwargs):
            destination.write(b'partial')
            raise OSError('disk full')

        with patch.object(FileStorage, 'save', failed_save), self.assertLogs(self.app.logger, level='ERROR'):
            response = self.upload()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(list(self.folder.iterdir()), [])
        self.assertEqual(self.upload().status_code, 201)


if __name__ == '__main__':
    unittest.main()
