# -*- coding: utf-8 -*-
"""装备页 (EquipmentPage + AddEquipmentDialog): 左装备列表 + 右详情(属性+词条定制器+符文槽)。

从 ui_main 拆出。符文槽: GEM_DBID 0/1 开放切换 + 持有符文列表 (tb_gem + gem_stat.json/GemNewStatData)。
"""

import os
import json
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLineEdit, QListWidget,
    QListWidgetItem, QAbstractItemView, QPushButton, QScrollArea, QFrame,
    QLabel, QSpinBox, QCheckBox, QFormLayout, QComboBox, QDialog,
    QDialogButtonBox, QMessageBox, QTableWidget, QTableWidgetItem,
)

from . import i18n
from .config import DATA_DIR
from .datasource import localize_name, USER_DBID
from .ui_common import make_card

# 开放符文槽所需的精工工具 ITEM_CID (StringData: "使用它开放符文槽")
GEM_TOOL_CID = 1450408
MOUNT_SLOTS = (
    ("ACC_HEAD", "equipment_page.part_head"),
    ("ACC_CHEST", "equipment_page.part_top"),
    ("ACC_LEG", "equipment_page.part_bottom"),
    ("ACC_HAND", "equipment_page.part_glove"),
    ("ACC_FOOT", "equipment_page.part_shoe"),
)


