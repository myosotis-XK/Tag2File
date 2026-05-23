# src/ui/components/style_utils.py
from PyQt5.QtWidgets import QLabel, QMenu, QPushButton
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt


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
