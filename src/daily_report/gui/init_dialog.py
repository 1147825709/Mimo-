"""首次启动：选择 AI 版 / 非 AI 版，生成配置。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from daily_report.config import (
    ApiProfile,
    Config,
    DEFAULT_BASE_URL,
    MODE_AI,
    MODE_BASIC,
    default_templates,
    profile_to_llm,
    save_config,
)


class InitDialog(QDialog):
    def __init__(self, parent=None, default_config_path: Path | None = None):
        super().__init__(parent)
        self.setWindowTitle("初始化工作台")
        self.setMinimumWidth(520)
        self.result_cfg: Config | None = None

        lay = QVBoxLayout(self)
        title = QLabel("选择使用模式")
        title.setStyleSheet("font-size:14pt; font-weight:700;")
        lay.addWidget(title)
        tip = QLabel(
            "AI 版：可用模型做日报成稿、周报/月报总结、任务拆分（需配置 API）。\n"
            "非 AI 版：上述功能改为手写，无需配置模型。\n"
            "选择后会生成 config.yaml，之后沿用该配置。"
        )
        tip.setWordWrap(True)
        lay.addWidget(tip)

        self.ai_btn = QPushButton("AI 版（推荐）")
        self.ai_btn.setObjectName("PrimaryBig")
        self.ai_btn.setCheckable(True)
        self.ai_btn.setChecked(True)
        self.basic_btn = QPushButton("非 AI 版")
        self.basic_btn.setObjectName("Ghost")
        self.basic_btn.setCheckable(True)
        row = QHBoxLayout()
        row.addWidget(self.ai_btn, 1)
        row.addWidget(self.basic_btn, 1)
        lay.addLayout(row)
        self.ai_btn.clicked.connect(lambda: self._set_mode(MODE_AI))
        self.basic_btn.clicked.connect(lambda: self._set_mode(MODE_BASIC))
        self._mode = MODE_AI

        form = QFormLayout()
        self.base_url = QLineEdit(DEFAULT_BASE_URL)
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("AI 版必填；非 AI 版可留空")
        self.model = QLineEdit("gpt-4o-mini")
        self.data_dir = QLineEdit(str(Path.cwd() / "data"))
        form.addRow("Base URL", self.base_url)
        form.addRow("API Key", self.api_key)
        form.addRow("模型", self.model)
        form.addRow("数据目录", self.data_dir)
        lay.addLayout(form)
        self.llm_form_rows = [self.base_url, self.api_key, self.model]

        browse = QPushButton("浏览数据目录…")
        browse.setObjectName("Ghost")
        browse.clicked.connect(self._browse)
        lay.addWidget(browse)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("开始使用")
        buttons.accepted.connect(self._accept)
        lay.addWidget(buttons)

        self._config_path = default_config_path or (Path.cwd() / "config.yaml")

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        self.ai_btn.setChecked(mode == MODE_AI)
        self.basic_btn.setChecked(mode == MODE_BASIC)
        for w in self.llm_form_rows:
            w.setEnabled(mode == MODE_AI)

    def _browse(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path = QFileDialog.getExistingDirectory(self, "选择数据目录", self.data_dir.text())
        if path:
            self.data_dir.setText(path)

    def _accept(self) -> None:
        data_dir = Path(self.data_dir.text().strip() or (Path.cwd() / "data")).expanduser()
        api_key = self.api_key.text().strip()
        if self._mode == MODE_AI and not api_key:
            QMessageBox.warning(
                self,
                "需要 API Key",
                "AI 版需要填写 API Key。\n若只想先用手写功能，请选择「非 AI 版」。",
            )
            return
        profile = ApiProfile(
            name="default",
            base_url=self.base_url.text().strip() or DEFAULT_BASE_URL,
            api_key=api_key,
            model=self.model.text().strip() or "gpt-4o-mini",
        )
        cfg = Config(
            llm=profile_to_llm(profile),
            data_dir=data_dir,
            config_path=self._config_path,
            app_mode=self._mode,
            templates=default_templates(),
            active_api="default",
            apis={"default": profile},
        )
        try:
            save_config(cfg, self._config_path)
        except OSError as e:
            QMessageBox.critical(self, "写入失败", str(e))
            return
        self.result_cfg = cfg
        self.accept()
