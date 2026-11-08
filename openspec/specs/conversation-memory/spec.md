# conversation-memory Specification

## Purpose
conversation-memory 能力负责把 Claude Code 对话中产生的可复用知识沉淀到本地 Obsidian vault，并提供按需检索召回，使跨项目的经验以结构化笔记形式持续积累并融入用户知识图谱。

## Requirements

### Requirement: 对话知识提取

执行 `/save-memory` 时，系统 SHALL 按封闭白名单从当前对话上下文提取五类内容：踩坑与解法、可复用素材的工程经验、关键决策及其理由、被推翻的认知、项目事实。系统 SHALL 排除：闲聊、可从代码或 git 历史推导的内容、密钥等敏感信息、标准文档知识（半分钟能查到的参数定义/语法/原理，除非对话产出了非默认实践选择及其理由）、已有笔记已覆盖的内容。系统 SHALL 在写入前输出提取审计表（候选知识、命中类目编号、判定理由），未命中白名单的候选 SHALL 被丢弃。系统 SHALL NOT 以情境理由（如用户在备考、有教学价值）创设白名单外豁免；唯一例外是用户显式要求保存，此时笔记 frontmatter SHALL 标注 `source: user-requested`。

#### Scenario: 候选知识未命中白名单
- **WHEN** 某候选知识不属于五类中任何一类，且用户未显式要求保存
- **THEN** 该候选在审计表中被标记为"无"并丢弃，不写入任何笔记

#### Scenario: 标准文档知识
- **WHEN** 对话包含参数定义、语法等标准文档内容，且未产出非默认实践选择
- **THEN** 该内容不生成笔记；若产出了非默认实践选择，仅记录该增量

#### Scenario: 用户显式要求保存
- **WHEN** 用户明确要求保存某条白名单外内容
- **THEN** 内容被保存且 frontmatter 标注 `source: user-requested`

#### Scenario: 对话包含报错及修复过程
- **WHEN** 用户在对话中遇到报错并找到修复方式后执行 `/save-memory`
- **THEN** 生成的笔记包含该问题与解法的配对记录，且不含密钥等敏感信息

#### Scenario: 对话无可提取内容
- **WHEN** 对话仅包含闲聊或没有产生新增知识
- **THEN** 系统告知用户本次无可保存内容，不创建任何笔记

### Requirement: 素材与经验解耦

超过 10 行的命令/配置/代码片段 SHALL 存入 `AI记忆/snippets/` 素材文件（frontmatter 含 `type: snippet`，正文只含原始文本块），经验笔记正文 SHALL 只保留素材链接及一两行经验说明。无经验附着的纯素材 SHALL NOT 生成经验笔记。

#### Scenario: 提取出带经验的代码片段
- **WHEN** 某候选知识包含超过 10 行的代码及其使用经验
- **THEN** 代码存入 snippets/ 素材文件，经验笔记只记录经验与指向素材的双链

#### Scenario: 纯素材无经验
- **WHEN** 候选只有可复用片段而没有适用条件、坑或选型理由
- **THEN** 至多保存素材文件本身，不创建经验笔记

### Requirement: 去重合并

写入前系统 SHALL 检索 vault 中同主题的已有笔记，并按合并规则判定：内容为全新主题则新建笔记；一次提取的多条同域薄知识 SHALL 合并写入域级经验笔记而非各建文件；主题已有笔记则追加到对应小节；已有结论被本次对话推翻则在旧笔记中标注被取代并指向新结论。

#### Scenario: 多条同域薄知识
- **WHEN** 一次提取产生多条属于同一领域且各自内容较薄的知识
- **THEN** 合并写入同一篇域级经验笔记的对应小节，不逐条新建文件

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

执行 `/recall` 时，系统 SHALL 从当前任务上下文提炼 2~5 个关键词，经同义词扩词后通过双通道检索 vault：标签通道与正文通道，命中按覆盖率加权计分（标签 +2、标题 +3、正文 +1，各乘以覆盖率 = 较短串长度/较长串长度，双向包含均算命中，多命中叠加）。种子笔记 SHALL 沿知识图谱边扩展一跳，邻居得分 = 起点种子分 × 0.5^跳数 × 边类型系数（solved_by=1.2、related/part_of=1.0、supersedes/superseded_by=0.3 且标注已过时）。系统 SHALL 按总分排序，在字数预算内（默认约 3000 字，种子笔记全文单篇截断约 800 字、邻居仅标题加首行）将结果注入当前上下文。匹配器 SHALL 与打分管线解耦，词面匹配可整体替换为语义匹配而不改动计分逻辑。SKILL.md 的 description SHALL 包含触发提示，使 Claude 在任务涉及历史经验时主动建议执行召回。双通道及同义词扩展后均无命中时，系统 SHALL 告知用户没有相关历史记忆。

