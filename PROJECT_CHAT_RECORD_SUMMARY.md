# 第三事业部项目聊天记录配置总结

整理时间：2026-05-08  
整理范围：本机 Codex 会话记录中与 `D:\第三事业部` 相关的内容，以及当前目录仍可见的项目文件。  
重点范围：飞书配置、API 配置、蒲公英采集、项目筛选标准、当前状态与遗留事项。

## 1. 当前项目概况

当前目录在撤回删除后只恢复了部分内容，实际可见内容包括：

- `ad-workbench`：React + Vite 前端工作台。
- `有道答疑笔5-6月合作_测试项目`：当前保留的业务测试项目资料。
- `插件参考1`：恢复出的浏览器插件参考文件，目前仅看到 `靓号.crx`。

聊天记录中曾经存在但当前目录已不可见的核心代码目录包括：

- `browser_extension`
- `rpa_mcp_sync`
- `config`
- `runtime`
- `scripts`
- `tests`
- 根目录旧入口 `screening-workbench.html` / `screening-workbench.js`

这意味着：聊天记录中有一部分功能已经实现和验证过，但对应源码目前不在当前工作区，不能直接运行或继续补丁。后续如果要恢复后端能力，需要先找回这些目录，或按本文档重新实现。

## 2. 有道答疑笔项目业务配置

项目名称统一为：

```text
有道答疑笔5-6月合作
```

业务 Brief 已整理在：

```text
D:\第三事业部\有道答疑笔5-6月合作_测试项目\brief.txt
```

生成出的测试资料包括：

- `01_项目brief.csv`
- `02_筛选标准.csv`
- `03_达人池实体表.csv`
- `04_字段字典.csv`
- `有道答疑笔5-6月合作_测试项目.xlsx`

核心筛选口径：

- 规避疑似限流达人，优先真实化、流量稳定账号。
- 单个达人预算低于 2 万，总达人预算暂定 12 万。
- 发布时间：5 月 7 日至 5 月 19 日。
- 达人数量：10 位，曝光型 50%，教育垂类或卖货型 50%。
- 人设方向：高知家庭、教师人设、教育、亲子、中产家庭、北京上海 IP 优先。
- 合作笔记自然流量下 CPC 低于 2，CPE 低于 20，最好低于 10。
- 阅读流量来源中搜索 + 推荐大于 40%。
- 粉丝 35 岁以上占比大于 40%，该项不符合直接 pass。
- 孩子年龄聚焦小升初、初高中。
- 表格中需要标注孩子年龄、年级、性别。
- 不需要小红书主页链接，需要蒲公英链接。
- 外溢进店成本越低越好，30/90 天内成本标准为 50 以下。

项目卡片指标口径在聊天中已确定为业务指标：

- `总合格达人数`
- `现有达人池`
- `合格占比`

其中合格占比最终口径为：

```text
现有合格达人数 / 目标合格达人数
```

目标合格达人数默认曾设为 `200`，并且在“立项 + 标准 + 飞书绑定”里可配置目标合格达人数、项目周期开始、项目周期结束。

## 3. 飞书配置演进

### 3.1 最初目标

用户要求飞书配置面向非技术人员，不展示 `lark-cli` 命令、事件订阅、写入方式、自动配置向导等技术细节。

最终前端配置项应只保留：

```text
飞书链接
App ID
App Secret
```

曾经提过“飞书机器人配置”，但后续明确要求去掉机器人配置，只让用户填链接、appid、appsecret。

### 3.2 首页入口

最初曾误改到 `ad-workbench` 管理员系统配置页，后续用户指出实际首页是旧工作台：

```text
http://127.0.0.1:8797
```

因此飞书配置最终应在首页的：

```text
立项 + 标准 + 飞书绑定 -> 飞书绑定 / 飞书配置
```

而不是放进独立管理员系统配置页，也不是和 API 配置混在一起。

### 3.3 后端接口约定

聊天记录中曾新增过后端保存/读取接口：

```text
GET  /api/projects/feishu/connection
POST /api/projects/feishu/connection
```

连接文件路径约定：

```text
config/projects/{project_id}.feishu.connection.json
```

有道答疑笔项目对应：

```text
config/projects/youdao_001.feishu.connection.json
```

安全要求：

- `App Secret` 保存后不明文回显。
- 前端只显示已配置状态。
- `*.feishu.connection.json` 不能被当作普通项目配置混入 `/api/overview`，避免密钥类内容出现在项目列表或首页响应里。

### 3.4 已验证情况

聊天记录里有一次验证结果：

- 当前保存的 lark-cli App 凭证可用。
- 消息推送曾成功两次。
- 最近一次返回过 `message_id`：

```text
om_x100b50edf0f1f544b2eb2515e69b98e
```

