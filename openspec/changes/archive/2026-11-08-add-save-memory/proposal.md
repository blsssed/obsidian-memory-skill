# Proposal

## Why

与 AI 编程助手的日常对话中会产生大量有价值但易流失的知识：踩过的坑及其解法、可复用的命令与配置、关键技术决策及其理由、被推翻的旧认知。这些内容散落在一次次会话里，会话结束即丢失。现有方案各有缺口：通用 Obsidian MCP 只提供笔记读写工具，感知不到对话内容；claude-mem 一类记忆插件虽然能自动总结会话，但存入私有存储，无法沉淀进用户自己的知识库。本项目提供一个 Claude Code skill，把对话中的可复用知识总结写入本地 Obsidian vault，与用户既有笔记形成双链互连，实现跨项目的经验积累，同时保持零依赖、可发布到 GitHub。

## What Changes

新增 `conversation-memory` 能力，以纯 skill 形式交付（SKILL.md + 3 个 references 文件，无脚本、无 MCP server）：

- **写入侧 `/save-memory`**：按白名单规则从当前对话提取五类知识（踩坑与解法 / 可复用命令与配置 / 决策及理由 / 被推翻的认知 / 项目事实），检索 vault 判定新建、追加或标注取代，按模板写入笔记（frontmatter + `[[双链]]` + 类型化边）
- **读取侧 `/recall`**：按当前任务关键词检索 vault，将命中笔记注入上下文
- **安装**：全局安装到 `~/.claude/skills/save-memory/`，README 提供双语安装与配置指引

## Capabilities

### New Capabilities
- `conversation-memory`: 将 Claude Code 对话中的可复用知识提取、去重合并并写入本地 Obsidian vault，支持按任务关键词检索召回，笔记以双链和类型化边融入用户知识图谱。

## Impact

- 新增文件：`SKILL.md`、`references/extraction-rules.md`、`references/note-template.md`、`references/merge-rules.md`、`README.md`
- 新增全局安装：`~/.claude/skills/save-memory/`
- 外部副作用：向用户 vault 的 `AI记忆/` 目录写入 markdown 笔记
- 不修改任何现有系统代码；无运行时依赖（仅使用 Claude Code 内置工具）