#### Scenario: 任务与历史笔记相关
- **WHEN** 用户当前任务的关键词经标签或正文通道命中 vault 中的笔记
- **THEN** 打分排序后的笔记要点在字数预算内注入当前会话上下文，供后续回答参考

#### Scenario: 标签未命中但正文命中
- **WHEN** 关键词未命中任何 tag，但命中某笔记正文
- **THEN** 该笔记仍作为种子参与打分与图谱扩展，召回结果正常返回

#### Scenario: 图谱一跳扩展
- **WHEN** 种子笔记存在双链或类型化边邻居
- **THEN** 邻居以标题加首行纳入结果并按跳数衰减计分，经 supersedes/superseded_by 边到达的节点被标注已过时

#### Scenario: 无命中笔记
- **WHEN** 关键词及其中英文同义词在标签与正文双通道均无命中
- **THEN** 系统告知用户没有相关历史记忆，正常继续任务

### Requirement: 自动总结

SessionEnd hook SHALL 在会话结束时读取 transcript 并统计用户消息轮数；少于 5 轮时 SHALL 静默跳过；达到 5 轮时系统 SHALL 以嵌套 headless 会话执行提取流程（继承封闭白名单与审计规则）并将结果写入 vault。hook SHALL 通过独立环境标记防止嵌套会话结束时再次触发自身，执行与异常状态 SHALL 记录到日志文件，hook SHALL 以异步方式运行且显式设置超时，不阻塞会话退出。

#### Scenario: 短会话跳过
- **WHEN** 会话的用户消息少于 5 轮
- **THEN** hook 直接退出，不触发任何模型调用

#### Scenario: 达到阈值触发
- **WHEN** 会话用户消息达到 5 轮及以上
- **THEN** 嵌套 headless 会话按提取规则总结对话并写入 vault 的 AI记忆/ 目录

#### Scenario: 防递归
- **WHEN** 嵌套 headless 会话自身结束时触发 SessionEnd hook
- **THEN** hook 检测到防递归标记并直接退出，不产生循环调用

#### Scenario: 嵌套调用失败
- **WHEN** 嵌套调用超时或返回非零
- **THEN** 异常记录到日志文件，不影响用户会话退出

### Requirement: 会话启动注入

SessionStart hook SHALL 在会话启动与恢复（startup/resume）时生成记忆索引并注入会话上下文：每篇经验笔记一行（标题、tags、updated），按 updated 倒序，行数上限约 40。索引 SHALL 仅用于让 Claude 知晓已有记忆的存在，笔记内容 SHALL 留待任务出现后按需检索深读。clear 与 compact 来源 SHALL 不重复注入。

#### Scenario: 新会话启动
- **WHEN** 会话以 startup 或 resume 来源开始
- **THEN** 记忆索引以结构化 hook 输出注入会话上下文

#### Scenario: 清除与压缩后
- **WHEN** SessionStart 以 clear 或 compact 来源触发
- **THEN** 不注入索引，避免重复

#### Scenario: 记忆为空
- **WHEN** AI记忆/ 目录不存在或为空
- **THEN** 不注入任何内容，会话正常开始

### Requirement: 记忆园艺

`/garden-memory` SHALL 检测知识库健康问题并默认只报告不修改：指向不存在笔记的双链（红链）、主题重叠的薄笔记（少于 10 行）、同义或大小写不一致的 tags、子主题数量超限（约 5 个小节以上）的域笔记。修复 SHALL 仅在用户对具体条目确认后执行，且 SHALL 仅作用于 AI记忆/ 目录。

#### Scenario: 红链检测
- **WHEN** 存在指向不存在笔记的双链
- **THEN** 园艺报告列出红链及其可能的修复目标

#### Scenario: 只报告不修改
- **WHEN** 园艺检测完成
- **THEN** 输出问题清单且未修改任何文件，等待用户逐项确认

#### Scenario: 确认后修复
- **WHEN** 用户对某条问题确认修复
- **THEN** 系统仅对该条执行修复，其余保持不动
