import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from PyQt5.QtCore import QObject, QPoint, QRect, QRunnable, QSize, Qt, QThreadPool, pyqtSignal
from PyQt5.QtGui import QPixmap

from src.core.DictManage import DictManage
from src.models import FileItem, PixmapIcon, PixmapSequenceIcon, draw_text_on_pixmap, get_file_init_icon
from src.utils import format_file_size, get_all_files, get_available_filename, get_cache_path, thumbnailExtractor


# ---------------- View Models ----------------

@dataclass(frozen=True)
class FileViewModel:
    file_path: str
    file_name: str
    file_size_bytes: int
    file_date: float
    label_pos: tuple[int, int]
    label_size: tuple[int, int]
    icon_source: object | None

    @property
    def formatted_size(self) -> str:
        return format_file_size(self.file_size_bytes)

    @property
    def formatted_date(self) -> str:
        return datetime.fromtimestamp(self.file_date).strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class LayoutSnapshot:
    labels_rect: list[list[tuple[tuple[int, int], tuple[int, int], str] | None]]
    content_size: QSize
    horizontal_spacing: int
    max_row: int
    max_col: int


@dataclass
class ActionResult:
    success: bool
    changed_paths: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    notifications: list[str] = field(default_factory=list)
    path_mapping: dict[str, str] = field(default_factory=dict)


# ---------------- State Layer ----------------

class FileGridState:
    def __init__(self):
        # 持有文件墙的核心状态；外部通过 FileShowArea 的 API 间接读写这些数据。
        self._file_paths: list[str] = []
        self._items: dict[str, FileItem] = {}
        self._item_cache: dict[str, FileItem] = {}
        self._selected: set[str] = set()
        self._ctrl_selected: set[str] = set()
        self._visible: set[str] = set()
        self._current_file: Optional[str] = None
        self._hover_file: Optional[str] = None
        self._selection_snapshot: set[str] = set()

    def get_files(self) -> list[str]:
        return self._file_paths.copy()

    def set_files(self, file_paths: list[str]) -> set[str]:
        old_files = set(self._file_paths)
        new_files = set(file_paths)
        removed = old_files - new_files
        self._file_paths = file_paths.copy()
        for file_path in removed:
            self._items.pop(file_path, None)
        self._selected -= removed
        self._ctrl_selected -= removed
        self._visible -= removed
        if self._current_file in removed:
            self._current_file = None
        if self._hover_file in removed:
            self._hover_file = None
        return removed

    def append_files(self, file_paths: list[str]) -> list[str]:
        additions = [path for path in file_paths if path not in self._items]
        self._file_paths.extend(additions)
        return additions

    def remove_files(self, file_paths: list[str]) -> None:
        remove_set = set(file_paths)
        self._file_paths = [path for path in self._file_paths if path not in remove_set]
        for file_path in remove_set:
            self._items.pop(file_path, None)
        self._selected -= remove_set
        self._ctrl_selected -= remove_set
        self._visible -= remove_set
        if self._current_file in remove_set:
            self._current_file = self._file_paths[0] if self._file_paths else None
        if self._hover_file in remove_set:
            self._hover_file = None

    def contains(self, file_path: str) -> bool:
        return file_path in self._items

    def get_item(self, file_path: str) -> FileItem:
        return self._items[file_path]

    def get_item_if_exists(self, file_path: str) -> Optional[FileItem]:
        return self._items.get(file_path)

    def set_item(self, file_path: str, file_item: FileItem) -> None:
        self._items[file_path] = file_item
        self._item_cache[file_path] = file_item

    def get_cached_item(self, file_path: str) -> Optional[FileItem]:
        return self._item_cache.get(file_path)

    def get_items(self) -> dict[str, FileItem]:
        return self._items

    def get_selected_files(self) -> list[str]:
        return [path for path in self._file_paths if path in self._selected]

    def get_selected_set(self) -> set[str]:
        return self._selected.copy()

    def clear_selection(self) -> set[str]:
        previous = self._selected.copy()
        self._selected.clear()
        self._ctrl_selected.clear()
        return previous

    def select_all(self) -> set[str]:
        self._selected = set(self._file_paths)
        return self._selected.copy()

    def is_selected(self, file_path: str) -> bool:
        return file_path in self._selected

    def select_only(self, file_path: Optional[str]) -> tuple[set[str], set[str]]:
        previous = self._selected.copy()
        self._selected.clear()
        if file_path is not None:
            self._selected.add(file_path)
        return previous, self._selected.copy()

    def set_selected(self, file_path: str, selected: bool) -> None:
        if selected:
            self._selected.add(file_path)
        else:
            self._selected.discard(file_path)

    def snapshot_selection(self) -> None:
        self._selection_snapshot = self._selected.copy()

    def get_selection_snapshot(self) -> set[str]:
        return self._selection_snapshot.copy()

    def clear_ctrl_selection(self) -> None:
        self._ctrl_selected.clear()

    def set_ctrl_selection(self, file_paths: set[str]) -> None:
        self._ctrl_selected = file_paths.copy()

    def get_ctrl_selection(self) -> set[str]:
        return self._ctrl_selected.copy()

    def get_current_file(self) -> Optional[str]:
        return self._current_file

    def set_current_file(self, file_path: Optional[str]) -> Optional[str]:
        previous = self._current_file
        if file_path is not None and file_path not in self._items:
            file_path = None
        self._current_file = file_path
        return previous

    def get_hover_file(self) -> Optional[str]:
        return self._hover_file

    def set_hover_file(self, file_path: Optional[str]) -> Optional[str]:
        previous = self._hover_file
        if file_path is not None and file_path not in self._items:
            file_path = None
        self._hover_file = file_path
        return previous

    def get_visible_files(self) -> set[str]:
        return self._visible.copy()

    def set_visible_files(self, file_paths: set[str]) -> None:
        self._visible = file_paths.copy()

    def reorder_files(self, file_paths: list[str]) -> None:
        self._file_paths = file_paths.copy()

    def clear(self) -> None:
        self._file_paths.clear()
        self._items.clear()
        self._selected.clear()
        self._ctrl_selected.clear()
        self._visible.clear()
        self._current_file = None
        self._hover_file = None
        self._selection_snapshot.clear()


