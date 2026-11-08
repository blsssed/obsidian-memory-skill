---
name: save-memory
description: 总结当前对话中的经验教训并写入 Obsidian 笔记库，或按任务关键词召回历史记忆。Use when the user says "save memory", "保存记忆", "总结对话", "写入笔记", "recall", "召回记忆", or when a task would clearly benefit from previously saved experience (re-encountering an error, resuming an old topic, asking "之前怎么解决的"). Proactively suggest recalling notes when relevant past experience may exist.
license: MIT
metadata:
  author: mason
  version: "0.1.0"
---

# Obsidian 对话记忆

把当前会话中有价值的知识沉淀到 Obsidian vault，并能在后续任务中召回。知识以笔记形式积累，通过 `[[双链]]` 和 frontmatter 类型化边融入用户知识图谱。

## 配置（安装时按需修改这一处）

- **VAULT 路径**：`C:\Users\HONOR\Documents\Obsidian Vault`
- **记忆目录**：`<VAULT>/AI记忆/`（不存在时创建）

## 流程一：/save-memory —— 总结并写入

严格按以下顺序执行：

1. **提取**：读取 [references/extraction-rules.md](references/extraction-rules.md)，从当前对话上下文提取五类知识。若全部规则都不命中（对话无可提取内容），明确告知用户"本次对话没有值得保存的内容"，到此结束，不创建任何文件。
2. **检索**：用 Glob/Grep 在 `<VAULT>/AI记忆/` 中搜索同主题已有笔记——用提取出的主题词、tags、笔记标题关键词各搜一遍；也搜索 vault 其他目录确认是否与用户既有笔记相关。
3. **合并判定**：读取 [references/merge-rules.md](references/merge-rules.md)，对每条提取出的知识判定走哪条路径（新建 / 追加 / 标注取代）。
4. **写入**：读取 [references/note-template.md](references/note-template.md)，按模板生成或更新笔记。写入前必须用 Glob 验证每个 `[[双链]]` 目标真实存在；只链真实文件。
5. **汇报**：向用户列出本次新建了哪些笔记、更新了哪些笔记、建立了哪些链接，一句话说明每条知识的去向。

## 流程二：/recall —— 召回历史记忆

1. 从当前任务中提炼 2~5 个检索关键词（技术名词、报错信息、工具名、项目名）。
2. Grep 搜索 `<VAULT>/AI记忆/`（必要时扩展到整个 vault），命中后读取笔记全文。
3. 把与当前任务相关的要点（结论、命令、坑）注入上下文，并在回答中注明来自哪篇笔记。
4. 无命中则告知用户"没有找到相关历史记忆"，正常继续任务。

## 硬性约束

- **只写入 `AI记忆/` 目录**。可以读取整个 vault、双链可以指向任何笔记，但绝不修改 `AI记忆/` 以外的文件。
- **敏感信息永不写入**：API key、密码、token、内网地址等，无论上下文多重要。
- 文件名清洗、frontmatter 结构、UTF-8 编码，一律遵循 [references/note-template.md](references/note-template.md)。
- 笔记语言跟随用户对话语言。
