# -*- coding: utf-8 -*-
"""备份管理 + 保存前改动对比对话框。

BackupDialog  : 备份/还原/删除管理 (多版本备份, ds_save.backup/list_backups)。
SaveDiffDialog: 保存前展示 build_diff() 的改动内容, 用户确认后由调用方写回。
"""

import os
import shutil
import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QTreeWidget, QTreeWidgetItem,
    QMessageBox, QAbstractItemView,
)

import ds_save

from . import i18n


def _fmt_size(size):
    """字节 -> 人性化大小 (KB)"""
    try:
        return f"{size / 1024:.1f} KB"
    except (TypeError, ValueError):
        return "-"


def _fmt_time(mtime):
    return datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")


def _fmt_val(v):
    if v is None:
        return "NULL"
    return str(v)


def _truncate(text, limit=100):
    text = str(text)
    return text if len(text) <= limit else text[:limit] + "…"


# ============================================================
# 备份管理对话框
# ============================================================
class BackupDialog(QDialog):
    """备份/还原管理: 版本列表 + 立即备份 / 还原所选 / 删除所选。"""

    def __init__(self, data, main_window):
        super().__init__(main_window)
        self.data = data
        self.main_window = main_window
        self.setWindowTitle(str(i18n.tr("backup_page.title")))
        self.setMinimumSize(640, 420)
        self._rows = []   # [(path, mtime, size)]
        self._build()
        self._refresh()

    # ---------- 构建 ----------
    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)

        # 当前存档信息
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #7f849c; font-size: 9pt;")
        lay.addWidget(self.info_label)

        # 版本列表
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels([
            str(i18n.tr("backup_page.col_time")),
            str(i18n.tr("backup_page.col_size")),
            str(i18n.tr("backup_page.col_type")),
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        lay.addWidget(self.table, 1)

        # 按钮行
        btn_row = QHBoxLayout()
        self.backup_btn = QPushButton(str(i18n.tr("backup_page.backup_now")))
        self.backup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.backup_btn.clicked.connect(self._on_backup_now)
        btn_row.addWidget(self.backup_btn)
        self.restore_btn = QPushButton(str(i18n.tr("backup_page.restore")))
        self.restore_btn.setObjectName("primaryBtn")
        self.restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restore_btn.clicked.connect(self._on_restore)
        btn_row.addWidget(self.restore_btn)
        self.delete_btn = QPushButton(str(i18n.tr("backup_page.delete")))
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self.delete_btn)
        btn_row.addStretch(1)
        close_btn = QPushButton(str(i18n.tr("backup_page.close")))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

    # ---------- 数据 ----------
    def _refresh(self):
        """刷新当前存档信息 + 版本列表。"""
        if not self.data.db_path:
            self.info_label.setText(str(i18n.tr("status.no_db")))
            self.backup_btn.setEnabled(False)
            self.restore_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            return
        try:
            mtime = os.path.getmtime(self.data.db_path)
            size = os.path.getsize(self.data.db_path)
        except OSError:
            mtime, size = None, None
        path_txt = self.data.db_path
        meta_txt = ""
        if mtime is not None:
            meta_txt = str(i18n.tr("backup_page.current_mtime",
                                  time=_fmt_time(mtime), size=_fmt_size(size)))
        self.info_label.setText(
            str(i18n.tr("backup_page.current_info", path=path_txt)) + "\n" + meta_txt)

        self._rows = ds_save.list_backups(self.data.db_path)
        self.table.setRowCount(0)
        if not self._rows:
            self.table.setRowCount(1)
            hint = QTableWidgetItem(str(i18n.tr("backup_page.no_backup")))
            hint.setFlags(Qt.ItemFlag.ItemIsEnabled)
            hint.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(0, 0, hint)
            self.table.setSpan(0, 0, 1, 3)
        else:
            self.table.setRowCount(len(self._rows))
            for i, (path, mtime, size) in enumerate(self._rows):
                old_fmt = path.endswith(".backup")
                time_txt = _fmt_time(mtime)
                if old_fmt:
                    time_txt += " " + str(i18n.tr("backup_page.old_fmt"))
                type_txt = (str(i18n.tr("backup_page.type_old"))
                            if old_fmt else str(i18n.tr("backup_page.type_normal")))
                t0 = QTableWidgetItem(time_txt)
                t0.setData(Qt.ItemDataRole.UserRole, path)
                t1 = QTableWidgetItem(_fmt_size(size))
                t1.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                    | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(i, 0, t0)
                self.table.setItem(i, 1, t1)
                self.table.setItem(i, 2, QTableWidgetItem(type_txt))
            self.table.setColumnWidth(0, 220)
            self.table.setColumnWidth(1, 100)
        self._update_buttons()

    def _selected_path(self):
        rows = self.table.selectionModel().selectedRows() if self.table.rowCount() else []
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _update_buttons(self):
        if not self.data.db_path:
            self.backup_btn.setEnabled(False)
            self.restore_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            return
        self.backup_btn.setEnabled(True)
        has = self._selected_path() is not None
        self.restore_btn.setEnabled(has)
        self.delete_btn.setEnabled(has)

    # ---------- 操作 ----------
    def _on_backup_now(self):
        try:
            bak = ds_save.backup(self.data.db_path)
        except Exception as e:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(e))
            return
        self.main_window.set_status(str(i18n.tr("backup_page.backup_done", path=bak)))
        self._refresh()

    def _on_restore(self):
        path = self._selected_path()
        if not path:
            QMessageBox.information(self, str(i18n.tr("dialogs.confirm")),
                                    str(i18n.tr("backup_page.no_selection")))
            return
        if QMessageBox.question(
                self, str(i18n.tr("dialogs.confirm")),
                str(i18n.tr("backup_page.restore_confirm"))
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            shutil.copy2(path, self.data.db_path)
            self.data.load(self.data.db_path)
        except Exception as e:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(e))
            return
        self.main_window.set_status(str(i18n.tr("status.restore_done")))
        self.main_window.refresh_all_pages()
        self._refresh()
        QMessageBox.information(self, str(i18n.tr("status.success")),
                                str(i18n.tr("backup_page.restore_done")))

    def _on_delete(self):
        path = self._selected_path()
        if not path:
            QMessageBox.information(self, str(i18n.tr("dialogs.confirm")),
                                    str(i18n.tr("backup_page.no_selection")))
            return
        if QMessageBox.question(
                self, str(i18n.tr("dialogs.confirm")),
                str(i18n.tr("backup_page.delete_confirm", name=os.path.basename(path)))
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            os.remove(path)
        except Exception as e:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(e))
            return
        self.main_window.set_status(str(i18n.tr("backup_page.deleted")))
        self._refresh()


