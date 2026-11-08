# Design

## Context

用户希望通过对话沉淀经验到 Obsidian，且项目要发布到 GitHub。此前调研确认：MCP server 拿不到对话历史（工具只收模型传入的参数），通用 Obsidian MCP 无法自动总结；claude-mem 等 hook 插件能自动总结但存私有存储。因此选择纯 skill 形态，利用 Claude Code 内置的 Write/Edit/Grep/Glob 工具直接操作 vault 文件夹。

## Goals

- `/save-memory` 将对话知识按白名单提取、去重合并后写入 vault
- `/recall` 按任务关键词检索 vault 并注入上下文
- 零运行时依赖，clone 即可用
- 笔记通过双链与类型化边融入用户既有知识图谱

## Non-Goals

- 会话结束自动触发（SessionEnd hook，v2）
- 图谱多跳遍历召回（graph.py BFS，v2）
- MOC 枢纽笔记自动维护（v2+）
- MCP server 版本（视 GitHub 反馈）
- 支持 Obsidian 以外的笔记工具

## Decisions

- **纯 skill，不建 MCP server**：MCP 架构上拿不到对话内容，"总结"必须由模型完成；Claude Code 内置文件工具已覆盖读写需求。
- **双轨图谱边**：`[[双链]]` 写在正文与普通属性中，Obsidian 原生图谱免费获得；语义关系（related/solved_by/supersedes/part_of）放 frontmatter 自定义属性，为 v2 的脚本遍历预留 schema，边类型控制在 4 种以内以保证写入判断稳定。
- **v1 手动触发**：`/save-memory`、`/recall` 均由用户显式调用；description 中写触发提示，让 Claude 在相关场景主动建议。
- **全局安装**：安装到 `~/.claude/skills/save-memory/`，符合"跨项目积累记忆"的定位；repo 内保留同结构源文件。
- **vault 路径写在 SKILL.md 顶部配置区**：无配置文件依赖，安装时一处修改；README 说明替换方法。
- **不写脚本**：v1 的确定性校验（文件名清洗、frontmatter 格式）通过模板与规则文档约束模型行为实现，复杂度留到 v2 评估。

## Risks / Trade-offs

- [vault 路径因人而异，硬编码导致他人安装即坏] → README 提供显眼的配置步骤；SKILL.md 顶部配置区集中声明
- [提取规则过宽导致笔记噪音、过窄导致漏记] → 白名单 + 排除清单 + 每篇笔记内容上限约束；规则独立成 references/extraction-rules.md 便于迭代
- [双链可能指向不存在的笔记产生红链] → 规则强制写入前 Glob 验证目标存在；仅链真实笔记
- [追加写入可能破坏用户手动整理的笔记结构] → 追加仅发生在 `AI记忆/` 目录内，不触碰用户其他目录
