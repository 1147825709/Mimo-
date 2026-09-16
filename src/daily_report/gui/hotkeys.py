"""Windows 全局热键（RegisterHotKey）。"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
from typing import Callable

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

# 与 PyQt 无关的简易热键管理：独立线程跑消息循环


class HotkeyManager:
    def __init__(self):
        self._thread = None
        self._callbacks: dict[int, Callable[[], None]] = {}
        self._hwnd = None

    def register(self, hotkey_id: int, modifiers: int, vk: int, callback: Callable[[], None]) -> bool:
        self._callbacks[hotkey_id] = callback
        if self._thread is None:
            self._start_thread()
        # 在热键线程里注册
        self._pending_reg = getattr(self, "_pending_reg", [])
        self._pending_reg.append((hotkey_id, modifiers, vk))
        return True

    def unregister_all(self) -> None:
        if self._hwnd and self._thread:
            user32.PostThreadMessageW(self._thread.ident, 0x0012, 0, 0)  # WM_QUIT
            self._thread.join(timeout=2)
            self._thread = None

    def _start_thread(self) -> None:
        import threading

        def run() -> None:
            # 创建消息窗口
            hwnd = user32.CreateWindowExW(
                0, "STATIC", "dr-hotkey", 0, 0, 0, 0, 0, 0, 0, 0, 0
            )
            self._hwnd = hwnd
            # 注册热键
            pending = getattr(self, "_pending_reg", [])
            for hid, mod, vk in pending:
                user32.RegisterHotKey(hwnd, hid, mod | MOD_NOREPEAT, vk)
            msg = wt.MSG()
            while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
                if msg.message == WM_HOTKEY:
                    hid = int(msg.wParam)
                    cb = self._callbacks.get(hid)
                    if cb:
                        try:
                            cb()
                        except Exception:
                            pass
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            for hid, mod, vk in pending:
                user32.UnregisterHotKey(hwnd, hid)
            if hwnd:
                user32.DestroyWindow(hwnd)

        t = threading.Thread(target=run, daemon=True, name="dr-hotkey")
        t.start()
        self._thread = t


# 虚拟键
VK_M = 0x4D
VK_B = 0x42
VK_S = 0x53
