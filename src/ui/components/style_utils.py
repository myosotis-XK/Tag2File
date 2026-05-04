# src/ui/components/style_utils.py
from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt


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
    if isinstance(color, str):
        qcolor = QColor(color)
    else:
        qcolor = color
    
    label = QLabel(text, parent)
    
    # 计算背景色和边框色
    bg_color = qcolor.name()
    darker_color = QColor(qcolor)
    darker_color.setHsv(qcolor.hue(), qcolor.saturation(), int(qcolor.value() * 0.7))
    border_color = darker_color.name()
    
    # 构建样式表
    stylesheet_parts = [
        f"background-color: {bg_color};",
        "color: #333333;",
        f"border: 1px solid {border_color};",
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
                background-color: {qcolor.lighter(110).name()};
                border-color: #c0c0c0;
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
