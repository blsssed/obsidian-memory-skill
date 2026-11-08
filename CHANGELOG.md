# Changelog

遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 结构；版本号遵循语义化版本。

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
