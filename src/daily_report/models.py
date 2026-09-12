"""日报数据模型与 Markdown 序列化。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable


@dataclass
class WorkLogEntry:
    """当天随手记的一条工作流水。"""

    timestamp: datetime
    text: str

    @property
    def time_str(self) -> str:
        return self.timestamp.strftime("%H:%M")

    def to_line(self) -> str:
        return f"- {self.time_str} {self.text.strip()}"

    @classmethod
    def parse_line(cls, line: str, default_date: date) -> "WorkLogEntry | None":
        raw = line.strip()
        if not raw or raw.startswith("#"):
            return None
        if raw.startswith("- "):
            raw = raw[2:].strip()
        # 形如 09:30 正文
        if len(raw) >= 5 and raw[2] == ":" and raw[:2].isdigit():
            hh, mm = int(raw[:2]), int(raw[3:5])
            text = raw[5:].strip()
            ts = datetime(default_date.year, default_date.month, default_date.day, hh, mm)
            return cls(timestamp=ts, text=text)
        ts = datetime(default_date.year, default_date.month, default_date.day, 0, 0)
        return cls(timestamp=ts, text=raw)


@dataclass
class DailyReport:
    report_date: date
    goal: str = ""
    work_items: list[str] = field(default_factory=list)
    next_steps: str = ""

    @property
    def date_str(self) -> str:
        return self.report_date.isoformat()

    def to_markdown(self) -> str:
        lines: list[str] = [f"# 日报 {self.date_str}", ""]
        lines.append("## 任务目标")
        lines.append(self.goal.strip() or "（未填写）")
        lines.append("")
        lines.append("## 具体工作")
        if self.work_items:
            for i, item in enumerate(self.work_items, start=1):
                text = item.strip().replace("\n", " ")
                lines.append(f"{i}. {text}")
        else:
            lines.append("（未填写）")
        lines.append("")
        lines.append("## 下一步计划")
        lines.append(self.next_steps.strip() or "（未填写）")
        lines.append("")
        return "\n".join(lines)

    def body_text(self) -> str:
        """用于检索/汇总的纯文本。"""
        parts = [self.goal, "\n".join(self.work_items), self.next_steps]
        return "\n".join(p for p in parts if p)

    @classmethod
    def from_markdown(cls, text: str, report_date: date) -> "DailyReport":
        goal = ""
        work_items: list[str] = []
        next_steps = ""
        section: str | None = None
        buffer: list[str] = []

        def flush() -> None:
            nonlocal goal, next_steps, work_items, buffer
            if section == "任务目标":
                goal = "\n".join(buffer).strip()
            elif section == "下一步计划":
                next_steps = "\n".join(buffer).strip()
            elif section == "具体工作":
                items = []
                for line in buffer:
                    line = line.strip()
                    if not line or line == "（未填写）":
                        continue
                    # 去掉序号前缀 1. / 1、 等
                    if line[0].isdigit():
                        for sep in (".", "、", "．"):
                            if sep in line[:4]:
                                line = line.split(sep, 1)[1].strip()
                                break
                    items.append(line)
                work_items = items
            buffer = []

        for raw in text.splitlines():
            line = raw.rstrip()
            if line.startswith("## "):
                flush()
                title = line[3:].strip()
                if title.startswith("任务目标"):
                    section = "任务目标"
                elif title.startswith("具体工作"):
                    section = "具体工作"
                elif title.startswith("下一步计划"):
                    section = "下一步计划"
                else:
                    section = None
                continue
            if line.startswith("# "):
                continue
            if section:
                buffer.append(line)
        flush()

        return cls(
            report_date=report_date,
            goal=goal,
            work_items=work_items,
            next_steps=next_steps,
        )


def parse_work_items(raw: str | Iterable[str] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.split("|") if p.strip()]
        return parts
    return [str(p).strip() for p in raw if str(p).strip()]
