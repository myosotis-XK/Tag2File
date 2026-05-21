from PyQt5.QtCore import QRect, QSize

from src.models import FileItem

from .file_grid_models import LayoutSnapshot


# ---------------- 布局层 ----------------

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
        content_height = 4 * label_spacing + max_row * (label_width + label_spacing) + name_height_accumulator + h_scroll_height
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
