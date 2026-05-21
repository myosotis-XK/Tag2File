from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from PyQt5.QtCore import QSize

from src.models import FileItem, get_file_init_icon
from src.utils import format_file_size


# ---------------- 视图模型 ----------------

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
