from PyQt5.QtWidgets import QFrame, QLabel, QLineEdit, QMenu, QPushButton, QScrollArea, QWidget
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt


def build_dialog_qss():
    """
    构建桌面对话框相关控件的统一 QSS。
    """
    return """
        QDialog, QMessageBox, QInputDialog, QFileDialog, QColorDialog {
            background-color: #f4f7fb;
            color: #243447;
        }
        QLabel {
            color: #243447;
            background-color: transparent;
        }
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QListView, QTreeView {
            background-color: #fbfdff;
            color: #243447;
            border: 1px solid #bfd0e0;
            border-radius: 8px;
            padding: 5px 8px;
            selection-background-color: #d8ebff;
            font-size: 14px;
        }
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
            border: 1px solid #7ea8d6;
            background-color: #ffffff;
        }
        QComboBox::drop-down {
            border: none;
            width: 24px;
        }
        QComboBox::down-arrow {
            width: 10px;
            height: 10px;
        }
        QGroupBox {
            color: #243447;
            border: 1px solid #d6e1ec;
            border-radius: 10px;
            margin-top: 10px;
            padding-top: 10px;
            background-color: #f8fbff;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0px 4px;
        }
        QListWidget, QTreeWidget {
            background-color: #fbfdff;
            color: #243447;
            border: 1px solid #bfd0e0;
            border-radius: 10px;
            padding: 6px;
            outline: none;
            font-size: 14px;
        }
        QListWidget::item, QTreeWidget::item {
            padding: 6px 10px;
            margin: 1px 0px;
            border-radius: 6px;
            border: 1px solid transparent;
        }
        QListWidget::item:hover, QTreeWidget::item:hover {
            background-color: #eef5fc;
            border-color: #d9e7f5;
        }
        QListWidget::item:selected, QTreeWidget::item:selected {
            background-color: #d8ebff;
            color: #1f2d3d;
            border-color: #7ea8d6;
        }
        QHeaderView::section {
            background-color: #eef4fa;
            color: #435466;
            border: none;
            border-bottom: 1px solid #d6e1ec;
            padding: 6px 8px;
            font-weight: 600;
        }
        QScrollArea {
            background-color: #f8fbff;
            border: 1px solid #d6e1ec;
            border-radius: 10px;
        }
        QScrollArea > QWidget > QWidget {
            background-color: #f8fbff;
            border: none;
        }
        QDialog QPushButton, QMessageBox QPushButton, QInputDialog QPushButton,
        QFileDialog QPushButton, QColorDialog QPushButton {
            background-color: #f8fbff;
            color: #243447;
            border: 1px solid #bfd0e0;
            border-radius: 6px;
            padding: 3px 8px;
            font-size: 13px;
            min-height: 24px;
        }
        QDialog QPushButton:hover, QMessageBox QPushButton:hover, QInputDialog QPushButton:hover,
        QFileDialog QPushButton:hover, QColorDialog QPushButton:hover {
            background-color: #e7f1fb;
            border-color: #7ea8d6;
        }
        QDialog QPushButton:pressed, QMessageBox QPushButton:pressed, QInputDialog QPushButton:pressed,
        QFileDialog QPushButton:pressed, QColorDialog QPushButton:pressed {
            background-color: #d8e8f8;
        }
        QDialogButtonBox QPushButton {
            min-width: 42px;
            min-height: 24px;
        }
    """


def install_application_style(app):
    """
    为整个应用安装统一的桌面对话框样式。
    """
    existing = app.styleSheet() or ""
    dialog_qss = build_dialog_qss()
    if dialog_qss not in existing:
        app.setStyleSheet(f"{existing}\n{dialog_qss}".strip())
    return app


def _to_qcolor(color):
    return QColor(color) if isinstance(color, str) else QColor(color)


def _is_tag_color_tokens(color):
    return isinstance(color, dict) and "bg_normal" in color and "text_normal" in color


def _get_contrast_text_color(background_color):
    # 依据 HSV 的明暗和饱和度动态调整阈值，让高饱和亮色更早切深字。
    hue, saturation, value, _ = background_color.getHsv()
    if hue < 0:
        hue = 0

    threshold = 145 + saturation * 0.10
    if 35 <= hue <= 200:
        threshold += 8
    elif 220 <= hue <= 320:
        threshold -= 6

    threshold = max(110, min(threshold, 185))
    return QColor("#2f2f2f") if value >= threshold else QColor("#dddddd")


