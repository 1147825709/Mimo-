"""设置：模式 / 多 API 管理（加密）/ 数据 / 提示词模板。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from daily_report.config import (
    ApiProfile,
    Config,
    DEFAULT_BASE_URL,
    MODE_AI,
    MODE_BASIC,
    TEMPLATE_LABELS,
    default_templates,
    profile_to_llm,
    save_config,
)
from daily_report.secrets import mask_api_key


class SettingsDialog(QDialog):
    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumSize(720, 600)
        self._cfg = cfg
        # 工作副本
        self._apis: dict[str, ApiProfile] = {
            k: ApiProfile(**vars(v)) for k, v in cfg.apis.items()
        }
        if not self._apis:
            self._apis["default"] = ApiProfile(
                name="default",
                base_url=cfg.llm.base_url,
                api_key=cfg.llm.api_key,
                model=cfg.llm.model,
                temperature=cfg.llm.temperature,
                timeout=cfg.llm.timeout,
            )
        self._active = cfg.active_api if cfg.active_api in self._apis else next(iter(self._apis))

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # --- 基本 ---
        basic = QWidget()
        bf = QFormLayout(basic)
        self.mode_box = QComboBox()
        self.mode_box.addItem("AI 版（可用模型总结 / 拆分 / 成稿）", MODE_AI)
        self.mode_box.addItem("非 AI 版（总结类需手写，无需 API）", MODE_BASIC)
        self.mode_box.setCurrentIndex(0 if cfg.app_mode == MODE_AI else 1)
        bf.addRow("版本模式", self.mode_box)

        row = QHBoxLayout()
        self.data_dir = QLineEdit(str(cfg.data_dir))
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._browse_data)
        row.addWidget(self.data_dir)
        row.addWidget(browse)
        bf.addRow("数据目录", row)

        self.config_path_label = QLineEdit(
            str(cfg.config_path) if cfg.config_path else "（尚未创建 config.yaml）"
        )
        self.config_path_label.setReadOnly(True)
        bf.addRow("配置文件", self.config_path_label)

        hint = QLabel(
            "API Key 以本机加密形式写入 config.yaml（enc:v1:…），不会明文保存。\n"
            "至少保留一套 API 配置；可添加多家服务商后随时切换。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#7A8B9A;")
        bf.addRow(hint)
        tabs.addTab(basic, "基本")

        # --- API 配置 ---
        api_tab = QWidget()
        al = QHBoxLayout(api_tab)

        left = QVBoxLayout()
        left.addWidget(QLabel("API 配置列表"))
        self.api_list = QListWidget()
        self.api_list.currentTextChanged.connect(self._on_api_selected)
        left.addWidget(self.api_list, 1)

        btns = QHBoxLayout()
        self.btn_add_api = QPushButton("添加")
        self.btn_add_api.setObjectName("Ghost")
        self.btn_add_api.clicked.connect(self._add_api)
        self.btn_del_api = QPushButton("删除")
        self.btn_del_api.setObjectName("DangerGhost")
        self.btn_del_api.clicked.connect(self._delete_api)
        self.btn_use_api = QPushButton("设为当前")
        self.btn_use_api.setObjectName("PrimaryBig")
        self.btn_use_api.clicked.connect(self._set_active)
        btns.addWidget(self.btn_add_api)
        btns.addWidget(self.btn_del_api)
        btns.addWidget(self.btn_use_api)
        left.addLayout(btns)
        left.addWidget(QLabel("当前使用：—"))
        self.lbl_active = left.itemAt(left.count() - 1).widget()
        al.addLayout(left, 1)

        right = QFormLayout()
        self.ed_name = QLineEdit()
        self.ed_name.setPlaceholderText("配置名称，如 openai / deepseek")
        self.ed_base = QLineEdit()
        self.ed_base.setPlaceholderText("https://api.openai.com/v1")
        self.ed_key = QLineEdit()
        self.ed_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.ed_key.setPlaceholderText("sk-…（已保存的会解密回填；改完自动加密）")
        self.ed_model = QComboBox()
        self.ed_model.setEditable(True)
        for m in (
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4.1-mini",
            "deepseek-chat",
            "qwen-plus",
            "moonshot-v1-8k",
        ):
            self.ed_model.addItem(m)
        self.ed_temp = QDoubleSpinBox()
        self.ed_temp.setRange(0.0, 2.0)
        self.ed_temp.setSingleStep(0.1)
        self.btn_save_api = QPushButton("保存这套 API")
        self.btn_save_api.clicked.connect(self._save_current_api)
        right.addRow("名称", self.ed_name)
        right.addRow("Base URL", self.ed_base)
        right.addRow("API Key", self.ed_key)
        right.addRow("模型", self.ed_model)
        right.addRow("Temperature", self.ed_temp)
        right.addRow(self.btn_save_api)
        al.addLayout(right, 2)
        tabs.addTab(api_tab, "API 配置")

        # --- 提示词模板 ---
        tpl = QWidget()
        tl = QVBoxLayout(tpl)
        tl.addWidget(
            QLabel("占位符：{date} {date_range} {content} {title} {extra}")
        )
        self.tpl_picker = QComboBox()
        for key, label in TEMPLATE_LABELS.items():
            self.tpl_picker.addItem(label, key)
        self.tpl_picker.currentIndexChanged.connect(self._switch_tpl)
        tl.addWidget(self.tpl_picker)
        self.tpl_edit = QPlainTextEdit()
        tl.addWidget(self.tpl_edit, 1)
        br = QHBoxLayout()
        btn_reset = QPushButton("恢复当前为默认")
        btn_reset.clicked.connect(self._reset_current_tpl)
        btn_reset_all = QPushButton("全部恢复默认")
        btn_reset_all.clicked.connect(self._reset_all_tpl)
        br.addWidget(btn_reset)
        br.addWidget(btn_reset_all)
        br.addStretch(1)
        tl.addLayout(br)
        tabs.addTab(tpl, "AI 提示词模板")

        self._tpl_cache: dict[str, str] = dict(cfg.templates)
        self._shown_tpl_key: str | None = None
        self._reload_api_list()
        self._switch_tpl()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ---------- API 列表 ----------

    def _reload_api_list(self) -> None:
        self.api_list.blockSignals(True)
        self.api_list.clear()
        for name in sorted(self._apis.keys()):
            mark = "● " if name == self._active else "○ "
            p = self._apis[name]
            item = QListWidgetItem(f"{mark}{name}  ·  {p.model}  ·  {mask_api_key(p.api_key)}")
            item.setData(32, name)  # Qt.UserRole
            self.api_list.addItem(item)
            if name == self._active:
                self.api_list.setCurrentItem(item)
        self.api_list.blockSignals(False)
        self.lbl_active.setText(f"当前使用：{self._active}")
        cur = self.api_list.currentItem()
        if cur:
            self._fill_form(cur.data(32))
        elif self._apis:
            self._fill_form(self._active)

    def _fill_form(self, name: str) -> None:
        p = self._apis.get(name)
        if not p:
            return
        self.ed_name.setText(p.name)
        self.ed_base.setText(p.base_url)
        self.ed_key.setText(p.api_key)  # 明文回填便于编辑
        self.ed_model.setCurrentText(p.model)
        self.ed_temp.setValue(p.temperature)

    def _on_api_selected(self, _text: str) -> None:
        item = self.api_list.currentItem()
        if item:
            self._fill_form(item.data(32))

    def _collect_profile(self) -> ApiProfile | None:
        name = self.ed_name.text().strip()
        if not name:
            QMessageBox.information(self, "提示", "请填写配置名称。")
            return None
        return ApiProfile(
            name=name,
            base_url=self.ed_base.text().strip() or DEFAULT_BASE_URL,
            api_key=self.ed_key.text().strip(),
            model=self.ed_model.currentText().strip() or "gpt-4o-mini",
            temperature=float(self.ed_temp.value()),
            timeout=self._cfg.llm.timeout,
        )

    def _save_current_api(self) -> None:
        item = self.api_list.currentItem()
        old_name = item.data(32) if item else None
        profile = self._collect_profile()
        if not profile:
            return
        # 改名
        if old_name and old_name != profile.name and old_name in self._apis:
            del self._apis[old_name]
            if self._active == old_name:
                self._active = profile.name
        self._apis[profile.name] = profile
        if self._active not in self._apis:
            self._active = profile.name
        self._reload_api_list()
        # 选中刚保存的
        for i in range(self.api_list.count()):
            if self.api_list.item(i).data(32) == profile.name:
                self.api_list.setCurrentRow(i)
                break

    def _add_api(self) -> None:
        n = 1
        while f"api{n}" in self._apis:
            n += 1
        name = f"api{n}"
        self._apis[name] = ApiProfile(name=name)
        self._reload_api_list()
        for i in range(self.api_list.count()):
            if self.api_list.item(i).data(32) == name:
                self.api_list.setCurrentRow(i)
                break
        self.ed_name.setFocus()

    def _delete_api(self) -> None:
        item = self.api_list.currentItem()
        if not item:
            return
        name = item.data(32)
        if len(self._apis) <= 1:
            QMessageBox.information(self, "提示", "至少保留一套 API 配置。")
            return
        ret = QMessageBox.question(self, "删除确认", f"删除 API 配置「{name}」？")
        if ret != QMessageBox.StandardButton.Yes:
            return
        del self._apis[name]
        if self._active == name:
            self._active = next(iter(self._apis))
        self._reload_api_list()

    def _set_active(self) -> None:
        item = self.api_list.currentItem()
        if not item:
            return
        self._active = item.data(32)
        self._reload_api_list()

    # ---------- 其它 ----------

    def _browse_data(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择数据目录", self.data_dir.text())
        if path:
            self.data_dir.setText(path)

    def _switch_tpl(self, *_args) -> None:
        if self._shown_tpl_key:
            self._tpl_cache[self._shown_tpl_key] = self.tpl_edit.toPlainText()
        key = self.tpl_picker.currentData()
        self._shown_tpl_key = key
        self.tpl_edit.setPlainText(self._tpl_cache.get(key, default_templates().get(key, "")))

    def _reset_current_tpl(self) -> None:
        key = self.tpl_picker.currentData()
        self.tpl_edit.setPlainText(default_templates().get(key, ""))
        self._tpl_cache[key] = self.tpl_edit.toPlainText()

    def _reset_all_tpl(self) -> None:
        self._tpl_cache = default_templates()
        self._switch_tpl()

    def _save(self) -> None:
        if self._shown_tpl_key:
            self._tpl_cache[self._shown_tpl_key] = self.tpl_edit.toPlainText()
        # 先把表单里未点「保存这套 API」的改动收进去
        if self.ed_name.text().strip():
            p = self._collect_profile()
            if p:
                item = self.api_list.currentItem()
                old = item.data(32) if item else None
                if old and old != p.name and old in self._apis:
                    del self._apis[old]
                    if self._active == old:
                        self._active = p.name
                self._apis[p.name] = p

        mode = self.mode_box.currentData()
        data_dir = Path(self.data_dir.text().strip()).expanduser()
        dest = self._cfg.config_path or (Path.cwd() / "config.yaml")

        if self._active not in self._apis:
            self._active = next(iter(self._apis))
        cfg = Config(
            llm=profile_to_llm(self._apis[self._active]),
            data_dir=data_dir,
            config_path=dest,
            app_mode=mode,
            templates=dict(self._tpl_cache),
            active_api=self._active,
            apis=dict(self._apis),
        )
        try:
            saved = save_config(cfg, dest)
        except OSError as e:
            QMessageBox.critical(self, "保存失败", str(e))
            return
        self._cfg = cfg
        QMessageBox.information(self, "已保存", f"配置已写入（API Key 已加密）\n{saved}")
        self.accept()

    def result_config(self) -> Config:
        return self._cfg
