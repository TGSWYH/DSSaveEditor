# -*- coding: utf-8 -*-
"""QSS 主题: 现代深色 / 浅色。

apply_theme(app, theme) 把对应 QSS 应用到 QApplication。
深色参考常见现代暗色配色: 背景 #1e1e2e, 强调 #7aa2f7, 圆角按钮, 表格高亮。
"""

# 通用字体 (Windows 上微软雅黑好看)
_FONT = "Microsoft YaHei UI, Microsoft YaHei, Segoe UI, 9pt"

_DARK_QSS = f"""
* {{
    font-family: Microsoft YaHei UI, Microsoft YaHei, Segoe UI;
    font-size: 9pt;
    color: #cdd6f4;
}}
QMainWindow, QDialog {{
    background-color: #1e1e2e;
}}
QToolBar {{
    background-color: #181825;
    border: none;
    border-bottom: 1px solid #313244;
    spacing: 4px;
    padding: 6px;
}}
QToolBar QToolButton {{
    background-color: #313244;
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
    color: #cdd6f4;
}}
QToolBar QToolButton:hover {{
    background-color: #45475a;
}}
QToolBar QToolButton:pressed {{
    background-color: #7aa2f7;
    color: #1e1e2e;
}}
QToolBar QToolButton:disabled {{
    color: #585b70;
    background-color: #181825;
}}
QLabel {{
    background: transparent;
    color: #cdd6f4;
}}
QLabel#titleLabel {{
    font-size: 11pt;
    font-weight: 600;
    color: #7aa2f7;
}}
QLabel#hintLabel {{
    color: #7f849c;
}}
QTabWidget::pane {{
    border: 1px solid #313244;
    border-radius: 6px;
    background-color: #1e1e2e;
}}
QTabBar::tab {{
    background-color: #181825;
    color: #7f849c;
    padding: 8px 16px;
    border: 1px solid #313244;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: #313244;
    color: #cdd6f4;
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    background-color: #45475a;
    color: #cdd6f4;
}}
QTableWidget {{
    background-color: #1e1e2e;
    alternate-background-color: #181825;
    gridline-color: rgba(255,255,255,0.06);
    border: 1px solid #313244;
    border-radius: 4px;
    selection-background-color: rgba(122,162,247,0.28);
    selection-color: #ffffff;
    outline: 0;
}}
QTableWidget::item {{
    padding: 4px 8px;
    border: none;
}}
QTableWidget::item:hover {{
    background-color: rgba(122,162,247,0.12);
}}
QTableWidget::item:selected {{
    background-color: rgba(122,162,247,0.28);
    color: #ffffff;
}}
QHeaderView::section {{
    background-color: rgba(255,255,255,0.06);
    color: #cdd6f4;
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid rgba(122,162,247,0.35);
    font-weight: 600;
}}
QHeaderView::section:hover {{
    background-color: rgba(255,255,255,0.10);
}}
QListWidget {{
    background-color: #1e1e2e;
    alternate-background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 4px;
    outline: 0;
}}
QListWidget::item {{
    padding: 4px 8px;
    border: none;
}}
QListWidget::item:hover {{
    background-color: rgba(122,162,247,0.12);
}}
QListWidget::item:selected {{
    background-color: rgba(122,162,247,0.28);
    color: #ffffff;
}}
QListWidget::item:disabled {{
    color: #585b70;
}}
QTreeWidget {{
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 4px;
    outline: 0;
}}
QTreeWidget::item {{
    padding: 4px 6px;
    border: none;
}}
QTreeWidget::item:hover {{
    background-color: rgba(122,162,247,0.12);
}}
QTreeWidget::item:selected {{
    background-color: rgba(122,162,247,0.28);
    color: #ffffff;
}}
QTreeWidget::branch {{
    background-color: transparent;
}}
QCheckBox {{
    color: #cdd6f4;
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid #45475a;
    border-radius: 4px;
    background-color: #181825;
}}
QCheckBox::indicator:hover {{
    border-color: #7aa2f7;
}}
QCheckBox::indicator:checked {{
    background-color: #7aa2f7;
    border-color: #7aa2f7;
}}
QCheckBox:disabled {{
    color: #585b70;
}}
QMessageBox {{
    background-color: #1e1e2e;
}}
QMessageBox QLabel {{
    color: #cdd6f4;
}}
QInputDialog {{
    background-color: #1e1e2e;
}}
QInputDialog QLabel {{
    color: #cdd6f4;
}}
QComboBox {{
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 4px 10px;
    min-height: 22px;
}}
QComboBox:hover {{
    border-color: #7aa2f7;
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: #1e1e2e;
    color: #cdd6f4;
    selection-background-color: #7aa2f7;
    selection-color: #1e1e2e;
    border: 1px solid #313244;
    outline: 0;
}}
QLineEdit, QSpinBox, QPlainTextEdit {{
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 4px 8px;
    selection-background-color: #7aa2f7;
    selection-color: #1e1e2e;
}}
QLineEdit:focus, QSpinBox:focus, QPlainTextEdit:focus {{
    border-color: #7aa2f7;
}}
QPushButton {{
    background-color: #313244;
    color: #cdd6f4;
    border: none;
    border-radius: 6px;
    padding: 6px 16px;
    min-width: 64px;
}}
QPushButton:hover {{
    background-color: #45475a;
}}
QPushButton:pressed {{
    background-color: #7aa2f7;
    color: #1e1e2e;
}}
QPushButton:disabled {{
    color: #585b70;
    background-color: #181825;
}}
QPushButton#primaryBtn {{
    background-color: #7aa2f7;
    color: #1e1e2e;
    font-weight: 600;
}}
QPushButton#primaryBtn:hover {{
    background-color: #89b4fa;
}}
QPushButton#primaryBtn:pressed {{
    background-color: #b4befe;
}}
QPushButton#langBtn {{
    background-color: #313244;
    color: #cdd6f4;
    border: 2px solid #45475a;
    border-radius: 8px;
    padding: 12px 20px;
    font-size: 12pt;
    font-weight: 600;
    min-width: 180px;
    min-height: 56px;
}}
QPushButton#langBtn:hover {{
    border-color: #7aa2f7;
    background-color: #45475a;
    color: #cdd6f4;
}}
QPushButton#langBtn:pressed {{
    background-color: #7aa2f7;
    color: #1e1e2e;
    border-color: #7aa2f7;
}}
QStatusBar {{
    background-color: #181825;
    color: #7f849c;
    border-top: 1px solid #313244;
}}
QStatusBar::item {{ border: none; }}
QScrollBar:vertical {{
    background-color: #181825;
    width: 12px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background-color: #45475a;
    border-radius: 6px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: #585b70;
}}
QScrollBar:horizontal {{
    background-color: #181825;
    height: 12px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background-color: #45475a;
    border-radius: 6px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: #585b70;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    border: none; background: none; width: 0; height: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
}}
QScrollArea {{
    background-color: #1e1e2e;
    border: none;
}}
QGroupBox {{
    border: 1px solid #313244;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
    color: #cdd6f4;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #7aa2f7;
}}
QSplitter::handle {{
    background-color: #313244;
}}
"""

