# -*- coding: utf-8 -*-
"""总览页 (OverviewPage): 玩家卡片 + 资源卡片 + 角色列表卡片; 未加载时显示引导。

从 ui_main 拆出。
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QScrollArea, QFrame, QGridLayout, QMessageBox,
)

from . import i18n
from .datasource import USER_DBID, CUR_GOLD
from .ui_common import make_card


# ============================================================
# 总览页
# ============================================================
class OverviewPage(QWidget):
    """总览: 玩家卡片 + 资源卡片 + 角色列表卡片; 未加载时显示引导。"""

    # 信号: 点击角色行 -> 请求切到角色页并选中
    character_clicked = Signal(int)

    def __init__(self, data, names, main_window):
        super().__init__()
        self.data = data
        self.names = names
        self.main_window = main_window
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget()
        self.container_lay = QVBoxLayout(self.container)
        self.container_lay.setContentsMargins(0, 0, 0, 0)
        self.container_lay.setSpacing(12)
        self.scroll_area.setWidget(self.container)
        outer.addWidget(self.scroll_area)

    def reload(self):
        # 清空
        self._clear_layout(self.container_lay)
        if not self.data.db_path:
            self._build_guide()
            return
        self._build_player_card()
        self._build_resource_card()
        self._build_character_list_card()

    def _build_guide(self):
        card, lay = make_card(str(i18n.tr("overview.no_save")))
        hint = QLabel(str(i18n.tr("overview.open_hint")))
        hint.setStyleSheet("color: #7f849c; font-size: 11pt;")
        lay.addWidget(hint)
        open_btn = QPushButton(str(i18n.tr("menu.open")))
        open_btn.setObjectName("primaryBtn")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setFixedWidth(200)
        open_btn.clicked.connect(self.main_window.cmd_open)
        lay.addWidget(open_btn)
        self.container_lay.addWidget(card)
        self.container_lay.addStretch(1)

    def _build_player_card(self):
        card, lay = make_card(str(i18n.tr("overview.player_card")))
        try:
            row = self.data.fetchone(
                "SELECT USER_DBID, CREATE_DATE FROM tb_user WHERE USER_DBID=?",
                (USER_DBID,),
            )
        except Exception:
            row = None
        uid = row["USER_DBID"] if row else "?"
        create_date = row["CREATE_DATE"] if row and row["CREATE_DATE"] else "-"
        try:
            char_count = len(self.data.select_all(
                "tb_character", "USER_DBID=?", (USER_DBID,)))
        except Exception:
            char_count = 0
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(6)
        grid.addWidget(self._kv_label("UID"), 0, 0)
        grid.addWidget(self._val_label(str(uid)), 0, 1)
        grid.addWidget(self._kv_label(str(i18n.tr("overview.character_count"))), 1, 0)
        grid.addWidget(self._val_label(str(char_count)), 1, 1)
        grid.addWidget(self._kv_label("CREATE_DATE"), 2, 0)
        grid.addWidget(self._val_label(str(create_date)), 2, 1)
        lay.addLayout(grid)
        self.container_lay.addWidget(card)

    def _build_resource_card(self):
        # 资源卡片: 只保留金币 (ITEM_CID=1000001), 以太晶体/体力已废弃
        card, lay = make_card(str(i18n.tr("overview.resource_card")))
        amount = 0
        try:
            r = self.data.fetchone(
                "SELECT AMOUNT FROM tb_currency WHERE USER_DBID=? AND ITEM_CID=?",
                (USER_DBID, CUR_GOLD),
            )
            if r:
                amount = r["AMOUNT"] or 0
        except Exception:
            pass
        mapped = self.names.resolve("ITEM_CID", CUR_GOLD)
        name = mapped if mapped else str(i18n.tr("overview_page.gold"))
        self._overview_cur_entries = {}
        row = QHBoxLayout()
        row.addWidget(self._kv_label(name))
        e = QLineEdit()
        e.setFixedWidth(160)
        e.setText(str(amount))
        row.addWidget(e)
        row.addStretch(1)
        self._overview_cur_entries[CUR_GOLD] = e
        lay.addLayout(row)
        apply_btn = QPushButton(str(i18n.tr("currency.apply")))
        apply_btn.setObjectName("primaryBtn")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.clicked.connect(self._apply_overview_currency)
        lay.addWidget(apply_btn)
        self.container_lay.addWidget(card)

    def _apply_overview_currency(self):
        for cid, e in self._overview_cur_entries.items():
            raw = e.text().strip()
            try:
                val = int(raw)
            except ValueError:
                QMessageBox.warning(self, str(i18n.tr("status.error")),
                                     str(i18n.tr("table.invalid_number")))
                return
            try:
                exists = self.data.fetchone(
                    "SELECT 1 FROM tb_currency WHERE USER_DBID=? AND ITEM_CID=?",
                    (USER_DBID, cid),
                )
                if exists:
                    self.data.execute(
                        "UPDATE tb_currency SET AMOUNT=? WHERE USER_DBID=? AND ITEM_CID=?",
                        (val, USER_DBID, cid),
                    )
                else:
                    self.data.execute(
                        "INSERT INTO tb_currency (USER_DBID, ITEM_CID, AMOUNT) VALUES (?,?,?)",
                        (USER_DBID, cid, val),
                    )
            except Exception as ex:
                QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
                return
        self.main_window.set_status(str(i18n.tr("currency.modified")))

    def _build_character_list_card(self):
        card, lay = make_card(str(i18n.tr("overview.character_list")))
        try:
            rows = self.data.select_all("tb_character", "USER_DBID=?", (USER_DBID,))
        except Exception:
            rows = []
        if not rows:
            empty = QLabel(str(i18n.tr("character_page.no_data")))
            empty.setStyleSheet("color: #7f849c;")
            lay.addWidget(empty)
        else:
            for r in rows:
                cid = r["CHARACTER_CID"]
                cname = self.names.resolve("CHARACTER_CID", cid)
                disp = cname if cname else f"#{cid}"
                text = str(i18n.tr("character_page.list_lv_fmt",
                                   name=disp, lv=r["LEVEL"]))
                btn = QPushButton(text)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(
                    "text-align: left; padding: 6px 10px; "
                    "background: transparent; border: 1px solid rgba(122,162,247,0.2);"
                    "border-radius: 6px;"
                )
                btn.clicked.connect(lambda _=False, c=cid: self.character_clicked.emit(c))
                lay.addWidget(btn)
        self.container_lay.addWidget(card)
        self.container_lay.addStretch(1)

    # ---------- 辅助 ----------
    def _kv_label(self, text):
        lbl = QLabel(str(text))
        lbl.setStyleSheet("color: #7f849c; font-size: 9pt;")
        return lbl

    def _val_label(self, text):
        lbl = QLabel(str(text))
        lbl.setStyleSheet("font-size: 11pt; font-weight: 600;")
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return lbl

    def _clear_layout(self, layout):
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            else:
                self._clear_layout(item.layout())
