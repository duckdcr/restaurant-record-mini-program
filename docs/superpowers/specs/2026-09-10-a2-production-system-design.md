# A2 安心留样真实业务版设计规格

日期：2026-09-10  
状态：待用户复核  
基准：`A2台账AI_安心留样_静态交互原型.html` 与“优化 Astra 小程序方案”项目对话

## 1. 目标

把当前仅依赖内存和定时器的微信原生小程序升级为可本地端到端运行、可配置后上线的真实业务版本，同时严格保留现有 HTML 原型的页面结构、视觉语言与主要交互。

完成后必须具备：微信登录、真实图片上传、可配置视觉 AI 识别、字段级置信度与人工核验、台账持久化、菜单与漏记联动、48 小时预警、到期处置、完整审计证据和真实 Excel 导出。

## 2. 已确认边界

- 使用微信原生小程序，不使用 `web-view`、uni-app 或 Taro。
- 保留四个底部入口：待办、登记、台账、管理。
- 不设置管理员、留样员两套权限；所有已登录用户拥有相同业务功能。
- “复核人”“食安员”等字段是业务记录，不构成权限角色。
- 保留现有暖白、森林绿、鼠尾草配色、排版层级、圆角、卡片、筛选、Toast 和底部抽屉。
- 图2继续作为启动画面；每次小程序从后台进入前台时播放一次，内部切页、相机返回和授权返回不重复播放。
- 启动画面主体动画为 1.8 秒，随后在 280 毫秒内淡出。
- 不提交任何真实 AppSecret、AI API Key、数据库密码或对象存储密钥。
- 外部服务未配置时必须明确展示“未配置/不可用”，允许人工登记，不得用模拟结果伪装成功。

## 3. 方案选择

采用“微信原生小程序 + FastAPI + SQLAlchemy + SQLite/PostgreSQL + 可插拔对象存储 + OpenAI 兼容视觉适配器”。

开发环境默认 SQLite 和本地图片目录，确保无需外部账号即可验证真实持久化、导出和业务闭环；生产环境通过环境变量切换 PostgreSQL、OSS/S3 与真实微信、AI服务。开发模式仅绕过外部身份交换，不绕过业务数据库和审计逻辑。

未选择微信云开发，是因为现有项目对话已经确定保留 FastAPI 路线，而且 PostgreSQL、对象存储、模型适配与监管导出在独立后端中更容易测试和迁移。

## 4. 总体架构

```text
微信原生小程序
  ├─ 启动/登录状态
  ├─ 待办、登记、台账、管理
  ├─ API 客户端、文件上传、下载预览
  └─ 加载/空/错/重试与本地待同步草稿
              │ HTTPS + Bearer Session Token
FastAPI
  ├─ 微信身份交换与开发身份
  ├─ 菜单、漏记、台账、处置领域服务
  ├─ AI 识别适配器与字段校验
  ├─ 审计事件与 Excel 报表
  └─ 文件存储适配器
              │
SQLAlchemy ─ SQLite（开发）/ PostgreSQL（生产）
对象存储 ─ 本地目录（开发）/ S3 或 OSS（生产）
```

小程序页面只负责展示和采集，不自行计算权威状态。到期时间、漏记数量、状态迁移和审计内容均由服务端计算。

## 5. 代码边界

### 小程序

- `app.js`：只维护会话、前后台状态和全局刷新信号，不再保存业务演示数据。
- `config/index.js`：API 地址、开发模式和超时配置。
- `services/api.js`：统一请求、会话头、错误映射和一次重试。
- `services/auth.js`：`wx.login`、开发身份登录、会话持久化。
- `services/upload.js`：图片压缩、格式/大小检查、上传与失败恢复。
- `services/download.js`：报表下载及 `wx.openDocument`。
- `utils/sample.js`：纯函数表单归一化与页面映射，便于 Node 测试。
- 四个业务页面继续使用现有 WXML/WXSS，JS 改为读取 API 数据。

### 后端

- `backend/app/main.py`：FastAPI 组装与生命周期。
- `backend/app/config.py`：从环境变量加载配置并校验。
- `backend/app/database.py`：引擎、会话和初始化。
- `backend/app/models.py`：数据库模型。
- `backend/app/schemas.py`：请求/响应模型。
- `backend/app/auth.py`：微信 `code2session`、开发会话和 Bearer 鉴权。
- `backend/app/services/dashboard.py`：首页、漏记和到期聚合。
- `backend/app/services/samples.py`：登记、状态机、处置和审计。
- `backend/app/services/recognition.py`：视觉模型接口、Schema 校验和人工降级。
- `backend/app/services/reports.py`：安全 Excel 输出。
- `backend/app/storage.py`：本地/S3/OSS 文件存储接口。
- `backend/app/routes/`：按 auth、dashboard、menus、recognition、samples、reports 分组。

## 6. 数据模型

### `users`

- `id`、`openid`、`display_name`、`avatar_url`
- `created_at`、`last_login_at`
- `openid` 唯一；不包含权限角色字段。

### `menus`

