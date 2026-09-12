"""知识星球：内容入口。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from daily_report.gui.hub_window import FeatureCard, HubBackground


class GameHubWindow(QWidget):
    back_to_hub = Signal()
    open_minesweeper = Signal()
    open_thunder = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("知识星球")
        self.setMinimumSize(900, 560)
        self._bg = HubBackground(self)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 32, 40, 28)
        lay.setSpacing(16)

        top = QHBoxLayout()
        btn_back = QPushButton("← 返回工作台")
        btn_back.setObjectName("Ghost")
        btn_back.clicked.connect(self.back_to_hub.emit)
        title = QLabel("知识星球")
        title.setObjectName("AppTitle")
        top.addWidget(btn_back)
        top.addWidget(title)
        top.addStretch(1)
        lay.addLayout(top)

        cards = QHBoxLayout()
        cards.setSpacing(18)

        self.card_mine = FeatureCard(
            "扫",
            "扫雷",
            "简单 / 中等 / 困难 · 左键翻开 · 右键插旗 · 数字键快速开局",
            enabled=True,
        )
        self.card_mine.clicked.connect(self.open_minesweeper.emit)
        cards.addWidget(self.card_mine, 1)

        self.card_thunder = FeatureCard(
            "战",
            "雷霆战机",
            "无尽模式 · 积分升级武器 · 随机补给 · 难度递增",
            enabled=True,
        )
        self.card_thunder.clicked.connect(self.open_thunder.emit)
        cards.addWidget(self.card_thunder, 1)

        lay.addLayout(cards, 1)

        tip = QLabel("扫雷：左键翻开，右键插旗；点数字可快速展开周围。战机：WASD/方向键移动，自动开火。")
        tip.setStyleSheet("color:#7A8B9A; background:transparent;")
        lay.addWidget(tip)

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        self._bg.resize(self.size())
        super().resizeEvent(event)
