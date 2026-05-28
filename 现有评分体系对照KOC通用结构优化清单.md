# 现有评分体系对照 KOC 通用结构优化清单

生成日期：2026-05-26

对照文档：`KOC低预算项目通用评分体系结构.md`

检查对象：

- `rpa_mcp_sync/creator_store.py`
- `rpa_mcp_sync/web.py`
- `ad-workbench/src/pages/screening`

重要边界：

- KOC 达人投放项目不是“预算低的项目”，而是以小体量真实账号、多账号矩阵、口碑种草、真实体验、内容铺量为核心策略的项目。
- KOC 通用结构只在 Brief 明确提到 KOC、小 KOC、素人 KOC、KOC 矩阵等表达时启用。
- 或在项目创建/项目配置中明确选择达人类型为 KOC 时启用。
- 或 Brief 虽未直接写 KOC，但明确要求低预算、多账号矩阵、真实体验、素人种草、批量测评、内容铺量，且项目配置确认按 KOC 结构执行。
- 预算低于 2000 元本身不是启用 KOC 结构的充分条件。
- 混合项目中，该结构只应用于 KOC 分组，不应用于 KOL 或中腰部达人分组。

## 1. 总体判断

现有评分体系已经具备两阶段评分的雏形，但还没有完全收敛成“仅在 KOC 项目或 KOC 分组启用的低预算 KOC 通用结构 + 项目专属配置”的稳定体系。

已有能力：

- 已有项目配置层：`projectFitConfig`、`formatBudgetPolicy`、`hardRules`、`projectSpecialScoring`。
- 已有详情补采优先级：`detail_collection_priority`。
- 已有预算形态判断：图文/视频预算、仅图文可投、仅视频可投、均超预算。
- 已有低赞、近期更新、商单信号的派生函数。
- 已有 LLM 评分 payload，能把项目配置、达人字段、详情字段传给模型。
- Brief 优化接口已经要求大模型输出 `projectSpecialScoring`。

主要问题：

- 缺少明确的 KOC 项目定义和结构启用条件，容易把“低预算”误当成“KOC”。
- 评分维度仍是旧六维结构，不是 KOC 通用七维结构。
- 一阶段、二阶段、三阶段的输出状态没有完全拆开。
- 内容占比、人设证据、项目场景占比仍偏“文本命中/模型判断”，没有稳定落成结构化字段。
- 风险控制被混在硬过滤、扣分、详情优先级里，没有作为独立负向层。
- 默认权重仍偏旧项目模板，低预算 KOC 的默认权重没有单独配置。
- 前端展示仍以总分和六维分为主，不能完整呈现 KOC 三阶段判断。

## 2. 通用结构对照

### 2.1 一阶段基础筛选

通用结构要求：

- 一阶段只用稳定字段判断是否值得补采详情。
- 输出：优先补采、可补采、低优先级、数据暂缓、一阶段 Pass。
- 不直接给最终强推荐。

现有情况：

- `score_values()` 会直接输出 `total_score` 和 `recommend_level`。
- `_creator_stage_derivatives()` 已经有 `stage_one_status`，但只嵌在评分理由中，不是主状态。
- `detail_collection_priority()` 仍依赖总分分档，而不是明确的一阶段 KOC 优先级。

需要优化：

1. 增加独立字段 `stage1_priority`。
2. 增加独立字段 `stage1_reason`。
3. 一阶段评分结果不要直接等同于最终 `recommend_level`。
4. 筛选工作台列表优先展示一阶段状态，而不是只展示总分。

优先级：P0。

### 2.2 二阶段详情补采

通用结构要求：

- 补采主页简介、近 8-20 篇笔记标题/正文、发布时间、点赞评论收藏、笔记类型、合作案例、回复率。
- 生成内容主题占比、产品场景占比、人设证据、低赞风险、冲突内容占比、商单信号。

现有情况：

- 详情补采链路可用，已有 `detail_text`、`recent_notes`、`note_cases`。
- 已有 `_low_like_risk()`、`_recent_update_status()`、`_commercial_order_signal()`。
- 但缺少稳定的：
  - `target_content_ratio`
  - `product_scene_ratio`
  - `conflict_content_ratio`
  - `persona_match_evidence`
  - `target_content_evidence`

需要优化：

