import os
from typing import Callable, Optional

from PyQt5.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from src.models import PixmapIcon, PixmapSequenceIcon, draw_text_on_pixmap, get_file_init_icon
from src.utils import get_cache_path, thumbnailExtractor

from .file_grid_state import FileGridState


# ---------------- 缩略图加载 ----------------

class ThumbnailWorkerSignals(QObject):
    loaded = pyqtSignal(str, int, object, int)


class ThumbnailWorker(QRunnable):
    def __init__(self, file_path: str, image_size: int, generation: int):
        super().__init__()
        self.file_path = file_path
        self.image_size = image_size
        self.generation = generation
        self.signals = ThumbnailWorkerSignals()

    def run(self):
        file_path = self.file_path
        image_size = self.image_size
        icon = None

        try:
            thumbnail_sequence = thumbnailExtractor.extract_thumbnail(file_path, image_size)
            if thumbnail_sequence:
                if thumbnail_sequence.animated:
                    icon = PixmapSequenceIcon(thumbnail_sequence)
                else:
                    image = thumbnail_sequence.frames[0]
                    icon = PixmapIcon(image)
                    cache_path = get_cache_path(file_path, image_size)
                    image.save(cache_path, "PNG")

            if icon is None:
                icon = get_file_init_icon(file_path, image_size)
                if not os.path.exists(file_path):
                    icon = PixmapIcon(draw_text_on_pixmap(icon.source, "文件不存在"))
        except Exception:
            icon = get_file_init_icon(file_path, image_size)
            if not os.path.exists(file_path):
                icon = PixmapIcon(draw_text_on_pixmap(icon.source, "文件不存在"))

        self.signals.loaded.emit(file_path, image_size, icon, self.generation)


class ThumbnailController(QObject):
    def __init__(self, apply_icon_callback: Callable[[str], None], parent: Optional[QObject] = None):
        super().__init__(parent)
        self._apply_icon_callback = apply_icon_callback
        self._thread_pool = QThreadPool()
        self._generation = 0

    def invalidate(self) -> None:
        # 通过 generation 丢弃过时缩略图结果，替代 UI 线程里阻塞等待旧任务结束。
        self._generation += 1
        self._thread_pool.clear()

    def load(
        self,
        state: FileGridState,
        file_paths: list[str],
        image_size: int,
        use_cache: bool = True,
    ) -> None:
        # 优先命中内存/磁盘缓存；只有当前尺寸缺失时才真正提交后台任务。
        if not file_paths:
            return
        self._generation += 1
        generation = self._generation
        self._thread_pool.clear()

        for file_path in file_paths:
            file_item = state.get_item_if_exists(file_path)
            if file_item is None:
                continue

            if use_cache and image_size in file_item.icon_source:
                file_item.icon = True
                file_item.icon_source["current"] = file_item.icon_source[image_size]
                self._apply_icon_callback(file_path)
                continue

            if use_cache:
                cache_path = get_cache_path(file_path, image_size)
                if os.path.exists(cache_path):
                    from PyQt5.QtGui import QPixmap

                    pixmap = QPixmap(cache_path)
                    if not pixmap.isNull():
                        icon = PixmapIcon(pixmap)
                        file_item.icon = True
                        file_item.icon_source[image_size] = icon
                        file_item.icon_source["current"] = icon
                        self._apply_icon_callback(file_path)
                        continue

            worker = ThumbnailWorker(file_path, image_size, generation)
            worker.signals.loaded.connect(lambda path, size, icon, gen: self._handle_loaded(state, path, size, icon, gen))
            self._thread_pool.start(worker)

    def _handle_loaded(self, state: FileGridState, file_path: str, image_size: int, icon: object, generation: int) -> None:
        if generation != self._generation:
            return

        file_item = state.get_item_if_exists(file_path)
        if file_item is None:
            return

        file_item.icon = True
        file_item.icon_source[image_size] = icon
        if isinstance(icon, PixmapSequenceIcon):
            file_item.icon_source["current"] = icon
        else:
            pixmap = icon.source
            if not os.path.exists(file_path):
                pixmap = draw_text_on_pixmap(pixmap, "文件不存在")
            file_item.icon_source["current"] = PixmapIcon(pixmap)

        self._apply_icon_callback(file_path)
