# 安心留样 · 微信原生小程序（真实后端版）

本项目由 `A2台账AI_安心留样_静态交互原型.html` 演进为可运行业务版本：前端使用微信原生小程序，后端使用 FastAPI 落地数据库、登录、上传与 AI 接口。

## 当前能力（已落地）

- 菜单版本管理与看板：菜单 `PUT/GET`、缺失项统计、风险任务。
- 图片上传：后端签名校验（PNG/JPEG/WebP）后保存到本地或 S3。
- 微信登录/开发登录：`/api/v1/auth/wechat` 与 `/api/v1/auth/dev`（开发环境）。
- AI 识别适配：支持外部兼容模型接口，未配置时返回 `AI_NOT_CONFIGURED`，前端支持人工补齐。
- 留样登记、处置、软删除与审计：单张图片不可重复登记；支持幂等提交。
- 报表导出：Excel 生成与下载，带权限校验。

## 目录结构

```
.
├── app.js / app.json / app.wxss                 全局配置与状态
├── backend/
│   ├── run.py                                  启动后端入口
│   ├── app/
│   │   ├── seed.py                             一键初始化示例数据
│   │   ├── storage.py                           存储适配器（local / s3）
│   │   ├── models.py / routes / services ...
│   │   └── ...
│   ├── tests/                                  后端自动化测试
│   │   ├── test_end_to_end.py                  端到端链路验证
│   │   └── ...
│   └── requirements.txt
├── components/
│   ├── nav-bar
│   ├── toast
│   └── drawer
├── pages/
│   ├── splash
│   ├── tasks
│   ├── scan
│   ├── ledger
│   └── admin
├── services/
│   ├── api.js
│   ├── auth.js
│   ├── upload.js
│   └── download.js
├── start-backend.ps1                            后端启动脚本
└── README.md
```

## 环境与启动

### 1. 配置环境变量

1. 复制 `.env.example` 到 `.env`（可选）。
2. 按需填写：
   - `APP_ENV=development|test|production`
   - `APP_HOST=127.0.0.1`（生产建议改为 `0.0.0.0`）
   - `APP_PORT=8000`
   - `DATABASE_URL`（生产使用 Supabase Postgres 的 `postgresql+psycopg://...` 连接串）
   - `SESSION_SECRET`
   - 微信登录：`WECHAT_APP_ID` / `WECHAT_APP_SECRET`
   - AI：`AI_BASE_URL` / `AI_API_KEY` / `AI_MODEL`
   - 存储：`STORAGE_BACKEND=local`（默认）或 `s3`；生产建议使用 Supabase Storage S3

> 上线时：`APP_ENV=production`。后端会在生产环境下强制要求 `WECHAT_APP_ID`、`WECHAT_APP_SECRET` 与足够长度的 `SESSION_SECRET`。

### 1.1 小程序运行时配置（生产/开发快速切换）

前端支持通过 `globalThis.__A2_CONFIG__` 切环境，`appEnv` 会影响 `apiBaseUrl` 与登录模式：

```js
globalThis.__A2_CONFIG__ = {
  appEnv: 'production',
  apiBaseUrl: 'https://your-domain.com/api/v1',
  authMode: 'wechat',
  requestTimeout: 15000,
};
```

开发联调建议：

```js
globalThis.__A2_CONFIG__ = {
  appEnv: 'development',
  apiBaseUrl: 'http://127.0.0.1:8000/api/v1',
  authMode: 'dev',
  devDisplayName: '王丽',
};
```

### 2. 安装后端依赖

```powershell
pip install -r backend/requirements.txt
```

### 3. 一键启动后端

```powershell
# 不带参数：使用默认 host/port（127.0.0.1:8000）
./start-backend.ps1

# 开发模式热重载 + 启动前写入种子数据
./start-backend.ps1 -Reload -Seed

# 生产启动（默认不启用热重载）
./start-backend.ps1 -Production
```

### 4. 或直接运行后端脚本

```powershell
python backend/run.py --host 127.0.0.1 --port 8000 --reload --seed
```

### 5. 小程序导入

1. 打开微信开发者工具 → 导入项目，选择本仓库根目录。
2. AppID 选用你的微信测试号（支持真机调试）。
3. 后端服务勾选「不使用云服务」。
4. 开发者工具中把请求域名配置为 `http://127.0.0.1:8000`（用于本地调试）。