但也明确指出：

- 当时服务端没有找到当前项目已落盘的飞书链接配置。
- `config/projects/youdao_001.feishu.connection.json` 当时不存在。
- 旧的 `runtime/smoke/tables.cli.yaml` 是占位配置。
- 用占位配置实际读表报过 `NOTEXIST`，不能冒充真实读取/写入成功。

结论：

- 消息推送曾经跑通过。
- Base / Sheet 的读取写入没有完整跑通。
- 需要用户在首页重新保存一次链接、App ID、App Secret，生成项目连接文件后再测。

### 3.5 飞书链接示例

用户提供过真实表格链接；为避免泄露，仓库文档中仅保留脱敏示例：

```text
https://example.feishu.cn/wiki/WIKI_TOKEN?renamingWikiNode=false&sheet=SHEET_ID
```

校验状态曾返回：

```text
项目编号：youdao_001
配置文件：config\projects\youdao_001.feishu.connection.json
飞书链接：<已脱敏>
飞书应用：<已脱敏>，密钥：是
连接问题：unsupported_wiki_object:sheet
```

这里的关键判断是：该链接指向飞书 Wiki 下的电子表格 `sheet`，不是多维表格 `bitable/base`。

### 3.6 权限提示优化

飞书 API 返回权限不足时，会给出权限开通链接。用户要求前端不要笼统报错，而要展示可点击入口。

聊天中已完成过的设计：

- 后端返回 `missing_wiki_permission` 时，前端从错误 `message` 中提取飞书权限开通 URL。
- 前端显示按钮：

```text
打开飞书权限配置
```

这样非技术用户可以直接点击授权，而不是只看到“校验失败”。

### 3.7 电子表格与多维表格统一支持规划

用户最终明确需求：

在飞书机器人配置且权限足够的情况下，系统要同时支持：

- 飞书电子表格 `sheets`
- 飞书多维表格 `bitable/base`
- 同一个链接下多个子表
- 读取字段
- 按字段写入

聊天中确定的技术方向是抽象成“远端表目标”，不要把电子表格硬塞进多维表逻辑：

配置新增：

```text
resource_type:
  bitable  # 飞书多维表格
  sheet    # 飞书电子表格
```

链接解析：

- Wiki 链接先读 `wiki_node`。
- `obj_type=bitable` 走多维表格 API。
- `obj_type=sheet` 走电子表格 API。

子表选择：

- 多维表：一个 base 下可能有多个 table。
- 电子表格：一个 spreadsheet 下可能有多个 sheet。
- URL 里有 `table=` 或 `sheet=` 时直接选中。
- URL 没有指定子表时返回 `ambiguous_table_id`，前端展示可选子表名称和 ID。

字段读取：

- 多维表：调用 bitable 字段接口读取字段列表。
- 电子表格：读取首行作为字段名。

按字段写入：

- 多维表：按字段名执行 `batch_create` / `batch_update`。
- 电子表格：按首行字段映射列，新增行 append，更新行按行号覆盖对应行。

聊天中列出的待实现函数：

```text
FeishuClient.list_sheet_tabs()
FeishuClient.list_sheet_fields()
FeishuClient.list_sheet_records()
FeishuClient.apply_sheet_plan()
resolve_feishu_table_target()
```

还需要补：

- sheet 多子表选择。
- 前端展示 `available_tables`。
- sheet / bitable 两类读写测试覆盖。

当前状态：由于源码目录已丢失，这部分只停留在方案和部分已完成的错误提示，不具备当前可运行代码。

## 4. API 配置

### 4.1 用户要求

当前项目需要独立的 API 配置界面，支持：

- Gemini
- OpenAI
- OpenAI 兼容服务
- 配置 `base-url`
- 配置模型名
- 配置 API Key
- 配置环境变量名
- 配置生成参数

用户明确指出：

```text
这个是独立的设置，跟飞书配置不要放在一起
```

因此 API 配置应独立于飞书绑定页。

### 4.2 当前可见前端实现

当前 `ad-workbench` 里仍能看到 API 配置页实现。

相关文件：

```text
D:\第三事业部\ad-workbench\src\pages\WorkbenchLayout.jsx
D:\第三事业部\ad-workbench\src\pages\admin\AdminDashboard.jsx
D:\第三事业部\ad-workbench\src\styles\index.css
```

管理员导航里有：

```text
API 配置
```

React 组件名：

```text
TabApiSettings
```

默认配置：

```js
{
  protocol: 'openai-compatible',
  base_url: 'https://api.openai.com/v1',
  model: 'gpt-4.1-mini',
  api_key: '',
  api_key_env: 'OPENAI_API_KEY',
  temperature: 0.2,
  max_tokens: 1200,
  timeout_seconds: 60
}
```

