"""关键词检索（多词 AND）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from daily_report.models import DailyReport


@dataclass
class SearchHit:
    report: DailyReport
    matched_lines: list[str]
    score: int


def search_reports(
    reports: list[DailyReport],
    keywords: list[str],
    case_sensitive: bool = False,
) -> list[SearchHit]:
    if not keywords:
        return []
    keys = keywords if case_sensitive else [k.lower() for k in keywords]
    hits: list[SearchHit] = []

    for report in reports:
        lines = _collect_lines(report)
        # 全文是否包含所有关键词（AND）
        haystack = "\n".join(line for _, line in lines)
        hay_all = haystack if case_sensitive else haystack.lower()
        if not all(k in hay_all for k in keys):
            continue

        matched: list[str] = []
        score = 0
        for section, line in lines:
            hay = line if case_sensitive else line.lower()
            if any(k in hay for k in keys):
                matched.append(f"[{section}] {line}")
                score += 1
        if matched:
            hits.append(SearchHit(report=report, matched_lines=matched, score=score))

    hits.sort(key=lambda h: (-h.score, -h.report.report_date.toordinal()))
    return hits


def _collect_lines(report: DailyReport) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for line in report.goal.splitlines():
        if line.strip():
            out.append(("任务目标", line.strip()))
    for item in report.work_items:
        if item.strip():
            out.append(("具体工作", item.strip()))
    for line in report.next_steps.splitlines():
        if line.strip():
            out.append(("下一步计划", line.strip()))
    return out


def filter_by_date(
    reports: list[DailyReport],
    start: date | None = None,
    end: date | None = None,
) -> list[DailyReport]:
    result = []
    for r in reports:
        if start and r.report_date < start:
            continue
        if end and r.report_date > end:
            continue
        result.append(r)
    return result
