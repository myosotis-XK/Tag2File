from typing import Optional

from src.models import FileItem


# ---------------- 状态层 ----------------

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
        self._selection_snapshot -= removed
        if self._current_file in removed:
            self._current_file = None
        if self._hover_file in removed:
            self._hover_file = None
        return removed

    def get_item(self, file_path: str) -> Optional[FileItem]:
        return self._items[file_path]

    def get_item_if_exists(self, file_path: str) -> Optional[FileItem]:
        return self._items.get(file_path)

    def get_cached_item(self, file_path: str) -> Optional[FileItem]:
        return self._item_cache.get(file_path)

    def set_item(self, file_path: str, file_item: FileItem) -> None:
        self._items[file_path] = file_item
        self._item_cache[file_path] = file_item

    def get_items(self) -> dict[str, FileItem]:
        return self._items

    def contains(self, file_path: str) -> bool:
        return file_path in self._items

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

    def clear_selection(self) -> set[str]:
        previous = self._selected.copy()
        self._selected.clear()
        self._ctrl_selected.clear()
        return previous

    def get_selected_files(self) -> list[str]:
        return [path for path in self._file_paths if path in self._selected]

    def get_selected_set(self) -> set[str]:
        return self._selected.copy()

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
