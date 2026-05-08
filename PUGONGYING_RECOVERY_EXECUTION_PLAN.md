# 蒲公英采集与达人池管理恢复执行计划

日期：2026-05-08  
项目：有道答疑笔5-6月合作  
依据：`PROJECT_CHAT_RECORD_SUMMARY.md`、当前恢复版代码、`原首页.zip`、聊天记录中已确认的产品口径。

## 1. 目标

本计划用于恢复并完善以下能力：

- 原前端界面和聊天记录中确认过的前端优化。
- 蒲公英真实浏览器采集。
- 完整达人池写入、评分、审核、管理流程。
- 飞书电子表格 / 多维表格字段读取与按字段写回。
- API 配置独立管理能力保留。

最终目标是让系统围绕 `有道答疑笔5-6月合作` 单项目形成闭环：

```text
立项 + 标准 + 飞书绑定
-> 蒲公英博主广场采集
-> 达人详情补全
-> AI/规则评分
-> 人工审核
-> 写入本地达人池
-> 写回飞书
-> 操作日志留痕
```

## 2. 当前基础

当前已经恢复的基础能力：

- FastAPI 后端：`rpa_mcp_sync`
- 旧首页最小入口：
  - `screening-workbench.html`
  - `screening-workbench.css`
  - `screening-workbench.js`
- 飞书配置接口：
  - `GET /api/projects/feishu/connection`
  - `POST /api/projects/feishu/connection`
  - `POST /api/projects/feishu/test`
  - `GET /api/projects/feishu/tables`
  - `GET /api/projects/feishu/fields`
  - `POST /api/projects/feishu/records`
- API 配置接口：
  - `GET /api/llm/config`
  - `POST /api/llm/config`
  - `POST /api/llm/test`
- React 前端 `ad-workbench` 仍可构建。
- `原首页.zip` 已确认包含完整原前端源码，核心文件包括：
  - `ad-workbench/src/pages/screening/ScreeningDashboard.jsx`
  - `ad-workbench/src/styles/index.css`
  - `ad-workbench/src/pages/admin/AdminDashboard.jsx`
  - 其它角色页和公共组件。

当前仍缺失或未完成：

- 蒲公英真实浏览器自动化采集。
- 完整达人池持久化。
- 评分、审核、批次、日志全链路。
- 原前端界面与恢复版后端的重新接入。
- 飞书写回 UI 与字段映射 UI。

## 3. 阶段一：备份与恢复原前端

### 目标

恢复 `原首页.zip` 中的原前端体验，同时保留已经恢复的后端接口和独立 API 配置。

### 操作

1. 创建备份目录：

```text
backup/recovery-before-original-home-YYYYMMDD-HHMMSS
```

备份：

- `ad-workbench`
- `screening-workbench.html`
- `screening-workbench.css`
- `screening-workbench.js`
- `rpa_mcp_sync`
- `tests`

2. 解压 `原首页.zip` 到临时目录：

```text
runtime/original-home-extract
```

3. 对比当前 `ad-workbench` 与压缩包中的 `ad-workbench`。

重点文件：

```text
ad-workbench/src/pages/screening/ScreeningDashboard.jsx
ad-workbench/src/styles/index.css
ad-workbench/src/pages/WorkbenchLayout.jsx
ad-workbench/src/pages/admin/AdminDashboard.jsx
```

4. 恢复原筛选工作台页面。

保留或合并当前已有优化：

- 独立 `API 配置` 菜单。
- API 配置不能和飞书配置放在一起。
- 飞书配置只能面向非技术人员展示 `飞书链接 / App ID / App Secret`。

### 聊天记录中必须保留的前端优化

- 只保留 `有道答疑笔5-6月合作` 一个项目。
- 所有项目显示业务名称，不显示 `project_id`。
- 项目指标改为：
  - `总合格达人数`
  - `现有达人池`
  - `合格占比`
- 合格占比口径：

```text
现有合格达人数 / 目标合格达人数
```

- `需求量化` 属于 `立项 + 标准 + 飞书绑定`，不属于 `候选评分预览`。
- 右上角项目选择放到大标题下面。
- 项目选择切换时自动切换内容。
- 操作日志、最近任务、飞书校验、任务状态尽量中文化。
- 去掉面向用户的冗余说明文案。

### 验收

```powershell
cd D:\第三事业部\ad-workbench
npm run build
```

访问：

```text
http://127.0.0.1:8797/workbench/screening
```

或当前路由体系下对应筛选工作台入口。

## 4. 阶段二：建立达人池数据模型

### 目标

