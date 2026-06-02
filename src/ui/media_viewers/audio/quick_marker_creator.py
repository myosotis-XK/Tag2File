from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QColorDialog,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.ui.components.preset_selector_dialog import PresetSelectorDialog
from src.ui.components.style_utils import apply_color_preview_button_style
from src.ui.components.time_input import TimeInput
from src.ui.ui_text import AudioMarkerText, CommonText

from .audio_theme import (
    MARKER_LINE_EDIT_STYLE,
    PRIMARY_BUTTON_STYLE,
    QUICK_MARKER_STYLE,
    SECONDARY_BUTTON_STYLE,
)
from .marker_store import MarkerStore


class QuickMarkerCreator(QWidget):
    marker_create_requested = pyqtSignal(dict)

    def __init__(self, audio_file_path=None, parent=None):
        super().__init__(parent)
        self.audio_file_path = audio_file_path
        self.current_color = "#3498db"
        self.selected_preset_id = None
        self.marker_store = MarkerStore()
        self.init_ui()

    def init_ui(self):
        self.setObjectName("quick_marker_creator")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)
        self.setStyleSheet(QUICK_MARKER_STYLE)

        time_layout = QHBoxLayout()
        time_layout.setSpacing(8)

        self.start_time_input = TimeInput()
        time_layout.addWidget(self.start_time_input)

        separator_label = QLabel("-")
        separator_label.setAlignment(Qt.AlignCenter)
        separator_label.setStyleSheet("""
            color: #7f8c8d;
            font-weight: bold;
            font-size: 14px;
            background-color: transparent;
        """)
        time_layout.addWidget(separator_label)

        self.end_time_input = TimeInput()
        time_layout.addWidget(self.end_time_input)
        time_layout.addStretch()

        self.create_btn = QPushButton(self.tr(AudioMarkerText.CREATE))
        self.create_btn.setFixedWidth(54)
        self.create_btn.setFocusPolicy(Qt.NoFocus)
        self.create_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.create_btn.clicked.connect(self.validate_and_create)
        time_layout.addWidget(self.create_btn)
        main_layout.addLayout(time_layout)

        control_layout = QHBoxLayout()
        control_layout.setSpacing(5)

        self.preset_btn = QPushButton(self.tr(AudioMarkerText.PRESET))
        self.preset_btn.setFixedWidth(44)
        self.preset_btn.setFocusPolicy(Qt.NoFocus)
        self.preset_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.preset_btn.clicked.connect(self.show_preset_menu)
        control_layout.addWidget(self.preset_btn)

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(24, 24)
        self.color_btn.clicked.connect(self.choose_color)
        control_layout.addWidget(self.color_btn)
        self.update_color_button()

        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText(self.tr(AudioMarkerText.NOTE_PLACEHOLDER))
        self.label_input.setStyleSheet(MARKER_LINE_EDIT_STYLE)
        control_layout.addWidget(self.label_input)

        self.clear_btn = QPushButton(self.tr(CommonText.CLEAR))
        self.clear_btn.setFixedWidth(50)
        self.clear_btn.setFocusPolicy(Qt.NoFocus)
        self.clear_btn.setStyleSheet(SECONDARY_BUTTON_STYLE)
        self.clear_btn.clicked.connect(self.clear_all)
        control_layout.addWidget(self.clear_btn)
        main_layout.addLayout(control_layout)

    def update_color_button(self):
        apply_color_preview_button_style(self.color_btn, self.current_color)

    def set_audio_file_path(self, path, duration_ms=None):
        self.audio_file_path = path
        if duration_ms is not None:
            self.start_time_input.set_max_duration(duration_ms)
            self.end_time_input.set_max_duration(duration_ms)

    def show_preset_menu(self):
        presets = self.marker_store.get_preset_rows()
        if not presets:
            QMessageBox.information(self, self.tr(CommonText.INFO), self.tr(AudioMarkerText.NO_PRESETS))
            return

        dialog = PresetSelectorDialog(
            presets=presets,
            current_preset_id=self.selected_preset_id,
            parent=self,
        )
        dialog.move(self.preset_btn.mapToGlobal(self.preset_btn.rect().bottomLeft()))

        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_selected_data()
            if data:
                self.on_preset_selected(data['id'], data['color'], data['name'])

    def on_preset_selected(self, preset_id, color, name):
        self.current_color = color
        self.selected_preset_id = preset_id
        self.update_color_button()
        self.label_input.setText(name)

    def choose_color(self):
        color = QColorDialog.getColor(QColor(self.current_color), self, self.tr(AudioMarkerText.CHOOSE_MARKER_COLOR))
        if color.isValid():
            self.current_color = color.name()
            self.selected_preset_id = None
            self.update_color_button()

    def clear_all(self):
        self.start_time_input.clear()
        self.end_time_input.clear()
        self.label_input.clear()
        self.current_color = "#3498db"
        self.selected_preset_id = None
        self.update_color_button()

    def validate_and_create(self):
        if not self.audio_file_path:
            QMessageBox.warning(self, self.tr(CommonText.ERROR), self.tr(AudioMarkerText.AUDIO_NOT_LOADED))
            return

        start_ms = self.start_time_input.get_milliseconds()
        end_ms = self.end_time_input.get_milliseconds()
        if start_ms is None and end_ms is None:
            QMessageBox.warning(self, self.tr(CommonText.ERROR), self.tr(AudioMarkerText.ENTER_AT_LEAST_ONE_TIME))
            return

        label = self.label_input.text().strip() or self.tr(AudioMarkerText.UNNAMED_MARKER)

        if end_ms is None:
            marker_data = {
                'type': 0,
                'time': start_ms if start_ms is not None else end_ms,
                'label': label,
                'color': self.current_color,
                'preset_id': self.selected_preset_id,
            }
        else:
            if start_ms is None:
                start_ms = 0
            if end_ms < start_ms:
                QMessageBox.warning(self, self.tr(CommonText.ERROR), self.tr(AudioMarkerText.END_BEFORE_START))
                return
            marker_data = {
                'type': 1,
                'start': start_ms,
                'end': end_ms,
                'label': label,
                'color': self.current_color,
                'preset_id': self.selected_preset_id,
            }

        self.marker_create_requested.emit(marker_data)
