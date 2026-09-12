"""LLM 提示词模板。"""

from __future__ import annotations

from daily_report.models import DailyReport, WorkLogEntry

SYSTEM_SUMMARY = (
    "你是一名严谨的工作助理，擅长把多篇日报提炼成结构清晰的周报/月报。"
    "输出使用简体中文，条理清楚，不要编造日报中不存在的内容。"
)

SYSTEM_DAILY_COMPOSE = (
    "你是一名严谨的工作助理。根据用户当天随手记的工作流水，"
    "整理成结构清晰的日报。只使用流水中的信息，可合并同类项、润色措辞，"
    "不要编造未发生的工作。输出使用简体中文，且必须严格使用指定 Markdown 结构。"
)


def daily_compose_prompt(
    report_date: str,
    logs: list[WorkLogEntry],
    existing_goal: str = "",
    existing_next: str = "",
    hint: str = "",
) -> str:
    log_lines = "\n".join(e.to_line() for e in logs) or "（无流水）"
    extra = []
    if existing_goal.strip():
        extra.append(f"已有任务目标（可作为参考/保留）：\n{existing_goal.strip()}")
    if existing_next.strip():
        extra.append(f"已有下一步计划（可作为参考/保留）：\n{existing_next.strip()}")
    if hint.strip():
        extra.append(f"用户补充说明：\n{hint.strip()}")
    extra_block = ("\n\n" + "\n\n".join(extra)) if extra else ""

    return f"""请根据以下 {report_date} 的工作流水，生成一篇日报。

输出必须严格是下面这个 Markdown 结构（不要额外解释、不要代码块围栏）：

# 日报 {report_date}

## 任务目标
用 1-2 句概括今天的主要目标/主题。若信息不足可从具体工作中归纳。

## 具体工作
用编号列表 1. 2. 3.… 列出具体工作条目。合并重复/相近流水，每条简洁完整。

## 下一步计划
根据流水中的未完成事项、后续动作写 1-3 条。若确实没有，写「继续推进今日相关工作」。

工作流水：
{log_lines}
{extra_block}
"""


def parse_daily_report(text: str, report_date) -> DailyReport:
    """从模型输出解析日报；容忍代码块围栏。"""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # 去掉 ```markdown / ```
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return DailyReport.from_markdown(cleaned, report_date)


def _format_reports(reports: list[DailyReport]) -> str:
    chunks: list[str] = []
    for r in reports:
        work = "\n".join(f"  - {w}" for w in r.work_items) or "  （无）"
        chunks.append(
            f"### {r.date_str}\n"
            f"任务目标：{r.goal or '（无）'}\n"
            f"具体工作：\n{work}\n"
            f"下一步计划：{r.next_steps or '（无）'}"
        )
    return "\n\n".join(chunks)


def weekly_prompt(reports: list[DailyReport], start: str, end: str) -> str:
    return f"""请根据以下 {start} 至 {end} 的日报，生成一份周报总结。

要求结构如下：
# 周报 {start} ~ {end}

## 本周概览
用 2-4 句话概括本周整体进展与重点。

## 主要工作
按主题归类（不要简单按天罗列），每类下列出要点，可标注涉及日期。

## 成果与亮点
列出可交付成果、关键决策或亮点。

## 问题与风险
如有则写，没有可写「无」。

## 下周计划
结合各日「下一步计划」归纳，条理化输出。

原始日报：
{_format_reports(reports)}
"""


def monthly_prompt(reports: list[DailyReport], month_label: str) -> str:
    return f"""请根据以下 {month_label} 的日报，生成一份月报总结。

要求结构如下：
# 月报 {month_label}

## 本月概览
用 3-5 句话概括本月整体情况。

## 重点工作
按项目/主题归类总结，突出产出与进展。

## 关键成果
列出量化或可验证的成果。

## 问题与改进
总结问题、风险与经验教训。

## 下月展望
给出下月重点方向与计划。

原始日报：
{_format_reports(reports)}
"""

SYSTEM_TASK_BREAKDOWN = (
    "你是一名严谨的项目助理，擅长把大任务拆成可执行、可验收的小步骤。"
    "输出使用简体中文，条目简洁具体，不要空话。"
)


def task_breakdown_prompt(
    title: str,
    description: str = "",
    deadline: str = "",
    max_items: int = 12,
) -> str:
    dl = f"\n预计完成日期: {deadline}" if deadline else ""
    desc = description.strip() or "（无补充描述）"
    return f"""请将下面的大任务拆分成可执行的小任务（子任务）。

要求：
1. 输出 3~{max_items} 条子任务，按合理执行顺序排列。
2. 每条只输出一行，以「- 」开头，不要编号、不要复选框。
3. 每条应具体可验收（做什么 + 可交付结果），避免「跟进」「推进」等空泛词。
4. 不要输出其它说明文字、标题或代码块。

大任务标题: {title}
补充描述:
{desc}
{dl}

请直接输出子任务列表：
"""


def parse_subtasks(text: str) -> list[str]:
    """从模型输出解析子任务标题列表。"""
    items: list[str] = []
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    for raw in cleaned.splitlines():
        line = raw.strip()
        if not line:
            continue
        line = line.lstrip("*•· ").strip()
        if line[:1].isdigit() or (len(line) > 2 and line[0].isdigit() and line[1] in ".、．"):
            for sep in (".", "、", "．"):
                if sep in line[:4]:
                    line = line.split(sep, 1)[1].strip()
                    break
        if line.startswith("["):
            if "]" in line:
                line = line.split("]", 1)[1].strip()
            else:
                continue
        if line.startswith("- "):
            line = line[2:].strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("：") or line.endswith(":"):
            continue
        items.append(line.strip())
    seen = set()
    out = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out
