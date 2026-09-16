"""全局搜索：日报 / 流水 / Bug / 任务。"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from daily_report.bug_store import BugStore
from daily_report.storage import ReportStore
from daily_report.tasks import TaskStore


class GlobalSearchDialog(QDialog):
    open_daily = Signal(date)
    open_bug = Signal(str)
    open_task = Signal(str)

    def __init__(
        self,
        report_store: ReportStore,
        bug_store: BugStore,
        task_store: TaskStore,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("全局搜索")
        self.setMinimumSize(640, 480)
        self._rs = report_store
        self._bs = bug_store
        self._ts = task_store

        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.q = QLineEdit()
        self.q.setPlaceholderText("搜索日报、流水、Bug、任务…（空格分词 AND）")
        self.q.returnPressed.connect(self._search)
        btn = QPushButton("搜索")
        btn.setObjectName("PrimaryBig")
        btn.clicked.connect(self._search)
        row.addWidget(self.q, 1)
        row.addWidget(btn)
        lay.addLayout(row)

        self.results = QListWidget()
        self.results.itemDoubleClicked.connect(self._activate)
        lay.addWidget(self.results, 1)

        tip = QLabel("双击打开对应条目")
        tip.setStyleSheet("color:#7A8B9A;")
        lay.addWidget(tip)
        self.q.setFocus()

    def _search(self) -> None:
        raw = self.q.text().strip()
        if not raw:
            self.results.clear()
            return
        keys = raw.split()
        self.results.clear()
        hay_keys = [k.lower() for k in keys]

        def match(text: str) -> bool:
            t = (text or "").lower()
            return all(k in t for k in hay_keys)

        # 日报
        for d in self._rs.list_dates():
            r = self._rs.load(d)
            if not r:
                continue
            body = f"{r.goal}\n" + "\n".join(r.work_items) + f"\n{r.next_steps}"
            if match(body) or match(d.isoformat()):
                item = QListWidgetItem(f"[日报] {d.isoformat()}  {(r.goal or '').splitlines()[0][:30] if r.goal else ''}")
                item.setData(Qt.ItemDataRole.UserRole, ("daily", d.isoformat()))
                self.results.addItem(item)

        # 流水
        for d in self._rs.list_log_dates():
            logs = self._rs.load_logs(d)
            hits = [e for e in logs if match(e.text)]
            if hits:
                preview = "；".join(e.text[:20] for e in hits[:2])
                item = QListWidgetItem(f"[流水] {d.isoformat()}  {preview}")
                item.setData(Qt.ItemDataRole.UserRole, ("daily", d.isoformat()))
                self.results.addItem(item)

        # Bug
        for b in self._bs.load_all():
            if match(b.full_text()):
                item = QListWidgetItem(f"[Bug] {b.bug_id}  {b.title[:40]}")
                item.setData(Qt.ItemDataRole.UserRole, ("bug", b.bug_id))
                self.results.addItem(item)

        # 任务
        for t in self._ts.load_all():
            body = f"{t.title}\n{t.description}\n" + "\n".join(s.title for s in t.subtasks)
            if match(body):
                item = QListWidgetItem(f"[任务] {t.task_id}  [{t.progress_pct}%] {t.title[:30]}")
                item.setData(Qt.ItemDataRole.UserRole, ("task", t.task_id))
                self.results.addItem(item)

        self.results.insertItem(0, QListWidgetItem(f"共 {self.results.count()} 条结果"))

    def _activate(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, val = data
        if kind == "daily":
            self.open_daily.emit(date.fromisoformat(val))
        elif kind == "bug":
            self.open_bug.emit(val)
        elif kind == "task":
            self.open_task.emit(val)
        self.accept()
