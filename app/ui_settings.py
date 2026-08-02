# -*- coding: utf-8 -*-
"""设置对话框: 语言下拉 + 主题下拉 + 保存按钮。

保存后写 config.json, 提示重启生效。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QLabel,
    QPushButton, QDialogButtonBox, QHBoxLayout,
)

from . import i18n, config


class SettingsDialog(QDialog):
    """设置对话框"""

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self._cfg = dict(cfg)
        self.setWindowTitle(str(i18n.tr("settings.title")))
        self.setModal(True)
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        # 语言下拉
        self.lang_combo = QComboBox()
        for code, name in i18n.SUPPORTED:
            self.lang_combo.addItem(name, code)
        idx = self.lang_combo.findData(self._cfg.get("language", "en"))
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        form.addRow(str(i18n.tr("settings.language")), self.lang_combo)

        # 语言切换说明
        lang_desc = QLabel(str(i18n.tr("settings.language_desc")))
        lang_desc.setObjectName("hintLabel")
        lang_desc.setWordWrap(True)
        form.addRow("", lang_desc)

        # 主题下拉
        self.theme_combo = QComboBox()
        self.theme_combo.addItem(
            str(i18n.tr("settings.theme_dark")), "dark"
        )
        self.theme_combo.addItem(
            str(i18n.tr("settings.theme_light")), "light"
        )
        idx = self.theme_combo.findData(self._cfg.get("theme", "dark"))
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        form.addRow(str(i18n.tr("settings.theme")), self.theme_combo)

        layout.addLayout(form)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        save_btn = QPushButton(str(i18n.tr("settings.save")))
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton(str(i18n.tr("dialogs.cancel")))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _on_save(self):
        self._cfg["language"] = self.lang_combo.currentData()
        self._cfg["theme"] = self.theme_combo.currentData()
        config.save_config(self._cfg)
        self.accept()

    def cfg(self):
        return self._cfg
