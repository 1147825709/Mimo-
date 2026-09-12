from datetime import date, datetime
from pathlib import Path

from daily_report.models import DailyReport, WorkLogEntry
from daily_report.search import search_reports
from daily_report.storage import ReportStore, month_range, week_range


def test_task_plan_progress(tmp_path: Path):
    from datetime import timedelta

    from daily_report.tasks import SubTask, TaskPlan, TaskStore

    ts = TaskStore(tmp_path)
    deadline = date.today() + timedelta(days=3)
    task = ts.create(title="上线支付模块", description="完成联调并上线", deadline=deadline)
    task.subtasks = [
        SubTask("接口联调", True),
        SubTask("前端页面", True),
        SubTask("压测报告", False),
        SubTask("灰度发布", False),
    ]
    ts.save(task)
    loaded = ts.load(task.task_id)
    assert loaded is not None
    assert loaded.done_count == 2
    assert loaded.total == 4
    assert loaded.progress_pct == 50
    assert loaded.days_left() == 3
    assert "剩余 3 天" in loaded.remaining_text()

    text = loaded.to_markdown()
    again = TaskPlan.from_markdown(text, loaded.task_id)
    assert again.done_count == 2
    assert again.deadline == deadline


def test_parse_subtasks_from_model():
    from daily_report.prompts import parse_subtasks

    raw = """1. 完成接口文档
2、补充单元测试
- 写部署脚本
[ ] 更新 README
"""
    items = parse_subtasks(raw)
    assert "完成接口文档" in items
    assert "补充单元测试" in items
    assert "写部署脚本" in items
    assert "更新 README" in items


def test_bug_store_and_similar(tmp_path: Path):
    from daily_report.bug_search import find_similar, search_bugs
    from daily_report.bug_store import BugStore

    bs = BugStore(tmp_path)
    b1 = bs.create(
        title="登录接口超时",
        symptom="点击登录后一直转圈，最终 504",
        error_info="Gateway Timeout: upstream timed out\nPOST /api/login 504",
        root_cause="鉴权服务连接池耗尽",
        solution="扩大连接池并增加超时重试",
        tags=["登录", "超时", "后端"],
    )
    b2 = bs.create(
        title="支付回调重复入账",
        symptom="同一订单支付成功回调多次，余额重复增加",
        error_info="duplicate callback order_id=123",
        root_cause="未做幂等校验",
        solution="按业务单号加唯一索引",
        tags=["支付", "幂等"],
    )
    assert b1.bug_id.startswith("BUG-")
    loaded = bs.load(b1.bug_id)
    assert loaded is not None
    assert "连接池" in loaded.root_cause
    assert "登录" in loaded.tags

    hits = search_bugs(bs.load_all(), ["超时"])
    assert len(hits) == 1 and hits[0].bug_id == b1.bug_id

    similar = find_similar("登录接口 504 超时 Gateway Timeout", bs.load_all())
    assert similar
    assert similar[0].bug.bug_id == b1.bug_id
    assert similar[0].score > 0.2


def test_api_key_encrypt_roundtrip():
    from daily_report.secrets import decrypt_api_key, encrypt_api_key, mask_api_key

    key = "sk-test-abcdef123456"
    enc = encrypt_api_key(key)
    assert enc.startswith("enc:v1:")
    assert key not in enc
    assert decrypt_api_key(enc) == key
    # 二次加密幂等
    assert encrypt_api_key(enc) == enc
    # 明文迁移
    assert decrypt_api_key("sk-plain") == "sk-plain"
    assert "…" in mask_api_key(key)


