"""主窗口：随手记流水、日报编辑、AI 成稿、周报/月报、搜索。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, QDate, QTimer, Signal
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from daily_report.config import Config
from daily_report.gui.settings_dialog import SettingsDialog
from daily_report.gui.workers import ComposeController, SummaryController
from daily_report.models import DailyReport, WorkLogEntry
from daily_report.search import search_reports
from daily_report.storage import ReportStore, month_range, week_range


class MainWindow(QMainWindow):
    """日报记录主功能窗口。"""

    back_to_hub = Signal()
    config_changed = Signal(object)  # Config

    def __init__(self, cfg: Config, store: ReportStore | None = None):
        super().__init__()
        self.setWindowTitle("日报记录")
        self.resize(1180, 780)

        self._cfg = cfg
        self._store = store or ReportStore(cfg.data_dir)
        self._current_date = date.today()
        self._logs_cache: list[WorkLogEntry] = []

        self._summary_ctrl = SummaryController(self)
        self._summary_ctrl.finished.connect(self._on_summary_ok)
        self._summary_ctrl.failed.connect(self._on_summary_fail)
        self._summary_ctrl.status.connect(self._set_status)

        self._compose_ctrl = ComposeController(self)
        self._compose_ctrl.finished.connect(self._on_compose_ok)
        self._compose_ctrl.failed.connect(self._on_compose_fail)
        self._compose_ctrl.status.connect(self._set_status)

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(20000)
        self._autosave_timer.timeout.connect(self._autosave_draft)
        self._autosave_timer.start()
        self._dirty = False

        self._build_ui()
        self._build_menu()
        self.apply_mode()
        self._reload_list()
        self._load_report(self._current_date)
        self._set_status(f"数据目录: {self._store.data_dir}")
        self.goal_edit.textChanged.connect(self._mark_dirty)
        self.work_edit.textChanged.connect(self._mark_dirty)
        self.next_edit.textChanged.connect(self._mark_dirty)

    def _mark_dirty(self) -> None:
        self._dirty = True

    def _autosave_draft(self) -> None:
        if not self._dirty:
            return
        text_goal = self.goal_edit.toPlainText().strip()
        text_work = self.work_edit.toPlainText().strip()
        text_next = self.next_edit.toPlainText().strip()
        if not (text_goal or text_work or text_next):
            return
        draft_dir = self._store.data_dir / "drafts"
        draft_dir.mkdir(parents=True, exist_ok=True)
        path = draft_dir / f"{self._current_date.isoformat()}.md"
        try:
            path.write_text(self._collect_report().to_markdown(), encoding="utf-8")
            self._dirty = False
            self._set_status(f"自动草稿已存 {path.name}")
        except Exception:
            pass

    def _goto_date(self, d: date) -> None:
        self._load_report(d)
        self.tabs.setCurrentIndex(0)

    def goto_date_external(self, d: date) -> None:
        self.show()
        self.raise_()
        self._goto_date(d)

    # ---------- UI ----------

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("DailyRoot")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        top = QHBoxLayout()
        btn_back = QPushButton("← 返回工作台")
        btn_back.setObjectName("Ghost")
        btn_back.clicked.connect(self.back_to_hub.emit)
        title = QLabel("日报记录")
        title.setObjectName("SectionTitle")
        top.addWidget(btn_back)
        top.addWidget(title)
        top.addStretch(1)
        outer.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(splitter, 1)
        self.setCentralWidget(root)

        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(8, 8, 4, 8)

        left_l.addWidget(QLabel("选择日期"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self._on_date_changed)
        left_l.addWidget(self.date_edit)

        btn_row = QHBoxLayout()
        self.btn_today = QPushButton("回到今天")
        self.btn_today.clicked.connect(self._load_current_from_date)
        self.btn_delete = QPushButton("删除日报")
        self.btn_delete.clicked.connect(self._delete_current)
        btn_row.addWidget(self.btn_today)
        btn_row.addWidget(self.btn_delete)
        left_l.addLayout(btn_row)

        left_l.addWidget(QLabel("日报列表（含仅有流水的日期）"))
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_list_select)
        left_l.addWidget(self.list_widget, 1)

        splitter.addWidget(left)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_editor_tab(), "今日工作")
        self.tabs.addTab(self._build_summary_tab(), "周报 / 月报")
        self.tabs.addTab(self._build_search_tab(), "关键词搜索")
        from daily_report.gui.calendar_view import CalendarView

        self.calendar_view = CalendarView(self._store)
        self.calendar_view.open_date.connect(self._goto_date)
        self.tabs.addTab(self.calendar_view, "日历")
        splitter.addWidget(self.tabs)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 900])

        self.setStatusBar(QStatusBar())

    def _build_editor_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        self.editor_title = QLabel("日报")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        self.editor_title.setFont(title_font)
        lay.addWidget(self.editor_title)

        # ---- 随手记流水 ----
        log_box = QVBoxLayout()
        log_head = QHBoxLayout()
        log_head.addWidget(QLabel("随手记流水（完成一项工作就记一条）"))
        self.log_count_label = QLabel("0 条")
        log_head.addWidget(self.log_count_label)
        log_head.addStretch(1)
        btn_clear_logs = QPushButton("清空流水")
        btn_clear_logs.clicked.connect(self._clear_logs)
        log_head.addWidget(btn_clear_logs)
        log_box.addLayout(log_head)

        log_input_row = QHBoxLayout()
        self.log_input = QLineEdit()
        self.log_input.setPlaceholderText("例如：修复了搜索 AND 语义并补了单测")
        self.log_input.returnPressed.connect(self._add_log)
        self.btn_add_log = QPushButton("记一笔")
        self.btn_add_log.setStyleSheet("font-weight: bold; padding: 6px 14px;")
        self.btn_add_log.clicked.connect(self._add_log)
        log_input_row.addWidget(self.log_input, 1)
        log_input_row.addWidget(self.btn_add_log)
        log_box.addLayout(log_input_row)

        self.log_list = QListWidget()
        self.log_list.setMaximumHeight(140)
        log_box.addWidget(self.log_list)

        log_del_row = QHBoxLayout()
        btn_del_log = QPushButton("删除选中流水")
        btn_del_log.clicked.connect(self._delete_selected_log)
        btn_use_checked = QPushButton("仅用勾选流水成稿")
        btn_use_checked.setObjectName("Ghost")
        btn_use_checked.clicked.connect(lambda: self._run_compose(only_checked=True))
        log_del_row.addWidget(btn_del_log)
        log_del_row.addWidget(btn_use_checked)
        log_del_row.addStretch(1)
        log_box.addLayout(log_del_row)
        lay.addLayout(log_box)

        # ---- 生成方式 ----
        gen_row = QHBoxLayout()
        gen_row.addWidget(QLabel("日报成稿方式"))
        self.compose_hint = QLineEdit()
        self.compose_hint.setPlaceholderText("可选：给 AI 的补充说明，例如「侧重支付模块」")
        self.btn_ai_compose = QPushButton("AI 一键生成日报")
        self.btn_ai_compose.setStyleSheet(
            "font-weight: bold; padding: 6px 14px; background: #2b6cb0; color: white;"
        )
        self.btn_ai_compose.clicked.connect(self._run_compose)
        gen_row.addWidget(self.compose_hint, 1)
        gen_row.addWidget(self.btn_ai_compose)
        lay.addLayout(gen_row)
        self.ai_tip = QLabel("提示：可先「记一笔」，下班前点 AI 生成草稿，再手动改后保存；也可完全手写。")
        self.ai_tip.setStyleSheet("color: #666;")
        lay.addWidget(self.ai_tip)

        # ---- 日报三段 ----
        form_l = QVBoxLayout()
        form_l.addWidget(QLabel("任务目标"))
        self.goal_edit = QPlainTextEdit()
        self.goal_edit.setPlaceholderText("今天要完成什么？（手写，或由 AI 生成）")
        self.goal_edit.setMaximumHeight(80)
        form_l.addWidget(self.goal_edit)

        form_l.addWidget(QLabel("具体工作（每行一条，保存后自动编号 1. 2. 3.…）"))
        self.work_edit = QPlainTextEdit()
        self.work_edit.setPlaceholderText("实现关键词搜索\n接入 OpenAI 协议\n编写 README")
        form_l.addWidget(self.work_edit, 1)

        form_l.addWidget(QLabel("下一步计划"))
        self.next_edit = QPlainTextEdit()
        self.next_edit.setPlaceholderText("明天/后续要做什么？")
        self.next_edit.setMaximumHeight(80)
        form_l.addWidget(self.next_edit)
        lay.addLayout(form_l, 1)

        save_row = QHBoxLayout()
        self.btn_save = QPushButton("保存日报")
        self.btn_save.setStyleSheet("font-weight: bold; padding: 8px;")
        self.btn_save.clicked.connect(self._save_report)
        self.btn_save_as_draft = QPushButton("仅保存草稿（不写正式日报）")
        self.btn_save_as_draft.clicked.connect(self._save_draft)
        save_row.addWidget(self.btn_save, 2)
        save_row.addWidget(self.btn_save_as_draft, 1)
        lay.addLayout(save_row)

        return w

    def _build_summary_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)

        mode_row = QHBoxLayout()
        self.summary_mode = QComboBox()
        self.summary_mode.addItems(["周报（本周）", "月报（本月）"])
        self.summary_mode.currentIndexChanged.connect(self._on_summary_mode)
        mode_row.addWidget(QLabel("类型"))
        mode_row.addWidget(self.summary_mode)
        mode_row.addSpacing(16)

        self.week_anchor = QDateEdit()
        self.week_anchor.setCalendarPopup(True)
        self.week_anchor.setDisplayFormat("yyyy-MM-dd")
        self.week_anchor.setDate(QDate.currentDate())
        self.week_anchor.dateChanged.connect(lambda *_: self._update_summary_range())
        self.lbl_week = QLabel("周锚点")
        mode_row.addWidget(self.lbl_week)
        mode_row.addWidget(self.week_anchor)

        self.month_edit = QDateEdit()
        self.month_edit.setDisplayFormat("yyyy-MM")
        self.month_edit.setDate(QDate.currentDate())
        self.month_edit.setVisible(False)
        self.month_edit.dateChanged.connect(lambda *_: self._update_summary_range())
        self.lbl_month = QLabel("月份")
        self.lbl_month.setVisible(False)
        mode_row.addWidget(self.lbl_month)
        mode_row.addWidget(self.month_edit)

        self.btn_run_summary = QPushButton("生成总结")
        self.btn_run_summary.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self.btn_run_summary.clicked.connect(self._run_summary)
        mode_row.addWidget(self.btn_run_summary)
        mode_row.addStretch(1)
        lay.addLayout(mode_row)

        self.summary_range_label = QLabel("")
        lay.addWidget(self.summary_range_label)

        # 左：总结编辑；右：本周/本月日报原文
        body = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(6)
        ll.addWidget(QLabel("总结内容"))
        self.summary_view = QTextEdit()
        self.summary_view.setPlaceholderText(
            "配置好模型后点击「生成总结」。\n结果会保存到 data/summaries/。"
        )
        ll.addWidget(self.summary_view, 1)
        body.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)
        src_head = QHBoxLayout()
        self.src_title = QLabel("本周日报原文")
        src_head.addWidget(self.src_title)
        src_head.addStretch(1)
        self.btn_copy_src = QPushButton("复制全部")
        self.btn_copy_src.setObjectName("Ghost")
        self.btn_copy_src.clicked.connect(self._copy_source_reports)
        src_head.addWidget(self.btn_copy_src)
        rl.addLayout(src_head)
        self.source_view = QTextEdit()
        self.source_view.setReadOnly(True)
        self.source_view.setPlaceholderText("切换日期后，这里会显示该周/该月的全部日报。")
        rl.addWidget(self.source_view, 1)
        body.addWidget(right)
        body.setSizes([420, 420])
        lay.addWidget(body, 1)

        manual_row = QHBoxLayout()
        self.btn_save_manual_summary = QPushButton("保存手写总结")
        self.btn_save_manual_summary.setObjectName("PrimaryBig")
        self.btn_save_manual_summary.clicked.connect(self._save_manual_summary)
        self.btn_save_manual_summary.setVisible(False)
        manual_row.addWidget(self.btn_save_manual_summary)
        manual_row.addStretch(1)
        lay.addLayout(manual_row)

        save_row = QHBoxLayout()
        self.btn_save_summary = QPushButton("另存为 Markdown…")
        self.btn_save_summary.clicked.connect(self._save_summary_as)
        self.btn_open_summaries = QPushButton("打开 summaries 目录")
        self.btn_open_summaries.clicked.connect(self._open_summaries_dir)
        save_row.addWidget(self.btn_save_summary)
        save_row.addWidget(self.btn_open_summaries)
        save_row.addStretch(1)
        lay.addLayout(save_row)

        return w

    def _build_search_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)

        row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入关键词，空格分隔表示 AND")
        self.search_input.returnPressed.connect(self._run_search)
        self.case_check = QCheckBox("区分大小写")
        self.btn_search = QPushButton("搜索")
        self.btn_search.clicked.connect(self._run_search)
        row.addWidget(self.search_input, 1)
        row.addWidget(self.case_check)
        row.addWidget(self.btn_search)
        lay.addLayout(row)

        date_row = QHBoxLayout()
        self.search_from = QDateEdit()
        self.search_from.setCalendarPopup(True)
        self.search_from.setDisplayFormat("yyyy-MM-dd")
        self.search_from.setDate(QDate.currentDate().addMonths(-3))
        self.search_to = QDateEdit()
        self.search_to.setCalendarPopup(True)
        self.search_to.setDisplayFormat("yyyy-MM-dd")
        self.search_to.setDate(QDate.currentDate())
        date_row.addWidget(QLabel("起"))
        date_row.addWidget(self.search_from)
        date_row.addWidget(QLabel("止"))
        date_row.addWidget(self.search_to)
        date_row.addStretch(1)
        lay.addLayout(date_row)

        self.search_results = QTextEdit()
        self.search_results.setReadOnly(True)
        self.search_results.setPlaceholderText("搜索结果将显示在这里。")
        lay.addWidget(self.search_results, 1)

        return w

    def _build_menu(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")
        act_back = QAction("返回工作台", self)
        act_back.triggered.connect(self.back_to_hub.emit)
        file_menu.addAction(act_back)
        act_settings = QAction("设置…", self)
        act_settings.triggered.connect(self._open_settings)
        file_menu.addAction(act_settings)
        act_reload = QAction("重新加载数据", self)
        act_reload.triggered.connect(self._reload_all)
        file_menu.addAction(act_reload)

        help_menu = menubar.addMenu("帮助")
        act_about = QAction("关于", self)
        act_about.triggered.connect(self._about)
        help_menu.addAction(act_about)

    # ---------- 数据加载 ----------

    def _reload_all(self) -> None:
        self._reload_list()
        self._load_report(self._current_date)
        self._update_summary_range()
        if hasattr(self, "calendar_view"):
            self.calendar_view.refresh()
        self._set_status(f"已重新加载 — {self._store.data_dir}")

    def _all_active_dates(self) -> list[date]:
        dates = set(self._store.list_dates())
        dates.update(self._store.list_log_dates())
        return sorted(dates)

    def _reload_list(self) -> None:
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for d in self._all_active_dates():
            r = self._store.load(d)
            goal = r.goal.splitlines()[0][:32] if r and r.goal else ""
            n_logs = len(self._store.load_logs(d))
            tags = []
            if r and (r.goal or r.work_items):
                tags.append("已成稿")
            if n_logs:
                tags.append(f"流水{n_logs}")
            tag = " · ".join(tags)
            item = QListWidgetItem(f"{d.isoformat()}  {tag}  {goal}")
            item.setData(Qt.ItemDataRole.UserRole, d.isoformat())
            self.list_widget.addItem(item)
            if d == self._current_date:
                self.list_widget.setCurrentItem(item)
        self.list_widget.blockSignals(False)

    def _load_report(self, d: date) -> None:
        self._current_date = d
        self.date_edit.blockSignals(True)
        self.date_edit.setDate(QDate(d.year, d.month, d.day))
        self.date_edit.blockSignals(False)

        report = self._store.load_or_create(d)
        self.editor_title.setText(f"日报 {report.date_str}")
        self.goal_edit.setPlainText(report.goal)
        self.work_edit.setPlainText("\n".join(report.work_items))
        self.next_edit.setPlainText(report.next_steps)
        self._load_logs_ui(d)

        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == d.isoformat():
                self.list_widget.blockSignals(True)
                self.list_widget.setCurrentRow(i)
                self.list_widget.blockSignals(False)
                break

    def _load_logs_ui(self, d: date) -> None:
        self._logs_cache = self._store.load_logs(d)
        self.log_list.blockSignals(True)
        self.log_list.clear()
        for e in self._logs_cache:
            item = QListWidgetItem(f"{e.time_str}  {e.text}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.log_list.addItem(item)
        self.log_list.blockSignals(False)
        self.log_count_label.setText(f"{len(self._logs_cache)} 条")

    def _checked_log_texts(self) -> list[str]:
        out = []
        for i in range(self.log_list.count()):
            it = self.log_list.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                t = it.text()
                # 去掉时间前缀 "HH:MM  "
                if len(t) > 6 and t[2] == ":":
                    t = t[6:].strip()
                out.append(t)
        return out

    def refresh_logs_if_needed(self, d: date | None = None) -> None:
        """悬浮窗等外部写入流水后调用，立刻刷新当前打开的日期列表。"""
        target = d or date.today()
        if target == self._current_date:
            self._load_logs_ui(self._current_date)
        # 无论是否当天，都刷新左侧列表上的「流水N」标签
        self._reload_list()

    # ---------- 随手记 ----------

    def _add_log(self) -> None:
        text = self.log_input.text().strip()
        if not text:
            return
        # 若不是今天，仍允许记到选中日期
        d = self._current_date
        self._store.append_log(d, text)
        self.log_input.clear()
        self._load_logs_ui(d)
        self._reload_list()
        self._set_status(f"已记一笔到 {d.isoformat()}")

    def _delete_selected_log(self) -> None:
        row = self.log_list.currentRow()
        if row < 0 or row >= len(self._logs_cache):
            QMessageBox.information(self, "提示", "请先在流水列表中选中一条。")
            return
        del self._logs_cache[row]
        self._store.save_logs(self._current_date, self._logs_cache)
        self._load_logs_ui(self._current_date)
        self._reload_list()

    def _clear_logs(self) -> None:
        if not self._logs_cache:
            return
        ret = QMessageBox.question(
            self, "确认清空", f"清空 {self._current_date.isoformat()} 的全部流水？"
        )
        if ret == QMessageBox.StandardButton.Yes:
            self._store.clear_logs(self._current_date)
            self._load_logs_ui(self._current_date)
            self._reload_list()

    # ---------- 保存 / AI 成稿 ----------

    def _collect_report(self) -> DailyReport:
        return DailyReport(
            report_date=self._current_date,
            goal=self.goal_edit.toPlainText().strip(),
            work_items=[
                line.strip()
                for line in self.work_edit.toPlainText().splitlines()
                if line.strip()
            ],
            next_steps=self.next_edit.toPlainText().strip(),
        )

    def _save_report(self) -> None:
        report = self._collect_report()
        path = self._store.save(report)
        self._reload_list()
        self._set_status(f"已保存正式日报 {path.name}")
        self.btn_save.setText("已保存 ✓")
        QTimer.singleShot(1200, lambda: self.btn_save.setText("保存日报"))

    def _save_draft(self) -> None:
        report = self._collect_report()
        draft_dir = self._store.data_dir / "drafts"
        draft_dir.mkdir(parents=True, exist_ok=True)
        path = draft_dir / f"{report.date_str}.md"
        path.write_text(report.to_markdown(), encoding="utf-8")
        self._set_status(f"已保存草稿 {path}")

    def _ensure_llm_ready(self) -> bool:
        if not self._cfg.is_ai:
            QMessageBox.information(
                self,
                "当前为非 AI 版",
                "非 AI 版没有自动总结。\n请手写周报/月报后点「保存手写总结」。",
            )
            return False
        if not self._cfg.llm_ready():
            QMessageBox.warning(
                self,
                "未配置模型",
                "请先在「文件 → 设置」中配置 OpenAI 协议的 Base URL / API Key / 模型。",
            )
            return False
        return True

    def apply_mode(self) -> None:
        """按 AI / 非 AI 模式切换界面。"""
        is_ai = self._cfg.is_ai
        self.btn_ai_compose.setVisible(is_ai)
        self.compose_hint.setVisible(is_ai)
        self.ai_tip.setVisible(is_ai)
        self.btn_run_summary.setVisible(is_ai)
        self.btn_save_manual_summary.setVisible(not is_ai)
        self.summary_view.setReadOnly(is_ai)
        if is_ai:
            self.summary_view.setPlaceholderText(
                "配置好模型后点击「生成总结」。\n结果会保存到 data/summaries/。"
            )
        else:
            self.summary_view.setPlaceholderText(
                "非 AI 版：请在此手写周报/月报，然后点「保存手写总结」。\n"
                "可先复制左侧「将汇总」范围内的日报作为素材。"
            )

    def _save_manual_summary(self) -> None:
        text = self.summary_view.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "提示", "请先填写总结内容。")
            return
        if self.summary_mode.currentIndex() == 0:
            qd = self.week_anchor.date()
            start, _ = week_range(date(qd.year(), qd.month(), qd.day()))
            out = self._store.summaries_dir / f"week_{start.isoformat()}.md"
        else:
            qd = self.month_edit.date()
            start, _ = month_range(date(qd.year(), qd.month(), 1))
            out = self._store.summaries_dir / f"month_{start.strftime('%Y-%m')}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        self._set_status(f"已保存手写总结: {out}")

    def _run_compose(self, only_checked: bool = False) -> None:
        if not self._ensure_llm_ready():
            return
        from datetime import datetime as _dt

        if only_checked:
            texts = self._checked_log_texts()
            logs = [
                WorkLogEntry(timestamp=_dt.now(), text=t) for t in texts
            ]
            if not logs:
                QMessageBox.information(
                    self,
                    "未勾选",
                    "请先在流水列表勾选要纳入日报的条目。",
                )
                return
        else:
            logs = self._store.load_logs(self._current_date)
        if not logs and not self.goal_edit.toPlainText().strip():
            QMessageBox.information(
                self,
                "没有流水",
                "当天还没有工作流水。请先在上方「记一笔」记录完成的工作，再点 AI 生成。",
            )
            return
        self.btn_ai_compose.setEnabled(False)
        self.btn_ai_compose.setText("生成中…")
        self._compose_ctrl.start(
            self._cfg,
            self._current_date,
            logs,
            existing_goal=self.goal_edit.toPlainText().strip(),
            existing_next=self.next_edit.toPlainText().strip(),
            hint=self.compose_hint.text().strip(),
        )

    def _on_compose_ok(self, report: DailyReport) -> None:
        self.btn_ai_compose.setEnabled(True)
        self.btn_ai_compose.setText("AI 一键生成日报")
        self.goal_edit.setPlainText(report.goal)
        self.work_edit.setPlainText("\n".join(report.work_items))
        self.next_edit.setPlainText(report.next_steps)
        self._set_status("AI 草稿已填入编辑区，确认后点「保存日报」")

    def _on_compose_fail(self, err: str) -> None:
        self.btn_ai_compose.setEnabled(True)
        self.btn_ai_compose.setText("AI 一键生成日报")
        QMessageBox.critical(self, "AI 生成失败", err)

    def _delete_current(self) -> None:
        d = self._current_date
        if not self._store.exists(d):
            QMessageBox.information(self, "提示", f"{d.isoformat()} 没有正式日报。")
            return
        ret = QMessageBox.question(
            self, "确认删除", f"确定删除 {d.isoformat()} 的正式日报吗？流水会保留。"
        )
        if ret == QMessageBox.StandardButton.Yes:
            self._store.delete(d)
            self._reload_list()
            self._load_report(d)
            self._set_status(f"已删除日报 {d.isoformat()}")

    # ---------- 事件 ----------

    def _on_date_changed(self, qd: QDate) -> None:
        self._load_report(date(qd.year(), qd.month(), qd.day()))

    def _load_current_from_date(self) -> None:
        self._load_report(date.today())
        self.tabs.setCurrentIndex(0)
        self.log_input.setFocus()

    def _on_list_select(self, current: QListWidgetItem | None, _prev=None) -> None:
        if not current:
            return
        iso = current.data(Qt.ItemDataRole.UserRole)
        if iso:
            self._load_report(date.fromisoformat(iso))

    def _on_summary_mode(self, _idx: int) -> None:
        is_week = self.summary_mode.currentIndex() == 0
        self.lbl_week.setVisible(is_week)
        self.week_anchor.setVisible(is_week)
        self.lbl_month.setVisible(not is_week)
        self.month_edit.setVisible(not is_week)
        self._update_summary_range()

    def _update_summary_range(self) -> None:
        if self.summary_mode.currentIndex() == 0:
            qd = self.week_anchor.date()
            anchor = date(qd.year(), qd.month(), qd.day())
            start, end = week_range(anchor)
            title = "本周日报原文"
        else:
            qd = self.month_edit.date()
            anchor = date(qd.year(), qd.month(), 1)
            start, end = month_range(anchor)
            title = "本月日报原文"
        reports = self._store.load_range(start, end)
        n = len(reports)
        if self.summary_mode.currentIndex() == 0:
            self.summary_range_label.setText(
                f"将汇总 {start.isoformat()}（周一）~ {end.isoformat()}（周日），共 {n} 篇日报"
            )
        else:
            self.summary_range_label.setText(
                f"将汇总 {start.isoformat()} ~ {end.isoformat()}，共 {n} 篇日报"
            )
        if hasattr(self, "src_title"):
            self.src_title.setText(f"{title}（{n} 篇）")
        if hasattr(self, "source_view"):
            self._refresh_source_reports(reports, start, end)

    def _refresh_source_reports(self, reports, start: date, end: date) -> None:
        """右侧展示范围内全部日报，便于写周报/月报时对照。"""
        if not reports:
            self.source_view.setPlainText(
                f"{start.isoformat()} ~ {end.isoformat()} 范围内还没有日报。\n"
                "可在「今日工作」里先记录。"
            )
            self._source_text = ""
            return
        parts: list[str] = []
        # 标出范围内缺失的工作日
        present = {r.report_date for r in reports}
        cursor = start
        missing = []
        while cursor <= end:
            if cursor.weekday() < 5 and cursor not in present:
                missing.append(cursor.isoformat())
            cursor = date.fromordinal(cursor.toordinal() + 1)
        if missing:
            parts.append("（缺日报：" + "、".join(missing) + "）\n")

        for r in reports:
            work = "\n".join(f"  {i}. {w}" for i, w in enumerate(r.work_items, 1)) or "  （无）"
            parts.append(
                f"======== {r.date_str} ========\n"
                f"【任务目标】{r.goal or '（无）'}\n"
                f"【具体工作】\n{work}\n"
                f"【下一步计划】{r.next_steps or '（无）'}\n"
            )
        text = "\n".join(parts)
        self._source_text = text
        self.source_view.setPlainText(text)

    def _copy_source_reports(self) -> None:
        text = getattr(self, "_source_text", "") or self.source_view.toPlainText()
        if not text.strip():
            return
        QApplication.clipboard().setText(text)
        self._set_status("已复制范围内日报到剪贴板")

    def _run_summary(self) -> None:
        self._update_summary_range()
        if not self._ensure_llm_ready():
            return
        if self.summary_mode.currentIndex() == 0:
            qd = self.week_anchor.date()
            anchor = date(qd.year(), qd.month(), qd.day())
            start, end = week_range(anchor)
            reports = self._store.load_range(start, end)
            mode = "week"
            month_label = ""
        else:
            qd = self.month_edit.date()
            anchor = date(qd.year(), qd.month(), 1)
            start, end = month_range(anchor)
            reports = self._store.load_range(start, end)
            mode = "month"
            month_label = f"{start.year}年{start.month}月"

        if not reports:
            QMessageBox.information(self, "提示", "该时间范围内没有日报，无法生成总结。")
            return

        self.btn_run_summary.setEnabled(False)
        self.summary_view.setPlainText("正在生成…")
        self._summary_ctrl.start(
            self._cfg,
            reports,
            mode,
            week_start=start.isoformat(),
            week_end=end.isoformat(),
            month_label=month_label,
        )

    def _on_summary_ok(self, text: str) -> None:
        self.btn_run_summary.setEnabled(True)
        self.summary_view.setPlainText(text)
        if self.summary_mode.currentIndex() == 0:
            qd = self.week_anchor.date()
            start, _ = week_range(date(qd.year(), qd.month(), qd.day()))
            out = self._store.summaries_dir / f"week_{start.isoformat()}.md"
        else:
            qd = self.month_edit.date()
            start, _ = month_range(date(qd.year(), qd.month(), 1))
            out = self._store.summaries_dir / f"month_{start.strftime('%Y-%m')}.md"
        out.write_text(text + "\n", encoding="utf-8")
        self._set_status(f"总结已保存: {out}")

    def _on_summary_fail(self, err: str) -> None:
        self.btn_run_summary.setEnabled(True)
        self.summary_view.setPlainText(f"生成失败：{err}")
        QMessageBox.critical(self, "生成失败", err)

    def _save_summary_as(self) -> None:
        text = self.summary_view.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "提示", "当前没有可保存的总结内容。")
            return
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "保存总结", "summary.md", "Markdown (*.md)"
        )
        if path:
            Path(path).write_text(text + "\n", encoding="utf-8")
            self._set_status(f"已另存: {path}")

    def _open_summaries_dir(self) -> None:
        d = self._store.summaries_dir
        d.mkdir(parents=True, exist_ok=True)
        import os
        import subprocess
        import sys

        if sys.platform.startswith("win"):
            os.startfile(d)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(d)])
        else:
            subprocess.Popen(["xdg-open", str(d)])

    def _run_search(self) -> None:
        raw = self.search_input.text().strip()
        if not raw:
            self.search_results.setPlainText("请输入关键词。")
            return
        keywords = [k for k in raw.split() if k]
        start = date(
            self.search_from.date().year(),
            self.search_from.date().month(),
            self.search_from.date().day(),
        )
        end = date(
            self.search_to.date().year(),
            self.search_to.date().month(),
            self.search_to.date().day(),
        )
        reports = self._store.load_range(start, end)
        # 同时把流水纳入检索范围（未正式成稿也可搜到）
        from datetime import datetime as _dt

        for d in self._store.list_log_dates():
            if start <= d <= end and not self._store.exists(d):
                logs = self._store.load_logs(d)
                if logs:
                    pseudo = DailyReport(
                        report_date=d,
                        goal="",
                        work_items=[e.text for e in logs],
                        next_steps="",
                    )
                    reports.append(pseudo)

        hits = search_reports(reports, keywords, case_sensitive=self.case_check.isChecked())
        if not hits:
            self.search_results.setPlainText(
                f"未找到包含 {keywords} 的日报/流水。\n范围: {start} ~ {end}"
            )
            return
        parts = [f"找到 {len(hits)} 篇相关内容：\n"]
        for hit in hits:
            parts.append(f"■ {hit.report.date_str}（命中 {hit.score} 次）")
            for line in hit.matched_lines:
                parts.append(f"    {line}")
            parts.append("")
        self.search_results.setPlainText("\n".join(parts))
        self._set_status(f"搜索到 {len(hits)} 篇")

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._cfg, self)
        if dlg.exec():
            self._cfg = dlg.result_config()
            self._store = ReportStore(self._cfg.data_dir)
            self._reload_all()
            self._set_status("设置已更新")
            self.config_changed.emit(self._cfg)

    def apply_config(self, cfg: Config) -> None:
        self._cfg = cfg
        self._store = ReportStore(cfg.data_dir)
        if hasattr(self, "calendar_view"):
            self.calendar_view.set_store(self._store)
        self.apply_mode()
        self._reload_all()

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "关于工作台",
            "工作台 · 日报记录\n\n"
            "白天随手记流水 → 下班 AI 一键成稿或手写日报 → 周报/月报汇总。\n\n"
            f"模型: {self._cfg.llm.model}\n"
            f"Base URL: {self._cfg.llm.base_url}\n"
            f"数据: {self._cfg.data_dir}",
        )

    def _set_status(self, msg: str) -> None:
        self.statusBar().showMessage(msg)
