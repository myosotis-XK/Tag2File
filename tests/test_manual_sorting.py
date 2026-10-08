"""Manual sort persistence, transactions, and offscreen Qt drag interaction."""

from fractions import Fraction
from pathlib import Path
import os
import random
import sqlite3
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QEvent, QMimeData, QPoint, Qt
from PyQt5.QtGui import QMouseEvent, QPixmap
from PyQt5.QtTest import QSignalSpy, QTest
from PyQt5.QtWidgets import QApplication, QLabel, QMenu

from test_tag_notifications import TagbaseTestSupport


class DragEvent:
    def __init__(self, view, position, source=None):
        self._source = view if source is None else source
        self._position = position
        self._mime = QMimeData()
        self._mime.setData("application/x-tag2file-manual-sort", b"internal")
        self.accepted = False

    def source(self):
        return self._source

    def mimeData(self):
        return self._mime

    def pos(self):
        return self._position

    def setDropAction(self, action):
        self.action = action

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.accepted = False


class ManualSortingTests(TagbaseTestSupport, unittest.TestCase):
    def setUp(self):
        super().setUp()
        from src.utils import config
        config["MainFileShowArea"] = {"search_sort_key": "date", "search_sort_order": "desc",
                                     "folder_sort_key": "date", "folder_sort_order": "desc"}

    def seed(self, times=(100, 80, 50)):
        for path, timestamp in zip(self.paths, times):
            os.utime(path, (timestamp, timestamp))
        self.api.add_tag("A", self.paths)
        return self.paths

    def ranks(self, api=None):
        return {name: Fraction(value) for name, value in
                (api or self.api).conn.execute("SELECT name, manual_order FROM file")}

    def extra_file(self, name, timestamp, tag="A"):
        path = self.folder / name
        path.write_bytes(b"manual sort test")
        os.utime(path, (timestamp, timestamp))
        normalized = path.as_posix()
        self.api.add_tag(tag, [normalized])
        return normalized

    def grid(self):
        window = self.window()
        view = window.MainFileShowArea
        view.set_sort("manual", "desc")
        self.drain()
        return window, view

    def activate_drag(self, view, paths):
        controller = view.manual_sort_controller
        controller._active = True
        controller._drag_paths = list(paths)
        controller._drag_db = self.api.db_path
        return controller

    def before(self, view, path):
        item = view.state.get_item(path)
        return QPoint(item.label_pos[0] + 1, item.label_pos[1] + 1) - view.get_scroll_offset()

    def image_point(self, view, path):
        label = view._labels[path]
        icon = label.findChild(QLabel, "icon_label")
        return icon.mapTo(label, QPoint(icon.width() // 2, icon.height() - 2))

    def test_initial_values_and_new_files_use_time_in_every_position(self):
        a, b, c = self.seed()
        before = {p: (Path(p).read_bytes(), os.stat(p).st_mtime_ns) for p in self.paths}
        self.assertEqual(self.ranks(), {a: Fraction(100), b: Fraction(80), c: Fraction(50)})
        self.api.move_files_manually([c], b, "before")
        self.assertEqual(self.ranks()[c], 90)
        middle = self.extra_file("middle.txt", 95)
        end = self.extra_file("end.txt", 20)
        front = self.extra_file("front.txt", 120)
        self.assertEqual(self.api.get_manual_file_order([end, c, front, a, middle, b]),
                         [front, a, middle, c, b, end])
        self.api.add_tag("another", [c])
        self.assertEqual(self.ranks()[c], 90)
        self.assertEqual(before, {p: (Path(p).read_bytes(), os.stat(p).st_mtime_ns) for p in self.paths})

    def test_legacy_migration_and_reopen_preserve_manual_values(self):
        a, b, c = self.seed()
        db_path = self.api.db_path
        self.api.close()
        del self.DataAPI._instances[db_path]
        with sqlite3.connect(db_path) as conn:
            conn.execute("DROP INDEX idx_file_manual_order")
            conn.execute("ALTER TABLE file DROP COLUMN manual_order")
        self.api = self.DataAPI(db_path)
        self.manager.load_tagbase(db_path)
        self.assertEqual(self.ranks()[c], 50)
        self.api.move_files_manually([c], b, "before")
        saved = self.ranks()
        self.api._ensure_manual_order_schema()
        self.assertEqual(self.ranks(), saved)
        self.api.close()
        del self.DataAPI._instances[db_path]
        self.api = self.DataAPI(db_path)
        self.manager.load_tagbase(db_path)
        self.assertEqual(self.ranks(), saved)
        self.assertEqual(self.api.get_manual_file_order(self.paths), [a, c, b])

    def test_time_changes_and_refresh_do_not_change_manual_position(self):
        a, b, c = self.seed()
        _, view = self.grid()
        self.manager.move_files_manually([c], b, "before")
        os.utime(c, (500, 500))
        view.refresh_files([c])
        self.api.conn.execute("UPDATE file SET mtime=500 WHERE name=?", (c,))
        self.api.conn.commit()
        view.resort_files()
        self.assertEqual(view.get_files(), [a, c, b])
        self.assertEqual(self.ranks()[c], 90)

    def test_group_move_uses_hidden_global_neighbors(self):
        a, b, c = self.seed()
        hidden = self.extra_file("hidden.txt", 95)
        before = self.ranks()
        self.api.move_files_manually([b, c], a, "after")
        self.assertEqual(self.api.get_manual_file_order([a, b, c, hidden]), [a, b, c, hidden])
        self.assertGreater(self.ranks()[c], before[hidden])
        self.assertEqual(self.ranks()[hidden], before[hidden])
        self.assertEqual(self.api.get_manual_file_order([c, a, b]), [a, b, c])

    def test_equal_times_are_stable_and_only_equal_run_is_redistributed(self):
        a, b, c = self.seed((80, 80, 80))
        high = self.extra_file("high.txt", 100)
        low = self.extra_file("low.txt", 50)
        saved = self.ranks()
        self.assertEqual(self.api.get_manual_file_order([c, b, a]), [a, b, c])
        self.api.move_files_manually([c], b, "before")
        self.assertEqual(self.api.get_manual_file_order([a, b, c, high, low]), [high, a, c, b, low])
        self.assertEqual(self.ranks()[high], saved[high])
        self.assertEqual(self.ranks()[low], saved[low])
        self.assertEqual(len({self.ranks()[p] for p in (a, b, c)}), 3)

    def test_equal_run_without_outer_neighbors_and_list_ends(self):
        a, b, c = self.seed((80, 80, 80))
        self.api.move_files_manually([c], b, "before")
        self.assertEqual(self.api.get_manual_file_order(self.paths), [a, c, b])
        self.api.move_files_manually([b], a, "before")
        self.assertEqual(self.api.get_manual_file_order(self.paths), [b, a, c])
        self.api.move_files_manually([b], c, "after")
        self.assertEqual(self.api.get_manual_file_order(self.paths), [a, c, b])

    def test_256_successive_insertions_remain_exact(self):
        a, b, c = self.seed()
        additional = [self.extra_file(f"insert-{i}.txt", 10) for i in range(256)]
        upper = self.ranks()[a]
        for path in additional:
            self.api.move_files_manually([path], b, "before")
            value = self.ranks()[path]
            self.assertTrue(Fraction(80) < value < upper)
            upper = value
        self.assertEqual(self.api.get_manual_file_order(self.paths + additional), [a, *additional, b, c])

    def test_invalid_noop_and_failed_transaction_do_not_publish(self):
        a, b, c = self.seed((80, 80, 80))
        spy = QSignalSpy(self.manager.fileChanged)
        self.manager.move_files_manually([a], b, "before")
        self.manager.move_files_manually([a], a, "after")
        for paths, target, placement in [([c], "missing", "before"),
                                         (["missing"], a, "before"), ([c], a, "invalid")]:
            with self.assertRaises(ValueError):
                self.manager.move_files_manually(paths, target, placement)
        saved = self.ranks()
        saved_order = self.api.get_manual_file_order(self.paths)
        bid = self.api.conn.execute("SELECT id FROM file WHERE name=?", (b,)).fetchone()[0]
        self.api.conn.execute(f"CREATE TRIGGER reject_sort BEFORE UPDATE OF manual_order ON file "
                              f"WHEN OLD.id={bid} BEGIN SELECT RAISE(ABORT, 'sort failed'); END")
        self.api.conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.manager.move_files_manually([c], b, "before")
        self.assertEqual(self.ranks(), saved)
        self.assertEqual(self.api.get_manual_file_order(self.paths), saved_order)
        self.assertFalse(self.api.conn.in_transaction)
        self.assertEqual(len(spy), 0)

    def test_indexed_neighbors_and_cached_refresh_avoid_full_library_reads(self):
        a, b, c = self.seed()
        hidden = self.extra_file("hidden.txt", 95, "hidden")
        many = [(self.folder / f"missing-{index}.txt").as_posix() for index in range(1003)]
        self.api.add_tag("many", many)
        all_paths = self.paths + [hidden] + many
        self.api.get_manual_file_order(all_paths)
        plan = self.api.conn.execute(
            "EXPLAIN QUERY PLAN SELECT id, name, manual_order FROM file INDEXED BY idx_file_manual_order "
            "WHERE manual_order COLLATE fraction_order > ? "
            "ORDER BY manual_order COLLATE fraction_order ASC, id DESC LIMIT 2", ("80/1",),
        ).fetchall()
        description = ' '.join(row[3] for row in plan)
        self.assertIn("SEARCH file USING INDEX idx_file_manual_order", description)
        self.assertNotIn("TEMP B-TREE", description)
        statements = []
        self.api.conn.set_trace_callback(statements.append)
        try:
            self.api.move_files_manually([c], b, "before")
            self.assertEqual(self.api.get_manual_file_order([a, b, c, hidden]), [a, hidden, c, b])
        finally:
            self.api.conn.set_trace_callback(None)
        selects = [sql.upper() for sql in statements if sql.lstrip().upper().startswith("SELECT")]
        self.assertTrue(selects)
        self.assertTrue(all("WHERE" in sql for sql in selects), selects)
        self.assertEqual(self.ranks()[c], Fraction(175, 2))

    def test_manual_cache_refreshes_after_local_and_external_changes(self):
        a, b, c = self.seed()
        self.assertEqual(self.api.get_manual_file_order(self.paths), [a, b, c])
        self.api.move_files_manually([c], b, "before")
        self.assertEqual(self.api.get_manual_file_order(self.paths), [a, c, b])
        front = self.extra_file("new.txt", 120)
        self.assertEqual(self.api.get_manual_file_order(self.paths + [front]), [front, a, c, b])
        renamed = (self.folder / "renamed.png").as_posix()
        self.api.rename_file(a, renamed)
        self.assertEqual(self.api.get_manual_file_order([renamed, b, c, front]), [front, renamed, c, b])
        self.api.delete_file(front)
        self.assertEqual(self.api.get_manual_file_order([renamed, b, c, front]), [renamed, c, b])
        external = sqlite3.connect(self.api.db_path)
        try:
            external.create_collation("fraction_order", self.api._compare_manual_order)
            external.execute("UPDATE file SET manual_order='20/1' WHERE name=?", (c,))
            external.commit()
        finally:
            external.close()
        self.assertEqual(self.api.get_manual_file_order([renamed, b, c]), [renamed, b, c])

    def test_repeated_group_moves_match_index_order_and_preserve_other_files(self):
        self.seed()
        extra = [(self.folder / f"group-{index}.txt").as_posix() for index in range(30)]
        self.api.add_tag("A", extra)
        all_paths = self.paths + extra
        with self.api.conn:
            self.api.conn.executemany("UPDATE file SET manual_order=? WHERE name=?", [
                (f"{100 - index // 3 * 5}/1", path) for index, path in enumerate(all_paths)
            ])
        order = self.api.get_manual_file_order(all_paths)
        generator = random.Random(42)
        for _ in range(70):
            moving = generator.sample(order, generator.randint(1, 4))
            remaining = [path for path in order if path not in moving]
            target = generator.choice(remaining)
            placement = generator.choice(["before", "after"])
            index = remaining.index(target) + (placement == "after")
            expected = remaining[:index] + moving + remaining[index:]
            self.api.move_files_manually(moving, target, placement)
            order = self.api.get_manual_file_order(all_paths)
            self.assertEqual(order, expected)
            raw = self.api.conn.execute("SELECT id, name, manual_order FROM file").fetchall()
            raw.sort(key=lambda row: (-Fraction(row[2]), row[0]))
            self.assertEqual([row[1] for row in raw], expected)

    def test_rename_delete_and_other_library(self):
        a, b, c = self.seed()
        self.api.move_files_manually([c], b, "before")
        renamed = (self.folder / "renamed.png").as_posix()
        result = self.FileActionService(self.manager).rename_file(c, "renamed.png")
        self.assertTrue(result.success)
        self.assertEqual(self.ranks()[renamed], 90)
        other = self.DataAPI(str(self.folder / "other.db"))
        other.add_tag("A", [a, b, renamed])
        self.assertEqual(other.get_manual_file_order([a, b, renamed]), [a, b, renamed])
        self.api.delete_file(renamed)
        self.assertNotIn(renamed, self.ranks())
        self.assertEqual(self.api.get_manual_file_order([a, b]), [a, b])

    def test_move_notification_resorts_once_and_preserves_grid_state(self):
        a, b, c = self.seed()
        window, view = self.grid()
        view.set_selected_files([b, c], c)
        changes = QSignalSpy(view.filesChanged)
        events = QSignalSpy(self.manager.fileChanged)
        offset = view.get_scroll_offset()
        with patch.object(view, "set_files", wraps=view.set_files) as replaced, \
             patch.object(window, "get_tag_files", wraps=window.get_tag_files) as search:
            self.manager.move_files_manually([c], b, "before")
            self.drain()
        self.assertEqual(view.get_files(), [a, c, b])
        self.assertEqual(set(view.get_selected_files()), {b, c})
        self.assertEqual(view.get_current_file(), c)
        self.assertEqual(view.get_scroll_offset(), offset)
        self.assertEqual((len(changes), len(events), replaced.call_count, search.call_count), (1, 1, 0, 0))

    def test_search_folder_settings_are_independent_and_manual_is_restored(self):
        a, b, c = self.seed()
        window, view = self.grid()
        self.manager.move_files_manually([c], b, "before")
        view.set_selected_files([c], c)
        window.enter_folder(str(self.folder))
        self.assertFalse(view.is_manual_sort())
        self.assertNotIn("manual", dict(view._sort_options()))
        view.set_sort("name", "asc")
        window.restore_search_snapshot()
        self.assertTrue(view.is_manual_sort())
        self.assertEqual(view.get_files(), [a, c, b])
        self.assertEqual(view.get_selected_files(), [c])
        window.enter_folder(str(self.folder))
        self.assertEqual((view.current_sort_key, view.current_sort_order), ("name", "asc"))

    def test_manual_menu_and_normal_sort_do_not_erase_saved_order(self):
        a, b, c = self.seed()
        _, view = self.grid()
        self.manager.move_files_manually([c], b, "before")
        menu = QMenu()
        view.addSortMenu(menu)
        actions = menu.actions()[0].menu().actions()
        self.assertFalse(actions[-1].isEnabled())
        self.assertFalse(actions[-2].isEnabled())
        view.set_sort("date", "desc")
        self.assertEqual(view.get_files(), [a, b, c])
        view.set_sort("manual", "desc")
        self.assertEqual(view.get_files(), [a, c, b])

    def test_click_preserves_group_until_release_and_ctrl_toggles(self):
        a, b, c = self.seed()
        _, view = self.grid()
        label = view._labels[a]
        point = self.image_point(view, a)
        view.set_selected_files([a, c], a)
        QTest.mousePress(label, Qt.LeftButton, pos=point)
        self.assertEqual(set(view.get_selected_files()), {a, c})
        QTest.mouseRelease(label, Qt.LeftButton, pos=point)
        self.assertEqual(view.get_selected_files(), [a])
        QTest.mouseClick(view._labels[c], Qt.LeftButton, Qt.ControlModifier)
        self.assertEqual(set(view.get_selected_files()), {a, c})

    def test_drag_threshold_and_qdrag_capture_selected_group(self):
        a, b, c = self.seed()
        _, view = self.grid()
        controller = view.manual_sort_controller
        label = view._labels[a]
        position = self.image_point(view, a)
        view.set_selected_files([a, c], a)
        captured = []

        class FakeDrag:
            def __init__(self, source):
                self.source = source
            def setMimeData(self, mime):
                self.mime = mime
            def setPixmap(self, pixmap):
                pass
            def setHotSpot(self, hotspot):
                pass
            def exec_(self, action):
                captured.append((controller._drag_paths[:], self.mime.hasFormat(controller.MIME_TYPE)))
                return Qt.IgnoreAction
            def deleteLater(self):
                pass

        QTest.mousePress(label, Qt.LeftButton, pos=position)
        with patch("src.ui.file_grid_manual_sort.QDrag", FakeDrag):
            QApplication.sendEvent(label, QMouseEvent(QEvent.MouseMove, position + QPoint(1, 0),
                                                       Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
            self.assertEqual(captured, [])
            QApplication.sendEvent(label, QMouseEvent(QEvent.MouseMove,
                position + QPoint(QApplication.startDragDistance() + 1, 0),
                Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
        self.assertEqual(captured, [([a, c], True)])
        self.assertFalse(controller._active)
        self.assertFalse(view.rubber_band.isVisible())

    def test_drag_starts_only_on_thumbnail_using_context_menu_hit_test(self):
        a, b, c = self.seed()
        _, view = self.grid()
        controller = view.manual_sort_controller
        label = view._labels[a]
        icon = label.findChild(QLabel, "icon_label")
        filename = label.findChild(QLabel, "file_name_label")
        pixmap = QPixmap(40, 20)
        pixmap.fill(Qt.blue)
        icon.setPixmap(pixmap)
        # A small, bottom-aligned image leaves whitespace inside the icon widget.
        outside = [(icon, QPoint(50, 5)), (icon, QPoint(5, 90)),
                   (filename, filename.rect().center()), (label, QPoint(1, 1))]
        for widget, point in outside:
            with self.subTest(widget=widget.objectName(), point=point):
                with patch.object(controller, "_start_drag") as started, \
                     patch.object(view, "isMouseOnThumbnail", wraps=view.isMouseOnThumbnail) as hit:
                    QTest.mousePress(widget, Qt.LeftButton, pos=point)
                    self.assertIsNone(controller._pending_path)
                    self.assertTrue(view.mouse_press)
                    self.assertTrue(hit.called)
                    QApplication.sendEvent(widget, QMouseEvent(QEvent.MouseMove, point + QPoint(20, 0),
                                                               Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
                    started.assert_not_called()
                    QTest.mouseRelease(widget, Qt.LeftButton, pos=point + QPoint(20, 0))
        image = QPoint(50, 90)
        with patch.object(controller, "_start_drag") as started, \
             patch.object(view, "isMouseOnThumbnail", wraps=view.isMouseOnThumbnail) as hit:
            QTest.mousePress(icon, Qt.LeftButton, pos=image)
            self.assertEqual(controller._pending_path, a)
            self.assertEqual(hit.call_args[0], (icon.mapTo(label, image), label))
            QApplication.sendEvent(icon, QMouseEvent(QEvent.MouseMove, image + QPoint(20, 0),
                                                    Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
            started.assert_called_once()
            QTest.mouseRelease(icon, Qt.LeftButton, pos=image + QPoint(20, 0))
        icon.clear()
        QTest.mousePress(label, Qt.LeftButton, pos=self.image_point(view, a))
        self.assertIsNone(controller._pending_path)
        QTest.mouseRelease(label, Qt.LeftButton, pos=self.image_point(view, a))

    def test_blank_rubber_selection_and_double_click_still_work(self):
        a, b, c = self.seed()
        _, view = self.grid()
        view.setFixedSize(300, 400)
        view.updateLayout()
        QTest.mousePress(view, Qt.LeftButton, pos=QPoint(1, 1))
        QApplication.sendEvent(view, QMouseEvent(QEvent.MouseMove, QPoint(290, 350),
                                                Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
        self.assertTrue(view.rubber_band.isVisible())
        QTest.mouseRelease(view, Qt.LeftButton, pos=QPoint(290, 350))
        self.assertEqual(set(view.get_selected_files()), {a, b, c})
        self.assertFalse(view.manual_sort_controller._active)
        activated = QSignalSpy(view.fileActivated)
        with patch("src.ui.FileShowArea.MultiImageViewer") as viewer:
            icon = view._labels[a].findChild(QLabel, "icon_label")
            QTest.mouseDClick(icon, Qt.LeftButton, pos=icon.rect().center())
            self.assertEqual(len(activated), 1)
            viewer.return_value.load_image_files.assert_called_once_with(view.get_files(), a)

    def test_reorder_preserves_nonzero_scroll_and_selection(self):
        self.seed()
        for index in range(24):
            self.extra_file(f"scroll-{index}.txt", 40 - index)
        _, view = self.grid()
        view.setFixedSize(250, 200)
        view.updateLayout()
        view.set_scroll_offset(100)
        offset = view.get_scroll_offset()
        self.assertGreater(offset.y(), 0)
        first, last = view.get_files()[0], view.get_files()[-1]
        view.set_selected_files([last], last)
        changed = QSignalSpy(view.filesChanged)
        self.manager.move_files_manually([last], first, "before")
        self.assertEqual(view.get_scroll_offset(), offset)
        self.assertEqual(view.get_selected_files(), [last])
        self.assertEqual(view.get_current_file(), last)
        self.assertEqual(len(changed), 1)

    def test_drop_group_and_noop_use_visible_slot(self):
        a, b, c = self.seed()
        hidden = self.extra_file("hidden.txt", 95, "hidden")
        _, view = self.grid()
        view.set_selected_files([b, c], b)
        controller = self.activate_drag(view, [b, c])
        first = view.state.get_item(a)
        event = DragEvent(view, QPoint(first.label_pos[0] + first.label_size[0], first.label_pos[1] + 1))
        view.dropEvent(event)
        self.assertFalse(event.accepted)  # Already after A in this filtered view.
        self.assertEqual(self.ranks()[hidden], 95)
        controller = self.activate_drag(view, [b, c])
        event = DragEvent(view, self.before(view, a))
        view.dragMoveEvent(event)
        self.assertTrue(controller.marker.isVisible())
        view.dropEvent(event)
        self.assertTrue(event.accepted)
        self.assertEqual(view.get_files(), [b, c, a])
        self.assertEqual(self.api.get_manual_file_order([a, b, c, hidden]), [b, c, a, hidden])

    def test_drop_save_failure_keeps_order_and_reports_error(self):
        a, b, c = self.seed()
        _, view = self.grid()
        self.api.conn.execute("CREATE TRIGGER reject_sort BEFORE UPDATE OF manual_order ON file "
                              "BEGIN SELECT RAISE(ABORT, 'sort failed'); END")
        self.api.conn.commit()
        saved = self.ranks()
        self.activate_drag(view, [c])
        event = DragEvent(view, self.before(view, a))
        errors = QSignalSpy(view.errorOccurred)
        with patch("src.ui.FileShowArea.QMessageBox.critical"):
            view.dropEvent(event)
        self.assertFalse(event.accepted)
        self.assertEqual(len(errors), 1)
        self.assertEqual(view.get_files(), [a, b, c])
        self.assertEqual(self.ranks(), saved)

    def test_external_drop_and_context_changes_cancel_drag(self):
        a, b, c = self.seed()
        _, view = self.grid()
        controller = self.activate_drag(view, [c])
        external = DragEvent(view, self.before(view, a), source=object())
        view.dragEnterEvent(external)
        self.assertFalse(external.accepted)
        view.set_browse_context("folder")
        self.assertFalse(controller._active)
        view.set_browse_context("search")
        self.activate_drag(view, [c])
        view.set_files([(p, 0, 0) for p in (a, b)])
        self.assertFalse(controller._active)
        self.activate_drag(view, [a])
        other = self.DataAPI(str(self.folder / "other.db"))
        self.manager.load_tagbase(other.db_path)
        self.assertFalse(controller._active)

    def test_edge_scroll_and_layout_hit_test_cover_virtualized_rows(self):
        self.seed()
        for index in range(30):
            self.extra_file(f"long-file-name-{index}.txt", 40 - index)
        _, view = self.grid()
        view.setFixedSize(250, 200)
        view.updateLayout()
        controller = self.activate_drag(view, [self.paths[0]])
        event = DragEvent(view, QPoint(100, 195))
        view.dragMoveEvent(event)
        self.assertTrue(controller.scroll_timer.isActive())
        with patch("src.ui.file_grid_manual_sort.QCursor.pos", return_value=view.mapToGlobal(event.pos())):
            controller._auto_scroll()
        self.assertGreater(view.v_scroll.value(), 0)
        self.assertLess(len(view._labels), len(view.get_files()))
        view.v_scroll.setValue(view.v_scroll.maximum())
        controller.update_position(QPoint(240, 180))
        self.assertIsNotNone(controller._target)
        rows = [[((10, 10), (80, 100), "a"), ((100, 10), (80, 60), "b")],
                [((10, 120), (80, 160), "c"), ((100, 120), (80, 80), "d")],
                [((10, 290), (80, 100), "e")]]
        self.assertEqual(view.layout_engine.get_insertion_index(QPoint(20, 250), rows), 2)
        self.assertEqual(view.layout_engine.get_insertion_index(QPoint(150, 250), rows), 4)
        self.assertEqual(view.layout_engine.get_insertion_index(QPoint(20, 400), rows), 5)

    def test_drag_autoscroll_runs_during_moves_and_stationary_edge_hover(self):
        self.seed()
        for index in range(30):
            self.extra_file(f"autoscroll-{index}.txt", 40 - index)
        _, view = self.grid()
        view.setFixedSize(250, 200)
        view.updateLayout()
        controller = self.activate_drag(view, [self.paths[0]])
        edge = QPoint(100, view.height() - view.h_scroll.height() - 2)
        event = DragEvent(view, edge)
        with patch("src.ui.file_grid_manual_sort.QCursor.pos", side_effect=lambda: view.mapToGlobal(edge)):
            for _ in range(20):
                view.dragMoveEvent(event)
                QTest.qWait(5)
            self.assertGreater(view.v_scroll.value(), 0)
            moving_value = view.v_scroll.value()
            QTest.qWait(80)
            self.assertGreater(view.v_scroll.value(), moving_value)
        center = QPoint(100, 100)
        with patch("src.ui.file_grid_manual_sort.QCursor.pos", side_effect=lambda: view.mapToGlobal(center)):
            view.dragMoveEvent(DragEvent(view, center))
            stopped_value = view.v_scroll.value()
            QTest.qWait(80)
            self.assertEqual(view.v_scroll.value(), stopped_value)
        controller.cancel()
        self.assertFalse(controller.scroll_timer.isActive())

    def test_drag_autoscroll_outside_edges_limits_and_drop_cleanup(self):
        self.seed()
        for index in range(30):
            self.extra_file(f"outside-{index}.txt", 40 - index)
        _, view = self.grid()
        view.setFixedSize(250, 200)
        view.updateLayout()
        controller = self.activate_drag(view, [self.paths[0]])
        view.v_scroll.setValue(200)
        top = QPoint(100, 2)
        view.dragEnterEvent(DragEvent(view, top))
        controller.leave()
        with patch("src.ui.file_grid_manual_sort.QCursor.pos", side_effect=lambda: view.mapToGlobal(QPoint(100, -15))):
            QTest.qWait(80)
            self.assertLess(view.v_scroll.value(), 200)
        near_value = view.v_scroll.value()
        with patch("src.ui.file_grid_manual_sort.QCursor.pos", side_effect=lambda: view.mapToGlobal(QPoint(100, -180))):
            QTest.qWait(80)
            self.assertLess(view.v_scroll.value(), near_value)
            self.assertFalse(controller.marker.isVisible())
            self.assertIsNone(controller._target)
        view.v_scroll.setValue(500)
        with patch("src.ui.file_grid_manual_sort.QCursor.pos", side_effect=lambda: view.mapToGlobal(QPoint(-180, -180))):
            QTest.qWait(80)
            self.assertLess(view.v_scroll.value(), 500)
        stopped = view.v_scroll.value()
        with patch("src.ui.file_grid_manual_sort.QCursor.pos", side_effect=lambda: view.mapToGlobal(QPoint(-180, 100))):
            QTest.qWait(80)
            self.assertEqual(view.v_scroll.value(), stopped)
        with patch("src.ui.file_grid_manual_sort.QCursor.pos", side_effect=lambda: view.mapToGlobal(QPoint(100, -180))):
            view.v_scroll.setValue(0)
            QTest.qWait(50)
            self.assertEqual(view.v_scroll.value(), 0)
        with patch("src.ui.file_grid_manual_sort.QCursor.pos", side_effect=lambda: view.mapToGlobal(QPoint(430, 380))):
            view.v_scroll.setValue(50)
            QTest.qWait(80)
            self.assertGreater(view.v_scroll.value(), 50)
            self.assertFalse(controller.marker.isVisible())
            view.v_scroll.setValue(view.v_scroll.maximum())
            QTest.qWait(50)
            self.assertEqual(view.v_scroll.value(), view.v_scroll.maximum())
        # A rejected drop must also stop the polling timer.
        view.dropEvent(DragEvent(view, QPoint(100, 100), source=object()))
        self.assertFalse(controller.scroll_timer.isActive())

    def test_drag_autoscroll_handles_horizontal_overflow(self):
        self.seed()
        _, view = self.grid()
        view.setFixedSize(80, 200)
        view.updateLayout()
        controller = self.activate_drag(view, [self.paths[0]])
        right = QPoint(280, 100)
        view.dragMoveEvent(DragEvent(view, right))
        with patch("src.ui.file_grid_manual_sort.QCursor.pos", side_effect=lambda: view.mapToGlobal(right)):
            QTest.qWait(80)
            self.assertGreater(view.h_scroll.value(), 0)
        previous = view.h_scroll.value()
        with patch("src.ui.file_grid_manual_sort.QCursor.pos", side_effect=lambda: view.mapToGlobal(QPoint(-200, 100))):
            QTest.qWait(80)
            self.assertLess(view.h_scroll.value(), previous)
        controller.cancel()

    def test_native_drag_lifetime_keeps_scroll_outside_then_stops_on_release(self):
        self.seed()
        for index in range(30):
            self.extra_file(f"drag-lifetime-{index}.txt", 40 - index)
        _, view = self.grid()
        view.setFixedSize(250, 200)
        view.updateLayout()
        controller = view.manual_sort_controller
        label = view._labels[self.paths[0]]
        observations = []

        class FakeDrag:
            def __init__(self, source):
                pass
            def setMimeData(self, mime):
                pass
            def setPixmap(self, pixmap):
                pass
            def setHotSpot(self, hotspot):
                pass
            def deleteLater(self):
                pass
            def exec_(self, action):
                controller.leave()
                with patch("src.ui.file_grid_manual_sort.QCursor.pos",
                           side_effect=lambda: view.mapToGlobal(QPoint(100, 400))):
                    QTest.qWait(80)
                    observations.append((view.v_scroll.value(), controller.scroll_timer.isActive()))
                return Qt.IgnoreAction  # Released outside any accepting target.

        QTest.mousePress(label, Qt.LeftButton, pos=self.image_point(view, self.paths[0]))
        with patch("src.ui.file_grid_manual_sort.QDrag", FakeDrag):
            controller._start_drag()
        self.assertGreater(observations[0][0], 0)
        self.assertTrue(observations[0][1])
        self.assertFalse(controller._active)
        self.assertFalse(controller.scroll_timer.isActive())
        value_after_release = view.v_scroll.value()
        with patch("src.ui.file_grid_manual_sort.QCursor.pos", side_effect=lambda: view.mapToGlobal(QPoint(100, 400))):
            QTest.qWait(80)
            self.assertEqual(view.v_scroll.value(), value_after_release)

    def test_web_new_file_initializes_manual_value(self):
        self.seed()
        path = self.folder / "web.txt"
        path.write_bytes(b"web insertion")
        os.utime(path, (95, 95))
        with self.web.app.test_client() as client:
            with client.session_transaction() as session:
                session['logged_in'] = True
                session['user_id'] = 1
            response = client.post('/add_tag', json={
                'db_path': self.api.db_path, 'tag': 'A', 'file_paths': [path.as_posix()],
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ranks()[path.as_posix()], 95)


if __name__ == "__main__":
    unittest.main()
