# -*- coding: utf-8 -*-
"""通用 UI 辅助: 卡片样式 _CARD_QSS + 卡片容器 make_card + 清空布局 _clear_layout。

从 ui_main / ui_quest 拆出, 各页面 (overview/character/equipment/quest/tools) 复用。
ui_quest 以别名 _make_card 使用 make_card。
另含启动免责声明对话框 DisclaimerDialog (main.py 启动流程调用)。
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QDialog, QPushButton,
)

from . import i18n


def make_card(title_text):
    """创建卡片容器 QFrame (objectName=card), 返回 (frame, layout)。"""
    frame = QFrame()
    frame.setObjectName("card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(16, 12, 16, 14)
    lay.setSpacing(8)
    if title_text:
        title = QLabel(str(title_text))
        title.setObjectName("cardTitle")
        lay.addWidget(title)
    return frame, lay


def _clear_layout(layout):
    if layout is None:
        return
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.deleteLater()
        else:
            _clear_layout(item.layout())


# ============================================================
# 启动免责声明对话框
# ============================================================
class DisclaimerDialog(QDialog):
    """启动免责声明: 展示免责声明 + 免费声明, 点"我已了解"才进入主界面。

    每次启动必看, 防止盗用者隐藏。冒烟模式 (smoke) 下由 main() 跳过。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(str(i18n.tr("disclaimer.title")))
        self.setModal(True)
        self.setMinimumWidth(460)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 18)
        lay.setSpacing(12)

        # 标题 (加粗主题蓝)
        title_lbl = QLabel(str(i18n.tr("disclaimer.title")))
        title_lbl.setStyleSheet("font-size: 13pt; font-weight: 700; color: #7aa2f7;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title_lbl)

        # 免责声明段
        disc_lbl = QLabel(str(i18n.tr("disclaimer.disclaimer")))
        disc_lbl.setWordWrap(True)
        disc_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(disc_lbl)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: rgba(122,162,247,0.35); background: rgba(122,162,247,0.35);")
        lay.addWidget(line)

        # 免费声明段
        free_lbl = QLabel(str(i18n.tr("disclaimer.free")))
        free_lbl.setWordWrap(True)
        free_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(free_lbl)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        understand_btn = QPushButton(str(i18n.tr("disclaimer.understand")))
        understand_btn.setObjectName("primaryBtn")
        understand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        understand_btn.clicked.connect(self.accept)
        btn_row.addWidget(understand_btn)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)
