"""OpenAI 兼容协议客户端。"""

from __future__ import annotations

from daily_report.config import LLMConfig


class LLMClient:
    def __init__(self, cfg: LLMConfig):
        if not cfg.api_key:
            raise RuntimeError(
                "未配置 API Key。请在 config.yaml 的 llm.api_key 中设置，"
                "或导出环境变量 DAILY_REPORT_API_KEY / OPENAI_API_KEY。"
            )
        # 延迟导入，便于无 Key 时仍可写日报
        from openai import OpenAI

        self._cfg = cfg
        self._client = OpenAI(
            base_url=cfg.base_url,
            api_key=cfg.api_key,
            timeout=cfg.timeout,
        )

    def chat(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._cfg.model,
            temperature=self._cfg.temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = resp.choices[0].message.content
        return (content or "").strip()
