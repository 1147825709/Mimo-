# 工作台（日报 · Bug · 任务 · 知识星球）

个人效率工作台：白天随手记、下班 AI/手写成稿、Bug 沉淀与相似检索、任务计划进度，以及「知识星球」经典小游戏。  
支持 **AI 版 / 非 AI 版**，任意 **OpenAI 兼容** 接口（OpenAI / DeepSeek / 火山方舟 / 通义等）。

---

## 功能一览

| 大功能 | 说明 |
|--------|------|
| **日报记录** | 全天「记一笔」流水 → AI 一键成稿或手写三段 → 周报/月报汇总 → 关键词搜索 |
| **Bug 列表** | 现象/错误/根因/方案/标签；关键词检索；**找相近历史 Bug** |
| **任务计划** | 设定截止日期；AI 拆分子任务；进度条与剩余天数（逾期标红） |
| **知识星球** | 扫雷（初级/中级/高级）· 雷霆战机（无尽、积分升武器、随机掉命） |

其它：

- 桌面**悬浮小胶囊**「✎ 记」：平时缩小，点击展开；可切「流水 / Bug」
- **系统托盘**驻留：关窗不退出，可再呼出
- Q 版机器猫背景 + 圆角主题

---

## 快速开始

### 方式一：直接运行 exe（推荐）

1. 把 `dist\日报工作台.exe` 拷到任意目录（建议单独文件夹）
2. 双击运行；首次会弹出 **初始化向导**
3. 选择 **AI 版** 或 **非 AI 版**，填好数据目录后生成 `config.yaml`
4. AI 版：在 **文件 → 设置 → API 配置** 里添加服务商（Key 会加密写入配置）

> 若 Windows 提示已阻止：右键 exe → 属性 → **解除锁定**。

### 方式二：源码运行

```powershell
conda create -n daily-report python=3.12 -y
conda activate daily-report
cd D:\mimo\project\daily-report
pip install -e .
daily-report gui
```

---

## AI 版 vs 非 AI 版

| 能力 | AI 版 | 非 AI 版 |
|------|-------|----------|
| 随手记 / Bug / 任务 / 游戏 | 有 | 有 |
| 日报 AI 成稿 | 有 | 隐藏按钮，手写 |
| 周报 / 月报 | AI 总结 | 可编辑正文，点「保存手写总结」 |
| 任务 AI 拆分 | 有 | 手动加子任务 |
| 是否需要 API Key | 是 | 否 |

首次启动或 `daily-report init --mode ai|basic` 可选定模式；之后可在设置中改。

---

## 模型与 API

支持任意 OpenAI 协议地址，例如：

| 服务商 | Base URL 示例 | 模型示例 |
|--------|----------------|----------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 火山方舟 | `https://ark.cn-beijing.volces.com/api/coding/v3` | `deepseek-v4-flash` |
| 通义 | DashScope OpenAI 兼容地址 | `qwen-plus` |

- **多套 API**：设置 → API 配置 → 添加 / 删除 / **设为当前** / 改模型  
- **加密存储**：Key 写入 `config.yaml` 为 `enc:v1:…`，不明文保存  
- **提示词模板**：设置 → AI 提示词模板，可改日报成稿 / 周报 / 月报 / 任务拆分模板  
  占位符：`{date}` `{date_range}` `{content}` `{title}` `{extra}`

环境变量（可选，优先于配置文件）：`DAILY_REPORT_*` / `OPENAI_*`。

---

## 使用要点

### 日报
1. 右下角胶囊或主界面「记一笔」随时写流水  
2. AI 版：点「AI 一键生成日报」→ 草稿进编辑区 → 保存  
3. 非 AI 版：手写任务目标 / 具体工作（每行一条自动编号）/ 下一步计划  

### 周报 / 月报
- 右侧会显示该周/该月**全部日报原文**，可「复制全部」  
- AI 版点生成；非 AI 版手写后「保存手写总结」  

### Bug
- 快速记：标题 + 现象 + 标签  
- 完整记：根因、堆栈、方案  
- **搜索相似**：按报错/描述打分，复用历史方案  

### 任务计划
- 设标题、描述、预计完成日  
- AI 拆分或手动加子任务，勾选更新进度与剩余天数  

### 知识星球
- 扫雷：左键开、右键旗→?→取消；点数字快速展开；首点安全  
- 战机：WASD/方向键移动，自动开火；积分升武器；随机掉命；分数越高越难  

---

## 数据目录

默认在配置的 `storage.data_dir`（初始化时选定），结构：

```
data/
  logs/          # 随手记流水 YYYY-MM-DD.md
  reports/       # 正式日报
  drafts/        # 草稿
  summaries/     # 周报 / 月报
  bugs/          # Bug 记录
  tasks/         # 任务计划
```

全部为本地 Markdown，可备份、可用 Git 管理。

---

## 命令行（可选）

```powershell
daily-report gui
daily-report log 修复了登录超时
daily-report compose                 # AI 日报成稿
daily-report week / month
daily-report bug add|list|search|similar
daily-report task add|breakdown|progress|list
daily-report init --mode basic
```

---

## 重新打包 exe

```powershell
conda activate daily-report
cd D:\mimo\project\daily-report
.\build_exe.ps1
# 产物: dist\日报工作台.exe（约 58–60MB 单文件）
```

依赖：PyInstaller、PySide6、openai、PyYAML、python-dateutil（见 `requirements.txt` / `pyproject.toml`）。

---

## 测试

```powershell
python -m pytest tests -q          # 单元测试
python scripts/ai_live_test.py     # 需可用 API（读 $env:DAILY_REPORT_CONFIG）
```

AI 实测大纲与结果见 `data/AI_TEST_REPORT.md`（示例：配置解密、连通、日报成稿、周报、月报、任务拆分、模板可控输出）。

---

## 目录结构（源码）

```
src/daily_report/
  config.py / secrets.py     # 配置、多 API、加密
  storage.py / models.py     # 日报与流水
  bugs.py / bug_store.py / bug_search.py
  tasks.py
  prompts.py / llm.py
  gui/                       # 工作台 UI、悬浮窗、托盘、游戏
  assets/doraemon_bg.png
```

---

## 说明

- 加密为**本机混淆**，防配置文件被直接偷看；不要指望跨机器直接拷走密文。  
- 知识星球仅供自己休息时使用，请遵守公司相关规定。  
- 首次无配置时会进入初始化；删除 `config.yaml` 可重新走一遍向导。