- `id`、`menu_date`、`meal`、`version`、`created_by`、`created_at`
- 同一日期和餐次保存新版本；历史版本不覆盖。

### `menu_items`

- `id`、`menu_id`、`dish_name`、`normalized_name`、`sort_order`
- 用稳定 ID 关联登记和漏记判断，避免只依赖自由文本。

### `samples`

- `id`、`menu_item_id`、`dish_name`、`meal`
- `sampled_at`、`expires_at`、`keeper_id`
- `amount_g`、`temperature_c`、`note`
- `status`：`active | warning | expired | disposed | deleted`
- `created_at`、`updated_at`、`deleted_at`
- `deleted` 为软删除状态，默认查询不返回。

### `sample_images`

- `id`、`sample_id`、`storage_key`、`sha256`、`mime_type`、`size_bytes`
- 原始上传在登记完成后与台账关联，不能仅保留临时路径。

### `recognition_runs`

- `id`、`upload_id`、`provider`、`model`、`model_version`
- `raw_response_json`、`structured_result_json`、`status`、`error_code`
- `created_at`、`duration_ms`

### `recognition_fields`

- `run_id`、`field_name`、`source`
- `raw_value`、`final_value`、`confidence`、`was_modified`
- `source` 仅允许 `ai | default | manual | menu_match`。

### `disposals`

- `id`、`sample_id`、`method`、`note`
- `operator_id`、`reviewer_name`、`disposed_at`
- 同一留样只能存在一个有效处置记录。

### `audit_events`

- `id`、`entity_type`、`entity_id`、`action`
- `actor_id`、`before_json`、`after_json`、`created_at`
- 登记、修改、核验、菜单保存、处置、软删除和导出都写入。

## 7. API 合同

所有业务 API 使用 `/api/v1` 前缀；成功返回 JSON，错误统一返回 `{ "code", "message", "retryable", "details" }`。生产模式要求 Bearer 会话。

### 身份

- `POST /auth/wechat`：接收微信临时 `code`，服务端调用 `code2session`，创建/更新用户并返回会话。
- `POST /auth/dev`：仅 `APP_ENV=development` 可用，返回本地开发用户会话。
- `GET /auth/me`：返回当前用户。

### 首页和菜单

- `GET /dashboard?date=YYYY-MM-DD`：返回摘要、最多三条紧急任务和各餐完成度。
- `GET /menus/{date}`：返回某日全部餐次及版本。
- `PUT /menus/{date}/{meal}`：保存菜单新版本并返回重算后的漏记信息。
- `POST /menus/{date}/copy-previous`：复制最近一个可用菜单版本。

### 识别与登记

- `POST /uploads`：上传 JPEG/PNG/WebP，最大 10MB，返回 `upload_id`、哈希和预览地址。
- `POST /recognitions`：接收 `upload_id`、日期、餐次候选，调用真实模型并返回字段级来源和置信度。
- `POST /samples`：提交最终人工确认值、识别运行 ID 和上传 ID，事务内创建台账、图片关联、字段修订和审计事件。
- `GET /samples`：支持日期、餐次、状态、人员和关键词筛选。
- `GET /samples/{id}`：返回台账、证据时间线、AI结果和处置记录。
- `POST /samples/{id}/dispose`：校验状态后保存处置与复核信息。
- `DELETE /samples/{id}`：软删除，必须提供原因。

### 报表

- `POST /reports`：接收日期范围，生成真实 `.xlsx` 并写入导出审计事件。
- `GET /reports/{id}/download`：返回受会话保护的文件流。

## 8. 关键流程

### 启动与登录

1. `App.onShow` 判断本次是否为从后台恢复。
2. 非相机/授权临时返回时展示 1.8 秒启动层。
3. 读取本地会话并请求 `/auth/me`；失效则调用 `wx.login`。
4. 开发环境可使用 `/auth/dev`，界面明确标记“本地开发身份”。
5. 登录失败展示可恢复错误，不渲染伪造用户。

### AI 登记

1. 用户选择/拍摄照片，小程序先验证类型和大小并压缩。
2. 上传成功后调用识别；超过 1 秒持续显示进度状态。
3. AI 返回值逐字段显示来源、置信度和候选。
4. 低置信度或缺失字段必须人工确认；125g、4℃只能作为 `default` 建议。
5. 保存按钮只在必填字段与两个建议值确认后可用。
6. `/samples` 成功后清理图片和菜名，保留餐次和当前用户。
7. 保存结果立即出现在台账和首页统计中。

### 菜单与漏记

1. 菜单按日期、餐次保存版本。
2. dashboard 将当前菜单项目与未删除的台账按 `menu_item_id` 比对。
3. 未登记菜单项目形成漏记待办；新增登记后自动减少。
4. 菜单修改后重新计算，不修改已有历史台账。

### 到期与处置

1. `expires_at = sampled_at + 48h`，统一使用 `Asia/Shanghai`。
2. 剩余不超过 4 小时为 `warning`，已过期未处置为 `expired`。
3. dashboard 和 samples 查询均实时计算展示状态，不依赖写死倒计时。
4. 处置必须保存方式、说明、操作人、复核人和时间。
5. 处置事务成功后只移除对应待办，不影响其他危险记录。

