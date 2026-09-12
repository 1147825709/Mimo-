"""经典 Windows 风格扫雷。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from PySide6.QtCore import Qt, QPoint, QRect, QSize, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QPolygon
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

LEVELS = {
    "初级": (9, 9, 10),
    "中级": (16, 16, 40),
    "高级": (30, 16, 99),
}

# Windows 扫雷经典数字色
NUM_COLORS = {
    1: QColor("#0000FF"),
    2: QColor("#008000"),
    3: QColor("#FF0000"),
    4: QColor("#000080"),
    5: QColor("#800000"),
    6: QColor("#008080"),
    7: QColor("#000000"),
    8: QColor("#808080"),
}

CELL = 28
PAD = 12


@dataclass
class Cell:
    mine: bool = False
    revealed: bool = False
    flagged: bool = False
    question: bool = False
    adjacent: int = 0
    exploded: bool = False


@dataclass
class MineBoard:
    rows: int
    cols: int
    mines: int
    grid: list[list[Cell]] = field(default_factory=list)
    started: bool = False
    over: bool = False
    won: bool = False

    def build_empty(self) -> None:
        self.grid = [[Cell() for _ in range(self.cols)] for _ in range(self.rows)]
        self.started = False
        self.over = False
        self.won = False

    def place_mines(self, safe_r: int, safe_c: int) -> None:
        cells = [
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if abs(r - safe_r) > 1 or abs(c - safe_c) > 1  # 首点及周围安全
        ]
        if len(cells) < self.mines:
            cells = [
                (r, c)
                for r in range(self.rows)
                for c in range(self.cols)
                if not (r == safe_r and c == safe_c)
            ]
        random.shuffle(cells)
        for r, c in cells[: self.mines]:
            self.grid[r][c].mine = True
        self._compute_adj()
        self.started = True

    def _compute_adj(self) -> None:
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c].mine:
                    continue
                n = 0
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        rr, cc = r + dr, c + dc
                        if 0 <= rr < self.rows and 0 <= cc < self.cols and self.grid[rr][cc].mine:
                            n += 1
                self.grid[r][c].adjacent = n

    def reveal(self, r: int, c: int) -> None:
        if self.over or not (0 <= r < self.rows and 0 <= c < self.cols):
            return
        cell = self.grid[r][c]
        if cell.revealed or cell.flagged:
            return
        if not self.started:
            self.place_mines(r, c)
        cell.revealed = True
        if cell.mine:
            cell.exploded = True
            self.over = True
            return
        if cell.adjacent == 0:
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr or dc:
                        self.reveal(r + dr, c + dc)
        self._check_win()

    def chord(self, r: int, c: int) -> None:
        """数字键：周围旗数等于数字时翻开其余。"""
        if self.over:
            return
        cell = self.grid[r][c]
        if not cell.revealed or cell.adjacent == 0:
            return
        flags = 0
        neighbors = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                rr, cc = r + dr, c + dc
                if 0 <= rr < self.rows and 0 <= cc < self.cols:
                    n = self.grid[rr][cc]
                    if n.flagged:
                        flags += 1
                    elif not n.revealed:
                        neighbors.append((rr, cc))
        if flags == cell.adjacent:
            for rr, cc in neighbors:
                self.reveal(rr, cc)

    def cycle_flag(self, r: int, c: int) -> None:
        if self.over or not (0 <= r < self.rows and 0 <= c < self.cols):
            return
        cell = self.grid[r][c]
        if cell.revealed:
            return
        if not cell.flagged and not cell.question:
            cell.flagged = True
        elif cell.flagged:
            cell.flagged = False
            cell.question = True
        else:
            cell.question = False

    def _check_win(self) -> None:
        for row in self.grid:
            for cell in row:
                if not cell.mine and not cell.revealed:
                    return
        self.won = True
        self.over = True

    def reveal_all_mines(self) -> None:
        for row in self.grid:
            for cell in row:
                if cell.mine:
                    cell.revealed = True

    def flags_used(self) -> int:
        return sum(1 for row in self.grid for c in row if c.flagged)


class MineCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.board = MineBoard(9, 9, 10)
        self.board.build_empty()
        self.set_board_size()
        self._pressed = False
        self._press_cell: tuple[int, int] | None = None
        self.setMouseTracking(True)

    def set_board(self, rows: int, cols: int, mines: int) -> None:
        self.board = MineBoard(rows, cols, mines)
        self.board.build_empty()
        self.set_board_size()

    def set_board_size(self) -> None:
        w = self.board.cols * CELL + PAD * 2
        h = self.board.rows * CELL + PAD * 2 + 36  # 顶栏
        self.setFixedSize(w, h)

    def new_game(self) -> None:
        self.board.build_empty()
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.size()

    def _cell_at(self, pos) -> tuple[int, int] | None:  # noqa: ANN001
        x = int(pos.x()) - PAD
        y = int(pos.y()) - PAD - 36
        if x < 0 or y < 0:
            return None
        c, r = x // CELL, y // CELL
        if 0 <= r < self.board.rows and 0 <= c < self.board.cols:
            return r, c
        return None

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        rc = self._cell_at(event.position())
        if rc is None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self._press_cell = rc
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self.board.cycle_flag(*rc)
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
        rc = self._cell_at(event.position())
        if event.button() == Qt.MouseButton.LeftButton and self._pressed:
            if rc:
                cell = self.board.grid[rc[0]][rc[1]]
                if cell.revealed:
                    self.board.chord(*rc)
                else:
                    self.board.reveal(*rc)
            self._pressed = False
            self._press_cell = None
            self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: ANN001
        rc = self._cell_at(event.position())
        self._press_cell = rc if self._pressed else None
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        b = self.board

        # 窗口灰底
        p.fillRect(self.rect(), QColor("#C0C0C0"))

        # 顶栏（剩余雷 / 时钟占位用分数风格）
        self._draw_led_panel(p, b)

        # 棋盘外框（凹陷）
        board_rect = QRect(PAD, PAD + 36, b.cols * CELL, b.rows * CELL)
        self._draw_sunken(p, board_rect)

        for r in range(b.rows):
            for c in range(b.cols):
                x = PAD + c * CELL + 3
                y = PAD + 36 + r * CELL + 3
                rect = QRect(x, y, CELL - 4, CELL - 4)
                cell = b.grid[r][c]
                is_press = self._press_cell == (r, c) and not cell.revealed and not b.over
                self._draw_cell(p, rect, cell, b, is_press)

        # 游戏结束覆盖文案
        if b.over:
            p.setPen(QPen(QColor("#000000"), 2))
            f = QFont("Arial", 16, QFont.Weight.Bold)
            p.setFont(f)
            msg = "胜利！" if b.won else "游戏结束"
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, msg)

        p.end()

    def _draw_led_panel(self, p: QPainter, b: MineBoard) -> None:
        # 凹陷面板
        panel = QRect(PAD, PAD, b.cols * CELL, 28)
        p.fillRect(panel, QColor("#C0C0C0"))
        self._draw_sunken(p, panel)

        remain = max(0, b.mines - b.flags_used())
        # 左：雷数 LED
        self._draw_led_number(p, QRect(PAD + 6, PAD + 4, 60, 20), remain)
        # 右：完成度 / 状态
        f = QFont("Courier New", 14, QFont.Weight.Bold)
        p.setFont(f)
        p.setPen(QColor("#FF0000"))
        status = ":-)" if b.won else (":-( " if b.over and not b.won else ":-|")
        # 简化为剩余未开格子提示
        unrevealed = sum(1 for row in b.grid for cell in row if not cell.revealed)
        text = f"{unrevealed:3d}"
        p.drawText(
            QRect(PAD + b.cols * CELL - 70, PAD + 4, 64, 20),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            text,
        )
        # 中间笑脸按钮
        cx = PAD + b.cols * CELL // 2
        face = QRect(cx - 11, PAD + 3, 22, 22)
        self._draw_raised(p, face)
        p.setPen(QColor("#000000"))
        f2 = QFont("Segoe UI Symbol", 10)
        p.setFont(f2)
        emoji = "🙂" if not b.over else ("😎" if b.won else "😵")
        p.drawText(face, Qt.AlignmentFlag.AlignCenter, emoji)

    def _draw_led_number(self, p: QPainter, rect: QRect, n: int) -> None:
        p.fillRect(rect, QColor("#000000"))
        s = f"{n:03d}" if n >= 0 else f"{-n:03d}"
        f = QFont("Courier New", 14, QFont.Weight.Bold)
        p.setFont(f)
        p.setPen(QColor("#FF0000"))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, s)

    def _draw_raised(self, p: QPainter, rect: QRect) -> None:
        p.fillRect(rect, QColor("#C0C0C0"))
        p.setPen(QPen(QColor("#FFFFFF"), 2))
        p.drawLine(rect.topLeft(), rect.topRight())
        p.drawLine(rect.topLeft(), rect.bottomLeft())
        p.setPen(QPen(QColor("#808080"), 1))
        p.drawLine(rect.topRight(), rect.bottomRight())
        p.drawLine(rect.bottomLeft(), rect.bottomRight())

    def _draw_sunken(self, p: QPainter, rect: QRect) -> None:
        p.setPen(QPen(QColor("#808080"), 2))
        p.drawLine(rect.topLeft(), rect.topRight())
        p.drawLine(rect.topLeft(), rect.bottomLeft())
        p.setPen(QPen(QColor("#FFFFFF"), 2))
        p.drawLine(rect.topRight(), rect.bottomRight())
        p.drawLine(rect.bottomLeft(), rect.bottomRight())

    def _draw_cell(self, p: QPainter, rect: QRect, cell: Cell, board: MineBoard, pressed: bool) -> None:
        if cell.revealed:
            # 已翻开：扁平 + 细边框
            if cell.exploded:
                p.fillRect(rect, QColor("#FF0000"))
            else:
                p.fillRect(rect, QColor("#C0C0C0"))
            p.setPen(QPen(QColor("#808080"), 1))
            p.drawRect(rect)
            if cell.mine:
                self._draw_mine(p, rect)
            elif cell.adjacent:
                p.setFont(QFont("Arial", 12, QFont.Weight.Bold))
                p.setPen(NUM_COLORS[cell.adjacent])
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(cell.adjacent))
        else:
            if pressed:
                # 按下扁平
                p.fillRect(rect, QColor("#C0C0C0"))
                p.setPen(QPen(QColor("#808080"), 1))
                p.drawRect(rect)
            else:
                self._draw_raised(p, rect)
            if cell.flagged:
                self._draw_flag(p, rect)
            elif cell.question:
                p.setFont(QFont("Arial", 12, QFont.Weight.Bold))
                p.setPen(QColor("#000000"))
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "?")

    def _draw_mine(self, p: QPainter, rect: QRect) -> None:
        cx, cy = rect.center().x(), rect.center().y()
        p.setBrush(QBrush(QColor("#000000")))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(cx - 6), int(cy - 6), 12, 12)
        p.setPen(QPen(QColor("#000000"), 2))
        p.drawLine(int(cx - 8), int(cy), int(cx + 8), int(cy))
        p.drawLine(int(cx), int(cy - 8), int(cx), int(cy + 8))
        p.drawLine(int(cx - 5), int(cy - 5), int(cx + 5), int(cy + 5))
        p.drawLine(int(cx - 5), int(cy + 5), int(cx + 5), int(cy - 5))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(int(cx - 3), int(cy - 3), 3, 3)

    def _draw_flag(self, p: QPainter, rect: QRect) -> None:
        cx = rect.center().x()
        # 旗杆
        p.setPen(QPen(QColor("#000000"), 2))
        p.drawLine(int(cx), int(rect.top() + 6), int(cx), int(rect.bottom() - 6))
        # 旗面
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FF0000"))
        p.drawPolygon(
            QPolygon(
                [
                    rect.topLeft(),
                    rect.topLeft() + QPoint(10, 4),
                    rect.topLeft() + QPoint(0, 8),
                ]
            )
        )
        # 底座
        p.setBrush(QColor("#000000"))
        p.drawRect(int(cx - 5), int(rect.bottom() - 7), 10, 2)


class MinesweeperWindow(QWidget):
    back_to_hub = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("扫雷")
        self._build_ui()
        self._new_level("初级")

    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        top = QHBoxLayout()
        btn_back = QPushButton("← 返回知识星球")
        btn_back.setObjectName("Ghost")
        btn_back.clicked.connect(self.back_to_hub.emit)
        self.level_box = QComboBox()
        self.level_box.addItems(list(LEVELS.keys()))
        self.level_box.currentTextChanged.connect(self._new_level)
        self.btn_new = QPushButton("开局")
        self.btn_new.clicked.connect(lambda: self._new_level(self.level_box.currentText()))
        self.lbl_info = QLabel("")
        top.addWidget(btn_back)
        top.addWidget(QLabel("难度"))
        top.addWidget(self.level_box)
        top.addWidget(self.btn_new)
        top.addStretch(1)
        top.addWidget(self.lbl_info)
        lay.addLayout(top)

        center = QHBoxLayout()
        center.addStretch(1)
        self.canvas = MineCanvas()
        center.addWidget(self.canvas)
        center.addStretch(1)
        lay.addLayout(center, 1)

        tip = QLabel("左键翻开 · 右键 旗→?→取消 · 点数字可快速展开周围 · 首次点击保证安全")
        tip.setStyleSheet("color:#7A8B9A;")
        lay.addWidget(tip)

        # 监听棋盘状态更新信息栏（简单轮询式：在画完后由外部刷）
        self._info_timer = None
        from PySide6.QtCore import QTimer

        self._info_timer = QTimer(self)
        self._info_timer.timeout.connect(self._refresh_info)
        self._info_timer.start(400)
        self._refresh_info()

    def _new_level(self, level: str) -> None:
        rows, cols, mines = LEVELS.get(level, LEVELS["初级"])
        self.canvas.set_board(rows, cols, mines)
        self.canvas.update()
        self._refresh_info()

    def _refresh_info(self) -> None:
        b = self.canvas.board
        remain = max(0, b.mines - b.flags_used())
        if b.won:
            state = "胜利"
        elif b.over:
            state = "失败"
        elif not b.started:
            state = "等待首次点击"
        else:
            state = "进行中"
        self.lbl_info.setText(f"剩余雷数 {remain}  ·  {state}")

    def closeEvent(self, event) -> None:  # noqa: ANN001
        if self._info_timer:
            self._info_timer.stop()
        super().closeEvent(event)
