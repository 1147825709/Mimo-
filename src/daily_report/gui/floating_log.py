"""桌面悬浮窗：默认小胶囊，点击展开；支持流水 / Bug。"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, QPoint, QTimer, Signal
from PySide6.QtGui import QEnterEvent, QMouseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from daily_report.bug_store import BugStore
from daily_report.storage import ReportStore

COMPACT_W = 92
COMPACT_H = 36
EXPANDED_W = 360


class FloatingLogWidget(QWidget):
    """默认小胶囊，点击展开录入面板；支持流水与 Bug。"""

    logged = Signal(str)
    bug_saved = Signal(str)
    open_main = Signal()
    open_bugs = Signal()

    def __init__(
        self,
        store: ReportStore,
        bug_store: BugStore | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._store = store
        self._bug_store = bug_store
        self._drag_offset: QPoint | None = None
        self._expanded = False  # 默认收起成小胶囊
        self._mode = "log"  # log | bug
        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.timeout.connect(self.collapse)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle("悬浮随手记")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- 小胶囊（默认）----
        self.pill = QFrame()
        self.pill.setObjectName("FloatPill")
        pill_l = QHBoxLayout(self.pill)
        pill_l.setContentsMargins(14, 6, 14, 6)
        pill_l.setSpacing(6)
        self.pill_label = QLabel("✎ 记")
        self.pill_label.setObjectName("FloatPillLabel")
        pill_l.addWidget(self.pill_label)
        root.addWidget(self.pill)

        # ---- 展开面板 ----
        self.card = QFrame()
        self.card.setObjectName("FloatingCard")
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        head = QHBoxLayout()
        self.title_lb = QLabel("随手记")
        self.title_lb.setObjectName("FloatTitle")
        self.btn_collapse = QPushButton("收起")
        self.btn_collapse.setFixedWidth(48)
        self.btn_collapse.setObjectName("Ghost")
        self.btn_collapse.clicked.connect(self.collapse)
        btn_close = QPushButton("×")
        btn_close.setFixedWidth(36)
        btn_close.setObjectName("DangerGhost")
        btn_close.clicked.connect(self.hide)
        head.addWidget(self.title_lb)
        head.addStretch(1)
        head.addWidget(self.btn_collapse)
        head.addWidget(btn_close)
        lay.addLayout(head)

        mode_row = QHBoxLayout()
        self.btn_mode_log = QPushButton("流水")
        self.btn_mode_bug = QPushButton("Bug")
        for b in (self.btn_mode_log, self.btn_mode_bug):
            b.setCheckable(True)
            b.setObjectName("Ghost")
            b.setFixedHeight(30)
        self.btn_mode_log.setChecked(True)
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_group.addButton(self.btn_mode_log)
        self._mode_group.addButton(self.btn_mode_bug)
        self.btn_mode_log.clicked.connect(lambda: self._set_mode("log"))
        self.btn_mode_bug.clicked.connect(lambda: self._set_mode("bug"))
        mode_row.addWidget(self.btn_mode_log, 1)
        mode_row.addWidget(self.btn_mode_bug, 1)
        lay.addLayout(mode_row)

        # 流水
        self.log_panel = QWidget()
        log_l = QVBoxLayout(self.log_panel)
        log_l.setContentsMargins(0, 0, 0, 0)
        log_l.setSpacing(6)
        self.input = QLineEdit()
        self.input.setPlaceholderText("完成了一项工作就记一条…")
        self.input.returnPressed.connect(self._save_log)
        log_l.addWidget(self.input)
        self.btn_save_log = QPushButton("记一笔")
        self.btn_save_log.setObjectName("PrimaryBig")
        self.btn_save_log.clicked.connect(self._save_log)
        log_l.addWidget(self.btn_save_log)
        lay.addWidget(self.log_panel)

        # Bug
        self.bug_panel = QWidget()
        bug_l = QVBoxLayout(self.bug_panel)
        bug_l.setContentsMargins(0, 0, 0, 0)
        bug_l.setSpacing(6)
        self.bug_title = QLineEdit()
        self.bug_title.setPlaceholderText("Bug 标题（必填）")
        self.bug_title.returnPressed.connect(self._focus_bug_symptom)
        bug_l.addWidget(self.bug_title)
        self.bug_symptom = QLineEdit()
        self.bug_symptom.setPlaceholderText("现象/报错（可选）")
        self.bug_symptom.returnPressed.connect(self._save_bug)
        bug_l.addWidget(self.bug_symptom)
        self.bug_tags = QLineEdit()
        self.bug_tags.setPlaceholderText("标签，逗号分隔（可选）")
        self.bug_tags.returnPressed.connect(self._save_bug)
        bug_l.addWidget(self.bug_tags)
        self.btn_save_bug = QPushButton("记 Bug")
        self.btn_save_bug.setObjectName("PrimaryBig")
        self.btn_save_bug.clicked.connect(self._save_bug)
        bug_l.addWidget(self.btn_save_bug)
        self.bug_panel.setVisible(False)
        lay.addWidget(self.bug_panel)

        foot = QHBoxLayout()
        self.btn_open = QPushButton("打开日报")
        self.btn_open.setObjectName("Ghost")
        self.btn_open.clicked.connect(self.open_main.emit)
        self.btn_open_bugs = QPushButton("打开 Bug 列表")
        self.btn_open_bugs.setObjectName("Ghost")
        self.btn_open_bugs.clicked.connect(self.open_bugs.emit)
        foot.addWidget(self.btn_open)
        foot.addWidget(self.btn_open_bugs)
        lay.addLayout(foot)

        self.recent = QLabel("")
        self.recent.setWordWrap(True)
        self.recent.setStyleSheet("color: #7A8B9A; font-size: 9pt;")
        lay.addWidget(self.recent)

        root.addWidget(self.card)
        self.card.setVisible(False)

        self._refresh_recent()
        self._apply_compact_size()
        self._place_default()

    # ---------- 尺寸/显示 ----------

    def _apply_compact_size(self) -> None:
        self.pill.setVisible(True)
        self.card.setVisible(False)
        self.setFixedSize(COMPACT_W, COMPACT_H)
        self.pill_label.setText("✎ 记")

    def expand(self, mode: str | None = None) -> None:
        self._collapse_timer.stop()
        self.pill.setVisible(False)
        self.card.setVisible(True)
        self._expanded = True
        if mode:
            self._mode = mode
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        self._set_mode(self._mode)
        self.adjustSize()
        self.setFixedSize(EXPANDED_W, max(self.sizeHint().height(), 200))
        if self._mode == "log":
            self.input.setFocus()
        else:
            self.bug_title.setFocus()

    def collapse(self) -> None:
        self._expanded = False
        self._apply_compact_size()

    def schedule_collapse(self, ms: int = 900) -> None:
        self._collapse_timer.start(ms)

    def toggle_expanded(self) -> None:
        if self._expanded:
            self.collapse()
        else:
            self.expand()

    # ---------- 交互 ----------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            # 小胶囊：点击即展开（区分拖动：松开时若位移很小）
            if not self._expanded:
                self._press_global = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if not self._expanded and event.button() == Qt.MouseButton.LeftButton:
            press = getattr(self, "_press_global", None)
            if press is not None:
                moved = (event.globalPosition().toPoint() - press).manhattanLength()
                if moved < 8:
                    self.expand()
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def enterEvent(self, event: QEnterEvent) -> None:
        self.setWindowOpacity(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        self.setWindowOpacity(0.88 if not self._expanded else 0.96)
        super().leaveEvent(event)

    # ---------- 数据 ----------

    def _place_default(self) -> None:
        screen = self.screen()
        if screen is None:
            from PySide6.QtWidgets import QApplication

            screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(geo.right() - self.width() - 20, geo.bottom() - self.height() - 20)

    def set_store(self, store: ReportStore, bug_store: BugStore | None = None) -> None:
        self._store = store
        if bug_store is not None:
            self._bug_store = bug_store
        if self._expanded:
            self._refresh_recent()

    def set_bug_store(self, bug_store: BugStore) -> None:
        self._bug_store = bug_store
        if self._expanded and self._mode == "bug":
            self._refresh_recent()

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        is_log = mode == "log"
        self.log_panel.setVisible(is_log)
        self.bug_panel.setVisible(not is_log)
        self.btn_mode_log.setChecked(is_log)
        self.btn_mode_bug.setChecked(not is_log)
        self.title_lb.setText("随手记" if is_log else "快记 Bug")
        self._refresh_recent()
        if self._expanded:
            self.adjustSize()
            self.setFixedWidth(EXPANDED_W)
            self.setFixedHeight(self.height())

    def _refresh_recent(self) -> None:
        if self._mode == "log":
            try:
                entries = self._store.load_logs(date.today())
            except Exception:
                entries = []
            if not entries:
                self.recent.setText("今天还没有流水")
                return
            lines = [f"{e.time_str} {e.text}" for e in entries[-3:]]
            self.recent.setText("最近流水：\n" + "\n".join(lines))
        else:
            if not self._bug_store:
                self.recent.setText("Bug 存储未初始化")
                return
            try:
                bugs = self._bug_store.load_all()[-3:]
            except Exception:
                bugs = []
            if not bugs:
                self.recent.setText("还没有 Bug 记录")
                return
            lines = [f"{b.bug_id}  {b.title[:24]}" for b in reversed(bugs)]
            self.recent.setText("最近 Bug：\n" + "\n".join(lines))

    def _save_log(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self._store.append_log(date.today(), text)
        self.input.clear()
        self._refresh_recent()
        self.logged.emit(text)
        self.schedule_collapse(800)

    def _focus_bug_symptom(self) -> None:
        self.bug_symptom.setFocus()

    def _save_bug(self) -> None:
        title = self.bug_title.text().strip()
        if not title:
            self.bug_title.setFocus()
            return
        if not self._bug_store:
            self.recent.setText("Bug 存储未初始化")
            return
        tags_raw = self.bug_tags.text().strip()
        tags = [t.strip() for t in tags_raw.replace("，", ",").replace("、", ",").split(",") if t.strip()]
        bug = self._bug_store.create(
            title=title,
            symptom=self.bug_symptom.text().strip(),
            tags=tags,
        )
        self.bug_title.clear()
        self.bug_symptom.clear()
        self.bug_tags.clear()
        self._refresh_recent()
        self.bug_saved.emit(f"{bug.bug_id} {bug.title}")
        self.schedule_collapse(800)
