import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app import i18n
from app.ui_achievement import AchievementPage


class FakeSaveData:
    db_path = "memory"

    def __init__(self):
        self.row = {"USER_DBID": 1000, "GROUP_ID": 100017, "STEP": 0, "CNT": 164}

    def select_all(self, table, where="", params=()):
        if table == "tb_achievement_count":
            return [dict(self.row)]
        return []

    def execute(self, sql, params=()):
        self.row["STEP"], self.row["CNT"] = params[:2]


class FeatureLocaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_achievement_page_is_localized_for_every_supported_language(self):
        expected_titles = {
            "zh_CN": "今日菜谱：完全制霸！",
            "zh_TW": "今日菜譜：完全制霸！",
            "en": "Today's Menu: Total Domination!",
            "ja": "本日のレシピ：完全制覇！",
            "ko_KR": "오늘의 레시피: 완전 정복!",
            "de": "Heutiges Rezept: vollständig gemeistert!",
            "fr": "Menu du jour : maîtrise totale !",
            "es_ES": "Menú de hoy: ¡dominio total!",
            "pt_BR": "Cardápio de hoje: domínio total!",
            "ru": "Меню дня: полное господство!",
            "th": "เมนูวันนี้: พิชิตครบถ้วน!",
        }
        main_window = SimpleNamespace(set_status=lambda _text: None)

        for language, expected_title in expected_titles.items():
            with self.subTest(language=language):
                i18n.set_language(language)
                page = AchievementPage(FakeSaveData(), None, main_window)
                page.reload()
                self.assertEqual(page.table.columnCount(), 5)
                self.assertEqual(page.table.item(0, 0).text(), expected_title)
                self.assertEqual(page.table.item(0, 3).text(), "164")
                self.assertEqual(page.table.item(0, 4).text(), "1000")
                self.assertNotEqual(i18n.tr("nav.achievement"), "nav.achievement")
                self.assertNotEqual(
                    i18n.tr("equipment_page.character_filter"),
                    "equipment_page.character_filter",
                )

    def test_applying_a_change_keeps_table_geometry_and_selection(self):
        i18n.set_language("zh_CN")
        data = FakeSaveData()
        page = AchievementPage(
            data, None, SimpleNamespace(set_status=lambda _text: None))
        page.resize(1200, 720)
        page.show()
        self.app.processEvents()
        page.reload()
        page.table.selectRow(0)
        self.app.processEvents()
        widths_before = [page.table.columnWidth(i) for i in range(5)]

        page.step_spin.setValue(1)
        page.count_spin.setValue(999)
        page._apply_selected()
        self.app.processEvents()

        self.assertEqual(page.table.currentRow(), 0)
        self.assertEqual(page.table.item(0, 2).text(), "1")
        self.assertEqual(page.table.item(0, 3).text(), "999")
        self.assertEqual(
            [page.table.columnWidth(i) for i in range(5)], widths_before)
        self.assertGreater(sum(widths_before), page.table.viewport().width() - 8)


if __name__ == "__main__":
    unittest.main()
