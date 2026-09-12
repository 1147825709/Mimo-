"""本地 OpenAI 兼容 mock，仅用于开发自测：python mock_llm_server.py"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # noqa: A003
        print(f"[mock] {self.address_string()} {fmt % args}")

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            req = json.loads(body.decode("utf-8"))
        except Exception:
            req = {}
        user_msg = ""
        for m in req.get("messages", []):
            if m.get("role") == "user":
                user_msg = m.get("content", "")

        if "拆分成可执行的小任务" in user_msg or "子任务列表" in user_msg:
            content = (
                "- 明确需求与验收标准\n"
                "- 完成核心接口与存储\n"
                "- 实现 GUI 与交互\n"
                "- 编写测试并跑通\n"
                "- 更新文档与自测清单\n"
            )
        elif "工作流水" in user_msg and "任务目标" in user_msg and "具体工作" in user_msg:
            # 日报成稿 mock
            date_hint = "2026-09-11"
            for line in user_msg.splitlines():
                if line.startswith("请根据以下 ") and " 的工作流水" in line:
                    date_hint = line.split(" ")[2] if len(line.split(" ")) > 2 else date_hint
                    break
            content = (
                f"# 日报 {date_hint}\n\n"
                "## 任务目标\n"
                "完善日报工具的随手记与 AI 成稿能力。\n\n"
                "## 具体工作\n"
                "1. 修复了搜索 AND 语义\n"
                "2. 给 GUI 增加随手记面板\n"
                "3. 补充单元测试并跑通\n\n"
                "## 下一步计划\n"
                "接入真实模型验证周报/月报汇总效果。\n"
            )
        elif "周报" in user_msg:
            content = (
                "# 周报（mock）\n\n"
                "## 本周概览\n基于日报自动汇总的示意内容。\n\n"
                "## 主要工作\n1. 框架搭建\n2. 搜索与导出\n\n"
                "## 成果与亮点\n- 可用 CLI\n\n"
                "## 问题与风险\n- 无\n\n"
                "## 下周计划\n- 接入真实模型\n\n"
                f"> 来源日报长度: {len(user_msg)}"
            )
        else:
            content = (
                "# 月报（mock）\n\n"
                "## 本月概览\n月度进展示意。\n\n"
                "## 重点工作\n1. 工具建设\n\n"
                "## 关键成果\n- 可用 GUI\n\n"
                "## 问题与改进\n- 无\n\n"
                "## 下月展望\n- 持续迭代\n"
            )
        payload = {
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "model": req.get("model", "mock"),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8765), Handler)
    print("Mock OpenAI server on http://127.0.0.1:8765/v1")
    server.serve_forever()
