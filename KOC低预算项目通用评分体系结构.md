# KOC 低预算项目通用评分体系结构

适用范围：KOC 达人投放项目，通常单达人预算低于 2000 元，但预算不是唯一判断条件。

## 0. KOC 达人投放项目定义

KOC 达人投放项目，是指品牌明确以“小体量、真实体验、低预算、多账号矩阵、口碑种草”为核心投放方式的达人项目。

它的本质不是“便宜达人项目”，而是用一批更接近真实消费者或真实使用者的账号，产出可信内容、铺设场景声量、验证卖点表达，并在有限预算下获取可复用的内容资产和长尾转化。

### 0.1 典型特征

一个项目可判断为 KOC 达人投放项目，通常具备以下多数特征：

- 达人定位：素人 KOC、小 KOC、真实用户、校园/母婴/留学/测评等垂类小号。
- 账号量级：粉丝量不是核心门槛，常见为几千到几万粉。
- 投放方式：多账号矩阵、批量种草、批量测评、内容铺量，而不是单个头部达人强曝光。
- 内容目标：真实体验、使用场景、心得分享、测评对比、问题解决、生活化种草。
- 商务目标：低成本试水、口碑铺设、素材沉淀、长尾搜索承接、转化验证。
- 成本特征：单达人预算较低，通常低于 2000 元，但不同类目可有轻微浮动。
- 评分重点：性价比、内容真实度、场景适配、互动质量、执行稳定性，而不是粉丝规模。

### 0.2 不应误判为 KOC 的情况

以下情况即使预算较低，也不能自动判定为 KOC 项目：

- Brief 要求 KOL、达人、腰部达人、垂类专家、专业背书达人。
- 项目目标是少量达人集中曝光，而不是矩阵铺量。
- 主要看品牌调性、专业权威、粉丝规模或内容制作水准。
- 达人报价低只是临时预算约束，不代表项目策略是 KOC 矩阵。
- 项目配置中选择的是 KOL、KOL/KOC 混合、专家型达人或中腰部达人。

### 0.3 KOC 项目与低预算项目的关系

低预算是 KOC 项目的常见结果，但不是充分条件。

判断顺序应是：

```text
先判断项目是否为 KOC 投放策略
再判断预算是否适合低预算 KOC 评分结构
最后再进入 KOC 通用评分体系
```

如果只看到“单达人预算低于 2000 元”，但 Brief 和项目配置没有任何 KOC 策略信号，则不能自动启用本结构。

启用条件：

- Brief 中明确出现 KOC、小 KOC、素人 KOC、低预算 KOC、KOC 矩阵等表达。
- 或项目创建/配置时，达人类型、投放矩阵、资源类型明确选择了 KOC。
- 或 Brief 虽未直接写 KOC，但明确要求低预算、多账号矩阵、真实体验、素人种草、批量测评、内容铺量，且项目配置确认按 KOC 结构执行。
- 如果 Brief 只写了“预算低于 2000 元”，但没有说明 KOC，也没有在项目配置中选择 KOC，则不能自动启用本结构，只能作为可选参考。
- 如果项目同时包含 KOL/KOC 混合矩阵，本结构只适用于 KOC 分组；KOL 分组应使用另一套量级和评分口径。

本文件只定义评分体系结构，不写代码。目标是把不同 KOC 项目之间可复用的“通用评分骨架”和每个项目由大模型解析出来的“专属评分配置”分开。

## 1. 总体原则

当项目明确为 KOC 项目或 KOC 分组时，评分核心不是找最大粉丝量，也不是找单项数据最漂亮的达人，而是判断：

- 预算内是否买得到有效阅读和互动
- 达人人设是否天然适合产品
- 近期内容是否能自然承接产品场景
- 数据是否真实稳定，不是偶然爆文或异常账号
- 是否具备执行确定性，如接单、回复、近期更新

通用体系负责回答“这个 KOC 值不值得继续看”。

