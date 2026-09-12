"""首页：大功能入口（日报记录等）。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from daily_report.config import Config
from daily_report.gui.resources import doraemon_bg_path
from daily_report.storage import ReportStore


def _apply_shadow(widget: QWidget, blur: int = 28, y: int = 8) -> None:
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, y)
    eff.setColor(Qt.GlobalColor.black)
    # 浅阴影
    from PySide6.QtGui import QColor

    eff.setColor(QColor(47, 126, 179, 50))
    widget.setGraphicsEffect(eff)


class FeatureCard(QFrame):
    clicked = Signal()

    def __init__(
        self,
        icon: str,
        title: str,
        desc: str,
        enabled: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("FeatureCard")
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor
        )
        self.setEnabled(enabled)
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(6)

        icon_lb = QLabel(icon)
        icon_lb.setObjectName("CardIcon")
        icon_lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lb.setStyleSheet(
            "font-size:18pt; font-weight:700; color:#2F7EB3; "
            "background:#E8F4FB; border-radius:14px;"
        )
        icon_lb.setFixedSize(48, 48)
        title_lb = QLabel(title)
        title_lb.setObjectName("CardTitle")
        desc_lb = QLabel(desc)
        desc_lb.setObjectName("CardDesc")
        desc_lb.setWordWrap(True)

        lay.addWidget(icon_lb)
        lay.addWidget(title_lb)
        lay.addWidget(desc_lb)
        lay.addStretch(1)

        if not enabled:
            badge = QLabel("敬请期待")
            badge.setStyleSheet(
                "color:#98A4B0; background:#EEF2F5; border-radius:8px;"
                "padding:2px 8px; font-size:9pt; align-self:flex-start;"
            )
            row = QHBoxLayout()
            row.addWidget(badge)
            row.addStretch(1)
            lay.addLayout(row)

        _apply_shadow(self)

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if self.isEnabled():
            self.clicked.emit()
        super().mousePressEvent(event)


class HubBackground(QWidget):
    """铺底背景图（弱化），供首页使用。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HubRoot")
        self._pix: QPixmap | None = None
        path = doraemon_bg_path()
        if path and path.is_file():
            self._pix = QPixmap(str(path))

    def paintEvent(self, event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.white)
        if self._pix and not self._pix.isNull():
            # 覆盖缩放，整体压淡
            scaled = self._pix.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            # 居中裁切
            x = (scaled.width() - self.width()) // 2
            y = (scaled.height() - self.height()) // 2
            painter.setOpacity(0.55)
            painter.drawPixmap(-x, -y, scaled)
            painter.setOpacity(1.0)
            # 左侧加一层奶油色渐隐，方便放文字
            from PySide6.QtGui import QColor, QLinearGradient

            grad = QLinearGradient(0, 0, self.width(), 0)
            grad.setColorAt(0.0, QColor(243, 248, 252, 230))
            grad.setColorAt(0.55, QColor(243, 248, 252, 120))
            grad.setColorAt(1.0, QColor(243, 248, 252, 0))
            painter.fillRect(self.rect(), grad)
        painter.end()


class HubWindow(QWidget):
    """应用首页：大功能入口。"""

    open_daily = Signal()
    open_bugs = Signal()
    open_tasks = Signal()
    open_games = Signal()
    open_settings = Signal()
    toggle_floating = Signal()
    open_data_dir = Signal()

    def __init__(self, cfg: Config, store: ReportStore, parent=None):
        super().__init__(parent)
        self._cfg = cfg
        self._store = store
        self.setWindowTitle("工作台")
        self.setMinimumSize(960, 620)

        self._bg = HubBackground(self)

        overlay = QVBoxLayout(self)
        overlay.setContentsMargins(40, 36, 40, 28)
        overlay.setSpacing(16)

        # 标题区
        head = QVBoxLayout()
        title = QLabel("工作台")
        title.setObjectName("AppTitle")
        sub = QLabel("把工作记下来，AI 帮你成稿 · 更多大功能持续加入")
        sub.setObjectName("AppSubtitle")
        head.addWidget(title)
        head.addWidget(sub)
        overlay.addLayout(head)

        # 功能卡片区
        cards = QHBoxLayout()
        cards.setSpacing(18)

        self.card_daily = FeatureCard(
            "日",
            "日报记录",
            "随手记流水 · AI 一键成稿 · 周报月报 · 关键词搜索",
            enabled=True,
        )
        self.card_daily.clicked.connect(self.open_daily.emit)
        cards.addWidget(self.card_daily, 3)

        self.card_bugs = FeatureCard(
            "B",
            "Bug 列表",
            "记录现象/根因/方案 · 关键词检索 · 搜索相近历史 Bug",
            enabled=True,
        )
        self.card_bugs.clicked.connect(self.open_bugs.emit)
        cards.addWidget(self.card_bugs, 3)

        self.card_todo = FeatureCard(
            "划",
            "任务计划",
            "设定截止日期 · AI 拆分子任务 · 进度与剩余时间",
            enabled=True,
        )
        self.card_todo.clicked.connect(self.open_tasks.emit)
        cards.addWidget(self.card_todo, 2)

        self.card_know = FeatureCard(
            "星",
            "知识星球",
            "经典小游戏 · 扫雷 · 雷霆战机",
            enabled=True,
        )
        self.card_know.clicked.connect(self.open_games.emit)
        cards.addWidget(self.card_know, 2)

        overlay.addLayout(cards, 1)

        # 底部快捷操作
        foot = QHBoxLayout()
        self.btn_float = QPushButton("悬浮随手记")
        self.btn_float.setObjectName("Ghost")
        self.btn_float.clicked.connect(self.toggle_floating.emit)
        self.btn_settings = QPushButton("模型设置")
        self.btn_settings.setObjectName("Ghost")
        self.btn_settings.clicked.connect(self.open_settings.emit)
        self.btn_data = QPushButton("打开数据目录")
        self.btn_data.setObjectName("Ghost")
        self.btn_data.clicked.connect(self.open_data_dir.emit)

        model_hint = QLabel("")
        model_hint.setObjectName("ModelHint")
        model_hint.setStyleSheet("color:#7A8B9A; background:transparent;")
        self._model_hint = model_hint
        self._refresh_model_hint()

        foot.addWidget(self.btn_float)
        foot.addWidget(self.btn_settings)
        foot.addWidget(self.btn_data)
        foot.addStretch(1)
        foot.addWidget(model_hint)
        overlay.addLayout(foot)

        # 提示
        tip = QLabel("提示：点卡片进入对应功能；右下角小胶囊「✎ 记」点击展开随手记/记 Bug，主界面关掉后仍可从托盘呼出。")
        tip.setStyleSheet("color:#7A8B9A; background:transparent;")
        overlay.addWidget(tip)

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        self._bg.resize(self.size())
        super().resizeEvent(event)

    def set_store(self, store: ReportStore) -> None:
        self._store = store

    def _refresh_model_hint(self) -> None:
        if not hasattr(self, "_model_hint"):
            return
        if self._cfg.is_ai:
            ready = "已配置" if self._cfg.llm_ready() else "未配置 API"
            self._model_hint.setText(
                f"AI 版 · {self._cfg.active_api}/{self._cfg.llm.model}（{ready}）"
            )
        else:
            self._model_hint.setText("非 AI 版 · 总结需手写")

    def set_config(self, cfg: Config) -> None:
        self._cfg = cfg
        self._refresh_model_hint()