协议切换默认值：

```js
openai-compatible:
  base_url: https://api.openai.com/v1
  model: gpt-4.1-mini
  api_key_env: OPENAI_API_KEY

gemini:
  base_url: https://generativelanguage.googleapis.com/v1beta
  model: gemini-2.5-flash
  api_key_env: GEMINI_API_KEY
```

前端调用接口：

```text
GET  /api/llm/config
POST /api/llm/config
POST /api/llm/test
```

保存逻辑：

- 优先调用后端 `/api/llm/config`。
- 如果后端不可用，退化保存到浏览器 `localStorage`：

```text
adflow-api-config
```

安全显示：

- API Key 页面读取时不回显。
- 保存新 Key 后输入框自动清空。
- 状态区显示 Key 是否已配置、来源是环境变量还是配置文件。

### 4.3 当前缺口

当前目录只看到前端 `ad-workbench`，没有后端 `rpa_mcp_sync` 等目录。

因此：

- `/api/llm/config` 当前没有可见后端实现。
- `/api/llm/test` 当前没有可见后端实现。
- 前端可以构建，但真实接入模型服务需要恢复或重建后端接口。

建议后端配置文件路径沿用聊天中显示的：

```text
config/ai_provider.yaml
```

建议后端返回结构保持前端预期：

```json
{
  "config": {
    "protocol": "openai-compatible",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4.1-mini",
    "api_key_env": "OPENAI_API_KEY",
    "temperature": 0.2,
    "max_tokens": 1200,
    "timeout_seconds": 60,
    "path": "config/ai_provider.yaml",
    "api_key_configured": true,
    "api_key_source": "env",
    "using_example_config": false
  },
  "message": "API 配置已保存"
}
```

## 5. 蒲公英 / 小红书采集链路

### 5.1 技术路线变化

原先有浏览器插件 `browser_extension`，后来用户要求：

```text
把原先插件的功能，改为浏览器功能，要求用户先登录，后续直接在博主广场进行我们的采集操作
```

目标页面：

```text
https://pgy.xiaohongshu.com/solar/pre-trade/note/kol
```

### 5.2 已跑通的真实页面链路

聊天记录中已用调试版 Chrome 跑通过：

1. 用户登录蒲公英。
2. 打开“找博主 / 博主广场”。
3. 列表页识别达人行。
4. 点击达人头像区域进入详情。
5. 切换详情页 `数据概览`。
6. 切换 `笔记数据`，选择 `合作笔记`。
7. 切换 `粉丝分析`，滚动到 `粉丝画像`。
8. 生成详情验证 JSON 和粉丝画像截图。

当时确认的批量采集入口：

```text
.blogger-list_list .d-new-table tbody tr
```

进入达人详情的稳定点击点：

```text
.profile
```

验证中成功打开过达人详情：

```text
/blogger-detail/662b042b00000000070041f6
```

### 5.3 采集字段与截图规则

详情页采集确认要覆盖：

- 数据概览
- 笔记数据中的合作笔记
- 粉丝分析中的核心指标
- 粉丝画像区域截图

粉丝画像截图范围最终改为：

```text
粉丝画像标题 + 性别分布 + 年龄分布
```

不包含地域分布。

截图选择器策略曾优化为：

```text
.contentPic.fansPic
```

并与“粉丝画像”标题合并裁剪。

合作笔记判断规则也曾加固：

- 如果详情页已经切到 `合作笔记` 筛选，并且按钮处于 active 状态，则当前笔记列表都按合作笔记记录。
- 不再只依赖每条笔记卡片是否出现“含推广流量”，避免漏采。

主 ID 规则：

- 主 ID 使用“小红书号”。
- 蒲公英详情 ID 保留为辅助更新入口。

### 5.4 浏览器调试要求

一开始尝试接管已有 Chrome，发现远程调试端口 `9222` 没有稳定监听。

建议启动方式：

```powershell
Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" -ArgumentList "--remote-debugging-port=9222","--profile-directory=Default"
```

后续为了避免默认用户目录复用导致调试端口不生效，曾启动独立调试版 Chrome。独立 profile 不继承原登录态，所以用户需要在新窗口登录蒲公英。

如果要验证插件按钮 / 内容脚本 / 截图入库，则需要用同一个登录 profile 重启 Chrome，并增加：

```text
--load-extension=<browser_extension 路径>
```

当前目录没有 `browser_extension` 源码，所以这部分目前不能复验。

## 6. 前端工作台与路由

### 6.1 当前可见项目

`ad-workbench` 是 React + Vite 项目。

脚本：

```json
{
  "dev": "vite",
  "build": "vite build",
  "preview": "vite preview"
}
```

管理员侧栏当前包括：

- 系统概览
- 账号管理
- 权限配置
- Agent 编排
- API 配置
- 系统配置
- 审计日志

