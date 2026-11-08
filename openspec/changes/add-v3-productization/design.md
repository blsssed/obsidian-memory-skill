# Design: add-v3-productization

## Context

v0.2.0 已交付四件套（hooks 自动总结/索引注入、graph.py 混合召回、/garden-memory）。真实使用暴露的问题决定了 v3 的形态：hooks 的默认开启形态在真实使用中暴露了成本与可观测性顾虑，自动化必须转为 opt-in；配置外置后无法预置他人机器的路径，vault 必须经 /save-memory-setup 或配置文件提供；黑链事故证明 prompt 窄约束会漏，格式规则需要确定性保障。

## 目标/非目标

**目标**：配置一处可改、安装一条命令、格式校验确定性、召回可量化。
**非目标**：语义检索（500+ 篇触发）、GUI、hooks 默认开启、W_TITLE 参数调整（等 recall_count 数据支撑后再调）。

## 关键决策

### D1：优先级链的实现方式
逐层赋值覆盖式（低→高循环，每层"有值才覆盖"），不用 try/except 链或 dict.update 全量合并——前者可读性差，后者会把空值也覆盖掉。坏 JSON 静默降级是硬要求：配置解析在 hook/召回路径上，不能因手滑坏一行就罢工。

### D2：配置加载器的代码组织
canonical 实现在 `scripts/memory_config.py`（graph.py 同目录直接 import）；两个 hooks **内联同款 ~15 行副本**而非 import——hook 由 settings.json 以绝对路径拉起，进程环境不可依赖 sys.path 与工作目录，自包含比 DRY 更稳。副本顶部注释标明 canonical 位置，改动需三处同步。这是有意的重复，v3.5 若嫌痛可改 plugin 结构统一。

### D3：validate.py 自包含轻量解析
不复用 graph.py 的 Note 解析（避免跨脚本 import 依赖），自实现 split_frontmatter 级别的几十行轻量解析。职责边界写死在 spec：validate 管格式，check 管链接健康，两者互不越权——防止未来有人在 validate 里塞语义判断。

### D4：record 子命令的安全写入策略
递增 recall_count 只允许"读全文 → 仅重写 frontmatter 段 → 正文原样保留"。用户笔记正文可能含手工内容，正则替换正文有破坏风险。frontmatter 段以 `---` 边界定界，重写后全文行数校验防止截断。

### D5：hooks opt-in 的落地形态
plugin 打包时 hooks **不写入 plugin 的 hooks.json**——装了 plugin 不等于开启自动化。README 提供"想要自动化"用户的手动注册片段（与 v2 相同的 JSON），注册动作本身即显式同意。可观测性增强放 session_end.py：日志行增加"跳过/执行/失败"三态与轮数，用户事后能对账。

### D6：/save-memory-setup 的定位
作为 SKILL.md 的"安装"小节而非"流程四"——它是低频一次性动作，与三个高频流程（写入/召回/园艺）不同级。流程：问 vault 路径（支持用户直接拖路径）→ os.path.isdir 验证 → 问记忆目录名（默认 AI记忆）→ Write 写 ~/.claude/save-memory.json → `graph.py build` 验证读到 → 汇报。零脚本零 GUI，对话即 UI。

### D7：plugin 规范先研究后动手
plugin JSON schema 与 marketplace 格式有时效性，实现时用 claude-code-guide 子代理查官方文档 + 本地 `claude plugin --help` 双源验证（网络不可达时以本地 binary 为准）。此为 tasks 5.1 的前置研究项，不预先假设 schema 细节。

## 附：5.1 plugin 规范实测结论（2026-11-08，来源：本机 CLI 实验 + 官方 marketplace 实例，官方文档因配额暂不可达）

全部结论均由本机 `claude plugin` 命令实测得出，非文档转述：

1. **plugin manifest**：`.claude-plugin/plugin.json`，最小合法字段 `{"name", "description", "version", "author": {"name"}}`；`claude plugin validate <目录>` 通过。常见可选字段：`license`、`keywords`、`homepage`、`repository`。`author` 缺失只报 warning 不报 error。
2. **skill 发现路径**：plugin 内 skill 必须是 `skills/<技能名>/SKILL.md`。实测对照：SKILL.md 放 plugin 根 → 嵌套 claude 的可用技能列表查无此技能（NONE）；放 `skills/probe-b/SKILL.md` → 技能加载成功（probe-b）。因此 repo 需重组为 plugin 根 + `skills/save-memory/`。
3. **hooks 分发**：plugin 的 hooks 从根目录 `hooks/hooks.json` 读取（官方实例 hookify/code-modernization 均如此，命令用 `${CLAUDE_PLUGIN_ROOT}` 引用包内脚本）。**不给 plugin 根目录放 hooks.json = 不自动启用任何 hook**，opt-in 由"省略文件"天然实现。skill 目录内自带的 hooks/ 源码不会被执行。
4. **marketplace 格式**：`.claude-plugin/marketplace.json` 必填 `name`、`owner`、`plugins[]`；顶层不允许 `description`（validate 报 Unrecognized key），说明文字应放 `"metadata": {"description": ...}`。plugin 条目含 `name/description/version/author/source`，本地或自托管用 `"source": "./相对路径"`。
5. **自托管安装路径**：repo 根同时放 `plugin.json` + `marketplace.json`、marketplace 条目 `source: "./"`，实测 `claude plugin validate` 通过、`claude plugin marketplace add <本地repo路径>` + `claude plugin install <plugin>@<marketplace>` 成功，技能可加载。用户侧一条命令：`claude plugin marketplace add <GitHub repo> && claude plugin install save-memory@<marketplace>`。
6. **安装副作用**：安装会写用户 settings.json 的 `enabledPlugins` 与 `extraKnownMarketplaces`（source 类型 `directory`）；插件文件缓存于 `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`（带版本目录，**不适合在 README 里写死 hooks 注册路径**——版本更新后路径会变）。
7. **hooks opt-in 的推荐形态**（据此更新 D5 的落地细节）：plugin 只打包 skill（skill 目录内含 hooks/ 源码），README 对想要自动化的用户给两条路：(a) 手动安装 skill 到 `~/.claude/skills/save-memory/` 后按固定路径注册 hooks；(b) 装 plugin 的用户用 `claude plugin list --json` 查 installPath 手动注册（版本升级需重注册，文档注明）。推荐 (a)。

## 风险与权衡

- hooks 内联配置副本 = 三处同步负担（接受：hook 自包含的可靠性收益 > DRY）
- recall_count 由 Claude 在 /recall 后手动执行 record，用户不跑 /recall 就没有数据（接受：这正是"数据反哺提取规则"需要的真实使用信号）
- plugin 安装路径与手动复制路径并存（接受：plugin 系统尚在演进，手动路径是兜底）
