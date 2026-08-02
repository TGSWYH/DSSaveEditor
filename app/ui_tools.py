# -*- coding: utf-8 -*-
"""数据工具页 + 通用表格能力: TablePanel / AddRowDialog / DataToolsPage 与 ADD_OK_NO_PK。

从 ui_main 拆出 (原"通用表格面板/新增行对话框/数据工具页"三节)。
"""

import ds_save

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QInputDialog, QDialog, QDialogButtonBox, QLineEdit, QFormLayout,
    QComboBox,
)

from . import i18n
from .datasource import cast_value, INVALID
from .ui_common import make_card, _CARD_QSS


# 允许新增行的无主键表 (主键表默认允许)
ADD_OK_NO_PK = {
    "tb_currency", "tb_stackable_item", "tb_team", "tb_skill_growth",
    "tb_title", "tb_quest_hold", "tb_quest_complete",
}


# ============================================================
# 通用表格面板 (保留, 供数据工具页使用)
# ============================================================
class TablePanel(QWidget):
    """单表编辑面板: 顶部工具条 + QTableWidget"""

    def __init__(self, data, names, table, main_window):
        super().__init__()
        self.data = data
        self.names = names
        self.table = table
        self.main_window = main_window
        self.cols_info = []
        self.col_names = []
        self.pk_cols = []
        self._build()
        self.reload()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        bar = QHBoxLayout()
        self.info_label = QLabel()
        bar.addWidget(self.info_label)
        bar.addStretch(1)
        self.add_btn = QPushButton(str(i18n.tr("table.add_row")))
        self.add_btn.clicked.connect(self._on_add)
        bar.addWidget(self.add_btn)
        self.del_btn = QPushButton(str(i18n.tr("table.delete_row")))
        self.del_btn.clicked.connect(self._on_delete)
        bar.addWidget(self.del_btn)
        layout.addLayout(bar)

        self.table_widget = QTableWidget()
        self.table_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_widget.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.horizontalHeader().setStretchLastSection(False)
        self.table_widget.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.cellDoubleClicked.connect(self._on_cell_double)
        layout.addWidget(self.table_widget)

    def reload(self):
        try:
            self.cols_info = self.data.table_columns(self.table)
            rows = self.data.select_all(self.table)
        except ds_save.DSError as e:
            self.info_label.setText(f"{self.table}: {e}")
            self.table_widget.clear()
            self.table_widget.setRowCount(0)
            self.table_widget.setColumnCount(0)
            return

        self.col_names = [c[0] for c in self.cols_info]
        self.pk_cols = [c[0] for c in self.cols_info if c[2]]
        self.add_btn.setEnabled(bool(self.pk_cols) or self.table in ADD_OK_NO_PK)
        self.del_btn.setEnabled(bool(self.pk_cols))
        self.info_label.setText(f"{self.table}  ·  {len(rows)}")

        self.table_widget.clear()
        self.table_widget.setColumnCount(len(self.col_names))
        self.table_widget.setHorizontalHeaderLabels(self.col_names)
        self.table_widget.setRowCount(len(rows))

        for r, row in enumerate(rows):
            for c, col_name in enumerate(self.col_names):
                raw = row[col_name]
                disp = self.names.format(col_name, raw)
                item = QTableWidgetItem("" if disp is None else str(disp))
                item.setData(Qt.ItemDataRole.UserRole, raw)
                item.setToolTip(str(raw) if raw is not None else "")
                item.setFlags(
                    Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
                )
                self.table_widget.setItem(r, c, item)

        self.table_widget.resizeColumnsToContents()
        for c in range(self.table_widget.columnCount()):
            w = self.table_widget.columnWidth(c)
            self.table_widget.setColumnWidth(c, max(80, min(260, w + 12)))

    def _on_cell_double(self, row, col):
        if col < 0 or col >= len(self.col_names):
            return
        col_name = self.col_names[col]
        col_type = self.cols_info[col][1] or ""
        item = self.table_widget.item(row, col)
        if item is None:
            return
        raw = item.data(Qt.ItemDataRole.UserRole)
        if not self.pk_cols:
            QMessageBox.warning(self, str(i18n.tr("dialogs.confirm")),
                                 str(i18n.tr("table.no_pk")))
            return
        new_val, ok = QInputDialog.getText(
            self, str(i18n.tr("table.edit_title")),
            f"{self.table}.{col_name} ({col_type or 'TEXT'})\n{i18n.tr('table.edit_label')}",
            text="" if raw is None else str(raw),
        )
        if not ok:
            return
        typed = cast_value(new_val.strip(), col_type)
        if typed is INVALID:
            QMessageBox.warning(self, str(i18n.tr("status.error")),
                                 str(i18n.tr("table.invalid_number")))
            return
        pk_vals = []
        for pkc in self.pk_cols:
            idx = self.col_names.index(pkc)
            pk_item = self.table_widget.item(row, idx)
            pk_raw = pk_item.data(Qt.ItemDataRole.UserRole) if pk_item else None
            t = self.cols_info[idx][1] or ""
            v = cast_value(str(pk_raw), t)
            pk_vals.append(pk_raw if v is INVALID else v)
        try:
            self.data.update_cell(self.table, self.pk_cols, pk_vals, col_name, typed)
        except Exception as e:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(e))
            return
        item.setData(Qt.ItemDataRole.UserRole, typed)
        item.setText("" if typed is None else str(self.names.format(col_name, typed)))
        item.setToolTip("" if typed is None else str(typed))
        self.main_window.set_status(f"{self.table}.{col_name} = {typed}")

    def _on_delete(self):
        rows = sorted({idx.row() for idx in self.table_widget.selectedIndexes()}, reverse=True)
        if not rows:
            return
        if not self.pk_cols:
            QMessageBox.warning(self, str(i18n.tr("dialogs.confirm")),
                                 str(i18n.tr("table.no_pk")))
            return
        if QMessageBox.question(self, str(i18n.tr("dialogs.confirm")),
                                  f"{len(rows)} ?") != QMessageBox.StandardButton.Yes:
            return
        for r in rows:
            pk_vals = []
            for pkc in self.pk_cols:
                idx = self.col_names.index(pkc)
                pk_item = self.table_widget.item(r, idx)
                pk_raw = pk_item.data(Qt.ItemDataRole.UserRole) if pk_item else None
                t = self.cols_info[idx][1] or ""
                v = cast_value(str(pk_raw), t)
                pk_vals.append(pk_raw if v is INVALID else v)
            try:
                self.data.delete_row(self.table, self.pk_cols, pk_vals)
            except Exception as e:
                QMessageBox.critical(self, str(i18n.tr("status.error")), str(e))
                break
        self.reload()
        self.main_window.set_status(f"{self.table}: -{len(rows)}")

    def _on_add(self):
        dlg = AddRowDialog(self.data, self.table, self.cols_info, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.reload()
            self.main_window.set_status(f"{self.table}: +1")


# ============================================================
# 新增行对话框
# ============================================================
class AddRowDialog(QDialog):
    def __init__(self, data, table, cols_info, parent=None):
        super().__init__(parent)
        self.data = data
        self.table = table
        self.cols_info = cols_info
        self.setWindowTitle(f"{i18n.tr('table.add_row')} - {table}")
        self.setMinimumWidth(420)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.entries = {}
        for cn, ct, pk in self.cols_info:
            e = QLineEdit()
            e.setPlaceholderText("" if not pk else "PK")
            form.addRow(f"{cn}{' (PK)' if pk else ''} ({ct or ''})", e)
            self.entries[cn] = e
        layout.addLayout(form)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(str(i18n.tr("dialogs.ok")))
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText(str(i18n.tr("dialogs.cancel")))
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_ok(self):
        cols, vals = [], []
        for cn, ct, _pk in self.cols_info:
            raw = self.entries[cn].text().strip()
            if raw == "":
                continue
            v = cast_value(raw, ct)
            if v is INVALID:
                QMessageBox.warning(self, str(i18n.tr("status.error")),
                                     f"{cn} ({ct or 'TEXT'}): {raw}")
                return
            cols.append(cn)
            vals.append(v)
        try:
            self.data.insert_row(self.table, cols, vals)
        except Exception as e:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(e))
            return
        self.accept()


