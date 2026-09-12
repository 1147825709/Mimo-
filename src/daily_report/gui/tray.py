"""系统托盘：后台运行、呼出工作台/悬浮窗。"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def make_tray_icon() -> QIcon:
    """画一个简易天蓝圆形图标，避免依赖额外资源。"""
    pix = QPixmap(64, 64)
    pix.fill(QColor(0, 0, 0, 0))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#4BA3D9"))
    p.setPen(QColor("#2F7EB3"))
    p.drawEllipse(4, 4, 56, 56)
    # 简单“记”字色块：用白圆 + 蓝点
    p.setBrush(QColor("#FFFFFF"))
    p.setPen(QColor("#FFFFFF"))
    p.drawEllipse(20, 18, 24, 20)
    p.setBrush(QColor("#E74C3C"))
    p.setPen(QColor("#E74C3C"))
    p.drawEllipse(30, 26, 6, 6)
    p.end()
    return QIcon(pix)


class TrayManager(QObject):
    show_hub_requested = Signal()
    toggle_floating_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tray: QSystemTrayIcon | None = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray = QSystemTrayIcon(make_tray_icon(), parent)
            self._tray.setToolTip("工作台 · 日报随手记")
            menu = QMenu()
            act_hub = QAction("打开工作台", menu)
            act_hub.triggered.connect(self.show_hub_requested.emit)
            act_float = QAction("显示/隐藏 随手记", menu)
            act_float.triggered.connect(self.toggle_floating_requested.emit)
            act_quit = QAction("退出", menu)
            act_quit.triggered.connect(self.quit_requested.emit)
            menu.addAction(act_hub)
            menu.addAction(act_float)
            menu.addSeparator()
            menu.addAction(act_quit)
            self._tray.setContextMenu(menu)
            self._tray.activated.connect(self._on_activated)
            self._tray.show()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_hub_requested.emit()

    def notify(self, title: str, msg: str) -> None:
        if self._tray:
            self._tray.showMessage(title, msg, QSystemTrayIcon.MessageIcon.Information, 2500)

    def available(self) -> bool:
        return self._tray is not None

    def hide(self) -> None:
        if self._tray:
            self._tray.hide()
