"""任务计划窗口：截止日期、子任务勾选、进度与剩余时间、AI 拆分。"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
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
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from daily_report.config import Config
from daily_report.gui.workers import BreakdownController
from daily_report.tasks import SubTask, TaskPlan, TaskStore

STATUSES = ["进行中", "已完成", "已取消"]


class TaskWindow(QMainWindow):
    back_to_hub = Signal()

    def __init__(self, store: TaskStore, cfg: Config):
        super().__init__()
        self.setWindowTitle("任务计划")
        self.resize(1180, 780)
        self._store = store
        self._cfg = cfg
        self._current_id: str | None = None

        self._bd = BreakdownController(self)
        self._bd.finished.connect(self._on_breakdown)
        self._bd.failed.connect(self._on_breakdown_fail)
        self._bd.status.connect(self._set_status)

        self._build_ui()
        self._reload_list()

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
        title = QLabel("任务计划")
        title.setObjectName("SectionTitle")
        top.addWidget(btn_back)
        top.addWidget(title)
        top.addStretch(1)
        outer.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(splitter, 1)
        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())

        # 左侧
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(4, 4, 4, 4)
        ll.setSpacing(6)

        self.btn_new = QPushButton("＋ 新建任务")
        self.btn_new.setObjectName("PrimaryBig")
        self.btn_new.clicked.connect(self._new_task)
        ll.addWidget(self.btn_new)

        self.filter_box = QComboBox()
        self.filter_box.addItems(["全部", "进行中", "已完成", "已取消", "逾期"])
        self.filter_box.currentIndexChanged.connect(self._reload_list)
        ll.addWidget(self.filter_box)

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_select)
        ll.addWidget(self.list_widget, 1)

        btn_del = QPushButton("删除选中")
        btn_del.setObjectName("DangerGhost")
        btn_del.clicked.connect(self._delete_selected)
        ll.addWidget(btn_del)
        splitter.addWidget(left)

        # 右侧
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 4, 4, 4)
        rl.setSpacing(8)

        self.detail_title = QLabel("新建任务")
        f = QFont()
        f.setPointSize(13)
        f.setBold(True)
        self.detail_title.setFont(f)
        rl.addWidget(self.detail_title)

        meta = QHBoxLayout()
        meta.addWidget(QLabel("标题"))
        self.edit_title = QLineEdit()
        self.edit_title.setPlaceholderText("要完成的大目标")
        meta.addWidget(self.edit_title, 3)
        meta.addWidget(QLabel("状态"))
        self.edit_status = QComboBox()
        self.edit_status.addItems(STATUSES)
        meta.addWidget(self.edit_status, 1)
        meta.addWidget(QLabel("预计完成"))
        self.edit_deadline = QDateEdit()
        self.edit_deadline.setCalendarPopup(True)
        self.edit_deadline.setDisplayFormat("yyyy-MM-dd")
        self.edit_deadline.setDate(QDate.currentDate().addDays(7))
        self.edit_deadline.dateChanged.connect(lambda *_: self._refresh_progress())
        meta.addWidget(self.edit_deadline, 1)
        rl.addLayout(meta)

        rl.addWidget(QLabel("描述"))
        self.edit_desc = QPlainTextEdit()
        self.edit_desc.setPlaceholderText("背景、范围、验收标准…")
        self.edit_desc.setMaximumHeight(90)
        rl.addWidget(self.edit_desc)

        # 进度条
        prog_row = QHBoxLayout()
        prog_row.addWidget(QLabel("进度"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        prog_row.addWidget(self.progress_bar, 2)
        self.lbl_remain = QLabel("剩余 —")
        self.lbl_remain.setStyleSheet("font-weight:700; color:#2F7EB3;")
        prog_row.addWidget(self.lbl_remain)
        self.lbl_subcount = QLabel("0/0")
        prog_row.addWidget(self.lbl_subcount)
        rl.addLayout(prog_row)

        # 子任务
        sub_head = QHBoxLayout()
        sub_head.addWidget(QLabel("子任务（勾选表示完成）"))
        sub_head.addStretch(1)
        self.btn_ai = QPushButton("AI 拆分任务")
        self.btn_ai.setStyleSheet(
            "font-weight:bold; padding:6px 14px; background:#2b6cb0; color:white;"
        )
        self.btn_ai.clicked.connect(self._run_breakdown)
        self.btn_add_sub = QPushButton("手动加一条")
        self.btn_add_sub.setObjectName("Ghost")
        self.btn_add_sub.clicked.connect(self._add_subtask)
        self.btn_del_sub = QPushButton("删除选中子任务")
        self.btn_del_sub.setObjectName("DangerGhost")
        self.btn_del_sub.clicked.connect(self._del_subtask)
        sub_head.addWidget(self.btn_ai)
        sub_head.addWidget(self.btn_add_sub)
        sub_head.addWidget(self.btn_del_sub)
        rl.addLayout(sub_head)

        self.sub_list = QListWidget()
        self.sub_list.setStyleSheet(
            "QListWidget::item { padding: 4px; } QListWidget { border: 2px solid #DCE7F0; border-radius: 10px; }"
        )
        self.sub_list.itemChanged.connect(lambda *_: self._refresh_progress())
        rl.addWidget(self.sub_list, 1)

        self.edit_new_sub = QLineEdit()
        self.edit_new_sub.setPlaceholderText("输入子任务后回车添加")
        self.edit_new_sub.returnPressed.connect(self._add_subtask)
        rl.addWidget(self.edit_new_sub)

        save_row = QHBoxLayout()
        self.btn_save = QPushButton("保存任务")
        self.btn_save.setObjectName("PrimaryBig")
        self.btn_save.clicked.connect(self._save_current)
        self.btn_mark_done = QPushButton("全部完成")
        self.btn_mark_done.setObjectName("Ghost")
        self.btn_mark_done.clicked.connect(self._mark_all_done)
        self.btn_clear = QPushButton("清空表单")
        self.btn_clear.setObjectName("Ghost")
        self.btn_clear.clicked.connect(self._clear_form)
        save_row.addWidget(self.btn_save)
        save_row.addWidget(self.btn_mark_done)
        save_row.addWidget(self.btn_clear)
        save_row.addStretch(1)
        rl.addLayout(save_row)

        splitter.addWidget(right)
        splitter.setSizes([300, 880])
        self._set_status("任务计划就绪")

    # ---------- 列表 ----------

    def apply_config(self, cfg: Config) -> None:
        self._cfg = cfg
        self.btn_ai.setVisible(cfg.is_ai)

    def set_store(self, store: TaskStore) -> None:
        self._store = store
        self._reload_list()

    def _reload_list(self) -> None:
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        filt = self.filter_box.currentText()
        tasks = self._store.load_all()
        # 未完成优先、截止近优先
        tasks.sort(key=lambda t: (t.status == "已完成", t.deadline or date.max, t.task_id))
        today = date.today()
        for t in tasks:
            if filt == "进行中" and t.status != "进行中":
                continue
            if filt == "已完成" and t.status != "已完成":
                continue
            if filt == "已取消" and t.status != "已取消":
                continue
            if filt == "逾期":
                d = t.days_left(today)
                if t.status == "已完成" or d is None or d >= 0:
                    continue
            remain = t.remaining_text(today)
            item = QListWidgetItem(
                f"{t.progress_pct:3d}%  {remain}  {t.title[:22]}"
            )
            item.setData(Qt.ItemDataRole.UserRole, t.task_id)
            # 逾期标红
            d = t.days_left(today)
            if t.status != "已完成" and d is not None and d < 0:
                from PySide6.QtGui import QColor

                item.setForeground(QColor("#E74C3C"))
            self.list_widget.addItem(item)
            if t.task_id == self._current_id:
                self.list_widget.setCurrentItem(item)
        self.list_widget.blockSignals(False)
        self._set_status(f"共 {self.list_widget.count()} 条任务")

    def _on_select(self, current: QListWidgetItem | None, _prev=None) -> None:
        if not current:
            return
        tid = current.data(Qt.ItemDataRole.UserRole)
        if tid:
            self._load_task(tid)

    def _load_task(self, task_id: str) -> None:
        task = self._store.load(task_id)
        if not task:
            return
        self._current_id = task_id
        self.detail_title.setText(task.task_id)
        self.edit_title.setText(task.title)
        self.edit_status.setCurrentText(task.status)
        if task.deadline:
            self.edit_deadline.setDate(
                QDate(task.deadline.year, task.deadline.month, task.deadline.day)
            )
        self.edit_desc.setPlainText(task.description)
        self._render_subtasks(task.subtasks)
        self._refresh_progress()

    def _render_subtasks(self, subtasks: list[SubTask]) -> None:
        self.sub_list.clear()
        for st in subtasks:
            item = QListWidgetItem(st.title)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if st.done else Qt.CheckState.Unchecked)
            self.sub_list.addItem(item)

    def _subtasks_from_ui(self) -> list[SubTask]:
        out = []
        for i in range(self.sub_list.count()):
            it = self.sub_list.item(i)
            out.append(
                SubTask(
                    title=it.text().strip(),
                    done=it.checkState() == Qt.CheckState.Checked,
                )
            )
        return out

    def _refresh_progress(self) -> None:
        subs = self._subtasks_from_ui()
        total = len(subs)
        done = sum(1 for s in subs if s.done)
        pct = 0 if total == 0 else int(round(done * 100 / total))
        if self.edit_status.currentText() == "已完成":
            pct = 100
        self.progress_bar.setValue(pct)
        self.lbl_subcount.setText(f"{done}/{total}")

        qd = self.edit_deadline.date()
        deadline = date(qd.year(), qd.month(), qd.day())
        left = (deadline - date.today()).days
        status = self.edit_status.currentText()
        if status == "已完成":
            self.lbl_remain.setText("已完成")
            self.lbl_remain.setStyleSheet("font-weight:700; color:#27AE60;")
        elif status == "已取消":
            self.lbl_remain.setText("已取消")
            self.lbl_remain.setStyleSheet("font-weight:700; color:#7A8B9A;")
        elif left < 0:
            self.lbl_remain.setText(f"已逾期 {-left} 天")
            self.lbl_remain.setStyleSheet("font-weight:700; color:#E74C3C;")
        elif left == 0:
            self.lbl_remain.setText("今天截止")
            self.lbl_remain.setStyleSheet("font-weight:700; color:#E67E22;")
        else:
            self.lbl_remain.setText(f"剩余 {left} 天")
            self.lbl_remain.setStyleSheet("font-weight:700; color:#2F7EB3;")

    def _clear_form(self) -> None:
        self._current_id = None
        self.detail_title.setText("新建任务")
        self.edit_title.clear()
        self.edit_status.setCurrentText("进行中")
        self.edit_deadline.setDate(QDate.currentDate().addDays(7))
        self.edit_desc.clear()
        self.sub_list.clear()
        self.edit_new_sub.clear()
        self._refresh_progress()
        self.edit_title.setFocus()

    def _new_task(self) -> None:
        self._clear_form()

    def _collect(self) -> TaskPlan | None:
        title = self.edit_title.text().strip()
        if not title:
            QMessageBox.information(self, "提示", "请填写任务标题。")
            return None
        qd = self.edit_deadline.date()
        deadline = date(qd.year(), qd.month(), qd.day())
        tid = self._current_id or self._store.next_id()
        return TaskPlan(
            task_id=tid,
            title=title,
            description=self.edit_desc.toPlainText().strip(),
            deadline=deadline,
            status=self.edit_status.currentText(),
            subtasks=self._subtasks_from_ui(),
        )

    def _save_current(self) -> None:
        task = self._collect()
        if not task:
            return
        # 全勾选且状态仍进行中 → 提示可标完成
        if task.subtasks and task.done_count == task.total and task.status == "进行中":
            task.status = "已完成"
            self.edit_status.setCurrentText("已完成")
        path = self._store.save(task)
        self._current_id = task.task_id
        self._reload_list()
        self._refresh_progress()
        self._set_status(f"已保存 {path.name}")

    def _add_subtask(self) -> None:
        text = self.edit_new_sub.text().strip()
        if not text:
            return
        item = QListWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Unchecked)
        self.sub_list.addItem(item)
        self.edit_new_sub.clear()
        self.edit_new_sub.setFocus()
        self._refresh_progress()

    def _del_subtask(self) -> None:
        row = self.sub_list.currentRow()
        if row < 0:
            return
        self.sub_list.takeItem(row)
        self._refresh_progress()

    def _mark_all_done(self) -> None:
        for i in range(self.sub_list.count()):
            self.sub_list.item(i).setCheckState(Qt.CheckState.Checked)
        self.edit_status.setCurrentText("已完成")
        self._refresh_progress()

    def _delete_selected(self) -> None:
        item = self.list_widget.currentItem()
        if not item:
            return
        tid = item.data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "确认删除", f"删除 {tid}？") == QMessageBox.StandardButton.Yes:
            self._store.delete(tid)
            if self._current_id == tid:
                self._clear_form()
            self._reload_list()

    # ---------- AI 拆分 ----------

    def _run_breakdown(self) -> None:
        title = self.edit_title.text().strip()
        if not title:
            QMessageBox.information(self, "提示", "请先填写任务标题，再点 AI 拆分。")
            return
        if not self._cfg.is_ai:
            QMessageBox.information(
                self,
                "当前为非 AI 版",
                "非 AI 版请使用「手动加一条」维护子任务。",
            )
            return
        if not self._cfg.llm_ready():
            QMessageBox.warning(
                self,
                "未配置模型",
                "请先在「文件 → 设置」中配置 OpenAI 协议的 Base URL / API Key / 模型。",
            )
            return
        # 已有子任务时确认
        if self.sub_list.count():
            ret = QMessageBox.question(
                self,
                "覆盖确认",
                "当前已有子任务，AI 拆分将替换它们。继续？",
            )
            if ret != QMessageBox.StandardButton.Yes:
                return
        qd = self.edit_deadline.date()
        deadline = f"{qd.year():04d}-{qd.month():02d}-{qd.day():02d}"
        self.btn_ai.setEnabled(False)
        self.btn_ai.setText("拆分中…")
        self._bd.start(
            self._cfg,
            title,
            self.edit_desc.toPlainText().strip(),
            deadline,
        )

    def _on_breakdown(self, items: list) -> None:
        self.btn_ai.setEnabled(True)
        self.btn_ai.setText("AI 拆分任务")
        self.sub_list.clear()
        for text in items:
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.sub_list.addItem(item)
        self._refresh_progress()
        self._set_status(f"AI 已生成 {len(items)} 条子任务，记得保存")

    def _on_breakdown_fail(self, err: str) -> None:
        self.btn_ai.setEnabled(True)
        self.btn_ai.setText("AI 拆分任务")
        QMessageBox.critical(self, "拆分失败", err)

    def _set_status(self, msg: str) -> None:
        self.statusBar().showMessage(msg)
