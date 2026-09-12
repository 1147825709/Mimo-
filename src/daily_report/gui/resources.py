"""资源路径：兼容源码运行与 PyInstaller 打包。"""

from __future__ import annotations

import sys
from pathlib import Path


def package_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    # resources.py 位于 daily_report/gui/，包根为上一级 daily_report/
    return Path(__file__).resolve().parent.parent


def asset_path(name: str) -> Path:
    candidates = [
        package_root() / "assets" / name,
        package_root().parent.parent / "assets" / name,  # <project>/assets
    ]
    for p in candidates:
        if p.is_file():
            return p
    return candidates[0]


def doraemon_bg_path() -> Path | None:
    p = asset_path("doraemon_bg.png")
    return p if p.is_file() else None
