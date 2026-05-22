import os
import shutil
import subprocess
import ctypes
from ctypes import wintypes
from typing import Optional

from src.core.DictManage import DictManage
from src.utils import get_all_files, get_available_filename

from .file_grid_models import ActionResult


# ---------------- 文件操作 ----------------

class FileActionService:
    def __init__(self, dict_manage: Optional[DictManage] = None):
        self.dict_manage = dict_manage or DictManage()

    def open_folder(self, file_path: str) -> ActionResult:
        normalized_path = os.path.normpath(file_path)
        try:
            if os.name == "nt" and self._open_folder_and_select_windows(normalized_path):
                return ActionResult(success=True, changed_paths=[file_path])
        except Exception:
            pass
        subprocess.Popen(["explorer.exe", "/select,", normalized_path])
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
            self.dict_manage.fileChanged.emit(
                "bulk_renamed",
                {"path_mapping": path_mapping.copy(), "file_paths": list(path_mapping.values())},
            )
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
        self.dict_manage.rename_file(file_path, new_file_path)
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
            self.dict_manage.fileChanged.emit("deleted", {"file_paths": list(changed_paths)})
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
            self.dict_manage.fileChanged.emit(
                "bulk_renamed",
                {"path_mapping": mapping.copy(), "file_paths": list(changed_paths)},
            )
        return ActionResult(
            success=not errors,
            changed_paths=changed_paths,
            errors=errors,
            path_mapping=mapping.copy(),
        )

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

    def _open_folder_and_select_windows(self, file_path: str) -> bool:
        shell32 = ctypes.windll.shell32
        ole32 = ctypes.windll.ole32
        pidl = ctypes.c_void_p()
        attrs = wintypes.DWORD()

        # 让 Shell 自己完成“打开目录并选中文件”，比重复拉起 explorer 更稳。
        result = shell32.SHParseDisplayName(
            ctypes.c_wchar_p(file_path),
            None,
            ctypes.byref(pidl),
            0,
            ctypes.byref(attrs),
        )
        if result != 0 or not pidl.value:
            return False

        try:
            result = shell32.SHOpenFolderAndSelectItems(pidl, 0, None, 0)
            return result == 0
        finally:
            ole32.CoTaskMemFree(pidl)
