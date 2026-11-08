# save-memory · Obsidian 对话记忆

[中文](#中文) | [English](#english)

把 Claude Code 对话中的经验沉淀到你的 Obsidian 笔记库——踩过的坑、可复用的命令、关键决策，不再随会话结束而丢失。

## 中文

### 这是什么

一个 Claude Code skill。对话结束后执行 `/save-memory`，它会按白名单规则提取对话中值得长期记住的知识（踩坑与解法、可复用命令/配置、决策及理由、被推翻的认知、项目事实），去重合并后写入你 Obsidian vault 的 `AI记忆/` 目录；执行 `/recall` 则按当前任务关键词检索历史记忆注入上下文。

笔记通过 `[[双链]]` 和 frontmatter 类型化边（`related` / `solved_by` / `supersedes` / `part_of`）融入你已有的知识图谱，在 Obsidian 的 Graph View 中可以看到记忆的生长。

### 为什么不是 MCP server

MCP server 拿不到对话历史——工具只接收模型调用时传入的参数。"总结对话"必须由模型完成，而 Claude Code 内置的文件工具已经覆盖读写需求。所以这是一个零依赖的纯 skill：没有脚本、没有 server、clone 即用。

### 安装

```bash
git clone https://github.com/mason/obsidian-memory-skill.git
# 或直接下载
mkdir -p ~/.claude/skills/save-memory/references
cp obsidian-memory-skill/SKILL.md ~/.claude/skills/save-memory/
cp obsidian-memory-skill/references/*.md ~/.claude/skills/save-memory/references/
```

然后**修改一处配置**：打开 `~/.claude/skills/save-memory/SKILL.md`，把"配置"区的 VAULT 路径改成你的 Obsidian 仓库路径。

重启 Claude Code 会话即可生效。

### 使用

```
/save-memory   # 总结当前对话 → 提取 → 去重合并 → 写入 Obsidian
/recall        # 按当前任务关键词检索历史记忆
```

skill 的 description 包含了触发提示：当你的任务涉及历史经验（再次遇到某个报错、重启某个话题）时，Claude 会主动建议召回相关笔记。

### 笔记长什么样

```markdown
---
tags: [openspec, cli]
source: claude-code
created: 2026-11-08
updated: 2026-11-08
---

# OpenSpec 使用经验

## 一句话结论
...

## 详情
### 2026-11-08 补充
...

## 相关
- 详见 [[MCP架构认知]]
```

### 写入边界（安全）

- 只写入 vault 的 `AI记忆/` 目录，vault 其他内容只读（可双链、不可修改）
- 密钥、密码、token 等敏感信息无例外地不写入
- 笔记语言跟随你的对话语言

### 路线图

- [ ] v2：SessionEnd hook，会话结束自动总结
- [ ] v2：`graph.py` 图谱遍历，多跳召回（捞回你没想到要搜的相关笔记）
- [ ] v2+：MOC 主题枢纽笔记自动维护
- [ ] 视反馈：MCP server 版本

本项目使用 [OpenSpec](https://github.com/Fission-AI/OpenSpec) 做规格驱动开发，规格见 `openspec/` 目录。

---

## English

### What it is

A Claude Code skill that captures durable knowledge from your conversations — pitfalls and fixes, reusable commands, decisions and their rationale — into your Obsidian vault. Run `/save-memory` to extract, dedupe, and write notes into `AI记忆/`; run `/recall` to inject relevant past notes into context.

Notes integrate with your existing knowledge graph via `[[wikilinks]]` and typed frontmatter edges (`related` / `solved_by` / `supersedes` / `part_of`), visible in Obsidian's Graph View.

### Why not an MCP server

MCP servers can't see conversation history — tools only receive arguments passed by the model. Summarization must be done by the model itself, and Claude Code's built-in file tools already cover reading and writing. Hence a zero-dependency pure skill: no scripts, no server, clone and go.

### Install

```bash
git clone https://github.com/mason/obsidian-memory-skill.git
mkdir -p ~/.claude/skills/save-memory/references
cp obsidian-memory-skill/SKILL.md ~/.claude/skills/save-memory/
cp obsidian-memory-skill/references/*.md ~/.claude/skills/save-memory/references/
```

Then edit the VAULT path in the config section of `~/.claude/skills/save-memory/SKILL.md`, and restart your Claude Code session.

### Usage

```
/save-memory   # extract → dedupe/merge → write to Obsidian
/recall        # search past notes by current task keywords
```

The skill's description includes trigger phrases, so Claude proactively suggests recalling notes when a task touches past experience.

### Write boundary (safety)

- Writes only to `AI记忆/` inside your vault; everything else is read-only (linkable, never modified)
- Secrets (keys, passwords, tokens) are never written, no exceptions
- Notes follow your conversation language

### Roadmap

- [ ] v2: SessionEnd hook for automatic summarization
- [ ] v2: `graph.py` multi-hop graph recall
- [ ] v2+: automatic MOC hub notes
- [ ] Maybe: an MCP server variant

Spec-driven with [OpenSpec](https://github.com/Fission-AI/OpenSpec); see `openspec/`.

## License

MIT
