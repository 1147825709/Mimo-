"""本地 Markdown 日报与工作流水存储。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from daily_report.models import DailyReport, WorkLogEntry


class ReportStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.reports_dir = data_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.summaries_dir = data_dir / "summaries"
        self.summaries_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir = data_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    # ---------- 日报 ----------

    def path_for(self, d: date) -> Path:
        return self.reports_dir / f"{d.isoformat()}.md"

    def exists(self, d: date) -> bool:
        return self.path_for(d).is_file()

    def save(self, report: DailyReport) -> Path:
        path = self.path_for(report.report_date)
        path.write_text(report.to_markdown(), encoding="utf-8")
        return path

    def load(self, d: date) -> DailyReport | None:
        path = self.path_for(d)
        if not path.is_file():
            return None
        text = path.read_text(encoding="utf-8")
        return DailyReport.from_markdown(text, d)

    def load_or_create(self, d: date) -> DailyReport:
        return self.load(d) or DailyReport(report_date=d)

    def list_dates(self, start: date | None = None, end: date | None = None) -> list[date]:
        dates: list[date] = []
        for p in sorted(self.reports_dir.glob("*.md")):
            try:
                d = date.fromisoformat(p.stem)
            except ValueError:
                continue
            if start and d < start:
                continue
            if end and d > end:
                continue
            dates.append(d)
        return dates

    def load_range(self, start: date, end: date) -> list[DailyReport]:
        reports = []
        for d in self.list_dates(start, end):
            r = self.load(d)
            if r:
                reports.append(r)
        return reports

    def delete(self, d: date) -> bool:
        path = self.path_for(d)
        if path.is_file():
            path.unlink()
            return True
        return False

    # ---------- 工作流水 ----------

    def log_path_for(self, d: date) -> Path:
        return self.logs_dir / f"{d.isoformat()}.md"

    def append_log(
        self, d: date, text: str, timestamp: datetime | None = None
    ) -> WorkLogEntry:
        entry = WorkLogEntry(
            timestamp=timestamp or datetime.now(),
            text=text.strip(),
        )
        path = self.log_path_for(d)
        if not path.is_file():
            path.write_text(f"# 工作流水 {d.isoformat()}\n\n", encoding="utf-8")
        with path.open("a", encoding="utf-8") as f:
            f.write(entry.to_line() + "\n")
        return entry

    def load_logs(self, d: date) -> list[WorkLogEntry]:
        path = self.log_path_for(d)
        if not path.is_file():
            return []
        entries: list[WorkLogEntry] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            e = WorkLogEntry.parse_line(line, d)
            if e:
                entries.append(e)
        entries.sort(key=lambda x: x.timestamp)
        return entries

    def save_logs(self, d: date, entries: list[WorkLogEntry]) -> Path:
        path = self.log_path_for(d)
        lines = [f"# 工作流水 {d.isoformat()}", ""]
        entries = sorted(entries, key=lambda x: x.timestamp)
        for e in entries:
            lines.append(e.to_line())
        lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def clear_logs(self, d: date) -> bool:
        path = self.log_path_for(d)
        if path.is_file():
            path.unlink()
            return True
        return False

    def list_log_dates(self) -> list[date]:
        dates: list[date] = []
        for p in sorted(self.logs_dir.glob("*.md")):
            try:
                dates.append(date.fromisoformat(p.stem))
            except ValueError:
                continue
        return dates


def week_range(anchor: date) -> tuple[date, date]:
    """周一到周日。"""
    start = anchor - timedelta(days=anchor.weekday())
    end = start + timedelta(days=6)
    return start, end


def month_range(anchor: date) -> tuple[date, date]:
    start = anchor.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = start.replace(month=start.month + 1, day=1) - timedelta(days=1)
    return start, end
