# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
