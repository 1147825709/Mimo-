"""任务计划：大目标 + 截止日期 + 子任务进度。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path


@dataclass
class SubTask:
    title: str
    done: bool = False

    def to_line(self) -> str:
        mark = "x" if self.done else " "
        return f"- [{mark}] {self.title.strip()}"

    @classmethod
    def parse_line(cls, line: str) -> "SubTask | None":
        raw = line.strip()
        if not raw.startswith("-"):
            return None
        raw = raw[1:].strip()
        # - [x] 标题 或 - [ ] 标题
        m = re.match(r"\[([ xX])\]\s*(.+)", raw)
        if m:
            done = m.group(1).lower() == "x"
            return cls(title=m.group(2).strip(), done=done)
        # - 标题
        if raw.startswith("["):
            return None
        return cls(title=raw, done=False)


@dataclass
class TaskPlan:
    task_id: str
    title: str
    description: str = ""
    deadline: date | None = None
    status: str = "进行中"  # 进行中 / 已完成 / 已取消
    created_at: datetime | None = None
    subtasks: list[SubTask] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now()

    @property
    def created_str(self) -> str:
        return (self.created_at or datetime.now()).strftime("%Y-%m-%d %H:%M")

    @property
    def deadline_str(self) -> str:
        return self.deadline.isoformat() if self.deadline else ""

    @property
    def total(self) -> int:
        return len(self.subtasks)

    @property
    def done_count(self) -> int:
        return sum(1 for s in self.subtasks if s.done)

    @property
    def progress(self) -> float:
        if not self.subtasks:
            return 1.0 if self.status == "已完成" else 0.0
        return self.done_count / len(self.subtasks)

    @property
    def progress_pct(self) -> int:
        return int(round(self.progress * 100))

    def days_left(self, today: date | None = None) -> int | None:
        if not self.deadline:
            return None
        today = today or date.today()
        return (self.deadline - today).days

    def remaining_text(self, today: date | None = None) -> str:
        if self.status == "已完成":
            return "已完成"
        if self.status == "已取消":
            return "已取消"
        d = self.days_left(today)
        if d is None:
            return "未设截止日"
        if d < 0:
            return f"已逾期 {-d} 天"
        if d == 0:
            return "今天截止"
        return f"剩余 {d} 天"

    def to_markdown(self) -> str:
        lines = [
            f"# {self.task_id}",
            "",
            f"- 标题: {self.title}",
            f"- 状态: {self.status}",
            f"- 截止: {self.deadline_str or '（未设置）'}",
            f"- 创建: {self.created_str}",
            f"- 进度: {self.done_count}/{self.total} ({self.progress_pct}%)",
            "",
            "## 描述",
            self.description.strip() or "（无）",
            "",
            "## 子任务",
        ]
        if self.subtasks:
            lines.extend(s.to_line() for s in self.subtasks)
        else:
            lines.append("- [ ] （暂无，可用 AI 拆分）")
        lines.append("")
        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, text: str, fallback_id: str) -> "TaskPlan":
        title = ""
        status = "进行中"
        deadline: date | None = None
        created_at = datetime.now()
        description_lines: list[str] = []
        subtasks: list[SubTask] = []
        section: str | None = None

        for raw in text.splitlines():
            line = raw.rstrip()
            if line.startswith("# "):
                continue
            if line.startswith("- 标题:"):
                title = line.split(":", 1)[1].strip()
                continue
            if line.startswith("- 状态:"):
                status = line.split(":", 1)[1].strip() or "进行中"
                continue
            if line.startswith("- 截止:"):
                ds = line.split(":", 1)[1].strip()
                if ds and ds != "（未设置）":
                    try:
                        deadline = date.fromisoformat(ds[:10])
                    except ValueError:
                        pass
                continue
            if line.startswith("- 创建:"):
                try:
                    created_at = datetime.strptime(
                        line.split(":", 1)[1].strip(), "%Y-%m-%d %H:%M"
                    )
                except ValueError:
                    pass
                continue
            if line.startswith("- 进度:"):
                continue
            if line.startswith("## "):
                name = line[3:].strip()
                section = name
                continue
            if section == "描述":
                if line.strip() and line.strip() != "（无）":
                    description_lines.append(line)
            elif section == "子任务":
                st = SubTask.parse_line(line)
                if st and not (st.title == "（暂无，可用 AI 拆分）"):
                    subtasks.append(st)

        return cls(
            task_id=fallback_id,
            title=title or fallback_id,
            description="\n".join(description_lines).strip(),
            deadline=deadline,
            status=status,
            created_at=created_at,
            subtasks=subtasks,
        )


class TaskStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.tasks_dir = data_dir / "tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, task_id: str) -> Path:
        safe = re.sub(r"[^\w\-]+", "_", task_id)
        return self.tasks_dir / f"{safe}.md"

    def next_id(self, when: datetime | None = None) -> str:
        when = when or datetime.now()
        prefix = when.strftime("TASK-%Y%m%d")
        n = 1
        while True:
            tid = f"{prefix}-{n:03d}"
            if not self.path_for(tid).exists():
                return tid
            n += 1

    def save(self, task: TaskPlan) -> Path:
        path = self.path_for(task.task_id)
        path.write_text(task.to_markdown(), encoding="utf-8")
        return path

    def load(self, task_id: str) -> TaskPlan | None:
        path = self.path_for(task_id)
        if not path.is_file():
            return None
        return TaskPlan.from_markdown(path.read_text(encoding="utf-8"), task_id)

    def create(
        self,
        title: str,
        description: str = "",
        deadline: date | None = None,
    ) -> TaskPlan:
        task = TaskPlan(
            task_id=self.next_id(),
            title=title.strip(),
            description=description.strip(),
            deadline=deadline,
        )
        self.save(task)
        return task

    def list_ids(self) -> list[str]:
        return [p.stem for p in sorted(self.tasks_dir.glob("*.md"))]

    def load_all(self) -> list[TaskPlan]:
        tasks = []
        for tid in self.list_ids():
            t = self.load(tid)
            if t:
                tasks.append(t)
        return tasks

    def delete(self, task_id: str) -> bool:
        path = self.path_for(task_id)
        if path.is_file():
            path.unlink()
            return True
        return False