API 配置已经是独立菜单项。

### 6.2 曾经的旧首页

聊天中大量功能落在旧首页：

```text
http://127.0.0.1:8797
```

对应旧入口文件曾是：

```text
screening-workbench.html
screening-workbench.js
```

但当前目录已不可见。若要继续使用旧首页，需要恢复这些文件和 `rpa_mcp_sync` 后端。

### 6.3 项目选择器

用户要求：

```text
右上角的项目选择放在大标题下面，且随着项目选择会自动切换内容
```

该需求出现在后续会话中，但没有看到最终完成记录。当前可见的 `ad-workbench` 也没有完整项目切换逻辑。

后续需要实现：

- 项目选择器放在页面大标题下方。
- 切换项目时刷新项目上下文。
- 飞书配置、筛选标准、达人池、任务日志都随项目切换。
- 当前只保留 `有道答疑笔5-6月合作` 一个项目时，选择器可以隐藏或显示单选状态。

## 7. PowerShell / Codex 环境

聊天中曾解决 PowerShell 默认编码问题，判断乱码多半是 PowerShell 5 默认编码读取 UTF-8 文件导致。

已安装并切换 PowerShell 7：

```text
PowerShell: 7.6.1
PSHOME: C:\Users\adsolo7\AppData\Local\Programs\PowerShell\7
当前进程: C:\Users\adsolo7\AppData\Local\Programs\PowerShell\7\pwsh.exe
pwsh 路径: C:\Users\adsolo7\AppData\Local\Programs\PowerShell\7\pwsh.exe
```

Kiro 默认终端曾设置为 PowerShell 7，路径：

```text
C:\Users\adsolo7\AppData\Roaming\Kiro\User\settings.json
```

备份：

```text
C:\Users\adsolo7\AppData\Roaming\Kiro\User\settings.json.bak-20260508-105223
```

这对读取中文文件、避免前端源码被误判乱码很重要。

## 8. 当前风险与恢复建议

### 8.1 最大风险

当前工作区曾执行过只保留有道项目的删除操作，随后尝试撤回。由于删除使用 PowerShell `Remove-Item`，大部分内容没有进入回收站。

已恢复内容：

- `有道答疑笔5-6月合作_测试项目`
- `ad-workbench`
- `插件参考1\靓号.crx`

未恢复内容：

- 后端服务源码
- 旧首页源码
- 浏览器插件源码
- 测试目录
- 配置目录
- runtime 验证文件

### 8.2 不建议做的事

- 不要把 `lark-cli`、权限命令、事件订阅等技术项显示给非技术用户。
- 不要把飞书配置和 API 配置放在同一个页面。
- 不要把 `App Secret`、API Key 明文回显。
- 不要把连接配置文件混入项目列表。
- 不要用占位 `tables.cli.yaml` 假装真实读写成功。

### 8.3 建议下一步

1. 先恢复或重建后端目录。

   最少需要重新提供：

   ```text
   rpa_mcp_sync
   config
   tests
   screening-workbench.html
   screening-workbench.js
   browser_extension
   ```

2. 重建飞书后端接口。

   必须覆盖：

   ```text
   GET/POST /api/projects/feishu/connection
   POST /api/projects/feishu/test
   GET /api/projects/feishu/tables
   GET /api/projects/feishu/fields
   POST /api/projects/feishu/records
   ```

3. 按“远端表目标”抽象支持 sheet 与 bitable。

   不要只支持多维表格，也不要要求用户理解两者差异。用户只填飞书链接，系统自动识别。

4. 重建 API 配置后端。

   必须覆盖：

   ```text
   GET  /api/llm/config
   POST /api/llm/config
   POST /api/llm/test
   ```

5. 接入 LLM 时，配置读取优先级建议为：

   ```text
   页面配置文件中的 inline key
   环境变量 api_key_env
   .env
   ```

   页面不要回显真实 key。

6. 恢复蒲公英采集浏览器能力。

   推荐路线：

   - 用户先登录蒲公英。
   - 系统接管已登录浏览器或引导打开调试版 Chrome。
   - 在博主广场列表页批量识别达人。
   - 点击 `.profile` 进入详情页。
   - 自动读取数据概览、合作笔记、粉丝画像。
   - 将结果写入本地达人池，再同步飞书。

## 9. 一句话结论

聊天记录中已经把关键产品口径定清楚了：这个系统应围绕“有道答疑笔5-6月合作”项目，提供非技术人员可用的飞书连接配置、独立 API 模型配置、蒲公英达人采集和按字段同步能力。当前前端 API 配置页仍可见，但飞书读写、旧首页、浏览器采集和后端接口源码已随目录删除丢失，需要先恢复源码或按本文档重建。