项目专属配置负责回答“这个 KOC 适不适合当前项目”。

## 2. 两层结构

### 2.1 通用评分骨架

所有低预算 KOC 项目共用。

包括：

- 字段完整度
- 预算适配
- 成本效率
- 阅读互动表现
- 账号活跃与稳定性
- 商单与执行确定性
- 内容承接基础能力
- 风险识别
- 补采优先级

通用骨架不直接写死行业、人群、内容关键词。

### 2.2 项目专属评分配置

由大模型根据 Brief 解析生成。

包括：

- 当前项目目标人群
- 产品核心使用场景
- 必须匹配的人设或身份
- 优先内容主题
- 不适合内容主题
- 推荐投放形式
- 预算口径
- 行业特殊硬规则
- 项目专属加分项
- 项目专属降权项
- 人工复核项

项目专属配置不改变通用评分结构，只填充结构里的判断标准。

## 3. 推荐评分流程

明确启用 KOC 结构后，低预算 KOC 项目建议统一采用三阶段：

`一阶段基础筛选 -> 二阶段详情补采 -> 三阶段项目匹配评分`

### 3.1 一阶段：基础筛选

目标：快速判断是否值得补采详情，不给最终强推荐。

使用字段：

- 昵称
- 主页链接
- 蒲公英链接
- 达人类型
- 粉丝数
- 报价
- 合作形式
- 阅读中位数
- 互动中位数
- CPM
- CPE
- 近 30 天活跃字段
- 回复率
- 已有标签

输出：

- 优先补采
- 可补采
- 低优先级
- 数据暂缓
- 一阶段 Pass

### 3.2 二阶段：详情补采

目标：补齐语义判断和风险判断证据。

补采字段：

- 主页简介
- 近 8-20 篇笔记标题
- 近 8-20 篇笔记正文
- 笔记发布时间
- 点赞、收藏、评论、分享
- 笔记类型，图文或视频
- 合作笔记案例
- 商单权限或接单证据
- 回复率
- 近期是否更新

输出：

- 内容主题占比
- 产品场景占比
- 人设证据
- 低赞风险
- 冲突内容占比
- 商单信号
- 推荐投放形式
- 需要人工复核的问题

### 3.3 三阶段：项目匹配评分

目标：结合项目专属配置，输出最终推荐结论。

输出：

- 强推荐
- 推荐
- 备选
- 待人工确认
- 不推荐
- Pass

三阶段必须带证据，不允许只输出分数。

## 4. 通用评分维度结构

建议低预算 KOC 项目统一使用 7 个一级维度。

| 维度 | 建议权重 | 通用判断 |
|---|---:|---|
| 预算适配 | 15-20 | 是否在预算内，是否存在可投形式 |
| 成本效率 | 15-25 | CPE、CPM、阅读单价是否合理 |
| 阅读互动质量 | 15-25 | 阅读、互动是否达到同量级可投水平 |
| 人设匹配基础 | 10-20 | 账号身份、标签、简介是否接近项目人群 |
| 内容场景匹配 | 15-25 | 近期内容是否能自然承接产品 |
| 执行确定性 | 5-15 | 回复率、接单、近期更新、合作案例 |
| 风险控制 | 负向扣分 | 低赞、断更、异常波动、强冲突内容 |

权重不是固定死的。通用结构固定，具体权重由项目配置调整。

## 5. 低预算 KOC 通用基准

在 KOC 项目或 KOC 分组中，预算低于 2000 元时，不建议用粉丝量作为主要门槛。

注意：低预算不自动等于 KOC。若项目 Brief 实际要的是低价 KOL、中腰部达人、垂类专家或混合矩阵，应按项目配置选择对应结构。

### 5.1 预算层级

