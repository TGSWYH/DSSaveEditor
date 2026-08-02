# -*- coding: utf-8 -*-
"""角色养成页 (CharacterPage): 左角色列表 + 右编辑面板 + 高级原始表格。

从 ui_main 拆出。
"""

import os
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget,
    QListWidgetItem, QScrollArea, QFrame, QCheckBox, QLabel, QLineEdit,
    QFormLayout, QPushButton, QSpinBox, QMessageBox,
)

from . import i18n
from .datasource import USER_DBID, localize_name
from .ui_common import make_card
from .ui_tools import TablePanel


# ============================================================
# 角色养成页
# ============================================================
class CharacterPage(QWidget):
    """角色养成: 左角色列表 + 右编辑面板 + 高级原始表格。"""

    def __init__(self, data, names, main_window):
        super().__init__()
        self.data = data
        self.names = names
        self.main_window = main_window
        self._current_cid = None
        # 加载技能名映射 (skill_names.json, 同目录, 缺失则空)
        self.skill_names = self._load_skill_names()
        # 加载等级->经验映射 (level_exp.json, 改等级时自动匹配经验)
        self.level_exp = self._load_level_exp()
        self._skill_spins = {}  # type_value -> QSpinBox
        self._build()

    @staticmethod
    def _load_skill_names():
        """加载 skill_names.json; 失败返回 {}。
        结构: {char_cid_str: {type_value_str: {name, slot_order, slot_type, skill_type, max_level}}}
        """
        try:
            path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "skill_names.json",
            )
            if not os.path.exists(path):
                return {}
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

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

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左: 角色列表
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 6, 0)
        left_lay.setSpacing(4)
        self.char_list = QListWidget()
        self.char_list.currentRowChanged.connect(self._on_select)
        left_lay.addWidget(self.char_list)
        splitter.addWidget(left)

        # 右: 编辑面板 (滚动)
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(6, 0, 0, 0)
        right_lay.setSpacing(8)

        self.edit_scroll = QScrollArea()
        self.edit_scroll.setWidgetResizable(True)
        self.edit_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.edit_container = QWidget()
        self.edit_lay = QVBoxLayout(self.edit_container)
        self.edit_lay.setContentsMargins(0, 0, 0, 0)
        self.edit_lay.setSpacing(8)
        self.edit_scroll.setWidget(self.edit_container)
        right_lay.addWidget(self.edit_scroll, 1)

        # 高级开关
        adv_row = QHBoxLayout()
        adv_row.addStretch(1)
        self.adv_chk = QCheckBox(str(i18n.tr("character_page.advanced")))
        self.adv_chk.toggled.connect(self._on_advanced)
        adv_row.addWidget(self.adv_chk)
        right_lay.addLayout(adv_row)

        # 高级区 (原始表格)
        self.adv_container = QWidget()
        self.adv_lay = QVBoxLayout(self.adv_container)
        self.adv_lay.setContentsMargins(0, 0, 0, 0)
        self.adv_container.setVisible(False)
        right_lay.addWidget(self.adv_container, 2)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([260, 700])
        outer.addWidget(splitter, 1)

    def reload(self):
        self.char_list.clear()
        try:
            rows = self.data.select_all("tb_character", "USER_DBID=?", (USER_DBID,))
        except Exception:
            rows = []
        self._rows = rows
        if not rows:
            self._clear_layout(self.edit_lay)
            empty = QLabel(str(i18n.tr("character_page.no_data")))
            empty.setStyleSheet("color: #7f849c; font-size: 11pt;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.edit_lay.addWidget(empty)
            self.edit_lay.addStretch(1)
            return
        for r in rows:
            cid = r["CHARACTER_CID"]
            cname = self.names.resolve("CHARACTER_CID", cid)
            disp = cname if cname else f"#{cid}"
            item = QListWidgetItem(f"{disp}  (Lv.{r['LEVEL']})")
            item.setData(Qt.ItemDataRole.UserRole, cid)
            self.char_list.addItem(item)
        # 默认选第一个
        self.char_list.setCurrentRow(0)

    def _on_select(self, row_idx):
        if row_idx < 0 or row_idx >= len(self._rows):
            return
        r = self._rows[row_idx]
        self._current_cid = r["CHARACTER_CID"]
        self._render_edit(r)

    def select_character(self, cid):
        """供 MainWindow 调用: 选中指定 cid 的角色。"""
        for i in range(self.char_list.count()):
            it = self.char_list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == cid:
                self.char_list.setCurrentRow(i)
                return

    def _render_edit(self, r):
        self._clear_layout(self.edit_lay)
        cid = r["CHARACTER_CID"]
        cname = self.names.resolve("CHARACTER_CID", cid)
        name_text = cname if cname else f"#{cid}"
        name_lbl = QLabel(name_text)
        name_lbl.setStyleSheet("font-size: 16pt; font-weight: 700; color: #7aa2f7;")
        self.edit_lay.addWidget(name_lbl)

        sub = QLabel(f"CHARACTER_CID = {cid}")
        sub.setStyleSheet("color: #7f849c; font-size: 9pt;")
        self.edit_lay.addWidget(sub)

        self._char_entries = {}
        fields = [
            ("LEVEL", i18n.tr("character.level")),
            ("TRANSCEND", i18n.tr("character.transcend")),
        ]
        form = QFormLayout()
        form.setSpacing(8)
        for col, label in fields:
            if col == "TRANSCEND":
                # 超越: 限制 0~6
                e = QSpinBox()
                e.setRange(0, 6)
                e.setFixedWidth(120)
                e.setValue(r[col] or 0)
                form.addRow(str(label), e)
            else:
                e = QLineEdit()
                e.setFixedWidth(180)
                v = r[col]
                e.setText("" if v is None else str(v))
                if col == "LEVEL":
                    # 等级修改时经验自动匹配 + 飞升自动计算
                    hint = QLabel(str(i18n.tr("character_page.exp_auto")))
                    hint.setStyleSheet("color: #7f849c; font-size: 8pt;")
                    row_box = QWidget()
                    row_lay = QHBoxLayout(row_box)
                    row_lay.setContentsMargins(0, 0, 0, 0)
                    row_lay.setSpacing(6)
                    row_lay.addWidget(e)
                    row_lay.addWidget(hint)
                    form.addRow(str(label), row_box)
                else:
                    form.addRow(str(label), e)
            self._char_entries[col] = e
        self.edit_lay.addLayout(form)

        apply_btn = QPushButton(str(i18n.tr("character_page.apply")))
        apply_btn.setObjectName("primaryBtn")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.clicked.connect(self._apply)

        max_btn = QPushButton(str(i18n.tr("character_page.max_all")))
        max_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        max_btn.clicked.connect(self._max_all)

        btn_row = QHBoxLayout()
        btn_row.addWidget(apply_btn)
        btn_row.addWidget(max_btn)
        btn_row.addStretch(1)
        self.edit_lay.addLayout(btn_row)

        # 技能等级编辑区
        self._build_skill_section(cid)
        self.edit_lay.addStretch(1)

    def _build_skill_section(self, cid):
        """构建技能等级编辑区: 每技能一行 (名称 + 当前等级 + QSpinBox + 应用)。
        排序: 普通技能按 slot_order 升序, MASTER 技能排最后并加 ★ 标记。
        """
        # 读 tb_skill_growth 当前等级
        cur_levels = {}
        try:
            rows = self.data.select_all(
                "tb_skill_growth",
                "USER_DBID=? AND CHARACTER_CID=?",
                (USER_DBID, cid),
            )
            for r in rows:
                cur_levels[r["TYPE_VALUE"]] = r["SLOT_LEVEL"]
        except Exception:
            rows = []

        # 技能元信息 (来自 skill_names.json), key 是字符串
        meta = self.skill_names.get(str(cid), {}) if self.skill_names else {}

        # 合并: 数据库里有的 + 映射里有的 (取并集, 以 TYPE_VALUE 为 key)
        all_tvs = set(cur_levels.keys()) | set(int(k) for k in meta.keys())

        # 排序: 普通技能按 slot_order 升序, MASTER 排最后
        def sort_key(tv):
            info = meta.get(str(tv), {})
            is_master = info.get("skill_type", "") == "MASTER"
            slot_order = info.get("slot_order", 999)
            return (1 if is_master else 0, slot_order, tv)

        sorted_tvs = sorted(all_tvs, key=sort_key)

        # 卡片容器
        card, lay = make_card(str(i18n.tr("character_page.skills")))
        self._skill_spins = {}
        self._skill_checks = {}

        if not sorted_tvs:
            empty = QLabel(str(i18n.tr("character_page.skill_none")))
            empty.setStyleSheet("color: #7f849c;")
            lay.addWidget(empty)
        else:
            for tv in sorted_tvs:
                info = meta.get(str(tv), {})
                name = localize_name(info.get("name")) or f"技能 {tv}"
                max_level = info.get("max_level", 10) or 10
                is_master = info.get("skill_type", "") == "MASTER"
                disp_name = ("★ " + name) if is_master else name
                cur_lv = cur_levels.get(tv, 0) or 0

                row = QHBoxLayout()
                name_lbl = QLabel(disp_name)
                name_lbl.setMinimumWidth(140)
                if is_master:
                    name_lbl.setStyleSheet("color: #f9e2af; font-weight: 600;")
                row.addWidget(name_lbl)

                if is_master:
                    # 大师技: 点亮制, 有记录(=1)即已点亮, 用 checkbox 表示
                    chk = QCheckBox(str(i18n.tr("character_page.master_lit")))
                    chk.setChecked(cur_lv >= 1)
                    chk.setMinimumWidth(90)
                    row.addWidget(chk)
                    self._skill_checks[tv] = chk
                else:
                    cur_lbl = QLabel(f"Lv.{cur_lv}")
                    cur_lbl.setStyleSheet("color: #7f849c;")
                    cur_lbl.setMinimumWidth(50)
                    row.addWidget(cur_lbl)

                    spin = QSpinBox()
                    if max_level <= 1:
                        # 被动/固定技能 (如闪避): 不可修改等级
                        spin.setRange(0, 1)
                        spin.setValue(cur_lv if cur_lv >= 0 else 0)
                        spin.setEnabled(False)
                        spin.setToolTip(str(i18n.tr("character_page.skill_fixed")))
                    else:
                        # 普通技能: 0=未学习, 1..max_level
                        spin.setRange(0, max_level)
                        spin.setValue(cur_lv if cur_lv >= 0 else 0)
                    spin.setFixedWidth(90)
                    row.addWidget(spin)
                    self._skill_spins[tv] = spin

                apply_one = QPushButton(str(i18n.tr("character_page.skill_apply")))
                apply_one.setCursor(Qt.CursorShape.PointingHandCursor)
                apply_one.clicked.connect(lambda _=False, t=tv: self._apply_one_skill(t))
                row.addWidget(apply_one)
                row.addStretch(1)
                lay.addLayout(row)

            # 全部应用
            all_btn = QPushButton(str(i18n.tr("character_page.skill_all")))
            all_btn.setObjectName("primaryBtn")
            all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            all_btn.clicked.connect(self._apply_all_skills)
            lay.addWidget(all_btn)

        self.edit_lay.addWidget(card)

    def _apply_one_skill(self, type_value):
        """应用单个技能 (普通技能: upsert 等级; 大师技: 勾选点亮/取消删除)。"""
        if self._current_cid is None:
            return
        cid = self._current_cid
        # 大师技: checkbox 点亮制
        chk = self._skill_checks.get(type_value)
        if chk is not None:
            try:
                if chk.isChecked():
                    self.data.execute(
                        "INSERT OR REPLACE INTO tb_skill_growth "
                        "(USER_DBID, CHARACTER_CID, TYPE_VALUE, SLOT_LEVEL) VALUES (?,?,?,1)",
                        (USER_DBID, cid, type_value),
                    )
                else:
                    self.data.execute(
                        "DELETE FROM tb_skill_growth "
                        "WHERE USER_DBID=? AND CHARACTER_CID=? AND TYPE_VALUE=?",
                        (USER_DBID, cid, type_value),
                    )
            except Exception as ex:
                QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
                return
            self.main_window.set_status(
                str(i18n.tr("character_page.skill_updated"))
                + f" (TV={type_value} "
                + (str(i18n.tr("character_page.master_lit")) if chk.isChecked() else str(i18n.tr("character_page.master_off")))
                + ")"
            )
            return
        spin = self._skill_spins.get(type_value)
        if spin is None:
            return
        lv = spin.value()
        try:
            if lv <= 0:
                # 0 = 未学习, 删除记录
                self.data.execute(
                    "DELETE FROM tb_skill_growth "
                    "WHERE USER_DBID=? AND CHARACTER_CID=? AND TYPE_VALUE=?",
                    (USER_DBID, cid, type_value),
                )
            else:
                self.data.execute(
                    "INSERT OR REPLACE INTO tb_skill_growth "
                    "(USER_DBID, CHARACTER_CID, TYPE_VALUE, SLOT_LEVEL) VALUES (?,?,?,?)",
                    (USER_DBID, cid, type_value, lv),
                )
        except Exception as ex:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
            return
        self.main_window.set_status(
            str(i18n.tr("character_page.skill_updated")) + f" (TV={type_value} -> {lv})"
        )

    def _apply_all_skills(self):
        """应用所有技能 (普通技能逐条 upsert, 大师技按勾选点亮/删除)。"""
        if self._current_cid is None:
            return
        cid = self._current_cid
        try:
            # 普通技能
            for tv, spin in self._skill_spins.items():
                lv = spin.value()
                if lv <= 0:
                    # 0 = 未学习, 删除记录
                    self.data.execute(
                        "DELETE FROM tb_skill_growth "
                        "WHERE USER_DBID=? AND CHARACTER_CID=? AND TYPE_VALUE=?",
                        (USER_DBID, cid, tv),
                    )
                else:
                    self.data.execute(
                        "INSERT OR REPLACE INTO tb_skill_growth "
                        "(USER_DBID, CHARACTER_CID, TYPE_VALUE, SLOT_LEVEL) VALUES (?,?,?,?)",
                        (USER_DBID, cid, tv, lv),
                    )
            # 大师技 (点亮制)
            for tv, chk in self._skill_checks.items():
                if chk.isChecked():
                    self.data.execute(
                        "INSERT OR REPLACE INTO tb_skill_growth "
                        "(USER_DBID, CHARACTER_CID, TYPE_VALUE, SLOT_LEVEL) VALUES (?,?,?,1)",
                        (USER_DBID, cid, tv),
                    )
                else:
                    self.data.execute(
                        "DELETE FROM tb_skill_growth "
                        "WHERE USER_DBID=? AND CHARACTER_CID=? AND TYPE_VALUE=?",
                        (USER_DBID, cid, tv),
                    )
        except Exception as ex:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
            return
        self.main_window.set_status(str(i18n.tr("character_page.skill_updated")))

    def _apply(self):
        if self._current_cid is None:
            return
        cid = self._current_cid
        sets, vals = [], []
        new_level = None
        for col, _label in [
            ("LEVEL", None), ("TRANSCEND", None),
        ]:
            e = self._char_entries.get(col)
            if e is None:
                continue
            if col == "TRANSCEND":
                # QSpinBox 0~6
                v = e.value()
            else:
                raw = e.text().strip()
                if raw == "":
                    continue
                try:
                    v = int(raw)
                except ValueError:
                    QMessageBox.warning(self, str(i18n.tr("status.error")),
                                         f"{cid} {col}: {raw}")
                    return
            if col == "LEVEL":
                new_level = v
            sets.append(f'"{col}"=?')
            vals.append(v)
        if not sets:
            return
        # 等级变化时, 经验自动匹配 level_exp.json (规则: LEVEL=L -> EXP=表[L-1])
        if new_level is not None and self.level_exp:
            exp = self.level_exp.get(str(new_level))
            if exp is not None:
                sets.append('"EXP"=?')
                vals.append(int(exp))
            # 飞升随等级自动计算 (关隘: 0~20=0, 20~30=1, ..., 60~70=5)
            ascend = max(0, min(5, (new_level - 1) // 10 - 1))
            sets.append('"ASCEND"=?')
            vals.append(ascend)
        vals.extend([USER_DBID, cid])
        sql = ("UPDATE tb_character SET " + ", ".join(sets)
               + " WHERE USER_DBID=? AND CHARACTER_CID=?")
        try:
            self.data.execute(sql, vals)
        except Exception as ex:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
            return
        self.main_window.set_status(str(i18n.tr("character_page.modified")))

    def _max_all(self):
        """一键满级: 等级->70 + 经验匹配 + 飞升->5 + 点亮全部技能。"""
        if self._current_cid is None:
            return
        cid = self._current_cid
        if QMessageBox.question(
                self, str(i18n.tr("dialogs.confirm")),
                str(i18n.tr("character_page.max_all_confirm"))
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            # 1. 等级/经验/飞升
            exp = int(self.level_exp.get("70", 0)) if self.level_exp else 0
            self.data.execute(
                "UPDATE tb_character SET LEVEL=70, EXP=?, ASCEND=5 "
                "WHERE USER_DBID=? AND CHARACTER_CID=?",
                (exp, USER_DBID, cid))
            # 2-3. 技能 (普通技能 -> max_level, 大师技 -> 1)
            meta = self.skill_names.get(str(cid), {}) if self.skill_names else {}
            for tv, info in meta.items():
                skill_type = info.get("skill_type", "")
                if skill_type == "MASTER":
                    slot_lv = 1
                elif skill_type == "SKILL":
                    slot_lv = info.get("max_level", 1) or 1
                else:
                    continue
                self.data.execute(
                    "INSERT OR REPLACE INTO tb_skill_growth "
                    "(USER_DBID, CHARACTER_CID, TYPE_VALUE, SLOT_LEVEL) VALUES (?,?,?,?)",
                    (USER_DBID, cid, int(tv), slot_lv))
        except Exception as ex:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
            return
        self.main_window.set_status(str(i18n.tr("character_page.max_all_done")))
        # 重新取当前行并重建编辑区 (刷新等级/技能显示)
        try:
            rows = self.data.select_all(
                "tb_character", "USER_DBID=? AND CHARACTER_CID=?", (USER_DBID, cid))
            if rows:
                self._render_edit(rows[0])
        except Exception:
            pass

    def _on_advanced(self, checked):
        if not checked:
            self.adv_container.setVisible(False)
            return
        self._clear_layout(self.adv_lay)
        self.adv_container.setVisible(True)
        self.adv_lay.addWidget(TablePanel(self.data, self.names, "tb_character", self.main_window))

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
