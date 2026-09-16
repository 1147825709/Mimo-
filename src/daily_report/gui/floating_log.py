"""桌面悬浮窗：默认小胶囊，点击展开；支持流水 / Bug。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, QPoint, QTimer, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from daily_report.bug_store import BugStore
from daily_report.storage import ReportStore

COMPACT_W = 92
COMPACT_H = 36
EXPANDED_W = 400
EXPANDED_W_BUG = 440


def _ui_state_path(data_dir: Path) -> Path:
    return data_dir / "ui_state.json"


def load_ui_state(data_dir: Path) -> dict:
    p = _ui_state_path(data_dir)
    try:
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def save_ui_state(data_dir: Path, state: dict) -> None:
    try:
        p = _ui_state_path(data_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


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
        self._expanded = False
        self._mode = "log"
        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.timeout.connect(self.collapse)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        # 失焦不隐藏；减少被系统「吃掉」的概率
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowTitle("悬浮随手记")
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        # 防消失：定时自检，若曾要求显示却不见了则拉回
        self._keep_alive = QTimer(self)
        self._keep_alive.setInterval(3000)
        self._keep_alive.timeout.connect(self._ensure_visible)
        self._should_show = False
        self._keep_alive.start()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 小胶囊
        self.pill = QFrame()
        self.pill.setObjectName("FloatPill")
        pill_l = QHBoxLayout(self.pill)
        pill_l.setContentsMargins(14, 6, 14, 6)
        pill_l.setSpacing(6)
        self.pill_label = QLabel("✎ 记")
        self.pill_label.setObjectName("FloatPillLabel")
        pill_l.addWidget(self.pill_label)
        root.addWidget(self.pill)

        # 展开面板
        self.card = QFrame()
        self.card.setObjectName("FloatingCard")
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(14, 12, 14, 12)
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
        self.input.setMinimumHeight(34)
        self.input.returnPressed.connect(self._save_log)
        log_l.addWidget(self.input)
        self.btn_save_log = QPushButton("记一笔")
        self.btn_save_log.setObjectName("PrimaryBig")
        self.btn_save_log.setMinimumHeight(36)
        self.btn_save_log.clicked.connect(self._save_log)
        log_l.addWidget(self.btn_save_log)
        lay.addWidget(self.log_panel)

        # Bug（更宽更高，现象用多行）
        self.bug_panel = QWidget()
        bug_l = QVBoxLayout(self.bug_panel)
        bug_l.setContentsMargins(0, 0, 0, 0)
        bug_l.setSpacing(6)
        self.bug_title = QLineEdit()
        self.bug_title.setPlaceholderText("Bug 标题（必填）")
        self.bug_title.setMinimumHeight(34)
        self.bug_title.returnPressed.connect(self._focus_bug_symptom)
        bug_l.addWidget(self.bug_title)

        self.bug_symptom = QPlainTextEdit()
        self.bug_symptom.setPlaceholderText("现象 / 报错（可多行，可选）")
        self.bug_symptom.setMinimumHeight(88)
        self.bug_symptom.setMaximumHeight(140)
        bug_l.addWidget(self.bug_symptom)

        self.bug_tags = QLineEdit()
        self.bug_tags.setPlaceholderText("标签，逗号分隔（可选）")
        self.bug_tags.setMinimumHeight(34)
        self.bug_tags.returnPressed.connect(self._save_bug)
        bug_l.addWidget(self.bug_tags)

        self.btn_save_bug = QPushButton("记 Bug")
        self.btn_save_bug.setObjectName("PrimaryBig")
        self.btn_save_bug.setMinimumHeight(36)
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
        self._load_pos()

    def showEvent(self, event) -> None:  # noqa: ANN001
        self._should_show = True
        super().showEvent(event)

    def hideEvent(self, event) -> None:  # noqa: ANN001
        # 用户点 × 会 hide；keep_alive 不会强行弹出
        super().hideEvent(event)

    def set_user_hidden(self, hidden: bool) -> None:
        self._should_show = not hidden

    def _ensure_visible(self) -> None:
        if self._should_show and not self.isVisible():
            self.show()
            self.raise_()
            self.setWindowOpacity(1.0)

    def _load_pos(self) -> None:
        try:
            st = load_ui_state(Path(self._store.data_dir))
            x, y = st.get("float_x"), st.get("float_y")
            if x is not None and y is not None:
                self.move(int(x), int(y))
        except Exception:
            pass

    def _save_pos(self) -> None:
        try:
            st = load_ui_state(Path(self._store.data_dir))
            st["float_x"] = self.x()
            st["float_y"] = self.y()
            save_ui_state(Path(self._store.data_dir), st)
        except Exception:
            pass

    # ---------- 尺寸 ----------

    def _apply_compact_size(self) -> None:
        self.pill.setVisible(True)
        self.card.setVisible(False)
        self.setFixedSize(COMPACT_W, COMPACT_H)
        self.pill_label.setText("✎ 记")
        self.setStyleSheet("FloatingLogWidget { background: #4BA3D9; }")

    def _apply_expand_chrome(self) -> None:
        self.setStyleSheet("FloatingLogWidget { background: #F3F8FC; }")

    def _fixed_expand_size(self) -> tuple[int, int]:
        if self._mode == "bug":
            # 标题+多行现象+标签+按钮+最近
            return EXPANDED_W_BUG, 430
        return EXPANDED_W, 280

    def expand(self, mode: str | None = None) -> None:
        self._collapse_timer.stop()
        self.pill.setVisible(False)
        self.card.setVisible(True)
        self._expanded = True
        if mode:
            self._mode = mode
        self._set_mode(self._mode, resize=False)
        w, h = self._fixed_expand_size()
        self.setFixedSize(w, h)
        self._apply_expand_chrome()
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
        if self._drag_offset is not None:
            self._save_pos()
        self._drag_offset = None
        super().mouseReleaseEvent(event)

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

    def _set_mode(self, mode: str, resize: bool = True) -> None:
        self._mode = mode
        is_log = mode == "log"
        self.log_panel.setVisible(is_log)
        self.bug_panel.setVisible(not is_log)
        self.btn_mode_log.setChecked(is_log)
        self.btn_mode_bug.setChecked(not is_log)
        self.title_lb.setText("随手记" if is_log else "快记 Bug")
        self._refresh_recent()
        if self._expanded and resize:
            w, h = self._fixed_expand_size()
            self.setFixedSize(w, h)

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
            lines = [f"{b.bug_id}  {b.title[:28]}" for b in reversed(bugs)]
            self.recent.setText("最近 Bug：\n" + "\n".join(lines))

    def _flash_ok(self, msg: str) -> None:
        self.title_lb.setText(msg)
        QTimer.singleShot(1200, lambda: self.title_lb.setText("随手记" if self._mode == "log" else "快记 Bug"))

    def _save_log(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self._store.append_log(date.today(), text)
        self.input.clear()
        self._refresh_recent()
        self._flash_ok("✓ 已记流水")
        self.logged.emit(text)
        self.schedule_collapse(1200)

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
        tags = [
            t.strip()
            for t in tags_raw.replace("，", ",").replace("、", ",").split(",")
            if t.strip()
        ]
        bug = self._bug_store.create(
            title=title,
            symptom=self.bug_symptom.toPlainText().strip(),
            tags=tags,
        )
        self.bug_title.clear()
        self.bug_symptom.clear()
        self.bug_tags.clear()
        self._refresh_recent()
        self._flash_ok(f"✓ {bug.bug_id}")
        self.bug_saved.emit(f"{bug.bug_id} {bug.title}")
        # Bug 常需连记多条，不自动收起
