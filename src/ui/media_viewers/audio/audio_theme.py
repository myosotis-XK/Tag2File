"""Shared visual styling for the desktop audio player."""

APP_BACKGROUND = "#f4f7fb"
PANEL_BACKGROUND = "#f8fbff"
SURFACE = "#ffffff"
BORDER = "#d6e1ec"
BORDER_STRONG = "#bfd0e0"
TEXT = "#243447"
TEXT_MUTED = "#6b7b8c"
PRIMARY = "#3498db"
PRIMARY_DARK = "#2980b9"
PRIMARY_SOFT = "#d8ebff"
CONTROL_BG = "#eef5fb"


SCROLLBAR_STYLE = f"""
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 8px 2px 8px 2px;
    }}
    QScrollBar::handle:vertical {{
        background: #c7d6e5;
        border-radius: 4px;
        min-height: 32px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: #9fb7ce;
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: transparent;
        border: none;
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 10px;
        margin: 2px 8px 2px 8px;
    }}
    QScrollBar::handle:horizontal {{
        background: #c7d6e5;
        border-radius: 4px;
        min-width: 32px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: #9fb7ce;
    }}
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal,
    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {{
        background: transparent;
        border: none;
        width: 0px;
    }}
"""


PLAYER_STYLE = f"""
    QWidget#audio_player_root {{
        background-color: {APP_BACKGROUND};
        color: {TEXT};
        font-family: "Microsoft YaHei", "Segoe UI";
    }}
    QWidget#audio_player_left_card,
    QWidget#audio_player_right_card {{
        background-color: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 14px;
    }}
    QWidget#audio_player_tab_bar {{
        background-color: #edf4fa;
        border: 1px solid {BORDER};
        border-radius: 11px;
    }}
    QSplitter::handle {{
        background-color: #e5edf6;
        margin: 16px 3px;
        border-radius: 2px;
        width: 6px;
    }}
    QLabel#audio_time_label {{
        color: {TEXT_MUTED};
        font-size: 13px;
        font-weight: 500;
        padding: 2px 0px;
    }}
    {SCROLLBAR_STYLE}
"""


ICON_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {CONTROL_BG};
        color: {TEXT};
        border: 1px solid {BORDER_STRONG};
        border-radius: 20px;
        font-size: 19px;
        padding-bottom: 1px;
    }}
    QPushButton:hover {{
        background-color: #e3eff8;
        border-color: #9fbedb;
    }}
    QPushButton:pressed {{
        background-color: #d5e6f5;
    }}
"""


PLAY_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {PRIMARY};
        color: white;
        border: 1px solid {PRIMARY};
        border-radius: 23px;
        font-size: 21px;
        font-weight: 700;
        padding-bottom: 1px;
    }}
    QPushButton:hover {{
        background-color: {PRIMARY_DARK};
        border-color: {PRIMARY_DARK};
    }}
    QPushButton:pressed {{
        background-color: #21618c;
    }}
"""


TAB_BUTTON_STYLE = f"""
    QPushButton {{
        padding: 8px 12px;
        border: none;
        border-radius: 9px;
        background-color: transparent;
        color: #506579;
        font-size: 14px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: #e2edf7;
        color: {TEXT};
    }}
    QPushButton:checked {{
        background-color: {SURFACE};
        color: #1f2d3d;
        border: 1px solid {BORDER};
        font-weight: 700;
    }}
"""


LYRIC_SCROLL_STYLE = f"""
    QScrollArea {{
        background-color: {PANEL_BACKGROUND};
        border: 1px solid {BORDER};
        border-radius: 12px;
    }}
    QScrollArea > QWidget > QWidget {{
        background-color: {PANEL_BACKGROUND};
        border: none;
    }}
    {SCROLLBAR_STYLE}
"""


LYRIC_STYLE = """
    QLabel {
        color: #7b8a99;
        background-color: transparent;
        border: none;
        border-radius: 8px;
        font-size: 18px;
        padding: 3px 10px;
    }
"""


LYRIC_HOVER_STYLE = """
    QLabel {
        color: #2980b9;
        background-color: transparent;
        border: none;
        border-radius: 8px;
        font-size: 18px;
        padding: 3px 10px;
    }
"""