1. 新增内容解析派生层，不只让 LLM 判断。
2. 基于项目配置里的关键词计算目标内容占比。
3. 基于项目配置里的冲突类目计算冲突内容占比。
4. 把证据标题/正文摘要保存为结构化字段。

优先级：P0。

### 2.3 三阶段项目匹配评分

通用结构要求：

- 三阶段结合项目专属配置输出最终推荐。
- 输出：强推荐、推荐、备选、待人工确认、不推荐、Pass。
- 必须带证据、风险和人工复核项。

现有情况：

- LLM payload 已要求输出 `projectMatchStatus`。
- `_normalize_llm_score()` 会读取 `recommendLevel` 等结果。
- 但数据库主表 `creator_scores` 没有独立保存 `project_match_status`，最终仍主要落为 `recommend_level`。
- 规则评分与二阶段审号结论容易混在一起。

需要优化：

1. 将 `recommend_level` 拆成：
   - `stage1_priority`
   - `project_match_status`
   - `final_recommend_level`
2. `project_match_status` 只允许二阶段详情证据充分时进入强推荐/推荐。
3. 证据不足时输出 `待人工确认`，不能直接强推荐。

优先级：P0。

## 3. 评分维度对照

### 3.1 现有六维

现有代码和前端主要使用：

```text
budget
fans
cpe
engagement
persona
content
```

问题：

- `budget_score` 当前实际更像执行确定性分，包含报价完整、链接、回复率等，不等于预算适配。
- `fans_score` 容易被理解为粉丝量或粉丝画像，但 KOC 项目里粉丝量应低权重。
- `persona_score` 和 `content_score` 边界不清。
- 风险控制没有独立维度，只混在硬过滤或理由里。

### 3.2 建议七维

建议逐步迁移到低预算 KOC 通用七维：

| 新维度 | 对应现有能力 | 优化点 |
|---|---|---|
| 预算适配 | formatBudgetPolicy、quote_price | 从 budget_score 中拆出来 |
| 成本效率 | cpe_score、CPM/CPE/CPC | 保留并增强动态 P50/P75 |
| 阅读互动质量 | traffic_score | 改名更清楚，按同量级比较 |
| 人设匹配基础 | persona_score | 必须引用项目身份配置 |
| 内容场景匹配 | content_score、projectFitConfig | 增加内容占比和场景证据 |
| 执行确定性 | reply_rate、商单、近期更新 | 从 budget_score 中拆出 |
| 风险控制 | hard_defects、warning_defects | 独立负向层，不参与正向加分 |

优先级：P1。

## 4. 项目专属配置对照

### 4.1 已有配置

现有 `web.py` 的 Brief 优化接口已要求大模型输出：

- `projectFitConfig`
- `formatBudgetPolicy`
- `hardRules`
- `projectSpecialScoring`
- `scoringCriteria`
- `post_score_rules`
- `manual_review_rules`

这部分方向正确。

### 4.2 缺口

通用结构要求大模型输出的专属配置应更稳定，包括：

- `project_delivery_type`
- `creator_matrix_type`
- `is_koc_project`
- `koc_activation_reason`
- `project_fit_config`
- `content_fit_config`
- `format_budget_config`
- `hard_rule_config`
- `scoring_weight_config`
- `manual_review_config`

现有配置的问题：

- 命名有多套：`projectFitConfig`、`projectSpecialScoring`、`scoringCriteria` 同时承载人设、内容、规则，边界不够清楚。
- `projectSpecialScoring` 更像专属加权策略，但没有覆盖完整的内容占比、冲突内容占比、证据字段要求。
- `hardRules` 里已有 `must_have_study_content_ratio`，但评分代码没有把它稳定转成 `target_content_ratio` 判断。

需要优化：

1. 先增加项目类型识别配置，判断是否为 KOC 达人投放项目。
2. 在 `projectFitConfig` 下明确保留项目人群/产品/场景。
3. 新增或规范 `contentFitConfig`，专门存内容关键词、内容占比、冲突内容。
4. 新增或规范 `manualReviewConfig`，专门存人工复核项。
5. `projectSpecialScoring` 只做项目专属分档和加减权，不再混放所有配置。

优先级：P1。

## 5. 字段层面缺口

### 5.1 应新增的达人派生字段

一阶段：

- `stage1_priority`
- `stage1_reason`
- `budget_fit_status`
- `data_efficiency_level`
- `engagement_level`
- `identity_weak_signal`
- `content_weak_signal`