### 导出

1. 服务端查询指定范围内台账、识别修订和处置数据。
2. 任何以 `= + - @` 开头的用户文本在 Excel 中添加单引号，防止公式注入。
3. 生成文件后返回下载 ID；小程序下载并调用 `wx.openDocument`。

## 9. UI 状态约束

现有页面结构和视觉 tokens 不变，只增加必要状态：

- 待办：骨架加载、无任务、模块失败重试、刷新中。
- 登记：图片校验失败、上传进度、识别失败、人工模式、保存失败重试。
- 台账：加载、空结果、请求失败、分页追加状态。
- 管理：菜单保存成功/失败、导出生成中/失败/可下载。
- 所有耗时操作立即禁用重复提交；请求结束后在 `finally` 恢复。
- 错误文案描述用户下一步，不显示密钥、上游响应体、SQL 或堆栈。

## 10. 安全与配置

环境变量由 `.env.example` 定义：

- `APP_ENV`
- `DATABASE_URL`
- `SESSION_SECRET`
- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`
- `AI_BASE_URL`
- `AI_API_KEY`
- `AI_MODEL`
- `AI_TIMEOUT_SECONDS`
- `STORAGE_BACKEND`
- `STORAGE_LOCAL_DIR`
- `S3_ENDPOINT_URL`
- `S3_BUCKET`
- `S3_ACCESS_KEY_ID`
- `S3_SECRET_ACCESS_KEY`
- `CORS_ORIGINS`
- `APP_TIMEZONE`

生产启动时若 `SESSION_SECRET`、微信配置或数据库配置缺失则拒绝启动。AI配置缺失不阻断人工登记，但识别端点返回明确的 `AI_NOT_CONFIGURED`。

上传端验证扩展名、MIME、文件签名和大小；文件名由服务端生成。CORS 不允许通配符。数据库写入使用事务。日志不记录密钥、完整微信 code 或原始照片内容。

## 11. 离线与失败恢复

- 上传前表单可保存到小程序本地草稿，包含本地图片临时路径和创建时间。
- 网络恢复后由用户确认重试；不在后台静默重复创建台账。
- 每次提交携带客户端幂等键，服务端对 `POST /samples` 去重。
- AI失败时允许使用人工模式继续填写；原失败运行仍写审计。
- 数据库或文件写入任一失败时整个登记事务回滚，孤立上传由定期清理策略删除。

## 12. 测试策略

实施严格遵循红—绿—重构：每个行为先写失败测试并确认失败原因，再写最小实现。

### 后端自动测试

- 微信开发/生产鉴权边界与会话失效。
- 菜单版本、漏记计算和同日餐次隔离。
- 48小时与4小时预警边界、上海时区和夏令时无关性。
- AI字段 Schema、置信度、来源与缺省降级。
- 登记事务、幂等、证据链、软删除和处置状态机。
- 处置只关闭对应待办，并保存说明与复核人。
- Excel内容、日期范围、公式注入和导出审计。
- 上传大小、类型、文件签名和哈希。

### 小程序自动测试

- API错误归一化、会话头和401重登录。
- 页面数据映射、筛选、登记表单门禁和草稿恢复。
- 启动层前后台判定，相机/授权返回不误播。
- 保存成功后刷新台账并清理正确字段。

### 静态和人工验证

- Node 语法、JSON、WXML、WXSS编译检查。
- FastAPI 测试套件和数据库迁移检查。
- 微信开发者工具内完成登录、拍照、识别、保存、筛选、处置、菜单和导出全链路。
- 375px等效手机宽度无横向溢出，主要点击目标不小于44px。

## 13. 验收标准

- 重启后菜单、台账、处置和审计数据仍存在。
- 保存一条留样后，台账新增该记录，首页登记数和漏记数同步变化。
- 日期、倒计时、状态均由真实当前时间计算，不含固定 `2026-09-09`。
- AI未配置或失败时不会显示“识别完成”，用户可以切换人工登记。
- AI配置有效时真实图片可得到字段级结果，并保存原始响应和人工最终值。
- 处置任意记录只改变该记录，完整保存说明、复核人和操作人。
- Excel按钮产生可打开的真实文件，且数据与查询范围一致。
- 微信生产登录只接受服务端交换得到的身份，不信任客户端提交的用户ID。
- 没有管理员/留样员权限分叉；所有登录用户使用相同页面和API权限。
- 启动画面素材与图2一致，并符合前后台播放规则。
- 所有自动测试通过，WXML/WXSS/JS静态检查通过。

## 14. 外部依赖与可验证范围

仓库内会完整实现所有接口、适配器和本地真实业务闭环。微信 `code2session` 与视觉AI的在线成功验证需要在开发者本机通过环境变量提供有效 AppSecret 和 AI API Key；没有这些凭据时，验收覆盖开发身份、真实数据库、真实文件上传、人工降级、Excel与所有错误路径，不声称外部服务已在线验证。

