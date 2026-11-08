# Spec Delta

## Purpose

conversation-memory 能力负责把 Claude Code 对话中产生的可复用知识沉淀到本地 Obsidian vault，并提供按需检索召回，使跨项目的经验以结构化笔记形式持续积累并融入用户知识图谱。

## ADDED Requirements

### Requirement: 对话知识提取

执行 `/save-memory` 时，系统 SHALL 按白名单从当前对话上下文提取五类内容：踩坑与解法、可复用的命令/配置/代码片段、关键决策及其理由、被推翻的认知、项目事实。系统 SHALL 排除闲聊内容、可从代码或 git 历史推导的内容、以及密钥等敏感信息。

#### Scenario: 对话包含报错及修复过程
- **WHEN** 用户在对话中遇到报错并找到修复方式后执行 `/save-memory`
- **THEN** 生成的笔记包含该问题与解法的配对记录，且不含密钥等敏感信息

#### Scenario: 对话无可提取内容
- **WHEN** 对话仅包含闲聊或没有产生新增知识
- **THEN** 系统告知用户本次无可保存内容，不创建任何笔记

### Requirement: 去重合并

写入前系统 SHALL 检索 vault 中同主题的已有笔记，并按合并规则判定：内容为全新主题则新建笔记；主题已有笔记则追加到对应小节；已有结论被本次对话推翻则在旧笔记中标注被取代并指向新结论。

#### Scenario: 同主题笔记已存在
- **WHEN** 本次提取的知识与 vault 中某篇已有笔记主题相同
- **THEN** 新内容追加到该笔记的对应小节，而不是新建重复笔记

#### Scenario: 旧结论被推翻
- **WHEN** 本次对话证明已有笔记中的结论已过时
- **THEN** 旧笔记被更新并标注被取代，同时指向新结论所在位置

### Requirement: 笔记格式与知识图谱边

写入的笔记 SHALL 包含 frontmatter（date、tags 2~5 个、source 字段，语义成立时附加类型化边 related/solved_by/supersedes/part_of）与正文中 2~5 条 `[[双链]]`，双链 SHALL 仅指向真实存在的笔记。文件名 SHALL 清洗 Windows 非法字符，文件编码 SHALL 为 UTF-8。

#### Scenario: 新建一篇笔记
- **WHEN** 合并判定为新建
- **THEN** 生成含合法 frontmatter 的 markdown 文件，正文含指向真实存在笔记的双链，数量以实际相关笔记为准

#### Scenario: 文件名包含非法字符
- **WHEN** 提炼出的笔记标题包含 `\/:*?"<>|` 等 Windows 非法字符
- **THEN** 写入前文件名完成清洗，写入成功

### Requirement: 按需召回

执行 `/recall` 时，系统 SHALL 以当前任务的关键词检索 vault，并将命中笔记的相关内容注入当前上下文。SKILL.md 的 description SHALL 包含触发提示，使 Claude 在任务涉及历史经验时主动建议执行召回。

#### Scenario: 任务与历史笔记相关
- **WHEN** 用户当前任务的关键词命中 vault 中的笔记
- **THEN** 命中笔记的要点被注入当前会话上下文，供后续回答参考

#### Scenario: 无命中笔记
- **WHEN** 关键词在 vault 中无命中
- **THEN** 系统告知用户没有相关历史记忆，正常继续任务