def _get_text_hover_color(color):
    r, g, b = color.red(), color.green(), color.blue()

    r = min(r + 20 + (255 - r) // 3, 255)
    g = min(g + 20 + (255 - g) // 3, 255)
    b = min(b + 20 + (255 - b) // 3, 255)

    r = r + (255 - r) // 16
    g = g + (255 - g) // 16
    b = b + (255 - b) // 16

    return QColor(r, g, b)


def build_tag_color_tokens(color):
    if _is_tag_color_tokens(color):
        return color

    qcolor = _to_qcolor(color)
    bg_hover = qcolor.lighter(110)
    text_on_bg = _get_contrast_text_color(qcolor)

    border_normal = QColor(qcolor)
    border_normal.setHsv(qcolor.hue(), qcolor.saturation(), int(qcolor.value() * 0.7))

    return {
        "bg_normal": qcolor,
        "bg_hover": bg_hover,
        "border_normal": border_normal,
        "border_hover": QColor("#c0c0c0"),
        "text_on_bg_normal": text_on_bg,
        "text_on_bg_hover": text_on_bg,
        "text_normal": qcolor,
        "text_hover": _get_text_hover_color(qcolor),
    }


def build_colored_label_color_styles(color, hover_effect=True):
    """
    生成标签的颜色相关样式，不包含圆角、边距等布局样式。
    """
    tokens = build_tag_color_tokens(color)

    base_styles = [
        f"background-color: {tokens['bg_normal'].name()};",
        f"color: {tokens['text_on_bg_normal'].name()};",
        f"border: 1px solid {tokens['border_normal'].name()};",
    ]
    hover_styles = []
    if hover_effect:
        hover_styles = [
            f"background-color: {tokens['bg_hover'].name()};",
            f"color: {tokens['text_on_bg_hover'].name()};",
            f"border-color: {tokens['border_hover'].name()};",
        ]

    return base_styles, hover_styles


def apply_color_preview_button_style(
    button,
    color,
    border_width=1,
    border_radius=4,
    hover_border_width=None,
):
    """
    给颜色预览按钮应用统一样式：常态显示当前颜色，悬停时只强调边框。
    """
    tokens = build_tag_color_tokens(color)
    hover_border_width = 2 if hover_border_width is None else hover_border_width
    button.setFocusPolicy(Qt.NoFocus)
    button.setStyleSheet(f"""
        QPushButton {{
            background-color: {tokens['bg_normal'].name()};
            border: {border_width}px solid {tokens['border_normal'].name()};
            border-radius: {border_radius}px;
        }}
        QPushButton:hover {{
            border: {hover_border_width}px solid {tokens['border_hover'].name()};
        }}
    """)


def apply_button_style(button, variant="default", size="default"):
    """
    给常规文本按钮应用统一样式，适合管理/查询/清空这类标准操作按钮。
    """
    styles = {
        "default": {
            "bg": "#f8fbff",
            "text": "#243447",
            "border": "#bfd0e0",
            "hover_bg": "#e7f1fb",
            "hover_border": "#7ea8d6",
            "pressed_bg": "#d8e8f8",
            "disabled_bg": "#f3f6f9",
            "disabled_text": "#9aa5b1",
            "disabled_border": "#d3dde7",
        },
        "primary": {
            "bg": "#3498db",
            "text": "#ffffff",
            "border": "#3498db",
            "hover_bg": "#2980b9",
            "hover_border": "#2980b9",
            "pressed_bg": "#21618c",
            "disabled_bg": "#a8d0ef",
            "disabled_text": "#f7fbff",
            "disabled_border": "#a8d0ef",
        },
        "secondary": {
            "bg": "#95a5a6",
            "text": "#ffffff",
            "border": "#95a5a6",
            "hover_bg": "#7f8c8d",
            "hover_border": "#7f8c8d",
            "pressed_bg": "#6c7a7b",
            "disabled_bg": "#c7d0d1",
            "disabled_text": "#f6f8f8",
            "disabled_border": "#c7d0d1",
        },
        "success": {
            "bg": "#27ae60",
            "text": "#ffffff",
            "border": "#27ae60",
            "hover_bg": "#229954",
            "hover_border": "#229954",
            "pressed_bg": "#1e8449",
            "disabled_bg": "#9bd4b3",
            "disabled_text": "#f7fcf9",
            "disabled_border": "#9bd4b3",
        },
        "operator": {
            "bg": "#eaf1f7",
            "text": "#4f6273",
            "border": "#c1d0df",
            "hover_bg": "#dce8f3",
            "hover_border": "#7ea8d6",
            "pressed_bg": "#cfdeee",
            "disabled_bg": "#f3f6f9",
            "disabled_text": "#9aa5b1",
            "disabled_border": "#d6e0e9",
        },
    }

    size_styles = {
        "default": {
            "radius": 6,
            "padding_v": 5,
            "padding_h": 14,
            "font_size": 14,
        },
        "control": {
            "radius": 4,
            "padding_v": 2,
            "padding_h": 10,
            "font_size": 13,
        },
        "operator": {
            "radius": 8,
            "padding_v": 2,
            "padding_h": 10,
            "font_size": 15,
        },
    }

    palette = styles.get(variant, styles["default"])
    metrics = size_styles.get(size, size_styles["default"])
    button.setCursor(Qt.PointingHandCursor)
    button.setFocusPolicy(Qt.NoFocus)
    button.setStyleSheet(f"""
        QPushButton {{
            background-color: {palette['bg']};
            color: {palette['text']};
            border: 1px solid {palette['border']};
            border-radius: {metrics['radius']}px;
            padding: {metrics['padding_v']}px {metrics['padding_h']}px;
            font-size: {metrics['font_size']}px;
        }}
        QPushButton:hover {{
            background-color: {palette['hover_bg']};
            border-color: {palette['hover_border']};
        }}
        QPushButton:pressed {{
            background-color: {palette['pressed_bg']};
        }}
        QPushButton:disabled {{
            background-color: {palette['disabled_bg']};
            color: {palette['disabled_text']};
            border-color: {palette['disabled_border']};
        }}
    """)
    return button


def create_button(text, parent=None, variant="default", fixed_height=30, size="default"):
    """
    创建统一样式的常规文本按钮。
    """
    button = QPushButton(text, parent)
    button.setFixedHeight(fixed_height)
    return apply_button_style(button, variant, size=size)


def create_context_menu(parent=None):
    """
    创建统一样式的上下文菜单，方便全局集中美化。
    """
    menu = QMenu(parent)
    menu.setStyleSheet("""
        QMenu {
            background-color: #ffffff;
            color: #2f2f2f;
            border: 1px solid #c7d0d9;
            padding: 2px 0px;
        }
        QMenu::item {
            padding: 5px 18px 5px 14px;
            margin: 0px 4px;
            color: #2f2f2f;
            background-color: transparent;
        }
        QMenu::item:selected {
            color: #1f2d3d;
            background-color: #d8ebff;
            border-radius: 2px;
        }
        QMenu::indicator {
            width: 8px;
            height: 8px;
            margin-left: 2px;
            margin-right: 4px;
        }
        QMenu::right-arrow {
            margin-right: 2px;
        }
        QMenu::indicator:checked {
            background-color: #1f1f1f;
            border-radius: 4px;
        }
        QMenu::indicator:unchecked {
            background-color: transparent;
        }
        QMenu::separator {
            height: 1px;
            margin: 4px 8px;
            background-color: #e2e8f0;
        }
        QMenu::item:disabled {
            color: #9aa5b1;
        }
    """)
    return menu


def apply_line_edit_style(line_edit, compact=False):
    """
    给普通输入框应用统一的浅色样式。
    """
    radius = 6 if compact else 8
    padding_v = 4 if compact else 5
    padding_h = 8 if compact else 10
    line_edit.setStyleSheet(f"""
        QLineEdit {{
            background-color: #fbfdff;
            color: #243447;
            border: 1px solid #bfd0e0;
            border-radius: {radius}px;
            padding: {padding_v}px {padding_h}px;
            selection-background-color: #d8ebff;
            font-size: 14px;
        }}
        QLineEdit:focus {{
            border: 1px solid #7ea8d6;
            background-color: #ffffff;
        }}
        QLineEdit:disabled {{
            background-color: #f3f6f9;
            color: #9aa5b1;
            border-color: #d3dde7;
        }}
    """)
    return line_edit


def apply_list_widget_style(list_widget, compact=False):
    """
    给列表控件应用统一的浅色面板样式。
    """
    border_radius = 8 if compact else 10
    padding = 4 if compact else 6
    item_padding_v = 4 if compact else 6
    item_padding_h = 8 if compact else 10
    list_widget.setStyleSheet(f"""
        QListWidget {{
            background-color: #fbfdff;
            color: #243447;
            border: 1px solid #bfd0e0;
            border-radius: {border_radius}px;
            padding: {padding}px;
            outline: none;
            font-size: 14px;
        }}
        QListWidget::item {{
            padding: {item_padding_v}px {item_padding_h}px;
            margin: 1px 0px;
            border-radius: 6px;
            border: 1px solid transparent;
        }}
        QListWidget::item:hover {{
            background-color: #eef5fc;
            border-color: #d9e7f5;
        }}
        QListWidget::item:selected {{
            background-color: #d8ebff;
            color: #1f2d3d;
            border-color: #7ea8d6;
        }}
    """)
    return list_widget


def apply_dialog_style(dialog):
    """
    给 QDialog 应用统一的浅色桌面样式。
    """
    dialog.setStyleSheet(build_dialog_qss())
    return dialog


def configure_dialog_button_box(button_box, ok_variant="primary", cancel_variant="default"):
    """
    统一 QDialogButtonBox 的按钮文案和尺寸。
    """
    try:
        from PyQt5.QtWidgets import QDialogButtonBox
    except ImportError:
        return button_box

    ok_button = button_box.button(QDialogButtonBox.Ok)
    if ok_button:
        ok_button.setText("确认")
        ok_button.setMinimumSize(42, 24)
        apply_button_style(ok_button, variant=ok_variant)

    cancel_button = button_box.button(QDialogButtonBox.Cancel)
    if cancel_button:
        cancel_button.setText("取消")
        cancel_button.setMinimumSize(42, 24)
        apply_button_style(cancel_button, variant=cancel_variant)

    return button_box


def apply_panel_style(widget, tone="default", padding=0):
    """
    给容器应用统一的轻量面板样式。
    """
    tones = {
        "default": ("#ffffff", "#d6e1ec"),
        "soft": ("#f8fbff", "#d6e1ec"),
        "muted": ("#f3f7fb", "#d6e1ec"),
    }
    background, border = tones.get(tone, tones["default"])
    if not widget.objectName():
        widget.setObjectName(f"panel_{id(widget)}")
    widget.setStyleSheet(f"""
        QWidget#{widget.objectName()} {{
            background-color: {background};
            border: 1px solid {border};
            border-radius: 10px;
            padding: {padding}px;
        }}
    """)
    return widget


def apply_scroll_area_style(scroll_area, tone="soft", border_radius=10):
    """
    给滚动容器应用统一的浅色面板样式。
    """
    tones = {
        "default": ("#ffffff", "#d6e1ec", "#ffffff"),
        "soft": ("#f8fbff", "#d6e1ec", "#f8fbff"),
        "muted": ("#f3f7fb", "#d6e1ec", "#f3f7fb"),
    }
    background, border, viewport = tones.get(tone, tones["soft"])
    scroll_area.setFrameShape(QFrame.NoFrame)
    scroll_area.setStyleSheet(f"""
        QScrollArea {{
            background-color: {background};
            border: 1px solid {border};
            border-radius: {border_radius}px;
        }}
        QScrollArea > QWidget > QWidget {{
            background-color: {viewport};
            border: none;
        }}
    """)
    return scroll_area


def create_colored_label(text, color, parent=None, hover_effect=True):
    """
    创建带颜色样式的标签
    
    Args:
        text: 标签文本
        color: 颜色值（可以是字符串如'#FF0000'或QColor对象）
        parent: 父组件
        hover_effect: 是否启用悬停效果
    
    Returns:
        QLabel: 配置好样式的标签
    """
    label = QLabel(text, parent)
    
    base_styles, hover_styles = build_colored_label_color_styles(color, hover_effect)

    # 构建样式表
    stylesheet_parts = base_styles + [
        "border-radius: 10px;",
        "padding: 5px 10px;",
        "margin: 3px;",
        "font: 14px;"
    ]
    
    if hover_effect:
        label.setStyleSheet(f"""
            QLabel {{
                {''.join(stylesheet_parts)}
            }}
            QLabel:hover {{
                {''.join(hover_styles)}
            }}
        """)
    else:
        label.setStyleSheet(f"""
            QLabel {{
                {''.join(stylesheet_parts)}
            }}
        """)
    
    label.setCursor(Qt.PointingHandCursor)  # 设置鼠标指针样式
    
    return label