# ---------------- Layout Layer ----------------

class FileGridLayoutEngine:
    def compute_layout(
        self,
        file_paths: list[str],
        file_items: dict[str, FileItem],
        area_width: int,
        area_height: int,
        label_width: int,
        label_spacing: int,
        v_scroll_width: int,
        h_scroll_height: int,
    ) -> LayoutSnapshot:
        # 纯布局计算：根据当前可用宽度、标签尺寸和文件名高度，
        # 计算每个文件块的位置，以及滚动区域的内容尺寸。
        total_files = len(file_paths)
        fixed_width = 4 * label_spacing + v_scroll_width
        usable_width = max(label_width, area_width - fixed_width)
        num_columns = max(1, 1 + (usable_width - label_width) // (label_width + label_spacing))
        num_rows = (total_files + num_columns - 1) // num_columns if total_files else 0
        labels_rect = [[None for _ in range(num_columns)] for _ in range(num_rows)]

        if total_files == 0:
            content_width = max(area_width, label_width + fixed_width)
            content_height = max(area_height, 4 * label_spacing + h_scroll_height)
            return LayoutSnapshot(labels_rect, QSize(content_width, content_height), label_spacing, 0, 0)

        if num_columns > total_files or num_columns == 1:
            horizontal_spacing = label_spacing
        else:
            horizontal_spacing = round((usable_width - num_columns * label_width) / num_columns)

        col_width = label_width + horizontal_spacing
        row_height = label_width + label_spacing
        x_offset = 4 * label_spacing
        y_offset = 2 * label_spacing
        x_offsets = [x_offset + col * col_width for col in range(num_columns)]
        y_offsets = [y_offset + row * row_height for row in range(num_rows)]

        index = 0
        name_height_accumulator = 0
        for row in range(max(0, num_rows - 1)):
            max_name_height = 0
            for col in range(num_columns):
                file_path = file_paths[index]
                file_item = file_items[file_path]
                max_name_height = max(max_name_height, file_item.name_height)
                x = x_offsets[col]
                y = y_offsets[row] + name_height_accumulator
                file_item.label_pos = (x, y)
                labels_rect[row][col] = (file_item.label_pos, file_item.label_size, file_path)
                index += 1
            name_height_accumulator += max_name_height

        last_row_cols = total_files - index
        max_name_height = 0
        if num_rows > 0:
            last_row_index = num_rows - 1
            for col in range(last_row_cols):
                file_path = file_paths[index]
                file_item = file_items[file_path]
                max_name_height = max(max_name_height, file_item.name_height)
                x = x_offsets[col]
                y = y_offsets[last_row_index] + name_height_accumulator
                file_item.label_pos = (x, y)
                labels_rect[last_row_index][col] = (file_item.label_pos, file_item.label_size, file_path)
                index += 1
            name_height_accumulator += max_name_height

        max_col = min(num_columns, total_files)
        max_row = num_rows
        content_width = max(area_width, label_width + fixed_width)
        content_height = (
            4 * label_spacing
            + max_row * (label_width + label_spacing)
            + name_height_accumulator
            + h_scroll_height
        )
        return LayoutSnapshot(
            labels_rect=labels_rect,
            content_size=QSize(content_width, content_height),
            horizontal_spacing=horizontal_spacing,
            max_row=max_row,
            max_col=max_col,
        )

    def get_files_in_rect(
        self,
        rect: QRect,
        labels_rect: list[list[tuple[tuple[int, int], tuple[int, int], str] | None]],
        label_width: int,
        label_spacing: int,
        max_row: int,
        max_col: int,
    ) -> set[str]:
        # 用布局快照反查矩形覆盖到的文件集合，
        # 供框选和懒加载共用，避免在 UI 层重复写坐标命中逻辑。
        if not labels_rect or max_row == 0 or max_col == 0:
            return set()

        begin_pos = rect.topLeft()
        end_pos = rect.bottomRight()

        begin_row = begin_pos.y() // (label_width + label_spacing)
        begin_row = max(0, min(begin_row, max_row - 1))
        while begin_row != 0 and labels_rect[begin_row - 1][0][0][1] + labels_rect[begin_row - 1][0][1][1] > begin_pos.y():
            begin_row -= 1
        if labels_rect[begin_row][0][0][1] + labels_rect[begin_row][0][1][1] < begin_pos.y():
            begin_row += 1

        end_row = end_pos.y() // (label_width + label_spacing)
        end_row = max(0, min(end_row, max_row - 1))
        while end_row != 0 and labels_rect[end_row - 1][0][0][1] > end_pos.y():
            end_row -= 1
        if labels_rect[end_row][0][0][1] > end_pos.y():
            end_row -= 1

        begin_col = begin_pos.x() // (label_width + label_spacing)
        begin_col = max(0, min(begin_col, max_col - 1))
        while begin_col != 0 and labels_rect[0][begin_col - 1][0][0] + labels_rect[0][begin_col - 1][1][0] > begin_pos.x():
            begin_col -= 1
        if labels_rect[0][begin_col][0][0] + labels_rect[0][begin_col][1][0] < begin_pos.x():
            begin_col += 1

        end_col = end_pos.x() // (label_width + label_spacing)
        end_col = max(0, min(end_col, max_col - 1))
        while end_col != 0 and labels_rect[0][end_col - 1][0][0] > end_pos.x():
            end_col -= 1
        if labels_rect[0][end_col][0][0] > end_pos.x():
            end_col -= 1

        file_paths: set[str] = set()
        for row in range(begin_row, end_row + 1):
            for col in range(begin_col, end_col + 1):
                label = labels_rect[row][col]
                if label:
                    file_paths.add(label[2])
        return file_paths


# ---------------- Thumbnail Loading ----------------

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


# ---------------- File Actions ----------------

class FileActionService:
    def __init__(self, dict_manage: Optional[DictManage] = None):
        self.dict_manage = dict_manage or DictManage()

    def open_folder(self, file_path: str) -> ActionResult:
        subprocess.Popen(f'explorer /select,"{file_path.replace("/", "\\")}"')
        return ActionResult(success=True, changed_paths=[file_path])

    def copy_or_move_files(
        self,
        file_paths: list[str],
        target_folder: str,
        file_action: str,
        move_tags: bool,
    ) -> ActionResult:
        # 先按路径深度倒序处理，目录移动/复制时优先处理更深层级，
        # 避免父目录先变更后导致子路径映射失效。
        changed_paths: list[str] = []
        errors: list[str] = []
        path_mapping: dict[str, str] = {}

        sorted_paths = sorted(
            file_paths,
            key=lambda path: len(os.path.normpath(path).split(os.path.sep)),
            reverse=True,
        )
        for file_path in sorted_paths:
            if not os.path.exists(file_path):
                continue
            try:
                target_path = self._copy_or_move_single(file_path, target_folder, file_action)
                changed_paths.append(target_path)
                path_mapping[file_path] = target_path
                if move_tags:
                    self.dict_manage.dataAPI.rename_file(file_path, target_path)
                    if os.path.isdir(target_path):
                        self._sync_folder_children(file_path, target_path)
            except Exception as exc:
                errors.append(f"{file_path}: {exc}")

        if changed_paths and move_tags:
            self.dict_manage.notify_observers()
        return ActionResult(
            success=not errors,
            changed_paths=changed_paths,
            errors=errors,
            path_mapping=path_mapping,
        )

    def rename_file(self, file_path: str, new_name: str) -> ActionResult:
        new_file_path = os.path.join(os.path.dirname(file_path), new_name).replace("\\", "/")
        if os.path.exists(new_file_path):
            return ActionResult(success=False, errors=[f"Target path already exists: {new_file_path}"])

        os.rename(file_path, new_file_path)
        self.dict_manage.dataAPI.rename_file(file_path, new_file_path)
        self.dict_manage.notify_observers()
        return ActionResult(success=True, changed_paths=[new_file_path], path_mapping={file_path: new_file_path})

    def delete_files(self, file_paths: list[str], os_delete: bool = False) -> ActionResult:
        errors: list[str] = []
        changed_paths: list[str] = []
        for file_path in file_paths:
            try:
                self.dict_manage.delete_file(file_path, notify=False)
                if os_delete and os.path.exists(file_path):
                    if os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                    else:
                        os.remove(file_path)
                changed_paths.append(file_path)
            except Exception as exc:
                errors.append(f"{file_path}: {exc}")

        if changed_paths:
            self.dict_manage.notify_observers()
        return ActionResult(success=not errors, changed_paths=changed_paths, errors=errors)

    def refresh_file_meta(self, file_paths: list[str]) -> list[tuple[str, int, float]]:
        file_meta_datas: list[tuple[str, int, float]] = []
        for file_path in file_paths:
            stat_info = os.stat(file_path)
            file_meta_datas.append((file_path, stat_info.st_size, stat_info.st_mtime))
        return file_meta_datas

    def repair_files(self, mapping: dict[str, str]) -> ActionResult:
        changed_paths: list[str] = []
        errors: list[str] = []
        for original_path, selected_path in mapping.items():
            try:
                self.dict_manage.dataAPI.rename_file(original_path, selected_path)
                changed_paths.append(selected_path)
            except Exception as exc:
                errors.append(f"{original_path}: {exc}")
        if changed_paths:
            self.dict_manage.notify_observers()
        return ActionResult(success=not errors, changed_paths=changed_paths, errors=errors, path_mapping=mapping.copy())

    def build_repair_candidates(self, missing_file_paths: list[str], folder_path: str) -> tuple[list[list[str]], list[str], list[str]]:
        file_name_to_paths: dict[str, list[str]] = {}
        for root, dirs, files in os.walk(folder_path):
            for item in files + dirs:
                candidate = os.path.join(root, item).replace("\\", "/")
                file_name_to_paths.setdefault(item, []).append(candidate)

        groups: list[list[str]] = []
        titles: list[str] = []
        originals: list[str] = []
        for original_path in missing_file_paths:
            if os.path.exists(original_path):
                continue
            file_name = os.path.basename(original_path)
            groups.append(file_name_to_paths.get(file_name, []))
            titles.append(f"修复: '{file_name}' ({original_path})")
            originals.append(original_path)
        return groups, titles, originals

    def get_available_target_path(self, file_path: str, target_folder: str) -> str:
        target_path = os.path.join(target_folder, os.path.basename(file_path)).replace("\\", "/")
        if os.path.exists(target_path):
            target_path = get_available_filename(target_path)
        return target_path

    def collect_files(self, paths: list[str], accept_folder: bool) -> list[str]:
        file_paths: list[str] = []
        if accept_folder:
            return paths
        for path in paths:
            if os.path.isdir(path):
                file_paths.extend(get_all_files(path))
            else:
                file_paths.append(path)
        return file_paths

    def _copy_or_move_single(self, file_path: str, target_folder: str, file_action: str) -> str:
        target_path = self.get_available_target_path(file_path, target_folder)
        if file_action == "cut":
            shutil.move(file_path, target_path)
        elif file_action == "copy":
            if os.path.isdir(file_path):
                shutil.copytree(file_path, target_path)
            else:
                shutil.copy(file_path, target_path)
        else:
            raise ValueError(f"Unsupported file action: {file_action}")
        return target_path

    def _sync_folder_children(self, old_parent: str, new_parent: str) -> None:
        for file_path in get_all_files(new_parent):
            old_file_path = file_path.replace(new_parent, old_parent)
            self.dict_manage.dataAPI.rename_file(old_file_path, file_path)


# ---------------- Item Factory ----------------

def build_file_item(
    file_path_meta_data: tuple[str, int, float],
    label_width: int,
    image_size: int,
    cached_item: Optional[FileItem] = None,
) -> FileItem:
    file_path = file_path_meta_data[0]
    if cached_item is not None:
        cached_item.specifid = 0
        cached_item.selected = 0
        cached_item.hover = 0
        if cached_item.label_width != label_width:
            cached_item.update_label_size(label_width)
        return cached_item

    file_item = FileItem(file_path, file_path_meta_data[1], file_path_meta_data[2], label_width)
    file_item.icon_source = {"current": get_file_init_icon(file_path, image_size)}
    return file_item
