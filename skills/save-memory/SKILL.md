---
name: save-memory
description: 总结当前对话中的经验教训并写入 Obsidian 笔记库，按任务关键词召回历史记忆，或对知识库做健康体检（红链/碎片/标签归并）。Use when the user says "save memory", "保存记忆", "总结对话", "写入笔记", "recall", "召回记忆", "garden memory", "整理记忆", "知识库体检", or when a task would clearly benefit from previously saved experience (re-encountering an error, resuming an old topic, asking "之前怎么解决的"). Proactively suggest recalling notes when relevant past experience may exist.
license: MIT
metadata:
  author: blsssed
  version: "0.4.0"
---

# Obsidian 对话记忆

把当前会话中有价值的知识沉淀到 Obsidian vault，并能在后续任务中召回。知识以笔记形式积累，通过 `[[双链]]` 和 frontmatter 类型化边融入知识图谱；召回基于图谱扩展打分。

**所有能力都走一条与宿主无关的命令**，`<引擎>` = 本文件所在目录下的 `engine/mem.py`：

```
py -3 <引擎> <子命令>
```

| 子命令 | 用途 |
|---|---|
| `brief [-n 40]` | 记忆索引（标题 \| tags \| updated），会话开始时喂给模型 |
| `find <关键词...>` | 轻量定位：只出得分/标题/路径，不注入正文 |
| `recall <关键词...> [--record]` | 混合召回；`--record` 顺带维护 `recall_count` |
| `build` | 重建/增量更新图谱缓存 |
| `expand <笔记> [-d N]` | 从某篇笔记出发看它连着谁 |
| `check` | 全库体检：红链 / 跨目录 / 可疑别名 |
| `check-links <笔记...>` | 校验指定笔记的双链目标是否存在 |
| `validate [--note 文件]` | 格式校验（frontmatter / 文件名 / 编码） |
| `record <笔记名...>` | 手动维护 `recall_count` |

引擎零第三方依赖，纯标准库，跨平台。

## 配置

```
{ "vault": "<Obsidian 仓库路径>", "memory_dir": "AI记忆", "snippet_dir": "snippets" }
```

- 优先级：命令行 `--vault` > 环境变量 `SAVE_MEMORY_VAULT` > 配置文件 > 内置默认
- 坏 JSON 静默降级，工具不崩
- 未配置时引擎会打印配置文件应该写到哪个路径

**状态目录**（图谱缓存等）：`SAVE_MEMORY_HOME` > `~/.claude`（历史位置）> `~/.save-memory`。
同一台机器上装多个 agent 时，用 `SAVE_MEMORY_HOME` 给它们各自隔离，避免抢同一份缓存。

## 流程：按用户意图加载，不要凭记忆执行

| 用户要什么 | 读哪个文件 |
|---|---|
| 「保存记忆 / 总结对话 / 写入笔记」 | [workflows/extract.md](workflows/extract.md) |
| 「召回 / 之前怎么解决的 / 又遇到这个报错」 | [workflows/recall.md](workflows/recall.md) |
| 「整理记忆 / 知识库体检 / 红链清理」 | [workflows/garden.md](workflows/garden.md) |
| 首次安装 / 换 vault | [workflows/setup.md](workflows/setup.md) |

**主动召回**：任务明显涉及历史经验时（再次遇到某个报错、重启某个话题），主动建议跑一次 recall，而不是等用户开口。

## 策略文件（流程会引用）

- [references/extraction-rules.md](references/extraction-rules.md) —— 五类白名单、提取审计表、排除清单
- [references/merge-rules.md](references/merge-rules.md) —— 新建 / 域级合并 / 追加 / 标注取代
- [references/note-template.md](references/note-template.md) —— 目录结构、frontmatter、正文模板

## 硬性约束

- **只写入记忆目录**（含素材目录）。可以读取整个 vault、双链可以指向任何笔记，但链接只写在记忆笔记里——**绝不修改记忆目录以外的文件，包括「为建立双向链接」而编辑用户笔记**。
- **敏感信息永不写入**：API key、密码、token、内网地址等，无论上下文多重要。
- 文件名清洗、frontmatter 结构、UTF-8 编码，一律遵循 [references/note-template.md](references/note-template.md)。
- 笔记语言跟随用户对话语言。
