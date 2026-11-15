# Codex CLI 适配

`save-memory` 在 Codex CLI 上的安装、加载机制与实测能力边界。结论均来自 Codex **v0.119.0** 的实机验证，不是推测。

## 安装

Codex 读 `~/.codex/skills/<name>/SKILL.md`，格式与 Claude Code 相同（frontmatter 只要 `name` + `description`）。skill 目录是自包含的，所以装法只有一步：**把整个目录放到那里**。

Windows（推荐 Junction，仓库是唯一真相，改一次两边生效）：

```powershell
mklink /J "$env:USERPROFILE\.codex\skills\save-memory" "C:\path\to\obsidian-memory-skill\skills\save-memory"
```

macOS / Linux：

```bash
ln -s /path/to/obsidian-memory-skill/skills/save-memory ~/.codex/skills/save-memory
```

不想用链接就直接复制——目录自包含，复制到哪都能跑。

确认装上：

```bash
ls ~/.codex/skills/save-memory      # 应看到 engine/ references/ workflows/ SKILL.md
```

## 加载机制（实测）

Codex 的 skill **按需加载**，这一点与 Claude Code 一致但表现不同：

- 会话上下文里能拿到：skill 的**名称、简要说明（description）、以及一个相对路径**（实测显示为 `r0/save-memory/SKILL.md`）
- 上下文里**没有** SKILL.md 的完整正文 —— 模型要自己读那个路径才会拿到流程
- 所以 `SKILL.md` 的 `description` 承担触发职责，而 `engine/`、`workflows/`、`references/` 只在真正执行时才被读取

这意味着**不需要往 `AGENTS.md` 写任何东西**。`~/.codex/AGENTS.md` 是常驻上下文，塞流程文本只会污染每次会话。

实测补充：

- 会话里能正常执行 `py -3 .../engine/mem.py brief` 与 `recall`，输出与终端一致（Codex 会话记录里可查到 `tools.exec_command` + `shell: powershell`）
- 自然语言请求（"帮我从 save-memory 的笔记里找出 429/重试相关经验"）能返回测试库里的笔记内容
- **未硬证的一环**：那次自然语言请求没有留下可查的命令记录，无法区分它是执行了 `recall` 还是直接读取了笔记文件。如果模型偶尔算不出引擎的绝对路径，显式给出一次路径（或先把 vault 写进配置文件）即可——路径推导本身不是确定性的

Codex 还支持在 skill 目录里放 `agents/openai.yaml` 声明 `interface.default_prompt`（形如 `Use $save-memory to ...`），本 skill 未提供：`SKILL.md` 的 `description` 已足够触发。

## 多库共存（本机实际配置）

Claude 与 Codex 各用一个 vault，靠状态目录 + 各自的 `save-memory.json` 隔离：

| 宿主 | 状态目录 | vault |
|---|---|---|
| Claude Code | `~/.claude` | `Documents\Obsidian Vault` |
| Codex | `~/.save-memory-codex` | `Documents\Obsidian Vault - Codex` |

**Codex 侧没有设全局 `SAVE_MEMORY_HOME`** —— 那会让 Claude 也读到 Codex 的配置。所以 Codex 的命令里用 `--vault` 显式指定目标库，`~/.codex/AGENTS.md` 就是按这个写的：

```
py -3 "%USERPROFILE%\.codex\skills\save-memory\engine\mem.py" --vault "<codex 专用 vault>" brief
```

代价：两边共用同一个图谱缓存文件（`~/.claude/save-memory-graph.json`），不同 vault 会互相踢缓存、每次切换重建一次。百来篇的规模无感；要让缓存也隔离，给命令加环境变量前缀：

```
$env:SAVE_MEMORY_HOME="$env:USERPROFILE\.save-memory-codex"; py -3 "...\mem.py" brief
```

### 记忆可见性（awareness）

`brief` 输出的目录会写进各宿主的常驻指令，让模型知道"有这么个库、里面大概有什么"：

| 宿主 | 常驻文件 | 内容 |
|---|---|---|
| Claude Code | `~/.claude/CLAUDE.md` | 一段"什么时候先跑 brief" |
| Codex | `~/.codex/AGENTS.md` | 同上，外加 `--vault` 完整命令 |

这是 v0.4.0 删掉 SessionStart hook 之后的补偿：hook 会无条件注入索引，现在靠常驻指令 + 模型主动执行。可靠性低于 hook，但跨宿主可用。

## 调用

`SKILL.md` 里所有命令都写作 `py -3 <引擎> <子命令>`，`<引擎>` 指本 skill 目录下的 `engine/mem.py`。装好后的绝对路径是：

```
~/.codex/skills/save-memory/engine/mem.py
```

手工验证：

```bash
py -3 ~/.codex/skills/save-memory/engine/mem.py --vault "<你的 vault>" brief
py -3 ~/.codex/skills/save-memory/engine/mem.py --vault "<你的 vault>" recall 重试
```

配置好后可以省掉 `--vault`（见下节）。

### 没有自定义斜杠命令（实测，v0.119.0）

