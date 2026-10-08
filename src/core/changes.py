"""一次已提交的数据操作产生的变更，供桌面端和 Web 共用。"""

from dataclasses import dataclass, field
import os


def normalize_db_path(path: str) -> str:
    return os.path.normcase(os.path.abspath(path)).replace("\\", "/")


@dataclass
class TagbaseChanges:
    """成功提交后发布的快照；空变更不发通知。

    added/removed_relations 按标签记录实际增删的路径。
    added/removed_file_paths 表示标签库中的文件记录增删（影响补集查询），
    不表示磁盘文件增删；文件本身的操作另由 file_events 描述。
    missing_file_paths 记录宽松请求中忽略的未入库路径，不产生通知。
    """

    db_path: str
    tag_events: list[tuple[str, dict]] = field(default_factory=list)
    file_events: list[tuple[str, dict]] = field(default_factory=list)
    added_relations: dict[str, list[str]] = field(default_factory=dict)
    removed_relations: dict[str, list[str]] = field(default_factory=dict)
    added_file_paths: list[str] = field(default_factory=list)
    removed_file_paths: list[str] = field(default_factory=list)
    missing_file_paths: list[str] = field(default_factory=list)

    def merge(self, other: "TagbaseChanges") -> None:
        if self.db_path != other.db_path:
            raise ValueError("不能合并不同标签库的变更")
        self.tag_events.extend(other.tag_events)
        self.file_events.extend(other.file_events)
        for target, source in (
            (self.added_relations, other.added_relations),
            (self.removed_relations, other.removed_relations),
        ):
            for tag, paths in source.items():
                target.setdefault(tag, []).extend(paths)
        self.added_file_paths.extend(other.added_file_paths)
        self.removed_file_paths.extend(other.removed_file_paths)
        self.missing_file_paths.extend(other.missing_file_paths)

    def relation_notification(self):
        """关系通知包含库路径、受影响标签/文件及精确的增删映射。"""
        if not (self.added_relations or self.removed_relations
                or self.added_file_paths or self.removed_file_paths):
            return None
        added = {tag: list(dict.fromkeys(paths)) for tag, paths in self.added_relations.items()}
        removed = {tag: list(dict.fromkeys(paths)) for tag, paths in self.removed_relations.items()}
        paths = set(self.added_file_paths) | set(self.removed_file_paths)
        for relation in (added, removed):
            for values in relation.values():
                paths.update(values)
        action = "changed" if added and removed else "added" if added else "removed"
        return action, {
            "db_path": self.db_path,
            "tags": sorted(set(added) | set(removed)),
            "file_paths": sorted(paths),
            "added": added,
            "removed": removed,
            "added_file_paths": list(dict.fromkeys(self.added_file_paths)),
            "removed_file_paths": list(dict.fromkeys(self.removed_file_paths)),
        }
