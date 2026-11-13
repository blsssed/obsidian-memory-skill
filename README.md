# save-memory · Obsidian 对话记忆

把对话里的经验沉淀进你的 Obsidian 笔记库——踩过的坑、可复用的命令、关键决策——让它们不随会话结束而消失。

一个与宿主无关的 skill：引擎是一条零依赖命令，Claude Code、Codex CLI 共用同一份代码。

[中文](#中文) | [English](#english)

---

## 中文

### 它解决什么问题

你大概率遇到过这种情况：三个月前踩过一个坑，当时折腾了半天解决，现在又撞上了——但你不记得当时是怎么解决的，模型更不记得。

`save-memory` 做两件事：

1. **把值得留的东西写进你的 Obsidian**——踩坑与解法、可复用的命令/配置、决策及理由、被推翻的认知、项目事实
2. **在下次遇到相关问题时把它捞回来**——不是 `grep`，是同义词扩词 + 三通道打分 + 知识图谱扩展

知识以普通 Markdown 笔记的形式躺在 `AI记忆/` 里，通过 `[[双链]]` 和 frontmatter 类型化边融入你已有的知识图谱，在 Obsidian 的 Graph View 里能看到它在生长。**数据完全属于你**，不经过任何服务器。

### 三条命令的心智模型

| 命令 | 作用 | 类比 |
|---|---|---|
| `brief` | 列出记忆库目录（标题 + tags + 更新时间，不读正文） | 翻书目录 |
| `recall <关键词>` | 打分排序后返回正文 + 相关邻居 | 查索引找到具体章节 |
| `save`（流程） | 提取 → 去重合并 → 写入笔记 | 写完一章归档 |

`brief` 和 `recall` 是两件事：前者让模型**知道有哪些记忆**，后者才**把内容取出来**。没有 `brief`，记忆库对模型是隐形的。

### 安装

**Claude Code**

```bash
# 方式一：plugin
claude plugin marketplace add https://github.com/blsssed/obsidian-memory-skill
claude plugin install save-memory@save-memory

# 方式二：手动（目录自包含，复制或链接都行）
git clone https://github.com/blsssed/obsidian-memory-skill.git
cp -r obsidian-memory-skill/skills/save-memory ~/.claude/skills/
```

**Codex CLI**（v0.119.0 实测，详见 [docs/hosts-codex.md](docs/hosts-codex.md)）

```powershell
mklink /J "$env:USERPROFILE\.codex\skills\save-memory" "<仓库路径>\skills\save-memory"
```

**其他宿主**：skill 目录是自包含的（`SKILL.md` + `engine/` + `workflows/` + `references/`），整个复制或链接到宿主的 skills 目录即可。`SKILL.md` 的 frontmatter 只需 `name` + `description`。

### 配置

最小配置就是一个 vault 路径，写到状态目录下的 `save-memory.json`：

```json
{ "vault": "<Obsidian 仓库路径>", "memory_dir": "AI记忆", "snippet_dir": "snippets" }
```

**查找顺序**（`mem.py` 未配置时会直接打印期望路径）：

```
--vault 参数  >  SAVE_MEMORY_VAULT 环境变量  >  配置文件  >  内置默认
```

配置文件的位置由**状态目录**决定：

```
SAVE_MEMORY_HOME  >  ~/.claude（历史位置）  >  ~/.save-memory
```

### 多宿主共存

同一台机器装多个 agent 时，两种做法：

**共用**（默认）—— 两边共用一个库、一份缓存，改一次两边都受益。

**各用一个库** —— 各给一套状态目录 + 配置文件：

```bash
export SAVE_MEMORY_HOME=~/.save-memory-codex     # Windows: $env:SAVE_MEMORY_HOME="..."
```

```json
{ "vault": "<codex 专用 vault>", "memory_dir": "AI记忆", "snippet_dir": "snippets" }
```

笔记、图谱缓存、`recall_count` 完全隔离。

> `SAVE_MEMORY_HOME` 是**进程级**的：只在 Codex 里设，Claude 仍走默认 `~/.claude`。也可以在单条命令上用 `--vault` 覆盖，不依赖环境变量。

### 命令参考

`<引擎>` = `<skill目录>/engine/mem.py`。

```
py -3 <引擎> brief [-n 40]              # 记忆索引（标题 | tags | updated）
py -3 <引擎> find <关键词...>            # 轻量定位：只出得分/标题/路径
py -3 <引擎> recall <关键词...> [--record]   # 混合召回；--record 顺带记 recall_count
py -3 <引擎> expand <笔记> [-d N]        # 从某篇出发看它连着谁
py -3 <引擎> check                       # 全库体检：红链 / 跨目录 / 可疑别名
py -3 <引擎> check-links <笔记...>       # 校验指定笔记的双链目标是否存在
py -3 <引擎> validate [--note 文件]      # 格式校验
py -3 <引擎> record <笔记名...>          # 手动维护 recall_count
py -3 <引擎> build                       # 重建/增量更新图谱缓存
```

这些命令**可以直接在终端跑**，不经过任何 agent——引擎是独立可用的。

### 工作方式

skill 内部三层：

```
skills/save-memory/
├── SKILL.md        薄壳：触发描述 + 命令索引 + 硬性约束
├── workflows/      流程：extract / recall / garden / setup
├── references/     策略：提取白名单、合并规则、笔记模板
└── engine/         引擎：mem.py / validate.py / state.py / memory_config.py
```

模型按用户意图加载对应的 `workflows/*.md`，再由它调用引擎命令。宿主专有的工具名（`Glob`/`Grep`）在流程里已替换成引擎子命令——没有命令执行能力的宿主会退化为文件搜索。

**记忆可见性**：`brief` 的输出由各宿主的常驻指令带到上下文里（Claude 用 `~/.claude/CLAUDE.md`，Codex 用 `~/.codex/AGENTS.md`），模型才知道"有这么个库"。

### 笔记长什么样

```markdown
---
tags: [openspec, cli]
source: claude-code
created: 2026-11-08
updated: 2026-11-08
recall_count: 2
related: ["[[相关笔记]]"]
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

类型化边：`related` / `solved_by` / `supersedes` / `superseded_by` / `part_of`。写盘后会跑 `validate` 做确定性格式校验（frontmatter 必填、文件名合法性、UTF-8 无 BOM、高频泛词警告）——规则不只靠模型自觉。

### 安全边界

- **只写入 `AI记忆/`**；vault 其他内容只读。双链可以指向你的笔记，但链接只写在记忆笔记一侧，**绝不修改记忆目录以外的文件**（包括"为了建立双向链接"去编辑你的笔记）
- **敏感信息永不写入**：API key、密码、token、内网地址
- 笔记语言跟随你的对话语言
- 双 agent 并发写不会损坏数据：缓存与 `recall_count` 都是原子写，`recall_count` 额外加跨进程锁

### 测试

```bash
py -3 -m unittest discover -s tests        # Windows
python3 -m unittest discover -s tests      # macOS / Linux
```

81 个用例，标准库 `unittest`（不装 pytest），不需要预先配置 vault——每个用例自建隔离的临时库，不碰你真实的 Obsidian 仓库。

覆盖：frontmatter / 双链 / 代码段剥离、标签覆盖率与关键词词边界、种子打分与图谱扩展衰减、BOM 与同名笔记的构建、`record` 的正文保全与 BOM 保持、红链与跨目录检测、`validate` 的格式规则。

### 路线图

- [x] 图谱召回（`recall`）：同义词扩词 + 三通道打分 + 一跳扩展
- [x] 知识库体检（`check` / `validate` / `check-links`）
- [x] 配置外置 + 优先级链
- [x] plugin 打包
- [x] `recall_count` 使用统计 + 零召回园艺报告
- [x] **移除 hooks**，引擎与宿主解耦（`SAVE_MEMORY_HOME` + 状态目录）
- [x] `brief` / `find` / `check-links` / `validate` 子命令——能力不再依赖宿主专有工具
- [x] 81 个单测，锁住 BOM / 同名笔记 / 词边界 / 覆盖率阈值
- [x] **Codex CLI 适配**（按需加载 + 沙箱内可执行引擎）
- [x] 并发写保护（原子写 + 跨进程锁）
- [ ] 缓存改增量存储（触发条件：笔记数达到数百篇）
- [ ] 语义检索（触发条件：500+ 篇；打分管线已解耦，可整体替换匹配器）
- [ ] 视反馈：MCP server 版本

### 为什么不是 MCP server

MCP server 拿不到对话历史——工具只接收模型调用时传入的参数。"总结对话"必须由模型完成，而宿主内置的文件工具已经覆盖读写需求。所以这是一个纯 skill：没有常驻服务，唯一的外部依赖是 Python 标准库。

本项目用 [OpenSpec](https://github.com/Fission-AI/OpenSpec) 做规格驱动开发，规格见 `openspec/`。

---

## English

### What problem it solves

You hit the same error you fixed three months ago, and you can't remember how — and neither can the model.

`save-memory` does two things:

1. **Writes what's worth keeping into your Obsidian vault** — pitfalls and fixes, reusable commands, decisions and their rationale, corrected beliefs, project facts
2. **Brings them back when a related task shows up** — synonym expansion + three-channel scoring + knowledge-graph expansion, not `grep`

Notes are plain Markdown under `AI记忆/`, wired into your existing graph via `[[wikilinks]]` and typed frontmatter edges. **The data stays yours** — nothing leaves your machine.

### The three-command mental model

| Command | Does | Analogy |
|---|---|---|
| `brief` | Lists the memory index (title + tags + updated, no bodies) | Table of contents |
| `recall <keywords>` | Ranked scoring, returns bodies + neighbours | Look up a chapter |
| `save` (workflow) | Extract → dedupe/merge → write | File a new chapter |

`brief` and `recall` are different jobs: the former tells the model **what memories exist**, the latter **fetches the content**. Without `brief`, the whole vault is invisible to the model.

### Install

**Claude Code**

```bash
# Option 1: plugin
claude plugin marketplace add https://github.com/blsssed/obsidian-memory-skill
claude plugin install save-memory@save-memory

# Option 2: manual (self-contained; copy or link it anywhere)
git clone https://github.com/blsssed/obsidian-memory-skill.git
cp -r obsidian-memory-skill/skills/save-memory ~/.claude/skills/
```

**Codex CLI** (verified against v0.119.0 — see [docs/hosts-codex.md](docs/hosts-codex.md))

```powershell
mklink /J "$env:USERPROFILE\.codex\skills\save-memory" "<repo>\skills\save-memory"
```

**Other hosts**: the directory is self-contained (`SKILL.md` + `engine/` + `workflows/` + `references/`) — copy or link the whole thing into the host's skills directory. The frontmatter only needs `name` + `description`.

### Configuration

The minimum is one vault path, written to `save-memory.json` inside the state directory:

```json
{ "vault": "<Obsidian vault path>", "memory_dir": "AI记忆", "snippet_dir": "snippets" }
```

**Lookup order** (`mem.py` prints the expected path when unconfigured):

```
--vault flag  >  SAVE_MEMORY_VAULT env  >  config file  >  built-in default
```

The config file's location follows the **state directory**:

```
SAVE_MEMORY_HOME  >  ~/.claude (legacy)  >  ~/.save-memory
```

### Multiple hosts

**Shared** (default) — one vault, one cache, both agents benefit from each other's notes.

**Separate vaults** — one state directory + config each:

```bash
export SAVE_MEMORY_HOME=~/.save-memory-codex     # Windows: $env:SAVE_MEMORY_HOME="..."
```

```json
{ "vault": "<codex-only vault>", "memory_dir": "AI记忆", "snippet_dir": "snippets" }
```

Notes, graph cache and `recall_count` become fully isolated.

> `SAVE_MEMORY_HOME` is **process-level**: set it only in Codex and Claude keeps using `~/.claude`. You can also override per command with `--vault`, no env var needed.

### Command reference

`<engine>` = `<skill-dir>/engine/mem.py`.

```
py -3 <engine> brief [-n 40]                # memory index (title | tags | updated)
py -3 <engine> find <keywords...>           # locate notes without injecting bodies
py -3 <engine> recall <keywords...> [--record]  # hybrid recall; --record bumps recall_count
py -3 <engine> expand <note> [-d N]         # what a note connects to
py -3 <engine> check                        # red links / cross-dir / suspicious aliases
py -3 <engine> check-links <notes...>       # verify wikilink targets exist
py -3 <engine> validate [--note file]       # format checks
py -3 <engine> record <notes...>            # manual recall_count maintenance
py -3 <engine> build                        # rebuild / incrementally update the cache
```

These run **straight from a terminal** — the engine is useful without any agent.

### How it's structured

```
skills/save-memory/
├── SKILL.md        thin shell: trigger description + command index + hard rules
├── workflows/      procedures: extract / recall / garden / setup
├── references/     policies: extraction whitelist, merge rules, note template
└── engine/         the engine: mem.py / validate.py / state.py / memory_config.py
```

The model loads the matching `workflows/*.md`, then calls the engine. Host-specific tool names (`Glob`/`Grep`) have been replaced with engine subcommands — hosts without command execution degrade to file search.

**Memory visibility**: `brief` output is carried into context by each host's standing instructions (`~/.claude/CLAUDE.md` for Claude, `~/.codex/AGENTS.md` for Codex).

### What a note looks like

```markdown
---
tags: [openspec, cli]
source: claude-code
created: 2026-11-08
updated: 2026-11-08
recall_count: 2
related: ["[[another-note]]"]
---

# OpenSpec usage notes

## One-line conclusion
...

## Details
### 2026-11-08 addendum
...

## Related
- see [[MCP architecture notes]]
```

Typed edges: `related` / `solved_by` / `supersedes` / `superseded_by` / `part_of`. After writing, `validate` runs deterministic format checks (required frontmatter, filename legality, UTF-8 without BOM, generic-word warnings) — the rules don't rely on the model's diligence alone.

### Safety boundaries

- **Writes only to `AI记忆/`**; everything else in the vault is read-only. Wikilinks may point at your notes, but they're written only on the memory side — **no file outside the memory directory is ever modified** (including "for symmetry" edits)
- **Secrets are never written**: API keys, passwords, tokens, internal addresses
- Notes follow your conversation language
- Concurrent writes from two agents can't corrupt data: cache and `recall_count` use atomic writes, with a cross-process lock around `recall_count`

### Tests

```bash
python3 -m unittest discover -s tests
```

81 cases, stdlib `unittest` only (no pytest), no vault setup needed — every case builds its own throwaway vault and never touches your real Obsidian repo.

Covered: frontmatter / wikilink / code-fence parsing, tag coverage and keyword word boundaries, seed scoring and hop decay, graph building with BOM and duplicate names, `record` body preservation and BOM retention, red-link and cross-directory detection, `validate`'s format rules.

### Roadmap

- [x] Graph recall (`recall`): synonym expansion + three-channel scoring + one-hop expansion
- [x] Health checks (`check` / `validate` / `check-links`)
- [x] Externalized config + priority chain
- [x] Plugin packaging
- [x] `recall_count` usage stats + zero-recall garden report
- [x] **Hooks removed**; engine decoupled from the host (`SAVE_MEMORY_HOME` + state directory)
- [x] `brief` / `find` / `check-links` / `validate` subcommands — no host-specific tools required
- [x] 81 unit tests pinning BOM / duplicate names / word boundaries / coverage threshold
- [x] **Codex CLI adapter** (on-demand loading + engine executable inside the sandbox)
- [x] Concurrent-write protection (atomic writes + cross-process lock)
- [ ] Incremental cache storage (trigger: several hundred notes)
- [ ] Semantic retrieval (trigger: 500+ notes; the scoring pipeline is already decoupled from the matcher)
- [ ] Maybe: an MCP server variant

### Why not an MCP server

MCP servers can't see conversation history — tools only receive arguments passed by the model. Summarization must be done by the model itself, and the host's built-in file tools already cover reading and writing. Hence a pure skill: no resident service, and the only external dependency is Python's standard library.

Spec-driven with [OpenSpec](https://github.com/Fission-AI/OpenSpec); see `openspec/`.

## License

MIT
