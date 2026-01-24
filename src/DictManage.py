from .utils import *
import os
import threading
import sqlite3
from PyQt5.QtCore import QObject, QThread, Qt, QMetaObject

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
    _lock: threading.Lock
    ini_color: str
    tag2file_cache: dict[str, set[int]]
    file_cache: dict[int, tuple[str, int, float]]

    # 单例
    _instances: dict[str, "DataAPI"] = {}
    _cls_lock = threading.Lock()
    def __new__(cls, db_path: str):
        with cls._cls_lock:
            if db_path not in cls._instances:
                inst = super().__new__(cls)
                cls._instances[db_path] = inst
                inst.uncategorized_id = None

                # UI & 线程安全
                inst._lock = threading.Lock()

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
                        mtime REAL DEFAULT 0
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

                # 5️⃣ 插入默认数据
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

                # 6️⃣ 索引（性能关键）
                cur.execute("CREATE INDEX IF NOT EXISTS idx_tag_category ON tag(category_id);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_tag_file_tag ON tag_file(tag_id);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_tag_file_file ON tag_file(file_id);")
                
                cur.close()
        finally:
            conn.close()

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def rename_tag(self, old_name: str, new_name: str):
        with self._lock, self.conn:
            cur = self.conn.cursor()
            row = cur.execute("SELECT id FROM tag WHERE name=?", (old_name,)).fetchone()
            if not row:
                cur.close()
                return
            old_id = row[0]

            row = cur.execute("SELECT id FROM tag WHERE name=?", (new_name,)).fetchone()
            cur.close()

            if row: # 如果新名称存在，合并标签：将 old_name 的文件关联转移到 new_name
                new_id = row[0]
                self.conn.execute("""
                    INSERT OR IGNORE INTO tag_file(tag_id, file_id)
                    SELECT ?, file_id FROM tag_file WHERE tag_id = ?
                """, (new_id, old_id))
                self.conn.execute("DELETE FROM tag_file WHERE tag_id=?", (old_id,))
                self.conn.execute("DELETE FROM tag WHERE id=?", (old_id,))
            else:
                self.conn.execute("UPDATE tag SET name=? WHERE id=?", (new_name, old_id))

        # 同步缓存
        old_files = self.tag2file_cache.pop(old_name, None)
        if old_files is not None:
            if new_name in self.tag2file_cache:
                self.tag2file_cache[new_name] |= old_files
            else:
                self.tag2file_cache[new_name] = old_files

    def rename_file(self, old_name: str, new_name: str):
        with self._lock, self.conn:
            cur = self.conn.cursor()
            row = cur.execute("SELECT id FROM file WHERE name=?", (old_name,)).fetchone()
            cur.close()
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
        return {row[0] for row in cur.fetchall()}

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
        row = cur.fetchone()
        return row[0]

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
        return [row[0] for row in cur.fetchall()]

    def query(self, src_group: str, src_entity: str, dst_group: str):
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
        if tag in self.tag2file_cache:
            return len(self.tag2file_cache[tag])
        cur = self.conn.execute(
            """
            SELECT COUNT(*)
            FROM tag_file tf
            JOIN tag t ON t.id = tf.tag_id
            WHERE t.name = ?
            """,
            (tag,)
        )
        return cur.fetchone()[0]

    def get_all_files(self) -> set[tuple[str, int, float]]:
        with self._lock, self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT name, size_bytes, mtime FROM file")
            rows = cur.fetchall()
            cur.close()
        return {row[0] for row in rows}

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
    def _cleanup_orphan_files(self, file_ids: list[int]):
        with self._lock, self.conn:
            cur = self.conn.cursor()
            for file_id in file_ids:
                # 检查文件是否无关联 tag
                cur.execute("SELECT COUNT(*) FROM tag_file WHERE file_id=?", (file_id,))
                if cur.fetchone()[0] == 0:
                    # 删除文件
                    self.conn.execute("DELETE FROM file WHERE id=?", (file_id,))
                    if file_id in self.file_cache:
                        del self.file_cache[file_id]
            cur.close()

    def delete_tag(self, tag: str, file_paths: list[str]):
        with self._lock, self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT id FROM tag WHERE name=?", (tag,))
            row = cur.fetchone()
            if not row:
                return
            tag_id = row[0]
            file_ids = []
            for path in file_paths:
                cur.execute("SELECT id FROM file WHERE name=?", (path,))
                row = cur.fetchone()
                if row:
                    file_id = row[0]
                    file_ids.append(file_id)
                    cur.execute("DELETE FROM tag_file WHERE tag_id=? AND file_id=?", (tag_id, file_id))
            cur.close()
        self._cleanup_orphan_files(file_ids)
        if tag in self.tag2file_cache:
            self.tag2file_cache[tag] -= set(file_ids)

    def destroy_tag(self, tag: str):
        """删除标签及相关关系，同时清理孤立文件"""
        with self._lock, self.conn:
            cur = self.conn.cursor()
            # 查找 tag_id 和 category
            cur.execute("SELECT id FROM tag WHERE name=?", (tag,))
            row = cur.fetchone()
            if not row:
                return
            tag_id = row[0]

            # 删除 tag 与文件的关联
            cur.execute("SELECT file_id FROM tag_file WHERE tag_id=?", (tag_id,))
            file_ids = [r[0] for r in cur.fetchall()]

            # 删除 tag 本身
            cur.execute("DELETE FROM tag WHERE id=?", (tag_id,))
            cur.close()
        self._cleanup_orphan_files(file_ids)
        if tag in self.tag2file_cache:
            del self.tag2file_cache[tag]

    def change_special_tags_status(self, tag: str, status: bool):
        with self._lock, self.conn:
            self.conn.execute("""
                INSERT INTO tag_special_status (tag_id, status)
                VALUES (
                    (SELECT id FROM tag WHERE name = ?),
                    ?
                )
                ON CONFLICT(tag_id)
                DO UPDATE SET status = excluded.status
            """, (tag, int(status)))

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
        with self._lock, self.conn:
            cur = self.conn.cursor()
            row = cur.execute("SELECT id FROM file WHERE name=?", (file_path,)).fetchone()
            if not row:
                return
            fid = row[0]
            self.conn.execute("DELETE FROM file WHERE id=?", (fid,))
            cur.close()
        # 同步缓存
        self.file_cache.pop(fid, None)
        for tag, fids in self.tag2file_cache.items():
            fids.discard(fid)

    def add_tag(self, tag: str, file_paths: list[str]):
        if not tag or not file_paths:
            return

        THRESHOLD = 500      # 小批量阈值
        BATCH_SIZE = 10000   # 批量处理大小

        with self._lock, self.conn:
            cur = self.conn.cursor()

            # 确保 tag 存在
            cur.execute("SELECT id, category_id FROM tag WHERE name=?", (tag,))
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    "SELECT COALESCE(MAX(order_index), -1)+1 FROM tag WHERE category_id=?",
                    (self.uncategorized_id,)
                )
                order_index = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO tag (name, category_id, order_index) VALUES (?, ?, ?)",
                    (tag, self.uncategorized_id, order_index)
                )
                tag_id = cur.lastrowid
            else:
                tag_id = row[0]

            existing_files = {}

            # 查询已有文件 ID
            if len(file_paths) <= THRESHOLD:
                # 小批量直接 IN 查询
                placeholders = ','.join('?' for _ in file_paths)
                cur.execute(f"SELECT name, id FROM file WHERE name IN ({placeholders})", file_paths)
                existing_files = {row[0]: row[1] for row in cur.fetchall()}
            else:
                # 大批量使用临时表
                cur.execute("CREATE TEMP TABLE temp_files(name TEXT PRIMARY KEY)")
                for i in range(0, len(file_paths), BATCH_SIZE):
                    cur.executemany(
                        "INSERT INTO temp_files(name) VALUES (?)",
                        [(p,) for p in file_paths[i:i+BATCH_SIZE]]
                    )

                # 获取已有文件 ID
                cur.execute("SELECT f.name, f.id FROM file f JOIN temp_files t ON f.name = t.name")
                existing_files = {row[0]: row[1] for row in cur.fetchall()}

            # 批量插入不存在的文件
            new_files = [p for p in file_paths if p not in existing_files]
            if new_files:
                for i in range(0, len(new_files), BATCH_SIZE):
                    batch = new_files[i:i+BATCH_SIZE]
                    insert_datas = []
                    for file_path in batch:
                        st = os.stat(file_path)
                        size_bytes = st.st_size
                        mtime = st.st_mtime
                        insert_datas.append((file_path, size_bytes, mtime))
                    cur.executemany("INSERT INTO file(name, size_bytes, mtime) VALUES (?, ?, ?)", insert_datas) 

                # 查询新插入文件 ID
                for i in range(0, len(new_files), THRESHOLD):
                    batch = new_files[i:i+THRESHOLD]
                    placeholders = ','.join('?' for _ in batch)
                    cur.execute(f"SELECT id, name, size_bytes, mtime FROM file WHERE name IN ({placeholders})", batch)
                    rows = cur.fetchall()
                    for row in rows:
                        existing_files[row[1]] = row[0]
                        self.file_cache[row[0]] = (row[1], row[2], row[3]) # 同步缓存

            # 批量建立 tag ↔ file 关系
            for i in range(0, len(file_paths), BATCH_SIZE):
                cur.executemany(
                    "INSERT OR IGNORE INTO tag_file(tag_id, file_id) VALUES (?, ?)",
                    [(tag_id, existing_files[p]) for p in file_paths[i:i+BATCH_SIZE]]
                )

            # 清理临时表
            if len(file_paths) > THRESHOLD:
                cur.execute("DROP TABLE temp_files")

            cur.close()

            # 同步缓存
            if tag in self.tag2file_cache:
                self.tag2file_cache[tag] |= set(existing_files.values())



