"""日报日历：一眼看出哪天写了/有流水。"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWidgets import QCalendarWidget

from daily_report.storage import ReportStore


class CalendarView(QWidget):
    open_date = Signal(date)

    def __init__(self, store: ReportStore, parent=None):
        super().__init__(parent)
        self._store = store

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        head = QHBoxLayout()
        title = QLabel("日报日历")
        title.setObjectName("SectionTitle")
        tip = QLabel("■ 正式日报　□ 仅有流水　空白=无记录")
        tip.setStyleSheet("color:#7A8B9A;")
        head.addWidget(title)
        head.addWidget(tip)
        head.addStretch(1)
        btn = QPushButton("打开选中日")
        btn.setObjectName("PrimaryBig")
        btn.clicked.connect(self._emit_selected)
        head.addWidget(btn)
        lay.addLayout(head)

        self.cal = QCalendarWidget()
        self.cal.setGridVisible(True)
        self.cal.selectionChanged.connect(self._on_select)
        lay.addWidget(self.cal, 1)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMaximumHeight(140)
        lay.addWidget(self.detail)

        self.refresh()

    def refresh(self) -> None:
        # 清除旧格式：对有记录的日期先重置
        from PySide6.QtCore import QDate

        clear = QTextCharFormat()
        clear.setBackground(QColor("transparent"))
        clear.setForeground(QColor("#2C3E50"))
        for d in list(self._store.list_dates()) + list(self._store.list_log_dates()):
            try:
                self.cal.setDateTextFormat(QDate(d.year, d.month, d.day), clear)
            except Exception:
                pass

        formats: dict = {}
        today = date.today()

        def mark(d: date, bg: str, fg: str) -> None:
            f = QTextCharFormat()
            f.setBackground(QColor(bg))
            f.setForeground(QColor(fg))
            formats[d] = f

        for d in self._store.list_dates():
            mark(d, "#B3E5FC", "#01579B")
        for d in self._store.list_log_dates():
            if d not in formats:
                mark(d, "#FFF9C4", "#F57F17")
        # 今天描边
        f_today = formats.get(today)
        if f_today is None:
            f_today = QTextCharFormat()
            formats[today] = f_today
        f_today.setFontWeight(700)

        # PySide6: setDateTextFormat(QDate, QTextCharFormat)
        from PySide6.QtCore import QDate

        for d, fmt in formats.items():
            self.cal.setDateTextFormat(QDate(d.year, d.month, d.day), fmt)
        self._on_select()

    def _selected_date(self) -> date:
        qd = self.cal.selectedDate()
        return date(qd.year(), qd.month(), qd.day())

    def _on_select(self) -> None:
        d = self._selected_date()
        r = self._store.load(d)
        logs = self._store.load_logs(d)
        parts = [f"{d.isoformat()}"]
        if r and (r.goal or r.work_items):
            parts.append(f"正式日报：{(r.goal.splitlines()[0] if r.goal else '')[:40]}")
            parts.append(f"具体工作 {len(r.work_items)} 条")
        else:
            parts.append("无正式日报")
        if logs:
            parts.append(f"流水 {len(logs)} 条")
            parts.append(" / ".join(e.text[:16] for e in logs[:3]))
        else:
            parts.append("无流水")
        self.detail.setPlainText("\n".join(parts))

    def _emit_selected(self) -> None:
        self.open_date.emit(self._selected_date())

    def set_store(self, store: ReportStore) -> None:
        self._store = store
        self.refresh()