仓库为 Claude Code 提供的 `commands/*.md`（`/save-memory`、`/recall`、`/garden`、`/status`、`/setup`）**在 Codex 侧不存在等价物**，所以不要往 `~/.codex/prompts/` 装。

证据（本机 codex-cli 0.119.0）：

```powershell
# 放一个带唯一标记的 prompt 文件
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex\prompts" | Out-Null
'---`ndescription: smoke`n---`nMARKER_9931' | Set-Content "$env:USERPROFILE\.codex\prompts\test-sm.md"

# 让 Codex 打印「模型实际收到什么」，不需要模型回答，也不需要登录
codex debug prompt-input "/test-sm hello"
```

输出里 user message 的 `text` 就是字面量 `"/test-sm hello"`，`MARKER_9931` 一次都没出现 —— 说明该目录没有被读取、`/名字` 没有展开。二进制里也搜不到任何 `prompts` 目录拼接（只有 `memory/*/prompts.rs` 这类内部模块名），TUI 侧只有技能选择器（`Type to search skills`）。

Codex 里的等价做法：

- 输入 `/` 打开**技能选择器**，选 `save-memory`（技能目录已在索引里）
- 或者直接在句子里点名 `save-memory` / 描述意图，靠 `description` 命中
- 想要确定性动作，直接跑 `py -3 <引擎> check|validate|recall`（不经过模型，最稳）

## 配置与状态目录

配置文件与 Claude 侧共用一套优先级：

```
--vault 参数 > SAVE_MEMORY_VAULT 环境变量 > 配置文件 > 内置默认
```

配置文件位置由状态目录决定，`mem.py` 未配置时会直接打印期望路径。默认候选：

```
SAVE_MEMORY_HOME > ~/.claude（历史位置） > ~/.save-memory
```

**同一台机器上同时用 Claude Code 和 Codex 时，建议给 Codex 单独一个状态目录**，避免两边抢同一份图谱缓存：

```powershell
$env:SAVE_MEMORY_HOME = "$env:USERPROFILE\.save-memory-codex"
```

```bash
export SAVE_MEMORY_HOME=~/.save-memory-codex
```

这个变量只影响缓存、配置文件查找位置，不影响 vault 内容。

## 沙箱与命令执行（实测）

`codex exec` 的 `workspace-write`（等价 `--full-auto`）实测可用，启动横幅会打出可写范围：

```
sandbox: workspace-write [workdir, /tmp, $TMPDIR, <CODEX_HOME>\memories]
```

模型在这个沙箱里能正常执行 `py -3 .../mem.py`，并拿到真实输出。

注意两点：

1. **写操作只能在可写目录内**。`mem.py` 的 `build` 会写图谱缓存到状态目录；如果状态目录落在沙箱可写范围之外，首次构建会失败。要么把 `SAVE_MEMORY_HOME` 指到可写位置，要么先用 `--add-dir` 把该目录加进沙箱
2. **只读场景可以预热缓存**：先在宿主外跑一次 `build`，之后 `brief` / `recall` 在 mtime 未变时不会重新写盘

## 能力边界（如实记录）

| 能力 | Codex 上 |
|---|---|
| skill 自动发现 | ✅ 上下文里有 name + description + 路径 |
| 按需读取 SKILL.md 全文 | ✅ 模型会读 |
| 执行 `py -3` 引擎命令 | ✅ 在 `workspace-write` 沙箱内可用 |
| 记忆索引（`brief`） | ✅ 命令可用；**不会自动注入**，要模型主动跑或用户要求 |
| 会话结束自动总结 | ❌ **没有**。Codex 无 SessionEnd 等价钩子；v0.4.0 已移除该功能 |
| 会话启动注入索引 | ❌ **没有**。同上，改为 `brief` 手动触发 |
| 写入格式校验 | ✅ 由 `mem.py validate` / `check-links` 保证，不依赖钩子 |

**关于 provider 认证**：如果 `~/.codex/config.toml` 的 `model_provider` 指向第三方网关（例如 Ark CodingPlan），且 `auth.json` 里存的是别家 key，会遇到 `401 API key format is incorrect` 或 `InvalidSubscription`。这属于宿主的凭证配置，与 `save-memory` 无关，需按你实际使用的服务商修好——`save-memory` 不读也不改这些凭证。

## 复现验证

一条命令即可判定端到端是否通（把 vault 换成你自己的测试库）：

```bash
py -3 ~/.codex/skills/save-memory/engine/mem.py --vault "<测试 vault>" brief
```

期望看到：

```
[save-memory 记忆索引] 共 N 篇经验笔记（按更新时间倒序，前 N 篇）。相关任务出现时用 recall 深读具体内容：
- <标题> | tags: <标签> | updated: <日期>
```

再验证召回：

```bash
py -3 ~/.codex/skills/save-memory/engine/mem.py --vault "<测试 vault>" recall 重试
```

期望输出以 `# save-memory 召回结果` 开头，下面出现 `## ★<分数> <标题>` 的块。看到 `★` 就说明引擎被真实执行了。

在 Codex 会话里验证同样的两条，等价于确认「模型能否自己找到引擎」：让它执行上面两条命令，输出应与终端里一致。
