"""daily-report 命令行入口。"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from daily_report.config import Config, find_config_file, load_config, write_default_config
from daily_report.models import DailyReport, parse_work_items
from daily_report.search import filter_by_date, search_reports
from daily_report.storage import ReportStore, month_range, week_range


def _parse_date(s: str | None) -> date:
    if not s:
        return date.today()
    return date.fromisoformat(s)


def _load_ctx(args: argparse.Namespace) -> tuple[Config, ReportStore]:
    cfg = load_config(getattr(args, "config", None))
    store = ReportStore(cfg.data_dir)
    return cfg, store


def _print_ok(msg: str) -> None:
    print(f"✓ {msg}")


def _print_info(msg: str) -> None:
    print(msg)


def cmd_init(args: argparse.Namespace) -> int:
    dest = Path(args.config or "config.yaml").expanduser()
    if dest.exists() and not args.force:
        print(f"配置已存在: {dest}（使用 --force 覆盖）")
        return 1
    mode = getattr(args, "mode", "ai") or "ai"
    path = write_default_config(dest, mode=mode)
    _print_ok(f"已写入配置: {path}（模式: {mode}）")
    if mode == "ai":
        _print_info("请编辑 llm.api_key / llm.base_url / llm.model；templates 段可改 AI 提示词。")
    else:
        _print_info("非 AI 版：周报/月报/日报成稿请手写，无需 API。")
    data_dir = path.parent / "data"
    ReportStore(data_dir)
    _print_ok(f"数据目录: {data_dir}")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    path = find_config_file(getattr(args, "config", None))
    cfg = load_config(getattr(args, "config", None))
    _print_info(f"配置文件: {path or '（未找到，使用默认/环境变量）'}")
    _print_info(f"Base URL:  {cfg.llm.base_url}")
    _print_info(f"Model:     {cfg.llm.model}")
    key = cfg.llm.api_key
    masked = (key[:6] + "..." + key[-4:]) if len(key) > 12 else ("已设置" if key else "未设置")
    _print_info(f"API Key:   {masked}")
    _print_info(f"数据目录:  {cfg.data_dir}")
    return 0


def cmd_gui(args: argparse.Namespace) -> int:
    from daily_report.gui.app import main as gui_main

    # 把 --config 传给 GUI（通过环境约定：load_config 已读 --config）
    argv = ["daily-report-gui"]
    if getattr(args, "config", None):
        import os

        os.environ["DAILY_REPORT_CONFIG"] = str(args.config)
    return gui_main(argv)


def _prompt_multiline(label: str, initial: str = "") -> str:
    print(f"{label}（输入完成后以单独一行 END 结束）:")
    if initial:
        print("--- 当前内容 ---")
        print(initial)
        print("--- 输入新内容覆盖，直接 END 可保留 ---")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        lines.append(line)
    text = "\n".join(lines).strip()
    if not text and initial:
        return initial
    return text


def cmd_add(args: argparse.Namespace) -> int:
    _, store = _load_ctx(args)
    d = _parse_date(args.date)
    report = store.load_or_create(d)

    if args.goal is not None:
        report.goal = args.goal
    if args.work is not None:
        report.work_items = parse_work_items(args.work)
    if args.next is not None:
        report.next_steps = args.next

    if args.interactive or (args.goal is None and args.work is None and args.next is None):
        print(f"填写日报 {report.date_str}（直接回车跳过已有字段则保留原值）")
        if not args.goal:
            report.goal = _prompt_multiline("任务目标", report.goal)
        if not args.work:
            print("具体工作（每条一行，END 结束；可用 | 分隔多条）:")
            if report.work_items:
                print("--- 当前 ---")
                for i, w in enumerate(report.work_items, 1):
                    print(f"{i}. {w}")
                print("--- 输入新内容覆盖 ---")
            lines: list[str] = []
            while True:
                try:
                    line = input()
                except EOFError:
                    break
                if line.strip() == "END":
                    break
                if line.strip():
                    lines.append(line.strip())
            if lines:
                items: list[str] = []
                for line in lines:
                    items.extend(parse_work_items(line))
                report.work_items = items
        if not args.next:
            report.next_steps = _prompt_multiline("下一步计划", report.next_steps)

    path = store.save(report)
    _print_ok(f"已保存日报 {report.date_str}: {path}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    _, store = _load_ctx(args)
    d = _parse_date(args.date)
    report = store.load(d)
    if not report:
        print(f"未找到 {d.isoformat()} 的日报。可用 `daily-report add --date {d.isoformat()}` 创建。")
        return 1
    print(report.to_markdown())
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    _, store = _load_ctx(args)
    d = _parse_date(args.date)
    texts = args.text if isinstance(args.text, list) else [args.text]
    joined = " ".join(t for t in texts if t).strip()
    if not joined:
        print("请提供流水内容，例如：daily-report log 修复了登录超时")
        return 1
    entry = store.append_log(d, joined)
    _print_ok(f"已记一笔 [{d.isoformat()} {entry.time_str}] {entry.text}")
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    _, store = _load_ctx(args)
    d = _parse_date(args.date)
    entries = store.load_logs(d)
    if not entries:
        print(f"{d.isoformat()} 暂无工作流水。")
        return 0
    print(f"{d.isoformat()} 工作流水（{len(entries)} 条）：")
    for i, e in enumerate(entries, 1):
        print(f"  {i}. [{e.time_str}] {e.text}")
    return 0


def cmd_compose(args: argparse.Namespace) -> int:
    from daily_report.llm import LLMClient
    from daily_report.prompts import SYSTEM_DAILY_COMPOSE, daily_compose_prompt

    cfg, store = _load_ctx(args)
    d = _parse_date(args.date)
    logs = store.load_logs(d)
    report = store.load_or_create(d)

    if not logs and not report.goal.strip():
        print("当天没有流水，也没有已有目标。请先 `daily-report log ...` 记几条。")
        return 1

    print(f"正在调用 {cfg.llm.model} 根据 {len(logs)} 条流水生成日报…")
    client = LLMClient(cfg.llm)
    prompt = daily_compose_prompt(
        d.isoformat(),
        logs,
        existing_goal=report.goal,
        existing_next=report.next_steps,
        hint=args.hint or "",
    )
    text = client.chat(SYSTEM_DAILY_COMPOSE, prompt)

    from daily_report.prompts import parse_daily_report

    draft = parse_daily_report(text, d)

    if args.draft:
        draft_dir = store.data_dir / "drafts"
        draft_dir.mkdir(parents=True, exist_ok=True)
        path = draft_dir / f"{d.isoformat()}.md"
        path.write_text(draft.to_markdown(), encoding="utf-8")
        _print_ok(f"已保存草稿: {path}")
    else:
        # 合并：若已有手工内容且 --keep-manual，则不覆盖已有字段
        if args.keep_manual:
            if report.goal.strip():
                draft.goal = report.goal
            if report.work_items:
                draft.work_items = report.work_items
            if report.next_steps.strip():
                draft.next_steps = report.next_steps
        path = store.save(draft)
        _print_ok(f"已保存日报: {path}")

    print()
    print(draft.to_markdown())
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    _, store = _load_ctx(args)
    start = end = None
    if args.month:
        anchor = date.fromisoformat(f"{args.month}-01")
        start, end = month_range(anchor)
    if args.start:
        start = date.fromisoformat(args.start)
    if args.end:
        end = date.fromisoformat(args.end)
    dates = store.list_dates(start, end)
    if not dates:
        print("暂无日报记录。")
        return 0
    print(f"共 {len(dates)} 篇日报：")
    for d in dates:
        r = store.load(d)
        goal_first = (r.goal.splitlines()[0] if r and r.goal else "").strip()
        if len(goal_first) > 40:
            goal_first = goal_first[:40] + "…"
        print(f"  {d.isoformat()}  {goal_first}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    _, store = _load_ctx(args)
    d = _parse_date(args.date)
    if not args.yes:
        ans = input(f"确认删除 {d.isoformat()} 的日报？[y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("已取消。")
            return 0
    if store.delete(d):
        _print_ok(f"已删除 {d.isoformat()}")
        return 0
    print(f"未找到 {d.isoformat()} 的日报。")
    return 1


def _summarize(cfg: Config, store: ReportStore, reports: list[DailyReport], user_prompt: str, out_path: Path) -> int:
    if not reports:
        print("该时间范围内没有日报，无法生成总结。")
        return 1
    from daily_report.llm import LLMClient
    from daily_report.prompts import SYSTEM_SUMMARY

    print(f"正在调用模型 {cfg.llm.model} 汇总 {len(reports)} 篇日报…")
    client = LLMClient(cfg.llm)
    summary = client.chat(SYSTEM_SUMMARY, user_prompt)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(summary + "\n", encoding="utf-8")
    _print_ok(f"已保存总结: {out_path}")
    print()
    print(summary)
    return 0


def cmd_week(args: argparse.Namespace) -> int:
    from daily_report.prompts import weekly_prompt

    cfg, store = _load_ctx(args)
    anchor = _parse_date(args.date)
    start, end = week_range(anchor)
    reports = store.load_range(start, end)
    label = f"{start.isoformat()} ~ {end.isoformat()}"
    out = store.summaries_dir / f"week_{start.isoformat()}.md"
    prompt = weekly_prompt(reports, start.isoformat(), end.isoformat())
    return _summarize(cfg, store, reports, prompt, out)


def cmd_month(args: argparse.Namespace) -> int:
    from daily_report.prompts import monthly_prompt

    cfg, store = _load_ctx(args)
    if args.month:
        anchor = date.fromisoformat(f"{args.month}-01")
    else:
        anchor = _parse_date(args.date)
    start, end = month_range(anchor)
    reports = store.load_range(start, end)
    label = f"{start.year}年{start.month}月"
    out = store.summaries_dir / f"month_{start.strftime('%Y-%m')}.md"
    prompt = monthly_prompt(reports, label)
    return _summarize(cfg, store, reports, prompt, out)


def cmd_search(args: argparse.Namespace) -> int:
    _, store = _load_ctx(args)
    keywords = args.keywords
    if not keywords:
        print("请提供至少一个关键词。")
        return 1
    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else None
    reports = filter_by_date(store.load_range(start or date.min, end or date.max), start, end)
    # 未正式成稿的日期，把流水也纳入检索
    covered = {r.report_date for r in reports}
    for d in store.list_log_dates():
        if d in covered:
            continue
        if start and d < start:
            continue
        if end and d > end:
            continue
        logs = store.load_logs(d)
        if logs:
            reports.append(
                DailyReport(report_date=d, goal="", work_items=[e.text for e in logs], next_steps="")
            )
    hits = search_reports(reports, keywords, case_sensitive=args.case_sensitive)
    if not hits:
        print(f"未找到包含关键词 {keywords} 的日报/流水。")
        return 1
    print(f"找到 {len(hits)} 篇相关内容：\n")
    for hit in hits:
        print(f"■ {hit.report.date_str}  （命中 {hit.score} 次）")
        for line in hit.matched_lines[: args.max_lines]:
            print(f"    {line}")
        if len(hit.matched_lines) > args.max_lines:
            print(f"    … 另有 {len(hit.matched_lines) - args.max_lines} 行")
        print()
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    _, store = _load_ctx(args)
    dest = Path(args.output).expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else None
    reports = filter_by_date(store.load_range(start or date.min, end or date.max), start, end)
    parts = [r.to_markdown() for r in reports]
    dest.write_text("\n---\n\n".join(parts), encoding="utf-8")
    _print_ok(f"已导出 {len(reports)} 篇日报到 {dest}")
    return 0


def _bug_store(args: argparse.Namespace):
    cfg, store = _load_ctx(args)
    from daily_report.bug_store import BugStore

    return cfg, BugStore(store.data_dir)


def _task_store(args: argparse.Namespace):
    cfg, store = _load_ctx(args)
    from daily_report.tasks import TaskStore

    return cfg, TaskStore(store.data_dir)


def cmd_task_add(args: argparse.Namespace) -> int:
    from datetime import date as _date

    _, ts = _task_store(args)
    deadline = None
    if args.deadline:
        deadline = _date.fromisoformat(args.deadline)
    task = ts.create(title=args.title, description=args.desc, deadline=deadline)
    _print_ok(f"已创建 {task.task_id}: {task.title} 截止 {task.deadline_str or '未设置'}")
    return 0


def cmd_task_list(args: argparse.Namespace) -> int:
    _, ts = _task_store(args)
    tasks = ts.load_all()
    if not tasks:
        print("暂无任务计划。")
        return 0
    print(f"共 {len(tasks)} 条：")
    for t in tasks:
        print(
            f"  {t.task_id}  [{t.progress_pct:3d}%] {t.remaining_text():12s}  "
            f"{t.done_count}/{t.total}  {t.title}"
        )
    return 0


def cmd_task_show(args: argparse.Namespace) -> int:
    _, ts = _task_store(args)
    task = ts.load(args.task_id)
    if not task:
        print(f"未找到 {args.task_id}")
        return 1
    print(task.to_markdown())
    return 0


def cmd_task_progress(args: argparse.Namespace) -> int:
    _, ts = _task_store(args)
    task = ts.load(args.task_id)
    if not task:
        print(f"未找到 {args.task_id}")
        return 1
    if args.done:
        idx = {int(x) for x in args.done.split(",") if x.strip().isdigit()}
        for i, st in enumerate(task.subtasks, start=1):
            st.done = i in idx
    if args.status:
        task.status = args.status
    if task.subtasks and task.done_count == task.total and task.status == "进行中":
        task.status = "已完成"
    ts.save(task)
    _print_ok(f"{task.task_id} 进度 {task.done_count}/{task.total} ({task.progress_pct}%) {task.remaining_text()}")
    return 0


def cmd_task_breakdown(args: argparse.Namespace) -> int:
    from daily_report.llm import LLMClient
    from daily_report.prompts import SYSTEM_TASK_BREAKDOWN, parse_subtasks, task_breakdown_prompt
    from daily_report.tasks import SubTask

    cfg, ts = _task_store(args)
    task = ts.load(args.task_id)
    if not task:
        print(f"未找到 {args.task_id}")
        return 1
    print(f"正在调用 {cfg.llm.model} 拆分任务…")
    client = LLMClient(cfg.llm)
    prompt = task_breakdown_prompt(
        task.title, task.description, task.deadline_str
    )
    text = client.chat(SYSTEM_TASK_BREAKDOWN, prompt)
    items = parse_subtasks(text)
    if not items:
        print("模型未返回有效子任务。")
        return 1
    task.subtasks = [SubTask(title=x, done=False) for x in items]
    task.status = "进行中"
    ts.save(task)
    _print_ok(f"已生成 {len(items)} 条子任务：")
    for i, x in enumerate(items, 1):
        print(f"  {i}. {x}")
    return 0


def cmd_bug_add(args: argparse.Namespace) -> int:
    _, bs = _bug_store(args)
    tags = [t.strip() for t in args.tags.replace("，", ",").split(",") if t.strip()]
    bug = bs.create(
        title=args.title,
        symptom=args.symptom,
        error_info=args.error_info,
        root_cause=args.root_cause,
        solution=args.solution,
        tags=tags,
        env=args.env,
        note=args.note,
    )
    _print_ok(f"已创建 {bug.bug_id}: {bug.title}")
    return 0


def cmd_bug_list(args: argparse.Namespace) -> int:
    _, bs = _bug_store(args)
    bugs = bs.load_all()
    if not bugs:
        print("暂无 Bug 记录。")
        return 0
    print(f"共 {len(bugs)} 条：")
    for b in bugs:
        print(f"  [{b.status.value}] {b.bug_id}  {b.title}  {b.tags_text()}")
    return 0


def cmd_bug_show(args: argparse.Namespace) -> int:
    _, bs = _bug_store(args)
    bug = bs.load(args.bug_id)
    if not bug:
        print(f"未找到 {args.bug_id}")
        return 1
    print(bug.to_markdown())
    return 0


def cmd_bug_search(args: argparse.Namespace) -> int:
    from daily_report.bug_search import search_bugs

    _, bs = _bug_store(args)
    hits = search_bugs(bs.load_all(), args.keywords)
    if not hits:
        print("无匹配。")
        return 1
    print(f"找到 {len(hits)} 条：")
    for b in hits:
        print(f"  [{b.status.value}] {b.bug_id}  {b.title}")
    return 0


def cmd_bug_similar(args: argparse.Namespace) -> int:
    from daily_report.bug_search import find_similar

    _, bs = _bug_store(args)
    q = " ".join(args.text)
    hits = find_similar(q, bs.load_all(), top_k=args.top)
    if not hits:
        print("未找到相近 Bug。")
        return 1
    print(f"找到 {len(hits)} 条相近：\n")
    for h in hits:
        print(f"■ [{h.score:.0%}] {h.bug.bug_id}  {h.bug.title}")
        if h.reasons:
            print(f"  原因: {'；'.join(h.reasons)}")
        if h.bug.solution:
            print(f"  方案: {h.bug.solution.replace(chr(10),' ')[:80]}")
        print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="daily-report",
        description="日报/周报/月报记录与总结工具（OpenAI 协议）",
    )
    p.add_argument("--config", help="指定配置文件路径")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("init", help="生成默认 config.yaml")
    sp.add_argument("--force", action="store_true", help="覆盖已有配置")
    sp.add_argument("--mode", choices=["ai", "basic"], default="ai", help="ai=AI版 basic=非AI版")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("config", help="查看当前生效配置")
    sp.set_defaults(func=cmd_config)

    sp = sub.add_parser("gui", help="启动图形界面")
    sp.set_defaults(func=cmd_gui)

    sp = sub.add_parser("add", help="新增/更新日报（默认今天）")
    sp.add_argument("--date", help="日期 YYYY-MM-DD，默认今天")
    sp.add_argument("--goal", help="任务目标")
    sp.add_argument("--work", help="具体工作，多条用 | 分隔")
    sp.add_argument("--next", dest="next", help="下一步计划")
    sp.add_argument("-i", "--interactive", action="store_true", help="强制交互填写")
    sp.set_defaults(func=cmd_add)

    sp = sub.add_parser("log", help="随手记一条工作流水（可多次）")
    sp.add_argument("text", nargs="+", help="流水内容")
    sp.add_argument("--date", help="日期 YYYY-MM-DD，默认今天")
    sp.set_defaults(func=cmd_log)

    sp = sub.add_parser("logs", help="查看某天工作流水")
    sp.add_argument("--date", help="日期 YYYY-MM-DD，默认今天")
    sp.set_defaults(func=cmd_logs)

    sp = sub.add_parser("compose", help="根据当天流水 AI 生成日报（需模型）")
    sp.add_argument("--date", help="日期 YYYY-MM-DD，默认今天")
    sp.add_argument("--hint", help="给模型的补充说明")
    sp.add_argument("--draft", action="store_true", help="只存草稿到 data/drafts/，不覆盖正式日报")
    sp.add_argument("--keep-manual", action="store_true", help="保留已有手工字段不被覆盖")
    sp.set_defaults(func=cmd_compose)

    sp = sub.add_parser("bug", help="Bug 列表：add/list/show/search/similar")
    bug_sub = sp.add_subparsers(dest="bug_cmd", required=True)

    bp = bug_sub.add_parser("add", help="新增一条 Bug")
    bp.add_argument("--title", required=True)
    bp.add_argument("--symptom", default="")
    bp.add_argument("--error", dest="error_info", default="")
    bp.add_argument("--root", dest="root_cause", default="")
    bp.add_argument("--solution", default="")
    bp.add_argument("--tags", default="", help="逗号分隔")
    bp.add_argument("--env", default="")
    bp.add_argument("--note", default="")
    bp.set_defaults(func=cmd_bug_add)

    bp = bug_sub.add_parser("list", help="列出 Bug")
    bp.set_defaults(func=cmd_bug_list)

    bp = bug_sub.add_parser("show", help="查看 Bug 详情")
    bp.add_argument("bug_id")
    bp.set_defaults(func=cmd_bug_show)

    bp = bug_sub.add_parser("search", help="关键词 AND 搜索")
    bp.add_argument("keywords", nargs="+")
    bp.set_defaults(func=cmd_bug_search)

    bp = bug_sub.add_parser("similar", help="搜索相近历史 Bug")
    bp.add_argument("text", nargs="+", help="报错或描述")
    bp.add_argument("--top", type=int, default=5)
    bp.set_defaults(func=cmd_bug_similar)

    sp = sub.add_parser("task", help="任务计划：add/list/show/progress")
    task_sub = sp.add_subparsers(dest="task_cmd", required=True)

    tp = task_sub.add_parser("add", help="新建任务")
    tp.add_argument("--title", required=True)
    tp.add_argument("--desc", default="")
    tp.add_argument("--deadline", default="", help="YYYY-MM-DD")
    tp.set_defaults(func=cmd_task_add)

    tp = task_sub.add_parser("list", help="列出任务")
    tp.set_defaults(func=cmd_task_list)

    tp = task_sub.add_parser("show", help="查看任务详情")
    tp.add_argument("task_id")
    tp.set_defaults(func=cmd_task_show)

    tp = task_sub.add_parser("progress", help="更新子任务完成状态")
    tp.add_argument("task_id")
    tp.add_argument(
        "--done",
        default="",
        help="已完成子任务序号，逗号分隔，如 1,2,3",
    )
    tp.add_argument(
        "--status",
        default="",
        help="进行中/已完成/已取消",
    )
    tp.set_defaults(func=cmd_task_progress)

    tp = task_sub.add_parser("breakdown", help="AI 拆分子任务（需模型）")
    tp.add_argument("task_id")
    tp.set_defaults(func=cmd_task_breakdown)

    sp = sub.add_parser("show", help="查看某天日报")
    sp.add_argument("--date", help="日期 YYYY-MM-DD，默认今天")
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("list", help="列出日报")
    sp.add_argument("--month", help="筛选月份 YYYY-MM")
    sp.add_argument("--start", help="起始日期")
    sp.add_argument("--end", help="结束日期")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("delete", help="删除某天日报")
    sp.add_argument("--date", help="日期 YYYY-MM-DD，默认今天")
    sp.add_argument("-y", "--yes", action="store_true", help="不确认")
    sp.set_defaults(func=cmd_delete)

    sp = sub.add_parser("week", help="生成本周/指定周的周报总结（需配置模型）")
    sp.add_argument("--date", help="锚点日期，默认今天；取该日所在周一~周日")
    sp.set_defaults(func=cmd_week)

    sp = sub.add_parser("month", help="生成本月/指定月的月报总结（需配置模型）")
    sp.add_argument("--month", help="月份 YYYY-MM，默认本月")
    sp.add_argument("--date", help="锚点日期，与 --month 二选一")
    sp.set_defaults(func=cmd_month)

    sp = sub.add_parser("search", help="按关键词搜索日报")
    sp.add_argument("keywords", nargs="+", help="一个或多个关键词（AND）")
    sp.add_argument("--start", help="起始日期")
    sp.add_argument("--end", help="结束日期")
    sp.add_argument("--case-sensitive", action="store_true")
    sp.add_argument("--max-lines", type=int, default=5, help="每篇最多展示命中行数")
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("export", help="导出日期范围内日报为单个 Markdown")
    sp.add_argument("--output", "-o", required=True, help="输出文件路径")
    sp.add_argument("--start", help="起始日期")
    sp.add_argument("--end", help="结束日期")
    sp.set_defaults(func=cmd_export)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n已中断。")
        return 130
    except Exception as e:  # noqa: BLE001 — CLI 顶层统一报错
        print(f"错误: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
