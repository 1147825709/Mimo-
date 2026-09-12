"""截图：首页 / 日报 / 悬浮窗（唯一文件名，避免缓存混淆）。"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from daily_report.config import load_config  # noqa: E402
from daily_report.gui.app import _pick_font, _try_load_system_fonts  # noqa: E402
from daily_report.gui.floating_log import FloatingLogWidget  # noqa: E402
from daily_report.gui.hub_window import HubWindow  # noqa: E402
from daily_report.gui.main_window import MainWindow  # noqa: E402
from daily_report.gui.styles import build_qss  # noqa: E402
from daily_report.storage import ReportStore  # noqa: E402


def _valid(path: str) -> None:
    im = QImage(path)
    print(f"  {path}: {im.width()}x{im.height()} null={im.isNull()}")


def main() -> int:
    cfg = load_config()
    store = ReportStore(cfg.data_dir)
    app = QApplication(sys.argv)
    _try_load_system_fonts()
    app.setFont(_pick_font())
    app.setStyleSheet(build_qss())

    Path("data").mkdir(exist_ok=True)

    hub = HubWindow(cfg, store)
    hub.resize(1100, 700)
    hub.show()

    daily = MainWindow(cfg, store)
    daily.resize(1180, 780)
    daily.show()

    float_log = FloatingLogWidget(store)
    # 悬浮窗自适应尺寸
    float_log.show()
    float_log.adjustSize()

    def shots() -> None:
        hub.grab().save("data/ui_hub.jpg", "JPG", 92)
        daily.grab().save("data/ui_daily.jpg", "JPG", 92)
        float_log.grab().save("data/ui_float.jpg", "JPG", 92)
        print("saved")
        _valid("data/ui_hub.jpg")
        _valid("data/ui_daily.jpg")
        _valid("data/ui_float.jpg")
        print("float size", float_log.width(), float_log.height())
        app.quit()

    QTimer.singleShot(700, shots)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
