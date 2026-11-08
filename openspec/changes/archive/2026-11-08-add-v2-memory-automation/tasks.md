# Tasks

## 1. graph.py 混合召回脚本

- [x] 1.1 实现 `build` 子命令：扫描 vault 全部 .md，解析正文 `[[双链]]` + frontmatter 类型化边 → 邻接表 → graph.json（含每文件 mtime）。验证：对真实 vault 构建后人工核对邻接关系与 snippets 引用
- [x] 1.2 实现 `expand` 子命令：BFS 一跳/二跳，输出邻居标题、首行摘要、边类型，supersedes 类边标注 ⚠️。验证：以《LLM API工程经验》为种子，输出含《LLM 模型类型差异》与《tenacity重试模板》
- [x] 1.3 实现 `recall` 子命令：同义词表扩词 → 双通道产种子（标签/正文，覆盖率加权计分）→ 一跳扩展（×0.5^跳数×边类型系数）→ 总分排序 → 字数预算截断输出。验证：`recall 限流 重试` 命中《LLM API工程经验》且邻居正确参与排序；`recall 429` 经正文通道命中；无关词返回无记忆
- [x] 1.4 实现 `check` 子命令：红链检测（指向不存在笔记的双链清单）。验证：手工造一条红链能被检出，删除后复查为空
- [x] 1.5 打分参数集中为顶部常量（权重/衰减/边系数/预算），graph.json mtime 增量缓存。验证：修改一篇笔记后重跑 build 仅重解析该文件

## 2. SessionEnd / SessionStart hooks

- [x] 2.1 实现 `hooks/session_start.py`：扫描 AI记忆/ 生成索引（标题|tags|updated 倒序，≤40 行），以结构化 JSON additionalContext 输出；空目录不输出。验证：直接运行检查 JSON 合法且行数受限
- [x] 2.2 实现 `hooks/session_end.py`：读 stdin payload → SAVE_MEMORY_RUNNING 防递归检查 → 解析 transcript 统计 human 轮数 → <5 轮退出 / ≥5 轮嵌套 `claude -p`（acceptEdits + allowedTools + --add-dir）→ 日志写 ~/.claude/save-memory.log。验证：短/长 transcript 各模拟一次，行为分叉正确
- [x] 2.3 嵌套调用端到端验证一次：确认笔记落盘、子会话结束不递归、日志有记录。验证：vault 出现新笔记且 save-memory.log 无异常
  - 备注（2026-11-08 用户决策）：机制层已验证（嵌套调用成功、超时保护触发、SessionStart 注入真实会话生效）；用户因 token 成本/黑盒/标题权重停用 hooks，全量端到端验证随停用一并搁置。hooks 作为 opt-in 代码保留

## 3. SKILL.md 流程升级

- [x] 3.1 `/recall` 流程改为：提炼关键词（三场景规则保留）→ `graph.py recall` → 预算内结果注入。验证：流程步骤与 spec 的按需召回 requirement 一致
- [x] 3.2 新增流程三 `/garden-memory`：graph.py check + 碎片/tags/域笔记分析，只报告、逐项确认后修复。验证：含"只报告不修改"硬约束
- [x] 3.3 配置区增加 scripts/ 与 hooks/ 路径说明，版本升 0.2.0。验证：路径与全局安装布局一致

## 4. 注册与同步

- [x] 4.1 `~/.claude/settings.json` 注册两个 hook（SessionEnd async+timeout，SessionStart matcher startup|resume）。验证：settings JSON 语法合法，hook 命令在 Git Bash 下可执行
- [x] 4.2 全局安装同步（SKILL.md + references + scripts + hooks）。验证：`~/.claude/skills/save-memory/` 与 repo 内容一致

## 5. 文档与版本

- [x] 5.1 README 增加 hooks 配置节（settings.json 片段 + 工作原理图）与 v2 特性说明，ROADMAP 勾选 v2 已完成项。验证：按 README 可在新机器配好 hook
- [ ] 5.2 git 提交（feat: v2 自动化闭环 + 图谱召回 + 园艺）。验证：git log 与 status 干净

## 6. 变更收尾

- [ ] 6.1 `openspec validate add-v2-memory-automation` 通过，全部任务勾选。验证：validate 无 error
