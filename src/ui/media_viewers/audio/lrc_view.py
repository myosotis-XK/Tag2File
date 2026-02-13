import os
import re
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea
from PyQt5.QtCore import Qt

class LrcView(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setAlignment(Qt.AlignCenter)
        self.setWidget(self.container)
        self.labels, self.lyrics_data, self.current_index = [], [], -1

    def load_lrc(self, file_path):
        self.clear()
        if not os.path.exists(file_path):
            return

        # 支持多种歌词格式: [mm:ss.ms], [mm:ss], [hh:mm:ss.ms]
        patterns = [
            re.compile(r'\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)'),  # [mm:ss.ms]
            re.compile(r'\[(\d{2}):(\d{2})\](.*)'),             # [mm:ss]
            re.compile(r'\[(\d{2}):(\d{2}):(\d{2})\.(\d{2,3})\](.*)'),  # [hh:mm:ss.ms]
        ]

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    matched = False
                    # 尝试第一种格式 [mm:ss.ms]
                    match = patterns[0].search(line)
                    if match:
                        m, s, ms, text = match.groups()
                        total_ms = int(m)*60000 + int(s)*1000 + int(ms.ljust(3, '0')[:3])
                        matched = True
                    else:
                        # 尝试第二种格式 [mm:ss]
                        match = patterns[1].search(line)
                        if match:
                            m, s, text = match.groups()
                            total_ms = int(m)*60000 + int(s)*1000
                            matched = True
                        else:
                            # 尝试第三种格式 [hh:mm:ss.ms]
                            match = patterns[2].search(line)
                            if match:
                                h, m, s, ms, text = match.groups()
                                total_ms = int(h)*3600000 + int(m)*60000 + int(s)*1000 + int(ms.ljust(3, '0')[:3])
                                matched = True

                    if matched and text.strip():
                        lbl = QLabel(text.strip())
                        lbl.setAlignment(Qt.AlignCenter)
                        lbl.setStyleSheet("color: gray; font-size: 14px;")
                        self.layout.addWidget(lbl)
                        self.labels.append(lbl)
                        self.lyrics_data.append((total_ms, text.strip()))
        except (UnicodeDecodeError, IOError) as e:
            print(f"歌词加载失败: {e}")
        except Exception as e:
            print(f"歌词解析错误: {e}")

    def update_position(self, ms):
        idx = -1
        for i, (t, _) in enumerate(self.lyrics_data):
            if t <= ms: idx = i
            else: break
        # 只在索引真正改变时才更新样式，优化性能
        if idx != self.current_index:
            if self.current_index != -1 and self.current_index < len(self.labels):
                self.labels[self.current_index].setStyleSheet("color: gray; font-size: 14px;")
            if idx != -1 and idx < len(self.labels):
                self.labels[idx].setStyleSheet("color: #3498db; font-weight: bold; font-size: 18px;")
                self.ensureWidgetVisible(self.labels[idx], 150, 150)
            self.current_index = idx

    def clear(self):
        for i in reversed(range(self.layout.count())):
            self.layout.itemAt(i).widget().setParent(None)
        self.labels, self.lyrics_data, self.current_index = [], [], -1