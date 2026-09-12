"""后台线程：LLM 总结、耗时 IO。"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal

from daily_report.config import Config
from daily_report.models import DailyReport, WorkLogEntry
from daily_report.prompts import (
    SYSTEM_DAILY_COMPOSE,
    SYSTEM_SUMMARY,
    SYSTEM_TASK_BREAKDOWN,
    parse_daily_report,
    parse_subtasks,
)


def _fill_tpl(tpl: str, **kw: str) -> str:
    out = tpl
    for k, v in kw.items():
        out = out.replace("{" + k + "}", str(v if v is not None else ""))
    return out


def _reports_block(reports: list[DailyReport]) -> str:
    chunks = []
    for r in reports:
        work = "\n".join(f"  - {w}" for w in r.work_items) or "  （无）"
        chunks.append(
            f"### {r.date_str}\n任务目标：{r.goal or '（无）'}\n"
            f"具体工作：\n{work}\n下一步计划：{r.next_steps or '（无）'}"
        )
    return "\n\n".join(chunks)


def _logs_block(logs: list[WorkLogEntry]) -> str:
    return "\n".join(e.to_line() for e in logs) or "（无流水）"


class Worker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, fn: Callable[[], object]):
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
            self.finished.emit(result)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class SummaryWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)
    status = Signal(str)

    def __init__(
        self,
        cfg: Config,
        reports: list[DailyReport],
        mode: str,  # "week" | "month"
        week_start: str = "",
        week_end: str = "",
        month_label: str = "",
    ):
        super().__init__()
        self._cfg = cfg
        self._reports = reports
        self._mode = mode
        self._week_start = week_start
        self._week_end = week_end
        self._month_label = month_label

    def run(self) -> None:
        try:
            if not self._reports:
                self.failed.emit("该时间范围内没有日报，无法生成总结。")
                return
            self.status.emit(
                f"正在调用 {self._cfg.llm.model} 汇总 {len(self._reports)} 篇日报…"
            )
            from daily_report.llm import LLMClient

            client = LLMClient(self._cfg.llm)
            content = _reports_block(self._reports)
            if self._mode == "week":
                user = _fill_tpl(
                    self._cfg.template("weekly_summary"),
                    date_range=f"{self._week_start} ~ {self._week_end}",
                    date=f"{self._week_start} ~ {self._week_end}",
                    content=content,
                )
            else:
                user = _fill_tpl(
                    self._cfg.template("monthly_summary"),
                    date_range=self._month_label,
                    date=self._month_label,
                    content=content,
                )
            text = client.chat(SYSTEM_SUMMARY, user)
            self.finished.emit(text)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class SummaryController(QObject):
    """把 SummaryWorker 挂到线程上，避免 UI 卡死。"""

    finished = Signal(str)
    failed = Signal(str)
    status = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: SummaryWorker | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start(
        self,
        cfg: Config,
        reports: list[DailyReport],
        mode: str,
        week_start: str = "",
        week_end: str = "",
        month_label: str = "",
    ) -> None:
        if self.running:
            self.failed.emit("已有总结任务在进行中，请稍候。")
            return

        self._thread = QThread(self)
        self._worker = SummaryWorker(
            cfg, reports, mode, week_start, week_end, month_label
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.status.connect(self.status.emit)
        self._thread.start()

    def _cleanup(self) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait(3000)
            self._thread = None
        self._worker = None

    def _on_finished(self, text: str) -> None:
        self.finished.emit(text)
        self._cleanup()

    def _on_failed(self, err: str) -> None:
        self.failed.emit(err)
        self._cleanup()


class ComposeWorker(QObject):
    """根据当天流水生成日报草稿。"""

    finished = Signal(object)  # DailyReport
    raw_text = Signal(str)
    failed = Signal(str)
    status = Signal(str)

    def __init__(
        self,
        cfg: Config,
        report_date,
        logs: list[WorkLogEntry],
        existing_goal: str = "",
        existing_next: str = "",
        hint: str = "",
    ):
        super().__init__()
        self._cfg = cfg
        self._report_date = report_date
        self._logs = logs
        self._existing_goal = existing_goal
        self._existing_next = existing_next
        self._hint = hint

    def run(self) -> None:
        try:
            if not self._logs and not self._existing_goal.strip():
                self.failed.emit(
                    "当天还没有工作流水，无法 AI 成稿。请先在上方「记一笔」记录几条工作。"
                )
                return
            self.status.emit(f"正在调用 {self._cfg.llm.model} 生成日报草稿…")
            from daily_report.llm import LLMClient

            client = LLMClient(self._cfg.llm)
            extra_parts = []
            if self._existing_goal.strip():
                extra_parts.append(f"已有任务目标（可参考）：\n{self._existing_goal.strip()}")
            if self._existing_next.strip():
                extra_parts.append(f"已有下一步计划（可参考）：\n{self._existing_next.strip()}")
            if self._hint.strip():
                extra_parts.append(f"用户补充说明：\n{self._hint.strip()}")
            extra = ("\n\n" + "\n\n".join(extra_parts)) if extra_parts else ""
            user = _fill_tpl(
                self._cfg.template("daily_compose"),
                date=self._report_date.isoformat(),
                content=_logs_block(self._logs),
                extra=extra,
            )
            text = client.chat(SYSTEM_DAILY_COMPOSE, user)
            self.raw_text.emit(text)
            report = parse_daily_report(text, self._report_date)
            self.finished.emit(report)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class ComposeController(QObject):
    finished = Signal(object)
    raw_text = Signal(str)
    failed = Signal(str)
    status = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: ComposeWorker | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start(
        self,
        cfg: Config,
        report_date,
        logs: list[WorkLogEntry],
        existing_goal: str = "",
        existing_next: str = "",
        hint: str = "",
    ) -> None:
        if self.running:
            self.failed.emit("已有 AI 生成任务在进行中，请稍候。")
            return
        self._thread = QThread(self)
        self._worker = ComposeWorker(
            cfg, report_date, logs, existing_goal, existing_next, hint
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.raw_text.connect(self.raw_text.emit)
        self._worker.failed.connect(self._on_failed)
        self._worker.status.connect(self.status.emit)
        self._thread.start()

    def _cleanup(self) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait(3000)
            self._thread = None
        self._worker = None

    def _on_finished(self, report) -> None:
        self.finished.emit(report)
        self._cleanup()

    def _on_failed(self, err: str) -> None:
        self.failed.emit(err)
        self._cleanup()


class BreakdownWorker(QObject):
    """AI 将大任务拆成子任务标题列表。"""

    finished = Signal(list)  # list[str]
    failed = Signal(str)
    status = Signal(str)

    def __init__(
        self,
        cfg: Config,
        title: str,
        description: str = "",
        deadline: str = "",
    ):
        super().__init__()
        self._cfg = cfg
        self._title = title
        self._description = description
        self._deadline = deadline

    def run(self) -> None:
        try:
            if not self._title.strip():
                self.failed.emit("请先填写任务标题。")
                return
            self.status.emit(f"正在调用 {self._cfg.llm.model} 拆分任务…")
            from daily_report.llm import LLMClient

            client = LLMClient(self._cfg.llm)
            extra = f"\n预计完成日期: {self._deadline}" if self._deadline else ""
            user = _fill_tpl(
                self._cfg.template("task_breakdown"),
                title=self._title,
                content=self._description or "（无补充描述）",
                extra=extra,
            )
            text = client.chat(SYSTEM_TASK_BREAKDOWN, user)
            items = parse_subtasks(text)
            if not items:
                self.failed.emit("模型未返回有效子任务，请重试或补充描述。")
                return
            self.finished.emit(items)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class BreakdownController(QObject):
    finished = Signal(list)
    failed = Signal(str)
    status = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: BreakdownWorker | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start(self, cfg: Config, title: str, description: str = "", deadline: str = "") -> None:
        if self.running:
            self.failed.emit("已有拆分任务在进行中。")
            return
        self._thread = QThread(self)
        self._worker = BreakdownWorker(cfg, title, description, deadline)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.status.connect(self.status.emit)
        self._thread.start()

    def _cleanup(self) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait(3000)
            self._thread = None
        self._worker = None

    def _on_finished(self, items: list) -> None:
        self.finished.emit(items)
        self._cleanup()

    def _on_failed(self, err: str) -> None:
        self.failed.emit(err)
        self._cleanup()
