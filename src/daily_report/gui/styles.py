"""全局圆润主题 QSS。"""

from __future__ import annotations

# 主色：哆啦A梦天蓝；辅：奶油底、圆角卡片
ACCENT = "#4BA3D9"
ACCENT_DARK = "#2F7EB3"
BG = "#F3F8FC"
CARD = "#FFFFFF"
TEXT = "#2C3E50"
MUTED = "#7A8B9A"
DANGER = "#E74C3C"
SUCCESS = "#27AE60"

RADIUS = "14px"
RADIUS_SM = "10px"


def build_qss() -> str:
    return f"""
* {{
    font-family: "Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif;
    color: {TEXT};
    font-size: 10pt;
}}

QMainWindow, QDialog {{
    background: {BG};
}}

QWidget#HubRoot, QWidget#DailyRoot {{
    background: transparent;
}}

QLabel {{
    background: transparent;
    border: none;
}}

QLabel#AppTitle {{
    font-size: 22pt;
    font-weight: 700;
    color: {TEXT};
    padding: 4px 0;
}}

QLabel#AppSubtitle {{
    font-size: 11pt;
    color: {MUTED};
    padding-bottom: 8px;
}}

QLabel#SectionTitle {{
    font-size: 13pt;
    font-weight: 700;
}}

QFrame#FeatureCard {{
    background: rgba(255, 255, 255, 220);
    border: 2px solid #E8F1F8;
    border-radius: {RADIUS};
}}

QFrame#FeatureCard:hover {{
    border: 2px solid {ACCENT};
    background: #FFFFFF;
}}

QFrame#FeatureCard[disabled="true"] {{
    background: rgba(245, 245, 245, 200);
    border: 2px solid #EEE;
}}

QLabel#CardIcon {{
    font-size: 28pt;
}}

QLabel#CardTitle {{
    font-size: 14pt;
    font-weight: 700;
}}

QLabel#CardDesc {{
    font-size: 10pt;
    color: {MUTED};
}}

QPushButton {{
    background: {ACCENT};
    color: white;
    border: none;
    border-radius: {RADIUS_SM};
    padding: 8px 16px;
    font-weight: 600;
    min-height: 28px;
}}

QPushButton:hover {{
    background: {ACCENT_DARK};
}}

QPushButton:pressed {{
    padding-top: 10px;
    padding-bottom: 6px;
}}

QPushButton:disabled {{
    background: #C5D4E0;
    color: #F5F5F5;
}}

QPushButton#PrimaryBig {{
    background: {ACCENT};
    font-size: 12pt;
    padding: 12px 20px;
    border-radius: 16px;
    min-height: 36px;
}}

QPushButton#PrimaryBig:hover {{
    background: {ACCENT_DARK};
}}

QPushButton#Ghost {{
    background: rgba(255,255,255,200);
    color: {TEXT};
    border: 2px solid #D5E4F0;
}}

QPushButton#Ghost:hover {{
    border: 2px solid {ACCENT};
    background: white;
}}

QPushButton#DangerGhost {{
    background: rgba(255,255,255,180);
    color: {DANGER};
    border: 2px solid #F5C6C2;
}}

QPushButton#DangerGhost:hover {{
    background: #FDEDEC;
}}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {{
    background: #FFFFFF;
    border: 2px solid #DCE7F0;
    border-radius: {RADIUS_SM};
    padding: 6px 10px;
    selection-background-color: {ACCENT};
    selection-color: white;
}}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QComboBox:focus, QDateEdit:focus {{
    border: 2px solid {ACCENT};
}}

QListWidget, QTreeView, QTableView {{
    background: rgba(255,255,255,230);
    border: 2px solid #E4EEF6;
    border-radius: {RADIUS_SM};
    padding: 4px;
    outline: none;
}}

QListWidget::item {{
    border-radius: 8px;
    padding: 6px 8px;
    margin: 2px;
}}

QListWidget::item:selected {{
    background: #D6EBF8;
    color: {TEXT};
}}

QListWidget::item:hover {{
    background: #EAF5FC;
}}

QTabWidget::pane {{
    background: rgba(255,255,255,200);
    border: 2px solid #E4EEF6;
    border-radius: {RADIUS};
    top: -1px;
}}

QTabBar::tab {{
    background: rgba(255,255,255,180);
    border: 2px solid #E4EEF6;
    border-bottom: none;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    padding: 8px 18px;
    margin-right: 4px;
    color: {MUTED};
    font-weight: 600;
}}

QTabBar::tab:selected {{
    background: white;
    color: {ACCENT_DARK};
    border-color: {ACCENT};
}}

QStatusBar {{
    background: rgba(255,255,255,160);
    color: {MUTED};
    border-top: 1px solid #E4EEF6;
}}

QMenuBar {{
    background: transparent;
}}

QMenuBar::item:selected {{
    background: #E8F3FB;
    border-radius: 8px;
}}

QMenu {{
    background: white;
    border: 2px solid #E4EEF6;
    border-radius: 10px;
    padding: 6px;
}}

QMenu::item {{
    border-radius: 6px;
    padding: 6px 20px;
}}

QMenu::item:selected {{
    background: #E8F3FB;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: #C5D9E8;
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QFrame#FloatingCard {{
    background: rgba(255,255,255,245);
    border: 2px solid {ACCENT};
    border-radius: 16px;
}}

QFrame#FloatPill {{
    background: {ACCENT};
    border: 2px solid {ACCENT_DARK};
    border-radius: 18px;
}}

QFrame#FloatPill:hover {{
    background: {ACCENT_DARK};
}}

QLabel#FloatPillLabel {{
    color: white;
    font-weight: 700;
    font-size: 11pt;
    background: transparent;
    border: none;
    padding: 0px;
}}

QLabel#FloatTitle {{
    color: {ACCENT_DARK};
    font-weight: 700;
    font-size: 10pt;
}}

QCheckBox, QRadioButton {{
    background: transparent;
    spacing: 6px;
}}

QToolTip {{
    background: #2C3E50;
    color: white;
    border: none;
    padding: 6px 8px;
    border-radius: 6px;
}}
"""