_LIGHT_QSS = f"""
* {{
    font-family: Microsoft YaHei UI, Microsoft YaHei, Segoe UI;
    font-size: 9pt;
    color: #1e1e2e;
}}
QMainWindow, QDialog {{
    background-color: #f5f5fa;
}}
QToolBar {{
    background-color: #e6e6ef;
    border: none;
    border-bottom: 1px solid #cdd0e0;
    spacing: 4px;
    padding: 6px;
}}
QToolBar QToolButton {{
    background-color: #ffffff;
    border: 1px solid #cdd0e0;
    border-radius: 6px;
    padding: 6px 14px;
    color: #1e1e2e;
}}
QToolBar QToolButton:hover {{
    background-color: #eef0f8;
    border-color: #7aa2f7;
}}
QToolBar QToolButton:pressed {{
    background-color: #7aa2f7;
    color: #ffffff;
}}
QToolBar QToolButton:disabled {{
    color: #9ea0b0;
    background-color: #e6e6ef;
}}
QLabel {{ background: transparent; color: #1e1e2e; }}
QLabel#titleLabel {{
    font-size: 11pt; font-weight: 600; color: #3a5bbf;
}}
QLabel#hintLabel {{ color: #6b6f80; }}
QTabWidget::pane {{
    border: 1px solid #cdd0e0;
    border-radius: 6px;
    background-color: #ffffff;
}}
QTabBar::tab {{
    background-color: #e6e6ef;
    color: #6b6f80;
    padding: 8px 16px;
    border: 1px solid #cdd0e0;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: #ffffff;
    color: #1e1e2e;
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    background-color: #d8dae8;
    color: #1e1e2e;
}}
QTableWidget {{
    background-color: #ffffff;
    alternate-background-color: #f5f5fa;
    gridline-color: rgba(0,0,0,0.06);
    border: 1px solid #cdd0e0;
    border-radius: 4px;
    selection-background-color: rgba(122,162,247,0.28);
    selection-color: #1e1e2e;
    outline: 0;
}}
QTableWidget::item {{ padding: 4px 8px; border: none; }}
QTableWidget::item:hover {{
    background-color: rgba(122,162,247,0.12);
}}
QTableWidget::item:selected {{
    background-color: rgba(122,162,247,0.28); color: #1e1e2e;
}}
QHeaderView::section {{
    background-color: rgba(0,0,0,0.05);
    color: #1e1e2e;
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid rgba(122,162,247,0.45);
    font-weight: 600;
}}
QHeaderView::section:hover {{ background-color: rgba(0,0,0,0.08); }}
QListWidget {{
    background-color: #ffffff;
    alternate-background-color: #f5f5fa;
    color: #1e1e2e;
    border: 1px solid #cdd0e0;
    border-radius: 4px;
    outline: 0;
}}
QListWidget::item {{
    padding: 4px 8px;
    border: none;
}}
QListWidget::item:hover {{
    background-color: rgba(122,162,247,0.12);
}}
QListWidget::item:selected {{
    background-color: rgba(122,162,247,0.28);
    color: #1e1e2e;
}}
QListWidget::item:disabled {{
    color: #9ea0b0;
}}
QTreeWidget {{
    background-color: #ffffff;
    color: #1e1e2e;
    border: 1px solid #cdd0e0;
    border-radius: 4px;
    outline: 0;
}}
QTreeWidget::item {{
    padding: 4px 6px;
    border: none;
}}
QTreeWidget::item:hover {{
    background-color: rgba(122,162,247,0.12);
}}
QTreeWidget::item:selected {{
    background-color: rgba(122,162,247,0.28);
    color: #1e1e2e;
}}
QTreeWidget::branch {{
    background-color: transparent;
}}
QCheckBox {{
    color: #1e1e2e;
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid #cdd0e0;
    border-radius: 4px;
    background-color: #ffffff;
}}
QCheckBox::indicator:hover {{
    border-color: #7aa2f7;
}}
QCheckBox::indicator:checked {{
    background-color: #7aa2f7;
    border-color: #7aa2f7;
}}
QCheckBox:disabled {{
    color: #9ea0b0;
}}
QMessageBox {{
    background-color: #f5f5fa;
}}
QMessageBox QLabel {{
    color: #1e1e2e;
}}
QInputDialog {{
    background-color: #f5f5fa;
}}
QInputDialog QLabel {{
    color: #1e1e2e;
}}
QComboBox {{
    background-color: #ffffff;
    color: #1e1e2e;
    border: 1px solid #cdd0e0;
    border-radius: 6px;
    padding: 4px 10px;
    min-height: 22px;
}}
QComboBox:hover {{ border-color: #7aa2f7; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background-color: #ffffff;
    color: #1e1e2e;
    selection-background-color: #7aa2f7;
    selection-color: #ffffff;
    border: 1px solid #cdd0e0;
    outline: 0;
}}
QLineEdit, QSpinBox, QPlainTextEdit {{
    background-color: #ffffff;
    color: #1e1e2e;
    border: 1px solid #cdd0e0;
    border-radius: 6px;
    padding: 4px 8px;
    selection-background-color: #7aa2f7;
    selection-color: #ffffff;
}}
QLineEdit:focus, QSpinBox:focus, QPlainTextEdit:focus {{
    border-color: #7aa2f7;
}}
QPushButton {{
    background-color: #ffffff;
    color: #1e1e2e;
    border: 1px solid #cdd0e0;
    border-radius: 6px;
    padding: 6px 16px;
    min-width: 64px;
}}
QPushButton:hover {{ border-color: #7aa2f7; }}
QPushButton:pressed {{ background-color: #7aa2f7; color: #ffffff; }}
QPushButton:disabled {{ color: #9ea0b0; background-color: #e6e6ef; }}
QPushButton#primaryBtn {{
    background-color: #7aa2f7; color: #ffffff; border: none; font-weight: 600;
}}
QPushButton#primaryBtn:hover {{ background-color: #89b4fa; }}
QPushButton#primaryBtn:pressed {{ background-color: #3a5bbf; }}
QPushButton#langBtn {{
    background-color: #ffffff; color: #1e1e2e;
    border: 2px solid #cdd0e0; border-radius: 8px;
    padding: 12px 20px; font-size: 12pt; font-weight: 600;
    min-width: 180px; min-height: 56px;
}}
QPushButton#langBtn:hover {{ border-color: #7aa2f7; background-color: #f0f4ff; color: #1e1e2e; }}
QPushButton#langBtn:pressed {{ background-color: #7aa2f7; color: #ffffff; border-color: #7aa2f7; }}
QStatusBar {{
    background-color: #e6e6ef; color: #6b6f80;
    border-top: 1px solid #cdd0e0;
}}
QStatusBar::item {{ border: none; }}
QScrollBar:vertical {{
    background-color: #f5f5fa; width: 12px; border: none;
}}
QScrollBar::handle:vertical {{
    background-color: #cdd0e0; border-radius: 6px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background-color: #9ea0b0; }}
QScrollBar:horizontal {{
    background-color: #f5f5fa; height: 12px; border: none;
}}
QScrollBar::handle:horizontal {{
    background-color: #cdd0e0; border-radius: 6px; min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background-color: #9ea0b0; }}
QScrollBar::add-line, QScrollBar::sub-line {{
    border: none; background: none; width: 0; height: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QScrollArea {{ background-color: #ffffff; border: none; }}
QGroupBox {{
    border: 1px solid #cdd0e0; border-radius: 6px;
    margin-top: 10px; padding-top: 10px; color: #1e1e2e;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #3a5bbf;
}}
QSplitter::handle {{ background-color: #cdd0e0; }}
"""


def apply_theme(app, theme):
    """把主题 QSS 应用到 QApplication"""
    qss = _DARK_QSS if theme == "dark" else _LIGHT_QSS
    app.setStyleSheet(qss)
