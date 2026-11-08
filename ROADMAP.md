# Roadmap

## v2：自动化 + 图谱（把骨架变活）

1. **SessionEnd hook 自动总结**
   - 关键是节流而非触发：hook 先判断本次对话有无白名单命中，无则静默跳过
   - 配套 SessionStart 自动召回：会话开始注入相关历史笔记摘要，形成记忆闭环
2. **graph.py 多跳召回**
   - 一跳扩展：种子笔记 → 邻居列表（只注入标题+首行，省 token）
   - 类型化边语义：`superseded_by` 降权、`solved_by` 优先
   - `graph.json` 缓存 + mtime 增量更新
3. **园艺命令 `/garden-memory`**
   - 红链检测、碎片笔记合并、同义 tags 归并
   - 知识库只种不剪三个月就荒，长期可用的关键

## v3：工程化 + 产品化

4. **配置外置 + 多 vault**：路径挪到 `~/.claude/save-memory.json`，多 vault 按项目路由
5. **打包成 Claude Code plugin**：一条命令安装，hook 可随包分发
6. **校验脚本下沉**：frontmatter/文件名/编码校验从 prompt 约束改为 `validate.py` 确定性保证
7. **语义检索**：本地 embedding + sqlite-vec（500+ 篇笔记后再做）
8. **记忆使用统计**：frontmatter 记 `recall_count`，零召回笔记建议归档，用数据反哺提取规则

## 不做

- 记忆衰减自动删除（删数据必须人来决定）
- 联网同步/多人协作（Obsidian Sync 的领域）
- GUI

## 节奏

先跑两周 v1 用真实使用暴露提取规则缺陷 → v2（hook 闭环 + graph.py + 园艺）→ v3（plugin 化）。
