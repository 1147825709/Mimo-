"""Bug 本地存储。"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from daily_report.bugs import BugRecord


class BugStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.bugs_dir = data_dir / "bugs"
        self.bugs_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, bug_id: str) -> Path:
        safe = re.sub(r"[^\w\-]+", "_", bug_id)
        return self.bugs_dir / f"{safe}.md"

    def next_id(self, when: datetime | None = None) -> str:
        when = when or datetime.now()
        prefix = when.strftime("BUG-%Y%m%d")
        n = 1
        while True:
            bid = f"{prefix}-{n:03d}"
            if not self.path_for(bid).exists():
                return bid
            n += 1

    def save(self, bug: BugRecord) -> Path:
        path = self.path_for(bug.bug_id)
        path.write_text(bug.to_markdown(), encoding="utf-8")
        return path

    def load(self, bug_id: str) -> BugRecord | None:
        path = self.path_for(bug_id)
        if not path.is_file():
            return None
        text = path.read_text(encoding="utf-8")
        return BugRecord.from_markdown(text, bug_id)

    def create(
        self,
        title: str,
        symptom: str = "",
        error_info: str = "",
        root_cause: str = "",
        solution: str = "",
        tags: list[str] | None = None,
        env: str = "",
        note: str = "",
    ) -> BugRecord:
        bug = BugRecord(
            bug_id=self.next_id(),
            title=title.strip(),
            symptom=symptom.strip(),
            error_info=error_info.strip(),
            root_cause=root_cause.strip(),
            solution=solution.strip(),
            tags=[t.strip() for t in (tags or []) if t.strip()],
            env=env.strip(),
            note=note.strip(),
        )
        self.save(bug)
        return bug

    def list_ids(self) -> list[str]:
        ids = []
        for p in sorted(self.bugs_dir.glob("*.md")):
            ids.append(p.stem)
        return ids

    def load_all(self) -> list[BugRecord]:
        bugs = []
        for bid in self.list_ids():
            b = self.load(bid)
            if b:
                bugs.append(b)
        return bugs

    def delete(self, bug_id: str) -> bool:
        path = self.path_for(bug_id)
        if path.is_file():
            path.unlink()
            return True
        return False

    def export_index(self) -> str:
        """简易索引文本，便于调试。"""
        lines = []
        for b in self.load_all():
            lines.append(f"{b.bug_id}\t{b.status.value}\t{b.title}\t{b.tags_text()}")
        return "\n".join(lines)