建立本地可持久化的达人池、评分、审核、批次和日志数据层。

### 推荐存储

优先使用 SQLite：

```text
runtime/tasks.db
```

原因：

- 适合本地工作台。
- 支持去重、查询、分页、批次、状态流转。
- 后续导出 CSV / 写回飞书都方便。

### 数据表

#### projects

项目表。

核心字段：

- `project_id`
- `project_name`
- `target_qualified_creator_count`
- `period_start`
- `period_end`
- `brief`
- `created_at`
- `updated_at`

#### creators

达人主表。

核心字段：

- `creator_id`
- `project_id`
- `source`
- `xiaohongshu_id`
- `pgy_blogger_id`
- `pgy_url`
- `nickname`
- `creator_type`
- `persona_tags`
- `ip_city`
- `profile_url`
- `avatar_url`
- `status`
- `created_at`
- `updated_at`

#### creator_metrics

达人指标表。

核心字段：

- `creator_id`
- `followers_count`
- `quote_price`
- `budget_status`
- `traffic_stability`
- `rate_limit_risk`
- `natural_cpc`
- `natural_cpe`
- `search_recommend_ratio`
- `fans_35_plus_ratio`
- `child_age`
- `child_grade`
- `child_gender`
- `topic_point`
- `cost_30d`
- `cost_90d`
- `collected_at`

#### creator_scores

评分表。

核心字段：

- `creator_id`
- `total_score`
- `budget_score`
- `fans_score`
- `cpe_score`
- `traffic_score`
- `persona_score`
- `content_score`
- `hard_filter_passed`
- `score_reason`
- `scored_at`

#### screening_reviews

人工审核表。

核心字段：

- `creator_id`
- `review_status`
- `review_reason`
- `reviewer`
- `reviewed_at`

状态建议：

- `待补数据`
- `待审核`
- `已通过`
- `备选`
- `已驳回`
- `已写回飞书`

#### collection_batches

采集批次表。

核心字段：

- `batch_id`
- `project_id`
- `source_url`
- `status`
- `started_at`
- `finished_at`
- `total_count`
- `success_count`
- `failed_count`
- `error_message`

#### operation_logs

操作日志表。

核心字段：

- `log_id`
- `project_id`
- `action_type`
- `action`
- `target`
- `operator`
- `detail`
- `status`
- `created_at`

### 初始导入

导入现有模板：

```text
有道答疑笔5-6月合作_测试项目/03_达人池实体表.csv
```

作为当前项目初始达人池字段模板。

### 后端接口

新增：

```text
GET  /api/projects
GET  /api/projects/{project_id}
POST /api/projects/{project_id}

GET  /api/projects/{project_id}/creators
POST /api/projects/{project_id}/creators
POST /api/projects/{project_id}/creators/import
PATCH /api/projects/{project_id}/creators/{creator_id}

POST /api/projects/{project_id}/creators/score
POST /api/projects/{project_id}/creators/review

GET  /api/projects/{project_id}/batches
GET  /api/projects/{project_id}/logs
```

### 验收

- 首页项目卡片读取真实达人池数量。
- `现有达人池` 由数据库计算。
- `总合格达人数` 由审核通过数量计算。
- CSV 模板可导入。
- 操作日志可记录导入、审核、写回等动作。

## 5. 阶段三：蒲公英真实浏览器采集

### 目标

让用户登录蒲公英后，系统可以在真实页面上执行采集。

### 技术路线

使用 Playwright + Chrome DevTools Protocol。

支持两种模式：

1. 连接用户已经打开的调试 Chrome。
2. 启动独立调试 Chrome profile。

建议启动命令：

```powershell
Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" -ArgumentList "--remote-debugging-port=9222","--profile-directory=Default"
```

如果默认 profile 无法开启调试端口，则启动独立 profile。

### 用户流程

1. 用户点击“启动蒲公英采集”。
2. 系统检查 Chrome 调试端口。
3. 如果未登录，提示用户登录。
4. 用户进入：

```text
https://pgy.xiaohongshu.com/solar/pre-trade/note/kol
```

5. 系统识别当前是否在“博主广场 / 找博主”页面。
6. 系统读取列表页达人。
7. 系统按规则进入详情页补全数据。
8. 系统写入本地达人池。

### 页面选择器

聊天记录中已验证：

列表页达人行：

```text
.blogger-list_list .d-new-table tbody tr
```

进入详情页稳定点击点：

```text
.profile
```

详情页需要操作：

- `数据概览`
- `笔记数据 -> 合作笔记`
- `粉丝分析 -> 粉丝画像`

