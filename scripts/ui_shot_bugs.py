"""BugList 窗口截图。"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from daily_report.bug_store import BugStore  # noqa: E402
from daily_report.config import load_config  # noqa: E402
from daily_report.gui.app import _pick_font, _try_load_system_fonts  # noqa: E402
from daily_report.gui.bug_window import BugWindow  # noqa: E402
from daily_report.gui.hub_window import HubWindow  # noqa: E402
from daily_report.gui.styles import build_qss  # noqa: E402
from daily_report.storage import ReportStore  # noqa: E402


def main() -> int:
    cfg = load_config()
    rstore = ReportStore(cfg.data_dir)
    bstore = BugStore(cfg.data_dir)
    app = QApplication(sys.argv)
    _try_load_system_fonts()
    app.setFont(_pick_font())
    app.setStyleSheet(build_qss())

    hub = HubWindow(cfg, rstore)
    hub.resize(1180, 700)
    hub.show()

    bugs = BugWindow(bstore)
    bugs.resize(1200, 800)
    bugs.show()
    if bugs.list_widget.count():
        bugs.list_widget.setCurrentRow(0)

    def shots() -> None:
        hub.grab().save("data/ui_hub_bugs.jpg", "JPG", 92)
        bugs.grab().save("data/ui_buglist.jpg", "JPG", 92)
        print("hub", QImage("data/ui_hub_bugs.jpg").width())
        print("bugs", QImage("data/ui_buglist.jpg").width(), QImage("data/ui_buglist.jpg").height())
        print("bug count in list", bugs.list_widget.count())
        app.quit()

    QTimer.singleShot(600, shots)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