# ============================================================
# 数据工具页 (保留全部表格能力)
# ============================================================
class DataToolsPage(QWidget):
    """数据工具: 顶部说明 + 全部表下拉 + 表格编辑。"""

    def __init__(self, data, names, main_window):
        super().__init__()
        self.data = data
        self.names = names
        self.main_window = main_window
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        notice = QLabel(str(i18n.tr("tools_page.notice")))
        notice.setStyleSheet("color: #7f849c; font-size: 9pt;")
        notice.setWordWrap(True)
        layout.addWidget(notice)

        top = QHBoxLayout()
        top.addWidget(QLabel(str(i18n.tr("table.all_tables_label"))))
        self.all_combo = QComboBox()
        self.all_combo.currentIndexChanged.connect(self._on_table_changed)
        top.addWidget(self.all_combo, 1)
        top.addWidget(QLabel(str(i18n.tr("table.hint"))))
        layout.addLayout(top)

        self.container = QWidget()
        self.container_lay = QVBoxLayout(self.container)
        self.container_lay.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.container, 1)

    def reload(self):
        self.all_combo.clear()
        if not self.data.db_path:
            return
        for t in self.data.list_tables():
            self.all_combo.addItem(t, t)
        if self.all_combo.count() > 0:
            self._load_table(self.all_combo.currentData())

    def _on_table_changed(self, _idx):
        t = self.all_combo.currentData()
        if t:
            self._load_table(t)

    def _load_table(self, table):
        self._clear_layout(self.container_lay)
        self.container_lay.addWidget(
            TablePanel(self.data, self.names, table, self.main_window)
        )

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