class Observer(QObject):
    def __init__(self):
        super().__init__()
        self.observer_thread = QThread.currentThread()

    def observer_update(self):
        pass

    def thread_safe_update(self):
        if QThread.currentThread() == self.observer_thread:
            self.observer_update()
        else:
            QMetaObject.invokeMethod(self, 'observer_update', Qt.QueuedConnection)

class DictManage():
    # 单例
    _instance = None
    _initialized = False
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._initialized = True

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
            
            self._observers: list[Observer] = []
   
    # 观察者模式
    def add_observer(self, observer: Observer):
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer: Observer):
        if observer in self._observers:
            self._observers.remove(observer)

    def notify_observers(self):
        for observer in self._observers:
            observer.thread_safe_update()

    # DataAPI 方法封装
    # 不通知观察者
    def query(self, src_group: str, src_entity: str, dst_group: str):
        return self.dataAPI.query(src_group, src_entity, dst_group)
    
    def query_tag_file_count(self, tag: str) -> int:
        return self.dataAPI.query_tag_file_count(tag)

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


    # 通知观察者
    def create_tagbase(self, db_path: str) -> None:
        self.dataAPI.create_tagbase(db_path)
        self.notify_observers()

    def load_tagbase(self, db_path: str) -> None:
        self.dataAPI = DataAPI(db_path)
        self.notify_observers()

    def rename_tag(self, old_name: str, new_name: str) -> None:
        self.dataAPI.rename_tag(old_name, new_name)
        self.notify_observers()

    def rename_file(self, old_name: str, new_name: str) -> None:
        self.dataAPI.rename_file(old_name, new_name)
        self.notify_observers()

    def rename_category(self, old_name: str, new_name: str) -> None:
        self.dataAPI.rename_category(old_name, new_name)
        self.notify_observers()


    def create_category(self, category: str) -> None:
        self.dataAPI.create_category(category)
        self.notify_observers()

    def delete_category(self, category: str) -> None:
        self.dataAPI.delete_category(category)
        self.notify_observers()

    def set_category_color(self, category: str, color: str) -> None:
        self.dataAPI.set_category_color(category, color)
        self.notify_observers()

    def set_category_special(self, category: str, is_special: int) -> None:
        self.dataAPI.set_category_special(category, is_special)
        self.notify_observers()

    def reorder_categories(self, new_order: list[str]) -> None:
        self.dataAPI.reorder_categories(new_order)
        self.notify_observers()


    def delete_tag(self, tag: str, file_paths: list[str]) -> None:
        self.dataAPI.delete_tag(tag, file_paths)
        self.notify_observers()

    def destroy_tag(self, tag: str) -> None:
        self.dataAPI.destroy_tag(tag)
        self.notify_observers()

    def change_special_tags_status(self, tag: str, status: bool) -> None:
        self.dataAPI.change_special_tags_status(tag, status)
        self.notify_observers()

    def change_tag_category(self, tag: str, category: str) -> None:
        self.dataAPI.change_tag_category(tag, category)
        self.notify_observers()

    def reorder_tags(self, new_order: list[str]) -> None:
        self.dataAPI.reorder_tags(new_order)
        self.notify_observers()


    def delete_file(self, file_path: str, notify = True) -> None:
        self.dataAPI.delete_file(file_path)
        if notify:
            self.notify_observers()

    def add_tag(self, tag: str, file_paths: list[str]) -> None:
        self.dataAPI.add_tag(tag, file_paths)
        self.notify_observers()