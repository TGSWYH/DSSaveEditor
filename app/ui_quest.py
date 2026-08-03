# -*- coding: utf-8 -*-
"""任务系统 UI: 通用任务页 (列表+详情 / 表格直改 双模式) + 区域任务页 (表格+批量)。

QuestPage   : main/epic/character/grade/other 通用模板 (QSplitter 左列表右详情,
              组批量完成, 记录卡面板, 表格模式勾选批量)。
RegionQuestPage: 区域任务 147 个 (表格 + 完成次数编辑 + 批量操作)。

所有修改都调用 QuestManager 方法 (内存库), 由主窗口"保存修改"统一写回。
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QComboBox, QSpinBox, QCheckBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFrame, QScrollArea, QStackedWidget, QFormLayout,
)

from . import i18n
from .datasource import localize_name
from .ui_common import make_card as _make_card, _clear_layout


# 状态徽标 (内联样式, 主题 QSS 全局生效)
_BADGE_QSS = {
    "done": ("background: #1f3d2b; color: #98c379; border: 1px solid #98c379;"
             " border-radius: 9px; padding: 2px 10px; font-weight: 600;"),
    "hold": ("background: #4d3a22; color: #e0af68; border: 1px solid #e0af68;"
             " border-radius: 9px; padding: 2px 10px; font-weight: 600;"),
    "none": ("background: #2f3346; color: #9aa0b4; border: 1px solid #565b70;"
             " border-radius: 9px; padding: 2px 10px; font-weight: 600;"),
}


# ============================================================
# 通用任务页 (列表 + 详情 / 表格直改)
# ============================================================
class QuestPage(QWidget):
    """任务页模板: page_key = 'main'/'epic'/'character'/'grade'/'other'。

    列表模式: 左侧按线分组列表 + 右侧详情 (状态操作 + 记录卡面板)。
    表格模式: 全任务表格 + 底部勾选批量操作。
    """

    def __init__(self, data, names, main_window, quest_mgr, page_key):
        super().__init__()
        self.data = data
        self.names = names
        self.main_window = main_window
        self.qm = quest_mgr
        self.page_key = page_key
        self._lines = []          # [(key, name, [qid...])]
        self._qid_group = {}      # qid -> 线 key
        self._line_names = {}     # key -> 显示名 (含"第N章"等)
        self._completed = {}      # {db_category: set(cid)}
        self._holds = {}          # {cid: {step, cnt, tracking}}
        self._card_orders = {}    # {card_id: reward_order}
        self._selected_qid = None
        self._mode = "list"       # 'list' | 'table'
        self._card_lbls = {}      # card_id -> QLabel
        self._card_bases = {}     # card_id -> 卡名文本
        self._build()
        self.reload()

    # ---------- 布局 ----------
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        # 顶行: 搜索 + 视图切换
        top = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(str(i18n.tr("quest_page.search")))
        self.search_box.textChanged.connect(self._on_search)
        top.addWidget(self.search_box, 1)
        self.view_btn = QPushButton(str(i18n.tr("quest_page.view_table")))
        self.view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_btn.clicked.connect(self._toggle_view)
        top.addWidget(self.view_btn)
        outer.addLayout(top)

        # 状态筛选
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel(str(i18n.tr("quest_page.state"))))
        self.filter_combo = QComboBox()
        self.filter_combo.addItem(str(i18n.tr("quest_page.all")), "all")
        self.filter_combo.addItem(str(i18n.tr("quest_page.done")), "done")
        self.filter_combo.addItem(str(i18n.tr("quest_page.hold")), "hold")
        self.filter_combo.addItem(str(i18n.tr("quest_page.none")), "none")
        self.filter_combo.currentIndexChanged.connect(self._on_filter)
        filter_row.addWidget(self.filter_combo)
        filter_row.addStretch(1)
        outer.addLayout(filter_row)

        # 内容: 列表模式 / 表格模式
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        self._build_list_mode()
        self._build_table_mode()
        self.stack.setCurrentIndex(0)

    def _build_list_mode(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧: 列表 + 组快捷操作
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 6, 0)
        left_lay.setSpacing(4)
        self.quest_list = QListWidget()
        self.quest_list.currentRowChanged.connect(self._on_list_select)
        left_lay.addWidget(self.quest_list, 1)

        group_row = QHBoxLayout()
        self.group_combo = QComboBox()
        group_row.addWidget(self.group_combo, 1)
        self.group_done_btn = QPushButton(str(i18n.tr("quest_page.group_done")))
        self.group_done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.group_done_btn.clicked.connect(lambda: self._on_group_action(True))
        group_row.addWidget(self.group_done_btn)
        self.group_reset_btn = QPushButton(str(i18n.tr("quest_page.group_reset")))
        self.group_reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.group_reset_btn.clicked.connect(lambda: self._on_group_action(False))
        group_row.addWidget(self.group_reset_btn)
        left_lay.addLayout(group_row)
        splitter.addWidget(left)

        # 右侧: 详情滚动区
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
        splitter.setSizes([300, 700])
        self._splitter = splitter
        self.stack.addWidget(splitter)

    def _build_table_mode(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        # 铺满策略: 首列勾选列固定 36px, 其余列按内容自适应, 最后一列拉伸填满
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.table.cellDoubleClicked.connect(self._on_table_dbl)
        lay.addWidget(self.table, 1)

        batch = QHBoxLayout()
        self.batch_done_btn = QPushButton(str(i18n.tr("quest_page.batch_done")))
        self.batch_done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.batch_done_btn.clicked.connect(self._batch_done)
        batch.addWidget(self.batch_done_btn)
        self.batch_hold_btn = QPushButton(str(i18n.tr("quest_page.batch_hold")))
        self.batch_hold_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.batch_hold_btn.clicked.connect(self._batch_hold)
        batch.addWidget(self.batch_hold_btn)
        self.batch_reset_btn = QPushButton(str(i18n.tr("quest_page.batch_reset")))
        self.batch_reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.batch_reset_btn.clicked.connect(self._batch_reset)
        batch.addWidget(self.batch_reset_btn)
        self.select_all_btn = QPushButton(str(i18n.tr("quest_page.select_all")))
        self.select_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_all_btn.clicked.connect(self._select_all)
        batch.addWidget(self.select_all_btn)
        batch.addStretch(1)
        lay.addLayout(batch)
        self.stack.addWidget(page)

    # ---------- 数据加载 ----------
    def reload(self):
        self._load_states()
        self._rebuild_lines()
        self._rebuild_group_combo()
        self._rebuild_list()
        self._rebuild_table()

    def _load_states(self):
        if self.data.conn is None:
            self._completed, self._holds = {}, {}
            self._card_orders = {}
            return
        self._completed, self._holds = self.qm.load_states()
        self._card_orders = self.qm.load_card_orders()

    def _rebuild_lines(self):
        page = self.page_key
        if page == "epic":
            lines = []
            for cid, line in self.qm.epic_lines.items():
                ids = [str(x) for x in line.get("quests", [])
                       if not self.qm.is_hidden(x)]
                t = localize_name(line.get("title")) or ""
                s = localize_name(line.get("subtitle")) or ""
                name = (" · ".join(x for x in (t, s) if x)) or str(cid)
                lines.append((str(cid), name, ids))
            self._lines = lines
        else:
            self._lines = self.qm.lines_of(page)
        self._qid_group = {}
        self._line_names = {}
        for key, name, ids in self._lines:
            self._line_names[key] = self._plain_group_label(key, name)
            for qid in ids:
                self._qid_group[qid] = key

    def _plain_group_label(self, key, name):
        if self.page_key == "main" and isinstance(name, int):
            return str(i18n.tr("quest_page.chapter_fmt", n=name))
        if self.page_key == "unreleased":
            # 未开放任务: 单组无名称, 显示页面标题
            return str(i18n.tr("quest.nav_unreleased"))
        if name:
            return str(name)
        return str(i18n.tr("quest_page.all"))

    def _group_header(self, key, name, ids):
        return f"── {self._plain_group_label(key, name)} ({len(ids)}) ──"

    def _rebuild_group_combo(self):
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        for key, name, ids in self._lines:
            if not ids:
                continue
            self.group_combo.addItem(
                f"{self._plain_group_label(key, name)} ({len(ids)})", key)
        self.group_combo.blockSignals(False)

    # ---------- 筛选 ----------
    def _visible_quests(self):
        """按状态筛选 + 搜索词返回可见 qid 列表 (保持线顺序)。"""
        f = self.filter_combo.currentData()
        kw = self.search_box.text().strip().lower()
        out = []
        for key, _name, ids in self._lines:
            for qid in ids:
                if f != "all":
                    st, _ = self.qm.quest_state(self._completed, self._holds, qid)
                    if f == "done" and st != "done":
                        continue
                    if f == "hold" and st != "hold":
                        continue
                    if f == "none" and st != "none":
                        continue
                if kw:
                    nm = self.qm.qname(qid) or ""
                    if kw not in str(qid) and kw not in str(nm).lower():
                        continue
                out.append(qid)
        return out

    # ---------- 列表 ----------
    def _rebuild_list(self):
        self.quest_list.clear()
        if self.data.conn is None:
            it = QListWidgetItem(str(i18n.tr("quest_page.no_db")))
            it.setFlags(Qt.ItemFlag.NoItemFlags)
            it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.quest_list.addItem(it)
            self._visible_qids = []
            self._enabled(False)
            return
        visible = self._visible_quests()
        self._visible_qids = visible
        vset = set(visible)
        prev = self._selected_qid
        first_task_row = None
        for key, name, ids in self._lines:
            vis = [q for q in ids if q in vset]
            if not vis:
                continue
            head = QListWidgetItem(self._group_header(key, name, ids))
            head.setFlags(Qt.ItemFlag.NoItemFlags)
            head.setForeground(QColor("#7f849c"))
            self.quest_list.addItem(head)
            for qid in vis:
                st, _ = self.qm.quest_state(self._completed, self._holds, qid)
                nm = self.qm.qname(qid) or f"ID {qid}"
                prefix = "✅ " if st == "done" else ("🔄 " if st == "hold" else "")
                item = QListWidgetItem(f"{prefix}{qid} {nm}")
                item.setData(Qt.ItemDataRole.UserRole, qid)
                self.quest_list.addItem(item)
                if first_task_row is None:
                    first_task_row = self.quest_list.count() - 1
        # 恢复选中
        if prev and prev in vset:
            for i in range(self.quest_list.count()):
                it = self.quest_list.item(i)
                if it and it.data(Qt.ItemDataRole.UserRole) == prev:
                    self.quest_list.setCurrentRow(i)
                    break
        elif first_task_row is not None:
            self.quest_list.setCurrentRow(first_task_row)
        else:
            self._selected_qid = None
        self._enabled(True)

    def _enabled(self, on):
        self.group_done_btn.setEnabled(on)
        self.group_reset_btn.setEnabled(on)
        self.group_combo.setEnabled(on)
        self.batch_done_btn.setEnabled(on)
        self.batch_hold_btn.setEnabled(on)
        self.batch_reset_btn.setEnabled(on)
        self.select_all_btn.setEnabled(on)

    def _on_list_select(self, row):
        if row < 0:
            return
        it = self.quest_list.item(row)
        if it is None:
            return
        qid = it.data(Qt.ItemDataRole.UserRole)
        if qid is None:
            return  # 组头
        self._selected_qid = qid
        key = self._qid_group.get(qid)
        if key is not None:
            idx = self.group_combo.findData(key)
            if idx >= 0:
                self.group_combo.blockSignals(True)
                self.group_combo.setCurrentIndex(idx)
                self.group_combo.blockSignals(False)
        self._render_detail()

    # ---------- 详情 ----------
    def _render_detail(self):
        _clear_layout(self.detail_lay)
        if self.data.conn is None:
            lbl = QLabel(str(i18n.tr("quest_page.no_db")))
            lbl.setStyleSheet("color: #7f849c; font-size: 12pt;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.detail_lay.addWidget(lbl)
            self.detail_lay.addStretch(1)
            return
        qid = self._selected_qid
        if not qid:
            lbl = QLabel(str(i18n.tr("quest_page.no_selection")))
            lbl.setStyleSheet("color: #7f849c; font-size: 12pt;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.detail_lay.addWidget(lbl)
            self.detail_lay.addStretch(1)
            return
        meta = self.qm.q(qid)
        st, det = self.qm.quest_state(self._completed, self._holds, qid)
        name = self.qm.qname(qid) or f"ID {qid}"

        # 标题 + 状态徽标
        title_row = QHBoxLayout()
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("font-size: 15pt; font-weight: 700; color: #7aa2f7;")
        name_lbl.setWordWrap(True)
        title_row.addWidget(name_lbl, 1)
        badge = QLabel(self._state_text(st))
        badge.setStyleSheet(_BADGE_QSS[st])
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_row.addWidget(badge)
        self.detail_lay.addLayout(title_row)

        # 信息卡
        info_card, info_lay = _make_card("")
        form = QFormLayout()
        form.setSpacing(6)
        form.addRow(str(i18n.tr("quest_page.category")),
                    QLabel(str(meta.get("category") or meta.get("db_category") or "-")))
        form.addRow("ID", QLabel(str(qid)))
        key = self._qid_group.get(qid)
        form.addRow(str(i18n.tr("quest_page.line")),
                    QLabel(str(self._line_names.get(key, "-"))))
        form.addRow(str(i18n.tr("quest_page.steps_range")),
                    QLabel(self._steps_text(meta)))
        form.addRow(str(i18n.tr("quest_page.pre")), QLabel(self._pre_text(meta)))
        form.addRow(str(i18n.tr("quest_page.post")), QLabel(self._post_text(meta)))
        info_lay.addLayout(form)
        self.detail_lay.addWidget(info_card)

        # 状态操作卡
        self._render_status_card(qid, meta, st, det)

        # 记录卡面板 (仅 epic/main)
        if self.page_key in ("epic", "main"):
            self._render_card_panel()

        self.detail_lay.addStretch(1)

    @staticmethod
    def _state_text(st):
        if st == "done":
            return str(i18n.tr("quest_page.state_done"))
        if st == "hold":
            return str(i18n.tr("quest_page.state_hold"))
        return str(i18n.tr("quest_page.state_none"))

    def _steps_text(self, meta):
        steps = meta.get("steps")
        if not steps:
            return str(i18n.tr("quest_page.no_steps"))
        smin = steps.get("min", 0)
        smax = steps.get("max", 0)
        cnt = steps.get("count") or max(0, smax - smin + 1)
        return str(i18n.tr("quest_page.steps_fmt", min=smin, max=smax, count=cnt))

    def _pre_text(self, meta):
        pre = meta.get("pre") or []
        if not pre:
            return "-"
        parts = [self.qm.qname(p) or f"ID {p}" for p in pre]
        return " / ".join(parts)

    def _post_text(self, meta):
        nxt = meta.get("next")
        if not nxt:
            return "-"
        return self.qm.qname(nxt) or f"ID {nxt}"

    def _render_status_card(self, qid, meta, st, det):
        card, lay = _make_card(str(i18n.tr("quest_page.state")))
        form = QFormLayout()
        form.setSpacing(6)

        self.status_combo = QComboBox()
        self.status_combo.addItem(str(i18n.tr("quest_page.state_none")), "none")
        self.status_combo.addItem(str(i18n.tr("quest_page.state_hold")), "hold")
        self.status_combo.addItem(str(i18n.tr("quest_page.state_done")), "done")
        self.status_combo.setCurrentIndex({"none": 0, "hold": 1, "done": 2}[st])
        self.status_combo.currentIndexChanged.connect(self._on_state_changed)
        form.addRow(str(i18n.tr("quest_page.state")), self.status_combo)

        # 进行中控件 (步骤 / 进度 / 追踪)
        self.hold_widget = QWidget()
        hw = QFormLayout(self.hold_widget)
        hw.setContentsMargins(0, 0, 0, 0)
        hw.setSpacing(6)
        steps = meta.get("steps")
        self.step_combo = QComboBox()
        if steps:
            smin = steps.get("min", 0)
            smax = steps.get("max", 0)
            for n in range(smin, smax + 1):
                self.step_combo.addItem(str(i18n.tr("quest_page.step_fmt", n=n)), n)
            self.progress_spin = QSpinBox()
            self.progress_spin.setRange(0, steps.get("max_cnt", 0) or 0)
        else:
            # 无步骤数据: 只给 0/1
            self.step_combo.addItem("0", 0)
            self.step_combo.addItem("1", 1)
            self.progress_spin = QSpinBox()
            self.progress_spin.setRange(0, 1)
        if det:
            cur = det.get("step", 0)
            idx = self.step_combo.findData(cur)
            if idx >= 0:
                self.step_combo.setCurrentIndex(idx)
            self.progress_spin.setValue(det.get("cnt", 0))
        else:
            # 默认取该步 max_cnt (全任务最大)
            self.progress_spin.setValue(self.progress_spin.maximum())
        hw.addRow(str(i18n.tr("quest_page.step")), self.step_combo)
        hw.addRow(str(i18n.tr("quest_page.progress")), self.progress_spin)
        self.tracking_chk = QCheckBox(str(i18n.tr("quest_page.tracking")))
        self.tracking_chk.setChecked(bool(det and det.get("tracking")))
        hw.addRow("", self.tracking_chk)
        if not steps:
            note = QLabel(str(i18n.tr("quest_page.no_steps")))
            note.setStyleSheet("color: #7f849c; font-size: 9pt;")
            lay.addWidget(note)

        # 已完成提示
        self.done_hint = QLabel(str(i18n.tr("quest_page.done_hint")))
        self.done_hint.setStyleSheet("color: #e0af68; font-size: 9pt;")
        self.done_hint.setWordWrap(True)

        self.apply_btn = QPushButton(str(i18n.tr("quest_page.apply")))
        self.apply_btn.setObjectName("primaryBtn")
        self.apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_btn.clicked.connect(self._on_apply)

        lay.addLayout(form)
        lay.addWidget(self.hold_widget)
        lay.addWidget(self.done_hint)
        lay.addWidget(self.apply_btn)
        self._sync_status_visibility()
        self.detail_lay.addWidget(card)

    def _sync_status_visibility(self):
        mode = self.status_combo.currentData()
        self.hold_widget.setVisible(mode == "hold")
        self.done_hint.setVisible(mode == "done")

    def _on_state_changed(self, _idx):
        self._sync_status_visibility()

    def _on_apply(self):
        qid = self._selected_qid
        if not qid:
            return
        meta = self.qm.q(qid)
        mode = self.status_combo.currentData()
        if mode == "done":
            self.qm.set_complete(qid, meta.get("db_category"))
            msg = "quest_page.updated_done"
        elif mode == "hold":
            step = self.step_combo.currentData()
            cnt = self.progress_spin.value()
            tracking = 1 if self.tracking_chk.isChecked() else 0
            self.qm.set_hold(qid, step, cnt, tracking)
            msg = "quest_page.updated_hold"
        else:
            self.qm.reset_quest(qid)
            msg = "quest_page.updated_reset"
        self.main_window.set_status(str(i18n.tr(msg)))
        self._load_states()
        self._sync_card_orders()
        self._rebuild_list()
        self._rebuild_table()

    # ---------- 记录卡面板 (epic/main) ----------
    def _render_card_panel(self):
        self._card_lbls = {}
        self._card_bases = {}
        cards = []
        if self.page_key == "epic":
            for cid, line in self.qm.epic_lines.items():
                cards.append((int(cid), line))
        else:  # main: record_groups['1'] 8 张卡
            for c in self.qm.record_groups.get("1", []):
                cards.append((c.get("card_id"), c))
        if not cards:
            return
        frame, lay = _make_card(str(i18n.tr("quest_page.card_progress")))
        top = QHBoxLayout()
        hint = QLabel(str(i18n.tr("quest_page.card_sync_hint")))
        hint.setStyleSheet("color: #7f849c; font-size: 9pt;")
        hint.setWordWrap(True)
        top.addWidget(hint, 1)
        sync_btn = QPushButton(str(i18n.tr("quest_page.card_sync")))
        sync_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sync_btn.clicked.connect(self._sync_card_orders)
        top.addWidget(sync_btn)
        lay.addLayout(top)
        for card_id, line in cards:
            row = QHBoxLayout()
            t = localize_name(line.get("title")) or ""
            s = localize_name(line.get("subtitle")) or ""
            base = (" · ".join(x for x in (t, s) if x)) or f"ID {card_id}"
            maxo = line.get("max_order", 0) or 0
            order = self._card_orders.get(int(card_id), 0)
            lbl = QLabel(f"{base}  {order}/{maxo}")
            lbl.setStyleSheet("color: #c0c5dc;")
            lbl.setWordWrap(True)
            row.addWidget(lbl, 1)
            inc = QPushButton(str(i18n.tr("quest_page.card_inc")))
            inc.setFixedWidth(64)
            inc.setCursor(Qt.CursorShape.PointingHandCursor)
            inc.clicked.connect(lambda _=False, c=int(card_id): self._card_adjust(c, +1))
            row.addWidget(inc)
            dec = QPushButton(str(i18n.tr("quest_page.card_dec")))
            dec.setFixedWidth(64)
            dec.setCursor(Qt.CursorShape.PointingHandCursor)
            dec.clicked.connect(lambda _=False, c=int(card_id): self._card_adjust(c, -1))
            row.addWidget(dec)
            lay.addLayout(row)
            self._card_lbls[int(card_id)] = lbl
            self._card_bases[int(card_id)] = base
        self.detail_lay.addWidget(frame)

    def _card_adjust(self, card_id, delta):
        if self.data.conn is None:
            return
        c = self.qm.card_by_id(card_id)
        maxo = (c or {}).get("max_order", 0) or 0
        cur = self._card_orders.get(card_id, 0)
        new = max(0, min(maxo, cur + delta))
        if new == cur:
            return
        if new == 0:
            self.qm.reset_card_order(card_id)
        else:
            self.qm.set_card_order(card_id, new)
        self._card_orders[card_id] = new
        base = self._card_bases.get(card_id, f"ID {card_id}")
        self._card_lbls[card_id].setText(f"{base}  {new}/{maxo}")
        self.main_window.set_status(str(i18n.tr("quest_page.card_updated")))

    # ---------- 记录卡档位联动 ----------
    def _cards(self):
        """本页记录卡 [(card_id, card), ...]; 仅 epic/main 页有"""
        if self.page_key == "epic":
            return [(int(cid), line) for cid, line in self.qm.epic_lines.items()]
        if self.page_key == "main":
            return [(c.get("card_id"), c) for c in self.qm.record_groups.get("1", [])]
        return []

    def _sync_card_orders(self, _checked=False):
        """按任务完成状态重算记录卡档位 (档位 = 卡内已完成任务数)。
        在修改任务后调用, 保证卡面板进度与任务状态一致。"""
        if self.data.conn is None:
            return False
        changed = False
        for card_id, card in self._cards():
            new = self.qm.card_order_from_state(card, self._completed, self._holds)
            maxo = card.get("max_order", 0) or 0
            new = max(0, min(maxo, new))
            cur = self._card_orders.get(int(card_id), 0)
            if new == cur:
                continue
            if new == 0:
                self.qm.reset_card_order(int(card_id))
            else:
                self.qm.set_card_order(int(card_id), new)
            self._card_orders[int(card_id)] = new
            lbl = self._card_lbls.get(int(card_id))
            if lbl is not None:
                base = self._card_bases.get(int(card_id), f"ID {card_id}")
                lbl.setText(f"{base}  {new}/{maxo}")
            changed = True
        if changed:
            self.main_window.set_status(str(i18n.tr("quest_page.card_synced")))
        return changed

    # ---------- 表格模式 ----------
    def _rebuild_table(self):
        self.table.clear()
        headers = ["", str(i18n.tr("quest_page.state")), "ID",
                   str(i18n.tr("quest_page.name")), str(i18n.tr("quest_page.line")),
                   str(i18n.tr("quest_page.step")), str(i18n.tr("quest_page.progress"))]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        if self.data.conn is None:
            self.table.setRowCount(0)
            return
        visible = self._visible_quests()
        self.table.setRowCount(len(visible))
        for i, qid in enumerate(visible):
            st, det = self.qm.quest_state(self._completed, self._holds, qid)
            # 勾选
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(i, 0, chk)
            # 状态
            if st == "done":
                st_txt = "✅ " + str(i18n.tr("quest_page.state_done"))
            elif st == "hold":
                st_txt = ("🔄 " + str(i18n.tr("quest_page.state_hold")) + " " +
                          str(i18n.tr("quest_page.step_fmt", n=det.get("step", 0))))
            else:
                st_txt = str(i18n.tr("quest_page.state_none"))
            self.table.setItem(i, 1, QTableWidgetItem(st_txt))
            # ID
            id_it = QTableWidgetItem(str(qid))
            id_it.setData(Qt.ItemDataRole.UserRole, qid)
            self.table.setItem(i, 2, id_it)
            # 名称
            self.table.setItem(i, 3, QTableWidgetItem(self.qm.qname(qid) or f"ID {qid}"))
            # 所属线
            key = self._qid_group.get(qid)
            self.table.setItem(i, 4, QTableWidgetItem(str(self._line_names.get(key, "-"))))
            # 步骤
            step_txt = str(det.get("step", 0)) if st == "hold" else "-"
            self.table.setItem(i, 5, QTableWidgetItem(step_txt))
            # 进度
            prog_txt = str(det.get("cnt", 0)) if st == "hold" else "-"
            self.table.setItem(i, 6, QTableWidgetItem(prog_txt))
        # 铺满: 首列勾选固定 36px, 中间列按内容自适应, 末列拉伸填满
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        self.table.setColumnWidth(0, 36)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        for c in range(1, self.table.columnCount() - 1):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.table.columnCount() - 1,
                                    QHeaderView.ResizeMode.Stretch)

    def _on_table_dbl(self, row, _col):
        if row < 0 or row >= self.table.rowCount():
            return
        it = self.table.item(row, 2)
        if it is None:
            return
        qid = it.data(Qt.ItemDataRole.UserRole)
        if qid is None:
            return
        self._switch_to_list(qid)

    def _switch_to_list(self, qid):
        self._mode = "list"
        self.stack.setCurrentIndex(0)
        self.view_btn.setText(str(i18n.tr("quest_page.view_table")))
        self._selected_qid = qid
        self._rebuild_list()
        if qid not in self._visible_qids:
            return
        for i in range(self.quest_list.count()):
            it = self.quest_list.item(i)
            if it and it.data(Qt.ItemDataRole.UserRole) == qid:
                self.quest_list.setCurrentRow(i)
                break

    def _toggle_view(self):
        if self._mode == "list":
            self._mode = "table"
            self.stack.setCurrentIndex(1)
            self.view_btn.setText(str(i18n.tr("quest_page.view_list")))
            self._rebuild_table()
        else:
            self._switch_to_list(self._selected_qid)

    # ---------- 批量操作 ----------
    def _checked_qids(self):
        out = []
        for i in range(self.table.rowCount()):
            it = self.table.item(i, 0)
            if it and it.checkState() == Qt.CheckState.Checked:
                id_it = self.table.item(i, 2)
                if id_it and id_it.data(Qt.ItemDataRole.UserRole):
                    out.append(id_it.data(Qt.ItemDataRole.UserRole))
        return out

    def _batch_done(self):
        qids = self._checked_qids()
        if not qids:
            self.main_window.set_status(str(i18n.tr("quest_page.select_first")))
            return
        for qid in qids:
            self.qm.set_complete(qid, self.qm.q(qid).get("db_category"))
        self._after_batch(i18n.tr("quest_page.batch_applied", n=len(qids)))

    def _batch_hold(self):
        qids = self._checked_qids()
        if not qids:
            self.main_window.set_status(str(i18n.tr("quest_page.select_first")))
            return
        for qid in qids:
            steps = self.qm.q(qid).get("steps")
            if steps:
                step = 1 if (steps.get("min", 0) <= 1 <= steps.get("max", 1)) \
                    else steps.get("min", 0)
                cnt = steps.get("max_cnt", 0) or 0
            else:
                step, cnt = 0, 0
            self.qm.set_hold(qid, step, cnt)
        self._after_batch(i18n.tr("quest_page.batch_applied", n=len(qids)))

    def _batch_reset(self):
        qids = self._checked_qids()
        if not qids:
            self.main_window.set_status(str(i18n.tr("quest_page.select_first")))
            return
        for qid in qids:
            self.qm.reset_quest(qid)
        self._after_batch(i18n.tr("quest_page.batch_applied", n=len(qids)))

    def _select_all(self):
        checked_count = 0
        total = self.table.rowCount()
        for i in range(total):
            it = self.table.item(i, 0)
            if it is not None and it.checkState() == Qt.CheckState.Checked:
                checked_count += 1
        state = Qt.CheckState.Unchecked if checked_count == total else Qt.CheckState.Checked
        for i in range(total):
            it = self.table.item(i, 0)
            if it is not None:
                it.setCheckState(state)

    def _after_batch(self, msg):
        self.main_window.set_status(str(msg))
        self._load_states()
        self._sync_card_orders()
        self._rebuild_list()
        self._rebuild_table()

    # ---------- 组批量操作 ----------
    def _on_group_action(self, done):
        if self.data.conn is None:
            return
        key = self.group_combo.currentData()
        if not key:
            return
        qids = []
        for k, _n, ids in self._lines:
            if k == key:
                qids = list(ids)
                break
        if not qids:
            return
        if done:
            for qid in qids:
                self.qm.set_complete(qid, self.qm.q(qid).get("db_category"))
            msg = i18n.tr("quest_page.group_done_msg", n=len(qids))
        else:
            for qid in qids:
                self.qm.reset_quest(qid)
            msg = i18n.tr("quest_page.group_reset_msg", n=len(qids))
        self._after_batch(msg)

    # ---------- 搜索 / 筛选 ----------
    def _on_search(self, _text):
        if self._mode == "list":
            self._rebuild_list()
        else:
            self._rebuild_table()

    def _on_filter(self, _idx):
        if self._mode == "list":
            self._rebuild_list()
        else:
            self._rebuild_table()


# ============================================================
# 区域任务页 (表格 + 批量)
# ============================================================
class RegionQuestPage(QWidget):
    """区域任务 (动态任务) 147 个: 表格直改 + 完成次数 + 批量操作。"""

    def __init__(self, data, names, main_window, quest_mgr, page_key=None):
        super().__init__()
        self.data = data
        self.names = names
        self.main_window = main_window
        self.qm = quest_mgr
        self._groups = {}      # {group_id: {last_quest, quest, step, cnt}}
        self._complete = {}    # {quest_id: cnt}
        self._rows = []        # [qid] 过滤后的行序
        self._build()
        self.reload()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(6)

        # 顶行: 搜索 + 状态筛选 + 说明
        top = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(str(i18n.tr("region_page.search")))
        self.search_box.textChanged.connect(self._on_change)
        top.addWidget(self.search_box, 1)
        top.addWidget(QLabel(str(i18n.tr("region_page.filter"))))
        self.filter_combo = QComboBox()
        self.filter_combo.addItem(str(i18n.tr("quest_page.all")), "all")
        self.filter_combo.addItem(str(i18n.tr("quest_page.done")), "done")
        self.filter_combo.addItem(str(i18n.tr("region_page.state_none")), "none")
        self.filter_combo.currentIndexChanged.connect(self._on_change)
        top.addWidget(self.filter_combo)
        outer.addLayout(top)

        hint = QLabel(str(i18n.tr("region_page.hint")))
        hint.setStyleSheet("color: #7f849c; font-size: 9pt;")
        hint.setWordWrap(True)
        outer.addWidget(hint)

        # 主区表格
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        # 铺满策略: 首列勾选固定 36px, 其余列按内容自适应, 末列拉伸
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        outer.addWidget(self.table, 1)

        # 批量
        btn_row = QHBoxLayout()
        self.done_inc_btn = QPushButton(str(i18n.tr("region_page.done_inc")))
        self.done_inc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.done_inc_btn.clicked.connect(self._batch_inc)
        btn_row.addWidget(self.done_inc_btn)
        self.done_dec_btn = QPushButton(str(i18n.tr("region_page.done_dec")))
        self.done_dec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.done_dec_btn.clicked.connect(self._batch_dec)
        btn_row.addWidget(self.done_dec_btn)
        self.clear_hold_btn = QPushButton(str(i18n.tr("region_page.clear_hold")))
        self.clear_hold_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_hold_btn.clicked.connect(self._batch_clear_hold)
        btn_row.addWidget(self.clear_hold_btn)
        btn_row.addStretch(1)
        # 选择按钮: 全选 / 全不选 / 反选 (紧凑排列)
        self.select_all_btn = QPushButton(str(i18n.tr("region_page.select_all")))
        self.select_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_all_btn.clicked.connect(self._select_all)
        btn_row.addWidget(self.select_all_btn)
        self.select_none_btn = QPushButton(str(i18n.tr("region_page.select_none")))
        self.select_none_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_none_btn.clicked.connect(self._select_none)
        btn_row.addWidget(self.select_none_btn)
        self.select_invert_btn = QPushButton(str(i18n.tr("region_page.select_invert")))
        self.select_invert_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_invert_btn.clicked.connect(self._select_invert)
        btn_row.addWidget(self.select_invert_btn)
        outer.addLayout(btn_row)

    # ---------- 数据加载 ----------
    def reload(self):
        if self.data.conn is None:
            self._groups, self._complete = {}, {}
        else:
            self._groups, self._complete = self.qm.load_dynamic_states()
        self._rebuild_table()

    def _quest_status(self, qid):
        qid_i = int(qid)
        if qid_i in self._complete and self._complete[qid_i] > 0:
            return "done"
        meta = self.qm.dynamic.get(qid) or {}
        if int(meta.get("group") or 0) in self._groups:
            return "hold"
        return "none"

    def _visible_rows(self):
        f = self.filter_combo.currentData()
        kw = self.search_box.text().strip().lower()
        out = []
        for qid, meta in self.qm.dynamic.items():
            st = self._quest_status(qid)
            if f == "done" and st != "done":
                continue
            if f == "none" and st != "none":
                continue
            if kw:
                nm = localize_name(meta.get("name")) or ""
                if kw not in str(qid) and kw not in str(nm).lower():
                    continue
            out.append(qid)
        out.sort(key=lambda x: int(x))
        return out

    def _rebuild_table(self):
        self.table.clear()
        headers = ["", "ID", str(i18n.tr("table.column_name")),
                   str(i18n.tr("region_page.group")), str(i18n.tr("region_page.trigger")),
                   str(i18n.tr("region_page.status")),
                   str(i18n.tr("region_page.complete_cnt"))]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self._set_btns(True)
        if self.data.conn is None:
            self.table.setRowCount(0)
            self._set_btns(False)
            return
        if not self.qm.dynamic:
            self.table.setRowCount(1)
            it = QTableWidgetItem(str(i18n.tr("region_page.no_data")))
            it.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(0, 1, it)
            self._set_btns(False)
            return
        self._rows = self._visible_rows()
        self.table.setRowCount(len(self._rows))
        for i, qid in enumerate(self._rows):
            meta = self.qm.dynamic[qid]
            st = self._quest_status(qid)
            # 勾选
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(i, 0, chk)
            # ID
            id_it = QTableWidgetItem(str(qid))
            id_it.setData(Qt.ItemDataRole.UserRole, qid)
            self.table.setItem(i, 1, id_it)
            # 名称
            self.table.setItem(i, 2, QTableWidgetItem(
                localize_name(meta.get("name")) or f"ID {qid}"))
            # 区域组
            g = int(meta.get("group") or 0)
            gtxt = str(i18n.tr("region_page.group_fmt", n=g))
            if g in self._groups:
                gtxt += " 🔄"
            self.table.setItem(i, 3, QTableWidgetItem(gtxt))
            # 触发方式
            trig = meta.get("trigger")
            trig_txt = (str(i18n.tr("region_page.trigger_npc"))
                        if trig == "ENCOUNTER_NPC"
                        else str(i18n.tr("region_page.trigger_zone")))
            self.table.setItem(i, 4, QTableWidgetItem(trig_txt))
            # 状态
            if st == "hold":
                st_txt = "🔄 " + str(i18n.tr("quest_page.state_hold"))
            elif st == "done":
                st_txt = "✅ " + str(i18n.tr("quest_page.state_done"))
            else:
                st_txt = "-"
            self.table.setItem(i, 5, QTableWidgetItem(st_txt))
            # 完成次数 (可编辑)
            spin = QSpinBox()
            spin.setRange(0, 9999)
            spin.setValue(self._complete.get(int(qid), 0))
            spin.setKeyboardTracking(False)
            spin.editingFinished.connect(
                lambda q=qid, s=spin: self._on_cnt_changed(q, s))
            self.table.setCellWidget(i, 6, spin)
        # 铺满: 首列勾选固定 36px, 中间列按内容自适应, 末列拉伸填满
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        self.table.setColumnWidth(0, 36)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        for c in range(1, self.table.columnCount() - 1):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.table.columnCount() - 1,
                                    QHeaderView.ResizeMode.Stretch)

    def _set_btns(self, on):
        self.done_inc_btn.setEnabled(on)
        self.done_dec_btn.setEnabled(on)
        self.clear_hold_btn.setEnabled(on)
        self.select_all_btn.setEnabled(on)
        self.select_none_btn.setEnabled(on)
        self.select_invert_btn.setEnabled(on)

    # ---------- 完成次数编辑 ----------
    def _on_cnt_changed(self, qid, spin):
        if self.data.conn is None:
            return
        val = spin.value()
        if val <= 0:
            self.qm.delete_dynamic_complete(qid)
            self._complete.pop(int(qid), None)
        else:
            self.qm.set_dynamic_complete(qid, val)
            self._complete[int(qid)] = val
        self.main_window.set_status(str(i18n.tr("region_page.cnt_updated")))
        self._rebuild_table()

    # ---------- 批量操作 ----------
    def _checked_qids(self):
        out = []
        for i in range(self.table.rowCount()):
            it = self.table.item(i, 0)
            if it and it.checkState() == Qt.CheckState.Checked:
                id_it = self.table.item(i, 1)
                if id_it and id_it.data(Qt.ItemDataRole.UserRole):
                    out.append(id_it.data(Qt.ItemDataRole.UserRole))
        return out

    def _select_all(self):
        """全选: 勾选全部行。"""
        for i in range(self.table.rowCount()):
            it = self.table.item(i, 0)
            if it is not None:
                it.setCheckState(Qt.CheckState.Checked)

    def _select_none(self):
        """全不选: 取消全部勾选。"""
        for i in range(self.table.rowCount()):
            it = self.table.item(i, 0)
            if it is not None:
                it.setCheckState(Qt.CheckState.Unchecked)

    def _select_invert(self):
        """反选: 反转所有行勾选状态。"""
        for i in range(self.table.rowCount()):
            it = self.table.item(i, 0)
            if it is not None:
                it.setCheckState(Qt.CheckState.Unchecked
                                 if it.checkState() == Qt.CheckState.Checked
                                 else Qt.CheckState.Checked)

    def _batch_inc(self):
        qids = self._checked_qids()
        if not qids:
            self.main_window.set_status(str(i18n.tr("region_page.select_first")))
            return
        for qid in qids:
            cnt = self._complete.get(int(qid), 0) + 1
            self.qm.set_dynamic_complete(qid, cnt)
            self._complete[int(qid)] = cnt
        self.main_window.set_status(str(i18n.tr("region_page.applied", n=len(qids))))
        self._rebuild_table()

    def _batch_dec(self):
        qids = self._checked_qids()
        if not qids:
            self.main_window.set_status(str(i18n.tr("region_page.select_first")))
            return
        for qid in qids:
            cnt = self._complete.get(int(qid), 0) - 1
            if cnt <= 0:
                self.qm.delete_dynamic_complete(qid)
                self._complete.pop(int(qid), None)
            else:
                self.qm.set_dynamic_complete(qid, cnt)
                self._complete[int(qid)] = cnt
        self.main_window.set_status(str(i18n.tr("region_page.applied", n=len(qids))))
        self._rebuild_table()

    def _batch_clear_hold(self):
        qids = self._checked_qids()
        if not qids:
            self.main_window.set_status(str(i18n.tr("region_page.select_first")))
            return
        removed = 0
        for qid in qids:
            meta = self.qm.dynamic.get(qid) or {}
            g = int(meta.get("group") or 0)
            if g in self._groups:
                self.qm.delete_dynamic_group(g)
                del self._groups[g]
                removed += 1
        self.main_window.set_status(str(i18n.tr("region_page.hold_removed", n=removed)))
        self._rebuild_table()

    # ---------- 搜索 / 筛选 ----------
    def _on_change(self, *_):
        self._rebuild_table()