粉丝画像截图范围：

```text
粉丝画像标题 + 性别分布 + 年龄分布
```

优先选择器：

```text
.contentPic.fansPic
```

### 采集输出结构

每个达人输出：

```json
{
  "source": "pgy",
  "xiaohongshu_id": "",
  "pgy_blogger_id": "",
  "pgy_url": "",
  "nickname": "",
  "creator_type": "",
  "quote_price": 0,
  "followers_count": 0,
  "natural_cpc": null,
  "natural_cpe": null,
  "search_recommend_ratio": null,
  "fans_35_plus_ratio": null,
  "traffic_stability": "",
  "rate_limit_risk": "",
  "audience_profile_screenshot": "",
  "raw_payload": {}
}
```

### 后端接口

新增：

```text
POST /api/pgy/browser/start
GET  /api/pgy/browser/status
POST /api/pgy/collect/list
POST /api/pgy/collect/detail
POST /api/pgy/collect/batch
GET  /api/pgy/collect/batches/{batch_id}
```

### 验收

- 能检测 Chrome 是否可连接。
- 未登录时给出明确提示。
- 已登录后能识别博主广场列表。
- 能读取可见达人基础信息。
- 能进入详情页。
- 能切换合作笔记和粉丝画像。
- 能生成截图文件。
- 能写入本地达人池。

## 6. 阶段四：评分、去重与审核

### 目标

把采集数据转成有道项目可用的候选池，并支持审核决策。

### 去重规则

优先级：

1. 小红书号
2. 蒲公英详情 ID
3. 蒲公英链接
4. 昵称 + 粉丝数 + 报价组合

重复处理：

- 已存在达人更新指标。
- 保留最新采集批次。
- 不覆盖人工审核结果，除非用户明确重新审核。

### 有道项目硬性规则

必须满足或重点判断：

- 蒲公英链接存在。
- 单个达人报价低于 2 万。
- 35 岁以上粉丝占比大于 40%，不符合直接 pass。
- 搜索 + 推荐流量占比大于 40%。
- 合作笔记自然 CPC 低于 2。
- 合作笔记自然 CPE 低于 20，最好低于 10。
- 外溢进店成本 30/90 天低于 50。
- 孩子年龄聚焦小升初、初高中。
- 优先北京、上海 IP。
- 规避疑似限流账号。

### 评分维度

建议 100 分制：

- 预算匹配：20
- 粉丝画像：20
- 流量来源：15
- CPC/CPE 效率：15
- 人设匹配：20
- 内容与话题度：10

### 状态流转

```text
待补数据
-> 待审核
-> 已通过 / 备选 / 已驳回
-> 已写回飞书
```

### 前端管理

达人池表格需要支持：

- 筛选状态。
- 搜索昵称。
- 查看详情。
- 查看评分原因。
- 单个审核。
- 批量审核。
- 批量写回飞书。
- 导出 CSV。

### 验收

- 同一个达人不会重复入库。
- 评分规则有可解释原因。
- 人工审核不被后续采集覆盖。
- 审核操作写入操作日志。

## 7. 阶段五：飞书完整写回闭环

### 目标

支持把本地审核后的达人池按字段写入飞书电子表格或多维表格。

### 已恢复基础

当前已有接口：

```text
GET  /api/projects/feishu/connection
POST /api/projects/feishu/connection
GET  /api/projects/feishu/tables
GET  /api/projects/feishu/fields
POST /api/projects/feishu/records
```

### 需要补齐的 UI

飞书配置页只展示：

```text
飞书链接
App ID
App Secret
```

测试连接成功后展示：

- 资源类型：电子表格 / 多维表格
- 可选子表列表
- 当前选中子表
- 读取到的字段列表

字段映射 UI：

- 标准字段
- 飞书字段
- 字段类型
- 是否可写
- 是否必填

### 标准字段

至少包括：

- 达人ID
- 达人昵称
- 蒲公英链接
- 达人类型
- 人设标签
- IP城市
- 报价
- 预算状态
- 粉丝数
- 近30天流量稳定性
- 限流风险判断
- 合作笔记自然CPC
- 合作笔记自然CPE
- 搜索+推荐占比
- 35岁以上粉丝占比
- 孩子年龄
- 孩子年级
- 孩子性别
- 家庭/教育话题点
- 30天外溢进店成本
- 90天外溢进店成本
- 推荐等级
- 当前状态
- 备注

### 写回策略

