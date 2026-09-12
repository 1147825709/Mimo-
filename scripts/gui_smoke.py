"""GUI 冒烟：截图 + 模拟周报总结。"""

from __future__ import annotations

import os
import sys
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from daily_report.config import Config, LLMConfig, load_config  # noqa: E402
from daily_report.gui.app import _pick_font, _try_load_system_fonts  # noqa: E402
from daily_report.gui.main_window import MainWindow  # noqa: E402
from daily_report.storage import ReportStore, week_range  # noqa: E402


class _H(BaseHTTPRequestHandler):
    def log_message(self, *args):  # noqa: A003
        pass

    def do_POST(self):  # noqa: N802
        import json

        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)
        try:
            req = json.loads(raw.decode("utf-8"))
        except Exception:
            req = {}
        user_msg = ""
        for m in req.get("messages", []):
            if m.get("role") == "user":
                user_msg = m.get("content", "")
        if "工作流水" in user_msg and "具体工作" in user_msg:
            content = (
                "# 日报 2026-09-11\n\n"
                "## 任务目标\n完善随手记与 AI 成稿。\n\n"
                "## 具体工作\n1. GUI冒烟：随手记一条\n2. 验证 AI 成稿链路\n\n"
                "## 下一步计划\n接入真实模型。\n"
            )
        else:
            content = "# 周报 mock\n\n## 本周概览\n界面链路验证通过。"
        body = {
            "id": "c",
            "object": "chat.completion",
            "model": "mock",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content,
                    },
                    "finish_reason": "stop",
                }
            ],
        }
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> int:
    server = HTTPServer(("127.0.0.1", 8766), _H)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    cfg = load_config()
    cfg = Config(
        llm=LLMConfig(
            base_url="http://127.0.0.1:8766/v1",
            api_key="mock",
            model="mock",
        ),
        data_dir=cfg.data_dir,
        config_path=cfg.config_path,
    )

    app = QApplication(sys.argv)
    _try_load_system_fonts()
    app.setFont(_pick_font())
    win = MainWindow(cfg)
    win.show()

    out = Path("data/gui_smoke.png")
    out.parent.mkdir(parents=True, exist_ok=True)

    def step1() -> None:
        win.tabs.setCurrentIndex(0)
        win.log_input.setText("GUI冒烟：随手记一条")
        win._add_log()
        win.grab().save("data/gui_logs.png")
        print("logs:", win.log_count_label.text())
        win._run_compose()

    def step1b() -> None:
        print("compose goal:", win.goal_edit.toPlainText()[:40].replace("\n", " | "))
        win.grab().save("data/gui_editor.png")
        win.tabs.setCurrentIndex(1)
        win._update_summary_range()
        win._run_summary()

    def step2() -> None:
        text = win.summary_view.toPlainText()
        print("summary_text:", text[:80].replace("\n", " | "))
        win.grab().save("data/gui_summary.png")
        win.tabs.setCurrentIndex(2)
        win.search_input.setText("随手记")
        win._run_search()
        win.grab().save("data/gui_search.png")
        print("shots done")
        server.shutdown()
        app.quit()

    QTimer.singleShot(600, step1)
    QTimer.singleShot(2500, step1b)
    QTimer.singleShot(4500, step2)
    rc = app.exec()
    print("exit", rc)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
