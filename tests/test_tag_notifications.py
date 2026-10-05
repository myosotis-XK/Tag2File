"""使用临时标签库和离屏 Qt 验证数据通知、刷新次数及预览范围。"""

import importlib
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import sip
from PyQt5.QtCore import QCoreApplication, QEvent, QEventLoop, QTimer
from PyQt5.QtGui import QImage
from PyQt5.QtTest import QSignalSpy
from PyQt5.QtWidgets import QApplication


class TagNotificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix="tag2file-notifications-")
        cls.root = Path(cls.workspace.name)
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

        # 导入 UI 模块前隔离配置，避免导入时的默认值写入用户 config.ini。
        import src.utils as utils
        config_module = importlib.import_module("src.utils.config")
        cls.saved_config = {section: dict(utils.config[section]) for section in utils.config.sections()}
        cls.patchers = [patch.object(utils, "save_config", lambda: None),
                        patch.object(config_module, "save_config", lambda: None)]
        for patcher in cls.patchers:
            patcher.start()
        utils.config.clear()
        utils.config["DictManage"] = {"tagbase_folder": str(cls.root), "tagbase_name": "initial"}
        from src.core.DictManage import DataAPI, DictManage
        from src.ui.MainWindow import Tag2File
        from src.ui.CategoryManager import CategoryManager
        from src.ui.file_grid_actions import FileActionService
        cls.DataAPI, cls.manager = DataAPI, DictManage()
        cls.MainWindow, cls.CategoryManager = Tag2File, CategoryManager
        cls.FileActionService = FileActionService

        # Flask 初始化自己的用户库，同样放在临时目录。
        (cls.root / "web_app").mkdir()
        with patch.object(utils, "root", str(cls.root)):
            cls.web = importlib.import_module("web_app.flask_app")
        cls.web.app.config.update(TESTING=True, PUBLISH_TAGBASE_CHANGES=cls.manager.publish_changes)

    @classmethod
    def tearDownClass(cls):
        for api in cls.DataAPI._instances.values():
            api.close()
        cls.DataAPI._instances.clear()
        import src.utils as utils
        utils.config.clear()
        utils.config.read_dict(cls.saved_config)
        for patcher in reversed(cls.patchers):
            patcher.stop()
        cls.workspace.cleanup()

    def drain(self):
        loop = QEventLoop()
        QTimer.singleShot(40, loop.quit)
        loop.exec_()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def setUp(self):
        self.folder = self.root / self._testMethodName
        self.folder.mkdir()
        self.api = self.DataAPI(str(self.folder / "tags.db"))
        self.manager.load_tagbase(self.api.db_path)
        self.widgets = []
        self.paths = []
        for index in range(3):
            path = self.folder / f"{index}.png"
            image = QImage(16, 16, QImage.Format_ARGB32)
            image.fill(0xFF334455)
            self.assertTrue(image.save(str(path)))
            self.paths.append(str(path).replace("\\", "/"))
        self.drain()

    def tearDown(self):
        for widget in reversed(self.widgets):
            if not sip.isdeleted(widget):
                widget.close()
                widget.deleteLater()
        self.drain()

    def spies(self):
        return (QSignalSpy(self.manager.tagChanged),
                QSignalSpy(self.manager.tagFileRelationChanged),
                QSignalSpy(self.manager.fileChanged))

    def window(self, query="A"):
        window = self.MainWindow()
        self.widgets.append(window)
        window.changeFile(query)
        self.drain()
        return window

    def tag_view(self, window):
        window.showTagView(None, self.paths[:2])
        view = window.tag_view
        self.widgets.append(view)
        view.TagFileShowArea.thumbnail_controller._thread_pool.waitForDone(2000)
        view.TagFileShowArea.preview_thumbnail_controller._thread_pool.waitForDone(2000)
        self.drain()
        return view

    def test_existing_tag_emits_only_actual_relationships(self):
        self.api.create_tag("A")
        self.api.add_tag("A", [self.paths[0]])
        tag, relation, file = self.spies()
        self.manager.add_tag("A", [self.paths[0], self.paths[1], self.paths[1]])
        self.assertEqual((len(tag), len(relation), len(file)), (0, 1, 0))
        self.assertEqual(relation[0][0], "added")
        self.assertEqual(relation[0][1]["added"], {"A": [self.paths[1]]})
        self.manager.add_tag("A", self.paths[:2])
        self.manager.delete_tag("missing", self.paths)
        self.manager.delete_tag("A", [self.paths[2]])
        self.assertEqual((len(tag), len(relation), len(file)), (0, 1, 0))

    def test_new_tag_and_relations_coalesce_into_one_refresh(self):
        self.api.add_tag("A", self.paths[:2])
        window = self.window()
        tag, relation, file = self.spies()
        with patch.object(window, "update_tag_widget", wraps=window.update_tag_widget) as tree, \
             patch.object(window, "get_tag_files", wraps=window.get_tag_files) as search, \
             patch.object(window.MainFileShowArea, "set_files", wraps=window.MainFileShowArea.set_files) as grid:
            self.manager.add_tag("new", [self.paths[0]])
            self.drain()
            self.assertEqual((len(tag), len(relation), len(file)), (1, 1, 0))
            self.assertEqual(tag[0][0], "created")
            self.assertEqual(tree.call_count, 1)
            self.assertEqual(search.call_count, 1)
            self.assertEqual(grid.call_count, 0)  # 相同查询结果保留原网格。
        self.assertIn("new", window.tag_input.tag_model.stringList())

    def test_membership_updates_count_and_search_without_rebuilding_tag_panels(self):
        self.api.add_tag("A", [self.paths[0]])
        window = self.window()
        view = self.tag_view(window)
        category = self.CategoryManager()
        self.widgets.append(category)
        original_tree = window.tag_tree
        original_label = window._tag_labels["A"]
        with patch.object(window, "get_tag_files", wraps=window.get_tag_files) as search, \
             patch.object(window.MainFileShowArea, "set_files", wraps=window.MainFileShowArea.set_files) as grid, \
             patch.object(view, "create_tag_widget", wraps=view.create_tag_widget) as tags, \
             patch.object(category, "loadCategories", wraps=category.loadCategories) as categories, \
             patch.object(self.manager, "get_all_tags", wraps=self.manager.get_all_tags) as library:
            self.manager.add_tag("A", [self.paths[1]])
            self.drain()
            self.assertEqual((search.call_count, grid.call_count), (1, 1))
            self.assertEqual((tags.call_count, categories.call_count, library.call_count), (0, 0, 0))
        self.assertIs(window.tag_tree, original_tree)
        self.assertIs(window._tag_labels["A"], original_label)
        self.assertEqual(original_label.count, "2")
        self.assertEqual(set(window.MainFileShowArea.get_files()), set(self.paths[:2]))

    def test_single_file_updates_labels_without_decoding_and_defers_when_hidden(self):
        self.api.add_tag("A", self.paths[:2])
        self.api.create_tag("B")
        self.api.create_tag("C")
        window = self.window()
        view = self.tag_view(window)
        single = view.SingleFileTagView
        # 切换模式会沿用网格焦点，明确保持同一文件（网格按时间排序）。
        view.TagFileShowArea.set_current_file(single.current_file_path)
        with patch("src.ui.SingleFileTagView.load_pixmap", side_effect=AssertionError("unexpected image decode")), \
             patch.object(single, "update_tags", wraps=single.update_tags) as tags:
            self.manager.add_tag("B", [single.current_file_path])
            self.drain()
            self.assertEqual(tags.call_count, 0)
            self.assertTrue(single._tags_dirty)
        view.toggle_view()
        view.TagFileShowArea.preview_thumbnail_controller._thread_pool.waitForDone(2000)
        self.drain()
        self.assertEqual({single.tag_layout.itemAt(i).widget().text() for i in range(single.tag_layout.count())}, {"A", "B"})
        with patch("src.ui.SingleFileTagView.load_pixmap", side_effect=AssertionError("unexpected image decode")), \
             patch.object(single, "update_tags", wraps=single.update_tags) as tags:
            self.manager.add_tag("C", [single.current_file_path])
            self.drain()
            self.assertEqual(tags.call_count, 1)
            self.assertEqual(single.tag_layout.count(), 3)
            self.manager.delete_tag("C", [single.current_file_path])
            self.drain()
            self.assertEqual(single.tag_layout.count(), 2)

    def test_last_tag_removal_updates_complement_without_deleting_disk_file(self):
        self.api.add_tag("A", [self.paths[0]])
        window = self.window("missing'")
        tag, relation, file = self.spies()
        self.manager.delete_tag("A", [self.paths[0]])
        self.drain()
        self.assertEqual((len(tag), len(relation), len(file)), (0, 1, 0))
        self.assertEqual(relation[0][1]["removed_file_paths"], [self.paths[0]])
        self.assertEqual(window.MainFileShowArea.get_files(), [])
        self.assertTrue(Path(self.paths[0]).exists())

    def test_merge_preserves_union_with_partially_populated_cache(self):
        self.api.add_tag("source", self.paths[:2])
        self.api.add_tag("target", self.paths[1:])
        self.api.query("tag", "source", "file")
        self.api.tag2file_cache.pop("target", None)
        tag, relation, file = self.spies()
        self.manager.rename_tag("source", "target")
        self.assertEqual((len(tag), len(relation), len(file)), (1, 1, 0))
        self.assertEqual(tag[0][0], "merged")
        self.assertEqual(relation[0][1]["added"], {"target": [self.paths[0]]})
        self.assertEqual({p for p, _, _ in self.api.query("tag", "target", "file")}, set(self.paths))
        self.manager.rename_tag("target", "target")
        self.assertEqual(len(tag), 1)

    def test_destroy_tag_reports_relationships_and_orphan_records(self):
        self.api.add_tag("A", self.paths[:2])
        self.api.add_tag("B", [self.paths[1]])
        tag, relation, file = self.spies()
        self.manager.destroy_tag("A")
        self.assertEqual((len(tag), len(relation), len(file)), (1, 1, 0))
        self.assertEqual(relation[0][1]["removed_file_paths"], [self.paths[0]])
        self.assertEqual(self.api.query("file", self.paths[1], "tag"), {"B"})

    def test_renames_keep_tag_and_file_event_boundaries(self):
        self.api.add_tag("A", [self.paths[0]])
        window = self.window()
        tag, relation, file = self.spies()
        self.manager.rename_tag("A", "renamed")
        self.drain()
        self.assertEqual((len(tag), len(relation), len(file)), (1, 0, 0))
        self.assertEqual(self.api.query("file", self.paths[0], "tag"), {"renamed"})
        self.assertIn("renamed", window.tag_input.tag_model.stringList())
        window.changeFile("renamed")
        with patch.object(window, "update_tag_widget", wraps=window.update_tag_widget) as tree, \
             patch.object(window, "get_tag_files", wraps=window.get_tag_files) as search, \
             patch.object(window.MainFileShowArea, "set_files", wraps=window.MainFileShowArea.set_files) as grid:
            self.manager.rename_file(self.paths[0], self.paths[1])
            self.drain()
            self.assertEqual((tree.call_count, search.call_count, grid.call_count), (0, 1, 1))
        self.assertEqual((len(tag), len(relation), len(file)), (1, 0, 1))
        self.assertEqual(window.MainFileShowArea.get_files(), [self.paths[1]])

    def test_bulk_file_delete_publishes_one_relation_and_one_file_event(self):
        self.api.add_tag("A", self.paths)
        window = self.window()
        tag, relation, file = self.spies()
        with patch.object(window, "get_tag_files", wraps=window.get_tag_files) as search:
            result = self.FileActionService(self.manager).delete_files(self.paths[:2])
            self.drain()
            self.assertTrue(result.success)
            self.assertEqual((len(tag), len(relation), len(file)), (0, 1, 1))
            self.assertEqual(search.call_count, 1)
        self.assertEqual(window._tag_labels["A"].count, "1")

    def test_large_batch_and_noop_have_precise_payloads(self):
        paths = [f"{self.folder.as_posix()}/{i}.txt" for i in range(1003)]
        first = self.api.add_tag("batch", paths + paths[:5])
        self.assertEqual(len(first.added_relations["batch"]), len(paths))
        self.assertIsNone(self.api.add_tag("batch", paths).relation_notification())
        removed = self.api.delete_tag("batch", paths[:503])
        self.assertEqual(len(removed.removed_relations["batch"]), 503)
        self.assertEqual(self.api.query_tag_file_count("batch"), 500)

    def test_disk_delete_and_partial_failure_publish_only_committed_changes(self):
        tag, relation, file = self.spies()
        service = self.FileActionService(self.manager)
        result = service.delete_files([self.paths[0]], os_delete=True)
        self.assertTrue(result.success)
        self.assertFalse(Path(self.paths[0]).exists())
        self.assertEqual((len(tag), len(relation), len(file)), (0, 0, 1))

        self.api.add_tag("A", [self.paths[1]])
        with patch("src.ui.file_grid_actions.os.remove", side_effect=PermissionError("locked")):
            result = service.delete_files([self.paths[1]], os_delete=True)
        self.assertFalse(result.success)
        self.assertTrue(Path(self.paths[1]).exists())
        self.assertEqual(self.api.query_tag_file_count("A"), 0)
        self.assertEqual((len(tag), len(relation), len(file)), (0, 1, 2))
        self.assertEqual(file[1][1]["file_paths"], [self.paths[1]])

    def test_failed_transaction_does_not_create_tag_cache_or_notifications(self):
        self.api.conn.execute("CREATE TRIGGER reject_relation BEFORE INSERT ON tag_file BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        self.api.conn.commit()
        tag, relation, file = self.spies()
        with self.assertRaises(sqlite3.IntegrityError):
            self.manager.add_tag("failed", [self.paths[0]])
        self.assertNotIn("failed", self.api.get_all_tags())
        self.assertEqual(self.api.get_all_files(), set())
        self.assertEqual(self.api.file_cache, {})
        self.assertEqual((len(tag), len(relation), len(file)), (0, 0, 0))

    def test_switch_database_reloads_once_and_updates_all_tag_views(self):
        self.api.add_tag("A", self.paths[:2])
        window = self.window()
        view = self.tag_view(window)
        other = self.DataAPI(str(self.folder / "other.db"))
        other.add_tag("other", [self.paths[0]])
        tag, relation, file = self.spies()
        with patch.object(window, "update_tag_widget", wraps=window.update_tag_widget) as tree, \
             patch.object(window, "get_tag_files", wraps=window.get_tag_files) as search, \
             patch.object(view, "create_tag_widget", wraps=view.create_tag_widget) as pool:
            self.manager.add_tag("A", [self.paths[2]])  # 旧库仍有待执行的刷新。
            self.manager.load_tagbase(other.db_path)
            self.drain()
            self.assertEqual((tree.call_count, search.call_count, pool.call_count), (1, 1, 1))
        self.assertIn("other", window.tag_input.tag_model.stringList())
        self.assertNotIn("A", window._tag_labels)
        self.assertEqual((len(tag), len(relation), len(file)), (0, 1, 0))

    def test_filter_toggle_and_audio_marker_refresh_scope(self):
        self.api.add_tag("A", self.paths[:2])
        window = self.window()
        with patch.object(window, "get_tag_files", wraps=window.get_tag_files) as search, \
             patch.object(window, "update_tag_widget", wraps=window.update_tag_widget) as tree:
            window.onSpecialLabelCheckChanged("图片", False)
            self.drain()
            self.assertEqual(search.call_count, 1)
            self.assertEqual(tree.call_count, 0)
            self.assertEqual(window.MainFileShowArea.get_files(), [])
            self.manager.fileChanged.emit("audio_markers_changed", {"file_paths": [self.paths[0]]})
            self.drain()
            self.assertEqual(search.call_count, 1)

    def test_web_notification_is_queued_to_gui_and_filters_other_databases(self):
        gui_thread = threading.get_ident()
        delivered_on = []
        def record(action, payload):
            delivered_on.append(threading.get_ident())
        self.manager.tagFileRelationChanged.connect(record)
        self.addCleanup(lambda: self.manager.tagFileRelationChanged.disconnect(record))
        responses = []
        def post(db_path):
            with self.web.app.test_client() as client:
                with client.session_transaction() as session:
                    session['logged_in'] = True
                    session['user_id'] = 1
                responses.append(client.post('/add_tag', json={
                    'db_path': db_path, 'tag': 'web', 'file_paths': [self.paths[0]],
                }).status_code)
        worker = threading.Thread(target=post, args=(self.api.db_path,))
        worker.start()
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(delivered_on, [])
        self.drain()
        self.assertEqual(responses, [200])
        self.assertEqual(delivered_on, [gui_thread])
        other = self.DataAPI(str(self.folder / 'other.db'))
        worker = threading.Thread(target=post, args=(other.db_path,))
        worker.start()
        worker.join(5)
        self.drain()
        self.assertEqual(responses, [200, 200])
        self.assertEqual(delivered_on, [gui_thread])


if __name__ == "__main__":
    unittest.main()
