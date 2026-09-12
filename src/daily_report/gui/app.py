"""Qt 应用入口：工作台首页 + 日报记录 + 悬浮随手记 + 托盘。"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from daily_report.config import find_config_file, load_config
from daily_report.gui.styles import build_qss

_CJK_CANDIDATES = (
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "Segoe UI",
    "PingFang SC",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "SimHei",
)

_WIN_FONT_FILES = (
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyh.ttf",
    r"C:\Windows\Fonts\msyhl.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
)


def _try_load_system_fonts() -> None:
    for path in _WIN_FONT_FILES:
        p = Path(path)
        if p.is_file():
            fid = QFontDatabase.addApplicationFont(str(p))
            if fid != -1:
                return


def _pick_font() -> QFont:
    available = set(QFontDatabase.families())
    for name in _CJK_CANDIDATES:
        if name in available:
            f = QFont(name)
            f.setPointSize(10)
            return f
    return QFont()


def _ensure_config() -> None:
    if find_config_file() is None:
        from daily_report.config import write_default_config

        dest = Path.cwd() / "config.yaml"
        try:
            write_default_config(dest)
        except OSError:
            pass


def _open_dir(path: Path) -> None:
    import os
    import subprocess

    path.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        os.startfile(path)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("工作台")
    app.setOrganizationName("daily-report")
    app.setQuitOnLastWindowClosed(False)  # 关窗后仍可从托盘呼出
    _try_load_system_fonts()
    app.setFont(_pick_font())
    app.setStyleSheet(build_qss())

    from daily_report.config import find_config_file, load_config as _reload_cfg
    from daily_report.gui.init_dialog import InitDialog

    if find_config_file() is None:
        dlg = InitDialog()
        if dlg.exec() and dlg.result_cfg:
            cfg = dlg.result_cfg
        else:
            from daily_report.config import MODE_BASIC, write_default_config

            dest = Path.cwd() / "config.yaml"
            write_default_config(dest, mode=MODE_BASIC)
            cfg = _reload_cfg(dest)
    else:
        cfg = _reload_cfg()

    from daily_report.gui.floating_log import FloatingLogWidget
    from daily_report.bug_store import BugStore
    from daily_report.gui.bug_window import BugWindow
    from daily_report.gui.games.hub import GameHubWindow
    from daily_report.gui.games.minesweeper import MinesweeperWindow
    from daily_report.gui.games.thunder import ThunderWindow
    from daily_report.gui.hub_window import HubWindow
    from daily_report.gui.main_window import MainWindow
    from daily_report.gui.settings_dialog import SettingsDialog
    from daily_report.gui.task_window import TaskWindow
    from daily_report.gui.tray import TrayManager
    from daily_report.storage import ReportStore
    from daily_report.tasks import TaskStore

    store = ReportStore(cfg.data_dir)
    bug_store = BugStore(cfg.data_dir)
    task_store = TaskStore(cfg.data_dir)

    hub = HubWindow(cfg, store)
    daily = MainWindow(cfg, store)
    daily.apply_mode()
    bugs = BugWindow(bug_store)
    tasks = TaskWindow(task_store, cfg)
    tasks.apply_config(cfg)
    games_hub = GameHubWindow()
    mines = MinesweeperWindow()
    thunder = ThunderWindow()
    float_log = FloatingLogWidget(store, bug_store)
    tray = TrayManager(app)

    state = {"cfg": cfg, "store": store, "bug_store": bug_store, "task_store": task_store}

    def refresh_windows() -> None:
        c = state["cfg"]
        s = state["store"]
        hub.set_config(c)
        hub.set_store(s)
        daily.apply_config(c)
        float_log.set_store(s, state.get("bug_store"))

    def show_hub() -> None:
        hub.show()
        hub.raise_()
        hub.activateWindow()

    def open_daily() -> None:
        daily.show()
        daily.raise_()
        daily.activateWindow()

    def open_bugs() -> None:
        bugs.show()
        bugs.raise_()
        bugs.activateWindow()

    def open_tasks() -> None:
        tasks.show()
        tasks.raise_()
        tasks.activateWindow()

    def open_games() -> None:
        mines.hide()
        thunder.hide()
        games_hub.show()
        games_hub.raise_()
        games_hub.activateWindow()

    def open_mine() -> None:
        thunder.hide()
        games_hub.hide()
        mines.show()
        mines.raise_()
        mines.activateWindow()

    def open_thunder() -> None:
        mines.hide()
        games_hub.hide()
        thunder.show()
        thunder.raise_()
        thunder.activateWindow()
        thunder.canvas.start_game()
        thunder.canvas.setFocus()

    def back_to_game_hub() -> None:
        mines.hide()
        thunder.hide()
        games_hub.show()
        games_hub.raise_()
        games_hub.activateWindow()

    def back_to_hub() -> None:
        daily.hide()
        bugs.hide()
        tasks.hide()
        games_hub.hide()
        mines.hide()
        thunder.hide()
        show_hub()

    def toggle_float() -> None:
        if float_log.isVisible():
            float_log.hide()
        else:
            float_log.show()
            float_log.raise_()
            float_log.activateWindow()
            float_log.input.setFocus()

    def open_settings() -> None:
        dlg = SettingsDialog(state["cfg"], hub)
        if dlg.exec():
            state["cfg"] = dlg.result_config()
            state["store"] = ReportStore(state["cfg"].data_dir)
            refresh_windows()

    def open_data_dir() -> None:
        _open_dir(state["store"].data_dir)

    def do_quit() -> None:
        float_log.hide()
        daily.hide()
        bugs.hide()
        tasks.hide()
        games_hub.hide()
        mines.hide()
        thunder.hide()
        hub.hide()
        tray.hide()
        app.quit()

    hub.open_daily.connect(open_daily)
    hub.open_bugs.connect(open_bugs)
    hub.open_tasks.connect(open_tasks)
    hub.open_games.connect(open_games)
    hub.open_settings.connect(open_settings)
    hub.toggle_floating.connect(toggle_float)
    hub.open_data_dir.connect(open_data_dir)
    daily.back_to_hub.connect(back_to_hub)
    bugs.back_to_hub.connect(back_to_hub)
    tasks.back_to_hub.connect(back_to_hub)
    games_hub.back_to_hub.connect(back_to_hub)
    games_hub.open_minesweeper.connect(open_mine)
    games_hub.open_thunder.connect(open_thunder)
    mines.back_to_hub.connect(back_to_game_hub)
    thunder.back_to_hub.connect(back_to_game_hub)

    def on_config_changed(c) -> None:  # noqa: ANN001
        state["cfg"] = c
        state["store"] = ReportStore(c.data_dir)
        state["bug_store"] = BugStore(c.data_dir)
        state["task_store"] = TaskStore(c.data_dir)
        bugs._store = state["bug_store"]  # noqa: SLF001
        bugs._reload_list()
        tasks.apply_config(c)
        tasks.set_store(state["task_store"])
        float_log.set_bug_store(state["bug_store"])
        refresh_windows()

    daily.config_changed.connect(on_config_changed)
    float_log.open_main.connect(open_daily)
    float_log.open_bugs.connect(open_bugs)
    float_log.logged.connect(lambda t: tray.notify("随手记", f"已记录：{t[:40]}"))
    float_log.bug_saved.connect(
        lambda s: (
            tray.notify("Bug 列表", f"已记录：{s[:40]}"),
            bugs._reload_list(),
        )
    )

    tray.show_hub_requested.connect(show_hub)
    tray.toggle_floating_requested.connect(toggle_float)
    tray.quit_requested.connect(do_quit)

    def hub_close(event) -> None:  # noqa: ANN001
        event.ignore()
        hub.hide()
        daily.hide()
        bugs.hide()
        tasks.hide()
        games_hub.hide()
        mines.hide()
        thunder.hide()
        tray.notify("工作台", "已最小化到托盘，可继续用悬浮随手记")

    hub.closeEvent = hub_close  # type: ignore[method-assign]

    def daily_close(event) -> None:  # noqa: ANN001
        event.ignore()
        daily.hide()

    def bugs_close(event) -> None:  # noqa: ANN001
        event.ignore()
        bugs.hide()

    def tasks_close(event) -> None:  # noqa: ANN001
        event.ignore()
        tasks.hide()

    daily.closeEvent = daily_close  # type: ignore[method-assign]
    bugs.closeEvent = bugs_close  # type: ignore[method-assign]
    tasks.closeEvent = tasks_close  # type: ignore[method-assign]

    show_hub()
    # 默认显示悬浮窗，方便随时记
    float_log.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
