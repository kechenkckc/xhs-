# ScreeningDashboard.jsx 拆分执行计划

## 目标

将 `ad-workbench/src/pages/screening/ScreeningDashboard.jsx` 从单个 5600 行左右的大文件，拆分为结构清晰、职责明确、可复用的模块，同时不影响达人筛选工作台现有功能。

本次拆分的核心目标是“保功能拆结构”，不做业务重写，不改变接口协议，不调整现有视觉样式，不改动达人筛选工作台的用户操作路径。

## 当前问题

`ScreeningDashboard.jsx` 当前同时承担了以下职责：

- 项目列表、项目卡片、项目创建、项目归档/恢复/删除
- 项目概览、筛选计划、Brief 解析、任务目标提取
- 蒲公英筛选项、硬性筛选条件、采集配置
- 达人初筛、批量审核、单人审核、达人详情弹窗
- 审号工作台、达人画像、达人匹配度、推荐理由
- 项目达人池、阶段切换、数据更新、CSV 导出
- 飞书绑定、字段读取、字段映射、写回配置
- 项目日志、AI 配置、接口请求、错误处理
- 大量格式化函数、映射函数、评分函数、配置常量

这会带来几个直接影响：

- 维护成本高：修改一个小功能需要在大文件中定位多个相关区域。
- 复用困难：项目、日志、飞书绑定等能力难以给其他工作台直接复用。
- 协作风险高：多人同时修改同一个文件容易产生冲突。
- 测试困难：业务逻辑和 UI 混在一起，不方便独立验证。
- 后续扩展受限：完整项目协作工作台需要项目级公共底座，而当前公共能力被达人筛选业务包裹。

## 拆分原则

1. 先搬迁，后优化。
   第一轮只做代码迁移和 import 调整，不改业务行为。

2. 每一步都保持可运行。
   每拆一个模块，都进行构建或页面 smoke check。

3. 保留现有函数名和组件名。
   降低行为变化风险，也方便和原文件做 diff 对照。

4. CSS 类名不改。
   本次只拆 JS/JSX，不主动调整样式文件，避免视觉回归。

5. 达人筛选专属逻辑留在 screening 内。
   蒲公英、达人评分、筛选标准等先不提升为全局公共能力。

6. 可复用能力先局部抽出。
   项目、日志、飞书等能力先放在 `pages/screening` 内部目录，稳定后再提升到全局共享目录。

## 目标目录结构

```txt
ad-workbench/src/pages/screening/
  ScreeningDashboard.jsx

  api/
    screeningApi.js

  constants/
    projectConstants.js
    pgyConstants.js
    screeningConstants.js

  utils/
    formatters.js
    projectMappers.js
    creatorMappers.js
    creatorScoring.js
    pgyFilters.js
    screeningPlan.js

  components/
    project/
      ProjectsPreview.jsx
      ProjectCard.jsx
      CreateProjectModal.jsx
      ProjectSetupTab.jsx

    overview/
      OverviewTab.jsx

    screening-review/
      ScreeningReviewTab.jsx
      CreatorDetailModal.jsx
      CreatorRecentNotesPanel.jsx

    creator-audit/
      CreatorAuditTab.jsx

    creator-pool/
      ScorePreviewTab.jsx

    filters/
      SelectableMenu.jsx
      SelectedChips.jsx
      PgyFilterCards.jsx
      PgyFilterPopover.jsx
      PgyFindBloggerFilterPanel.jsx
      HardFilterEditor.jsx
      HardFilterValueControl.jsx

    logs/
      AuditLogTab.jsx

    config/
      AdvancedConfigTab.jsx
```

## 阶段 0：建立基线

### 工作内容

- 记录当前文件行数、主要组件、主要工具函数。
- 跑一次现有前端构建，确认拆分前基线可用。
- 梳理达人筛选工作台关键路径。

### 关键路径