def test_multi_api_profiles(tmp_path: Path):
    from daily_report.config import (
        ApiProfile,
        Config,
        LLMConfig,
        default_templates,
        load_config,
        profile_to_llm,
        save_config,
    )

    p1 = ApiProfile(name="openai", base_url="https://api.openai.com/v1", api_key="sk-aaa", model="gpt-4o-mini")
    p2 = ApiProfile(name="deepseek", base_url="https://api.deepseek.com/v1", api_key="sk-bbb", model="deepseek-chat")
    cfg = Config(
        llm=profile_to_llm(p1),
        data_dir=tmp_path / "data",
        config_path=tmp_path / "config.yaml",
        apis={"openai": p1, "deepseek": p2},
        active_api="openai",
        templates=default_templates(),
    )
    save_config(cfg)
    text = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    assert "sk-aaa" not in text
    assert "enc:v1:" in text

    loaded = load_config(tmp_path / "config.yaml")
    assert set(loaded.apis) == {"openai", "deepseek"}
    assert loaded.apis["openai"].api_key == "sk-aaa"
    assert loaded.apis["deepseek"].api_key == "sk-bbb"
    assert loaded.active_api == "openai"
    assert loaded.llm.model == "gpt-4o-mini"

    loaded.set_active_api("deepseek")
    assert loaded.llm.model == "deepseek-chat"
    assert loaded.llm.api_key == "sk-bbb"

    assert loaded.delete_api("openai")
    assert "openai" not in loaded.apis
    assert loaded.active_api == "deepseek"


def test_work_log_roundtrip(tmp_path: Path):
    store = ReportStore(tmp_path)
    d = date(2026, 9, 11)
    store.append_log(d, "完成搜索模块", timestamp=datetime(2026, 9, 11, 10, 30))
    store.append_log(d, "补了单元测试", timestamp=datetime(2026, 9, 11, 14, 0))
    entries = store.load_logs(d)
    assert len(entries) == 2
    assert entries[0].text == "完成搜索模块"
    assert entries[0].time_str == "10:30"
    assert entries[1].text == "补了单元测试"


def test_parse_daily_report_fence():
    from daily_report.prompts import parse_daily_report

    raw = "```markdown\n# 日报 2026-09-11\n\n## 任务目标\n完成工具\n\n## 具体工作\n1. 写代码\n\n## 下一步计划\n联调\n```"
    r = parse_daily_report(raw, date(2026, 9, 11))
    assert r.goal == "完成工具"
    assert r.work_items == ["写代码"]
    assert "联调" in r.next_steps


def test_work_log_entry_parse_line():
    e = WorkLogEntry.parse_line("- 09:15 修复超时", date(2026, 9, 11))
    assert e is not None
    assert e.time_str == "09:15"
    assert e.text == "修复超时"


def test_markdown_roundtrip():
    r = DailyReport(
        report_date=date(2026, 8, 27),
        goal="完成工具",
        work_items=["写存储", "写 CLI"],
        next_steps="接入模型",
    )
    text = r.to_markdown()
    parsed = DailyReport.from_markdown(text, r.report_date)
    assert parsed.goal == "完成工具"
    assert parsed.work_items == ["写存储", "写 CLI"]
    assert parsed.next_steps == "接入模型"


def test_week_range_monday():
    # 2026-08-27 is Thursday
    start, end = week_range(date(2026, 8, 27))
    assert start == date(2026, 8, 24)
    assert end == date(2026, 8, 30)


def test_month_range():
    start, end = month_range(date(2026, 2, 15))
    assert start == date(2026, 2, 1)
    assert end == date(2026, 2, 28)


def test_search_keywords():
    reports = [
        DailyReport(date(2026, 8, 25), "基础框架", ["conda 环境", "存储"], "CLI"),
        DailyReport(date(2026, 8, 26), "搜索能力", ["关键词搜索", "OpenAI"], "验证"),
    ]
    hits = search_reports(reports, ["搜索"])
    assert len(hits) == 1
    assert hits[0].report.report_date == date(2026, 8, 26)

    hits2 = search_reports(reports, ["OpenAI", "存储"])
    assert len(hits2) == 0  # AND：必须同一篇内同时出现

    hits4 = search_reports(reports, ["OpenAI", "关键词"])
    assert len(hits4) == 1
    assert hits4[0].report.report_date == date(2026, 8, 26)

    hits3 = search_reports(reports, ["conda"])
    assert hits3 and "conda" in hits3[0].matched_lines[0]
