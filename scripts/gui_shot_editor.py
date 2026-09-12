"""单独截取编辑页（随手记 + AI 成稿）。"""

import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from daily_report.config import Config, LLMConfig, load_config  # noqa: E402
from daily_report.gui.app import _pick_font, _try_load_system_fonts  # noqa: E402
from daily_report.gui.main_window import MainWindow  # noqa: E402


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):  # noqa: N802
        import json

        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)
        try:
            req = json.loads(raw.decode() or "{}")
        except Exception:
            req = {}
        user = ""
        for m in req.get("messages", []):
            if m.get("role") == "user":
                user = m.get("content", "")
        content = (
            "# 日报 2026-09-11\n\n## 任务目标\n完善随手记与 AI 成稿。\n\n"
            "## 具体工作\n1. GUI冒烟：随手记一条\n2. 验证 AI 成稿链路\n\n"
            "## 下一步计划\n接入真实模型。\n"
        ) if "工作流水" in user else "ok"
        body = {
            "id": "c",
            "object": "chat.completion",
            "model": "mock",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
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
    srv = HTTPServer(("127.0.0.1", 8767), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    cfg = load_config()
    cfg = Config(
        llm=LLMConfig(base_url="http://127.0.0.1:8767/v1", api_key="m", model="mock"),
        data_dir=cfg.data_dir,
        config_path=cfg.config_path,
    )
    app = QApplication(sys.argv)
    _try_load_system_fonts()
    app.setFont(_pick_font())
    win = MainWindow(cfg)
    win.show()

    def go() -> None:
        win.tabs.setCurrentIndex(0)
        win._load_report(win._current_date)
        win.log_input.setText("验证新编辑页截图")
        win._add_log()
        win._run_compose()

    def shot() -> None:
        win.tabs.setCurrentIndex(0)
        Path("data").mkdir(exist_ok=True)
        win.grab().save("data/gui_editor_v2.png")
        print("title:", win.editor_title.text())
        print("tabs:", [win.tabs.tabText(i) for i in range(win.tabs.count())])
        print("goal:", win.goal_edit.toPlainText()[:50])
        print("logs:", win.log_count_label.text())
        srv.shutdown()
        app.quit()

    QTimer.singleShot(400, go)
    QTimer.singleShot(2200, shot)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