# ============================================================
# 保存前改动对比对话框
# ============================================================
class SaveDiffDialog(QDialog):
    """展示 build_diff() 的改动内容: 每张变化表一个顶层节点,
    子节点为新增/删除/修改详情。确认应用 (Accepted) 后由调用方保存。"""

    def __init__(self, data, main_window, diff):
        super().__init__(main_window)
        self.data = data
        self.main_window = main_window
        self.diff = diff or {}
        self.setWindowTitle(str(i18n.tr("diff_page.title")))
        self.setMinimumSize(680, 480)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)

        hint = QLabel(str(i18n.tr("diff_page.hint")))
        hint.setStyleSheet("color: #7f849c; font-size: 9pt;")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        if not self.diff:
            empty = QLabel(str(i18n.tr("diff_page.no_changes")))
            empty.setStyleSheet("font-size: 12pt; color: #7f849c;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(empty, 1)
            btn_row = QHBoxLayout()
            btn_row.addStretch(1)
            close_btn = QPushButton(str(i18n.tr("backup_page.close")))
            close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            close_btn.clicked.connect(self.reject)
            btn_row.addWidget(close_btn)
            lay.addLayout(btn_row)
            return

        # 主区: 树形改动列表
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(1)
        for table in sorted(self.diff):
            d = self.diff[table]
            n_add = len(d.get("added", []))
            n_del = len(d.get("removed", []))
            n_mod = len(d.get("modified", []))
            title = f"{table}  (+{n_add} / -{n_del} / ~{n_mod})"
            top = QTreeWidgetItem([title])
            f = top.font(0)
            f.setBold(True)
            top.setFont(0, f)
            # 新增行
            for row in d.get("added", []):
                child = QTreeWidgetItem(
                    [str(i18n.tr("diff_page.row_added")) + ": " +
                     _truncate(", ".join(f"{c}={_fmt_val(v)}" for c, v in row.items()))])
                top.addChild(child)
            # 删除行
            for row in d.get("removed", []):
                child = QTreeWidgetItem(
                    [str(i18n.tr("diff_page.row_removed")) + ": " +
                     _truncate(", ".join(f"{c}={_fmt_val(v)}" for c, v in row.items()))])
                top.addChild(child)
            # 修改行
            for m in d.get("modified", []):
                key_txt = ", ".join(_fmt_val(v) for v in m.get("key", ())) or "-"
                row_node = QTreeWidgetItem(
                    [str(i18n.tr("diff_page.row_modified")) + ": " + key_txt])
                for col, (old, new) in m.get("changes", {}).items():
                    field = QTreeWidgetItem(
                        [f"{col}: {_fmt_val(old)} → {_fmt_val(new)}"])
                    row_node.addChild(field)
                top.addChild(row_node)
            self.tree.addTopLevelItem(top)
        self.tree.expandAll()
        lay.addWidget(self.tree, 1)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton(str(i18n.tr("diff_page.cancel")))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        apply_btn = QPushButton(str(i18n.tr("diff_page.apply")))
        apply_btn.setObjectName("primaryBtn")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.clicked.connect(self.accept)
        btn_row.addWidget(apply_btn)
        lay.addLayout(btn_row)
