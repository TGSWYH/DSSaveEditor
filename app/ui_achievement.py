# -*- coding: utf-8 -*-
"""Achievement counter editor."""

import json
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import i18n
from .config import DATA_DIR
from .datasource import USER_DBID, localize_name


class AchievementPage(QWidget):
    """Edit tb_achievement_count without writing the encrypted file immediately."""

    def __init__(self, data, names, main_window):
        super().__init__()
        self.data = data
        self.main_window = main_window
        self.names = self._load_names()
        self._build()

    @staticmethod
    def _load_names():
        try:
            with open(os.path.join(DATA_DIR, "achievement_names.json"),
                      "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel(str(i18n.tr("achievement_page.title")))
        title.setStyleSheet("font-size: 18pt; font-weight: 700;")
        layout.addWidget(title)

        hint = QLabel(str(i18n.tr("achievement_page.hint")))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #7f849c;")
        layout.addWidget(hint)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            str(i18n.tr("achievement_page.name")),
            str(i18n.tr("achievement_page.group_id")),
            str(i18n.tr("achievement_page.step")),
            str(i18n.tr("achievement_page.count")),
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table, 1)

        controls = QHBoxLayout()
        controls.addWidget(QLabel(str(i18n.tr("achievement_page.new_step"))))
        self.step_spin = QSpinBox()
        self.step_spin.setRange(0, 100)
        self.step_spin.setEnabled(False)
        controls.addWidget(self.step_spin)

        controls.addWidget(QLabel(str(i18n.tr("achievement_page.new_count"))))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(0, 2_000_000_000)
        self.count_spin.setEnabled(False)
        controls.addWidget(self.count_spin)

        self.apply_btn = QPushButton(str(i18n.tr("achievement_page.apply")))
        self.apply_btn.setObjectName("primaryBtn")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._apply_selected)
        controls.addWidget(self.apply_btn)

        controls.addStretch(1)
        layout.addLayout(controls)

    def _group_name(self, group_id):
        name = localize_name(self.names.get(str(group_id)))
        return name or str(i18n.tr(
            "achievement_page.group_fallback", group_id=group_id))

    def reload(self):
        self.table.setRowCount(0)
        self.apply_btn.setEnabled(False)
        self.step_spin.setEnabled(False)
        self.count_spin.setEnabled(False)
        if not self.data.db_path:
            return

        try:
            rows = self.data.select_all(
                "tb_achievement_count", "USER_DBID=?", (USER_DBID,))
        except Exception as ex:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(ex))
            return

        rows = sorted(rows, key=lambda row: row["GROUP_ID"])
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            group_id = row["GROUP_ID"]
            values = (
                self._group_name(group_id), group_id, row["STEP"], row["CNT"],
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column in (1, 2, 3):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, group_id)
                self.table.setItem(row_index, column, item)
        self.table.resizeColumnsToContents()

    def _selected_group_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_selection_changed(self):
        row = self.table.currentRow()
        enabled = row >= 0
        self.apply_btn.setEnabled(enabled)
        self.step_spin.setEnabled(enabled)
        self.count_spin.setEnabled(enabled)
        if enabled:
            self.step_spin.setValue(int(self.table.item(row, 2).text()))
            self.count_spin.setValue(int(self.table.item(row, 3).text()))

    def _apply_selected(self):
        group_id = self._selected_group_id()
        if group_id is None:
            return
        step = self.step_spin.value()
        value = self.count_spin.value()
        self.data.execute(
            "UPDATE tb_achievement_count SET STEP=?, CNT=? "
            "WHERE USER_DBID=? AND GROUP_ID=?",
            (step, value, USER_DBID, group_id),
        )
        self.reload()
        self.main_window.set_status(str(i18n.tr(
            "achievement_page.updated", group_id=group_id, step=step, count=value)))
