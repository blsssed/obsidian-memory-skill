# Changelog

遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 结构；版本号遵循语义化版本。

## [0.5.1] - 2026-11-14

### Fixed

- **不再教你运行不存在的命令**：v0.4.0 移除 hooks 与 slash command 之后，引擎的配置提示仍在说「请运行 /save-memory-setup」，而那个命令早已不存在——这是用户把触发方式记成斜杠命令的直接原因。现在改为给出两条真实路径：配置文件写到哪、或者对 agent 说「用 save-memory 配置」（`mem.py` × 2、`validate.py` × 1）
- `记忆目录不存在` 的提示补上解决动作，`mem.py validate` 与 `validate.py` 两个入口文案一致
- 流程标题与策略文件引用不再出现 `/save-memory`、`/garden-memory`、`/save-memory-setup` 这些命令名，改为中文动作名（「保存记忆」/「整理记忆」）——文档不该暗示存在一个不存在的入口

### Added

- README 新增两节：**快速开始**（配置 + 验证，两步跑通）与**日常怎么用**（四类意图 → 你说什么 → 内部走哪个流程），中英双语。明确写出**没有 `/save-memory` 斜杠命令**，触发靠 `description` 命中、点名 `save-memory`、或直接跑引擎三种方式
- 心智模型表区分「引擎命令」与「流程」——原表把 `save` 写成命令，实际它没有独立命令

## [0.5.0] - 2026-11-13

### Added

- **打分配置外置**：`W_TITLE` / `W_TAG` / `W_BODY` / `MIN_TAG_COVERAGE` / `HOP_DECAY` / `BODY_OCC_CAP` 改由 `save-memory.json` 的 `scoring` 段驱动。缺省值与 v0.4.0 的硬编码常量逐项相等，老配置升级后排名不变
- `mem.py params`：输出打分参数的默认值、允许区间与当前生效值（JSON）。没有 vault 也能跑，供桌面面板读取——默认值和区间只在 Python 侧定义一份，不在 JS 里抄第二份
- `memory_config.get_scoring()`：坏值**静默回落而不是夹紧**。越界的 1000 会被当成没写，而不是被悄悄改成 20——后者会让用户以为保存生效了

### Fixed

- **隐藏目录不再被当成笔记**：`build()` 以前用 `VAULT.rglob("*.md")`，把 `.obsidian`（配置）、`.trash`（回收站）、`.smart-env` 这些目录里的 Markdown 也索引了 —— 后果是从回收站删掉的笔记会被重新召回，配置目录里的说明文也变成"记忆"。现在 `vault_notes()` 跳过任何以点开头的目录段与文件名

### Changed

- 召回排名现在可以被配置改变：同一批笔记、同一关键词，改 `title_weight` 后顺序不同（`tests/test_scoring_config.py` 用子进程锁住这条，不靠函数级断言自说自话）
- 测试 81 → 103 个用例

## [0.4.0] - 2026-11-13

### Removed

- **hooks 全部移除**（`SessionEnd` 自动总结、`SessionStart` 索引注入）。它们是唯一无法跨 agent 移植的组件：嵌套调用依赖 `claude -p`，transcript 是 Claude Code 私有格式。记忆索引改为 `mem.py brief`，由宿主在需要时调用
- 已注册 hooks 的用户需要从 `~/.claude/settings.json` 里删掉对应的两段配置

### Added

- `engine/state.py`：状态目录解析（`SAVE_MEMORY_HOME` > `~/.claude` > `~/.save-memory`），多 agent 平台可隔离缓存
- `mem.py brief`：记忆索引（标题 | tags | updated），替代 SessionStart hook
- `mem.py find`：轻量定位，只出得分/标题/路径，不注入正文
- `mem.py check-links`：校验指定笔记的双链目标是否真实存在，替代「用 Glob 逐个验证」
- `mem.py validate`：格式校验收进统一入口（`validate.py` 仍可独立运行）
- `recall --record`：召回时顺带维护 `recall_count`，不再依赖模型记得单独跑一次 `record`
- `tests/`：81 个用例（标准库 `unittest`，零第三方依赖），锁住 BOM / 同名笔记 / 词边界 / 覆盖率阈值
- `docs/hosts-codex.md`：Codex CLI v0.119.0 实机验证的适配说明——skills 目录安装、按需加载机制、沙箱可写范围、能力矩阵（含做不到的部分）
- `write_atomic()` + 跨进程锁：两个 agent 同时运行时，不会再读到写了一半的缓存，`recall_count` 也不会因并发读改写而丢计数。拿不到锁时静默降级——正确性由原子写兜底，锁只负责减少竞争
- 双库用法：`SAVE_MEMORY_HOME` 隔离状态目录 + 各自的 `save-memory.json`，Claude 与 Codex 可以用各自独立的 vault

### Fixed

- `mem.py brief` 不再把 `snippets/` 下的素材列进记忆索引——它们没有 `updated` 字段，混进来会让索引出现一列 `-`
- 缓存写入失败（例如只读沙箱）不再让整次召回失败，只静默跳过缓存更新

### Changed

