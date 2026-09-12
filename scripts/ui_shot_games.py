"""知识星球 / 游戏截图冒烟。"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from daily_report.gui.app import _pick_font, _try_load_system_fonts  # noqa: E402
from daily_report.gui.games.hub import GameHubWindow  # noqa: E402
from daily_report.gui.games.minesweeper import MinesweeperWindow  # noqa: E402
from daily_report.gui.games.thunder import ThunderWindow  # noqa: E402
from daily_report.gui.styles import build_qss  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    _try_load_system_fonts()
    app.setFont(_pick_font())
    app.setStyleSheet(build_qss())

    hub = GameHubWindow()
    hub.resize(960, 580)
    hub.show()

    mine = MinesweeperWindow()
    mine.resize(900, 620)

    thunder = ThunderWindow()
    thunder.resize(700, 720)

    Path("data").mkdir(exist_ok=True)

    def s1() -> None:
        hub.grab().save("data/ui_gamehub.jpg", "JPG", 90)
        mine.show()
        mine.grab().save("data/ui_mine.jpg", "JPG", 90)

    def s2() -> None:
        thunder.show()
        # 跑几帧
        for _ in range(30):
            thunder.canvas._step()
        thunder.grab().save("data/ui_thunder.jpg", "JPG", 90)
        print("score", thunder.canvas.state.score, "lives", thunder.canvas.state.lives, "weapon", thunder.canvas.state.weapon)
        print("enemies", len(thunder.canvas.state.enemies))
        app.quit()

    QTimer.singleShot(300, s1)
    QTimer.singleShot(800, s2)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
