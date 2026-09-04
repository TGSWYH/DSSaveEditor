import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app import i18n
from app.ui_achievement import AchievementPage


class FakeSaveData:
    db_path = "memory"

    def select_all(self, table, where="", params=()):
        if table == "tb_achievement_count":
            return [{"USER_DBID": 1000, "GROUP_ID": 100017, "STEP": 0, "CNT": 164}]
        return []


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


if __name__ == "__main__":
    unittest.main()
