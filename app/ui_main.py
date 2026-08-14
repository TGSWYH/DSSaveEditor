# -*- coding: utf-8 -*-
"""主窗口: 概念化导航 + 卡片化页面 (游戏存档工作台)。

左侧导航 (QListWidget) + 右侧 QStackedWidget:
  📊 总览        (OverviewPage)  -- 含金币编辑
  👤 角色养成    (CharacterPage)
  ⚔ 装备        (EquipmentPage)  -- 含词条定制器
  ────────────
  📜 主线任务    (QuestPage)      -- 任务系统 6 页 (主线/因缘/英雄记录/区域/晋升/其他)
  ────────────
  🛠 数据工具    (DataToolsPage, 保留全部表格能力)

工具栏: 打开/备份/还原/保存/刷新/设置
表格: QTableWidget, _CID 列显示 'ID (名称)', 双击编辑, 新增/删除行

页面已拆分至独立文件 (本文件仅保留 import + MainWindow):
  ui_common.py    -- 卡片样式/卡片容器/清空布局 (make_card/_CARD_QSS/_clear_layout)
  ui_overview.py  -- OverviewPage
  ui_character.py -- CharacterPage
  ui_equipment.py -- EquipmentPage + AddEquipmentDialog
  ui_inventory.py -- InventoryPage
  ui_tools.py     -- TablePanel + AddRowDialog + DataToolsPage + ADD_OK_NO_PK
  ui_quest.py     -- QuestPage + RegionQuestPage (复用 ui_common 卡片辅助)
  ui_backup.py    -- BackupDialog + SaveDiffDialog (备份管理 + 保存前改动对比)
"""

import os
import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QListWidget, QListWidgetItem,
    QStackedWidget, QToolBar, QStatusBar, QLabel, QFileDialog, QMessageBox,
    QDialog,
)

import ds_save

from . import i18n, config
from .datasource import SaveData, NameResolver, QuestManager
from .ui_settings import SettingsDialog
from .ui_quest import QuestPage, RegionQuestPage
from .ui_overview import OverviewPage
from .ui_character import CharacterPage
from .ui_equipment import EquipmentPage
from .ui_inventory import InventoryPage
from .ui_karma import KarmaPage
from .ui_vehicle import VehiclePage
from .ui_rune import RunePage
from .ui_tools import DataToolsPage
from .ui_repair import RepairPage
from .ui_backup import BackupDialog, SaveDiffDialog


