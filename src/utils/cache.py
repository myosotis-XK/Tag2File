import time
import threading
from collections import OrderedDict

class AutoCleanupCache:
    def __init__(self, max_size=1000, ttl=600, cleanup_interval=60):
        """
        :param max_size: 最大缓存条数，设置为0则不限制大小
        :param ttl: 缓存过期时间，单位秒，默认10分钟
        :param cleanup_interval: 轮询清理过期缓存的间隔，单位秒，默认60秒
        """
        if max_size <= 0:
            max_size = float('inf')
        self.max_size = max_size
        self.ttl = ttl
        self.cleanup_interval = cleanup_interval
        self.cache = OrderedDict()  # 保持插入顺序，用于实现LRU
        self.lock = threading.Lock()
        self._stop_event = threading.Event()

        # 启动后台线程进行轮询清理
        self.thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.thread.start()

    def _cleanup_loop(self):
        while not self._stop_event.is_set():
            time.sleep(self.cleanup_interval)
            self.cleanup()

    def cleanup(self):
        """清理过期缓存"""
        with self.lock:
            now = time.time()
            keys_to_delete = [key for key, (value, timestamp) in self.cache.items()
                              if now - timestamp > self.ttl]
            for key in keys_to_delete:
                del self.cache[key]

    def set(self, key, value):
        with self.lock:
            if key in self.cache:
                del self.cache[key]  # 删除旧条目，下面会重新插入到末尾
            elif len(self.cache) >= self.max_size:
                # 超过最大缓存条数，删除最老的缓存
                self.cache.popitem(last=False)
            self.cache[key] = (value, time.time())

    def get(self, key, default=None):
        with self.lock:
            try:
                item = self.cache[key]
            except KeyError:
                return default
            value, _ = item
            # 更新为最近使用
            del self.cache[key]
            self.cache[key] = (value, time.time())
            return value
        
    def stop(self):
        """停止后台轮询线程"""
        self._stop_event.set()
        self.thread.join()

    def __setitem__(self, key, value):
        self.set(key, value)

    def __getitem__(self, key):
        with self.lock:
            item = self.cache[key]
            value, _ = item
            # 更新为最近使用
            del self.cache[key]
            self.cache[key] = (value, time.time())
            return value

    def __delitem__(self, key):
        with self.lock:
            del self.cache[key]

    def __contains__(self, key):
        with self.lock:
            return key in self.cache

    def __len__(self):
        return len(self.cache)