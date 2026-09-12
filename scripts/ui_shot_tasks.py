"""任务计划窗口截图。"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from daily_report.config import load_config  # noqa: E402
from daily_report.gui.app import _pick_font, _try_load_system_fonts  # noqa: E402
from daily_report.gui.styles import build_qss  # noqa: E402
from daily_report.gui.task_window import TaskWindow  # noqa: E402
from daily_report.tasks import SubTask, TaskStore  # noqa: E402


def main() -> int:
    cfg = load_config()
    ts = TaskStore(cfg.data_dir)
    if not ts.list_ids():
        t = ts.create(
            title="优化工作台任务计划模块",
            description="完成 GUI、AI 拆分、进度显示",
            deadline=date.today() + timedelta(days=5),
        )
        t.subtasks = [
            SubTask("明确需求与验收标准", True),
            SubTask("完成核心接口与存储", True),
            SubTask("实现 GUI 与交互", False),
            SubTask("编写测试并跑通", False),
        ]
        ts.save(t)

    app = QApplication(sys.argv)
    _try_load_system_fonts()
    app.setFont(_pick_font())
    app.setStyleSheet(build_qss())
    win = TaskWindow(ts, cfg)
    win.resize(1180, 800)
    win.show()
    if win.list_widget.count():
        win.list_widget.setCurrentRow(0)

    def shot() -> None:
        Path("data").mkdir(exist_ok=True)
        win.grab().save("data/ui_tasks.jpg", "JPG", 92)
        print("progress", win.progress_bar.value(), win.lbl_remain.text(), win.lbl_subcount.text())
        app.quit()

    QTimer.singleShot(500, shot)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
