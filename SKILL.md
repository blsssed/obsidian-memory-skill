---
name: save-memory
description: 总结当前对话中的经验教训并写入 Obsidian 笔记库，按任务关键词召回历史记忆，或对知识库做健康体检（红链/碎片/标签归并）。Use when the user says "save memory", "保存记忆", "总结对话", "写入笔记", "recall", "召回记忆", "garden memory", "整理记忆", "知识库体检", or when a task would clearly benefit from previously saved experience (re-encountering an error, resuming an old topic, asking "之前怎么解决的"). Proactively suggest recalling notes when relevant past experience may exist.
license: MIT
metadata:
  author: mason
  version: "0.2.0"
---

# Obsidian 对话记忆

把当前会话中有价值的知识沉淀到 Obsidian vault，并能在后续任务中召回。知识以笔记形式积累，通过 `[[双链]]` 和 frontmatter 类型化边融入知识图谱；召回基于图谱多跳扩展打分（scripts/graph.py），会话结束/开始由 hooks 自动总结与注入索引（README 有安装说明）。

## 配置（安装时按需修改这一处）

- **VAULT 路径**：`C:\Users\HONOR\Documents\Obsidian Vault`
- **记忆目录**：`<VAULT>/AI记忆/`（经验笔记，不存在时创建）
- **素材目录**：`<VAULT>/AI记忆/snippets/`（纯文本块，不存在时创建）
- **图谱脚本**：`<skill目录>/scripts/graph.py`（零依赖，`py -3 scripts/graph.py build|recall|expand|check`）
- **Hooks**：`<skill目录>/hooks/`（session_end.py 自动总结、session_start.py 索引注入）

## 流程一：/save-memory —— 总结并写入

严格按以下顺序执行：

1. **提取**：读取 [references/extraction-rules.md](references/extraction-rules.md)，从当前对话上下文提取五类知识。白名单是**封闭世界**——情境理由（用户在备考等）不构成提取依据，唯一例外是用户显式要求保存（标注 `source: user-requested`）。提取后**必须先输出提取审计表**（候选知识 / 命中类目编号 / 判定理由），类目为"无"的丢弃。若没有任何候选命中，明确告知用户"本次对话没有值得保存的内容"，到此结束。
2. **检索**：用 Glob/Grep 在 `<VAULT>/AI记忆/` 中搜索同主题已有笔记——用提取出的主题词、tags、笔记标题关键词各搜一遍。双链目标可以是用户笔记（标题须来自对话上下文），但**不为寻找建链目标扫描 vault 其他目录**。
3. **合并判定**：读取 [references/merge-rules.md](references/merge-rules.md)，对每条提取出的知识判定走哪条路径（新建 / 域级合并 / 追加 / 标注取代）。
4. **写入**：读取 [references/note-template.md](references/note-template.md)，按模板生成或更新笔记。超过 10 行的代码/配置**外置到 snippets/**，正文只留链接和一两行经验。写入前必须用 Glob 验证每个 `[[双链]]` 目标真实存在；只链真实文件。链接只写在记忆笔记一侧，不修改用户笔记。
5. **汇报**：向用户列出本次新建了哪些笔记、更新了哪些笔记、建立了哪些链接（含外置的 snippet），一句话说明每条知识的去向。

## 流程二：/recall —— 图谱混合召回

1. 从当前任务中提炼 2~5 个检索关键词（技术名词、报错信息、工具名、项目名；用户手动给出的关键词优先）。
2. 运行图谱召回（零依赖，自动增量构建缓存）：
   ```
   py -3 <skill目录>/scripts/graph.py recall <关键词1> <关键词2> ...
   ```
   脚本完成同义词扩词 → 标签/正文双通道种子计分 → 知识图谱一跳扩展（跳数衰减 × 边类型系数）→ 总分排序 → 字数预算内输出。种子笔记输出全文（单篇截断），邻居只出标题+首行与到达边类型。
3. 邻居笔记如需完整内容，再读取其全文深读。
4. 把与当前任务相关的要点（结论、命令、坑）注入上下文，并在回答中注明来自哪篇笔记；经 supersedes/superseded_by 边到达的笔记标注已过时，谨慎采用。
5. 双通道及同义词扩展后均无命中，告知用户"没有找到相关历史记忆"，正常继续任务。

## 流程三：/garden-memory —— 记忆园艺（只报告，确认后修复）

1. 运行 `py -3 <skill目录>/scripts/graph.py check`，列出红链（指向不存在笔记的双链）及最接近的现有笔记建议。
2. 在 `AI记忆/` 中检查：主题重叠的薄笔记（<10 行，建议合并）、同义或大小写不一致的 tags（如 mcp vs MCP，建议统一）、子主题小节超过 ~5 个的域笔记（建议拆分）。
3. 输出问题清单与修复建议，**默认不修改任何文件**。
4. 用户对具体条目逐项确认后，才执行对应修复，且仅作用于 `AI记忆/`。

## 硬性约束

- **只写入 `AI记忆/` 目录**（含 `snippets/`）。可以读取整个 vault、双链可以指向任何笔记，但链接只写在记忆笔记里——**绝不修改 `AI记忆/` 以外的文件，包括"为建立双向链接"而编辑用户笔记**。
- **敏感信息永不写入**：API key、密码、token、内网地址等，无论上下文多重要。
- 文件名清洗、frontmatter 结构、UTF-8 编码，一律遵循 [references/note-template.md](references/note-template.md)。
- 笔记语言跟随用户对话语言。
