# -*- coding: utf-8 -*-
"""背包页 (InventoryPage): 堆叠物品 + 料理, 支持批量操作 (删除 / 调整数量) 与新增道具。

从 ui_main 拆出。AddItemDialog: 按 item_types.json 选物品并写入存档。
"""

import os
import json
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QCheckBox, QTableWidget,
    QTableWidgetItem, QPushButton, QMessageBox, QInputDialog, QDialog,
    QDialogButtonBox, QComboBox, QListWidget, QListWidgetItem, QSpinBox,
    QLabel, QHeaderView,
)

from . import i18n
from .config import DATA_DIR
from .datasource import USER_DBID


# ============================================================
# 背包页 (批量操作模式)
# ============================================================
class InventoryPage(QWidget):
    """背包: 堆叠物品 + 料理, 支持批量操作 (删除 / 调整数量)。"""

    def __init__(self, data, names, main_window):
        super().__init__()
        self.data = data
        self.names = names
        self.main_window = main_window
        self._rows = []          # [{table, ITEM_CID, STACK_CNT}]
        self._batch_mode = False
        self._skip_delete_confirm = False
        # 新增道具数据: item_types.json {stackable: [cid...], cook: [cid...]}
        self.item_types = self._load_item_types()
        self._build()

    @staticmethod
    def _load_item_types():
        """加载 item_types.json; 失败返回 {} (新增道具对话框显示空列表, 不崩溃)。"""
        try:
            path = os.path.join(
                DATA_DIR,
                "item_types.json",
            )
            if not os.path.exists(path):
                return {}
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        # 顶部: 搜索 + 批量模式开关
        top = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(str(i18n.tr("inventory_page.search")))
        self.search_box.textChanged.connect(self._reload_table)
        top.addWidget(self.search_box, 1)
        self.batch_chk = QCheckBox(str(i18n.tr("inventory_page.batch_mode")))
        self.batch_chk.toggled.connect(self._on_batch_toggled)
        top.addWidget(self.batch_chk)
        outer.addLayout(top)

        # 表格
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        # 铺满策略: 末列拉伸填满 (其余列按内容自适应)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        outer.addWidget(self.table, 1)

        # 操作按钮
        btn_row = QHBoxLayout()
        self.del_btn = QPushButton(str(i18n.tr("inventory_page.delete")))
        self.del_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(self.del_btn)
        self.set_btn = QPushButton(str(i18n.tr("inventory_page.set_count")))
        self.set_btn.clicked.connect(self._set_count)
        btn_row.addWidget(self.set_btn)
        self.set_99_btn = QPushButton(str(i18n.tr("inventory_page.set_99")))
        self.set_99_btn.clicked.connect(lambda: self._set_fixed(99))
        btn_row.addWidget(self.set_99_btn)
        self.set_999_btn = QPushButton(str(i18n.tr("inventory_page.set_999")))
        self.set_999_btn.clicked.connect(lambda: self._set_fixed(999))
        btn_row.addWidget(self.set_999_btn)
        btn_row.addStretch(1)
        self.add_item_btn = QPushButton(str(i18n.tr("inventory_page.add_item")))
        self.add_item_btn.setObjectName("primaryBtn")
        self.add_item_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_item_btn.clicked.connect(self._open_add_dialog)
        btn_row.addWidget(self.add_item_btn)
        outer.addLayout(btn_row)

    def reload(self):
        self._reload_table()

    def _load_rows(self):
        """加载堆叠物品 + 料理, 应用搜索过滤并排序。"""
        self._rows = []
        if not self.data.db_path:
            return
        try:
            for r in self.data.select_all("tb_stackable_item"):
                self._rows.append({"table": "tb_stackable_item", "ITEM_CID": r["ITEM_CID"],
                                   "STACK_CNT": r["STACK_CNT"] or 0})
            for r in self.data.select_all("tb_cook_item"):
                self._rows.append({"table": "tb_cook_item", "ITEM_CID": r["ITEM_CID"],
                                   "STACK_CNT": r["STACK_CNT"] or 0})
        except Exception:
            return
        kw = self.search_box.text().strip().lower()
        if kw:
            self._rows = [r for r in self._rows
                          if kw in str(r["ITEM_CID"])
                          or kw in str(self.names.resolve("ITEM_CID", r["ITEM_CID"]) or "").lower()]
        self._rows.sort(key=lambda r: r["ITEM_CID"])

    def _reload_table(self, *_):
        if not self.data.db_path:
            self.table.clear()
            return
        self._load_rows()
        self.table.clear()
        if self._batch_mode:
            headers = ["", str(i18n.tr("table.column_name")),
                       str(i18n.tr("inventory_page.item_id")),
                       str(i18n.tr("inventory_page.count")),
                       str(i18n.tr("inventory_page.source"))]
        else:
            headers = [str(i18n.tr("table.column_name")),
                       str(i18n.tr("inventory_page.item_id")),
                       str(i18n.tr("inventory_page.count")),
                       str(i18n.tr("inventory_page.source"))]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(self._rows))
        for i, r in enumerate(self._rows):
            name = self.names.resolve("ITEM_CID", r["ITEM_CID"]) or f"#{r['ITEM_CID']}"
            col = 0
            if self._batch_mode:
                it = QTableWidgetItem()
                it.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                it.setCheckState(Qt.CheckState.Unchecked)
                self.table.setItem(i, col, it)
                col = 1
            self.table.setItem(i, col, QTableWidgetItem(str(name)))
            self.table.setItem(i, col + 1, QTableWidgetItem(str(r["ITEM_CID"])))
            self.table.setItem(i, col + 2, QTableWidgetItem(str(r["STACK_CNT"])))
            src = (i18n.tr("inventory_page.source_stack")
                   if r["table"] == "tb_stackable_item"
                   else i18n.tr("inventory_page.source_cook"))
            self.table.setItem(i, col + 3, QTableWidgetItem(str(src)))
        # 铺满: 批量模式首列勾选固定 36px; 其余列按内容自适应; 末列拉伸填满
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        if self._batch_mode:
            self.table.setColumnWidth(0, 36)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            start = 1
        else:
            start = 0
        for c in range(start, self.table.columnCount() - 1):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.table.columnCount() - 1,
                                    QHeaderView.ResizeMode.Stretch)

    def _on_batch_toggled(self, checked):
        self._batch_mode = checked
        self._reload_table()

    def _selected_rows(self):
        """批量模式: 勾选的行; 普通模式: 当前选中行。"""
        if self._batch_mode:
            out = []
            for i in range(self.table.rowCount()):
                it = self.table.item(i, 0)
                if it and it.checkState() == Qt.CheckState.Checked:
                    out.append(self._rows[i])
            return out
        row = self.table.currentRow()
        return [self._rows[row]] if 0 <= row < len(self._rows) else []

    def _delete_selected(self):
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(self, str(i18n.tr("dialogs.confirm")),
                                    str(i18n.tr("inventory_page.select_first")))
            return
        n = len(rows)
        if not self._skip_delete_confirm:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle(str(i18n.tr("dialogs.confirm")))
            msg.setText(str(i18n.tr("inventory_page.delete_confirm", n=n)))
            chk = QCheckBox(str(i18n.tr("inventory_page.no_confirm_again")))
            msg.setCheckBox(chk)
            yes_btn = msg.addButton(str(i18n.tr("dialogs.yes")),
                                    QMessageBox.ButtonRole.YesRole)
            msg.addButton(str(i18n.tr("dialogs.no")),
                          QMessageBox.ButtonRole.NoRole)
            msg.exec()
            if msg.clickedButton() is not yes_btn:
                return
            if chk.isChecked():
                self._skip_delete_confirm = True
        try:
            for r in rows:
                if r["table"] == "tb_stackable_item":
                    self.data.execute(
                        "DELETE FROM tb_stackable_item WHERE USER_DBID=? AND ITEM_CID=?",
                        (USER_DBID, r["ITEM_CID"]))
                else:
                    self.data.execute(
                        "DELETE FROM tb_cook_item WHERE USER_DBID=? AND ITEM_CID=?",
                        (USER_DBID, r["ITEM_CID"]))
        except Exception as ex:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
            return
        self.main_window.set_status(str(i18n.tr("inventory_page.deleted", n=n)))
        self._reload_table()

    def _set_count(self):
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(self, str(i18n.tr("dialogs.confirm")),
                                    str(i18n.tr("inventory_page.select_first")))
            return
        val, ok = QInputDialog.getInt(
            self, str(i18n.tr("inventory_page.set_count_title")),
            str(i18n.tr("inventory_page.count_hint")), 1, 0, 999999999)
        if not ok:
            return
        try:
            for r in rows:
                if r["table"] == "tb_stackable_item":
                    self.data.execute(
                        "UPDATE tb_stackable_item SET STACK_CNT=? WHERE USER_DBID=? AND ITEM_CID=?",
                        (val, USER_DBID, r["ITEM_CID"]))
                else:
                    self.data.execute(
                        "UPDATE tb_cook_item SET STACK_CNT=? WHERE USER_DBID=? AND ITEM_CID=?",
                        (val, USER_DBID, r["ITEM_CID"]))
        except Exception as ex:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
            return
        self.main_window.set_status(str(i18n.tr("inventory_page.count_updated")))
        self._reload_table()

    def _set_fixed(self, val):
        """快捷设定数量: 对选中行直接 UPDATE STACK_CNT=val (无输入框)。"""
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(self, str(i18n.tr("dialogs.confirm")),
                                    str(i18n.tr("inventory_page.select_first")))
            return
        try:
            for r in rows:
                if r["table"] == "tb_stackable_item":
                    self.data.execute(
                        "UPDATE tb_stackable_item SET STACK_CNT=? WHERE USER_DBID=? AND ITEM_CID=?",
                        (val, USER_DBID, r["ITEM_CID"]))
                else:
                    self.data.execute(
                        "UPDATE tb_cook_item SET STACK_CNT=? WHERE USER_DBID=? AND ITEM_CID=?",
                        (val, USER_DBID, r["ITEM_CID"]))
        except Exception as ex:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
            return
        self.main_window.set_status(str(i18n.tr("inventory_page.count_updated")))
        self._reload_table()

    def _open_add_dialog(self):
        """打开"新增道具"对话框; Accepted 后刷新表格。"""
        if not self.data.db_path:
            QMessageBox.information(self, "", str(i18n.tr("status.no_db")))
            return
        dlg = AddItemDialog(self.data, self.names, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._reload_table()
            self.main_window.set_status(str(i18n.tr("inventory_page.item_added",
                                                    name=dlg.item_name,
                                                    count=dlg.item_count)))


# ============================================================
# 新增道具对话框
# ============================================================
class AddItemDialog(QDialog):
    """新增道具: 选类型(堆叠/料理) -> 搜索并选物品 -> 数量 -> 写入存档。"""

    def __init__(self, data, names, main_window):
        super().__init__(main_window)
        self.data = data
        self.names = names
        self.main_window = main_window
        # main_window 是 InventoryPage, 复用其已加载的 item_types; 缺失则自加载
        self.item_types = getattr(main_window, "item_types", None) or {}
        if not self.item_types:
            self.item_types = InventoryPage._load_item_types()
        self.item_name = ""
        self.item_count = 1
        self.setWindowTitle(str(i18n.tr("inventory_page.add_title")))
        self.setMinimumSize(420, 460)
        self._build()
        self._refresh_list()

    # ---------- 布局 ----------
    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)

        # 类型选择
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel(str(i18n.tr("inventory_page.source"))))
        self.type_combo = QComboBox()
        self.type_combo.addItem(str(i18n.tr("inventory_page.type_stack")), "stackable")
        self.type_combo.addItem(str(i18n.tr("inventory_page.type_cook")), "cook")
        self.type_combo.currentIndexChanged.connect(lambda _i: self._refresh_list())
        type_row.addWidget(self.type_combo, 1)
        lay.addLayout(type_row)

        # 搜索
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(str(i18n.tr("inventory_page.add_search")))
        self.search_box.textChanged.connect(lambda _t: self._refresh_list())
        lay.addWidget(self.search_box)

        # 物品列表
        self.item_list = QListWidget()
        self.item_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        lay.addWidget(self.item_list, 1)

        # 数量
        cnt_row = QHBoxLayout()
        cnt_row.addWidget(QLabel(str(i18n.tr("inventory_page.add_count"))))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 9999)
        self.count_spin.setValue(1)
        cnt_row.addWidget(self.count_spin)
        cnt_row.addStretch(1)
        lay.addLayout(cnt_row)

        # 按钮
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(str(i18n.tr("dialogs.ok")))
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText(str(i18n.tr("dialogs.cancel")))
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    # ---------- 数据 ----------
    def _refresh_list(self):
        """按当前类型 + 搜索词填充物品列表 (CID 升序, 显示 "CID 名称")。"""
        self.item_list.clear()
        kind = self.type_combo.currentData()
        cids = list(self.item_types.get(kind, []))
        kw = self.search_box.text().strip().lower()
        if kw:
            cids = [c for c in cids
                    if kw in c.lower()
                    or kw in str(self.names.resolve("ITEM_CID", int(c)) or "").lower()]
        cids.sort(key=lambda c: int(c))
        for cid in cids:
            name = self.names.resolve("ITEM_CID", int(cid)) or f"#{cid}"
            it = QListWidgetItem(f"{cid} {name}")
            it.setData(Qt.ItemDataRole.UserRole, cid)
            self.item_list.addItem(it)

    def _new_item_dbid(self, table):
        """生成不冲突的 ITEM_DBID (时间戳<<28 | 随机28位), 在指定表内查重。"""
        import random
        while True:
            v = (int(time.time()) << 28) | random.getrandbits(28)
            exists = self.data.select_all(table, "ITEM_DBID=?", (v,))
            if not exists:
                return v

    def _on_ok(self):
        """校验并写入: 堆叠物品 INSERT OR REPLACE; 料理生成新 ITEM_DBID。"""
        cur = self.item_list.currentItem()
        if cur is None:
            QMessageBox.information(self, str(i18n.tr("dialogs.confirm")),
                                    str(i18n.tr("inventory_page.add_select_first")))
            return
        cid = int(cur.data(Qt.ItemDataRole.UserRole))
        cnt = self.count_spin.value()
        self.item_name = self.names.resolve("ITEM_CID", cid) or f"#{cid}"
        self.item_count = cnt
        kind = self.type_combo.currentData()
        now = int(time.time())
        try:
            if kind == "cook":
                new_dbid = self._new_item_dbid("tb_cook_item")
                self.data.execute(
                    "INSERT INTO tb_cook_item (USER_DBID, ITEM_DBID, ITEM_CID, "
                    "SPECIAL_BUFF_CID1, SPECIAL_BUFF_CID2, STACK_CNT, "
                    "CREATED_DATE, DELETED_DATE) VALUES (?,?,?,0,0,?,?,0)",
                    (USER_DBID, new_dbid, cid, cnt, now))
            else:
                self.data.execute(
                    "INSERT OR REPLACE INTO tb_stackable_item "
                    "(USER_DBID, ITEM_CID, STACK_CNT) VALUES (?,?,?)",
                    (USER_DBID, cid, cnt))
        except Exception as ex:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
            return
        self.accept()
