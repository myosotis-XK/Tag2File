"""HTTP contracts, slot permutations, and atomic manual-order notifications."""

from fractions import Fraction
import os
from pathlib import Path
import random
import threading
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtTest import QSignalSpy

from test_tag_notifications import TagbaseTestSupport


class ManualOrderAPITests(TagbaseTestSupport, unittest.TestCase):
    def seed(self, times=(100, 80, 50)):
        for path, timestamp in zip(self.paths, times):
            os.utime(path, (timestamp, timestamp))
        self.api.add_tag('A', self.paths)
        return self.paths

    def client(self):
        client = self.web.app.test_client()
        with client.session_transaction() as session:
            session['logged_in'] = True
            session['user_id'] = 1
        return client

    def post(self, operation, paths, **fields):
        return self.client().post('/api/manual_order/' + operation, json={
            'db_path': self.api.db_path, 'file_paths': paths, **fields,
        })

    def ranks(self):
        return {name: Fraction(value) for name, value in
                self.api.conn.execute('SELECT name, manual_order FROM file')}

    def database_order(self):
        # Independent of both the custom SQL collation and the in-memory order cache.
        rows = self.api.conn.execute('SELECT id, name, manual_order FROM file').fetchall()
        return [row[1] for row in sorted(rows, key=lambda row: (-Fraction(row[2]), row[0]))]

    def test_query_ignores_missing_paths_and_reads_only_requested_records(self):
        a, b, c = self.seed()
        statements = []
        self.api.conn.set_trace_callback(statements.append)
        try:
            response = self.post('query', [c.replace('/', '\\'), a])
        finally:
            self.api.conn.set_trace_callback(None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'success': True, 'file_paths': [a, c], 'missing_file_paths': []})
        self.assertIsNone(self.api._manual_order_cache)
        selects = [sql.upper() for sql in statements if sql.lstrip().upper().startswith('SELECT')]
        self.assertTrue(selects)
        self.assertTrue(all('WHERE' in sql for sql in selects), selects)
        self.assertFalse(self.api.conn.in_transaction)
        response = self.post('query', ['D:\\missing\\first.jpg', c, b, 'D:/missing/last.jpg'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            'success': True, 'file_paths': [b, c],
            'missing_file_paths': ['D:/missing/first.jpg', 'D:/missing/last.jpg'],
        })
        self.assertIsNone(self.api._manual_order_cache)
        self.assertFalse(self.api.conn.in_transaction)

    def test_query_all_missing_returns_empty_result_without_writes_or_notifications(self):
        # Files exist on disk, but none have been added to this tagbase.
        events = QSignalSpy(self.manager.fileChanged)
        before = self.api.conn.total_changes
        response = self.post('query', self.paths)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            'success': True, 'file_paths': [], 'missing_file_paths': self.paths,
        })
        self.assertEqual(self.api.conn.total_changes, before)
        self.assertEqual(len(events), 0)
        self.assertFalse(self.api.conn.in_transaction)

    def test_data_layer_strict_query_still_rejects_missing_files(self):
        a, b, c = self.seed()
        self.assertEqual(self.api.get_manual_file_order([c, a], strict=True), [a, c])
        with self.assertRaises(ValueError):
            self.api.get_manual_file_order([b, 'missing'], strict=True)
        self.assertFalse(self.api.conn.in_transaction)

    def test_data_layer_strict_set_still_rejects_missing_files(self):
        a, b, c = self.seed()
        with self.assertRaises(ValueError):
            self.api.set_manual_file_order([c, 'missing', a, b])
        self.assertEqual(self.database_order(), [a, b, c])
        self.assertFalse(self.api.conn.in_transaction)

    def test_set_all_missing_does_not_add_records_write_or_notify(self):
        # The requested files exist on disk; a loose set must not enroll them.
        events = QSignalSpy(self.manager.fileChanged)
        before = self.api.conn.total_changes
        response = self.post('set', self.paths)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            'success': True, 'changed': False, 'affected_count': 0, 'missing_file_paths': self.paths,
        })
        self.assertEqual(self.api.conn.total_changes, before)
        self.assertEqual(self.database_order(), [])
        self.assertEqual(len(events), 0)
        self.assertFalse(self.api.conn.in_transaction)

    def test_set_one_existing_file_with_missing_paths_is_noop(self):
        a, b, c = self.seed()
        events = QSignalSpy(self.manager.fileChanged)
        response = self.post('set', ['missing-first', c, 'missing-last'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            'success': True, 'changed': False, 'affected_count': 0,
            'missing_file_paths': ['missing-first', 'missing-last'],
        })
        self.assertEqual(self.database_order(), [a, b, c])
        self.assertEqual(len(events), 0)

    def test_move_uses_global_neighbors_keeps_group_order_and_publishes_once(self):
        a, b, c = self.seed()
        hidden = (self.folder / 'hidden.txt').as_posix()
        self.api.add_tag('hidden', [hidden])
        with self.api.conn:
            self.api.conn.execute("UPDATE file SET manual_order='95/1' WHERE name=?", (hidden,))
        events = QSignalSpy(self.manager.fileChanged)
        with patch.dict(self.web.app.config, PUBLISH_TAGBASE_CHANGES=self.manager.publish_changes), \
             patch.object(self.manager, 'publish_changes', wraps=self.manager.publish_changes) as publish:
            # The configured callback is independent of the patched bound-method lookup.
            with patch.dict(self.web.app.config, PUBLISH_TAGBASE_CHANGES=publish):
                response = self.post('move', [c, b], target=hidden, placement='before')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'success': True, 'changed': True, 'affected_count': 2})
        self.assertEqual(self.database_order(), [a, c, b, hidden])
        self.assertTrue(Fraction(95) < self.ranks()[b] < self.ranks()[c] < Fraction(100))
        self.assertEqual((publish.call_count, len(events)), (1, 1))
        self.assertEqual(events[0][0], 'manual_order_changed')
        response = self.post('move', [c, b], target=a, placement='after')
        self.assertFalse(response.get_json()['changed'])
        self.assertEqual(len(events), 1)

    def test_set_preserves_unsubmitted_slots_values_and_real_files(self):
        a, b, c = self.seed()
        hidden = [(self.folder / name).as_posix() for name in ('X.txt', 'Y.txt')]
        self.api.add_tag('hidden', hidden)
        with self.api.conn:
            self.api.conn.executemany('UPDATE file SET manual_order=? WHERE name=?',
                                     [('90/1', hidden[0]), ('70/1', hidden[1])])
        all_paths = self.paths + hidden
        self.assertEqual(self.api.get_manual_file_order(all_paths), [a, hidden[0], b, hidden[1], c])
        before = {p: (Path(p).read_bytes(), os.stat(p).st_mtime_ns) for p in self.paths}
        events = QSignalSpy(self.manager.fileChanged)
        response = self.post('set', [c, 'D:\\missing\\first.jpg', a, 'D:/missing/last.jpg', b])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            'success': True, 'changed': True, 'affected_count': 3,
            'missing_file_paths': ['D:/missing/first.jpg', 'D:/missing/last.jpg'],
        })
        expected = [c, hidden[0], a, hidden[1], b]
        self.assertEqual(self.database_order(), expected)
        self.assertEqual(self.api.get_manual_file_order(all_paths), expected)
        self.assertEqual(self.ranks(), {c: Fraction(100), a: Fraction(80), b: Fraction(50),
                                       hidden[0]: Fraction(90), hidden[1]: Fraction(70)})
        self.assertEqual(before, {p: (Path(p).read_bytes(), os.stat(p).st_mtime_ns) for p in self.paths})
        self.assertEqual(len(events), 1)
        self.assertFalse(self.post('set', [c, a, b]).get_json()['changed'])
        self.assertEqual(len(events), 1)
        self.api.close()
        del self.DataAPI._instances[self.api.db_path]
        self.web.tagbase_data_dict.pop(self.api.db_path, None)
        self.api = self.DataAPI(self.api.db_path)
        self.manager.load_tagbase(self.api.db_path)
        self.assertEqual(self.api.get_manual_file_order(all_paths), expected)

    def test_set_equal_rank_run_preserves_other_files_exact_slots(self):
        a, b, c = self.seed((100, 100, 100))
        x, y = [(self.folder / name).as_posix() for name in ('X.txt', 'Y.txt')]
        self.api.add_tag('hidden', [x, y])
        with self.api.conn:
            self.api.conn.execute("UPDATE file SET manual_order='100/1'")
        all_paths = [a, b, c, x, y]
        for warm in (False, True):
            if warm:
                self.api.get_manual_file_order(all_paths)
            desired = [y, a, c] if not warm else [a, c, y]
            response = self.post('set', ['missing-first', desired[0], 'missing-middle', *desired[1:]])
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['missing_file_paths'], ['missing-first', 'missing-middle'])
            expected = [desired[0], b, desired[1], x, desired[2]]
            self.assertEqual(self.database_order(), expected)
            self.assertEqual(self.api.get_manual_file_order(all_paths), expected)
        self.assertEqual(self.ranks()[b] > self.ranks()[x], True)

    def test_repeated_subsets_with_adjacent_equal_runs_preserve_every_other_slot(self):
        self.seed()
        extras = [(self.folder / f'{i}.txt').as_posix() for i in range(45)]
        self.api.add_tag('A', extras)
        all_paths = self.paths + extras
        with self.api.conn:
            self.api.conn.executemany('UPDATE file SET manual_order=? WHERE name=?', [
                (f'{100 - i // 4}/1', path) for i, path in enumerate(all_paths)])
        expected = self.database_order()
        generator = random.Random(13)
        for _ in range(70):
            selected = generator.sample(expected, generator.randint(2, len(expected)))
            selected_set = set(selected)
            replacements = iter(selected)
            expected = [next(replacements) if path in selected_set else path for path in expected]
            response = self.post('set', selected)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.database_order(), expected)
            self.assertEqual(self.api.get_manual_file_order(all_paths), expected)

    def test_query_and_set_support_more_than_one_sql_parameter_batch(self):
        self.seed()
        extras = [(self.folder / f'batch-{i}.txt').as_posix() for i in range(503)]
        self.api.add_tag('A', extras)
        all_paths = self.paths + extras
        with self.api.conn:
            self.api.conn.executemany('UPDATE file SET manual_order=? WHERE name=?', [
                (f'{1000 - i}/1', path) for i, path in enumerate(all_paths)])
        desired = all_paths[::-1]
        response = self.post('set', ['missing-first', *desired, 'missing-last'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['missing_file_paths'], ['missing-first', 'missing-last'])
        self.assertEqual(self.database_order(), desired)
        response = self.post('query', ['missing-first', *all_paths, 'missing-last'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['file_paths'], desired)
        self.assertEqual(response.get_json()['missing_file_paths'], ['missing-first', 'missing-last'])

    def test_set_and_query_never_scan_unrelated_files(self):
        a, b, c = self.seed()
        extras = [(self.folder / f'unrelated-{i}.txt').as_posix() for i in range(503)]
        self.api.add_tag('hidden', extras)
        statements = []
        self.api.conn.set_trace_callback(statements.append)
        try:
            self.assertEqual(self.post('set', [c, a, b]).status_code, 200)
            self.assertEqual(self.post('query', [a, b, c]).get_json()['file_paths'], [c, a, b])
        finally:
            self.api.conn.set_trace_callback(None)
        selects = [sql.upper() for sql in statements if sql.lstrip().upper().startswith('SELECT')]
        self.assertTrue(all('WHERE' in sql for sql in selects), selects)
        self.assertIsNone(self.api._manual_order_cache)

    def test_invalid_requests_are_json_and_do_not_notify_or_create_libraries(self):
        a, b, c = self.seed()
        saved = self.ranks()
        events = QSignalSpy(self.manager.fileChanged)
        client = self.client()
        base = {'db_path': self.api.db_path, 'file_paths': [a]}
        invalid = [None, [], {}, {**base, 'db_path': ''}, {**base, 'db_path': 123},
                   {**base, 'file_paths': []}, {**base, 'file_paths': 'path'},
                   {**base, 'file_paths': [None]}, {**base, 'file_paths': [' ']},
                   {**base, 'file_paths': [a, a.replace('/', '\\')]}]
        for operation in ('query', 'move', 'set'):
            for body in invalid:
                with self.subTest(operation=operation, body=body):
                    response = client.post('/api/manual_order/' + operation, json=body)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.get_json()['error'], 'invalid_request')
            response = client.post('/api/manual_order/' + operation, data='{', content_type='application/json')
            self.assertEqual(response.status_code, 400)
            body = {**base, 'target': b, 'placement': 'before', 'file_paths': [a, 'missing']}
            response = client.post('/api/manual_order/' + operation, json=body)
            self.assertEqual(response.status_code, 404 if operation == 'move' else 200)
            if operation != 'move':
                self.assertEqual(response.get_json()['missing_file_paths'], ['missing'])
            else:
                self.assertEqual(response.get_json()['error'], 'file_not_found')
            missing_db = (self.folder / 'does-not-exist.db').as_posix()
            body = {**base, 'db_path': missing_db, 'target': b, 'placement': 'before'}
            response = client.post('/api/manual_order/' + operation, json=body)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.get_json()['error'], 'tagbase_not_found')
            self.assertFalse(Path(missing_db).exists())
        for fields in ({}, {'target': b}, {'target': '', 'placement': 'before'},
                       {'target': b, 'placement': 'invalid'}, {'target': b, 'placement': []}):
            self.assertEqual(self.post('move', [a], **fields).status_code, 400)
        self.assertEqual(self.post('move', [a], target='missing', placement='after').status_code, 404)
        self.assertEqual(self.ranks(), saved)
        self.assertEqual(len(events), 0)
        self.assertFalse(self.api.conn.in_transaction)

    def test_unauthenticated_requests_return_401_json(self):
        self.seed()
        client = self.web.app.test_client()
        for operation in ('query', 'move', 'set'):
            response = client.post('/api/manual_order/' + operation, json={})
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.get_json()['error'], 'unauthorized')
            self.assertNotIn('Location', response.headers)

    def test_noop_set_single_file_and_move_to_self_do_not_publish(self):
        a, b, c = self.seed()
        with patch.dict(self.web.app.config, PUBLISH_TAGBASE_CHANGES=lambda _: self.fail('unexpected notification')):
            for operation, paths, fields in [('set', [a, b, c], {}), ('set', [b], {}),
                                             ('move', [a, b], {'target': a, 'placement': 'after'})]:
                response = self.post(operation, paths, **fields)
                expected = {'success': True, 'changed': False, 'affected_count': 0}
                if operation == 'set':
                    expected['missing_file_paths'] = []
                self.assertEqual(response.get_json(), expected)
        self.assertEqual(self.database_order(), [a, b, c])

    def test_transaction_failure_rolls_back_values_cache_and_notifications(self):
        a, b, c = self.seed()
        saved = self.ranks()
        self.api.get_manual_file_order(self.paths)
        aid = self.api.conn.execute('SELECT id FROM file WHERE name=?', (a,)).fetchone()[0]
        with self.api.conn:
            self.api.conn.execute(f'CREATE TRIGGER reject_manual_order BEFORE UPDATE OF manual_order ON file '
                                  f"WHEN OLD.id={aid} BEGIN SELECT RAISE(ABORT, 'injected failure'); END")
        self.api.get_manual_file_order(self.paths)
        cache = self.api._manual_order_cache
        events = QSignalSpy(self.manager.fileChanged)
        with self.assertLogs(self.web.app.logger.name, level='ERROR'):
            response = self.post('set', [c, 'missing', a, b])
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()['error'], 'database_error')
        self.assertEqual(self.ranks(), saved)
        self.assertEqual(cache, [a, b, c])
        self.assertEqual(self.api.get_manual_file_order(self.paths), [a, b, c])
        self.assertFalse(self.api.conn.in_transaction)
        self.assertEqual(len(events), 0)

    def test_worker_request_refreshes_desktop_once_on_gui_thread(self):
        from src.utils import config
        config['MainFileShowArea'] = {'search_sort_key': 'manual', 'search_sort_order': 'desc',
                                     'folder_sort_key': 'date', 'folder_sort_order': 'desc'}
        a, b, c = self.seed()
        window = self.window()
        view = window.MainFileShowArea
        view.set_selected_files([a, c], c)
        offset = view.get_scroll_offset()
        gui_thread = threading.get_ident()
        delivered_on = []
        def record(action, payload):
            delivered_on.append(threading.get_ident())
        self.manager.fileChanged.connect(record)
        self.addCleanup(lambda: self.manager.fileChanged.disconnect(record))
        files = QSignalSpy(view.filesChanged)
        responses = []
        with patch.object(view, 'set_files', wraps=view.set_files) as replaced, \
             patch.object(window, 'get_tag_files', wraps=window.get_tag_files) as search:
            worker = threading.Thread(target=lambda: responses.append(self.post('set', [c, a, b]).status_code))
            worker.start()
            worker.join(5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(delivered_on, [])
            self.drain()
        self.assertEqual(responses, [200])
        self.assertEqual(delivered_on, [gui_thread])
        self.assertEqual((len(files), replaced.call_count, search.call_count), (1, 0, 0))
        self.assertEqual(view.get_files(), [c, a, b])
        self.assertEqual(set(view.get_selected_files()), {a, c})
        self.assertEqual(view.get_current_file(), c)
        self.assertEqual(view.get_scroll_offset(), offset)

    def test_explicit_library_is_independent_of_active_desktop_library(self):
        a, b, c = self.seed()
        other = self.DataAPI(str(self.folder / 'other.db'))
        other.add_tag('A', self.paths)
        with other.conn:
            other.conn.executemany('UPDATE file SET manual_order=? WHERE name=?',
                                   [('100/1', a), ('80/1', b), ('50/1', c)])
        events = QSignalSpy(self.manager.fileChanged)
        response = self.post('set', [c, b, a], db_path=other.db_path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(other.get_manual_file_order(self.paths), [c, b, a])
        self.assertEqual(self.api.get_manual_file_order(self.paths), [a, b, c])
        self.assertEqual(self.manager.dataAPI.db_path, self.api.db_path)
        self.assertEqual(len(events), 0)


if __name__ == '__main__':
    unittest.main()
