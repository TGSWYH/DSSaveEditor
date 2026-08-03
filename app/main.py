# -*- coding: utf-8 -*-
"""入口: 读配置 -> 设置语言 -> 免责声明 -> 建主窗口。

main(smoke=False): 正常启动 (先展示免责声明, 点"我已了解"后进入)。
main(smoke=True): 冒烟模式, 跳过免责声明, 主窗口自动关闭, 用于验证不崩溃。
"""
import sys

from PySide6.QtWidgets import QApplication

from . import i18n, config
from .ui_theme import apply_theme
from .ui_common import DisclaimerDialog
from .ui_main import MainWindow


def main(smoke=False):
    # 1. 读配置 (文件缺失/损坏时用默认, 默认语言 en)
    cfg = config.load_config()

    # 2. 设置语言 (保留用户在 config 里选的语言, 不强制重置)
    i18n.set_language(cfg.get("language", "en"))

    # 3. 建应用
    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app, cfg.get("theme", "dark"))

    # 4. 免责声明 (每次启动必看, 防止盗用者隐藏; 冒烟模式跳过避免卡住)
    if not smoke:
        dlg = DisclaimerDialog()
        dlg.exec()

    # 5. 主窗口
    win = MainWindow(cfg, smoke=smoke)
    win.show()

    if smoke:
        from PySide6.QtCore import QTimer
        # 兜底: 2.5s 后退出整个应用
        QTimer.singleShot(2500, app.quit)

    return app.exec()


if __name__ == "__main__":
    main()