# ============================================================
# 主窗口
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self, cfg, smoke=False):
        super().__init__()
        self.cfg = dict(cfg)
        self.smoke = smoke
        self.data = SaveData()
        self.names = NameResolver()
        self.quest_mgr = QuestManager(self.data)

        self.setWindowTitle(str(i18n.tr("app_title")))
        self.resize(1200, 760)
        self._center(1200, 760)
        self.setMinimumSize(860, 560)

        self._build_toolbar()
        self._build_nav_and_pages()
        self._build_statusbar()

        self.set_status(str(i18n.tr("status.ready")))
        # 初始: 总览页显示引导
        self.pages["overview"].reload()

        if smoke:
            QTimer.singleShot(2000, self.close)

    # ---------- 构建 ----------
    def _center(self, w, h):
        screen = QGuiApplication.primaryScreen().geometry()
        self.move((screen.width() - w) // 2, (screen.height() - h) // 2)

    def _build_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(tb)

        self.act_open = QAction(str(i18n.tr("menu.open")), self)
        self.act_open.triggered.connect(self.cmd_open)
        tb.addAction(self.act_open)

        self.act_backup = QAction(str(i18n.tr("menu.backup")), self)
        self.act_backup.triggered.connect(self.cmd_backup)
        tb.addAction(self.act_backup)

        self.act_restore = QAction(str(i18n.tr("menu.restore")), self)
        self.act_restore.triggered.connect(self.cmd_restore)
        tb.addAction(self.act_restore)

        self.act_save = QAction(str(i18n.tr("menu.save")), self)
        self.act_save.triggered.connect(self.cmd_save)
        tb.addAction(self.act_save)

        tb.addSeparator()

        self.act_refresh = QAction(str(i18n.tr("menu.refresh")), self)
        self.act_refresh.triggered.connect(self.cmd_refresh)
        tb.addAction(self.act_refresh)

        self.act_settings = QAction(str(i18n.tr("menu.settings")), self)
        self.act_settings.triggered.connect(self.cmd_settings)
        tb.addAction(self.act_settings)

        self.title_label = QLabel(str(i18n.tr("status.no_db")))
        self.title_label.setObjectName("titleLabel")
        tb.addWidget(self.title_label)

    def _build_nav_and_pages(self):
        # 左导航 + 右内容
        central = QWidget()
        self.setCentralWidget(central)
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self.nav = QListWidget()
        self.nav.setFixedWidth(170)
        self.nav.setSpacing(2)
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._on_nav_changed)
        h.addWidget(self.nav)

        self.stack = QStackedWidget()
        h.addWidget(self.stack, 1)

        # 页面实例
        self.pages = {
            "overview": OverviewPage(self.data, self.names, self),
            "character": CharacterPage(self.data, self.names, self),
            "karma": KarmaPage(self.data, self.names, self),
            "vehicle": VehiclePage(self.data, self.names, self),
            "rune": RunePage(self.data, self.names, self),
            "equipment": EquipmentPage(self.data, self.names, self),
            "inventory": InventoryPage(self.data, self.names, self),
            # 任务系统 7 页
            "quest_main": QuestPage(self.data, self.names, self, self.quest_mgr, "main"),
            "quest_epic": QuestPage(self.data, self.names, self, self.quest_mgr, "epic"),
            "quest_character": QuestPage(self.data, self.names, self, self.quest_mgr, "character"),
            "quest_region": RegionQuestPage(self.data, self.names, self, self.quest_mgr),
            "quest_grade": QuestPage(self.data, self.names, self, self.quest_mgr, "grade"),
            "quest_other": QuestPage(self.data, self.names, self, self.quest_mgr, "other"),
            "quest_unreleased": QuestPage(self.data, self.names, self, self.quest_mgr, "unreleased"),
            "tools": DataToolsPage(self.data, self.names, self),
            "repair": RepairPage(self.data, self.names, self),
        }
        # 导航项 (emoji + 文案)
        nav_items = [
            ("📊 " + str(i18n.tr("nav.overview")), "overview"),
            ("👤 " + str(i18n.tr("nav.character")), "character"),
            ("🪞 " + str(i18n.tr("quest.nav_karma")), "karma"),
            ("🐾 " + str(i18n.tr("quest.nav_vehicle")), "vehicle"),
            ("🔮 " + str(i18n.tr("quest.nav_rune")), "rune"),
            ("⚔ " + str(i18n.tr("nav.equipment")), "equipment"),
            ("🎒 " + str(i18n.tr("nav.inventory")), "inventory"),
            ("──────────", None),  # 分隔: 任务区
            ("📜 " + str(i18n.tr("quest.nav_main")), "quest_main"),
            ("🔗 " + str(i18n.tr("quest.nav_epic")), "quest_epic"),
            ("🦸 " + str(i18n.tr("quest.nav_character")), "quest_character"),
            ("🗺 " + str(i18n.tr("quest.nav_region")), "quest_region"),
            ("🎖 " + str(i18n.tr("quest.nav_grade")), "quest_grade"),
            ("📦 " + str(i18n.tr("quest.nav_other")), "quest_other"),
            ("🕳 " + str(i18n.tr("quest.nav_unreleased")), "quest_unreleased"),
            ("──────────", None),  # 分隔: 工具区
            ("🛠 " + str(i18n.tr("nav.tools")), "tools"),
            ("🧰 " + str(i18n.tr("nav.repair")), "repair"),
        ]
        for text, key in nav_items:
            it = QListWidgetItem(text)
            if key is None:
                it.setFlags(Qt.ItemFlag.NoItemFlags)  # 分隔不可选
                f = it.font()
                f.setBold(False)
                it.setFont(f)
            it.setData(Qt.ItemDataRole.UserRole, key)
            self.nav.addItem(it)

        for key in ["overview", "character", "karma", "vehicle", "rune", "equipment", "inventory",
                    "quest_main", "quest_epic", "quest_character", "quest_region",
                    "quest_grade", "quest_other", "quest_unreleased", "tools", "repair"]:
            self.stack.addWidget(self.pages[key])

        # 总览点击角色 -> 切到角色页并选中
        self.pages["overview"].character_clicked.connect(self._on_overview_char_clicked)

        self.stack.setCurrentWidget(self.pages["overview"])

    def _build_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)

    # ---------- 导航 ----------
    def _on_nav_changed(self, row):
        if row < 0:
            return
        it = self.nav.item(row)
        key = it.data(Qt.ItemDataRole.UserRole)
        if key and key in self.pages:
            self.stack.setCurrentWidget(self.pages[key])

    def _on_overview_char_clicked(self, cid):
        # 切到角色页并选中
        self.nav.setCurrentRow(self._nav_row_for("character"))
        self.pages["character"].select_character(cid)

    def _nav_row_for(self, key):
        for i in range(self.nav.count()):
            it = self.nav.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == key:
                return i
        return 0

    def select_character(self, cid):
        """公开方法: 选中指定角色 (供外部调用)。"""
        self._on_overview_char_clicked(cid)

    # ---------- 状态栏 ----------
    def set_status(self, text):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.status.showMessage(f"[{ts}] {text}", 0)

    # ---------- 未保存修改保护 ----------
    def _confirm_discard(self):
        """当前存档有未写入修改时, 确认是否放弃。
        返回 True=可以继续(无修改或用户确认), False=取消操作。"""
        if self.data.conn is None:
            return True
        try:
            if not self.data.build_diff():
                return True
        except Exception:
            return True
        ret = QMessageBox.question(
            self, str(i18n.tr("dialogs.confirm")),
            str(i18n.tr("dialogs.discard_changes")),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return ret == QMessageBox.StandardButton.Yes

    # ---------- 工具栏命令 ----------
    def cmd_open(self):
        start_dir = self.cfg.get("last_path", "") or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, str(i18n.tr("dialogs.open_title")),
            start_dir, str(i18n.tr("dialogs.file_filter")),
        )
        if not path:
            return
        # 打开新存档会覆盖当前内存修改, 先确认
        if not self._confirm_discard():
            return
        try:
            self.data.load(path)
        except ds_save.DSError as e:
            QMessageBox.critical(self, str(i18n.tr("status.error")),
                                 f"{i18n.tr('dialogs.unsupported_file')}: {e}")
            return
        except Exception as e:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(e))
            return

        self.cfg["last_path"] = os.path.dirname(path)
        config.save_config(self.cfg)
        fname = os.path.basename(path)
        self.title_label.setText(f"{fname}  ({self.data.table_count})")
        self.set_status(str(i18n.tr("status.loaded", path=fname, count=self.data.table_count)))
        # 刷新所有页面数据
        self.refresh_all_pages()
        # 切到总览页
        self.nav.setCurrentRow(self._nav_row_for("overview"))

    def cmd_backup(self):
        if not self.data.db_path:
            QMessageBox.information(self, "", str(i18n.tr("status.no_db")))
            return
        dlg = BackupDialog(self.data, self)
        dlg.exec()

    def cmd_restore(self):
        # 还原功能已整合到备份管理对话框
        if not self.data.db_path:
            QMessageBox.information(self, "", str(i18n.tr("status.no_db")))
            return
        # 还原会覆盖当前内存修改, 先确认
        if not self._confirm_discard():
            return
        dlg = BackupDialog(self.data, self)
        dlg.exec()

    def cmd_save(self):
        if not self.data.db_path:
            QMessageBox.information(self, "", str(i18n.tr("status.no_db")))
            return
        diff = self.data.build_diff()
        if not diff:
            QMessageBox.information(self, str(i18n.tr("diff_page.title")),
                                    str(i18n.tr("diff_page.no_changes")))
            return
        dlg = SaveDiffDialog(self.data, self, diff)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            bak = self.data.save_to_db()
        except ds_save.DSError as e:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, str(i18n.tr("status.error")), str(e))
            return
        self.set_status(str(i18n.tr("status.saved")) + " | " +
                        str(i18n.tr("backup_page.backup_done", path=bak)))
        self.refresh_all_pages()
        QMessageBox.information(self, str(i18n.tr("status.success")),
                                str(i18n.tr("status.saved")))

    def cmd_refresh(self):
        if not self.data.db_path:
            return
        self.refresh_all_pages()
        self.set_status(str(i18n.tr("status.ready")))

    def cmd_settings(self):
        dlg = SettingsDialog(self.cfg, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.cfg = dlg.cfg()
            QMessageBox.information(self, str(i18n.tr("settings.title")),
                                      str(i18n.tr("settings.saved")))

    # ---------- 刷新页面 ----------
    def refresh_all_pages(self):
        """刷新总览/角色/宿命烙印/使魔/符文/装备/背包/数据工具/任务各页数据。"""
        for key in ("overview", "character", "karma", "vehicle", "rune", "equipment", "inventory", "tools",
                    "repair",
                    "quest_main", "quest_epic", "quest_character", "quest_region",
                    "quest_grade", "quest_other", "quest_unreleased"):
            self.pages[key].reload()

    # ---------- 关闭 ----------
    def closeEvent(self, e):
        # 有未写入修改时, 关闭窗口前确认
        if not self._confirm_discard():
            e.ignore()
            return
        try:
            self.data.close()
        except Exception:
            pass
        super().closeEvent(e)
