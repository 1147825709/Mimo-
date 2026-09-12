"""悬浮窗双模式截图：流水 / Bug。"""

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
from daily_report.gui.floating_log import FloatingLogWidget  # noqa: E402
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

    fl = FloatingLogWidget(rstore, bstore)
    fl.show()
    fl.adjustSize()

    Path("data").mkdir(exist_ok=True)

    def shot_log() -> None:
        fl._set_mode("log")
        fl.adjustSize()
        fl.grab().save("data/ui_float_log.jpg", "JPG", 92)
        print("log mode", fl.title_lb.text(), fl.width(), fl.height())

    def shot_bug() -> None:
        fl._set_mode("bug")
        fl.bug_title.setText("悬浮窗记一条示例 Bug")
        fl.bug_symptom.setText("复现步骤 xxx 报错 yyy")
        fl.bug_tags.setText("悬浮,示例")
        fl.adjustSize()
        fl.grab().save("data/ui_float_bug.jpg", "JPG", 92)
        print("bug mode", fl.title_lb.text(), fl.width(), fl.height())
        # 真正保存一条
        fl._save_bug()
        bugs = bstore.load_all()
        print("bug count", len(bugs), "last", bugs[-1].title if bugs else None)
        print("saved", QImage("data/ui_float_bug.jpg").width())
        app.quit()

    QTimer.singleShot(300, shot_log)
    QTimer.singleShot(600, shot_bug)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