- `scripts/` → `engine/`；`graph.py` → `mem.py`（它早就不只做 graph 了）
- `SKILL.md` 从 7.3KB 降到 4.0KB：流程拆到 `workflows/`，策略留在 `references/`，正文只保留索引与硬性约束
- 流程里的宿主专有工具名（Glob / Grep）改成引擎子命令；只有没有命令执行能力的宿主才退化为文件搜索
- `validate.py` 抽出 `check_paths()`，CLI 与 `mem.py validate` 共用同一段逻辑
- 缓存版本递增到 4（key 语义变更，旧缓存整批失效重建）

### Fixed

- `graph.py` 读取笔记改用 `utf-8-sig`：带 BOM 的文件此前 `startswith("---")` 失败，frontmatter 不解析、YAML 原文混入正文参与打分，且类型化边（`solved_by` 加权、`superseded_by` 降权与 ⚠️已过时标注）全部降级为 `wikilink`
- 图谱 key 由文件名（`path.stem`）改为 vault 内相对路径：不同目录下的同名笔记此前互相覆盖，被覆盖者从召回、红链检测、园艺中静默消失
- 关键词匹配加入 ASCII 词边界：`ai` / `go` / `ui` 这类短词不再命中 `email`、`good`、`build` 里的子串；中文关键词仍按子串匹配，`429` 在中文邻接中照常命中
- 标签通道加入最低覆盖率阈值（`MIN_TAG_COVERAGE = 0.6`）：`env`/`environment`、`api`/`apikey` 这类弱包含不再产生种子分
- `session_end.py` 在嵌套总结结束后由 hook 进程直接调用 `validate.py` 校验本次写入的笔记，问题写入日志与 `systemMessage`——此前嵌套会话的 `allowedTools` 不含 `Bash`，SKILL.md 要求的「写盘后校验」在自动总结路径上根本无法执行
- `graph.py record` 支持带 BOM 的文件并保持其原 BOM 状态；同名多篇笔记都会计数
- `graph.py check` 的跨目录判定改用相对路径，记忆目录名读取配置而非硬编码 `AI记忆`

## [0.3.0] - 2026-11-08

### Added

- **配置外置**：`~/.claude/save-memory.json` 统一配置 vault / memory_dir / snippet_dir；优先级链 `--vault` > `SAVE_MEMORY_VAULT` > 配置文件 > 内置默认；坏 JSON 静默降级
- **`/save-memory-setup`**：对话式一次性安装（问路径 → 验证目录 → 写配置 → `graph.py build` 验证）
- **`scripts/validate.py`**：写入后确定性格式校验（frontmatter 必填字段、文件名合法性、UTF-8 无 BOM、高频泛词警告）
- **`recall_count` 使用统计**：`graph.py record <笔记名...>` 只重写 frontmatter 递增计数；`/recall` 对 ★ 种子笔记自动记录；园艺报告列出创建 >14 天且零召回的笔记
- **plugin 打包**：repo 重组为 plugin 根 + `skills/save-memory/`，`.claude-plugin/plugin.json` + `marketplace.json`（自托管，`source: "./"`）
- session_end hook 三态日志（`action=skip|done|fail` + 轮数），可 grep 对账

### Changed

- 自动总结与会话启动注入改为 **opt-in**：hooks 默认关闭，README 提供显式注册片段
- 仓库目录结构：`SKILL.md` / `references/` / `scripts/` / `hooks/` → `skills/save-memory/` 下
- README 双语重写：双安装路径（plugin / 手动复制）、配置优先级链、hooks 开启说明

### Fixed

- `graph.py record` 重写校验误判（正文页脚含 `---` 时放弃写入）；改为"新文件以原正文结尾 + 长度只增不减"校验
- `graph.py check` 代码段内的 `` `[[` `` 不再被解析为链接（围栏代码块 + 行内代码先剥离）

## [0.2.0] - 2026-11-08

### Added

- **`graph.py` 图谱混合召回**：同义词扩词 → 标签/正文双通道种子计分（覆盖率加权）→ 一跳扩展（跳数衰减 0.5^hop × 边类型系数）→ 字数预算输出；mtime 增量缓存
- **`/garden-memory`** 知识库体检：红链、跨目录可疑链接、可疑别名链接、薄笔记合并、同义 tags 归并、域笔记拆分建议（只报告，确认后修复）
- **SessionEnd hook**：会话结束自动总结（<5 轮用户消息跳过；嵌套 headless 调用，防递归 + 超时保护）
- **SessionStart hook**：会话启动/恢复注入记忆索引
- `/recall` 同义词扩展（如"限流"↔"429"、"双链"↔"wikilink"）

## [0.1.1] - 2026-11-08

### Changed

- 提取规则加固：封闭世界白名单（情境理由不构成提取依据）、素材/经验解耦（>10 行代码外置 `snippets/`）、域级笔记合并规则
- 写入流程强制输出提取审计表

## [0.1.0] - 2026-11-08

### Added

- `/save-memory`：从对话提取五类知识（踩坑与解法、可复用命令/配置、决策及理由、被推翻的认知、项目事实），去重合并后写入 Obsidian `AI记忆/`
- 笔记模板：frontmatter（tags/source/created/updated + 类型化边）、一句话结论 → 详情 → 相关
- 写入边界：只写 `AI记忆/`，双链只写记忆笔记一侧；敏感信息永不写入