| 报价 | 通用处理 |
|---:|---|
| <=500 | 高性价比区，可优先看数据和内容 |
| 501-1000 | 主力可投区 |
| 1001-1500 | 需数据或匹配度明显优秀 |
| 1501-2000 | 备选或重点达人，需强内容场景 |
| >2000 | 超出低预算 KOC 结构，除非项目允许 |

### 5.2 数据层级

不同类目差异很大，因此只建议给结构，不建议写死统一阈值。

每个项目应从已采样本或参考达人中动态生成：

- 阅读 P25 / P50 / P75
- 互动 P25 / P50 / P75
- CPE P25 / P50 / P75
- CPM P25 / P50 / P75
- 报价 P25 / P50 / P75

通用判断：

- 达到 P75：强数据信号
- 达到 P50：可投信号
- 低于 P25：低优先级或需强内容弥补
- CPE 明显低于 P50：效率加分
- 报价高于 P75 且数据低于 P50：降权

### 5.3 粉丝量处理

粉丝量只做量级坐标，不做强推荐依据。

建议：

- 低粉但阅读互动好：保留
- 中粉但 CPE 高：降权
- 粉丝高但内容不匹配：不推荐
- 粉丝低且阅读互动低：低优先级

## 6. 一阶段通用结构

### 6.1 一阶段必备字段

- `creator_id`
- `nickname`
- `profile_url`
- `pgy_url`
- `creator_type`
- `followers_count`
- `quote_price`
- `video_quote_price`
- `cooperation_format`
- `daily_read_median`
- `daily_interaction_median`
- `cpm`
- `cpe`
- `reply_rate_48h`
- `recent_active_status`

### 6.2 一阶段派生字段

- `budget_fit_status`
- `format_budget_fit`
- `data_efficiency_level`
- `engagement_level`
- `identity_weak_signal`
- `content_weak_signal`
- `stage1_priority`
- `stage1_reason`
- `detail_need_reason`

### 6.3 一阶段输出结构

每个达人应输出：

```text
一阶段结论：优先补采 / 可补采 / 低优先级 / 数据暂缓 / 一阶段Pass
主要原因：报价、阅读、互动、CPE、人设弱信号
缺失字段：简介、笔记正文、点赞样本、合作案例等
下一步动作：补采详情 / 人工复核 / 暂缓 / 淘汰
```

## 7. 二阶段通用结构

### 7.1 二阶段内容解析字段

- `profile_intro`
- `recent_notes`
- `note_titles`
- `note_contents`
- `note_publish_times`
- `note_like_counts`
- `note_comment_counts`
- `note_collect_counts`
- `note_types`
- `cooperation_note_cases`

### 7.2 二阶段派生字段

- `target_content_ratio`
- `target_content_evidence`
- `persona_match_evidence`
- `product_scene_ratio`
- `product_scene_evidence`
- `conflict_content_ratio`
- `conflict_content_categories`
- `low_like_risk`
- `recent_update_status`
- `commercial_order_signal`
- `implantability`
- `recommended_format`
- `manual_review_items`

### 7.3 二阶段判断原则

- 内容匹配必须有标题或正文证据。
- 人设匹配必须有简介、标签或长期内容证据。
- 低赞风险必须基于单篇笔记点赞样本。
- 冲突内容不等于淘汰，除非占比高且项目场景弱。
- 字段缺失时不能猜测，只能标记待补或待人工确认。

## 8. 三阶段最终推荐结构

### 8.1 强推荐

适合直接进入提报或优先建联。

通用条件：

- 至少一种合作形式预算内
- 数据效率达到项目样本 P50 以上，最好 P75
- 内容场景明确匹配项目
- 人设或目标人群明确匹配
- 无明显低赞、断更、异常风险
- 有自然植入空间

### 8.2 推荐

适合进入候选名单。

通用条件：

- 预算基本适配
- 数据达到可投线
- 内容或人设至少一项强匹配
- 风险可控
- 有少量待确认项

### 8.3 备选

适合作为扩量或替补。

通用条件：

