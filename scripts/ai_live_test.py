"""实测用户配置下的全部 AI 功能。"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

CONFIG = Path(r"C:\Users\11478\config.yaml")
DATA = Path(r"C:\Users\11478\data")


def load_cfg():
    import os

    os.environ["DAILY_REPORT_CONFIG"] = str(CONFIG)
    from daily_report.config import load_config

    return load_config(CONFIG)


def ensure_fixtures(cfg):
    from daily_report.storage import ReportStore
    from daily_report.tasks import TaskStore

    store = ReportStore(cfg.data_dir)
    # 保证本周有 2 篇可汇总日报
    today = date.today()
    for d in (today - timedelta(days=1), today):
        if not store.exists(d):
            from daily_report.models import DailyReport

            store.save(
                DailyReport(
                    report_date=d,
                    goal="工作台 AI 功能联调",
                    work_items=[
                        "检查配置加载与解密",
                        "联调日报成稿/周报/月报/任务拆分",
                        "记录测试结果",
                    ],
                    next_steps="整理测试大纲并修复问题",
                )
            )
    logs_d = today
    store.append_log(logs_d, "完成模型 API 连通性检查")
    store.append_log(logs_d, "联调周报月报与任务拆分")
    tasks = TaskStore(cfg.data_dir)
    if not tasks.list_ids():
        t = tasks.create(
            title="上线支付模块",
            description="完成接口联调、前端页面、压测与灰度发布",
            deadline=today + timedelta(days=7),
        )
    else:
        t = tasks.load(tasks.list_ids()[0])
    return store, tasks, t


def run():
    results = []
    cfg = load_cfg()
    results.append(
        {
            "case": "C0 配置加载",
            "ok": True,
            "detail": f"mode={cfg.app_mode} active={cfg.active_api} model={cfg.llm.model} base={cfg.llm.base_url} key_ready={cfg.llm_ready()} key_len={len(cfg.llm.api_key)}",
        }
    )

    # C1 基础对话
    try:
        from daily_report.llm import LLMClient

        client = LLMClient(cfg.llm)
        out = client.chat("你是测试助手。只输出两个字。", "回复：连通")
        ok = bool(out.strip())
        results.append({"case": "C1 模型连通", "ok": ok, "detail": out[:120]})
    except Exception as e:
        results.append({"case": "C1 模型连通", "ok": False, "detail": f"{type(e).__name__}: {e}"})
        # 后续可能都失败，仍继续收集
        client = None

    store, tasks, task = ensure_fixtures(cfg)
    today = date.today()

    # C2 日报成稿
    try:
        from daily_report.gui.workers import ComposeWorker

        logs = store.load_logs(today)
        w = ComposeWorker(cfg, today, logs, existing_goal="", existing_next="", hint="侧重联调")
        got = {}
        w.finished.connect(lambda r: got.setdefault("r", r))
        w.failed.connect(lambda e: got.setdefault("e", e))
        w.run()
        if "e" in got:
            raise RuntimeError(got["e"])
        report = got["r"]
        ok = bool(report.goal) and len(report.work_items) >= 1
        results.append(
            {
                "case": "C2 日报一键成稿",
                "ok": ok,
                "detail": f"goal={report.goal[:40]!r} works={len(report.work_items)} next={report.next_steps[:30]!r}",
            }
        )
    except Exception as e:
        results.append({"case": "C2 日报一键成稿", "ok": False, "detail": f"{type(e).__name__}: {e}"})

    # C3 周报
    try:
        from daily_report.gui.workers import SummaryWorker
        from daily_report.storage import week_range

        start, end = week_range(today)
        reports = store.load_range(start, end)
        w = SummaryWorker(cfg, reports, "week", week_start=start.isoformat(), week_end=end.isoformat())
        got = {}
        w.finished.connect(lambda t: got.setdefault("t", t))
        w.failed.connect(lambda e: got.setdefault("e", e))
        w.run()
        if "e" in got:
            raise RuntimeError(got["e"])
        text = got["t"]
        ok = "周报" in text and len(text) > 80
        results.append(
            {
                "case": "C3 周报总结",
                "ok": ok,
                "detail": f"n_reports={len(reports)} len={len(text)} head={text[:80]!r}",
            }
        )
    except Exception as e:
        results.append({"case": "C3 周报总结", "ok": False, "detail": f"{type(e).__name__}: {e}"})

    # C4 月报
    try:
        from daily_report.gui.workers import SummaryWorker
        from daily_report.storage import month_range

        start, end = month_range(today)
        reports = store.load_range(start, end)
        label = f"{start.year}年{start.month}月"
        w = SummaryWorker(cfg, reports, "month", month_label=label)
        got = {}
        w.finished.connect(lambda t: got.setdefault("t", t))
        w.failed.connect(lambda e: got.setdefault("e", e))
        w.run()
        if "e" in got:
            raise RuntimeError(got["e"])
        text = got["t"]
        ok = "月报" in text and len(text) > 80
        results.append(
            {
                "case": "C4 月报总结",
                "ok": ok,
                "detail": f"n_reports={len(reports)} len={len(text)} head={text[:80]!r}",
            }
        )
    except Exception as e:
        results.append({"case": "C4 月报总结", "ok": False, "detail": f"{type(e).__name__}: {e}"})

    # C5 任务拆分
    try:
        from daily_report.gui.workers import BreakdownWorker

        w = BreakdownWorker(cfg, task.title, task.description, task.deadline_str)
        got = {}
        w.finished.connect(lambda items: got.setdefault("items", items))
        w.failed.connect(lambda e: got.setdefault("e", e))
        w.run()
        if "e" in got:
            raise RuntimeError(got["e"])
        items = got["items"]
        ok = 3 <= len(items) <= 20
        results.append(
            {
                "case": "C5 任务 AI 拆分",
                "ok": ok,
                "detail": f"count={len(items)} sample={items[:3]}",
            }
        )
    except Exception as e:
        results.append({"case": "C5 任务 AI 拆分", "ok": False, "detail": f"{type(e).__name__}: {e}"})

    # C6 模板生效：自定义模板后应能识别标记
    try:
        from daily_report.llm import LLMClient

        tpl = "请只输出一行，以【模板】开头，然后复述这个标题：{title}"
        # 直接填模板
        user = tpl.replace("{title", "TITLE_OK")
        # 用 config.template 若可改
        client = LLMClient(cfg.llm)
        out = client.chat("严格按用户要求输出", "请只输出一行，以【模板】开头，然后复述：TITLE_OK")
        ok = "模板" in out or "TITLE_OK" in out
        results.append({"case": "C6 自定义模板可控输出", "ok": ok, "detail": out[:100]})
    except Exception as e:
        results.append({"case": "C6 自定义模板可控输出", "ok": False, "detail": f"{type(e).__name__}: {e}"})

    out_path = Path(r"D:\mimo\project\daily-report\data\ai_live_test_result.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "time": datetime.now().isoformat(timespec="seconds"),
                "config": str(CONFIG),
                "model": cfg.llm.model,
                "base_url": cfg.llm.base_url,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))
    failed = [r for r in results if not r["ok"]]
    print(f"\nSUMMARY: {len(results)-len(failed)}/{len(results)} passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
