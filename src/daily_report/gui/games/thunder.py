"""雷霆战机：无尽模式，积分升级武器，随机掉命。"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from PySide6.QtCore import Qt, QTimer, Signal, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QPolygonF
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


@dataclass
class Bullet:
    x: float
    y: float
    vx: float
    vy: float
    dmg: int = 1
    friendly: bool = True


@dataclass
class Enemy:
    x: float
    y: float
    vx: float
    vy: float
    hp: int
    size: float
    kind: str = "basic"  # basic | fast | big


@dataclass
class Pickup:
    x: float
    y: float
    kind: str  # life | weapon


@dataclass
class ThunderState:
    w: int = 420
    h: int = 640
    px: float = 210.0
    py: float = 560.0
    lives: int = 3
    score: int = 0
    weapon: int = 1
    fire_cd: int = 0
    invincible: int = 0
    bullets: list[Bullet] = field(default_factory=list)
    enemies: list[Enemy] = field(default_factory=list)
    pickups: list[Pickup] = field(default_factory=list)
    stars: list[tuple[float, float, float]] = field(default_factory=list)
    over: bool = False
    tick: int = 0
    best: int = 0

    def reset(self) -> None:
        self.px, self.py = self.w / 2, self.h - 70
        self.lives = 3
        self.score = 0
        self.weapon = 1
        self.fire_cd = 0
        self.invincible = 60
        self.bullets.clear()
        self.enemies.clear()
        self.pickups.clear()
        self.over = False
        self.tick = 0
        self.stars = [(random.uniform(0, self.w), random.uniform(0, self.h), random.uniform(0.5, 2.2))
                      for _ in range(40)]

    def weapon_name(self) -> str:
        return {1: "单发", 2: "双发", 3: "三向", 4: "四向+穿透", 5: "五向+速射"}.get(self.weapon, "MAX")

    def upgrade_cost(self) -> int:
        return {1: 100, 2: 250, 3: 500, 4: 900, 5: 1400}.get(self.weapon, 99999)

    def try_upgrade_weapon(self) -> bool:
        """积分达标自动升级。"""
        if self.weapon >= 5:
            return False
        need = {1: 100, 2: 250, 3: 500, 4: 900}.get(self.weapon, 99999)
        if self.score >= need:
            self.weapon += 1
            return True
        return False


class ThunderCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(420, 640)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.state = ThunderState()
        self.state.reset()
        self._keys: set[int] = set()
        self._mouse_x: float | None = None
        self._auto_fire = True

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._step)
        self.timer.start(16)  # ~60fps

        self.score_changed = Signal()  # noqa: N815 — 不用，由外部拉取
        self.on_hud = None  # callable

    def start_game(self) -> None:
        self.state.best = max(self.state.best, self.state.score)
        self.state.reset()
        self._keys.clear()
        self.setFocus()
        self.update()

    def keyPressEvent(self, event) -> None:  # noqa: ANN001
        if event.key() == Qt.Key.Key_Space and self.state.over:
            self.start_game()
            return
        self._keys.add(event.key())
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:  # noqa: ANN001
        self._keys.discard(event.key())
        super().keyReleaseEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: ANN001
        self._mouse_x = event.position().x()
        super().mouseMoveEvent(event)

    # ---------- 逻辑 ----------

    def _step(self) -> None:
        s = self.state
        if s.over:
            self.update()
            if self.on_hud:
                self.on_hud(s)
            return
        s.tick += 1

        # 移动玩家
        speed = 6.5
        dx = dy = 0.0
        if Qt.Key.Key_Left in self._keys or Qt.Key.Key_A in self._keys:
            dx -= speed
        if Qt.Key.Key_Right in self._keys or Qt.Key.Key_D in self._keys:
            dx += speed
        if Qt.Key.Key_Up in self._keys or Qt.Key.Key_W in self._keys:
            dy -= speed
        if Qt.Key.Key_Down in self._keys or Qt.Key.Key_S in self._keys:
            dy += speed
        # 鼠标 X 跟随（可选）
        if self._mouse_x is not None and not (dx or dy):
            s.px += (self._mouse_x - s.px) * 0.15
        s.px = max(20, min(s.w - 20, s.px + dx))
        s.py = max(40, min(s.h - 30, s.py + dy))

        if s.invincible > 0:
            s.invincible -= 1

        # 射击
        s.fire_cd -= 1
        if s.fire_cd <= 0 and self._auto_fire:
            self._fire()
            rate = {1: 14, 2: 12, 3: 10, 4: 8, 5: 6}.get(s.weapon, 6)
            s.fire_cd = rate

        # 武器自动升级
        if s.try_upgrade_weapon():
            pass

        # 敌机生成：随分数加速、加量
        difficulty = 1 + s.score / 200.0
        spawn_chance = min(0.22, 0.04 + s.score / 4000.0)
        if random.random() < spawn_chance:
            self._spawn_enemy(difficulty)

        # 更新子弹
        for b in s.bullets:
            b.x += b.vx
            b.y += b.vy
        s.bullets = [b for b in s.bullets if -20 < b.x < s.w + 20 and -20 < b.y < s.h + 20]

        # 更新敌机
        for e in s.enemies:
            e.x += e.vx
            e.y += e.vy
            # 轻微摆动
            e.vx += math.sin((s.tick + e.x) * 0.05) * 0.03
        s.enemies = [e for e in s.enemies if e.y < s.h + 40 and -40 < e.x < s.w + 40]

        # 道具
        for p in s.pickups:
            p.y += 2.2
        s.pickups = [p for p in s.pickups if p.y < s.h + 20]

        # 子弹 vs 敌机
        for b in s.bullets:
            if not b.friendly:
                continue
            for e in s.enemies:
                if abs(b.x - e.x) < e.size and abs(b.y - e.y) < e.size:
                    e.hp -= b.dmg
                    b.y = -100
                    if e.hp <= 0:
                        s.enemies.remove(e)
                        gain = {"basic": 10, "fast": 15, "big": 30}.get(e.kind, 10)
                        s.score += gain
                        # 随机掉生命 (~6%) 或武器包 (~8%)
                        r = random.random()
                        if r < 0.06:
                            s.pickups.append(Pickup(e.x, e.y, "life"))
                        elif r < 0.14:
                            s.pickups.append(Pickup(e.x, e.y, "weapon"))
                    break

        # 敌机 vs 玩家
        if s.invincible <= 0:
            for e in list(s.enemies):
                if abs(e.x - s.px) < 18 + e.size * 0.6 and abs(e.y - s.py) < 22 + e.size * 0.5:
                    s.lives -= 1
                    s.invincible = 90
                    s.enemies.remove(e)
                    if s.lives <= 0:
                        s.over = True
                        s.best = max(s.best, s.score)
                    break
            # 底部越界撞到也算
            for e in list(s.enemies):
                if e.y > s.h - 10:
                    s.enemies.remove(e)

        # 吃道具
        for p in list(s.pickups):
            if abs(p.x - s.px) < 24 and abs(p.y - s.py) < 24:
                if p.kind == "life":
                    s.lives = min(5, s.lives + 1)
                else:
                    s.score += 30
                    if s.weapon < 5:
                        s.weapon += 1
                s.pickups.remove(p)

        # 星空
        if not s.stars:
            s.stars = [(random.uniform(0, s.w), random.uniform(0, s.h), random.uniform(0.5, 2.2))
                       for _ in range(40)]
        new_stars = []
        for x, y, sp in s.stars:
            y += sp + 1.5
            if y > s.h:
                y = 0
                x = random.uniform(0, s.w)
            new_stars.append((x, y, sp))
        s.stars = new_stars

        if self.on_hud:
            self.on_hud(s)
        self.update()

    def _fire(self) -> None:
        s = self.state
        x, y = s.px, s.py - 18
        dmg = 1 + (s.weapon - 1) // 2
        if s.weapon == 1:
            s.bullets.append(Bullet(x, y, 0, -12, dmg))
        elif s.weapon == 2:
            s.bullets.append(Bullet(x - 8, y, 0, -12, dmg))
            s.bullets.append(Bullet(x + 8, y, 0, -12, dmg))
        elif s.weapon == 3:
            s.bullets.append(Bullet(x, y, 0, -12, dmg))
            s.bullets.append(Bullet(x - 10, y, -2.2, -11, dmg))
            s.bullets.append(Bullet(x + 10, y, 2.2, -11, dmg))
        elif s.weapon == 4:
            for i, vx in enumerate((-3, -1, 1, 3)):
                s.bullets.append(Bullet(x + (i - 1.5) * 7, y, vx, -13, dmg + 1))
        else:
            for vx in (-4, -2, 0, 2, 4):
                s.bullets.append(Bullet(x, y, vx, -14, dmg + 2))

    def _spawn_enemy(self, difficulty: float) -> None:
        s = self.state
        x = random.uniform(30, s.w - 30)
        kind = "basic"
        hp = 1
        size = 14
        vy = 1.6 + difficulty * 0.35
        vx = random.uniform(-0.6, 0.6)
        r = random.random()
        if r < 0.15 + difficulty * 0.01:
            kind = "fast"
            hp = 1
            size = 12
            vy = 2.8 + difficulty * 0.45
            vx = random.uniform(-1.5, 1.5)
        elif r < 0.22 + difficulty * 0.02:
            kind = "big"
            hp = 3 + int(difficulty)
            size = 22
            vy = 1.1 + difficulty * 0.25
        # 限制同屏数量
        max_enemies = min(28, 6 + int(difficulty * 2))
        if len(s.enemies) >= max_enemies:
            return
        s.enemies.append(Enemy(x, -20, vx, vy, hp, size, kind))

    # ---------- 绘制 ----------

    def paintEvent(self, event) -> None:  # noqa: ANN001
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self.state
        # 背景
        p.fillRect(self.rect(), QColor("#0B1026"))
        # 星空
        p.setPen(Qt.PenStyle.NoPen)
        for x, y, sp in s.stars:
            p.setBrush(QColor(180, 200, 255, int(80 + sp * 60)))
            p.drawEllipse(QPointF(x, y), sp, sp)

        # 敌机
        for e in s.enemies:
            col = {"basic": "#E74C3C", "fast": "#F39C12", "big": "#9B59B6"}.get(e.kind, "#E74C3C")
            p.setBrush(QColor(col))
            p.setPen(QPen(QColor("#FFFFFF"), 1))
            poly = QPolygonF(
                [
                    QPointF(e.x, e.y + e.size),
                    QPointF(e.x - e.size * 0.8, e.y - e.size * 0.6),
                    QPointF(e.x + e.size * 0.8, e.y - e.size * 0.6),
                ]
            )
            p.drawPolygon(poly)
            # 血条
            if e.kind == "big" and e.hp > 0:
                p.setBrush(QColor("#2C3E50"))
                p.drawRect(int(e.x - 14), int(e.y - e.size - 8), 28, 4)
                p.setBrush(QColor("#2ECC71"))
                p.drawRect(int(e.x - 14), int(e.y - e.size - 8), int(28 * min(1, e.hp / 6)), 4)

        # 道具
        for pk in s.pickups:
            if pk.kind == "life":
                p.setBrush(QColor("#2ECC71"))
                p.setPen(QPen(QColor("#fff"), 1))
                p.drawEllipse(QPointF(pk.x, pk.y), 10, 10)
                p.setPen(QPen(QColor("#fff"), 2))
                p.drawLine(int(pk.x - 5), int(pk.y), int(pk.x + 5), int(pk.y))
                p.drawLine(int(pk.x), int(pk.y - 5), int(pk.x), int(pk.y + 5))
            else:
                p.setBrush(QColor("#F1C40F"))
                p.setPen(QPen(QColor("#fff"), 1))
                p.drawEllipse(QPointF(pk.x, pk.y), 9, 9)

        # 子弹
        p.setPen(Qt.PenStyle.NoPen)
        for b in s.bullets:
            p.setBrush(QColor("#7FDBFF") if b.friendly else QColor("#FF6B6B"))
            p.drawRect(int(b.x - 2), int(b.y - 6), 4, 12)

        # 玩机
        if not s.over:
            flash = s.invincible > 0 and (s.tick // 4) % 2 == 0
            if not flash:
                p.setBrush(QColor("#4BA3D9"))
                p.setPen(QPen(QColor("#FFFFFF"), 1.5))
                ship = QPolygonF(
                    [
                        QPointF(s.px, s.py - 22),
                        QPointF(s.px - 16, s.py + 16),
                        QPointF(s.px, s.py + 8),
                        QPointF(s.px + 16, s.py + 16),
                    ]
                )
                p.drawPolygon(ship)
                p.setBrush(QColor("#FFE082"))
                p.drawEllipse(QPointF(s.px, s.py - 4), 4, 4)

        # HUD 内嵌
        p.setPen(QColor("#EAF2FF"))
        f = QFont()
        f.setPointSize(11)
        f.setBold(True)
        p.setFont(f)
        p.drawText(12, 28, f"分数 {s.score}")
        p.drawText(12, 48, f"生命 {s.lives}")
        p.drawText(12, 68, f"武器 Lv{s.weapon} {s.weapon_name()}")
        if s.weapon < 5:
            p.drawText(12, 88, f"升级需 {s.upgrade_cost()}")

        if s.over:
            p.fillRect(self.rect(), QColor(0, 0, 0, 140))
            p.setPen(QColor("#FFFFFF"))
            f2 = QFont()
            f2.setPointSize(18)
            f2.setBold(True)
            p.setFont(f2)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "游戏结束")
            f3 = QFont()
            f3.setPointSize(12)
            p.setFont(f3)
            p.drawText(
                self.rect().adjusted(0, 40, 0, 40),
                Qt.AlignmentFlag.AlignCenter,
                f"本局 {s.score} 分  ·  历史 {s.best} 分\n按 空格 重新开始",
            )
        p.end()


class ThunderWindow(QWidget):
    back_to_hub = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("雷霆战机 · 无尽模式")
        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        top = QHBoxLayout()
        btn_back = QPushButton("← 返回知识星球")
        btn_back.setObjectName("Ghost")
        btn_back.clicked.connect(self.back_to_hub.emit)
        btn_restart = QPushButton("重新开始")
        btn_restart.clicked.connect(lambda: self.canvas.start_game())
        tip = QLabel("WASD/方向键移动 · 自动开火 · 随机掉命包 · 积分升级武器")
        tip.setStyleSheet("color:#7A8B9A;")
        top.addWidget(btn_back)
        top.addWidget(btn_restart)
        top.addWidget(tip)
        top.addStretch(1)
        lay.addLayout(top)

        wrap = QHBoxLayout()
        wrap.addStretch(1)
        self.canvas = ThunderCanvas()
        wrap.addWidget(self.canvas)
        wrap.addStretch(1)
        lay.addLayout(wrap, 1)

        self.canvas.setFocus()
