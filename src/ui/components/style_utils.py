# src/ui/components/style_utils.py
from PyQt5.QtWidgets import QLabel
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
