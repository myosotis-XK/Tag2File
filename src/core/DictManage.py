import os
import threading
import sqlite3
import time
import json
from PyQt5.QtCore import QObject, QThread, Qt, pyqtSignal, pyqtSlot
from src.utils import *
from .changes import TagbaseChanges, normalize_db_path

default_value = {
    'tagbase_folder': 'default_folder',
    'tagbase_name': 'tagbase',
    'default_folder': 'default_folder',
    'tagbase_list': '',
}
init_config_section('DictManage', default_value)
save_config()

class DataAPI():
    # 类型注解
    conn: sqlite3.Connection
    uncategorized_id: int
    _lock: threading.RLock
    ini_color: str
    tag2file_cache: dict[str, set[int]]
    file_cache: dict[int, tuple[str, int, float]]

    # 单例
    _instances: dict[str, "DataAPI"] = {}
    _cls_lock = threading.Lock()
    def __new__(cls, db_path: str):
        db_path = normalize_db_path(db_path)
        with cls._cls_lock:
            if db_path not in cls._instances:
                inst = super().__new__(cls)
                cls._instances[db_path] = inst
                inst.db_path = db_path
                inst.uncategorized_id = None

                # UI & 线程安全
                inst._lock = threading.RLock()

                # 配置
                inst.ini_color = "#c8c8c8"

                inst.tag2file_cache = {}
                inst.file_cache = {}

                # 加载数据库
                # 如果数据库不存在，创建
                if not os.path.exists(db_path):
                    inst.create_tagbase(db_path)

                inst.conn = sqlite3.connect(
                    db_path,
                    check_same_thread=False
                )
                inst.conn.execute("PRAGMA journal_mode=WAL;")
                inst.conn.execute("PRAGMA foreign_keys=ON;")

                # 缓存「未分类」ID
                cur = inst.conn.cursor()
                cur.execute("SELECT id FROM category WHERE name='未分类'")
                row = cur.fetchone()
                if row:
                    inst.uncategorized_id = row[0]
                else:
                    sql = """INSERT INTO category (name, color, order_index, is_special) VALUES (?, ?, 0, 0) RETURNING id;"""
                    cur.execute(sql, ("未分类", inst.ini_color))
                    inst.uncategorized_id = cur.fetchone()[0]
                    inst.conn.commit()
                cur.close()
            return cls._instances[db_path]
    
    def __init__(self, db_path: str):
        # 在 __new__ 中初始化
        pass

    def create_tagbase(self, db_path: str):
        """
        初始化 SQLite tagbase
        """
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        conn = sqlite3.connect(db_path)
        try:
            with conn:
                cur = conn.cursor()
                # category 表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS category (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        color TEXT NOT NULL,
                        order_index INTEGER NOT NULL,
                        is_special INTEGER NOT NULL DEFAULT 0
                    );
                """)

                # tag 表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS tag (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        category_id INTEGER NOT NULL,
                        order_index INTEGER NOT NULL,
                        FOREIGN KEY (category_id) REFERENCES category(id)
                    );
                """)

                # file 表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS file (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        size_bytes INTEGER DEFAULT 0,
                        mtime REAL DEFAULT 0,
                        extra_data TEXT
                    );
                """)

                # tag_file 关系表
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS tag_file (
                        tag_id INTEGER NOT NULL,
                        file_id INTEGER NOT NULL,
                        PRIMARY KEY (tag_id, file_id),
                        FOREIGN KEY (tag_id) REFERENCES tag(id) ON DELETE CASCADE,
                        FOREIGN KEY (file_id) REFERENCES file(id) ON DELETE CASCADE
                    );
                """)

                # tag_special_status 表
                cur.execute("""CREATE TABLE tag_special_status (
                    tag_id INTEGER PRIMARY KEY,
                    status INTEGER DEFAULT 0,
                    FOREIGN KEY(tag_id) REFERENCES tag(id) ON DELETE CASCADE
                    );
                """)

                # marker_preset 表（音频标记预设）
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS marker_preset (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        color TEXT NOT NULL,
                        order_index INTEGER NOT NULL
                    );
                """)

                # 插入默认数据
                cur.execute(
                    """
                        INSERT OR IGNORE INTO category (name, color, order_index, is_special)
                        VALUES (?, ?, 0, 1);
                    """, 
                    ("文件类型", "#000000")
                )
                category_id = cur.lastrowid
                for i, tag in enumerate(["图片","视频","音频","其他"]):
                    cur.execute(
                        """
                            INSERT OR IGNORE INTO tag (name, category_id, order_index)
                            VALUES (?, ?, ?);
                        """, 
                        (tag, category_id, i)
                    )

                cur.execute(
                    """
                        INSERT OR IGNORE INTO category (name, color, order_index, is_special)
                        VALUES (?, ?, 1, 0);
                    """,
                    ("未分类", self.ini_color)
                )

                # 索引
                cur.execute("CREATE INDEX IF NOT EXISTS idx_tag_category ON tag(category_id);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_tag_file_tag ON tag_file(tag_id);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_tag_file_file ON tag_file(file_id);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_marker_preset_order ON marker_preset(order_index);")

                cur.close()
        finally:
            conn.close()

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def rename_tag(self, old_name: str, new_name: str):
        changes = TagbaseChanges(self.db_path)
        if old_name == new_name:
            return changes
        with self._lock:
            with self.conn:
                cur = self.conn.cursor()
                try:
                    row = cur.execute("SELECT id FROM tag WHERE name=?", (old_name,)).fetchone()
                    if not row:
                        return changes
                    old_id = row[0]
                    files = cur.execute(
                        "SELECT f.id, f.name FROM file f JOIN tag_file tf ON f.id=tf.file_id WHERE tf.tag_id=?",
                        (old_id,),
                    ).fetchall()
                    row = cur.execute("SELECT id FROM tag WHERE name=?", (new_name,)).fetchone()
                    action = "renamed"
                    if row:
                        action = "merged"
                        new_id = row[0]
                        existing = {r[0] for r in cur.execute("SELECT file_id FROM tag_file WHERE tag_id=?", (new_id,))}
                        added = [path for fid, path in files if fid not in existing]
                        if added:
                            changes.added_relations[new_name] = added
                        if files:
                            changes.removed_relations[old_name] = [path for _, path in files]
                        cur.execute("INSERT OR IGNORE INTO tag_file(tag_id, file_id) SELECT ?, file_id FROM tag_file WHERE tag_id=?", (new_id, old_id))
                        cur.execute("DELETE FROM tag WHERE id=?", (old_id,))
                    else:
                        cur.execute("UPDATE tag SET name=? WHERE id=?", (new_name, old_id))
                    changes.tag_events.append((action, {
                        "old_name": old_name, "new_name": new_name,
                        "file_paths": [path for _, path in files],
                    }))
                finally:
                    cur.close()
            # 合并时目标标签可能只缓存了部分文件，重新查询比拼接不完整缓存可靠。
            self.tag2file_cache.pop(old_name, None)
            self.tag2file_cache.pop(new_name, None)
        return changes

    def rename_file(self, old_name: str, new_name: str):
        with self._lock, self.conn:
            cur = self.conn.cursor()
            row = cur.execute("SELECT id FROM file WHERE name=?", (old_name,)).fetchone()
            if not row:
                cur.close()
                return
            old_id = row[0]
            row = cur.execute("SELECT id FROM file WHERE name=?", (new_name,)).fetchone()
            cur.close()
            if row:
                raise ValueError("file already exists")
            self.conn.execute("UPDATE file SET name=? WHERE id=?", (new_name, old_id))
            
        # 同步缓存
        if old_id in self.file_cache:
            self.file_cache[old_id] = (new_name, self.file_cache[old_id][1], self.file_cache[old_id][2])

    def rename_category(self, old_name: str, new_name: str):
        with self._lock, self.conn:
            cur = self.conn.cursor()
            row = cur.execute("SELECT id FROM category WHERE name=?", (old_name,)).fetchone()
            if not row:
                cur.close()
                return
            old_id = row[0]
            row = cur.execute("SELECT id FROM category WHERE name=?", (new_name,)).fetchone()
            cur.close()
            if row:
                raise ValueError("category already exists")
            self.conn.execute("UPDATE category SET name=? WHERE id=?", (new_name, old_id))


    def _tag_to_file(self, tag: str) -> set[tuple[str, int, float]]:
        if tag in self.tag2file_cache:
            return {
                self.file_cache[fid]
                for fid in self.tag2file_cache[tag]
            }

        cur = self.conn.execute(
            """
            SELECT f.id, f.name, f.size_bytes, f.mtime
            FROM file f
            JOIN tag_file tf ON tf.file_id = f.id
            JOIN tag t ON t.id = tf.tag_id
            WHERE t.name = ?
            """,
            (tag,)
        )

        file_ids = set()
        for fid, name, size, mtime in cur.fetchall():
            self.file_cache[fid] = (name, size, mtime)
            file_ids.add(fid)

        cur.close()
        self.tag2file_cache[tag] = file_ids

        return {
            self.file_cache[fid]
            for fid in file_ids
        }

    def _file_to_tag(self, file_path: str) -> set[str]:
        """返回指定文件对应的所有 tag"""
        cur = self.conn.execute(
            """
            SELECT t.name
            FROM tag t
            JOIN tag_file tf ON tf.tag_id = t.id
            JOIN file f ON f.id = tf.file_id
            WHERE f.name = ?
            """,
            (file_path,)
        )
        try:
            return {row[0] for row in cur.fetchall()}
        finally:
            cur.close()

    def get_file_tags_batch(self, file_paths: list[str]) -> dict[str, list[str]]:
        """批量读取文件已有标签；标签库中不存在的文件返回空列表。"""
        paths = list(dict.fromkeys(file_paths))
        result = {path: [] for path in paths}
        with self._lock:
            for start in range(0, len(paths), 500):
                batch = paths[start:start + 500]
                if not batch:
                    continue
                placeholders = ",".join("?" for _ in batch)
                rows = self.conn.execute(
                    f"SELECT f.name, t.name FROM file f "
                    f"JOIN tag_file tf ON tf.file_id=f.id "
                    f"JOIN tag t ON t.id=tf.tag_id "
                    f"WHERE f.name IN ({placeholders}) ORDER BY f.name, t.name",
                    batch,
                ).fetchall()
                for path, tag in rows:
                    result[path].append(tag)
        return result

    def get_file_tag_details(self, file_path: str) -> list[tuple[str, str]]:
        with self._lock:
            return self.conn.execute(
                "SELECT t.name, c.color FROM file f JOIN tag_file tf ON f.id=tf.file_id "
                "JOIN tag t ON t.id=tf.tag_id JOIN category c ON c.id=t.category_id "
                "WHERE f.name=? ORDER BY c.order_index, t.order_index", (file_path,),
            ).fetchall()

    def _tag_to_category(self, tag: str) -> str:
        """返回指定 tag 所属的 category 名称"""
        cur = self.conn.execute(
            """
            SELECT c.name
            FROM category c
            JOIN tag t ON t.category_id = c.id
            WHERE t.name = ?
            """,
            (tag,)
        )
        try:
            row = cur.fetchone()
            return row[0]
        finally:
            cur.close()

    def _category_to_tag(self, category: str) -> list[str]:
        """返回指定 category 下的所有 tag 名称，按顺序"""
        cur = self.conn.execute(
            """
            SELECT t.name
            FROM tag t
            JOIN category c ON t.category_id = c.id
            WHERE c.name = ?
            ORDER BY t.order_index
            """,
            (category,)
        )
        try:
            return [row[0] for row in cur.fetchall()]
        finally:
            cur.close()

    def query(self, src_group: str, src_entity: str, dst_group: str):
        with self._lock:
            key = (src_group, dst_group)
            if key == ('tag', 'file'):
                return self._tag_to_file(src_entity)
            if key == ('file', 'tag'):
                return self._file_to_tag(src_entity)
            if key == ('tag', 'category'):
                return self._tag_to_category(src_entity)
            if key == ('category', 'tag'):
                return self._category_to_tag(src_entity)
            raise ValueError(f"unsupported relation {src_group} → {dst_group}")

    def query_tag_file_count(self, tag: str) -> int:
        with self._lock:
            if tag in self.tag2file_cache:
                return len(self.tag2file_cache[tag])
            cur = self.conn.execute(
                "SELECT COUNT(*) FROM tag_file tf JOIN tag t ON t.id=tf.tag_id WHERE t.name=?", (tag,),
            )
            try:
                return cur.fetchone()[0]
            finally:
                cur.close()

    def get_all_files(self) -> set[tuple[str, int, float]]:
        with self._lock, self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT name, size_bytes, mtime FROM file")
            rows = cur.fetchall()
            cur.close()
        return {row for row in rows}

    def get_all_tags(self) -> list[str]:
        with self._lock, self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT name FROM tag")
            rows = cur.fetchall()
            cur.close()
        return [row[0] for row in rows]

    def get_all_special_tags_status(self) -> list[tuple[str, int]]:
        with self._lock, self.conn:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT t.name, tss.status FROM tag_special_status tss
                LEFT JOIN tag t ON t.id = tss.tag_id
                """
            )
            rows = cur.fetchall()
            cur.close()
        return rows

    def get_special_tag_status(self, tag: str) -> bool:
        status = 1
        with self._lock, self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT id FROM tag WHERE name=?", (tag,))
            row = cur.fetchone()
            if not row:
                return
            tag_id = row[0]
            cur.execute("SELECT status FROM tag_special_status WHERE tag_id=?", (tag_id,))
            row = cur.fetchone()
            if row:
                status = row[0]
            else:
                cur.execute("INSERT INTO tag_special_status (tag_id, status) VALUES (?, 1)", (tag_id,))
            cur.close()
        return bool(status)

    def query_category(self, category: str = None) -> list[tuple[str, str, int]]:
        with self._lock, self.conn:
            cur = self.conn.cursor()
            if category:
                cur.execute("SELECT name, color, is_special FROM category WHERE name=?", (category,))
            else:
                cur.execute("SELECT name, color, is_special FROM category ORDER BY order_index")
            rows = cur.fetchall()
            cur.close()
        return rows

    # 类别操作
    def _create_category(self, category: str, cur: sqlite3.Cursor):
        cur.execute("SELECT id FROM category WHERE name=?", (category,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            "SELECT COALESCE(MAX(order_index), -1)+1 FROM category"
        )
        order_index = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO category (name, color, order_index) VALUES (?, ?, ?)",
            (category, self.ini_color, order_index)
        )
        category_id = cur.lastrowid
        return category_id
    
    def create_category(self, category: str):
        with self._lock, self.conn:
            cur = self.conn.cursor()
            self._create_category(category, cur)
            cur.close()

    def delete_category(self, category: str):
        with self._lock, self.conn:
            cur = self.conn.cursor()
            # 获取 category_id
            cur.execute("SELECT id FROM category WHERE name=?", (category,))
            row = cur.fetchone()
            if not row:
                return
            category_id = row[0]
            if category_id == self.uncategorized_id:
                return
            # 将该 category 下的 tags 移到未分类
            cur.execute("SELECT id FROM tag WHERE category_id=?", (category_id,))
            tag_ids = [r[0] for r in cur.fetchall()]
            for tid in tag_ids:
                cur.execute("UPDATE tag SET category_id=? WHERE id=?", (self.uncategorized_id, tid))
            # 删除 category
            cur.execute("DELETE FROM category WHERE id=?", (category_id,))
            cur.close()

    def set_category_color(self, category: str, color: str):
        with self._lock, self.conn:
            cur = self.conn.cursor()
            cur.execute("UPDATE category SET color=? WHERE name=?", (color, category))
            cur.close()

    def set_category_special(self, category: str, is_special: int):
        with self._lock, self.conn:
            cur = self.conn.cursor()
            cur.execute("UPDATE category SET is_special=? WHERE name=?", (is_special, category))
            cur.close()

    def reorder_categories(self, new_order: list[str]):
        with self._lock, self.conn:
            cur = self.conn.cursor()
            for index, name in enumerate(new_order):
                cur.execute(
                    "UPDATE category SET order_index=? WHERE name=?", 
                    (index, name)
                )
            cur.close()

    # 标签操作
    def _cleanup_orphan_files(self, file_ids: list[int], cur: sqlite3.Cursor) -> dict[int, str]:
        # 使用调用者的事务，关系删除和孤立记录清理一起提交或回滚。
        removed = {}
        for start in range(0, len(file_ids), 500):
            batch = file_ids[start:start + 500]
            placeholders = ','.join('?' for _ in batch)
            rows = cur.execute(
                f"SELECT id, name FROM file WHERE id IN ({placeholders}) "
                "AND NOT EXISTS (SELECT 1 FROM tag_file WHERE file_id=file.id)", batch,
            ).fetchall()
            removed.update(rows)
            cur.executemany("DELETE FROM file WHERE id=?", [(fid,) for fid, _ in rows])
        return removed

    def _create_tag(self, tag: str, cur: sqlite3.Cursor) -> int:
        cur.execute("SELECT COALESCE(MAX(order_index), -1)+1 FROM tag WHERE category_id=?", (self.uncategorized_id,))
        order_index = cur.fetchone()[0]
        cur.execute("INSERT INTO tag (name, category_id, order_index) VALUES (?, ?, ?)",
                    (tag, self.uncategorized_id, order_index))
        return cur.lastrowid

    def create_tag(self, tag: str) -> int:
        with self._lock, self.conn:
            cur = self.conn.cursor()
            try:
                return self._create_tag(tag, cur)
            finally:
                cur.close()

    def delete_tag(self, tag: str, file_paths: list[str]):
        changes = TagbaseChanges(self.db_path)
        paths = list(dict.fromkeys(path.replace('\\', '/') for path in file_paths))
        with self._lock:
            with self.conn:
                cur = self.conn.cursor()
                try:
                    row = cur.execute("SELECT id FROM tag WHERE name=?", (tag,)).fetchone()
                    if not row:
                        return changes
                    tag_id = row[0]
                    files = {}
                    for start in range(0, len(paths), 500):
                        batch = paths[start:start + 500]
                        placeholders = ','.join('?' for _ in batch)
                        files.update(cur.execute(
                            f"SELECT f.id, f.name FROM file f JOIN tag_file tf ON f.id=tf.file_id "
                            f"WHERE tf.tag_id=? AND f.name IN ({placeholders})", [tag_id, *batch],
                        ).fetchall())
                    cur.executemany("DELETE FROM tag_file WHERE tag_id=? AND file_id=?", [(tag_id, fid) for fid in files])
                    removed = self._cleanup_orphan_files(list(files), cur)
                finally:
                    cur.close()
            if files:
                changes.removed_relations[tag] = list(files.values())
            changes.removed_file_paths = list(removed.values())
            for fid in removed:
                self.file_cache.pop(fid, None)
            if tag in self.tag2file_cache:
                self.tag2file_cache[tag].difference_update(files)
        return changes

    def destroy_tag(self, tag: str):
        """删除标签及相关关系，同时清理孤立文件"""
        changes = TagbaseChanges(self.db_path)
        with self._lock:
            with self.conn:
                cur = self.conn.cursor()
                try:
                    row = cur.execute("SELECT id FROM tag WHERE name=?", (tag,)).fetchone()
                    if not row:
                        return changes
                    files = dict(cur.execute(
                        "SELECT f.id, f.name FROM file f JOIN tag_file tf ON f.id=tf.file_id WHERE tf.tag_id=?", (row[0],),
                    ).fetchall())
                    cur.execute("DELETE FROM tag WHERE id=?", (row[0],))
                    removed = self._cleanup_orphan_files(list(files), cur)
                finally:
                    cur.close()
            changes.tag_events.append(("deleted", {"tag": tag, "file_paths": list(files.values())}))
            if files:
                changes.removed_relations[tag] = list(files.values())
            changes.removed_file_paths = list(removed.values())
            for fid in removed:
                self.file_cache.pop(fid, None)
            self.tag2file_cache.pop(tag, None)
        return changes

    def change_special_tags_status(self, tag: str, status: bool):
        with self._lock, self.conn:
            row = self.conn.execute(
                "SELECT tss.status FROM tag t LEFT JOIN tag_special_status tss ON t.id=tss.tag_id WHERE t.name=?", (tag,),
            ).fetchone()
            if row is None or bool(1 if row[0] is None else row[0]) == bool(status):
                return False
            self.conn.execute("""
                INSERT INTO tag_special_status (tag_id, status)
                VALUES (
                    (SELECT id FROM tag WHERE name = ?),
                    ?
                )
                ON CONFLICT(tag_id)
                DO UPDATE SET status = excluded.status
            """, (tag, int(status)))
        return True

    def change_tag_category(self, tag: str, category: str):
        with self._lock, self.conn:
            cur = self.conn.cursor()
            # 获取 tag_id
            cur.execute("SELECT id FROM tag WHERE name=?", (tag,))
            row = cur.fetchone()
            if not row:
                return
            tag_id = row[0]
            category_id = self._create_category(category, cur)

            # 更新 tag 的 category_id
            cur.execute("UPDATE tag SET category_id=? WHERE id=?", (category_id, tag_id))

    def reorder_tags(self, new_order: list[str]):
        with self._lock, self.conn:
            cur = self.conn.cursor()
            for index, tag_name in enumerate(new_order):
                cur.execute(
                    "UPDATE tag SET order_index=? WHERE name=?",
                    (index, tag_name)
                )
            cur.close()


    # def add_tag(self, tag: str, file_paths: list[str]):
    #     # for循环
    #     if not tag or not file_paths:
    #         return

    #     with self._lock, self.conn:
    #         cur = self.conn.cursor()

    #         # 确保 tag 存在
    #         cur.execute("SELECT id, category_id FROM tag WHERE name=?", (tag,))
    #         row = cur.fetchone()
    #         if row is None:
    #             cur.execute(
    #                 "SELECT COALESCE(MAX(order_index), -1)+1 FROM tag WHERE category_id=?",
    #                 (self.uncategorized_id,)
    #             )
    #             order_index = cur.fetchone()[0]
    #             cur.execute(
    #                 "INSERT INTO tag (name, category_id, order_index) VALUES (?, ?, ?)",
    #                 (tag, self.uncategorized_id, order_index)
    #             )
    #             tag_id = cur.lastrowid
    #         else:
    #             tag_id = row[0]

    #         file_ids = set()
    #         for file_path in file_paths:
    #             # 检查文件是否已存在
    #             cur.execute("SELECT id FROM file WHERE name=?", (file_path,))
    #             row = cur.fetchone()
    #             if row:
    #                 fid = row[0]
    #             else:
    #                 # 插入新文件
    #                 st = os.stat(file_path)
    #                 size_bytes = st.st_size
    #                 mtime = st.st_mtime
    #                 cur.execute("INSERT INTO file (name, size_bytes, mtime) VALUES (?, ?, ?)", (file_path, size_bytes, mtime))
    #                 fid = cur.lastrowid
    #                 self.file_cache[fid] = (file_path, size_bytes, mtime)
    #             # 插入 tag_file 关联
    #             cur.execute("INSERT OR IGNORE INTO tag_file (tag_id, file_id) VALUES (?, ?)", (tag_id, fid))
    #             file_ids.add(fid)

    #         cur.close()

    #         # 同步缓存
    #         if tag in self.tag2file_cache:
    #             self.tag2file_cache[tag] |= file_ids


    # 文件操作
    def delete_file(self, file_path: str):
        changes = TagbaseChanges(self.db_path)
        with self._lock:
            with self.conn:
                cur = self.conn.cursor()
                try:
                    row = cur.execute("SELECT id FROM file WHERE name=?", (file_path,)).fetchone()
                    if not row:
                        return changes
                    fid = row[0]
                    tags = [row[0] for row in cur.execute(
                        "SELECT t.name FROM tag t JOIN tag_file tf ON t.id=tf.tag_id WHERE tf.file_id=?", (fid,),
                    ).fetchall()]
                    cur.execute("DELETE FROM file WHERE id=?", (fid,))
                finally:
                    cur.close()
            self.file_cache.pop(fid, None)
            for fids in self.tag2file_cache.values():
                fids.discard(fid)
            changes.file_events.append(("deleted", {"file_paths": [file_path]}))
            changes.removed_relations = {tag: [file_path] for tag in tags}
            changes.removed_file_paths = [file_path]
        return changes

    def add_tag(self, tag: str, file_paths: list[str]):
        changes = TagbaseChanges(self.db_path)
        if not tag or not file_paths:
            return changes
        paths = list(dict.fromkeys(path.replace('\\', '/') for path in file_paths))
        changed_files = {}
        with self._lock:
            with self.conn:
                cur = self.conn.cursor()
                try:
                    row = cur.execute("SELECT id FROM tag WHERE name=?", (tag,)).fetchone()
                    if row is None:
                        tag_id = self._create_tag(tag, cur)
                        changes.tag_events.append(("created", {"tag": tag}))
                    else:
                        tag_id = row[0]
                    for start in range(0, len(paths), 500):
                        batch = paths[start:start + 500]
                        placeholders = ','.join('?' for _ in batch)
                        sql = ("SELECT f.id, f.name, f.size_bytes, f.mtime, tf.file_id FROM file f "
                               "LEFT JOIN tag_file tf ON tf.file_id=f.id AND tf.tag_id=? "
                               f"WHERE f.name IN ({placeholders})")
                        rows = cur.execute(sql, [tag_id, *batch]).fetchall()
                        existing = {row[1] for row in rows}
                        new_files = []
                        for path in batch:
                            if path in existing:
                                continue
                            try:
                                stat = os.stat(path)
                                new_files.append((path, stat.st_size, stat.st_mtime))
                            except OSError:
                                new_files.append((path, 0, 0))
                        if new_files:
                            cur.executemany("INSERT INTO file(name, size_bytes, mtime) VALUES (?, ?, ?)", new_files)
                            changes.added_file_paths.extend(path for path, _, _ in new_files)
                            rows = cur.execute(sql, [tag_id, *batch]).fetchall()
                        additions = [row for row in rows if row[4] is None]
                        cur.executemany("INSERT INTO tag_file(tag_id, file_id) VALUES (?, ?)",
                                        [(tag_id, row[0]) for row in additions])
                        changed_files.update({fid: (path, size, mtime) for fid, path, size, mtime, _ in additions})
                finally:
                    cur.close()
            # 事务成功后才更新内存缓存；失败时不会留下半完成的标签或通知。
            self.file_cache.update(changed_files)
            if tag in self.tag2file_cache:
                self.tag2file_cache[tag].update(changed_files)
            if changed_files:
                changes.added_relations[tag] = [row[0] for row in changed_files.values()]
        return changes

    # ========== 通用 extra_data 管理方法 ==========

    def get_file_extra_data(self, file_path: str, key: str = None):
        """
        获取文件的 extra_data
        :param file_path: 文件路径
        :param key: 可选，指定获取的键（如 "audio_marker"）
        :return: 如果指定 key，返回该 key 的值；否则返回整个 extra_data 字典
        """
        with self._lock, self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT extra_data FROM file WHERE name=?", (file_path,))
            row = cur.fetchone()
            cur.close()

            if not row or not row[0]:
                return None if key else {}

            try:
                extra_data = json.loads(row[0])
                if key:
                    return extra_data.get(key)
                return extra_data
            except json.JSONDecodeError:
                return None if key else {}

    def set_file_extra_data(self, file_path: str, key: str, value):
        """
        设置文件 extra_data 的某个 key 的值（覆盖整个 key）
        :param file_path: 文件路径
        :param key: 要设置的键
        :param value: 要设置的值（会被序列化为 JSON）
        """
        with self._lock, self.conn:
            cur = self.conn.cursor()

            # 获取现有 extra_data
            cur.execute("SELECT extra_data FROM file WHERE name=?", (file_path,))
            row = cur.fetchone()

            if not row:
                cur.close()
                print(f"File not found: {file_path}")
                return

            # 解析现有数据
            try:
                extra_data = json.loads(row[0]) if row[0] else {}
            except json.JSONDecodeError:
                extra_data = {}

            # 设置新值
            extra_data[key] = value

            # 保存回数据库
            self.conn.execute(
                "UPDATE file SET extra_data=? WHERE name=?",
                (json.dumps(extra_data, ensure_ascii=False), file_path)
            )
            cur.close()

    def update_file_extra_data(self, file_path: str, key: str, value):
        """
        更新文件 extra_data（合并而非覆盖）
        如果 value 是字典，会合并到现有数据中
        :param file_path: 文件路径
        :param key: 要更新的键
        :param value: 要更新的值
        """
        with self._lock, self.conn:
            cur = self.conn.cursor()

            # 获取现有 extra_data
            cur.execute("SELECT extra_data FROM file WHERE name=?", (file_path,))
            row = cur.fetchone()

            if not row:
                cur.close()
                return

            # 解析现有数据
            try:
                extra_data = json.loads(row[0]) if row[0] else {}
            except json.JSONDecodeError:
                extra_data = {}

            # 合并数据
            if key in extra_data and isinstance(extra_data[key], dict) and isinstance(value, dict):
                extra_data[key].update(value)
            else:
                extra_data[key] = value

            # 保存回数据库
            self.conn.execute(
                "UPDATE file SET extra_data=? WHERE name=?",
                (json.dumps(extra_data, ensure_ascii=False), file_path)
            )
            cur.close()

    def delete_file_extra_data(self, file_path: str, key: str = None):
        """
        删除 extra_data 的某个 key 或整个 extra_data
        :param file_path: 文件路径
        :param key: 可选，指定要删除的键；如果为 None，删除整个 extra_data
        """
        with self._lock, self.conn:
            if key is None:
                # 删除整个 extra_data
                self.conn.execute("UPDATE file SET extra_data=NULL WHERE name=?", (file_path,))
            else:
                # 删除特定 key
                cur = self.conn.cursor()
                cur.execute("SELECT extra_data FROM file WHERE name=?", (file_path,))
                row = cur.fetchone()

                if not row or not row[0]:
                    cur.close()
                    return

                try:
                    extra_data = json.loads(row[0])
                    if key in extra_data:
                        del extra_data[key]
                        self.conn.execute(
                            "UPDATE file SET extra_data=? WHERE name=?",
                            (json.dumps(extra_data, ensure_ascii=False) if extra_data else None, file_path)
                        )
                except json.JSONDecodeError:
                    pass

                cur.close()

    def get_all_marker_presets(self):
        """
        获取所有标记预设
        :return: [(id, name, color, order_index), ...]
        """
        with self._lock, self.conn:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT id, name, color, order_index FROM marker_preset ORDER BY order_index"
            )
            presets = cur.fetchall()
            cur.close()
            return presets

    def create_marker_preset(self, name: str, color: str):
        """
        创建自定义标记预设
        :param name: 预设名称
        :param color: 颜色（十六进制）
        :return: 新创建的预设 ID
        """
        with self._lock, self.conn:
            cur = self.conn.cursor()

            # 获取当前最大 order_index
            cur.execute("SELECT MAX(order_index) FROM marker_preset")
            max_order = cur.fetchone()[0]
            next_order = (max_order or 0) + 1

            # 插入新预设
            cur.execute(
                """
                INSERT INTO marker_preset (name, color, order_index)
                VALUES (?, ?, ?)
                """,
                (name, color, next_order)
            )
            preset_id = cur.lastrowid
            cur.close()

            return preset_id

    def delete_marker_preset(self, preset_id: int):
        """
        删除预设
        :param preset_id: 预设 ID
        """
        with self._lock, self.conn:
            cur = self.conn.cursor()
            # 删除预设
            self.conn.execute("DELETE FROM marker_preset WHERE id=?", (preset_id,))
            cur.close()

    def update_marker_preset_order(self, preset_id: int, new_order_index: int):
        """
        更新预设的排序索引
        :param preset_id: 预设 ID
        :param new_order_index: 新的排序索引
        """
        with self._lock, self.conn:
            cur = self.conn.cursor()
            cur.execute(
                "UPDATE marker_preset SET order_index = ? WHERE id = ?",
                (new_order_index, preset_id)
            )
            cur.close()

    def update_marker_preset(self, preset_id: int, name: str, color: str):
        """
        更新预设的名称和颜色
        :param preset_id: 预设 ID
        :param name: 新的预设名称
        :param color: 新的颜色（十六进制）
        """
        with self._lock, self.conn:
            cur = self.conn.cursor()

            # 检查预设是否存在
            cur.execute("SELECT id FROM marker_preset WHERE id=?", (preset_id,))
            row = cur.fetchone()

            if not row:
                cur.close()
                raise ValueError("Preset not found")

            # 更新预设
            cur.execute(
                "UPDATE marker_preset SET name = ?, color = ? WHERE id = ?",
                (name, color, preset_id)
            )
            cur.close()

    def get_audio_markers(self, file_path: str) -> list[dict]:
        """
        获取指定音频文件的所有标记
        :param file_path: 文件路径
        :return: 标记列表 [{'id', 'type', 'time'/'start'/'end', 'label', 'color', 'preset_id', 'created_at'}, ...]
        """
        markers = self.get_file_extra_data(file_path, "audio_marker")
        return markers if markers else []

    def add_audio_marker(self, file_path: str, marker_data: dict):
        """
        添加单个音频标记
        :param file_path: 文件路径
        :param marker_data: 标记数据字典 {'type', 'time'/'start'/'end', 'label', 'color', 'preset_id'}
        :return: 新标记的 ID
        """
        markers = self.get_audio_markers(file_path)

        # 生成新 ID
        new_id = max([m.get('id', 0) for m in markers], default=0) + 1

        # 添加元数据
        marker_data['id'] = new_id
        marker_data['created_at'] = time.time()

        # 添加到列表
        markers.append(marker_data)

        # 保存
        self.set_file_extra_data(file_path, "audio_marker", markers)

        return new_id

    def update_audio_marker(self, file_path: str, marker_id: int, marker_data: dict):
        """
        更新指定 ID 的音频标记
        :param file_path: 文件路径
        :param marker_id: 标记 ID
        :param kwargs: 要更新的字段（如 label, color, time, start, end 等）
        """
        markers = self.get_audio_markers(file_path)
        for i, marker in enumerate(markers):
            if marker.get('id') == marker_id:
                markers[i] = marker_data
                break
        self.set_file_extra_data(file_path, "audio_marker", markers)

    def delete_audio_marker(self, file_path: str, marker_id: int):
        """
        删除指定 ID 的音频标记
        :param file_path: 文件路径
        :param marker_id: 标记 ID
        """
        markers = self.get_audio_markers(file_path)
        markers = [m for m in markers if m.get('id') != marker_id]
        self.set_file_extra_data(file_path, "audio_marker", markers)