- 项目列表加载
- 创建项目
- 项目切换
- 项目归档、恢复、删除
- 项目设置保存
- 飞书绑定、测试、读取表格、读取字段
- 生成筛选标准
- 蒲公英采集
- 初筛审核
- 审号工作台
- 达人详情弹窗
- 达人池阶段切换
- 达人指标更新
- CSV 导出
- 操作日志查看
- AI 配置保存与测试

### 验收标准

- 拆分前构建通过。
- 关键路径有明确的人工回归检查清单。
- 不产生任何业务代码改动。

## 阶段 1：抽 API 层

### 新增文件

```txt
ad-workbench/src/pages/screening/api/screeningApi.js
```

### 迁移内容

- `api`
- `formatApiErrorMessage`
- 项目相关请求：
  - 获取项目列表
  - 获取项目详情
  - 保存项目
  - 归档项目
  - 恢复项目
  - 删除项目
  - 获取项目日志
  - 获取项目达人
- 达人筛选相关请求：
  - 导入达人
  - 评分
  - 审核
  - 获取达人池
  - 更新达人池阶段
  - 更新达人指标
- 蒲公英相关请求：
  - 启动浏览器
  - 批量采集
  - 采集详情
- 飞书相关请求：
  - 保存连接
  - 测试连接
  - 获取表格
  - 获取字段
  - 写回
  - 读取/保存写回设置
- 筛选标准相关请求：
  - 优化筛选标准

### 注意事项

- 第一轮可以保留通用 `api(url, options)`，页面继续用原 URL 调用。
- 第二轮再逐步替换为语义化函数。
- 错误提示格式必须保持一致。

### 验收标准

- 所有接口调用 URL、method、body 与拆分前一致。
- 页面错误提示和成功提示不变。
- 前端构建通过。

## 阶段 2：抽格式化和映射工具

### 新增文件

```txt
utils/formatters.js
utils/projectMappers.js
utils/creatorMappers.js
```

### 迁移内容

`formatters.js`：

- `compactNumber`
- `formatCurrency`
- `formatDateTime`
- `getDateKey`
- `formatDateLabel`
- `formatCompleteness`
- `formatPercentValue`
- `formatNoteMetric`

`projectMappers.js`：

- `normalizeProjectBrief`
- `mapBackendProject`
- `parseStoredScreeningPlan`
- `getProjectCreators`
- `getProjectStats`
- `briefTextFromProject`
- `parseBriefTaskTargets`
- `getProjectTaskSummary`

`creatorMappers.js`：

- `mapBackendCreator`
- `getCreatorStatus`
- `getDefaultCreatorStatus`
- `isValidPgyDetailUrl`
- `getPgyUrl`
- `pickCreatorValue`
- `getCreatorRawPayload`
- `splitCreatorTags`
- `uniqueCompactItems`
- `getCreatorLocation`
- `getCreatorCategory`
- `getCreatorCollectedAt`
- `getCreatorXhsId`
- `getCreatorIntro`
- `getCreatorAvatarUrl`
- `getCreatorMetricChips`
- `getCreatorTags`
- `creatorHasTag`
- `projectBrandHint`
- `getCreatorNoteCases`
- `collectNoteCaseArrays`
- `getCreatorRealNoteCases`

### 注意事项

- 工具函数必须保持纯函数形态。
- 不引入 React 依赖。
- 避免形成循环依赖。

### 验收标准

- 项目卡片数据展示不变。
- 达人头像、标签、指标、链接展示不变。
- 构建通过。

## 阶段 3：抽评分和筛选计划逻辑

### 新增文件

```txt
utils/creatorScoring.js
utils/screeningPlan.js
utils/pgyFilters.js
```

### 迁移内容

`creatorScoring.js`：

- `reviewVariantFromStatus`
- `normalizeDimensionScore`
- `deriveDimensionScores`
- `getScoreColor`
- `getScoreTier`
- `getCreatorDetailStatus`
- `getProjectScoringCriteria`
- `getCreatorMatchProfile`
- `getMetricText`
- `getCreatorDeepAuditReason`
- `parseAuditReasonSections`
- `getCreatorRecommendation`
- `getCreatorFollowupInfo`
- `getCreatorTagGroups`
- `getPoolStage`
- `getCreatorUpdateLog`
- `getReviewVariant`