- 预算适配但数据一般
- 数据较好但内容匹配一般
- 内容匹配但缺少部分执行证据
- 需要人工确认后再推进

### 8.4 待人工确认

不能自动推荐或淘汰。

常见原因：

- 主页简介缺失
- 近期正文缺失
- 回复率缺失
- 商单证据缺失
- 数据波动原因不明
- 目标内容占比不确定

### 8.5 不推荐 / Pass

通用情况：

- 明确超预算且没有效率优势
- 内容长期与项目无关
- 明确目标人群不匹配
- 回复率明确低于项目硬线
- 近期断更严重
- 低赞风险高
- 异常流量或违规风险明确

## 9. 项目专属评分配置结构

项目专属配置由大模型从 Brief 中解析，不写死在通用评分里。

### 9.0 项目类型识别配置

大模型需要先判断项目是否应启用 KOC 结构。

配置项：

- `project_delivery_type`
- `creator_matrix_type`
- `is_koc_project`
- `koc_activation_reason`
- `koc_activation_confidence`
- `non_koc_warning`

判断依据：

```text
Brief 是否明确提到 KOC / 素人 / 小 KOC / KOC 矩阵
项目配置是否选择 KOC
是否要求多账号矩阵、批量种草、批量测评、内容铺量
是否强调真实用户体验、口碑、低成本试水、长尾搜索承接
是否只是低预算但没有 KOC 策略信号
```

输出原则：

- `is_koc_project=true` 时，才启用本通用评分结构。
- `is_koc_project=false` 时，不启用本结构。
- 证据不足时输出 `is_koc_project=待确认`，进入人工确认。

### 9.1 项目基础配置

```text
项目名称
产品名称
产品类别
投放目标
预算上限
单达人预算
目标达人数量
发布时间要求
合作形式要求
```

### 9.2 目标人群配置

大模型需要解析：

```text
目标用户是谁
购买决策者是谁
内容观看者是谁
年龄段
地域
身份
兴趣
消费能力
特殊人群标签
```

示例：

```text
听课宝：留学生、海外学习人群、港硕/英硕/美本/澳洲留学人群。
答疑笔：小学高年级到初高中学生家庭，家长是决策者。
```

### 9.3 产品场景配置

大模型需要解析：

```text
产品解决什么问题
适合在哪些内容场景出现
达人历史内容里应该有什么相似场景
什么样的笔记结构最容易种草
```

配置项：

- `preferred_content_scenes`
- `scene_keywords`
- `scene_negative_keywords`
- `implantation_scenarios`
- `demo_requirements`

### 9.4 人设匹配配置

大模型需要解析：

```text
必须匹配的人设
优先人设
可接受人设
不适合人设
```

配置项：

- `required_identity`
- `preferred_persona`
- `acceptable_persona`
- `excluded_persona`
- `persona_evidence_sources`

### 9.5 内容主题配置

大模型需要解析：

```text
目标内容主题
内容占比要求
可接受的泛内容
冲突内容
标题/正文关键词
```

配置项：

- `target_content_categories`
- `target_content_keywords`
- `minimum_target_content_ratio`
- `conflict_content_categories`
- `conflict_content_threshold`

### 9.6 预算与形式配置

大模型需要解析：

```text
图文是否可投
视频是否可投
哪种形式优先
图文预算上限
视频预算上限
超预算是否允许备选
```

配置项：

- `allowed_formats`
- `preferred_format`
- `image_quote_cap`
- `video_quote_cap`
- `single_creator_budget_cap`
- `over_budget_policy`

### 9.7 硬规则配置

只有 Brief 明确写出的要求，才进入硬规则。

配置项：

- `must_have_identity_match`
- `must_have_recent_update`
- `reply_rate_min`
- `must_have_commercial_order`
- `forbidden_content`
- `budget_hard_cap`
- `platform_requirement`

原则：

