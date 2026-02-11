"""
UI工具模块
提供UI相关的工具函数
"""
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication

def set_application_font():
    font = QFont()
    font.setFamily("Verdana")  # 首选 Verdana
    font.setStyleHint(QFont.SansSerif)  # 如果 Verdana 不可用，使用无衬线字体
    QApplication.setFont(font)
