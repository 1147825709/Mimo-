"""BugList 主功能窗口：录入、浏览、搜索相近。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from daily_report.bug_search import find_similar, search_bugs
from daily_report.bug_store import BugStore
from daily_report.bugs import BugRecord, BugStatus


class BugWindow(QMainWindow):
    back_to_hub = Signal()

    def __init__(self, store: BugStore):
        super().__init__()
        self.setWindowTitle("Bug 列表")
        self.resize(1200, 780)
        self._store = store
        self._current_id: str | None = None

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
        title = QLabel("Bug 列表")
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

        row_new = QHBoxLayout()
        self.btn_new = QPushButton("＋ 新建 Bug")
        self.btn_new.setObjectName("PrimaryBig")
        self.btn_new.clicked.connect(self._new_bug)
        row_new.addWidget(self.btn_new)
        ll.addLayout(row_new)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("关键词搜索（空格 AND）")
        self.search_input.returnPressed.connect(self._run_keyword_search)
        btn_s = QPushButton("搜索")
        btn_s.setObjectName("Ghost")
        btn_s.clicked.connect(self._run_keyword_search)
        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(btn_s)
        ll.addLayout(search_row)

        self.filter_status = QComboBox()
        self.filter_status.addItem("全部状态")
        for s in BugStatus:
            self.filter_status.addItem(s.value)
        self.filter_status.currentIndexChanged.connect(self._reload_list)
        ll.addWidget(self.filter_status)

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
        rl.setSpacing(6)

        self.detail_title = QLabel("新建 / 编辑 Bug")
        f = QFont()
        f.setPointSize(13)
        f.setBold(True)
        self.detail_title.setFont(f)
        rl.addWidget(self.detail_title)

        meta = QHBoxLayout()
        meta.addWidget(QLabel("标题"))
        self.edit_title = QLineEdit()
        self.edit_title.setPlaceholderText("一句话描述这个 Bug")
        meta.addWidget(self.edit_title, 3)
        meta.addWidget(QLabel("状态"))
        self.edit_status = QComboBox()
        for s in BugStatus:
            self.edit_status.addItem(s.value)
        meta.addWidget(self.edit_status, 1)
        meta.addWidget(QLabel("标签"))
        self.edit_tags = QLineEdit()
        self.edit_tags.setPlaceholderText("逗号分隔，如：登录,超时,后端")
        meta.addWidget(self.edit_tags, 2)
        meta.addWidget(QLabel("环境"))
        self.edit_env = QLineEdit()
        self.edit_env.setPlaceholderText("如：Win11 / Chrome 128")
        meta.addWidget(self.edit_env, 1)
        rl.addLayout(meta)

        def labeled_edit(placeholder: str, max_h: int | None = None) -> QPlainTextEdit:
            ed = QPlainTextEdit()
            ed.setPlaceholderText(placeholder)
            if max_h:
                ed.setMaximumHeight(max_h)
            return ed

        rl.addWidget(QLabel("现象"))
        self.edit_symptom = labeled_edit("复现步骤、表现…")
        rl.addWidget(self.edit_symptom, 2)

        rl.addWidget(QLabel("错误信息 / 日志"))
        self.edit_error = labeled_edit("报错堆栈、关键日志…")
        rl.addWidget(self.edit_error, 2)

        rl.addWidget(QLabel("根因"))
        self.edit_root = labeled_edit("问题原因", 90)
        rl.addWidget(self.edit_root)

        rl.addWidget(QLabel("解决方案"))
        self.edit_solution = labeled_edit("怎么修的、临时绕过方案…")
        rl.addWidget(self.edit_solution, 2)

        rl.addWidget(QLabel("备注"))
        self.edit_note = labeled_edit("关联单号、参考链接…", 70)
        rl.addWidget(self.edit_note)

        save_row = QHBoxLayout()
        self.btn_save = QPushButton("保存 Bug")
        self.btn_save.setObjectName("PrimaryBig")
        self.btn_save.clicked.connect(self._save_current)
        self.btn_clear = QPushButton("清空表单")
        self.btn_clear.setObjectName("Ghost")
        self.btn_clear.clicked.connect(self._clear_form)
        save_row.addWidget(self.btn_save)
        save_row.addWidget(self.btn_clear)
        save_row.addStretch(1)
        rl.addLayout(save_row)

        # 相近搜索
        sim_box = QVBoxLayout()
        sim_head = QHBoxLayout()
        sim_head.addWidget(QLabel("找相近 Bug"))
        self.sim_input = QLineEdit()
        self.sim_input.setPlaceholderText("粘贴报错/描述，或对当前编辑中的内容搜索")
        self.btn_sim = QPushButton("搜索相似")
        self.btn_sim.clicked.connect(self._run_similar)
        self.btn_sim_self = QPushButton("按当前表单找相似")
        self.btn_sim_self.setObjectName("Ghost")
        self.btn_sim_self.clicked.connect(self._run_similar_from_form)
        sim_head.addWidget(self.sim_input, 1)
        sim_head.addWidget(self.btn_sim)
        sim_head.addWidget(self.btn_sim_self)
        sim_box.addLayout(sim_head)
        self.sim_view = QTextEdit()
        self.sim_view.setReadOnly(True)
        self.sim_view.setMaximumHeight(160)
        self.sim_view.setPlaceholderText("相似结果会显示在这里；点击左侧列表可打开对应 Bug。")
        sim_box.addWidget(self.sim_view)
        rl.addLayout(sim_box)

        splitter.addWidget(right)
        splitter.setSizes([320, 880])

        self._set_status("Bug 列表就绪")

    # ---------- 列表 ----------

    def _reload_list(self) -> None:
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        status_filter = self.filter_status.currentText()
        bugs = self._store.load_all()
        bugs.sort(key=lambda b: b.created_at or b.bug_id, reverse=True)
        for b in bugs:
            if status_filter != "全部状态" and b.status.value != status_filter:
                continue
            item = QListWidgetItem(f"[{b.status.value}] {b.bug_id}  {b.title[:28]}")
            item.setData(Qt.ItemDataRole.UserRole, b.bug_id)
            self.list_widget.addItem(item)
            if b.bug_id == self._current_id:
                self.list_widget.setCurrentItem(item)
        self.list_widget.blockSignals(False)
        self._set_status(f"共 {self.list_widget.count()} 条")

    def _on_select(self, current: QListWidgetItem | None, _prev=None) -> None:
        if not current:
            return
        bid = current.data(Qt.ItemDataRole.UserRole)
        if bid:
            self._load_bug(bid)

    def _load_bug(self, bug_id: str) -> None:
        bug = self._store.load(bug_id)
        if not bug:
            return
        self._current_id = bug_id
        self.detail_title.setText(f"{bug.bug_id}")
        self.edit_title.setText(bug.title)
        self.edit_status.setCurrentText(bug.status.value)
        self.edit_tags.setText("、".join(bug.tags))
        self.edit_env.setText(bug.env)
        self.edit_symptom.setPlainText(bug.symptom)
        self.edit_error.setPlainText(bug.error_info)
        self.edit_root.setPlainText(bug.root_cause)
        self.edit_solution.setPlainText(bug.solution)
        self.edit_note.setPlainText(bug.note)

    def _clear_form(self) -> None:
        self._current_id = None
        self.detail_title.setText("新建 Bug")
        self.edit_title.clear()
        self.edit_status.setCurrentText(BugStatus.OPEN.value)
        self.edit_tags.clear()
        self.edit_env.clear()
        self.edit_symptom.clear()
        self.edit_error.clear()
        self.edit_root.clear()
        self.edit_solution.clear()
        self.edit_note.clear()
        self.edit_title.setFocus()

    def _new_bug(self) -> None:
        self._clear_form()
        self.edit_title.setFocus()

    def _collect(self) -> BugRecord | None:
        title = self.edit_title.text().strip()
        if not title:
            QMessageBox.information(self, "提示", "请填写标题。")
            return None
        tags = [
            t.strip()
            for t in self.edit_tags.text().replace("，", ",").replace("、", ",").split(",")
            if t.strip()
        ]
        bid = self._current_id or self._store.next_id()
        return BugRecord(
            bug_id=bid,
            title=title,
            status=BugStatus.from_str(self.edit_status.currentText()),
            tags=tags,
            env=self.edit_env.text().strip(),
            symptom=self.edit_symptom.toPlainText().strip(),
            error_info=self.edit_error.toPlainText().strip(),
            root_cause=self.edit_root.toPlainText().strip(),
            solution=self.edit_solution.toPlainText().strip(),
            note=self.edit_note.toPlainText().strip(),
        )

    def _save_current(self) -> None:
        bug = self._collect()
        if not bug:
            return
        path = self._store.save(bug)
        self._current_id = bug.bug_id
        self._reload_list()
        self._set_status(f"已保存 {path.name}")

    def _delete_selected(self) -> None:
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.information(self, "提示", "请先选中一条 Bug。")
            return
        bid = item.data(Qt.ItemDataRole.UserRole)
        ret = QMessageBox.question(self, "确认删除", f"删除 {bid}？")
        if ret == QMessageBox.StandardButton.Yes:
            self._store.delete(bid)
            if self._current_id == bid:
                self._clear_form()
            self._reload_list()

    # ---------- 相似搜索 ----------

    def _run_keyword_search(self) -> None:
        raw = self.search_input.text().strip()
        if not raw:
            self._reload_list()
            return
        keys = raw.split()
        hits = search_bugs(self._store.load_all(), keys)
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for b in hits:
            item = QListWidgetItem(f"[{b.status.value}] {b.bug_id}  {b.title[:28]}")
            item.setData(Qt.ItemDataRole.UserRole, b.bug_id)
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)
        self._set_status(f"关键词命中 {len(hits)} 条")

    def _run_similar(self) -> None:
        q = self.sim_input.text().strip()
        if not q:
            QMessageBox.information(self, "提示", "请输入要搜索的报错或描述。")
            return
        self._show_similar(q)

    def _run_similar_from_form(self) -> None:
        probe = self._collect()
        if not probe:
            return
        self._show_similar(probe)

    def _show_similar(self, query) -> None:  # noqa: ANN001
        exclude = self._current_id
        hits = find_similar(query, self._store.load_all(), exclude_id=exclude, top_k=8)
        if not hits:
            self.sim_view.setPlainText("未找到足够相近的历史 Bug。可尝试补充标签或更完整的报错。")
            return
        lines = [f"找到 {len(hits)} 条相近 Bug：\n"]
        for h in hits:
            lines.append(f"■ [{h.score:.0%}] {h.bug.bug_id}  {h.bug.title}")
            if h.reasons:
                lines.append(f"    原因：{'；'.join(h.reasons)}")
            if h.bug.solution:
                sol = h.bug.solution.replace("\n", " ")[:60]
                lines.append(f"    方案：{sol}…")
            lines.append("")
        lines.append("提示：在左侧列表点击对应 ID 可打开详情。")
        self.sim_view.setPlainText("\n".join(lines))
        self._set_status(f"相似命中 {len(hits)} 条")

    def _set_status(self, msg: str) -> None:
        self.statusBar().showMessage(msg)
