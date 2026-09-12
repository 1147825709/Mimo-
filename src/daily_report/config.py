"""配置加载：模式、模型、提示词模板。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_FILENAMES = ("config.yaml", "config.yml")
DEFAULT_BASE_URL = "https://api.openai.com/v1"

# 模式：ai = 可用模型；basic = 非 AI，总结类需手写
MODE_AI = "ai"
MODE_BASIC = "basic"

# 各 AI 功能默认模板。占位符：{content} 会替换为用户输入/素材
DEFAULT_TEMPLATES: dict[str, str] = {
    "daily_compose": (
        "你是严谨的工作助理。请根据下面当天的工作流水，整理成日报。\n"
        "只使用流水中的信息，可合并同类项、润色措辞，不要编造未发生的工作。\n"
        "输出必须严格使用这个 Markdown 结构：\n"
        "# 日报 {date}\n\n"
        "## 任务目标\n（1-2 句概括今日主要目标）\n\n"
        "## 具体工作\n1. …\n2. …\n\n"
        "## 下一步计划\n（1-3 条）\n\n"
        "工作流水：\n{content}\n"
        "{extra}"
    ),
    "weekly_summary": (
        "你是严谨的工作助理。请根据本周日报生成周报。\n"
        "按主题归类，不要按天流水账。输出结构：\n"
        "# 周报 {date_range}\n\n"
        "## 本周概览\n## 主要工作\n## 成果与亮点\n## 问题与风险\n## 下周计划\n\n"
        "原始日报：\n{content}"
    ),
    "monthly_summary": (
        "你是严谨的工作助理。请根据本月日报生成月报。\n"
        "输出结构：\n"
        "# 月报 {date_range}\n\n"
        "## 本月概览\n## 重点工作\n## 关键成果\n## 问题与改进\n## 下月展望\n\n"
        "原始日报：\n{content}"
    ),
    "task_breakdown": (
        "你是严谨的项目助理。请把下面的大任务拆成 3~12 条可执行子任务。\n"
        "每条一行，以「- 」开头，具体可验收，不要空话，不要其它说明。\n\n"
        "大任务标题: {title}\n"
        "补充描述:\n{content}\n"
        "{extra}"
    ),
}

TEMPLATE_LABELS = {
    "daily_compose": "日报一键成稿",
    "weekly_summary": "周报总结",
    "monthly_summary": "月报总结",
    "task_breakdown": "任务 AI 拆分",
}


def default_templates() -> dict[str, str]:
    return dict(DEFAULT_TEMPLATES)


@dataclass
class ApiProfile:
    """一套 API 配置（可多套并存）。api_key 运行时为明文；落盘会加密。"""

    name: str = "default"
    base_url: str = DEFAULT_BASE_URL
    api_key: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    timeout: float = 120.0


@dataclass
class LLMConfig:
    base_url: str = DEFAULT_BASE_URL
    api_key: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    timeout: float = 120.0


def profile_to_llm(p: ApiProfile) -> LLMConfig:
    return LLMConfig(
        base_url=p.base_url.rstrip("/"),
        api_key=p.api_key,
        model=p.model,
        temperature=p.temperature,
        timeout=p.timeout,
    )


@dataclass
class Config:
    llm: LLMConfig
    data_dir: Path
    config_path: Path | None = None
    app_mode: str = MODE_AI
    templates: dict[str, str] = field(default_factory=default_templates)
    active_api: str = "default"
    apis: dict[str, ApiProfile] = field(default_factory=dict)

    @property
    def is_ai(self) -> bool:
        return self.app_mode != MODE_BASIC

    def llm_ready(self) -> bool:
        key = (self.llm.api_key or "").strip()
        return bool(key) and "your-key" not in key

    def template(self, key: str) -> str:
        t = self.templates.get(key)
        if t and t.strip():
            return t
        return DEFAULT_TEMPLATES.get(key, "")

    def ensure_default_api(self) -> None:
        if not self.apis:
            self.apis["default"] = ApiProfile(
                name="default",
                base_url=self.llm.base_url,
                api_key=self.llm.api_key,
                model=self.llm.model,
                temperature=self.llm.temperature,
                timeout=self.llm.timeout,
            )
        if self.active_api not in self.apis:
            self.active_api = next(iter(self.apis))

    def apply_active_api(self) -> None:
        """把 active profile 同步到 llm。"""
        self.ensure_default_api()
        p = self.apis[self.active_api]
        self.llm = profile_to_llm(p)

    def set_active_api(self, name: str) -> bool:
        if name not in self.apis:
            return False
        self.active_api = name
        self.apply_active_api()
        return True

    def upsert_api(self, profile: ApiProfile) -> None:
        name = profile.name.strip() or "default"
        profile.name = name
        self.apis[name] = profile
        if self.active_api == name or self.active_api not in self.apis:
            self.active_api = name
            self.apply_active_api()

    def delete_api(self, name: str) -> bool:
        if name not in self.apis:
            return False
        if len(self.apis) <= 1:
            return False  # 至少保留一个
        del self.apis[name]
        if self.active_api == name:
            self.active_api = next(iter(self.apis))
            self.apply_active_api()
        return True


def _candidate_paths() -> list[Path]:
    paths: list[Path] = []
    cwd = Path.cwd()
    paths.extend(cwd / name for name in CONFIG_FILENAMES)
    parent = cwd.parent
    paths.extend(parent / name for name in CONFIG_FILENAMES)
    home_cfg = Path.home() / ".daily-report"
    paths.extend(home_cfg / name for name in CONFIG_FILENAMES)
    return paths


def find_config_file(explicit: str | Path | None = None) -> Path | None:
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if p.is_file():
            return p
        raise FileNotFoundError(f"配置文件不存在: {p}")
    env_path = os.environ.get("DAILY_REPORT_CONFIG")
    if env_path:
        p = Path(env_path).expanduser()
        if p.is_file():
            return p.resolve()
    for p in _candidate_paths():
        if p.is_file():
            return p.resolve()
    return None


def _parse_apis(raw: dict, legacy_llm: dict) -> dict[str, ApiProfile]:
    from daily_report.secrets import decrypt_api_key

    apis: dict[str, ApiProfile] = {}
    apis_raw = raw.get("apis") or {}
    if isinstance(apis_raw, dict):
        for name, item in apis_raw.items():
            if not isinstance(item, dict):
                continue
            key_stored = item.get("api_key_enc") or item.get("api_key") or ""
            apis[str(name)] = ApiProfile(
                name=str(name),
                base_url=str(item.get("base_url") or DEFAULT_BASE_URL),
                api_key=decrypt_api_key(str(key_stored)),
                model=str(item.get("model") or "gpt-4o-mini"),
                temperature=float(item.get("temperature", 0.3)),
                timeout=float(item.get("timeout", 120)),
            )
    # 兼容旧的单一 llm 段
    if not apis and legacy_llm:
        key_stored = legacy_llm.get("api_key_enc") or legacy_llm.get("api_key") or ""
        apis["default"] = ApiProfile(
            name="default",
            base_url=str(legacy_llm.get("base_url") or DEFAULT_BASE_URL),
            api_key=decrypt_api_key(str(key_stored)),
            model=str(legacy_llm.get("model") or "gpt-4o-mini"),
            temperature=float(legacy_llm.get("temperature", 0.3)),
            timeout=float(legacy_llm.get("timeout", 120)),
        )
    return apis


def load_config(explicit: str | Path | None = None) -> Config:
    path = find_config_file(explicit)
    raw: dict = {}
    if path is not None:
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    llm_raw = raw.get("llm") or {}
    storage_raw = raw.get("storage") or {}
    app_raw = raw.get("app") or {}
    tpl_raw = raw.get("templates") or {}

    mode = str(app_raw.get("mode") or MODE_AI).strip().lower()
    if mode not in (MODE_AI, MODE_BASIC):
        mode = MODE_AI

    active_api = str(app_raw.get("active_api") or "default")
    apis = _parse_apis(raw, llm_raw)

    # 环境变量可覆盖当前激活配置（不写盘）
    env_base = os.environ.get("DAILY_REPORT_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
    env_key = os.environ.get("DAILY_REPORT_API_KEY") or os.environ.get("OPENAI_API_KEY")
    env_model = os.environ.get("DAILY_REPORT_MODEL") or os.environ.get("OPENAI_MODEL")

    cfg = Config(
        llm=LLMConfig(),
        data_dir=Path.cwd() / "data",
        config_path=path,
        app_mode=mode,
        templates=default_templates(),
        active_api=active_api,
        apis=apis,
    )
    cfg.ensure_default_api()
    if active_api not in cfg.apis:
        active_api = next(iter(cfg.apis))
        cfg.active_api = active_api
    cfg.apply_active_api()

    if env_base:
        cfg.llm.base_url = env_base.rstrip("/")
    if env_key:
        cfg.llm.api_key = env_key
    if env_model:
        cfg.llm.model = env_model

    data_dir_raw = storage_raw.get("data_dir") or "./data"
    data_dir = Path(str(data_dir_raw)).expanduser()
    if not data_dir.is_absolute():
        base = path.parent if path else Path.cwd()
        data_dir = (base / data_dir).resolve()
    else:
        data_dir = data_dir.resolve()
    cfg.data_dir = data_dir

    templates = default_templates()
    for k, v in tpl_raw.items():
        if isinstance(v, str) and v.strip():
            templates[str(k)] = v
    cfg.templates = templates
    return cfg


def config_to_dict(cfg: Config) -> dict:
    from daily_report.secrets import encrypt_api_key

    cfg.ensure_default_api()
    apis_out = {}
    for name, p in cfg.apis.items():
        apis_out[name] = {
            "base_url": p.base_url,
            "model": p.model,
            "temperature": p.temperature,
            "timeout": p.timeout,
            "api_key_enc": encrypt_api_key(p.api_key),
        }
    # 兼容旧字段：写入当前激活配置（加密）
    active = cfg.apis[cfg.active_api]
    return {
        "app": {"mode": cfg.app_mode, "active_api": cfg.active_api},
        "llm": {
            "base_url": active.base_url,
            "model": active.model,
            "temperature": active.temperature,
            "timeout": active.timeout,
            "api_key_enc": encrypt_api_key(active.api_key),
        },
        "apis": apis_out,
        "storage": {
            "data_dir": str(cfg.data_dir).replace("\\", "/"),
        },
        "templates": dict(cfg.templates),
    }


def save_config(cfg: Config, dest: Path | None = None) -> Path:
    dest = dest or cfg.config_path or (Path.cwd() / "config.yaml")
    dest = dest.expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config_to_dict(cfg), f, allow_unicode=True, sort_keys=False)
    return dest


def write_default_config(
    dest: Path,
    data_dir: Path | None = None,
    mode: str = MODE_AI,
    api_key: str = "",
    base_url: str = DEFAULT_BASE_URL,
    model: str = "gpt-4o-mini",
) -> Path:
    dest = dest.expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = data_dir if data_dir else dest.parent / "data"
    profile = ApiProfile(name="default", base_url=base_url, api_key=api_key, model=model)
    cfg = Config(
        llm=profile_to_llm(profile),
        data_dir=data,
        config_path=dest,
        app_mode=mode if mode in (MODE_AI, MODE_BASIC) else MODE_AI,
        templates=default_templates(),
        active_api="default",
        apis={"default": profile},
    )
    return save_config(cfg, dest)