LYRIC_CURRENT_STYLE = """
    QLabel {
        color: #1f6fa5;
        background-color: transparent;
        border: none;
        border-radius: 10px;
        font-size: 19px;
        font-weight: 700;
        padding: 3px 10px;
    }
"""


LIST_PANEL_STYLE = f"""
    QListWidget {{
        border: 1px solid {BORDER};
        border-radius: 12px;
        background-color: {PANEL_BACKGROUND};
        outline: none;
        padding: 6px;
        color: {TEXT};
        selection-background-color: {PRIMARY_SOFT};
    }}
    QListWidget::item {{
        padding: 8px 10px;
        margin: 2px 0px;
        border-radius: 8px;
        border: 1px solid transparent;
    }}
    QListWidget::item:hover {{
        background-color: #edf6fd;
        border-color: #d6e8f8;
    }}
    QListWidget::item:selected {{
        background-color: {PRIMARY_SOFT};
        border-color: #9dc8ea;
        color: #1f2d3d;
    }}
    {SCROLLBAR_STYLE}
"""


QUICK_MARKER_STYLE = f"""
    QWidget#quick_marker_creator {{
        background-color: {PANEL_BACKGROUND};
        border: 1px solid {BORDER};
        border-radius: 12px;
    }}
"""


MARKER_LINE_EDIT_STYLE = f"""
    QLineEdit {{
        background-color: {SURFACE};
        color: {TEXT};
        border: 1px solid {BORDER_STRONG};
        border-radius: 8px;
        padding: 5px 8px;
        selection-background-color: {PRIMARY_SOFT};
    }}
    QLineEdit:focus {{
        border-color: #7ea8d6;
    }}
"""


PRIMARY_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {PRIMARY};
        color: white;
        border: 1px solid {PRIMARY};
        border-radius: 8px;
        padding: 5px 10px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {PRIMARY_DARK};
        border-color: {PRIMARY_DARK};
    }}
    QPushButton:pressed {{
        background-color: #21618c;
    }}
"""


SECONDARY_BUTTON_STYLE = f"""
    QPushButton {{
        background-color: {CONTROL_BG};
        color: #4f6273;
        border: 1px solid {BORDER_STRONG};
        border-radius: 8px;
        padding: 5px 8px;
    }}
    QPushButton:hover {{
        background-color: #dce8f3;
        border-color: #7ea8d6;
    }}
    QPushButton:pressed {{
        background-color: #cfdeee;
    }}
"""


SLIDER_STYLE = f"""
    QSlider::groove:horizontal {{
        height: 8px;
        background: #dfeaf4;
        border-radius: 4px;
    }}
    QSlider::sub-page:horizontal {{
        background: {PRIMARY};
        border-radius: 4px;
    }}
    QSlider::handle:horizontal {{
        background: {SURFACE};
        border: 2px solid {PRIMARY};
        width: 18px;
        height: 18px;
        margin: -6px 0px;
        border-radius: 9px;
    }}
    QSlider::handle:horizontal:hover {{
        border-color: {PRIMARY_DARK};
        background: #f8fbff;
    }}
    QSlider::groove:vertical {{
        width: 8px;
        background: #5c6f82;
        border-radius: 4px;
    }}
    QSlider::sub-page:vertical {{
        background: #5c6f82;
        border-radius: 4px;
    }}
    QSlider::add-page:vertical {{
        background: {PRIMARY};
        border-radius: 4px;
    }}
    QSlider::handle:vertical {{
        background: {SURFACE};
        border: 2px solid {PRIMARY_SOFT};
        width: 18px;
        height: 18px;
        margin: 0px -6px;
        border-radius: 9px;
    }}
"""


TOOLTIP_STYLE = """
    background-color: #314456;
    color: #f8fbff;
    padding: 6px 10px;
    border-radius: 6px;
    font-family: 'Segoe UI', 'Microsoft YaHei';
    font-size: 11px;
"""


VOLUME_POPUP_STYLE = """
    QWidget {
        background-color: rgba(49, 68, 86, 0.96);
        border: 1px solid rgba(216, 235, 255, 0.25);
        border-radius: 12px;
    }
"""
