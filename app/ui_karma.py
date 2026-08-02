# -*- coding: utf-8 -*-
"""宿命烙印页 (KarmaPage + AddKarmaDialog): 左烙印列表 + 右详情(等级/超越/锁定)。

tb_karma 每件烙印是独立实例 (ITEM_DBID 大数), 无 LEVEL 字段:
  EXP 与角色等级经验一致 (level_exp.json), ASCEND 随等级反推。
"""

import os
import json
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLineEdit, QListWidget,
    QListWidgetItem, QScrollArea, QFrame, QLabel, QFormLayout, QPushButton,
    QSpinBox, QCheckBox, QDialog, QDialogButtonBox, QMessageBox,
)

from . import i18n
from .datasource import USER_DBID, QuestManager
from .ui_common import make_card


# ============================================================
# 宿命烙印页
# ============================================================
class KarmaPage(QWidget):
    """宿命烙印: 左烙印列表 + 右详情 (等级/超越/锁定) + 新增/删除。"""

    def __init__(self, data, names, main_window):
        super().__init__()
        self.data = data
        self.names = names
        self.main_window = main_window
        # 图鉴联动: QuestManager 提供宿命烙印图鉴位操作
        self.qm = QuestManager(self.data)
        self._rows = []           # tb_karma 有效行
        self._current_dbid = None
        # 等级 -> EXP 映射 (level_exp.json); EXP -> 等级反查表
        self.level_exp = self._load_level_exp()
        self._exp_to_level = {int(v): int(k) for k, v in self.level_exp.items()}
        # 烙印物品清单 (item_types.json karma 数组)
        self.karma_cids = self._load_karma_cids()
        self._build()

    @staticmethod
    def _load_level_exp():
        """加载 level_exp.json: {等级: 该等级应匹配的经验值}; 失败返回 {}。"""
        try:
            path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "level_exp.json",
            )
            if not os.path.exists(path):
                return {}
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _load_karma_cids():
        """加载 item_types.json 的 karma 数组 (宿命烙印物品 CID); 失败返回 []。"""
        try:
            path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "item_types.json",
            )
            if not os.path.exists(path):
                return []
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return list(data.get("karma", [])) if isinstance(data, dict) else []
        except Exception:
            return []

    def _level_of_exp(self, exp):
        """EXP -> 等级 (精确匹配 level_exp 反查表; 无匹配返回 None)。"""
        try:
            return self._exp_to_level.get(int(exp))
        except (TypeError, ValueError):
            return None

    # ---------- 布局 ----------
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左: 搜索框 + 烙印列表
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 6, 0)
        left_lay.setSpacing(4)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(str(i18n.tr("karma_page.search")))
        self.search_box.textChanged.connect(self._on_search)
        left_lay.addWidget(self.search_box)
        self.karma_list = QListWidget()
        self.karma_list.currentRowChanged.connect(self._on_select)
        left_lay.addWidget(self.karma_list, 1)
        splitter.addWidget(left)

        # 右: 详情滚动区
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(6, 0, 0, 0)
        right_lay.setSpacing(8)
        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.detail_container = QWidget()
        self.detail_lay = QVBoxLayout(self.detail_container)
        self.detail_lay.setContentsMargins(0, 0, 0, 0)
        self.detail_lay.setSpacing(8)
        self.detail_scroll.setWidget(self.detail_container)
        right_lay.addWidget(self.detail_scroll, 1)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([280, 700])
        outer.addWidget(splitter, 1)

        # 底部按钮行
        btn_row = QHBoxLayout()
        self.add_btn = QPushButton(str(i18n.tr("karma_page.add")))
        self.add_btn.setObjectName("primaryBtn")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self._open_add_dialog)
        btn_row.addWidget(self.add_btn)
        self.del_btn = QPushButton(str(i18n.tr("karma_page.delete")))
        self.del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.del_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(self.del_btn)
        btn_row.addStretch(1)
        outer.addLayout(btn_row)

    # ---------- 数据 ----------
    def reload(self):
        self._rows = []
        if not self.data.db_path:
            self.karma_list.clear()
            self.add_btn.setEnabled(False)
            self.del_btn.setEnabled(False)
            self._clear_layout(self.detail_lay)
            return
        try:
            rows = self.data.select_all(
                "tb_karma", "USER_DBID=? AND DELETED_DATE=0", (USER_DBID,))
        except Exception:
            rows = []
        self._rows = sorted(rows, key=lambda r: r["ITEM_CID"])
        self.add_btn.setEnabled(True)
        self._populate_list(self._rows)
        if self._rows:
            self.karma_list.setCurrentRow(0)
        else:
            self._clear_layout(self.detail_lay)
            empty = QLabel(str(i18n.tr("karma_page.no_data")))
            empty.setStyleSheet("color: #7f849c; font-size: 11pt;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.detail_lay.addWidget(empty)
            self.detail_lay.addStretch(1)

    def _populate_list(self, rows):
        """填充烙印列表 (每项: 名称 (DBID后6位), UserRole 存 ITEM_DBID)。"""
        self.karma_list.clear()
        for r in rows:
            dbid = r["ITEM_DBID"]
            cid = r["ITEM_CID"]
            name = self.names.resolve("ITEM_CID", cid) or f"#{cid}"
            text = f"{name}  ({str(dbid)[-6:]})"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, dbid)
            self.karma_list.addItem(item)

    def _on_search(self, text):
        text = text.strip().lower()
        if not text:
            self._populate_list(self._rows)
            return
        filtered = []
        for r in self._rows:
            cid = r["ITEM_CID"]
            name = self.names.resolve("ITEM_CID", cid) or ""
            if text in str(cid).lower() or text in str(name).lower():
                filtered.append(r)
        self._populate_list(filtered)

    def _on_select(self, row_idx):
        if row_idx < 0 or row_idx >= self.karma_list.count():
            return
        item = self.karma_list.item(row_idx)
        if item is None:
            return
        dbid = item.data(Qt.ItemDataRole.UserRole)
        row = None
        for r in self._rows:
            if r["ITEM_DBID"] == dbid:
                row = r
                break
        if row is None:
            return
        self._current_dbid = dbid
        self._render_detail(row)

    # ---------- 详情 ----------
    def _render_detail(self, r):
        self._clear_layout(self.detail_lay)
        dbid = r["ITEM_DBID"]
        cid = r["ITEM_CID"]
        name = self.names.resolve("ITEM_CID", cid) or f"#{cid}"

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("font-size: 16pt; font-weight: 700; color: #7aa2f7;")
        self.detail_lay.addWidget(name_lbl)
        sub = QLabel(f"ITEM_DBID = {dbid}   ·   ITEM_CID = {cid}")
        sub.setStyleSheet("color: #7f849c; font-size: 9pt;")
        self.detail_lay.addWidget(sub)

        # 表单: 等级 / 超越 / 锁定
        form = QFormLayout()
        form.setSpacing(8)

        self._level_edit = QLineEdit()
        self._level_edit.setFixedWidth(180)
        lv = self._level_of_exp(r["EXP"])
        self._level_edit.setText("" if lv is None else str(lv))
        hint = QLabel(str(i18n.tr("karma_page.exp_auto")))
        hint.setStyleSheet("color: #7f849c; font-size: 8pt;")
        row_box = QWidget()
        row_lay = QHBoxLayout(row_box)
        row_lay.setContentsMargins(0, 0, 0, 0)
        row_lay.setSpacing(6)
        row_lay.addWidget(self._level_edit)
        row_lay.addWidget(hint)
        form.addRow(str(i18n.tr("karma_page.level")), row_box)

        self._transcend_spin = QSpinBox()
        self._transcend_spin.setRange(0, 6)
        self._transcend_spin.setFixedWidth(120)
        self._transcend_spin.setValue(r["TRANSCEND"] or 0)
        form.addRow(str(i18n.tr("karma_page.transcend")), self._transcend_spin)

        self._lock_chk = QCheckBox(str(i18n.tr("karma_page.lock")))
        self._lock_chk.setChecked(bool(r["IS_LOCK"]))
        form.addRow("", self._lock_chk)

        self.detail_lay.addLayout(form)

        apply_btn = QPushButton(str(i18n.tr("karma_page.apply")))
        apply_btn.setObjectName("primaryBtn")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.clicked.connect(self._apply)
        self.detail_lay.addWidget(apply_btn)
        self.detail_lay.addStretch(1)

    def _apply(self):
        """应用修改: 等级 -> EXP+ASCEND 自动匹配; 超越/锁定直接写。"""
        if self._current_dbid is None:
            return
        dbid = self._current_dbid
        transcend = self._transcend_spin.value()
        is_lock = 1 if self._lock_chk.isChecked() else 0

        raw = self._level_edit.text().strip()
        if raw == "":
            # 等级留空: 不动 EXP/ASCEND
            sets = ['"TRANSCEND"=?', '"IS_LOCK"=?']
            vals = [transcend, is_lock]
        else:
            try:
                lv = int(raw)
            except ValueError:
                QMessageBox.warning(self, str(i18n.tr("status.error")),
                                    f"{dbid} LEVEL: {raw}")
                return
            if lv < 1 or lv > 100:
                QMessageBox.warning(self, str(i18n.tr("status.error")),
                                    f"LEVEL {lv} 超出范围 (1~100)")
                return
            exp = int(self.level_exp.get(str(lv), 0)) if self.level_exp else 0
            ascend = max(0, min(5, (lv - 1) // 10 - 1))
            sets = ['"EXP"=?', '"ASCEND"=?', '"TRANSCEND"=?', '"IS_LOCK"=?']
            vals = [exp, ascend, transcend, is_lock]

        vals.append(dbid)
        sql = ("UPDATE tb_karma SET " + ", ".join(sets) + " WHERE ITEM_DBID=?")
        try:
            self.data.execute(sql, vals)
        except Exception as ex:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
            return
        self.main_window.set_status(str(i18n.tr("karma_page.updated")))
        # 重新取行并渲染 (刷新等级显示)
        try:
            rows = self.data.select_all("tb_karma", "ITEM_DBID=?", (dbid,))
            if rows:
                self._render_detail(rows[0])
        except Exception:
            pass

    # ---------- 新增 / 删除 ----------
    def _open_add_dialog(self):
        if not self.data.db_path:
            QMessageBox.information(self, "", str(i18n.tr("status.no_db")))
            return
        dlg = AddKarmaDialog(self.data, self.names, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.reload()
            msg = str(i18n.tr("karma_page.added", n=dlg.added_count))
            if getattr(dlg, "collection_unlocked", False):
                msg += " · " + str(i18n.tr("karma_page.collection_unlocked"))
            self.main_window.set_status(msg)

    def _delete_selected(self):
        if self._current_dbid is None:
            QMessageBox.information(self, str(i18n.tr("dialogs.confirm")),
                                    str(i18n.tr("karma_page.select_first")))
            return
        if QMessageBox.question(
                self, str(i18n.tr("dialogs.confirm")),
                str(i18n.tr("karma_page.delete_confirm"))
        ) != QMessageBox.StandardButton.Yes:
            return
        dbid = self._current_dbid
        try:
            self.data.execute("DELETE FROM tb_karma WHERE ITEM_DBID=?", (dbid,))
        except Exception as ex:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
            return
        self.main_window.set_status(str(i18n.tr("karma_page.deleted", n=1)))
        self._current_dbid = None
        self.reload()

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


# ============================================================
# 新增宿命烙印对话框
# ============================================================
class AddKarmaDialog(QDialog):
    """新增宿命烙印: 搜索并选烙印物品 -> 数量 (每件独立实例) -> 写入 tb_karma。"""

    def __init__(self, data, names, parent):
        super().__init__(parent)
        self.data = data
        self.names = names
        self.added_count = 0
        # 烙印物品清单 (从父页 KarmaPage 复用)
        self.karma_cids = list(getattr(parent, "karma_cids", None) or [])
        if not self.karma_cids:
            self.karma_cids = KarmaPage._load_karma_cids()
        self.setWindowTitle(str(i18n.tr("karma_page.add_title")))
        self.setMinimumSize(420, 460)
        self._build()
        self._refresh_list()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(str(i18n.tr("karma_page.add_search")))
        self.search_box.textChanged.connect(lambda _t: self._refresh_list())
        lay.addWidget(self.search_box)

        self.item_list = QListWidget()
        self.item_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        lay.addWidget(self.item_list, 1)

        cnt_row = QHBoxLayout()
        cnt_row.addWidget(QLabel(str(i18n.tr("karma_page.count"))))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 99)
        self.count_spin.setValue(1)
        cnt_row.addWidget(self.count_spin)
        cnt_row.addStretch(1)
        lay.addLayout(cnt_row)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(str(i18n.tr("dialogs.ok")))
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText(str(i18n.tr("dialogs.cancel")))
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _refresh_list(self):
        self.item_list.clear()
        cids = list(self.karma_cids)
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

    def _new_item_dbid(self):
        """生成不冲突的 ITEM_DBID (时间戳<<28 | 随机28位, 查 tb_karma 去重)。"""
        import random
        while True:
            v = (int(time.time()) << 28) | random.getrandbits(28)
            exists = self.data.select_all("tb_karma", "ITEM_DBID=?", (v,))
            if not exists:
                return v

    def _on_ok(self):
        cur = self.item_list.currentItem()
        if cur is None:
            QMessageBox.information(self, str(i18n.tr("dialogs.confirm")),
                                    str(i18n.tr("karma_page.select_first")))
            return
        cid = int(cur.data(Qt.ItemDataRole.UserRole))
        cnt = self.count_spin.value()
        now = int(time.time())
        # 图鉴联动: 通过父页 KarmaPage 访问 QuestManager (幂等位或)
        qm = getattr(self.parent(), "qm", None)
        try:
            for _ in range(cnt):
                new_dbid = self._new_item_dbid()
                self.data.execute(
                    "INSERT INTO tb_karma (ITEM_DBID, USER_DBID, ITEM_CID, "
                    "IS_LOCK, EXP, ASCEND, TRANSCEND, CREATED_DATE, DELETED_DATE) "
                    "VALUES (?,?,?,0,0,0,0,?,0)",
                    (new_dbid, USER_DBID, cid, now))
                if qm is not None:
                    qm.unlock_karma_collection(cid)
        except Exception as ex:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
            return
        self.added_count = cnt
        self.collection_unlocked = qm is not None
        self.accept()
