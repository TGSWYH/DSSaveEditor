# -*- coding: utf-8 -*-
"""使魔页 (VehiclePage): 自定义列表 (名称/类型/介绍 + 可用开关)。

vehicle_data.json 提供 30 个使魔元数据; tb_vehicle 有行 = 已解锁。
解锁/关闭 = INSERT/DELETE tb_vehicle 行, 立即生效。
"""

import os
import json
import time

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QCheckBox,
)

from . import i18n
from .config import DATA_DIR
from .datasource import USER_DBID, localize_name
from .ui_common import make_card


# ============================================================
# 使魔页
# ============================================================
class VehiclePage(QWidget):
    """使魔: 自定义列表, 每行 名称/类型/介绍 + 可用开关 (点击立即写库)。"""

    # 行内边距 (上下各 6) + 名称行与介绍间距 (2) —— 高度计算用
    ROW_V_PAD = 12
    ROW_SPACING = 2

    def __init__(self, data, names, main_window):
        super().__init__()
        self.data = data
        self.names = names
        self.main_window = main_window
        # 使魔元数据 vehicle_data.json: {cid_str: {name, type, desc, dlc, ...}}
        self.vehicles = self._load_vehicles()
        self._unlocked = set()   # 已解锁 VEHICLE_CID 集合
        self._rebuilding = False  # resize 触发的重建守卫
        self._row_widgets = {}   # cid -> 行 QWidget (供更新勾选)
        self._build()

    @staticmethod
    def _load_vehicles():
        """加载 vehicle_data.json; 失败返回 {} (列表空 + 提示, 不崩溃)。"""
        try:
            path = os.path.join(
                DATA_DIR,
                "vehicle_data.json",
            )
            if not os.path.exists(path):
                return {}
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    # ---------- 布局 ----------
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        hint = QLabel(str(i18n.tr("vehicle_page.hint")))
        hint.setStyleSheet("color: #7f849c; font-size: 9pt;")
        hint.setWordWrap(True)
        outer.addWidget(hint)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(str(i18n.tr("vehicle_page.search")))
        self.search_box.textChanged.connect(self._on_search)
        outer.addWidget(self.search_box)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.list_widget.setSpacing(2)
        outer.addWidget(self.list_widget, 1)

    # ---------- 数据 ----------
    def reload(self):
        self._unlocked = set()
        if self.data.db_path:
            try:
                rows = self.data.select_all(
                    "tb_vehicle", "USER_DBID=?", (USER_DBID,))
                for r in rows:
                    self._unlocked.add(r["VEHICLE_CID"])
            except Exception:
                pass
        self._rebuild_list()

    def _vehicle_name(self, cid):
        """使魔名: 优先数据文件 name -> names.resolve -> #CID。"""
        meta = self.vehicles.get(str(cid))
        if isinstance(meta, dict):
            n = localize_name(meta.get("name"))
            if n:
                return str(n)
        resolved = self.names.resolve("VEHICLE_CID", cid)
        if resolved:
            return str(resolved)
        return f"#{cid}"

    def _vehicle_type(self, cid):
        meta = self.vehicles.get(str(cid))
        if isinstance(meta, dict):
            t = localize_name(meta.get("type"))
            if t:
                return str(t)
        return None

    def _vehicle_desc(self, cid):
        meta = self.vehicles.get(str(cid))
        if isinstance(meta, dict):
            d = localize_name(meta.get("desc"))
            if d:
                return str(d)
        return None

    def _vehicle_dlc(self, cid):
        meta = self.vehicles.get(str(cid))
        if isinstance(meta, dict):
            return meta.get("dlc") or 0
        return 0

    def _rebuild_list(self):
        """重建列表: 按 CID 升序; 支持搜索 (名称/类型); 每行自定义 widget。
        行高按介绍文本换行结果自适应 (长介绍完整展开)。"""
        self.list_widget.clear()
        self._row_widgets = {}
        if not self.vehicles:
            item = QListWidgetItem(str(i18n.tr("vehicle_page.no_data")))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_widget.addItem(item)
            return
        kw = self.search_box.text().strip().lower()
        enabled = self.data.db_path is not None
        # 可用文本宽度: 视口宽 - 左右内边距 (10+10), 最小 240 防过窄
        avail_w = max(self.list_widget.viewport().width() - 20, 240)
        for cid in sorted(self.vehicles, key=lambda c: int(c)):
            name = self._vehicle_name(cid)
            vtype = self._vehicle_type(cid)
            if kw:
                if kw not in str(cid).lower() and kw not in name.lower() \
                        and not (vtype and kw in vtype.lower()):
                    continue
            is_on = int(cid) in self._unlocked
            row_widget = self._make_row_widget(cid, is_on, enabled, avail_w)
            h = row_widget.height()
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, h))
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row_widget)
            self._row_widgets[str(cid)] = row_widget

    def _make_row_widget(self, cid, is_on, enabled, avail_w):
        """构建单行使魔行: 第一行 名称+类型+DLC+开关, 第二行 完整介绍。
        返回的 widget 已按介绍换行高度 setFixedHeight。"""
        cid = str(cid)
        name = self._vehicle_name(cid)
        vtype = self._vehicle_type(cid)
        desc = self._vehicle_desc(cid)
        dlc = self._vehicle_dlc(cid)

        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(self.ROW_SPACING)

        # 第一行: 名称(粗体) + DLC徽标 + 类型 + 可用开关
        top = QHBoxLayout()
        top.setSpacing(6)
        name_lbl = QLabel(name)
        f = name_lbl.font()
        f.setBold(True)
        name_lbl.setFont(f)
        top.addWidget(name_lbl)
        if dlc:
            dlc_lbl = QLabel(str(i18n.tr("vehicle_page.dlc_badge")))
            dlc_lbl.setStyleSheet("color: #e0af68; font-weight: 600;")
            top.addWidget(dlc_lbl)
        if vtype:
            type_lbl = QLabel(str(i18n.tr("vehicle_page.type_fmt", type=vtype)))
            type_lbl.setStyleSheet("color: #7f849c; font-size: 9pt;")
            top.addWidget(type_lbl)
        top.addStretch(1)
        chk = QCheckBox(str(i18n.tr("vehicle_page.available")))
        chk.setChecked(is_on)
        chk.setEnabled(enabled)
        chk.setCursor(Qt.CursorShape.PointingHandCursor)
        chk.toggled.connect(lambda checked, c=cid: self._on_toggle(c, checked))
        top.addWidget(chk)
        lay.addLayout(top)

        # 第二行: 介绍 (wordWrap, 灰色小字; 无介绍则留空)
        desc_lbl = None
        if desc:
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet("color: #7f849c; font-size: 9pt;")
            desc_lbl.setWordWrap(True)
            lay.addWidget(desc_lbl)

        # 自适应高度: 名称行 + 介绍换行高度 (heightForWidth) + 上下边距 (+ 间距)
        name_h = name_lbl.sizeHint().height()
        desc_h = desc_lbl.heightForWidth(avail_w) if desc_lbl is not None else 0
        total = self.ROW_V_PAD + name_h + desc_h
        if desc_lbl is not None and desc_h > 0:
            total += self.ROW_SPACING
        w.setFixedHeight(total)
        return w

    # ---------- 交互 ----------
    def _on_toggle(self, cid, checked):
        """开关切换: 立即写 tb_vehicle (INSERT/DELETE), 状态栏提示。"""
        if self.data.db_path is None:
            return
        cid_int = int(cid)
        name = self._vehicle_name(cid)
        try:
            if checked:
                new_dbid = self._new_vehicle_dbid()
                self.data.execute(
                    "INSERT INTO tb_vehicle (VEHICLE_DBID, USER_DBID, VEHICLE_CID, "
                    "CREATED_DATE) VALUES (?,?,?,?)",
                    (new_dbid, USER_DBID, cid_int, int(time.time())))
                self._unlocked.add(cid_int)
                self.main_window.set_status(str(i18n.tr("vehicle_page.unlocked",
                                                        name=name)))
            else:
                self.data.execute(
                    "DELETE FROM tb_vehicle WHERE USER_DBID=? AND VEHICLE_CID=?",
                    (USER_DBID, cid_int))
                self._unlocked.discard(cid_int)
                self.main_window.set_status(str(i18n.tr("vehicle_page.locked",
                                                        name=name)))
        except Exception as ex:
            # 写库失败: 回弹勾选 (防止显示与实际不一致)
            w = self._row_widgets.get(cid)
            if w is not None:
                chk = w.findChild(QCheckBox)
                if chk is not None:
                    chk.blockSignals(True)
                    chk.setChecked(not checked)
                    chk.blockSignals(False)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
            return

    def _new_vehicle_dbid(self):
        """生成不冲突的 VEHICLE_DBID (时间戳<<28 | 随机28位, 查 tb_vehicle 去重)。"""
        import random
        while True:
            v = (int(time.time()) << 28) | random.getrandbits(28)
            exists = self.data.select_all("tb_vehicle", "VEHICLE_DBID=?", (v,))
            if not exists:
                return v

    # ---------- 搜索 ----------
    def _on_search(self, _text):
        self._rebuild_list()

    # ---------- 窗口缩放 ----------
    def resizeEvent(self, e):
        """列表宽度变化 -> 换行行数变化, 重建列表重算行高并恢复滚动位置。"""
        super().resizeEvent(e)
        if self._rebuilding:
            return
        self._rebuilding = True
        try:
            scroll = self.list_widget.verticalScrollBar().value()
            self._rebuild_list()
            self.list_widget.verticalScrollBar().setValue(scroll)
        finally:
            self._rebuilding = False
