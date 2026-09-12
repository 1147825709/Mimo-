"""验证：首页 + 日报 + 悬浮窗截图。"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from daily_report.config import load_config  # noqa: E402
from daily_report.gui.app import _pick_font, _try_load_system_fonts  # noqa: E402
from daily_report.gui.floating_log import FloatingLogWidget  # noqa: E402
from daily_report.gui.hub_window import HubWindow  # noqa: E402
from daily_report.gui.main_window import MainWindow  # noqa: E402
from daily_report.gui.styles import build_qss  # noqa: E402
from daily_report.storage import ReportStore  # noqa: E402


def main() -> int:
    cfg = load_config()
    store = ReportStore(cfg.data_dir)
    app = QApplication(sys.argv)
    _try_load_system_fonts()
    app.setFont(_pick_font())
    app.setStyleSheet(build_qss())

    hub = HubWindow(cfg, store)
    daily = MainWindow(cfg, store)
    float_log = FloatingLogWidget(store)

    Path("data").mkdir(exist_ok=True)
    hub.resize(1100, 700)
    hub.show()
    daily.show()
    float_log.show()

    def shots() -> None:
        hub.grab().save("data/shot_hub_v3.png")
        daily.grab().save("data/shot_daily_v3.png")
        float_log.grab().save("data/shot_float_v3.png")
        print("hub title ok", hub.windowTitle())
        print("daily title", daily.windowTitle())
        print("float visible", float_log.isVisible())
        print("bg exists", __import__("daily_report.gui.resources", fromlist=["doraemon_bg_path"]).doraemon_bg_path())
        app.quit()

    QTimer.singleShot(600, shots)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
