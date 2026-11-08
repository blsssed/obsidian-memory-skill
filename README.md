# save-memory · Obsidian 对话记忆

[中文](#中文) | [English](#english)

把 Claude Code 对话中的经验沉淀到你的 Obsidian 笔记库——踩过的坑、可复用的命令、关键决策，不再随会话结束而丢失。

## 中文

### 这是什么

一个 Claude Code skill。执行 `/save-memory`，它会按白名单规则提取对话中值得长期记住的知识（踩坑与解法、可复用命令/配置、决策及理由、被推翻的认知、项目事实），去重合并后写入你 Obsidian vault 的 `AI记忆/` 目录。

- `/recall` 不再是简单 Grep：同义词扩词 → 标签/正文双通道种子计分 → 知识图谱一跳扩展（跳数衰减 × 边类型系数）→ 总分排序、字数预算输出。同义词表能把"限流"捞回只写了"429"的笔记，图谱能把你想不到去搜的相关笔记一并带出来。
- `/garden-memory` 知识库体检：红链检测、碎片笔记合并建议、同义 tags 归并、超载域笔记拆分建议——只报告，逐项确认后才修复。
- 装上 hooks 后全自动：会话结束（≥5 轮用户消息）自动总结写入，会话开始注入记忆索引。

笔记通过 `[[双链]]` 和 frontmatter 类型化边（`related` / `solved_by` / `supersedes` / `part_of`）融入你已有的知识图谱，在 Obsidian 的 Graph View 中可以看到记忆的生长。

### 为什么不是 MCP server

MCP server 拿不到对话历史——工具只接收模型调用时传入的参数。"总结对话"必须由模型完成，而 Claude Code 内置的文件工具已经覆盖读写需求。所以这是一个纯 skill：没有 server，唯一的脚本（`graph.py`）零第三方依赖，纯标准库。

### 安装

```bash
git clone https://github.com/mason/obsidian-memory-skill.git
mkdir -p ~/.claude/skills/save-memory/references ~/.claude/skills/save-memory/scripts ~/.claude/skills/save-memory/hooks
cp obsidian-memory-skill/SKILL.md ~/.claude/skills/save-memory/
cp obsidian-memory-skill/references/*.md ~/.claude/skills/save-memory/references/
cp obsidian-memory-skill/scripts/graph.py ~/.claude/skills/save-memory/scripts/
cp obsidian-memory-skill/hooks/*.py ~/.claude/skills/save-memory/hooks/
```

然后**修改一处配置**：打开 `~/.claude/skills/save-memory/SKILL.md`，把"配置"区的 VAULT 路径改成你的 Obsidian 仓库路径。

重启 Claude Code 会话即可生效。手动流程（`/save-memory`、`/recall`、`/garden-memory`）不需要任何额外配置；要启用自动化闭环，再把下面两段 hooks 注册进 `~/.claude/settings.json`（与已有的 `"hooks"` 键合并）：

```json
{
  "hooks": {
    "SessionEnd": [
      { "hooks": [ { "type": "command",
        "command": "py -3 \"$HOME/.claude/skills/save-memory/hooks/session_end.py\"",
        "timeout": 300, "async": true } ] }
    ],
    "SessionStart": [
      { "matcher": "startup|resume", "hooks": [ { "type": "command",
        "command": "py -3 \"$HOME/.claude/skills/save-memory/hooks/session_start.py\"" } ] }
    ]
  }
}
```

hooks 说明：

- **SessionEnd 自动总结**：会话结束时统计用户消息轮数，<5 轮静默跳过（零成本）；≥5 轮以嵌套 headless 会话按 skill 的提取规则总结写入。带防递归标记和超时保护，`async` 运行不阻塞会话退出。macOS/Linux 用户把 `py -3` 换成 `python3`。
- **SessionStart 索引注入**：新会话启动/恢复时注入记忆索引（标题 | tags | 更新时间，上限 40 行），让 Claude 知道已有哪些记忆；内容仍按需经 `/recall` 深读。
- 日志在 `~/.claude/save-memory.log`，排障看这里。

### 使用

```
/save-memory     # 总结当前对话 → 提取 → 去重合并 → 写入 Obsidian
/recall          # 图谱混合召回：扩词 → 双通道计分 → 一跳扩展
/garden-memory   # 知识库体检：红链 / 碎片 / tags / 域笔记拆分建议
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

- 只写入 vault 的 `AI记忆/` 目录；vault 其他内容只读——双链可以指向你的笔记，但链接只写在记忆笔记一侧，**绝不修改 `AI记忆/` 以外的文件**（包括"为建双向链接"而编辑你的笔记）
- 密钥、密码、token 等敏感信息无例外地不写入
- 笔记语言跟随你的对话语言

### 路线图

- [x] v2：SessionEnd hook，会话结束自动总结（<5 轮自动跳过）
- [x] v2：SessionStart hook，记忆索引注入
- [x] v2：`graph.py` 图谱遍历，多跳召回（捞回你没想到要搜的相关笔记）
- [x] v2：`/garden-memory` 知识库体检
- [ ] v3：配置外置 + 多 vault、plugin 打包、validate.py 校验下沉、语义检索、recall_count 使用统计
- [ ] 视反馈：MCP server 版本

本项目使用 [OpenSpec](https://github.com/Fission-AI/OpenSpec) 做规格驱动开发，规格见 `openspec/` 目录。

---

## English

### What it is

A Claude Code skill that captures durable knowledge from your conversations — pitfalls and fixes, reusable commands, decisions and their rationale — into your Obsidian vault. Run `/save-memory` to extract, dedupe, and write notes into `AI记忆/`.

- `/recall` goes beyond plain Grep: synonym expansion → tag/body dual-channel seed scoring → one-hop graph expansion (hop decay × edge-type coefficient) → ranked output within a character budget. Synonym groups recall the note that only mentions "429" when you search "rate limit"; graph hops bring in related notes you didn't think to search for.
- `/garden-memory` health-checks your knowledge base: red links, thin-note merge suggestions, synonym tag unification, oversized domain-note split suggestions — report-only, fixes applied item by item after your confirmation.
- With hooks installed, it runs itself: sessions end (≥5 user rounds) are summarized automatically, and every new session starts with a memory index injected.

Notes integrate with your existing knowledge graph via `[[wikilinks]]` and typed frontmatter edges (`related` / `solved_by` / `supersedes` / `part_of`), visible in Obsidian's Graph View.

### Why not an MCP server

MCP servers can't see conversation history — tools only receive arguments passed by the model. Summarization must be done by the model itself, and Claude Code's built-in file tools already cover reading and writing. Hence a pure skill: no server, and the only script (`graph.py`) is stdlib-only with zero third-party dependencies.

### Install

```bash
git clone https://github.com/mason/obsidian-memory-skill.git
mkdir -p ~/.claude/skills/save-memory/references ~/.claude/skills/save-memory/scripts ~/.claude/skills/save-memory/hooks
cp obsidian-memory-skill/SKILL.md ~/.claude/skills/save-memory/
cp obsidian-memory-skill/references/*.md ~/.claude/skills/save-memory/references/
cp obsidian-memory-skill/scripts/graph.py ~/.claude/skills/save-memory/scripts/
cp obsidian-memory-skill/hooks/*.py ~/.claude/skills/save-memory/hooks/
```

Then edit the VAULT path in the config section of `~/.claude/skills/save-memory/SKILL.md`, and restart your Claude Code session. The manual commands (`/save-memory`, `/recall`, `/garden-memory`) need nothing else. To enable the automation loop, register the hooks below in `~/.claude/settings.json` (merge with an existing `"hooks"` key):

```json
{
  "hooks": {
    "SessionEnd": [
      { "hooks": [ { "type": "command",
        "command": "python3 \"$HOME/.claude/skills/save-memory/hooks/session_end.py\"",
        "timeout": 300, "async": true } ] }
    ],
    "SessionStart": [
      { "matcher": "startup|resume", "hooks": [ { "type": "command",
        "command": "python3 \"$HOME/.claude/skills/save-memory/hooks/session_start.py\"" } ] }
    ]
  }
}
```

Hook notes:

- **SessionEnd auto-summary**: counts user rounds at session end; <5 rounds exits silently (zero cost); ≥5 rounds runs the extraction flow in a nested headless session. Recursion-guarded and timeout-protected; `async` so it never blocks session exit. Windows users: use `py -3` instead of `python3`.
- **SessionStart index injection**: injects a compact memory index (title | tags | updated, up to 40 rows) on startup/resume so Claude knows what memory exists; content is still deep-read on demand via `/recall`.
- Logs go to `~/.claude/save-memory.log`.

### Usage

```
/save-memory     # extract → dedupe/merge → write to Obsidian
/recall          # graph hybrid recall: expand → dual-channel scoring → one-hop expansion
/garden-memory   # health check: red links / thin notes / tags / oversized domain notes
```

The skill's description includes trigger phrases, so Claude proactively suggests recalling notes when a task touches past experience.

### Write boundary (safety)

- Writes only to `AI记忆/` inside your vault; everything else is read-only — wikilinks may point at your notes, but they are written only on the memory-note side. **No file outside `AI记忆/` is ever modified** (including "for symmetry" edits to your own notes)
- Secrets (keys, passwords, tokens) are never written, no exceptions
- Notes follow your conversation language

### Roadmap

- [x] v2: SessionEnd hook for automatic summarization (<5 rounds skipped)
- [x] v2: SessionStart hook injecting a memory index
- [x] v2: `graph.py` multi-hop graph recall
- [x] v2: `/garden-memory` knowledge-base health check
- [ ] v3: externalized config + multi-vault, plugin packaging, validate.py, semantic retrieval, recall_count stats
- [ ] Maybe: an MCP server variant

Spec-driven with [OpenSpec](https://github.com/Fission-AI/OpenSpec); see `openspec/`.

## License

MIT
