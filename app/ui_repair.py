# -*- coding: utf-8 -*-
"""异常修复页 (RepairPage): QTabWidget 容器, 子功能 tab 承载各类存档异常修复。

首个子功能: 时间修复 (TimeRepairTab) —— 检测并修复存档时间字段异常,
如 PLAY_TIME 被写成负巨值导致游戏显示 -25 亿小时/无法打开存档。
后续存档问题修复均在此页面新增子 tab。
"""

import re
import time
import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
)

from . import i18n
from .ui_common import make_card


# ============================================================
# 时间修复子页
# ============================================================
class TimeRepairTab(QWidget):
    """检测并修复存档时间字段异常。

    时间字段两类:
      - INTEGER 时间戳/时长: tb_advent_status.PLAY_TIME (游玩秒数),
        各表 CREATED_DATE/DELETED_DATE (Unix 秒)
      - TEXT 日期: tb_user.LAST_LOGIN_TIME / LAST_LOGOUT_TIME / CREATE_DATE
    """

    # (表名, 列名, 类型, 允许值说明, 正常判定)
    # 类型: "int"=Unix秒/时长, "text"=YYYY-MM-DD[ HH:MM:SS]
    # 正常范围: int 时间戳 1973-01-01 (1e8) ~ 2100-01-01 (4.1e9);
    #           PLAY_TIME 时长: 0 ~ 10 年秒数; text 需可解析
    _INT_TIME_MIN = 100_000_000        # 1973-01-01
    _INT_TIME_MAX = 4_102_444_800      # 2100-01-01
    _PLAY_TIME_MAX = 315_360_000       # 10 年秒数
    _TEXT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}:\d{2})?$")

    FIELDS = [
        # (表, 列, 类型, i18n key 后缀)
        ("tb_advent_status", "PLAY_TIME", "play", "time_play_time"),
        ("tb_user", "LAST_LOGIN_TIME", "text", "time_last_login"),
        ("tb_user", "LAST_LOGOUT_TIME", "text", "time_last_logout"),
        ("tb_user", "CREATE_DATE", "text", "time_create_date"),
        ("tb_character", "CREATED_DATE", "int", "time_char_created"),
        ("tb_equipment", "CREATED_DATE", "int", "time_eq_created"),
        ("tb_equipment", "DELETED_DATE", "int0", "time_eq_deleted"),
        ("tb_gem", "CREATED_DATE", "int", "time_gem_created"),
        ("tb_gem", "DELETED_DATE", "int0", "time_gem_deleted"),
        ("tb_vehicle", "CREATED_DATE", "int", "time_veh_created"),
        ("tb_karma", "CREATED_DATE", "int", "time_karma_created"),
        ("tb_karma", "DELETED_DATE", "int0", "time_karma_deleted"),
        ("tb_costume", "CREATED_DATE", "int", "time_costume_created"),
        ("tb_cook_item", "CREATED_DATE", "int", "time_cook_created"),
        ("tb_cook_item", "DELETED_DATE", "int0", "time_cook_deleted"),
    ]

    def __init__(self, data, main_window):
        super().__init__()
        self.data = data
        self.main_window = main_window
        self._issues = []      # [(table, col, kind, row_key, value)]
        self._build()

    # ---------- 布局 ----------
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        card, lay = make_card(str(i18n.tr("repair_page.time_title")))
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        hint = QLabel(str(i18n.tr("repair_page.time_hint")))
        hint.setStyleSheet("color: #7f849c; font-size: 9pt;")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.scan_btn = QPushButton(str(i18n.tr("repair_page.btn_scan")))
        self.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_btn.clicked.connect(self._scan)
        btn_row.addWidget(self.scan_btn)
        self.fix_btn = QPushButton(str(i18n.tr("repair_page.btn_fix")))
        self.fix_btn.setObjectName("primaryBtn")
        self.fix_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fix_btn.setEnabled(False)
        self.fix_btn.clicked.connect(self._fix)
        btn_row.addWidget(self.fix_btn)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)

        self.summary_lbl = QLabel(str(i18n.tr("repair_page.scan_pending")))
        self.summary_lbl.setStyleSheet("font-size: 9pt;")
        lay.addWidget(self.summary_lbl)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            str(i18n.tr("repair_page.col_field")),
            str(i18n.tr("repair_page.col_value")),
            str(i18n.tr("repair_page.col_status")),
            str(i18n.tr("repair_page.col_fix")),
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table, 1)

        outer.addWidget(card)

    # ---------- 扫描 ----------
    def reload(self):
        """页面切换/存档打开时自动刷新。"""
        self._scan()

    def _scan(self):
        self._issues = []
        self.fix_btn.setEnabled(False)
        if not self.data.db_path:
            self.summary_lbl.setText(str(i18n.tr("status.no_db")))
            self.table.setRowCount(0)
            return
        rows_out = []
        for table, col, kind, key in self.FIELDS:
            try:
                rows = self.data.select_all(table)
            except Exception:
                rows = []
            if not rows:
                # 空表: 显示一条"无数据"行 (不算异常)
                rows_out.append((f"{table}.{col}", "-", "ok", "-", False))
                continue
            for r in rows:
                val = r[col]
                issue, fix_val = self._check(kind, val)
                display = self._fmt_value(kind, val)
                if issue:
                    rows_out.append((f"{table}.{col}", display, "bad",
                                     self._fmt_fix(kind, fix_val), True))
                    self._issues.append((table, col, kind, r, fix_val))
                else:
                    rows_out.append((f"{table}.{col}", display, "ok", "-", False))
        self._fill_table(rows_out)
        n = len(self._issues)
        if n:
            self.summary_lbl.setText(str(i18n.tr("repair_page.scan_bad", n=n)))
            self.fix_btn.setEnabled(True)
        else:
            self.summary_lbl.setText(str(i18n.tr("repair_page.scan_ok")))

    def _check(self, kind, val):
        """返回 (是否异常, 建议修复值)。"""
        if kind == "text":
            if val is None:
                return True, self._now_text()
            s = str(val).strip()
            if not self._TEXT_RE.match(s):
                return True, self._now_text()
            try:
                datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return True, self._now_text()
            return False, None
        try:
            num = int(val)
        except (TypeError, ValueError):
            return True, int(time.time())
        if kind == "play":
            # PLAY_TIME 是游玩时长(秒), 正常应为 0~数万秒量级;
            # 异常 (负值/int64溢出) 归零即可, 不能填当前时间戳 (会显示成 50 万小时)。
            if num < 0 or num > self._PLAY_TIME_MAX:
                return True, 0
            return False, None
        if kind == "int0" and num == 0:
            return False, None          # DELETED_DATE 0 = 未删除, 正常
        if num < self._INT_TIME_MIN or num > self._INT_TIME_MAX:
            return True, int(time.time())
        return False, None

    def _fmt_value(self, kind, val):
        if val is None:
            return "-"
        if kind == "text":
            return str(val)
        try:
            num = int(val)
        except (TypeError, ValueError):
            return str(val)
        if kind == "play":
            return self._fmt_play(num)
        if num == 0:
            return "0"
        try:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(num))
        except Exception:
            return str(num)

    def _fmt_fix(self, kind, val):
        if kind == "play":
            return self._fmt_play(val)
        if kind == "text":
            return str(val)
        if val == 0:
            return "0"
        try:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(val))
        except Exception:
            return str(val)

    @staticmethod
    def _fmt_play(sec):
        sec = max(int(sec), 0)
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        return str(i18n.tr("repair_page.play_fmt", h=h, m=m, s=s))

    @staticmethod
    def _now_text():
        return time.strftime("%Y-%m-%d %H:%M:%S")

    def _fill_table(self, rows_out):
        self.table.setRowCount(len(rows_out))
        ok_text = str(i18n.tr("repair_page.status_ok"))
        bad_text = str(i18n.tr("repair_page.status_bad"))
        for i, (field, val, status, fix, is_bad) in enumerate(rows_out):
            self.table.setItem(i, 0, QTableWidgetItem(field))
            self.table.setItem(i, 1, QTableWidgetItem(val))
            item = QTableWidgetItem(bad_text if is_bad else ok_text)
            if is_bad:
                item.setForeground(Qt.GlobalColor.red)
            self.table.setItem(i, 2, item)
            self.table.setItem(i, 3, QTableWidgetItem(fix))
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, max(self.table.columnWidth(0), 220))

    # ---------- 修复 ----------
    def _fix(self):
        if not self._issues:
            return
        if QMessageBox.question(
                self, str(i18n.tr("dialogs.confirm")),
                str(i18n.tr("repair_page.fix_confirm", n=len(self._issues)))
        ) != QMessageBox.StandardButton.Yes:
            return
        done = 0
        try:
            for table, col, kind, row, fix_val in self._issues:
                # 用主键定位 (user_dbid + 首列 id); 退化: 全表更新
                pk = "USER_DBID"
                try:
                    self.data.execute(
                        "UPDATE {0} SET {1}=? WHERE {2}=?".format(table, col, pk),
                        (fix_val, row[pk]))
                except Exception:
                    self.data.execute(
                        "UPDATE {0} SET {1}=?".format(table, col), (fix_val,))
                done += 1
        except Exception as ex:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
            return
        self.main_window.set_status(str(i18n.tr("repair_page.fixed", n=done)))
        self._scan()


# ============================================================
# 修复页容器
# ============================================================
class RepairPage(QWidget):
    """异常修复页: QTabWidget 承载各子功能 (时间修复等)。"""

    def __init__(self, data, names, main_window):
        super().__init__()
        self.data = data
        self.names = names
        self.main_window = main_window
        self.tabs = QTabWidget()
        self.time_tab = TimeRepairTab(data, main_window)
        self.tabs.addTab(self.time_tab, str(i18n.tr("repair_page.tab_time")))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.tabs)

    def reload(self):
        self.time_tab.reload()