`screeningPlan.js`：

- `normalizeHardFilterItem`
- `normalizeHardFilterList`
- `looksLikeCollectionHardFilter`
- `getLegacyCollectionHardFilters`
- `getLegacyScoringHardFilters`
- `hardFilterOptionsFor`
- `normalizeWorkbenchPlan`
- `syncScreeningCriteria`

`pgyFilters.js`：

- `getHardFilterConditionKind`
- `hardFilterConditionsFor`
- `defaultHardFilterCondition`
- `getHardFilterOptionMeta`
- `splitHardFilterValue`
- `normalizeHardFilterValue`
- `cloneHardFilterOption`
- `mergeDefaultHardFilters`
- `mergeOptionItems`
- `normalizePgyFilterItem`
- `normalizePgyFilters`
- `markManualPgyFilters`
- `getSchemeRequiredFilters`
- `getSchemeAdditionalFilters`
- `getPgyFilterMeta`
- `getPgySelectedItems`
- `formatPgyFilterValue`
- `makePgyFilterItem`
- `makePgyFilterItemsFromValues`
- `replacePgyFieldFilters`
- `togglePgyCollectionFilter`

### 注意事项

- `creatorScoring.js` 可以依赖 `screeningPlan.js`，但 `screeningPlan.js` 不应反向依赖评分逻辑。
- 蒲公英相关逻辑依赖常量，需等阶段 4 或同步拆出常量后再迁移。

### 验收标准

- 达人评分、推荐理由、匹配标签不变。
- 筛选计划保存结构不变。
- 蒲公英筛选项增删改行为不变。

## 阶段 4：抽常量

### 新增文件

```txt
constants/projectConstants.js
constants/pgyConstants.js
constants/screeningConstants.js
```

### 迁移内容

`projectConstants.js`：

- `STEPS`
- `PROJECT_ID`
- 项目默认状态相关配置

`pgyConstants.js`：

- `DEFAULT_PGY_DISPLAY_METRICS`
- `PGY_FOLLOWER_RANGE_OPTIONS`
- `PGY_FAN_AGE_OPTIONS`
- `PGY_MATERNAL_STAGE_OPTIONS`
- `PGY_BLOGGER_CATEGORY_OPTIONS`
- `PGY_REGION_OPTIONS`
- `PGY_MARKETING_GOAL_OPTIONS`
- `PGY_FAMILY_IDENTITY_OPTIONS`
- `PGY_CAREER_IDENTITY_OPTIONS`
- `PGY_SPECIAL_BACKGROUND_OPTIONS`
- `PGY_PRICE_RANGE_OPTIONS`
- `PGY_UNIT_PRICE_OPTIONS`
- `PGY_NOTE_COUNT_RANGE_OPTIONS`
- `PGY_INTERACTION_RANGE_OPTIONS`
- `PGY_RATE_RANGE_OPTIONS`
- `PGY_LIVE_COUNT_OPTIONS`
- `PGY_LIVE_VIEWER_OPTIONS`
- `PGY_LIVE_SALES_OPTIONS`
- `PGY_FILTER_OPTIONS`
- `PGY_FIND_BLOGGER_FILTER_GROUPS`
- `PGY_FILTER_CATALOG_UI`
- `PGY_FILTER_CATALOG_BY_FIELD`
- `PGY_SINGLE_VALUE_CONTROLS`

`screeningConstants.js`：

- `WEIGHT_LABELS`
- `HARD_FILTER_OPTIONS`
- `HARD_FILTER_CONDITIONS_BY_KIND`
- `DEFAULT_HARD_FILTER_CONDITIONS`
- `DISPLAY_METRIC_OPTIONS`
- `PGY_REQUIRED_FILTER_FIELDS`
- `PGY_ADDITIONAL_FILTER_FIELDS`
- `DEFAULT_COLLECTION_HARD_FILTER_FIELDS`
- `DEFAULT_SCORING_HARD_FILTER_FIELDS`
- `CONTROL_TYPE_LABELS`

### 注意事项

