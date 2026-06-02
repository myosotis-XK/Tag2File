from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QColorDialog,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QGroupBox
)

from src.ui.components.preset_selector import PresetSelector
from src.ui.components.style_utils import apply_color_preview_button_style, create_button
from src.ui.components.time_input import TimeInput
from src.ui.ui_text import AudioMarkerText, CommonText, PresetSelectorText


class MarkerEditDialog(QDialog):
    def __init__(self, marker_data=None, presets=None, max_duration_ms=None, parent=None):
        super().__init__(parent)
        self.marker_data = marker_data or {}
        self.presets = presets or []
        self.current_color = self.marker_data.get('color', '#3498db')
        self.selected_preset_id = self.marker_data.get('preset_id')
        self.max_duration_ms = max_duration_ms

        self.setWindowTitle(self.tr(AudioMarkerText.EDIT_MARKER) if marker_data else self.tr(AudioMarkerText.CREATE_MARKER))
        self.resize(450, 450)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        if self.presets:
            self.preset_selector = PresetSelector(title=self.tr(PresetSelectorText.PRESET_TYPE), parent=self)
            self.preset_selector.load_presets(self.presets)
            self.preset_selector.preset_selected.connect(self.on_preset_selected)
            layout.addWidget(self.preset_selector)

        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel(self.tr(AudioMarkerText.COLOR)))

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(60, 30)
        self.color_btn.clicked.connect(self.choose_color)
        color_layout.addWidget(self.color_btn)

        self.color_label = QLabel(self.current_color)
        self.color_label.setStyleSheet("color: #555; font-family: monospace;")
        color_layout.addWidget(self.color_label)
        color_layout.addStretch()
        layout.addLayout(color_layout)
        self._update_color_button()

        layout.addWidget(QLabel(self.tr(AudioMarkerText.NOTE_CONTENT)))
        self.text_edit = QTextEdit()
        self.text_edit.setMaximumHeight(100)
        self.text_edit.setPlaceholderText(self.tr(AudioMarkerText.NOTE_PLACEHOLDER))
        self.text_edit.setPlainText(self.marker_data.get('label', ''))
        layout.addWidget(self.text_edit)

        time_group = QGroupBox(self.tr(AudioMarkerText.TIME_SETTINGS))
        time_layout = QVBoxLayout()
        time_layout.setSpacing(10)

        time_input_layout = QHBoxLayout()
        time_input_layout.setSpacing(8)
        start_label = QLabel(self.tr(AudioMarkerText.START))
        start_label.setFixedWidth(40)
        time_input_layout.addWidget(start_label)

        self.start_time_input = TimeInput(max_duration_ms=self.max_duration_ms)
        time_input_layout.addWidget(self.start_time_input)

        separator = QLabel("-")
        separator.setAlignment(Qt.AlignCenter)
        separator.setStyleSheet("color: #7f8c8d; font-weight: bold; font-size: 14px;")
        time_input_layout.addWidget(separator)

        end_label = QLabel(self.tr(AudioMarkerText.END))
        end_label.setFixedWidth(40)
        time_input_layout.addWidget(end_label)

        self.end_time_input = TimeInput(max_duration_ms=self.max_duration_ms)
        time_input_layout.addWidget(self.end_time_input)
        time_input_layout.addStretch()
        time_layout.addLayout(time_input_layout)

        tip_label = QLabel(self.tr(AudioMarkerText.TIME_TIP))
        tip_label.setWordWrap(True)
        tip_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        time_layout.addWidget(tip_label)
        time_group.setLayout(time_layout)
        layout.addWidget(time_group)

        if self.marker_data.get('type') == 0:
            self.start_time_input.set_from_milliseconds(self.marker_data.get('time', 0))
        elif self.marker_data:
            self.start_time_input.set_from_milliseconds(self.marker_data.get('start', 0))
            self.end_time_input.set_from_milliseconds(self.marker_data.get('end', 0))

        layout.addStretch()

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = create_button(self.tr(CommonText.CANCEL))
        cancel_btn.setMinimumWidth(80)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = create_button(self.tr(CommonText.SAVE), variant="primary")
        save_btn.setMinimumWidth(80)
        save_btn.clicked.connect(self.accept)
        button_layout.addWidget(save_btn)
        layout.addLayout(button_layout)

    def _update_color_button(self):
        apply_color_preview_button_style(self.color_btn, self.current_color)
        self.color_label.setText(self.current_color)

    def on_preset_selected(self, preset_id, color, name):
        self.current_color = color
        self.selected_preset_id = preset_id
        self._update_color_button()
        self.text_edit.setPlainText(name)

    def choose_color(self):
        color = QColorDialog.getColor(QColor(self.current_color), self, self.tr(AudioMarkerText.CHOOSE_MARKER_COLOR))
        if color.isValid():
            self.current_color = color.name()
            self._update_color_button()
            self.selected_preset_id = None

    def accept(self):
        start_ms = self.start_time_input.get_milliseconds()
        end_ms = self.end_time_input.get_milliseconds()

        if start_ms is None and end_ms is None:
            QMessageBox.warning(self, self.tr(CommonText.ERROR), self.tr(AudioMarkerText.ENTER_AT_LEAST_ONE_TIME))
            return

        if end_ms is not None:
            if start_ms is None:
                start_ms = 0
            if end_ms < start_ms:
                QMessageBox.warning(self, self.tr(CommonText.ERROR), self.tr(AudioMarkerText.END_BEFORE_START))
                return

        super().accept()

    def get_data(self):
        start_ms = self.start_time_input.get_milliseconds()
        end_ms = self.end_time_input.get_milliseconds()
        label = self.text_edit.toPlainText().strip()

        if end_ms is None:
            return {
                'type': 0,
                'time': start_ms if start_ms is not None else 0,
                'label': label,
                'color': self.current_color,
                'preset_id': self.selected_preset_id,
            }

        if start_ms is None:
            start_ms = 0

        return {
            'type': 1,
            'start': start_ms,
            'end': end_ms,
            'label': label,
            'color': self.current_color,
            'preset_id': self.selected_preset_id,
        }