> 开发环境默认提供 `/api/v1/auth/dev`，便于本地联调；生产环境应使用 `/api/v1/auth/wechat`。

## 导入说明

打开**微信开发者工具**后，先在项目配置中打开：

- 请求超时和本地调试能力（如工具提示）
- 允许 `http://127.0.0.1:8000` 作为请求域名

## 业务差异说明

- 不再是仅内存演示；后端采用数据库持久化（SQLite 默认，生产可切换 Supabase PostgreSQL）。
- 识别环节支持 AI 配置后自动识别；未配置时返回可回退到手工登记。
- 扫码/相册照片会走后端上传接口，并支持下载报表文件。
- 认证与审计通过服务端真实落地，支持多次热启动数据持续保留。

## 注意

- 当前版本仍保留原型页面结构与导航样式，目标是“尽量少改体验、先保证数据链路真实可用”。
- 如遇到报表下载或 AI 接口异常，可通过 `/health` 与后端日志确认服务状态。
- 当前联调后端为 `https://a2-backend-temp.vercel.app`，前端已在 [app.js](/C:/餐饮记录小程序/app.js) 中绑定 `wx0dc97fb0b4143502`。
- Vercel 项目已预置生产环境 `WECHAT_APP_ID` 和随机 `SESSION_SECRET`；微信 `AppSecret`、AI 配置和生产数据库仍需补齐后再切换 `APP_ENV=production`。
- Vercel 上的 SQLite `/tmp` 与本地文件存储只适合联调；正式发布前必须改为 Supabase PostgreSQL 和对象存储。

## Supabase 生产接入

当前后端仍由 FastAPI 负责认证和业务权限，小程序不直接访问 Supabase。生产部署到 Vercel 时，在 Vercel 项目环境变量中配置：

```env
APP_ENV=production
DATABASE_URL=postgresql+psycopg://postgres.<project-ref>:<password>@<pooler-host>:6543/postgres?sslmode=require
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=https://<project-ref>.storage.supabase.co/storage/v1/s3
S3_BUCKET=sample-images
S3_ACCESS_KEY_ID=<storage-access-key>
S3_SECRET_ACCESS_KEY=<storage-secret-key>
S3_REGION=<project-region-from-supabase>
```

在 Supabase Storage 创建私有 bucket（例如 `sample-images`）并开启 S3 连接。图片和 Excel 报表都会通过同一存储适配器保存；本地开发仍可保持 `STORAGE_BACKEND=local`。

配置完成后重新部署，并访问 `https://a2-backend-temp.vercel.app/health` 验证数据库连接，再用微信开发者工具测试上传、登记和报表下载。

## 上线前清单（阻断项）

1. 配置正式 AppID（使用你微信小程序实名主体一致的 AppID）。
2. 准备 HTTPS 后端域名，并在微信小程序后台配置 request、uploadFile、downloadFile 域名白名单。
3. 确认 `APP_ENV=production`，`config/index.js` 生产环境 `authMode` 为 `wechat`。
4. 准备并核验 `WECHAT_APP_ID`、`WECHAT_APP_SECRET`、`SESSION_SECRET`。
5. 提交微信审核时补齐隐私保护指引、用户服务信息、客服电话和运营主体信息。
6. 真机测试通过登录、拍照/上传、下载报表、AI 回退流程。

## Vercel 绑定域名（你现在可以直接按这个清单操作）

当前项目：`a2-backend-temp`，临时 HTTPS：`https://a2-backend-temp.vercel.app`。

1. 准备一个你已归属的域名，例如 `api.example.com`。
2. 在本机登录 Vercel（一次性操作）：

```powershell
npx vercel login
```

3. 指定项目并部署到生产（已有部署可跳过）：

```powershell
npx vercel --prod
```

4. 将域名加到当前账号：

```powershell
npx vercel domains add api.example.com
```

5. 绑定项目主机名到自定义域名：

```powershell
npx vercel alias set <你的Vercel部署域名>.vercel.app api.example.com
```

6. 把 `api.example.com/api/v1` 写回 [app.js](/C:/餐饮记录小程序/app.js) 的 `apiBaseUrl`（`production` 分支）。
7. 在微信开发者工具重新编译测试（登录、上传、下载必须全部走 HTTPS）。
