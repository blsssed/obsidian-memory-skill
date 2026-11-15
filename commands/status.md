---
description: 一眼看 save-memory 现状：配置生效值、笔记数、缓存大小与版本
argument-hint: [可留空]
---

只读地把当前的 save-memory 状态摆出来。**不写任何文件，不重建缓存。**

1. 加载 `save-memory` 技能：读它的 `SKILL.md`，拿到本机的 `<引擎>` 路径。
2. 跑 `py -3 <引擎> params` —— JSON 输出里有 `configPath`（引擎实际读的配置文件）和 `effective`（当前生效的打分参数，已包含越界回落）。
3. 跑 `py -3 <引擎> brief -n 1` —— 首行给出记忆库经验笔记总篇数，同时证明 vault 可读；报「未配置 vault」就说明配置缺失，把提示的路径一并转述给用户。
4. 读 `configPath` 指向的配置文件原文（存在才读），列出 `vault` / `memory_dir` / `snippet_dir`；文件不存在就说「未配置，走内置默认」。
5. 用文件工具看同目录的 `save-memory-graph.json`：是否存在、字节数、修改时间、顶层 key 数（缓存内篇数）、任一 entry 的 `v`（缓存版本）。
6. 汇报时按层讲清配置来源：命令行 `--vault` > 环境变量 `SAVE_MEMORY_VAULT` > 配置文件 > 内置默认；配置文件本身按「状态目录优先、`~/.claude/save-memory.json` 兜底」找。

7. 用户附加要求（可留空）：$ARGUMENTS
