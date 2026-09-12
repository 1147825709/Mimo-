"""本机 API Key 加密/解密（本地混淆，非云端安全存储）。"""

from __future__ import annotations

import base64
import hashlib
import os
import platform
import secrets
from pathlib import Path

PREFIX = "enc:v1:"


def _home_username() -> str:
    home = Path.home().name
    return home or ""


def _env_username() -> str:
    return os.environ.get("USERNAME") or os.environ.get("USER") or ""


def _machine_materials() -> list[bytes]:
    """可能的密钥材料（加密用第一条；解密依次尝试）。

    优先用「主机 + 系统 + 家目录」——与运行账号（SYSTEM/用户）无关，更稳。
    """
    host = platform.node()
    system = platform.system()
    home = str(Path.home())
    users = []
    for u in (_env_username(), _home_username()):
        if u and u not in users:
            users.append(u)
    if not users:
        users = [""]
    mats: list[bytes] = []
    # v2：不含用户名
    mats.append("|".join([host, system, home]).encode("utf-8"))
    # v1：含用户名（兼容旧密文）
    for u in users:
        mats.append("|".join([host, system, u, home]).encode("utf-8"))
    # 去重保序
    seen = set()
    out = []
    for m in mats:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _keystream(key: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hashlib.sha256(key + counter.to_bytes(8, "big")).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def _keys_from_materials() -> list[bytes]:
    return [hashlib.sha256(b"dr-api-key|" + m).digest() for m in _machine_materials()]


def _primary_key() -> bytes:
    return _keys_from_materials()[0]


def _try_decrypt_with(key: bytes, salt: bytes, cipher: bytes) -> str | None:
    try:
        stream = _keystream(key + salt, len(cipher))
        plain = bytes(a ^ b for a, b in zip(cipher, stream))
        text = plain.decode("utf-8")
        # 合理校验：可打印、非空
        if text and all(32 <= ord(c) < 127 for c in text):
            return text
        return None
    except Exception:
        return None


def encrypt_api_key(plain: str) -> str:
    """返回 enc:v1:base64。空串原样返回。"""
    plain = (plain or "").strip()
    if not plain:
        return ""
    if plain.startswith(PREFIX):
        return plain
    raw = plain.encode("utf-8")
    salt = secrets.token_bytes(16)
    stream = _keystream(_primary_key() + salt, len(raw))
    cipher = bytes(a ^ b for a, b in zip(raw, stream))
    blob = salt + cipher
    return PREFIX + base64.urlsafe_b64encode(blob).decode("ascii")


def decrypt_api_key(stored: str) -> str:
    """解密；明文（非 enc: 前缀）原样返回。会尝试多种本机材料。"""
    stored = (stored or "").strip()
    if not stored:
        return ""
    if not stored.startswith(PREFIX):
        return stored
    try:
        blob = base64.urlsafe_b64decode(stored[len(PREFIX) :])
        if len(blob) < 16:
            return ""
        salt, cipher = blob[:16], blob[16:]
        for key in _keys_from_materials():
            text = _try_decrypt_with(key, salt, cipher)
            if text is not None:
                return text
        return ""
    except Exception:
        return ""


def mask_api_key(plain: str) -> str:
    plain = (plain or "").strip()
    if not plain:
        return "（未设置）"
    if len(plain) <= 10:
        return "*" * len(plain)
    return plain[:4] + "…" + plain[-4:]