class DictManage(QObject):
    # 标签元数据 / 分类 / 文件自身信息 / 标签与文件关联各自独立通知。
    # 同一操作可以产生多个事件，UI 在当前事件循环结束时合并刷新。
    tagChanged = pyqtSignal(str, object)
    categoryChanged = pyqtSignal(str, object)
    fileChanged = pyqtSignal(str, object)
    tagFileRelationChanged = pyqtSignal(str, object)
    _changesCommitted = pyqtSignal(object)
    audioMarkersChanged = pyqtSignal(str)
    markerPresetsChanged = pyqtSignal()
    tagbaseChanged = pyqtSignal(str)

    # 单例
    _instance = None
    _initialized = False
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            super().__init__()
            self._initialized = True
            self._changesCommitted.connect(self._deliver_changes, Qt.QueuedConnection)

            self.default_folder = config.get('DictManage', 'default_folder', fallback='default_folder')
            if self.default_folder == 'default_folder':
                self.default_folder = os.path.join(root, 'data', 'tagbase').replace('\\', '/')
            floder_path = config.get('DictManage', 'tagbase_folder', fallback='default_folder')
            if floder_path == 'default_folder':
                floder_path = self.default_folder
            os.makedirs(floder_path, exist_ok=True)
            tagbase_name = config.get('DictManage', 'tagbase_name', fallback='tagbase')
            self.db_path = os.path.join(floder_path, f"{tagbase_name}.db").replace('\\', '/')
            self.dataAPI = DataAPI(self.db_path)
            self.db_path = self.dataAPI.db_path

    def publish_changes(self, changes: TagbaseChanges) -> None:
        """Web 工作线程只投递结果，界面通知统一在 QObject 所在线程发出。"""
        if QThread.currentThread() == self.thread():
            self._deliver_changes(changes)
        else:
            self._changesCommitted.emit(changes)

    @pyqtSlot(object)
    def _deliver_changes(self, changes: TagbaseChanges) -> None:
        if changes.db_path != self.dataAPI.db_path:
            return
        for action, payload in changes.tag_events:
            self.tagChanged.emit(action, {**payload, "db_path": changes.db_path})
        relation = changes.relation_notification()
        if relation is not None:
            self.tagFileRelationChanged.emit(*relation)
        for action, payload in changes.file_events:
            self.fileChanged.emit(action, {**payload, "db_path": changes.db_path})

    # DataAPI 方法封装
    def query(self, src_group: str, src_entity: str, dst_group: str):
        return self.dataAPI.query(src_group, src_entity, dst_group)
    
    def query_tag_file_count(self, tag: str) -> int:
        return self.dataAPI.query_tag_file_count(tag)

    def get_file_tag_details(self, file_path: str):
        return self.dataAPI.get_file_tag_details(file_path)

    def get_all_files(self):
        return self.dataAPI.get_all_files()
    
    def get_all_tags(self):
        return self.dataAPI.get_all_tags()

    def get_all_special_tags_status(self):
        return self.dataAPI.get_all_special_tags_status()

    def get_special_tag_status(self, tag: str):
        return self.dataAPI.get_special_tag_status(tag)

    def query_category(self, category: str = None):
        return self.dataAPI.query_category(category)


    def create_tagbase(self, db_path: str) -> None:
        self.dataAPI.create_tagbase(db_path)

    def load_tagbase(self, db_path: str) -> None:
        self.dataAPI = DataAPI(db_path)
        self.db_path = self.dataAPI.db_path
        self.tagbaseChanged.emit(self.db_path)

    def rename_tag(self, old_name: str, new_name: str) -> None:
        self.publish_changes(self.dataAPI.rename_tag(old_name, new_name))

    def rename_file(self, old_name: str, new_name: str) -> None:
        self.dataAPI.rename_file(old_name, new_name)
        self.fileChanged.emit("renamed", {"old_path": old_name, "new_path": new_name})

    def rename_category(self, old_name: str, new_name: str) -> None:
        self.dataAPI.rename_category(old_name, new_name)
        payload = {"old_name": old_name, "new_name": new_name}
        self.categoryChanged.emit("renamed", payload)


    def create_category(self, category: str) -> None:
        self.dataAPI.create_category(category)
        self.categoryChanged.emit("created", {"category": category})

    def delete_category(self, category: str) -> None:
        self.dataAPI.delete_category(category)
        payload = {"category": category}
        self.categoryChanged.emit("deleted", payload)

    def set_category_color(self, category: str, color: str) -> None:
        self.dataAPI.set_category_color(category, color)
        self.categoryChanged.emit("color_changed", {"category": category, "color": color})

    def set_category_special(self, category: str, is_special: int) -> None:
        self.dataAPI.set_category_special(category, is_special)
        self.categoryChanged.emit("special_changed", {"category": category, "is_special": bool(is_special)})

    def reorder_categories(self, new_order: list[str]) -> None:
        self.dataAPI.reorder_categories(new_order)
        self.categoryChanged.emit("reordered", {"categories": list(new_order)})


    def create_tag(self, tag: str) -> None:
        self.dataAPI.create_tag(tag)
        self.tagChanged.emit("created", {"tag": tag})

    def delete_tag(self, tag: str, file_paths: list[str]) -> None:
        self.publish_changes(self.dataAPI.delete_tag(tag, file_paths))

    def destroy_tag(self, tag: str) -> None:
        self.publish_changes(self.dataAPI.destroy_tag(tag))

    def change_special_tags_status(self, tag: str, status: bool) -> None:
        if self.dataAPI.change_special_tags_status(tag, status):
            self.tagChanged.emit("special_status_changed", {"tag": tag, "status": bool(status)})

    def change_tag_category(self, tag: str, category: str) -> None:
        self.dataAPI.change_tag_category(tag, category)
        payload = {"tag": tag, "category": category}
        self.tagChanged.emit("category_changed", payload)

    def reorder_tags(self, new_order: list[str]) -> None:
        self.dataAPI.reorder_tags(new_order)
        self.tagChanged.emit("reordered", {"tags": list(new_order)})


    def delete_file(self, file_path: str, notify = True) -> TagbaseChanges:
        changes = self.dataAPI.delete_file(file_path)
        if notify:
            self.publish_changes(changes)
        return changes

    def add_tag(self, tag: str, file_paths: list[str]) -> None:
        self.publish_changes(self.dataAPI.add_tag(tag, file_paths))

    def get_audio_markers(self, file_path: str) -> list[dict]:
        return self.dataAPI.get_audio_markers(file_path)

    def add_audio_marker(self, file_path: str, marker_data: dict):
        marker_id = self.dataAPI.add_audio_marker(file_path, marker_data)
        self.audioMarkersChanged.emit(file_path)
        self.fileChanged.emit("audio_markers_changed", {"file_paths": [file_path]})
        return marker_id

    def update_audio_marker(self, file_path: str, marker_id: int, marker_data: dict):
        self.dataAPI.update_audio_marker(file_path, marker_id, marker_data)
        self.audioMarkersChanged.emit(file_path)
        self.fileChanged.emit("audio_markers_changed", {"file_paths": [file_path]})

    def delete_audio_marker(self, file_path: str, marker_id: int):
        self.dataAPI.delete_audio_marker(file_path, marker_id)
        self.audioMarkersChanged.emit(file_path)
        self.fileChanged.emit("audio_markers_changed", {"file_paths": [file_path]})

    def get_all_marker_presets(self):
        return self.dataAPI.get_all_marker_presets()

    def create_marker_preset(self, name: str, color: str):
        preset_id = self.dataAPI.create_marker_preset(name, color)
        self.markerPresetsChanged.emit()
        return preset_id

    def delete_marker_preset(self, preset_id: int):
        self.dataAPI.delete_marker_preset(preset_id)
        self.markerPresetsChanged.emit()
    
    def update_marker_preset_order(self, preset_id: int, new_order_index: int):
        self.dataAPI.update_marker_preset_order(preset_id, new_order_index)
        self.markerPresetsChanged.emit()

    def update_marker_preset(self, preset_id: int, name: str, color: str):
        self.dataAPI.update_marker_preset(preset_id, name, color)
        self.markerPresetsChanged.emit()
