# -*- coding: utf-8 -*-
"""通用 UI 辅助: 卡片样式 _CARD_QSS + 卡片容器 make_card + 清空布局 _clear_layout。

从 ui_main / ui_quest 拆出, 各页面 (overview/character/equipment/quest/tools) 复用。
ui_quest 以别名 _make_card 使用 make_card。
"""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel


# 卡片样式 (深浅主题通用, 用 objectName=card 在 ui_theme 里也可覆盖)
_CARD_QSS = (
    "QFrame#card { background-color: rgba(255,255,255,0.04);"
    "  border: 1px solid rgba(122,162,247,0.25); border-radius: 10px; }"
    "QFrame#cardTitle { background: transparent; border: none; }"
)


def make_card(title_text):
    """创建卡片容器 QFrame (objectName=card), 返回 (frame, layout)。"""
    frame = QFrame()
    frame.setObjectName("card")
    frame.setStyleSheet(_CARD_QSS)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(16, 12, 16, 14)
    lay.setSpacing(8)
    if title_text:
        title = QLabel(str(title_text))
        title.setObjectName("cardTitle")
        title.setStyleSheet("font-size: 11pt; font-weight: 600; color: #7aa2f7;")
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