- 硬规则必须可验证。
- 不可验证的要求进入二阶段评分或人工复核。
- 不要把主观偏好误写成硬规则。

### 9.8 加分项配置

配置项：

- `bonus_persona`
- `bonus_content_scenes`
- `bonus_data_signals`
- `bonus_execution_signals`
- `bonus_conversion_signals`

示例：

```text
听课宝：有 lecture、assignment、final、论文、课堂笔记等场景加分。
低预算美妆 KOC：素人真实测评、空瓶、成分党、前后对比加分。
母婴用品 KOC：真实宝宝使用、育儿经验、家庭日常场景加分。
```

### 9.9 降权项配置

配置项：

- `negative_persona`
- `negative_content_scenes`
- `negative_data_signals`
- `negative_execution_signals`
- `negative_risk_signals`

降权项不是硬淘汰，除非 Brief 明确要求。

## 10. 大模型解析输出模板

大模型应输出以下结构化配置，不是最终达人评分。

```text
project_fit_config
- project_delivery_type
- creator_matrix_type
- is_koc_project
- koc_activation_reason
- koc_activation_confidence
- product_name
- product_category
- campaign_goal
- target_audience
- decision_maker
- required_identity
- preferred_persona
- acceptable_persona
- excluded_persona

content_fit_config
- target_content_categories
- target_content_keywords
- preferred_content_scenes
- minimum_target_content_ratio
- conflict_content_categories
- conflict_content_threshold
- evidence_sources

format_budget_config
- allowed_formats
- preferred_format
- image_quote_cap
- video_quote_cap
- single_creator_budget_cap
- over_budget_policy

hard_rule_config
- budget_hard_cap
- reply_rate_min
- recent_update_days
- must_have_commercial_order
- must_have_identity_match
- forbidden_content

scoring_weight_config
- budget_weight
- cost_efficiency_weight
- engagement_weight
- persona_weight
- content_scene_weight
- execution_weight
- risk_penalty_policy

manual_review_config
- fields_to_review
- ambiguous_requirements
- unverifiable_requirements
- evidence_needed
```

## 11. 通用评分结构和专属配置的关系

| 通用结构 | 项目专属配置填充 |
|---|---|
| 预算适配 | 单达人预算、图文/视频预算、超预算策略 |
| 成本效率 | 项目样本 P25/P50/P75、参考达人基准 |
| 阅读互动质量 | 当前类目可投线、项目目标曝光或互动偏好 |
| 人设匹配基础 | required_identity、preferred_persona |
| 内容场景匹配 | target_content_keywords、preferred_content_scenes |
| 执行确定性 | 回复率、接单、档期、近期更新要求 |
| 风险控制 | forbidden_content、negative_risk_signals |

一句话：通用结构决定“看哪些维度”，项目配置决定“这些维度怎么看”。

## 12. 低预算 KOC 项目的推荐默认结构

如果 Brief 信息不完整，可先用以下默认结构：

```text
预算适配：20
成本效率：20
阅读互动质量：20
人设匹配：15
内容场景匹配：15
执行确定性：10
风险项：负向扣分
```

当项目强调内容种草时，提高内容场景匹配。

当项目强调转化时，提高成本效率和执行确定性。

当项目强调品牌调性时，提高人设匹配。

当项目预算极低时，提高预算适配，但不能只因低价强推荐。

## 13. 最终结论

适合各类低预算 KOC 项目的，不是一套固定阈值，而是一套稳定结构。该结构只在 Brief 或项目配置明确启用 KOC 时生效：

1. 先用基础数据排补采优先级。
2. 再用详情内容证据判断项目匹配。
3. 通用维度保持固定。
4. 行业、人群、关键词、预算、硬规则由大模型从 Brief 解析成项目专属配置。
5. 最终推荐必须同时说明分数、证据、风险和待复核项。

这样才能既复用系统能力，又避免每个项目被同一套泛规则误判。