- 只写 `已通过` 和 `备选`，除非用户手动选择其它状态。
- 按字段名映射写入。
- 多维表格走 `batch_create`。
- 电子表格按首行字段顺序 append。
- 不写只读字段、公式字段。
- 写回前做必填校验。
- 按小红书号 / 蒲公英 ID / 蒲公英链接去重。
- 写回结果记录批次与日志。

### 错误提示

必须面向非技术用户：

- 权限不足：显示“打开飞书权限配置”按钮。
- 子表未选择：显示可选子表。
- 字段缺失：提示缺少哪些字段。
- 字段不可写：提示哪些字段跳过。
- 链接类型识别：展示“电子表格”或“多维表格”，不要求用户理解 API。

### 验收

- 能读取用户提供的飞书链接。
- 能识别 sheet / bitable。
- 能列出子表。
- 能读取字段。
- 能保存字段映射。
- 能写入审核通过达人。
- 写回后本地状态变为 `已写回飞书`。

## 8. 阶段六：验证与交付

### 自动化测试

后端测试：

```powershell
python -m pytest -q
```

前端构建：

```powershell
cd D:\第三事业部\ad-workbench
npm run build
```

JS 语法：

```powershell
node --check D:\第三事业部\screening-workbench.js
```

### 测试覆盖

必须覆盖：

- 飞书 URL 解析。
- Wiki sheet 链接识别。
- base 链接识别。
- 多子表 `ambiguous_table_id`。
- 字段读取。
- 达人导入。
- 达人去重。
- 评分规则。
- 审核状态流转。
- 写回计划生成。
- API 配置保存和测试。

### 真实页面验证

1. 启动服务：

```powershell
D:\第三事业部\run_server.ps1
```

2. 打开首页：

```text
http://127.0.0.1:8797
```

3. 打开蒲公英博主广场：

```text
https://pgy.xiaohongshu.com/solar/pre-trade/note/kol
```

4. 登录后执行采集。
5. 检查本地达人池新增记录。
6. 审核通过 1-2 条测试记录。
7. 写回飞书测试表。
8. 查看飞书表中新增行。
9. 检查操作日志。

## 9. 推荐执行顺序

推荐顺序：

1. 阶段一：恢复原前端。
2. 阶段二：建立达人池数据模型。
3. 阶段三：蒲公英真实浏览器采集。
4. 阶段四：评分、去重与审核。
5. 阶段五：飞书完整写回闭环。
6. 阶段六：验证与交付。

原因：

- 原前端决定用户工作流入口。
- 达人池模型决定后续采集写入结构。
- 蒲公英采集依赖达人池落库。
- 评分审核依赖采集数据完整。
- 飞书写回依赖审核结果和字段映射。

## 10. 里程碑

### M1：原前端恢复

交付：

- 原界面恢复。
- 有道单项目展示。
- API 配置保留独立入口。
- 飞书配置改为非技术三字段。

### M2：达人池本地闭环

交付：

- CSV 初始达人池导入。
- 达人列表、状态、审核、日志可用。
- 项目指标真实计算。

### M3：蒲公英采集闭环

交付：

- 浏览器连接。
- 博主广场列表采集。
- 详情页补全。
- 粉丝画像截图。
- 入库去重。

### M4：评分审核闭环

交付：

- 有道规则评分。
- 人工审核。
- 批量操作。
- 操作日志。

### M5：飞书写回闭环

交付：

- sheet / bitable 均可识别。
- 子表选择。
- 字段映射。
- 审核达人写回。
- 写回结果日志。

## 11. 风险与注意事项

- 蒲公英页面 DOM 可能变化，采集选择器需要容错。
- 独立调试 Chrome 不继承默认登录态，可能需要用户重新登录。
- 飞书电子表格以首行作为字段名，如果首行为空或合并单元格较多，需要提示用户整理表头。
- 多维表格公式字段不可写，必须跳过。
- App Secret、API Key 不允许明文回显。
- 不要在非技术用户界面展示 lark-cli、OpenAPI 路径、事件订阅等技术细节。
- 测试配置不能污染真实 `config/projects/youdao_001.*`。

## 12. 完成定义

当以下条件全部满足时，视为恢复完成：

- 首页恢复原工作台体验。
- 有道项目可以看到真实达人池数量和合格数量。
- 用户登录蒲公英后可以一键采集列表与详情。
- 采集结果能进入本地达人池。
- 系统能根据有道 Brief 给出评分和推荐等级。
- 人工审核可以改状态并留日志。
- 飞书配置只需要填链接、App ID、App Secret。
- 系统能识别用户给的飞书电子表格链接。
- 系统能读取子表字段并写入审核通过达人。
- API 配置独立可用，不和飞书配置混放。
