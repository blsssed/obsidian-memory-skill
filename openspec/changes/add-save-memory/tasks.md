# Tasks

## 1. Skill 本体

- [x] 1.1 编写 `SKILL.md`：frontmatter（name/description 含触发提示）+ 顶部 vault 路径配置区 + `/save-memory` 与 `/recall` 完整流程。验证：文件包含两个方向的完整步骤，description 覆盖"总结对话/保存经验/召回记忆"类触发词
- [x] 1.2 编写 `references/extraction-rules.md`：五类白名单 + 排除清单 + 敏感信息规则。验证：规则可操作（每类含判定示例），与 spec 的提取要求一一对应
- [x] 1.3 编写 `references/note-template.md`：frontmatter 模板、正文结构、文件名清洗规则、UTF-8 约定。验证：模板与 spec 的笔记格式要求逐项对应
- [x] 1.4 编写 `references/merge-rules.md`：新建/追加/标注取代的判定条件与操作细节。验证：三种路径各有明确判定条件

## 2. 安装

- [x] 2.1 将 `SKILL.md` 与 `references/` 复制到 `~/.claude/skills/save-memory/`。验证：`ls ~/.claude/skills/save-memory` 可见完整结构

## 3. 文档

- [x] 3.1 编写中英双语 `README.md`：项目定位、安装步骤（clone → 复制到全局 → 修改 vault 路径）、使用演示、路线图。验证：按 README 步骤可在新机器完成安装

## 4. 验证

- [x] 4.1 运行 `openspec validate add-save-memory`。验证：无 error
- [x] 4.2 按 skill 规则向 vault `AI记忆/` 写入 2 篇测试笔记（含 frontmatter、双链、类型化边），用 Grep 验证 `/recall` 逻辑可命中，随后删除测试文件。验证：vault 恢复原状且写入格式合法

## 5. 版本管理

- [x] 5.1 `git init` + 编写 `.gitignore` + 首次提交全部文件。验证：`git log` 显示初始提交，`git status` 干净

## 6. 提取规则加固（v0.1.1，实测反馈）

- [x] 6.1 重写 `references/extraction-rules.md`：封闭世界总则、提取审计表、标准文档知识排除、素材解耦进白名单 #2。验证：无情境豁免通道，审计表为强制步骤
- [x] 6.2 `references/note-template.md` 增加 snippet 模板与目录结构；`references/merge-rules.md` 增加域级合并规则与分裂信号。验证：与 spec 修订逐项对应
- [x] 6.3 `SKILL.md` 更新（素材目录、审计表步骤、版本 0.1.1）并同步全局安装。验证：`~/.claude/skills/save-memory/` 与 repo 一致
- [x] 6.4 清理实测噪音笔记：删《LLM 采样参数速查》，《LLM API限流与重试》重写为《LLM API工程经验》+ tenacity snippet 外置。验证：vault 无红链