- 常量迁移容易导致 import 链路变复杂，需保持分层清晰。
- 不改变任何选项内容、顺序、默认值。

### 验收标准

- 筛选器选项完整。
- 默认筛选计划和默认硬性标准不变。
- 构建通过。

## 阶段 5：抽项目组件

### 新增文件

```txt
components/project/ProjectsPreview.jsx
components/project/ProjectCard.jsx
components/project/CreateProjectModal.jsx
components/project/ProjectSetupTab.jsx
```

### 迁移内容

- `ProjectsPreview`
- `ProjectCard`
- `CreateProjectModal`
- `ProjectSetupTab`

### 注意事项

- `ProjectSetupTab` 当前包含项目基础信息、筛选标准、飞书绑定。第一轮可以整体迁移，不在本阶段继续拆细。
- `ProjectSetupTab` 需要的筛选器组件和工具函数可能尚未拆完，应按 import 依赖补齐。

### 验收标准

- 项目列表正常展示。
- 项目搜索、筛选、视图切换正常。
- 新建项目弹窗可打开、关闭、创建。
- 归档、恢复、删除正常。
- 项目设置保存正常。
- 飞书配置区展示正常。

## 阶段 6：抽筛选器组件

### 新增文件

```txt
components/filters/SelectableMenu.jsx
components/filters/SelectedChips.jsx
components/filters/PgyFilterCards.jsx
components/filters/PgyFilterPopover.jsx
components/filters/PgyFindBloggerFilterPanel.jsx
components/filters/HardFilterEditor.jsx
components/filters/HardFilterValueControl.jsx
```

### 迁移内容

- `SelectableMenu`
- `SelectedChips`
- `PgyFilterCards`
- `PgyFilterPopover`
- `PgyFindBloggerFilterPanel`
- `HardFilterEditor`
- `HardFilterValueControl`

### 注意事项

- 这是高风险阶段，因为筛选器和计划结构强绑定。
- 不改变组件 props。
- 不改变字段名、选项 key、筛选项结构。

### 验收标准

- 蒲公英筛选项可打开、选择、清空、应用。
- 多选、单选、区间输入、自定义输入正常。
- 硬性标准可新增、删除、编辑。
- 保存筛选计划后 payload 结构不变。

## 阶段 7：抽业务 Tab

### 新增文件

```txt
components/overview/OverviewTab.jsx
components/screening-review/ScreeningReviewTab.jsx
components/screening-review/CreatorDetailModal.jsx
components/screening-review/CreatorRecentNotesPanel.jsx
components/creator-audit/CreatorAuditTab.jsx
components/creator-pool/ScorePreviewTab.jsx
components/logs/AuditLogTab.jsx
components/config/AdvancedConfigTab.jsx
```

### 迁移内容

- `OverviewTab`
- `ScreeningReviewTab`
- `CreatorDetailModal`
- `CreatorRecentNotesPanel`
- `CreatorAuditTab`
- `ScorePreviewTab`
- `AuditLogTab`
- `AdvancedConfigTab`

### 注意事项

- 保持原 props，不在本阶段引入新的全局状态。
- 与 `ScreeningDashboard.jsx` 的交互仍通过 props 传递。
- 不改变 tab key。

### 验收标准

- 所有 tab 可正常切换。
- 概览页筛选计划编辑和保存正常。
- 初筛审核、批量操作、详情弹窗正常。
- 审号工作台搜索、筛选、审核正常。
- 达人池阶段切换、指标更新、写回设置、导出正常。
- 日志筛选正常。
- AI 配置保存和测试正常。

## 阶段 8：收缩 ScreeningDashboard.jsx

### 保留内容

最终 `ScreeningDashboard.jsx` 只保留：

- 当前 tab 状态
- 当前项目状态
- 项目列表状态
- 飞书配置状态
- 页面级 message 状态
- 数据加载编排
- handler 编排
- tab 渲染分发
- 子组件 props 传递

### 目标规模

- 当前规模：约 5600 行。
- 第一轮拆分目标：约 300 到 600 行。

### 验收标准

