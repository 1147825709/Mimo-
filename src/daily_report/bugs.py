"""Bug 记录模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class BugStatus(str, Enum):
    OPEN = "待处理"
    FIXING = "修复中"
    RESOLVED = "已解决"
    WONTFIX = "暂不处理"
    DUPLICATE = "重复"

    @classmethod
    def from_str(cls, s: str) -> "BugStatus":
        s = (s or "").strip()
        for v in cls:
            if s in (v.value, v.name):
                return v
        return cls.OPEN


@dataclass
class BugRecord:
    bug_id: str
    title: str
    status: BugStatus = BugStatus.OPEN
    created_at: datetime | None = None
    tags: list[str] = field(default_factory=list)
    symptom: str = ""  # 现象
    error_info: str = ""  # 错误信息/日志
    root_cause: str = ""  # 根因
    solution: str = ""  # 解决方案
    env: str = ""  # 环境
    note: str = ""

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now()

    @property
    def created_str(self) -> str:
        return (self.created_at or datetime.now()).strftime("%Y-%m-%d %H:%M")

    def tags_text(self) -> str:
        return "、".join(self.tags)

    def full_text(self) -> str:
        parts = [
            self.title,
            self.symptom,
            self.error_info,
            self.root_cause,
            self.solution,
            self.env,
            self.note,
            " ".join(self.tags),
            self.status.value,
        ]
        return "\n".join(p for p in parts if p)

    def to_markdown(self) -> str:
        lines = [
            f"# {self.bug_id}",
            "",
            f"- 标题: {self.title}",
            f"- 状态: {self.status.value}",
            f"- 时间: {self.created_str}",
            f"- 标签: {self.tags_text() or '（无）'}",
            f"- 环境: {self.env or '（无）'}",
            "",
            "## 现象",
            self.symptom.strip() or "（未填写）",
            "",
            "## 错误信息",
            self.error_info.strip() or "（无）",
            "",
            "## 根因",
            self.root_cause.strip() or "（未填写）",
            "",
            "## 解决方案",
            self.solution.strip() or "（未填写）",
            "",
            "## 备注",
            self.note.strip() or "（无）",
            "",
        ]
        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, text: str, fallback_id: str) -> "BugRecord":
        title = ""
        status = BugStatus.OPEN
        created_at = datetime.now()
        tags: list[str] = []
        env = ""
        sections: dict[str, list[str]] = {}
        current: str | None = None

        for raw in text.splitlines():
            line = raw.rstrip()
            if line.startswith("# "):
                continue
            if line.startswith("- 标题:"):
                title = line.split(":", 1)[1].strip()
                continue
            if line.startswith("- 状态:"):
                status = BugStatus.from_str(line.split(":", 1)[1])
                continue
            if line.startswith("- 时间:"):
                try:
                    created_at = datetime.strptime(line.split(":", 1)[1].strip(), "%Y-%m-%d %H:%M")
                except ValueError:
                    pass
                continue
            if line.startswith("- 标签:"):
                raw_tags = line.split(":", 1)[1].strip()
                if raw_tags and raw_tags != "（无）":
                    for sep in ("、", ",", "，", " "):
                        raw_tags = raw_tags.replace(sep, "|")
                    tags = [t.strip() for t in raw_tags.split("|") if t.strip()]
                continue
            if line.startswith("- 环境:"):
                env = line.split(":", 1)[1].strip()
                if env == "（无）":
                    env = ""
                continue
            if line.startswith("## "):
                name = line[3:].strip()
                key = {
                    "现象": "symptom",
                    "错误信息": "error_info",
                    "根因": "root_cause",
                    "解决方案": "solution",
                    "备注": "note",
                }.get(name)
                current = key
                if key:
                    sections[key] = []
                continue
            if current:
                sections.setdefault(current, []).append(line)

        def join_block(key: str) -> str:
            body = "\n".join(sections.get(key, [])).strip()
            if body == "（未填写）" or body == "（无）":
                return ""
            return body

        return cls(
            bug_id=fallback_id,
            title=title or fallback_id,
            status=status,
            created_at=created_at,
            tags=tags,
            symptom=join_block("symptom"),
            error_info=join_block("error_info"),
            root_cause=join_block("root_cause"),
            solution=join_block("solution"),
            env=env,
            note=join_block("note"),
        )