二阶段：

- `target_content_ratio`
- `target_content_evidence`
- `product_scene_ratio`
- `product_scene_evidence`
- `persona_match_evidence`
- `conflict_content_ratio`
- `conflict_content_categories`
- `low_like_note_count`
- `recent_update_status`
- `commercial_order_signal`
- `implantability`
- `recommended_format`

三阶段：

- `project_match_status`
- `project_match_confidence`
- `final_recommend_level`
- `manual_review_items`
- `evidence_quotes`

### 5.2 已有但需规范的字段

- `detail_collection_priority`：建议定位为补采队列优先级，而不是推荐分档。
- `recommend_level`：建议定位为最终推荐结果，不再承载一阶段分档。
- `hard_filter_passed`：只代表已确认硬性条件，不代表字段缺失。
- `information_completeness`：需要增加详情证据完整度，不只看基础字段。

优先级：P0-P1。

## 6. 风险控制层缺口

现有风险来自：

- `_project_hard_filter_issues()`
- `_system_defects_for_creator()`
- `hard_defects`
- `warning_defects`
- `rate_limit_risk`
- `low_like_risk`

问题：

- 风险来源分散。
- 有些风险直接改 `hard_filter_passed`，有些只写理由。
- 缺少统一的 `risk_control_result`。

建议：

统一输出：

```text
risk_control_result
- hard_risks
- warning_risks
- missing_evidence_risks
- risk_level
- risk_action
```

其中：

- hard_risks：明确超预算、回复率低、不可接单、明确违规等。
- warning_risks：低赞、断更、数据波动、冲突内容占比高。
- missing_evidence_risks：缺正文、缺点赞样本、缺商单证据。

优先级：P1。

## 7. 前端展示缺口

现有前端已经展示：

- 总分
- 评分维度
- 详情补采
- 项目评分口径
- 风险提示

但与 KOC 通用结构相比，还缺：

- 一阶段状态
- 二阶段证据状态
- 项目匹配状态
- 内容占比
- 冲突内容占比
- 低赞风险样本数
- 推荐投放形式
- 人工复核项

建议列表页展示：

```text
一阶段状态 / 最终推荐
报价 / 阅读 / 互动 / CPE
预算形态
内容占比
风险标签
详情证据完整度
```

详情页展示：

```text
项目专属配置摘要
内容占比证据
人设证据
低赞样本
冲突内容样本
人工复核项
```

优先级：P2。

## 8. 具体优化优先级

### P0：先修评分结构边界

1. 增加 KOC 达人投放项目定义和启用条件：Brief 明确 KOC，项目配置选择 KOC，或 Brief 明确多账号矩阵/真实体验/素人种草且人工确认按 KOC 执行。
2. 拆分 `stage1_priority`、`project_match_status`、`final_recommend_level`。
3. 一阶段不再直接输出强推荐，只输出补采优先级。
4. 增加二阶段内容占比派生字段。
5. 将 `must_have_study_content_ratio` 等项目硬规则真正落到二阶段字段判断。
6. KOC 项目默认权重改为更适合 KOC 的结构，但不得只因预算低自动套用。

### P1：补齐 KOC 七维结构

1. 从六维迁移到七维或在六维上加映射层。
2. 将执行确定性从预算分中拆出来。
3. 将风险控制作为独立负向层。
4. 规范项目专属配置层，增加 `contentFitConfig` 和 `manualReviewConfig`。
5. 增加动态样本 P25/P50/P75 基准写入项目配置。

### P2：前端与复盘

1. 前端展示三阶段状态。
2. 展示内容占比和证据标题。
3. 展示风险样本和人工复核项。
4. 支持按 KOC 项目类型套用通用结构。
5. 将人工通过/淘汰结果回写，校准参考基准。

## 9. 最重要的改动结论

现有体系最大的优化点不是“再加一个评分维度”，而是把已有能力重新分层：

0. 先判断：当前项目或当前达人分组是否符合 KOC 达人投放项目定义。
1. 一阶段回答：这个 KOC 值不值得补采。
2. 二阶段回答：这个 KOC 有没有足够项目证据。
3. 三阶段回答：这个 KOC 是否适合最终推荐。

现在系统已经有这些零件，但状态、字段和评分结果还混在一起。下一步应先做结构拆分，再做权重和模型提示优化。