- `ScreeningDashboard.jsx` 变成页面编排层。
- 主要业务组件、工具函数、常量均已迁移到独立文件。
- 功能行为与拆分前一致。

## 推荐执行顺序

1. 建立基线和回归清单。
2. 抽 API 层。
3. 抽格式化、项目映射、达人映射工具。
4. 抽评分、筛选计划、蒲公英筛选逻辑。
5. 抽常量。
6. 抽项目组件。
7. 抽筛选器组件。
8. 抽业务 Tab。
9. 收缩 `ScreeningDashboard.jsx`。
10. 构建验证和关键路径回归。

## 风险控制

### 循环依赖

风险：工具函数拆分后互相 import，形成循环依赖。

处理方式：

- 常量只能被工具和组件引用。
- 工具函数尽量单向依赖。
- 组件可以引用工具，但工具不能引用组件。
- API 层不引用组件。

### 默认值丢失

风险：项目、达人、筛选计划字段很多，迁移时可能丢 fallback。

处理方式：

- 迁移时保持原函数体不改。
- 优先复制原逻辑，再调整 import。
- 每个 mapper 迁移后检查空数据和旧数据兼容。

### 筛选计划结构变化

风险：蒲公英筛选器和硬性标准的保存结构变化，会影响后端和飞书字段映射。

处理方式：

- 不改字段名。
- 不改默认选项。
- 保存前后对比 payload。

### UI 回归

风险：组件迁移后样式或布局异常。

处理方式：

- CSS 类名不改。
- 不调整 DOM 层级，除非 import 必须。
- 迁移后做页面截图或人工检查。

### API 行为变化

风险：请求封装后错误提示、请求体、URL 参数变化。

处理方式：

- 第一轮保留原始 `api(url, options)` 能力。
- 语义化 API 函数后置。
- 用浏览器 Network 或测试输出确认请求一致。

## 回归检查清单

### 项目

- 项目列表能加载。
- 可以选择项目。
- 可以新建项目。
- 可以归档项目。
- 可以恢复项目。
- 可以删除项目。
- 项目卡片进度、周期、预算、状态显示正常。

### 项目设置

- 基础信息可编辑和保存。
- 筛选计划可编辑和保存。
- 生成筛选标准可用。
- 飞书链接可保存。
- 飞书连接测试可用。
- 飞书表格和字段可读取。
- 飞书写回按钮可用。

### 概览

- 项目基本信息显示正常。
- 目标达人数量、通过数量、进度显示正常。
- 蒲公英筛选计划展示正常。
- 筛选计划展开、编辑、保存正常。

### 初筛审核

- 达人列表显示正常。
- 搜索、筛选、排序正常。
- 单选、多选正常。
- 单人审核正常。
- 批量审核正常。
- 达人详情弹窗正常。
- 重新评分、导入、刷新按钮正常。

### 审号工作台

- 达人匹配度列表显示正常。
- 搜索和筛选正常。
- 审核操作正常。
- 详情和推荐理由显示正常。

### 达人池

- 阶段 tab 切换正常。
- 标签筛选正常。
- 达人卡片显示正常。
- 阶段更新正常。
- 指标更新正常。
- 自动写回设置正常。
- CSV 导出正常。

### 日志和配置

- 操作日志显示正常。
- 日志类型筛选正常。
- AI 配置读取正常。
- AI 配置保存正常。
- AI 测试正常。

## 拆分完成后的后续工作

第一轮拆分稳定后，再考虑把以下能力提升到多工作台共享层：

- 项目上下文：`ProjectContext`
- 项目入口：`ProjectHub`
- 项目卡片：`ProjectCard`
- 项目动态：`ProjectTimeline`
- 飞书绑定：`IntegrationBinding`
- 项目指标：`ProjectMetrics`

这些能力将服务完整项目协作链路：

```txt
立项 -> 策划产出 -> 执行拆解 -> 媒介/达人协作 -> 交付跟进 -> 数据回流 -> 复盘归档
```

本次拆分不直接做这一步，避免结构拆分和业务改造叠加造成风险。
