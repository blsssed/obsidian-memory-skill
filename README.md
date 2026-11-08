# save-memory · Obsidian 对话记忆

[中文](#中文) | [English](#english)

把 Claude Code 对话中的经验沉淀到你的 Obsidian 笔记库——踩过的坑、可复用的命令、关键决策，不再随会话结束而丢失。

## 中文

### 这是什么

一个 Claude Code skill。执行 `/save-memory`，它会按白名单规则提取对话中值得长期记住的知识（踩坑与解法、可复用命令/配置、决策及理由、被推翻的认知、项目事实），去重合并后写入你 Obsidian vault 的 `AI记忆/` 目录。

- `/recall` 不再是简单 Grep：同义词扩词 → 标签/正文双通道种子计分 → 知识图谱一跳扩展（跳数衰减 × 边类型系数）→ 总分排序、字数预算输出。同义词表能把"限流"捞回只写了"429"的笔记，图谱能把你想不到去搜的相关笔记一并带出来。
- `/garden-memory` 知识库体检：红链检测、跨目录可疑链接、碎片笔记合并建议、同义 tags 归并、超载域笔记拆分、长期零召回笔记——只报告，逐项确认后才修复。
- `/save-memory-setup` 一次性对话式配置：问 vault 路径、验证、写配置文件，零 GUI。
- 可选开启 hooks 后全自动：会话结束（≥5 轮用户消息）自动总结写入，会话开始注入记忆索引。**hooks 默认不启用**，理由见下文。

笔记通过 `[[双链]]` 和 frontmatter 类型化边（`related` / `solved_by` / `supersedes` / `part_of`）融入你已有的知识图谱，在 Obsidian 的 Graph View 中可以看到记忆的生长。

### 为什么不是 MCP server

MCP server 拿不到对话历史——工具只接收模型调用时传入的参数。"总结对话"必须由模型完成，而 Claude Code 内置的文件工具已经覆盖读写需求。所以这是一个纯 skill：没有 server，唯一的脚本（`graph.py`）零第三方依赖，纯标准库。

### 安装

**方式一：plugin（推荐）**

```bash
claude plugin marketplace add mason/obsidian-memory-skill
claude plugin install save-memory@save-memory
```

装好后技能名为 `save-memory:save-memory`（plugin 带命名空间）。更新：`claude plugin update save-memory`。

**方式二：手动复制**（路径固定，适合想启用 hooks 的用户）

```bash
git clone https://github.com/mason/obsidian-memory-skill.git
mkdir -p ~/.claude/skills/save-memory
cp -r obsidian-memory-skill/skills/save-memory/* ~/.claude/skills/save-memory/
```

重启 Claude Code 会话后，首次运行 `/save-memory-setup`（或 `/save-memory` 按提示）完成配置：

```json
// ~/.claude/save-memory.json
{ "vault": "C:/Users/you/Documents/Obsidian Vault", "memory_dir": "AI记忆", "snippet_dir": "snippets" }
```

配置优先级：命令行 `--vault` > 环境变量 `SAVE_MEMORY_VAULT` > 配置文件 > 内置默认；文件不存在或 JSON 损坏时自动降级，工具不崩。

### 可选：hooks 自动化（默认关闭，显式开启）

装了 skill **不会**自动运行任何 hook。想要"会话结束自动总结 + 会话开始注入索引"，把下面两段注册进 `~/.claude/settings.json`（与已有的 `"hooks"` 键合并）：

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

- 上面的路径对应**方式二手动安装**。用 plugin 安装的用户如需 hooks：`claude plugin list --json` 查 `installPath`，把路径替换进命令——注意缓存路径带版本号，plugin 升级后需重新注册
- **SessionEnd 自动总结**：会话结束时统计用户消息轮数，<5 轮跳过（零成本）；≥5 轮以嵌套 headless 会话按 skill 的提取规则总结写入。带防递归标记和超时保护，`async` 运行不阻塞会话退出。macOS/Linux 用户把 `py -3` 换成 `python3`
- **SessionStart 索引注入**：新会话启动/恢复时注入记忆索引（标题 | tags | 更新时间，上限 40 行）
- 日志在 `~/.claude/save-memory.log`，每行带 `action=skip|done|fail` 三态与轮数，排障直接 grep

### 使用

```
/save-memory        # 总结当前对话 → 提取 → 去重合并 → 写入 Obsidian
/recall             # 图谱混合召回：扩词 → 双通道计分 → 一跳扩展
/garden-memory      # 知识库体检：红链 / 可疑链接 / 碎片 / tags / 零召回
/save-memory-setup  # 一次性配置：vault 路径 / 记忆目录
```

skill 的 description 包含了触发提示：当你的任务涉及历史经验（再次遇到某个报错、重启某个话题）时，Claude 会主动建议召回相关笔记。

### 笔记长什么样

```markdown
---
tags: [openspec, cli]
source: claude-code
created: 2026-11-08
updated: 2026-11-08
recall_count: 2
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

写入后 skill 会对新文件跑 `scripts/validate.py` 做确定性格式校验（frontmatter 必填字段、文件名合法性、UTF-8 无 BOM、高频泛词警告）——规则不再只靠模型自觉。

### 写入边界（安全）

- 只写入 vault 的 `AI记忆/` 目录；vault 其他内容只读——双链可以指向你的笔记，但链接只写在记忆笔记一侧，**绝不修改 `AI记忆/` 以外的文件**（包括"为建双向链接"而编辑你的笔记）
- 密钥、密码、token 等敏感信息无例外地不写入
- 笔记语言跟随你的对话语言

### 路线图

- [x] v2：SessionEnd hook，会话结束自动总结（<5 轮自动跳过）
- [x] v2：SessionStart hook，记忆索引注入
- [x] v2：`graph.py` 图谱遍历，多跳召回（捞回你没想到要搜的相关笔记）
- [x] v2：`/garden-memory` 知识库体检
- [x] v3：配置外置（`~/.claude/save-memory.json` 优先级链）+ 对话式安装 `/save-memory-setup`
- [x] v3：plugin 打包（hooks 默认关闭，显式 opt-in）
- [x] v3：`validate.py` 写入校验下沉
- [x] v3：`recall_count` 使用统计 + 零召回园艺报告
- [ ] 后续：语义检索（触发条件：500+ 篇笔记，打分管线已解耦）
- [ ] 视反馈：MCP server 版本

本项目使用 [OpenSpec](https://github.com/Fission-AI/OpenSpec) 做规格驱动开发，规格见 `openspec/` 目录。

---

## English

### What it is

A Claude Code skill that captures durable knowledge from your conversations — pitfalls and fixes, reusable commands, decisions and their rationale — into your Obsidian vault. Run `/save-memory` to extract, dedupe, and write notes into `AI记忆/`.

- `/recall` goes beyond plain Grep: synonym expansion → tag/body dual-channel seed scoring → one-hop graph expansion (hop decay × edge-type coefficient) → ranked output within a character budget. Synonym groups recall the note that only mentions "429" when you search "rate limit"; graph hops bring in related notes you didn't think to search for.
- `/garden-memory` health-checks your knowledge base: red links, cross-directory suspicious links, thin-note merge suggestions, synonym tag unification, oversized domain-note split suggestions, long-term zero-recall notes — report-only, fixes applied item by item after your confirmation.
- `/save-memory-setup` is a one-time conversational setup: asks for your vault path, validates it, writes the config file. No GUI.
- Optional hooks: sessions end (≥5 user rounds) are summarized automatically, and every new session starts with a memory index injected. **Hooks are off by default** — see below.

Notes integrate with your existing knowledge graph via `[[wikilinks]]` and typed frontmatter edges (`related` / `solved_by` / `supersedes` / `part_of`), visible in Obsidian's Graph View.

### Why not an MCP server

MCP servers can't see conversation history — tools only receive arguments passed by the model. Summarization must be done by the model itself, and Claude Code's built-in file tools already cover reading and writing. Hence a pure skill: no server, and the only script (`graph.py`) is stdlib-only with zero third-party dependencies.

### Install

**Option 1: plugin (recommended)**

```bash
claude plugin marketplace add mason/obsidian-memory-skill
claude plugin install save-memory@save-memory
```

The skill is then available as `save-memory:save-memory` (plugin namespace). Update with `claude plugin update save-memory`.

**Option 2: manual copy** (fixed paths; best if you want hooks)

```bash
git clone https://github.com/mason/obsidian-memory-skill.git
mkdir -p ~/.claude/skills/save-memory
cp -r obsidian-memory-skill/skills/save-memory/* ~/.claude/skills/save-memory/
```

Restart Claude Code, then run `/save-memory-setup` once (or let `/save-memory` prompt you):

```json
// ~/.claude/save-memory.json
{ "vault": "C:/Users/you/Documents/Obsidian Vault", "memory_dir": "AI记忆", "snippet_dir": "snippets" }
```

Priority: `--vault` flag > `SAVE_MEMORY_VAULT` env var > config file > built-in defaults. A missing or malformed config degrades silently — tools never crash on it.

### Optional: hooks automation (off by default, explicit opt-in)

Installing the skill **never** runs any hook by itself. For "summarize on session end + inject the index on start", register these in `~/.claude/settings.json` (merge with an existing `"hooks"` key):

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

- The path above matches **Option 2 (manual install)**. Plugin users who want hooks: get `installPath` from `claude plugin list --json` and substitute it — note the cache path contains the version, so re-register after a plugin update
- **SessionEnd auto-summary**: counts user rounds at session end; <5 rounds is skipped (zero cost); ≥5 rounds runs the extraction flow in a nested headless session. Recursion-guarded and timeout-protected; `async` so it never blocks session exit. Windows users: use `py -3` instead of `python3`
- **SessionStart index injection**: injects a compact memory index (title | tags | updated, up to 40 rows) on startup/resume
- Logs go to `~/.claude/save-memory.log`, one line per event with `action=skip|done|fail` and the round count — grep it for troubleshooting

### Usage

```
/save-memory        # extract → dedupe/merge → write to Obsidian
/recall             # graph hybrid recall: expand → dual-channel scoring → one-hop expansion
/garden-memory      # health check: red links / suspicious links / thin notes / tags / zero-recall
/save-memory-setup  # one-time setup: vault path / memory dir
```

The skill's description includes trigger phrases, so Claude proactively suggests recalling notes when a task touches past experience.

### What a note looks like

```markdown
---
tags: [openspec, cli]
source: claude-code
created: 2026-11-08
updated: 2026-11-08
recall_count: 2
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

After writing, the skill runs `scripts/validate.py` for deterministic format checks (required frontmatter fields, filename legality, UTF-8 without BOM, generic-word warnings) — the rules no longer rely on the model's diligence alone.

### Write boundary (safety)

- Writes only to `AI记忆/` inside your vault; everything else is read-only — wikilinks may point at your notes, but they are written only on the memory-note side. **No file outside `AI记忆/` is ever modified** (including "for symmetry" edits to your own notes)
- Secrets (keys, passwords, tokens) are never written, no exceptions
- Notes follow your conversation language

### Roadmap

- [x] v2: SessionEnd hook for automatic summarization (<5 rounds skipped)
- [x] v2: SessionStart hook injecting a memory index
- [x] v2: `graph.py` multi-hop graph recall
- [x] v2: `/garden-memory` knowledge-base health check
- [x] v3: externalized config (`~/.claude/save-memory.json` priority chain) + conversational `/save-memory-setup`
- [x] v3: plugin packaging (hooks off by default, explicit opt-in)
- [x] v3: `validate.py` format checks after writes
- [x] v3: `recall_count` usage stats + zero-recall garden report
- [ ] Later: semantic retrieval (trigger: 500+ notes; the scoring pipeline is already decoupled)
- [ ] Maybe: an MCP server variant

Spec-driven with [OpenSpec](https://github.com/Fission-AI/OpenSpec); see `openspec/`.

## License

MIT
