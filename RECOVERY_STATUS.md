# 恢复落实状态

日期：2026-05-08

## 已恢复

- 重建 `rpa_mcp_sync` FastAPI 后端骨架。
- 重建旧首页 `screening-workbench.html/js/css`，默认入口为 `http://127.0.0.1:8797`。
- 恢复有道项目概览接口：`GET /api/overview`。
- 恢复飞书配置保存/读取：`GET/POST /api/projects/feishu/connection`。
- 恢复飞书连接测试：`POST /api/projects/feishu/test`。
- 新增飞书表/字段/记录接口：
  - `GET /api/projects/feishu/tables`
  - `GET /api/projects/feishu/fields`
  - `POST /api/projects/feishu/records`
- 飞书链接解析支持 Wiki、电子表格 Sheet、多维表格 Base。
- API 配置后端接口已恢复：
  - `GET /api/llm/config`
  - `POST /api/llm/config`
  - `POST /api/llm/test`
- `ad-workbench` 构建产物可通过后端访问，`/workbench/...` 会回退到 React SPA。

## 当前仍是最小恢复版

- 蒲公英真实浏览器采集自动化还没有重建。
- 原 `browser_extension` 源码没有找到，只恢复了后端和入口，不恢复插件功能。
- 飞书远端读取/写入接口已经封装，但没有真实 App Secret 时只能做链接解析，不能完成远端读写。
- 当前没有保留任何测试写入的真实飞书配置或 API Key。

## 启动

```powershell
.\run_server.ps1
```

访问：

```text
http://127.0.0.1:8797
```
