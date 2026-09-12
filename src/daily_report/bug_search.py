"""Bug 关键词检索与「相近 bug」打分。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from daily_report.bugs import BugRecord


@dataclass
class BugHit:
    bug: BugRecord
    score: float
    reasons: list[str]


_TOKEN_RE = re.compile(r"[一-鿿A-Za-z0-9_]+")


def _tokens(text: str) -> set[str]:
    """中文按单字+双字，英文数字按词。"""
    text = text or ""
    found: set[str] = set()
    for m in _TOKEN_RE.finditer(text):
        w = m.group(0)
        if re.fullmatch(r"[一-鿿]+", w):
            chars = list(w)
            found.update(chars)
            found.update(w[i : i + 2] for i in range(len(chars) - 1))
        else:
            found.add(w.lower())
    return found


def similarity_score(a: BugRecord, b: BugRecord) -> tuple[float, list[str]]:
    """返回 (0~1 相似度, 命中原因)。"""
    reasons: list[str] = []
    score = 0.0

    # 标签重叠权重高
    ta, tb = set(a.tags), set(b.tags)
    if ta and tb:
        inter = ta & tb
        if inter:
            score += 0.35 * (len(inter) / max(len(ta), len(tb)))
            reasons.append(f"共同标签: {'、'.join(sorted(inter))}")

    # 标题 token
    ta_t, tb_t = _tokens(a.title), _tokens(b.title)
    if ta_t and tb_t:
        j = len(ta_t & tb_t) / len(ta_t | tb_t)
        score += 0.30 * j
        if j >= 0.25:
            reasons.append("标题相近")

    # 全文 token（现象/错误/方案）
    fa, fb = _tokens(a.full_text()), _tokens(b.full_text())
    if fa and fb:
        j = len(fa & fb) / len(fa | fb)
        score += 0.35 * j
        if j >= 0.12:
            reasons.append(f"正文重叠 {j:.0%}")

    # 错误信息直接子串/关键词
    if a.error_info and b.error_info:
        ea = a.error_info.strip().lower()
        eb = b.error_info.strip().lower()
        # 取最长公共行或关键错误码
        for line in {x.strip().lower() for x in a.error_info.splitlines() if x.strip()}:
            if len(line) >= 8 and line in eb:
                reasons.append("错误信息相似")
                score += 0.2
                break

    return min(score, 1.0), reasons


def find_similar(
    query: BugRecord | str,
    bugs: list[BugRecord],
    exclude_id: str | None = None,
    top_k: int = 5,
    min_score: float = 0.12,
) -> list[BugHit]:
    if isinstance(query, str):
        probe = BugRecord(bug_id="__query__", title=query, symptom=query)
    else:
        probe = query

    hits: list[BugHit] = []
    for b in bugs:
        if exclude_id and b.bug_id == exclude_id:
            continue
        sc, reasons = similarity_score(probe, b)
        if sc >= min_score:
            hits.append(BugHit(bug=b, score=sc, reasons=reasons))
    hits.sort(key=lambda h: -h.score)
    return hits[:top_k]


def search_bugs(
    bugs: list[BugRecord],
    keywords: list[str],
) -> list[BugRecord]:
    """多关键词 AND，匹配标题/标签/正文。"""
    if not keywords:
        return []
    keys = [k.lower() for k in keywords if k.strip()]
    out = []
    for b in bugs:
        hay = b.full_text().lower()
        if all(k in hay for k in keys):
            out.append(b)
    return out