# ============================================================
# 装备页 (含词条定制器)
# ============================================================
class EquipmentPage(QWidget):
    """装备: 左装备列表 + 右详情(属性+词条定制器)。词条可按属性筛选。"""

    def __init__(self, data, names, main_window):
        super().__init__()
        self.data = data
        self.names = names
        self.main_window = main_window
        # 加载 stat_names.json (主/副词条映射 + 属性类型)
        self.stat_names = self._load_stat_names()
        # 加载 equip_items.json (装备基底列表: 系列/部位)
        self.equip_items = self._load_equip_items()
        # 加载 equipment_exp.json (品质 -> 强化等级 -> 该档所需经验)
        self.enchant_exp = self._load_enchant_exp()
        # 加载 gem_stat.json (符文属性: {id: {s1, v1, s2, v2}})
        self.gem_stat = self._load_gem_stat()
        # 预构建按属性分组的词条缓存: stat_name -> [(id, display), ...]
        self._main_by_stat = {}   # stat_name -> list[(id, display)]
        self._sub_by_stat = {}    # stat_name -> list[(id, display)]
        self._main_all = []       # [(id, display)]
        self._sub_all = []        # [(id, display)]
        self._build_stat_cache()
        self._current_dbid = None
        self._mounted_slots = {}
        self._skip_delete_confirm = False  # 本次运行不再提示删除确认
        self._build()

    @staticmethod
    def _load_enchant_exp():
        """加载 equipment_exp.json; 失败返回 {}。
        结构: {NORMAL: {0: 100, 1: 300, ...}, SUPERIOR: {...}, ...}
        强化上限 = 该品质档位数-1 (NORMAL 3 / SUPERIOR 6 / RARE 9 / EPIC 12 / LEGENDARY 15)。
        经验规则: +L 装备 EXP = 档位 L-1 的 LevelMaxExp (已验证存档 21 件强化装备 0 误差)。
        """
        try:
            path = os.path.join(
                DATA_DIR,
                "equipment_exp.json",
            )
            if not os.path.exists(path):
                return {}
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _max_enchant(self, cid):
        """按装备品质返回强化上限 (档位数-1); 无规则时回退 15。"""
        grade = ""
        try:
            item = (self.equip_items or {}).get("item", {}).get(str(cid))
            if isinstance(item, dict):
                grade = str(item.get("grade") or "")
        except Exception:
            pass
        lvls = self.enchant_exp.get(grade)
        if isinstance(lvls, dict) and lvls:
            return max(int(k) for k in lvls)
        return 15

    def _exp_for_level(self, cid, level):
        """+L 装备应写入的 EXP = 档位 L-1 的 LevelMaxExp; L=0 -> 0。"""
        if level <= 0:
            return 0
        grade = ""
        try:
            item = (self.equip_items or {}).get("item", {}).get(str(cid))
            if isinstance(item, dict):
                grade = str(item.get("grade") or "")
        except Exception:
            pass
        lvls = self.enchant_exp.get(grade)
        if isinstance(lvls, dict) and str(level - 1) in lvls:
            return int(lvls[str(level - 1)])
        return 0

    @staticmethod
    def _load_stat_names():
        """加载 stat_names.json; 失败返回 {}。
        结构: {stat_key: {Attack: {name, stat_value, is_percentage}, ...},
               main_stat: {2311: {stat, name, ratio, weight}, ...},
               sub_stat: {20100: {stat, name, ratio, weight, memo}, ...}}
        """
        try:
            path = os.path.join(
                DATA_DIR,
                "stat_names.json",
            )
            if not os.path.exists(path):
                return {}
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _load_equip_items():
        """加载 equip_items.json (装备基底: {item: {cid: {series, grade, category}}}); 失败返回 {}。"""
        try:
            path = os.path.join(
                DATA_DIR,
                "equip_items.json",
            )
            if not os.path.exists(path):
                return {}
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _load_gem_stat():
        """加载 gem_stat.json (符文属性表, 由 GemNewStatData.table 导出)。
        结构: {STAT_INFO_CID: {"stat": StatList, "ratio": 档位 1/0.8/0.6}};
        失败返回 {} (符文列表属性列显示 "-")。"""
        try:
            path = os.path.join(
                DATA_DIR,
                "gem_stat.json",
            )
            if not os.path.exists(path):
                return {}
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _build_stat_cache(self):
        """预构建词条下拉缓存: (系列前缀, 属性名) 两级分组。
        系列规则: 装备 ITEM_CID 前3位 - 134 (136->2, 137->3, 138->4, 139->5)
        """
        if not self.stat_names:
            return
        stat_key = self.stat_names.get("stat_key", {})  # stat英文 -> 本地化名
        stat_cn = {}
        for k, v in stat_key.items():
            if isinstance(v, dict) and "name" in v:
                # 大小写无关匹配 (词条里 StatList 有驼峰/全大写混合, 如 MaxHP vs MAXHP)
                stat_cn[k.upper()] = localize_name(v["name"]) or k

        main_stat = self.stat_names.get("main_stat", {})
        sub_stat = self.stat_names.get("sub_stat", {})

        self._main_all = []
        self._sub_all = []
        self._main_by_stat = {}
        self._sub_by_stat = {}
        self._main_by_series = {}
        self._sub_by_series = {}

        # 主词条: 按 (系列前缀, 属性名) 分组
        for sid, info in main_stat.items():
            if not isinstance(info, dict):
                continue
            stat = info.get("stat", "")
            name = localize_name(info.get("name")) or f"#{sid}"
            disp = f"{sid} - {name}"
            series = str(sid)[0]
            self._main_all.append((sid, disp))
            grp = stat_cn.get(stat.upper(), name)
            self._main_by_stat.setdefault(grp, []).append((sid, disp))
            self._main_by_series.setdefault(series, []).append((sid, disp))

        # 副词条: 同上
        for sid, info in sub_stat.items():
            if not isinstance(info, dict):
                continue
            stat = info.get("stat", "")
            name = localize_name(info.get("name")) or f"#{sid}"
            disp = f"{sid} - {name}"
            series = str(sid)[0]
            self._sub_all.append((sid, disp))
            grp = stat_cn.get(stat.upper(), name)
            self._sub_by_stat.setdefault(grp, []).append((sid, disp))
            self._sub_by_series.setdefault(series, []).append((sid, disp))

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左: 搜索框 + 装备列表
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 6, 0)
        left_lay.setSpacing(4)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(str(i18n.tr("equipment_page.search")))
        self.search_box.textChanged.connect(self._on_search)
        left_lay.addWidget(self.search_box)
        self.character_combo = QComboBox()
        self.character_combo.currentIndexChanged.connect(self._on_character_changed)
        character_row = QHBoxLayout()
        character_row.addWidget(QLabel(str(i18n.tr("equipment_page.character_filter"))))
        character_row.addWidget(self.character_combo, 1)
        left_lay.addLayout(character_row)
        self.equip_list = QListWidget()
        self.equip_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.equip_list.currentRowChanged.connect(self._on_select)
        left_lay.addWidget(self.equip_list, 1)

        # 新增 / 删除按钮行
        btn_row = QHBoxLayout()
        add_btn = QPushButton(str(i18n.tr("equipment_page.add")))
        add_btn.setObjectName("primaryBtn")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._open_add_dialog)
        btn_row.addWidget(add_btn)
        del_btn = QPushButton(str(i18n.tr("equipment_page.delete")))
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(del_btn)
        left_lay.addLayout(btn_row)
        splitter.addWidget(left)

        # 右: 详情面板 (滚动)
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

    def reload(self):
        self.equip_list.clear()
        self.search_box.clear()
        self.character_combo.blockSignals(True)
        self.character_combo.clear()
        if not self.data.db_path:
            self._clear_layout(self.detail_lay)
            empty = QLabel(str(i18n.tr("equipment_page.no_equipment")))
            empty.setStyleSheet("color: #7f849c; font-size: 11pt;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.detail_lay.addWidget(empty)
            self.detail_lay.addStretch(1)
            self.character_combo.blockSignals(False)
            return
        try:
            # DELETED_DATE=0 表示未删除
            rows = self.data.select_all("tb_equipment", "DELETED_DATE=0")
        except Exception:
            rows = []
        # 按 ITEM_CID 排序
        rows = sorted(rows, key=lambda r: r["ITEM_CID"])
        self._all_rows = rows
        self._load_character_filter()
        self.character_combo.blockSignals(False)
        visible = self._filtered_rows()
        self._populate_list(visible)
        if visible:
            self.equip_list.setCurrentRow(0)
        else:
            self._clear_layout(self.detail_lay)
            empty = QLabel(str(i18n.tr("equipment_page.no_equipment")))
            empty.setStyleSheet("color: #7f849c; font-size: 11pt;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.detail_lay.addWidget(empty)
            self.detail_lay.addStretch(1)

    def _populate_list(self, rows):
        """填充装备列表 (每项: 名称 +强化, UserRole 存 ITEM_DBID)"""
        self.equip_list.clear()
        for r in rows:
            dbid = r["ITEM_DBID"]
            cid = r["ITEM_CID"]
            ench = r["ENCHANT_LEVEL"] or 0
            name = self.names.resolve("ITEM_CID", cid) or f"#{cid}"
            slot = self._mounted_slots.get(dbid)
            prefix = f"[{slot}] " if slot else ""
            text = f"{prefix}{name} +{ench}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, dbid)
            self.equip_list.addItem(item)

    def _on_search(self, text):
        """按名称/ID 过滤列表。"""
        text = text.strip().lower()
        source = self._filtered_rows()
        if not text:
            self._populate_list(source)
            return
        filtered = []
        for r in source:
            cid = r["ITEM_CID"]
            name = self.names.resolve("ITEM_CID", cid) or ""
            if text in str(name).lower() or text in str(cid):
                filtered.append(r)
        self._populate_list(filtered)

    def _load_character_filter(self):
        """Build character choices and ITEM_DBID -> equipped part mapping."""
        self.character_combo.addItem(str(i18n.tr("equipment_page.all_equipment")), None)
        try:
            characters = self.data.select_all(
                "tb_character", "USER_DBID=?", (USER_DBID,))
        except Exception:
            characters = []
        for row in sorted(characters, key=lambda value: value["CHARACTER_CID"]):
            cid = row["CHARACTER_CID"]
            name = self.names.resolve("CHARACTER_CID", cid) or f"#{cid}"
            self.character_combo.addItem(str(name), cid)

    def _filtered_rows(self):
        cid = self.character_combo.currentData()
        self._mounted_slots = {}
        if cid is None:
            return list(self._all_rows)
        try:
            mount = self.data.fetchone(
                "SELECT * FROM tb_equip_mount WHERE USER_DBID=? AND CHARACTER_CID=?",
                (USER_DBID, cid))
        except Exception:
            mount = None
        if mount is None:
            return []
        for column, name_key in MOUNT_SLOTS:
            dbid = mount[column]
            if dbid:
                self._mounted_slots[dbid] = str(i18n.tr(name_key))
        return [row for row in self._all_rows if row["ITEM_DBID"] in self._mounted_slots]

    def _on_character_changed(self, _index):
        self._current_dbid = None
        self._clear_layout(self.detail_lay)
        self._on_search(self.search_box.text())
        if self.equip_list.count():
            self.equip_list.setCurrentRow(0)
        else:
            empty = QLabel(str(i18n.tr("equipment_page.no_mounted_equipment")))
            empty.setStyleSheet("color: #7f849c; font-size: 11pt;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.detail_lay.addWidget(empty)
            self.detail_lay.addStretch(1)

    def _on_select(self, row_idx):
        if row_idx < 0:
            return
        it = self.equip_list.item(row_idx)
        if it is None:
            return
        dbid = it.data(Qt.ItemDataRole.UserRole)
        # 找到对应行数据
        row = None
        for r in self._all_rows:
            if r["ITEM_DBID"] == dbid:
                row = r
                break
        if row is None:
            return
        self._current_dbid = dbid
        self._render_detail(row)

    def _render_detail(self, r):
        """渲染装备详情面板。"""
        self._clear_layout(self.detail_lay)
        dbid = r["ITEM_DBID"]
        cid = r["ITEM_CID"]
        name = self.names.resolve("ITEM_CID", cid) or f"#{cid}"

        # 头部
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("font-size: 16pt; font-weight: 700; color: #7aa2f7;")
        self.detail_lay.addWidget(name_lbl)
        sub = QLabel(str(i18n.tr("equipment_page.dbid_fmt", dbid=dbid, cid=cid)))
        sub.setStyleSheet("color: #7f849c; font-size: 9pt;")
        self.detail_lay.addWidget(sub)

        # 属性区卡片
        attr_card, attr_lay = make_card(str(i18n.tr("equipment_page.detail")))
        form = QFormLayout()
        form.setSpacing(8)
        self._enchant_spin = QSpinBox()
        self._enchant_spin.setRange(0, self._max_enchant(cid))
        self._enchant_spin.setValue(r["ENCHANT_LEVEL"] or 0)
        self._enchant_spin.setFixedWidth(120)
        form.addRow(str(i18n.tr("equipment_page.enchant")), self._enchant_spin)

        self._lock_chk = QCheckBox(str(i18n.tr("equipment_page.locked")))
        self._lock_chk.setChecked(bool(r["IS_LOCK"]))
        self._lock_chk.setToolTip(str(i18n.tr("equipment_page.lock_tip")))
        form.addRow("", self._lock_chk)
        attr_lay.addLayout(form)
        self.detail_lay.addWidget(attr_card)

        # 词条区卡片
        stat_card, stat_lay = make_card(str(i18n.tr("equipment_page.main_stat")) + " / " +
                                        str(i18n.tr("equipment_page.sub_stat")))

        # 筛选属性下拉 (顶部)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel(str(i18n.tr("equipment_page.filter_stat"))))
        self.filter_combo = QComboBox()
        self.filter_combo.addItem(str(i18n.tr("equipment_page.all_stats")), "__all__")
        # 属性中文名列表 (来自 stat_key)
        if self.stat_names:
            stat_key = self.stat_names.get("stat_key", {})
            stat_cn_names = sorted({localize_name(v["name"]) for v in stat_key.values()
                                    if isinstance(v, dict) and "name" in v})
            for n in stat_cn_names:
                self.filter_combo.addItem(n, n)
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self.filter_combo, 1)
        stat_lay.addLayout(filter_row)

        # 主词条下拉
        self._main_combo = QComboBox()
        stat_lay.addWidget(QLabel(str(i18n.tr("equipment_page.main_stat"))))
        stat_lay.addWidget(self._main_combo)

        # 副词条 5 个下拉
        self._sub_combos = []
        for i in range(1, 6):
            sub_lbl = QLabel(f"{i18n.tr('equipment_page.sub_stat')} {i}")
            stat_lay.addWidget(sub_lbl)
            combo = QComboBox()
            self._sub_combos.append(combo)
            stat_lay.addWidget(combo)

        # 填充词条下拉 (初始全部)
        self._populate_stat_combos("__all__", r)

        self.detail_lay.addWidget(stat_card)

        # 符文槽卡片
        self._render_gem_card(r)

        # 应用按钮
        apply_btn = QPushButton(str(i18n.tr("equipment_page.apply")))
        apply_btn.setObjectName("primaryBtn")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.clicked.connect(self._apply)
        self.detail_lay.addWidget(apply_btn)
        self.detail_lay.addStretch(1)

    # ---------- 符文槽 ----------
    def _render_gem_card(self, r):
        """渲染符文槽卡片: 槽位状态 + 开放/关闭切换 + 持有符文列表 + 已镌刻展示。"""
        dbid = r["ITEM_DBID"]
        gem_dbid = r["GEM_DBID"] or 0

        card, lay = make_card(str(i18n.tr("equipment_page.gem_title")))

        # 1. 槽位状态行
        status_row = QHBoxLayout()
        # 语义: 0=未开放, 1=已开放未镌刻, 大数=已开放且已镌刻 (符文实例 ITEM_DBID)
        opened = gem_dbid != 0
        status_lbl = QLabel(str(i18n.tr("equipment_page.gem_opened" if opened
                                         else "equipment_page.gem_closed")))
        status_lbl.setStyleSheet(
            "color: #98c379; font-weight: 600;" if opened else "color: #7f849c;")
        status_row.addWidget(status_lbl)
        status_row.addStretch(1)
        # 开放/关闭按钮仅 0/1 状态显示; 已镌刻(大数)状态由下方"拆卸符文"按钮管理
        if gem_dbid in (0, 1):
            toggle_btn = QPushButton(str(i18n.tr("equipment_page.gem_close" if gem_dbid == 1
                                                 else "equipment_page.gem_open")))
            toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            toggle_btn.clicked.connect(lambda: self._toggle_gem_socket(dbid, gem_dbid))
            status_row.addWidget(toggle_btn)
        lay.addLayout(status_row)

        # 2. 解锁说明 (需精工工具, 显示当前持有数)
        tool_count = self._tool_count()
        tool_name = self.names.resolve("ITEM_CID", GEM_TOOL_CID) or f"#{GEM_TOOL_CID}"
        hint = QLabel(str(i18n.tr("equipment_page.gem_hint",
                                  tool=tool_name, count=tool_count)))
        hint.setStyleSheet("color: #7f849c; font-size: 9pt;")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        if tool_count <= 0:
            warn = QLabel(str(i18n.tr("equipment_page.gem_need_tool")))
            warn.setStyleSheet("color: #e0af68; font-size: 9pt;")
            warn.setWordWrap(True)
            lay.addWidget(warn)

        # 3. 已镌刻符文 (GEM_DBID 既非 0 也非 1: 未来镌刻后可能是符文实例 ITEM_DBID 大数)
        if gem_dbid not in (0, 1):
            engraved = self._engraved_gem_name(gem_dbid)
            eng_row = QHBoxLayout()
            eng_lbl = QLabel(str(i18n.tr("equipment_page.gem_engraved")) +
                             f": {engraved}")
            eng_lbl.setStyleSheet("color: #e0af68; font-size: 9pt;")
            eng_lbl.setWordWrap(True)
            eng_row.addWidget(eng_lbl, 1)
            detach_btn = QPushButton(str(i18n.tr("equipment_page.gem_detach")))
            detach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            detach_btn.clicked.connect(lambda: self._detach_gem(dbid, engraved))
            eng_row.addWidget(detach_btn)
            lay.addLayout(eng_row)

        # 3.5 镌刻操作区 (槽已开放未镌刻: GEM_DBID == 1)
        if gem_dbid == 1:
            engrave_row = QHBoxLayout()
            engrave_row.addWidget(QLabel(str(i18n.tr("equipment_page.gem_engrave_hint"))))
            self._gem_combo = QComboBox()
            # 过滤: 已被其他装备镌刻的符文实例不能重复镌刻
            engraved_ids = self._engraved_gem_ids()
            gems = [g for g in self._owned_gems()
                    if g["ITEM_DBID"] not in engraved_ids]
            for g in gems:
                g_cid = g["ITEM_CID"]
                g_name = self.names.resolve("ITEM_CID", g_cid) or f"#{g_cid}"
                g_dbid = g["ITEM_DBID"]
                self._gem_combo.addItem(
                    f"{str(g_dbid)[-6:]} {g_name}  {self._gem_effect_text(g['STAT_INFO_CID'])}",
                    g_dbid)
            engrave_btn = QPushButton(str(i18n.tr("equipment_page.gem_engrave")))
            engrave_btn.setObjectName("primaryBtn")
            engrave_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            engrave_btn.setEnabled(len(gems) > 0)
            engrave_btn.clicked.connect(lambda: self._engrave_gem(dbid))
            engrave_row.addWidget(self._gem_combo, 1)
            engrave_row.addWidget(engrave_btn)
            lay.addLayout(engrave_row)
            if not gems:
                none_lbl2 = QLabel(str(i18n.tr("equipment_page.gem_engrave_none")))
                none_lbl2.setStyleSheet("color: #7f849c; font-size: 9pt;")
                lay.addWidget(none_lbl2)

        # 4. 持有符文列表
        lay.addWidget(QLabel(str(i18n.tr("equipment_page.gem_owned"))))
        gems = self._owned_gems()
        if not gems:
            none_lbl = QLabel(str(i18n.tr("equipment_page.gem_none")))
            none_lbl.setStyleSheet("color: #7f849c; font-size: 9pt;")
            lay.addWidget(none_lbl)
        else:
            table = QTableWidget()
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels([
                str(i18n.tr("table.column_name")),
                str(i18n.tr("equipment_page.gem_effect")),
            ])
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setAlternatingRowColors(True)
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setStretchLastSection(True)
            table.setRowCount(len(gems))
            for i, g in enumerate(gems):
                cid = g["ITEM_CID"]
                gname = self.names.resolve("ITEM_CID", cid) or f"#{cid}"
                table.setItem(i, 0, QTableWidgetItem(gname))
                table.setItem(i, 1, QTableWidgetItem(self._gem_effect_text(g["STAT_INFO_CID"])))
            table.resizeColumnsToContents()
            table.setColumnWidth(0, max(table.columnWidth(0), 160))
            lay.addWidget(table)

        self.detail_lay.addWidget(card)

    def _toggle_gem_socket(self, dbid, cur_value):
        """切换符文槽开放/关闭 (GEM_DBID 0<->1); 完成后重建详情。"""
        new_value = 0 if cur_value == 1 else 1
        try:
            self.data.execute(
                "UPDATE tb_equipment SET GEM_DBID=? WHERE ITEM_DBID=?",
                (new_value, dbid))
        except Exception as ex:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
            return
        self.main_window.set_status(str(i18n.tr("equipment_page.gem_updated")))
        # 重新查询该行 (sqlite3.Row 不可变, 不能原地改 GEM_DBID), 再重建详情刷新状态
        row = None
        try:
            rows = self.data.select_all("tb_equipment", "ITEM_DBID=?", (dbid,))
            if rows:
                row = rows[0]
        except Exception:
            row = None
        if row is None:
            for rr in self._all_rows:
                if rr["ITEM_DBID"] == dbid:
                    row = rr
                    break
        if row is not None:
            self._render_detail(row)

    def _engrave_gem(self, dbid):
        """镌刻符文: 把选中符文实例 ITEM_DBID 写入装备 GEM_DBID; 完成后重建详情。"""
        if self.data.db_path is None:
            return
        combo = getattr(self, "_gem_combo", None)
        if combo is None or combo.currentData() is None:
            return
        rune_dbid = combo.currentData()
        # 符文名 (供状态栏提示)
        rune_name = str(rune_dbid)
        try:
            rows = self.data.select_all("tb_gem", "ITEM_DBID=?", (rune_dbid,))
            if rows:
                cid = rows[0]["ITEM_CID"]
                rune_name = self.names.resolve("ITEM_CID", cid) or f"#{cid}"
        except Exception:
            pass
        try:
            self.data.execute(
                "UPDATE tb_equipment SET GEM_DBID=? WHERE ITEM_DBID=?",
                (rune_dbid, dbid))
        except Exception as ex:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
            return
        self.main_window.set_status(str(i18n.tr("equipment_page.gem_engraved_done",
                                                name=rune_name)))
        self._rerender_gem_detail(dbid)

    def _detach_gem(self, dbid, rune_name):
        """拆卸符文: GEM_DBID 恢复为 1 (槽保留); 确认后执行并重建详情。"""
        if self.data.db_path is None:
            return
        if QMessageBox.question(
                self, str(i18n.tr("dialogs.confirm")),
                str(i18n.tr("equipment_page.gem_detach_confirm", name=rune_name))
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.data.execute(
                "UPDATE tb_equipment SET GEM_DBID=1 WHERE ITEM_DBID=?",
                (dbid,))
        except Exception as ex:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
            return
        self.main_window.set_status(str(i18n.tr("equipment_page.gem_detached")))
        self._rerender_gem_detail(dbid)

    def _rerender_gem_detail(self, dbid):
        """重新查询装备行并重建详情 (sqlite3.Row 不可变, 用于镌刻/拆卸后刷新)。"""
        row = None
        try:
            rows = self.data.select_all("tb_equipment", "ITEM_DBID=?", (dbid,))
            if rows:
                row = rows[0]
        except Exception:
            row = None
        if row is None:
            for rr in self._all_rows:
                if rr["ITEM_DBID"] == dbid:
                    row = rr
                    break
        if row is not None:
            self._render_detail(row)

    def _tool_count(self):
        """精工工具 (1450408) 当前持有数; 查失败返回 0。"""
        if not self.data.db_path:
            return 0
        try:
            row = self.data.fetchone(
                "SELECT STACK_CNT FROM tb_stackable_item WHERE USER_DBID=? AND ITEM_CID=?",
                (USER_DBID, GEM_TOOL_CID))
            return int(row[0] or 0) if row else 0
        except Exception:
            return 0

    def _owned_gems(self):
        """已拥有符文 (tb_gem 未删除行), 按 ITEM_CID 排序。"""
        if not self.data.db_path:
            return []
        try:
            rows = self.data.select_all("tb_gem", "DELETED_DATE=0")
        except Exception:
            return []
        return sorted(rows, key=lambda r: r["ITEM_CID"])

    def _engraved_gem_ids(self):
        """所有已被装备镌刻的符文实例 ITEM_DBID 集合 (tb_equipment.GEM_DBID 非 0/1 值)。
        同一个符文实例不能被镌刻到两件装备上, 镌刻下拉需过滤这些。"""
        ids = set()
        if not self.data.db_path:
            return ids
        try:
            rows = self.data.select_all("tb_equipment")
            for r in rows:
                g = r["GEM_DBID"]
                if g and g != 1:      # 0=未开放, 1=已开放未镌刻, 大数=已镌刻实例
                    ids.add(g)
        except Exception:
            pass
        return ids

    def _engraved_gem_name(self, gem_dbid):
        """按 GEM_DBID 尝试在 tb_gem 匹配符文实例 (ITEM_DBID=GEM_DBID); 匹配不到显示原值。"""
        if not self.data.db_path:
            return str(gem_dbid)
        try:
            rows = self.data.select_all("tb_gem", "ITEM_DBID=?", (gem_dbid,))
            if rows:
                cid = rows[0]["ITEM_CID"]
                return self.names.resolve("ITEM_CID", cid) or f"#{cid}"
        except Exception:
            pass
        return str(gem_dbid)

    def _gem_effect_text(self, stat_cid):
        """符文属性类型: 按实例 STAT_INFO_CID 查 gem_stat (GemNewStatData).
        gem_stat.json: {STAT_INFO_CID: {"stat": StatList, "ratio": 档位}};
        只显示属性类型 (游戏内数值由客户端公式计算, 数据表未导出, 以游戏为准);
        无数据返回 "-" (如旧版写入的 STAT_INFO_CID=0 死数据)。"""
        info = (self.gem_stat or {}).get(str(stat_cid))
        if not info:
            return "-"
        name = self._gem_stat_cn(info.get("stat")) or info.get("stat")
        return str(name) if name else "-"

    def _gem_stat_cn(self, stat):
        """属性英文名 -> 本地化名 (stat_names.stat_key, 大小写无关匹配); 找不到返回原英文。"""
        if not self.stat_names:
            return None
        sk = self.stat_names.get("stat_key", {})
        key = stat.upper()
        for k, v in sk.items():
            if isinstance(v, dict) and "name" in v and k.upper() == key:
                return localize_name(v["name"])
        return None

    def _populate_stat_combos(self, filter_stat, row):
        """填充主/副词条下拉。filter_stat='__all__' 显示全部, 否则按属性名筛选。
        只显示该装备系列(ITEM_CID)对应的词条; 当前词条若被筛选隐藏仍保留显示。
        """
        # 系列前缀: ITEM_CID 前3位 - 134 (136->2, 137->3, 138->4, 139->5)
        series = None
        try:
            cid_str = str(row.get("ITEM_CID", 0))
            if len(cid_str) >= 3:
                series = str(int(cid_str[:3]) - 134)
        except Exception:
            series = None

        def pick(all_items, by_stat, by_series):
            pool = by_series.get(series, all_items) if series else all_items
            if filter_stat == "__all__":
                return list(pool)
            pool_ids = {it[0] for it in pool}
            return [it for it in by_stat.get(filter_stat, []) if it[0] in pool_ids]

        # 主词条数据源
        main_items = pick(self._main_all, self._main_by_stat, self._main_by_series)
        # 副词条数据源
        sub_items = pick(self._sub_all, self._sub_by_stat, self._sub_by_series)

        # 当前装备的主词条
        cur_main = row["MAIN_STAT_CID"]
        cur_subs = [row[f"SUB_STAT_CID{i}"] for i in range(1, 6)]

        # --- 主词条下拉 ---
        self._main_combo.blockSignals(True)
        self._main_combo.clear()
        # 确保当前项在列表里
        main_ids = {it[0] for it in main_items}
        if cur_main and str(cur_main) not in main_ids:
            cur_name = localize_name((self.stat_names.get("main_stat", {})
                                      .get(str(cur_main), {}).get("name"))) or f"#{cur_main}"
            main_items.insert(0, (str(cur_main), f"{cur_main} - {cur_name} (current)"))
        for sid, disp in main_items:
            self._main_combo.addItem(disp, sid)
        # 选中当前值
        idx = self._main_combo.findData(str(cur_main))
        if idx >= 0:
            self._main_combo.setCurrentIndex(idx)
        self._main_combo.blockSignals(False)

        # --- 副词条下拉 ---
        for i, combo in enumerate(self._sub_combos):
            combo.blockSignals(True)
            combo.clear()
            # 副词条可清空 (0=无)
            combo.addItem(str(i18n.tr("equipment_page.none")), "0")
            sub_ids = {it[0] for it in sub_items}
            cur_sv = cur_subs[i]
            if cur_sv and str(cur_sv) not in sub_ids:
                cur_name = localize_name((self.stat_names.get("sub_stat", {})
                                          .get(str(cur_sv), {}).get("name"))) or f"#{cur_sv}"
                sub_items_list = list(sub_items)
                sub_items_list.insert(0, (str(cur_sv), f"{cur_sv} - {cur_name} (current)"))
            else:
                sub_items_list = sub_items
            for sid, disp in sub_items_list:
                combo.addItem(disp, sid)
            # 选中当前值 (0 表示无)
            target = str(cur_sv) if cur_sv else "0"
            idx = combo.findData(target)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.blockSignals(False)

    def _on_filter_changed(self, _idx):
        """属性筛选变化 -> 重新填充词条下拉 (保留当前选中装备的值)。"""
        if self._current_dbid is None:
            return
        # 找到当前装备行
        row = None
        for r in self._all_rows:
            if r["ITEM_DBID"] == self._current_dbid:
                row = r
                break
        if row is None:
            return
        filter_stat = self.filter_combo.currentData()
        self._populate_stat_combos(filter_stat, row)

    def _apply(self):
        """应用装备修改: 写 ENCHANT_LEVEL/IS_LOCK/MAIN_STAT_CID/SUB_STAT_CID1-5。
        EXP 字段不再暴露 (无经验规则表), 保持原值不动。
        """
        if self._current_dbid is None:
            return
        dbid = self._current_dbid
        ench = self._enchant_spin.value()
        is_lock = 1 if self._lock_chk.isChecked() else 0
        main_stat = self._main_combo.currentData()
        sub_stats = [combo.currentData() for combo in self._sub_combos]

        # 强化等级与 EXP 联动: EXP = 上一档 LevelMaxExp (按品质), 否则游戏加载会回退强化
        cid = 0
        for r in self._all_rows:
            if r["ITEM_DBID"] == dbid:
                cid = r["ITEM_CID"]
                break
        exp = self._exp_for_level(cid, ench)

        sets = [
            '"ENCHANT_LEVEL"=?', '"EXP"=?', '"IS_LOCK"=?',
            '"MAIN_STAT_CID"=?',
            '"SUB_STAT_CID1"=?', '"SUB_STAT_CID2"=?', '"SUB_STAT_CID3"=?',
            '"SUB_STAT_CID4"=?', '"SUB_STAT_CID5"=?',
        ]
        vals = [ench, exp, is_lock, int(main_stat) if main_stat else 0]
        for sv in sub_stats:
            vals.append(int(sv) if sv else 0)
        vals.append(dbid)
        sql = ("UPDATE tb_equipment SET " + ", ".join(sets)
               + " WHERE ITEM_DBID=?")
        try:
            self.data.execute(sql, vals)
        except Exception as ex:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
            return
        self.main_window.set_status(str(i18n.tr("equipment_page.updated")))

    def _delete_selected(self):
        """删除选中的装备 (支持多选), 确认后执行。"""
        if not self.data.db_path:
            return
        items = self.equip_list.selectedItems()
        if not items:
            QMessageBox.information(
                self, str(i18n.tr("dialogs.confirm")),
                str(i18n.tr("equipment_page.select_first")))
            return
        n = len(items)
        # 确认 (支持"本次运行不再提示")
        if not self._skip_delete_confirm:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle(str(i18n.tr("dialogs.confirm")))
            msg.setText(str(i18n.tr("equipment_page.delete_confirm", n=n)))
            chk = QCheckBox(str(i18n.tr("equipment_page.no_confirm_again")))
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
        dbids = [it.data(Qt.ItemDataRole.UserRole) for it in items]
        try:
            for dbid in dbids:
                self.data.execute("DELETE FROM tb_equipment WHERE ITEM_DBID=?", (dbid,))
        except Exception as ex:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
            return
        self.main_window.set_status(str(i18n.tr("equipment_page.deleted", n=n)))
        self.reload()

    def _open_add_dialog(self):
        """打开"新增装备"对话框: 选基底装备/主词条/副词条/强化等级。"""
        if not self.data.db_path:
            return
        dlg = AddEquipmentDialog(self.names, self.stat_names, self.equip_items, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.result_data()
            new_dbid = self._new_item_dbid()
            try:
                self.data.execute(
                    "INSERT INTO tb_equipment (ITEM_DBID, USER_DBID, ITEM_CID, "
                    "ENCHANT_LEVEL, EXP, IS_LOCK, GEM_DBID, MAIN_STAT_CID, "
                    "SUB_STAT_CID1, SUB_STAT_CID2, SUB_STAT_CID3, SUB_STAT_CID4, "
                    "SUB_STAT_CID5, CREATED_DATE, DELETED_DATE) "
                    "VALUES (?,?,?,?,?,0,0,?,?,?,?,?,?,?,0)",
                    (new_dbid, USER_DBID, data["item_cid"], data["enchant"],
                     data.get("enchant_exp", 0),
                     data["main"], *data["subs"], int(time.time())),
                )
            except Exception as ex:
                QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
                return
            self.main_window.set_status(str(i18n.tr("equipment_page.added")))
            self.reload()

    def _new_item_dbid(self):
        """生成不冲突的 ITEM_DBID (时间戳<<28 | 随机28位, 56位内, 查询确认唯一)。"""
        import random
        while True:
            v = (int(time.time()) << 28) | random.getrandbits(28)
            exists = self.data.select_all("tb_equipment", "ITEM_DBID=?", (v,))
            if not exists:
                return v

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
# 新增装备对话框
# ============================================================
class AddEquipmentDialog(QDialog):
    """新增装备: 选系列/部位/基底装备/主词条/副词条/强化等级。"""

    PART_MAP = [("1300", "equipment_page.part_head"),
                ("1301", "equipment_page.part_top"),
                ("1302", "equipment_page.part_bottom"),
                ("1303", "equipment_page.part_glove"),
                ("1304", "equipment_page.part_shoe")]

    def __init__(self, names, stat_names, equip_items, parent=None):
        super().__init__(parent)
        self.names = names
        self.stat_names = stat_names
        self.equip_items = equip_items.get("item", {}) if equip_items else {}
        # 强化经验规则 (从父页 EquipmentPage 继承)
        self.enchant_exp = {}
        if parent is not None and hasattr(parent, "enchant_exp"):
            self.enchant_exp = parent.enchant_exp
        self.setWindowTitle(str(i18n.tr("equipment_page.add_title")))
        self.setMinimumWidth(480)
        self._build()
        self._refresh_equips()

    def _max_enchant_for(self, cid):
        """按基底装备品质返回强化上限; 无规则回退 15。"""
        grade = ""
        try:
            v = self.equip_items.get(str(cid))
            if isinstance(v, dict):
                grade = str(v.get("grade") or "")
        except Exception:
            pass
        lvls = self.enchant_exp.get(grade)
        if isinstance(lvls, dict) and lvls:
            return max(int(k) for k in lvls)
        return 15

    def _exp_for(self, cid, level):
        """+L 应写入 EXP = 上一档 LevelMaxExp"""
        if level <= 0:
            return 0
        grade = ""
        try:
            v = self.equip_items.get(str(cid))
            if isinstance(v, dict):
                grade = str(v.get("grade") or "")
        except Exception:
            pass
        lvls = self.enchant_exp.get(grade)
        if isinstance(lvls, dict) and str(level - 1) in lvls:
            return int(lvls[str(level - 1)])
        return 0
    def _build(self):
        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        self.series_combo = QComboBox()
        for s in ["2", "3", "4", "5"]:
            self.series_combo.addItem(str(i18n.tr("equipment_page.series_fmt",
                                                  series=s)), s)
        self.series_combo.currentIndexChanged.connect(self._on_series_part_changed)
        form.addRow(str(i18n.tr("equipment_page.series")), self.series_combo)

        self.part_combo = QComboBox()
        for cat, key in self.PART_MAP:
            self.part_combo.addItem(str(i18n.tr(key)), cat)
        self.part_combo.currentIndexChanged.connect(self._on_series_part_changed)
        form.addRow(str(i18n.tr("equipment_page.part")), self.part_combo)

        self.equip_combo = QComboBox()
        form.addRow(str(i18n.tr("equipment_page.base_equip")), self.equip_combo)

        self.main_combo = QComboBox()
        form.addRow(str(i18n.tr("equipment_page.main_stat")), self.main_combo)

        self.sub_combos = []
        for i in range(1, 6):
            c = QComboBox()
            self.sub_combos.append(c)
            form.addRow(f"{i18n.tr('equipment_page.sub_stat')} {i}", c)

        self.enchant_spin = QSpinBox()
        self.enchant_spin.setRange(0, 15)  # 选择装备后按品质刷新
        form.addRow(str(i18n.tr("equipment_page.enchant")), self.enchant_spin)

        lay.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _on_series_part_changed(self, *_):
        self._refresh_equips()

    def _refresh_equips(self):
        """刷新基底装备列表 (当前系列+部位) 与词条下拉。"""
        series = self.series_combo.currentData()
        part = self.part_combo.currentData()
        self.equip_combo.clear()
        cids = [cid for cid, v in self.equip_items.items()
                if v.get("series") == series and str(v.get("category", "")) == part]
        for cid in sorted(cids):
            name = localize_name(self.names.resolve("ITEM_CID", int(cid))) or f"#{cid}"
            self.equip_combo.addItem(f"{cid} - {name}", cid)
        # 选择变化后按品质刷新强化上限
        self.equip_combo.currentIndexChanged.connect(self._on_equip_changed)
        self._refresh_stats()
        self._on_equip_changed()

    def _on_equip_changed(self, *_):
        """按当前选中基底装备的品质设置强化上限。"""
        cid = self.equip_combo.currentData()
        if cid:
            self.enchant_spin.setRange(0, self._max_enchant_for(int(cid)))

    def _refresh_stats(self):
        """刷新主/副词条下拉 (当前系列)。"""
        series = self.series_combo.currentData()
        main_stat = self.stat_names.get("main_stat", {})
        sub_stat = self.stat_names.get("sub_stat", {})
        self.main_combo.clear()
        for sid, info in sorted(main_stat.items()):
            if str(sid)[0] != series:
                continue
            name = localize_name(info.get("name")) or f"#{sid}"
            self.main_combo.addItem(f"{sid} - {name}", sid)
        for c in self.sub_combos:
            c.clear()
            c.addItem(str(i18n.tr("equipment_page.none")), "0")
            for sid, info in sorted(sub_stat.items()):
                if str(sid)[0] != series:
                    continue
                name = localize_name(info.get("name")) or f"#{sid}"
                c.addItem(f"{sid} - {name}", sid)

    def result_data(self):
        cid = int(self.equip_combo.currentData())
        return {
            "item_cid": cid,
            "main": int(self.main_combo.currentData()),
            "subs": [int(c.currentData()) for c in self.sub_combos],
            "enchant": self.enchant_spin.value(),
            "enchant_exp": self._exp_for(cid, self.enchant_spin.value()),
        }
