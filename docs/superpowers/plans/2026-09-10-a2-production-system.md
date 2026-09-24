# A2 安心留样真实业务版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有微信原生静态演示升级为可本地端到端运行、可配置生产外部服务的真实留样业务系统。

**Architecture:** 现有 WXML/WXSS 作为固定视图层，新增小程序会话与 API 服务层；FastAPI 负责身份、菜单、识别、登记、状态、审计与报表，SQLAlchemy 同时支持 SQLite 和 PostgreSQL。图片与AI均使用适配器，开发环境使用本地文件和开发身份，生产环境切换微信 `code2session`、对象存储与真实视觉模型。

**Tech Stack:** 微信原生小程序、JavaScript、Node test、Python 3.12、FastAPI、Pydantic、SQLAlchemy、SQLite/PostgreSQL、httpx、openpyxl、pytest。

**Spec:** `docs/superpowers/specs/2026-09-10-a2-production-system-design.md`

## Global Constraints

- 页面结构、视觉 tokens、四个底部入口和图2启动素材保持不变。
- 不建立管理员/留样员权限分叉，复核人只作为业务字段。
- 没有外部密钥时不得模拟微信或AI成功；人工登记必须可用。
- 生产密钥仅从环境变量读取，仓库只包含 `.env.example`。
- 所有权威业务状态由服务端计算，客户端不写死日期、数量和倒计时。
- 每项生产行为先写失败测试并确认失败原因，再写最小实现。
- 当前目录不是 Git 仓库；每个任务的“提交”步骤替换为记录测试结果，不初始化 Git。

---

### Task 1: Backend foundation, sessions, and persistent schema

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/app/models.py`
- Create: `backend/app/schemas.py`
- Create: `backend/app/auth.py`
- Create: `backend/app/main.py`
- Create: `backend/app/routes/__init__.py`
- Create: `backend/app/routes/auth.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_auth.py`
- Create: `backend/tests/test_database.py`
- Create: `backend/requirements.txt`
- Create: `.env.example`

**Interfaces:**
- Produces: `Settings`, `get_settings()`, SQLAlchemy `Base`, `get_db()`, `create_access_token(user_id)`, `get_current_user()`, `/api/v1/auth/dev`, `/api/v1/auth/wechat`, `/api/v1/auth/me`.

- [ ] **Step 1: Write failing authentication and persistence tests**

```python
def test_dev_login_persists_one_user(client, db_session):
    response = client.post('/api/v1/auth/dev', json={'display_name': '王丽'})
    assert response.status_code == 200
    assert response.json()['user']['display_name'] == '王丽'
    assert db_session.query(User).count() == 1

def test_production_rejects_dev_login(production_client):
    assert production_client.post('/api/v1/auth/dev', json={'display_name': '王丽'}).status_code == 404
```

- [ ] **Step 2: Run tests and verify the expected import failure**

Run: `python -m pytest backend/tests/test_auth.py backend/tests/test_database.py -q`  
Expected: collection fails because `backend.app` does not exist.

- [ ] **Step 3: Implement configuration, models, database sessions, signed sessions, and auth routes**

```python
class Settings(BaseModel):
    app_env: Literal['development', 'test', 'production'] = 'development'
    database_url: str = 'sqlite:///./backend/data/a2.db'
    session_secret: str = 'development-only-change-me'
    app_timezone: str = 'Asia/Shanghai'

def create_access_token(user_id: int, settings: Settings) -> str:
    payload = f'{user_id}:{int(time.time())}'
    signature = hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f'{payload}:{signature}'.encode()).decode()
```

Create all schema tables from the approved design, register exception handling, and expose `/health` plus authenticated identity routes.

- [ ] **Step 4: Run Task 1 tests and verify pass**

Run: `python -m pytest backend/tests/test_auth.py backend/tests/test_database.py -q`  
Expected: all Task 1 tests pass.

- [ ] **Step 5: Record Task 1 verification**

Run: `python -m pytest backend/tests -q`  
Expected: all existing backend tests pass; record the count in the implementation log.

### Task 2: Versioned menus and live dashboard

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/menus.py`
- Create: `backend/app/services/dashboard.py`
- Create: `backend/app/routes/menus.py`
- Create: `backend/app/routes/dashboard.py`
- Create: `backend/tests/test_menus.py`
- Create: `backend/tests/test_dashboard.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: authenticated user, SQLAlchemy models and `get_db()`.
- Produces: `save_menu()`, `get_menu_for_date()`, `copy_previous_menu()`, `build_dashboard()`, menu and dashboard endpoints.

- [ ] **Step 1: Write failing menu version and live-status tests**

```python
def test_saving_menu_creates_new_version(client, auth_headers):
    body = {'items': ['土豆烧牛肉', '清炒时蔬', '米饭']}
    first = client.put('/api/v1/menus/2026-09-10/lunch', json=body, headers=auth_headers)
    second = client.put('/api/v1/menus/2026-09-10/lunch', json=body, headers=auth_headers)
    assert first.json()['version'] == 1
    assert second.json()['version'] == 2

def test_dashboard_derives_missing_and_expired_items(client, auth_headers, seeded_business_data):
    data = client.get('/api/v1/dashboard?date=2026-09-10', headers=auth_headers).json()
    assert data['summary']['missing_count'] == 2
    assert data['summary']['expired_count'] == 1
    assert len(data['tasks']) <= 3
```

- [ ] **Step 2: Run Task 2 tests and verify endpoint-not-found failures**

Run: `python -m pytest backend/tests/test_menus.py backend/tests/test_dashboard.py -q`  
Expected: 404 responses because menu/dashboard routes are not registered.

- [ ] **Step 3: Implement versioned menus and server-derived dashboard**

```python
def effective_status(sampled_at: datetime, disposed: bool, now: datetime) -> str:
    if disposed:
        return 'disposed'
    remaining = sampled_at + timedelta(hours=48) - now
    if remaining.total_seconds() <= 0:
        return 'expired'
    if remaining <= timedelta(hours=4):
        return 'warning'
    return 'active'
```

Normalize meal values, create immutable menu versions, compare latest menu items with samples, sort tasks by expired → warning → missing, and return dynamic meal progress.

- [ ] **Step 4: Run Task 2 tests and full backend suite**

Run: `python -m pytest backend/tests/test_menus.py backend/tests/test_dashboard.py -q`  
Expected: Task 2 tests pass.

- [ ] **Step 5: Record Task 2 verification**

Run: `python -m pytest backend/tests -q`  
Expected: all backend tests pass.

### Task 3: Secure upload and real AI recognition adapter

**Files:**
- Create: `backend/app/storage.py`
- Create: `backend/app/services/recognition.py`
- Create: `backend/app/routes/uploads.py`
- Create: `backend/app/routes/recognitions.py`
- Create: `backend/tests/test_uploads.py`
- Create: `backend/tests/test_recognition.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces: `StorageBackend.save()`, `LocalStorage`, `RecognitionService.recognize()`, `/uploads`, `/recognitions`.

- [ ] **Step 1: Write failing upload-validation and AI-degradation tests**

```python
def test_upload_saves_hash_and_rejects_non_image(client, auth_headers, png_bytes):
    ok = client.post('/api/v1/uploads', files={'file': ('label.png', png_bytes, 'image/png')}, headers=auth_headers)
    assert ok.status_code == 201
    assert len(ok.json()['sha256']) == 64
    bad = client.post('/api/v1/uploads', files={'file': ('x.txt', b'hello', 'text/plain')}, headers=auth_headers)
    assert bad.status_code == 415

def test_recognition_reports_not_configured_without_fake_result(client, auth_headers, uploaded_image):
    response = client.post('/api/v1/recognitions', json={'upload_id': uploaded_image['id'], 'meal': 'lunch'}, headers=auth_headers)
    assert response.status_code == 503
    assert response.json()['code'] == 'AI_NOT_CONFIGURED'
```

- [ ] **Step 2: Run Task 3 tests and verify route failures**

Run: `python -m pytest backend/tests/test_uploads.py backend/tests/test_recognition.py -q`  
Expected: 404 responses for missing endpoints.

- [ ] **Step 3: Implement file signatures, local storage, OpenAI-compatible request, and strict result parsing**

```python
ALLOWED_SIGNATURES = {b'\x89PNG\r\n\x1a\n': 'image/png', b'\xff\xd8\xff': 'image/jpeg'}

class RecognitionField(BaseModel):
    value: str | float | None
    confidence: float = Field(ge=0, le=1)
    source: Literal['ai', 'default', 'manual', 'menu_match']
```

Use `httpx.AsyncClient` with configured timeout and bearer key, send the stored image and menu candidates, validate JSON, persist raw/structured runs, and return stable error codes.

- [ ] **Step 4: Run Task 3 tests including deterministic fake upstream responses**

Run: `python -m pytest backend/tests/test_uploads.py backend/tests/test_recognition.py -q`  
Expected: validation, unconfigured, malformed and successful adapter tests pass.

- [ ] **Step 5: Record Task 3 verification**

Run: `python -m pytest backend/tests -q`  
Expected: full backend suite passes.

### Task 4: Transactional samples, evidence, disposal, and soft deletion

**Files:**
- Create: `backend/app/services/samples.py`
- Create: `backend/app/routes/samples.py`
- Create: `backend/tests/test_samples.py`
- Create: `backend/tests/test_disposals.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: users, menus, uploads and recognition runs.
- Produces: `create_sample()`, `list_samples()`, `get_sample_evidence()`, `dispose_sample()`, `soft_delete_sample()` and sample endpoints.

- [ ] **Step 1: Write failing transaction, idempotency, and targeted-disposal tests**

```python
def test_sample_creation_is_idempotent_and_updates_dashboard(client, auth_headers, sample_payload):
    headers = {**auth_headers, 'Idempotency-Key': 'device-1-entry-1'}
    first = client.post('/api/v1/samples', json=sample_payload, headers=headers)
    second = client.post('/api/v1/samples', json=sample_payload, headers=headers)
    assert first.status_code == 201
    assert second.json()['id'] == first.json()['id']

def test_disposal_preserves_note_reviewer_and_other_expired_tasks(client, auth_headers, two_expired_samples):
    target, untouched = two_expired_samples
    response = client.post(f'/api/v1/samples/{target.id}/dispose', json={'method': 'discard', 'note': '外观无异常', 'reviewer_name': '张海涛'}, headers=auth_headers)
    assert response.json()['disposal']['reviewer_name'] == '张海涛'
    assert client.get(f'/api/v1/samples/{untouched.id}', headers=auth_headers).json()['status'] == 'expired'
```

- [ ] **Step 2: Run Task 4 tests and verify route failures**

Run: `python -m pytest backend/tests/test_samples.py backend/tests/test_disposals.py -q`  
Expected: 404 responses for missing sample routes.

- [ ] **Step 3: Implement transaction-safe sample and audit services**

```python
def dispose_sample(db: Session, sample: Sample, actor: User, payload: DisposalCreate, now: datetime):
    if effective_status(sample.sampled_at, bool(sample.disposal), now) not in {'warning', 'expired'}:
        raise DomainError('SAMPLE_NOT_DISPOSABLE', 409)
    disposal = Disposal(sample_id=sample.id, operator_id=actor.id,
                        reviewer_name=payload.reviewer_name, method=payload.method,
                        note=payload.note, disposed_at=now)
    db.add(disposal)
    append_audit(db, 'sample', sample.id, 'disposed', actor.id, None, payload.model_dump())
    return disposal
```

Require manual confirmation sources for amount and temperature, attach uploads/recognition fields, calculate `expires_at`, emit audit events, and implement soft deletion with a required reason.

- [ ] **Step 4: Run Task 4 tests and verify all state transitions**

Run: `python -m pytest backend/tests/test_samples.py backend/tests/test_disposals.py -q`  
Expected: all Task 4 tests pass.

- [ ] **Step 5: Record Task 4 verification**

Run: `python -m pytest backend/tests -q`  
Expected: full backend suite passes.

### Task 5: Safe real Excel reports

**Files:**
- Create: `backend/app/services/reports.py`
- Create: `backend/app/routes/reports.py`
- Create: `backend/tests/test_reports.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces: `sanitize_excel_text()`, `build_report_workbook()`, `/reports`, `/reports/{id}/download`.

- [ ] **Step 1: Write failing workbook and formula-injection tests**

```python
@pytest.mark.parametrize('value', ['=1+1', '+cmd', '-2+3', '@SUM(A1)'])
def test_excel_user_text_is_not_a_formula(value):
    assert sanitize_excel_text(value) == "'" + value

def test_report_contains_sample_disposal_and_audit(client, auth_headers, disposed_sample):
    response = client.post('/api/v1/reports', json={'date_from': '2026-09-01', 'date_to': '2026-09-30'}, headers=auth_headers)
    download = client.get(response.json()['download_url'], headers=auth_headers)
    workbook = load_workbook(BytesIO(download.content))
    assert workbook.active['A2'].value == disposed_sample.dish_name
```

- [ ] **Step 2: Run Task 5 tests and verify missing-module/route failures**

Run: `python -m pytest backend/tests/test_reports.py -q`  
Expected: import or 404 failure because reporting is not implemented.

- [ ] **Step 3: Implement report persistence, workbook generation, protected download, and export audit**

```python
def sanitize_excel_text(value: str) -> str:
    return "'" + value if value and value[0] in '=+-@' else value
```

Generate columns for dish, meal, sampled/expiry time, keeper, amount, temperature, status, image hash, AI model, modifications, disposal and audit ID.

- [ ] **Step 4: Run Task 5 and full backend tests**

Run: `python -m pytest backend/tests/test_reports.py -q`  
Expected: Task 5 tests pass and downloaded workbook opens through openpyxl.

- [ ] **Step 5: Record Task 5 verification**

Run: `python -m pytest backend/tests -q`  
Expected: full backend suite passes.

### Task 6: Mini-program service layer, login, and launch behavior

**Files:**
- Create: `config/index.js`
- Create: `services/api.js`
- Create: `services/auth.js`
- Create: `services/upload.js`
- Create: `services/download.js`
- Create: `utils/sample.js`
- Create: `tests/miniprogram-services.test.mjs`
- Modify: `app.js`
- Modify: `app.json`
- Modify: `pages/splash/splash.js`
- Modify: `pages/splash/splash.wxml`
- Modify: `pages/splash/splash.wxss`

**Interfaces:**
- Produces: `request()`, `login()`, `uploadImage()`, `downloadReport()`, `normalizeRecognition()`, app session and launch-overlay state.

- [ ] **Step 1: Write failing pure service and lifecycle tests**

```javascript
test('sample form never labels default values as AI values', () => {
  const result = normalizeRecognition({ fields: { amount_g: null, temperature_c: null } });
  assert.equal(result.amount.source, 'default');
  assert.equal(result.temperature.requiresConfirmation, true);
});

test('camera return does not request another launch overlay', () => {
  const state = nextLaunchState({ backgroundReason: 'camera', hasPlayed: true });
  assert.equal(state.showSplash, false);
});
```

- [ ] **Step 2: Run Node tests and verify missing-module failures**

Run: `node --test tests/miniprogram-services.test.mjs`  
Expected: module-not-found failures for new services/utilities.

- [ ] **Step 3: Implement configurable API wrapper, session login, uploads, downloads, and launch-overlay state**

```javascript
function request({ path, method = 'GET', data }) {
  return new Promise((resolve, reject) => wx.request({
    url: config.apiBaseUrl + path,
    method,
    data,
    header: sessionHeader(),
    success: (res) => res.statusCode < 400 ? resolve(res.data) : reject(normalizeApiError(res)),
    fail: () => reject({ code: 'NETWORK_ERROR', message: '网络连接失败', retryable: true })
  }));
}
```

Use storage only for session and explicit drafts, never for authoritative dashboard data. Replace splash as a reusable overlay controlled by app foreground state.

- [ ] **Step 4: Run Node tests and syntax checks**

Run: `node --test tests/miniprogram-services.test.mjs`  
Expected: Task 6 tests pass.

- [ ] **Step 5: Record Task 6 verification**

Run: `Get-ChildItem -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }`  
Expected: every JavaScript file exits successfully.

### Task 7: Wire the four existing pages to live services

**Files:**
- Modify: `pages/tasks/tasks.js`
- Modify: `pages/tasks/tasks.wxml`
- Modify: `pages/tasks/tasks.wxss`
- Modify: `pages/scan/scan.js`
- Modify: `pages/scan/scan.wxml`
- Modify: `pages/scan/scan.wxss`
- Modify: `pages/ledger/ledger.js`
- Modify: `pages/ledger/ledger.wxml`
- Modify: `pages/ledger/ledger.wxss`
- Modify: `pages/admin/admin.js`
- Modify: `pages/admin/admin.wxml`
- Modify: `pages/admin/admin.wxss`
- Modify: `components/nav-bar/index.js`
- Modify: `components/nav-bar/index.wxml`
- Create: `tests/page-models.test.mjs`

**Interfaces:**
- Consumes: Task 6 service modules and all backend API contracts.
- Produces: live dashboard, recognition/save flow, persisted ledger/evidence/disposal, versioned menus and real report download.

- [ ] **Step 1: Write failing page-model tests for dynamic values and error recovery**

```javascript
test('dashboard view model uses server counts rather than fixture numbers', () => {
  const vm = dashboardViewModel({ summary: { registered_count: 4, total_count: 9, warning_count: 1, expired_count: 2 } });
  assert.deepEqual(vm.stats.map(item => item.value), ['4/9', '01', '02']);
});

test('disposing one record leaves every other record unchanged', () => {
  const rows = applyDisposedRecord([{ id: 1, status: 'expired' }, { id: 2, status: 'expired' }], 2);
  assert.deepEqual(rows.map(row => row.status), ['expired', 'disposed']);
});
```

- [ ] **Step 2: Run page-model tests and verify missing exports**

Run: `node --test tests/page-models.test.mjs`  
Expected: imports or exports fail because page models are not implemented.

- [ ] **Step 3: Replace fixtures and timers with API-backed page states while preserving markup hierarchy**

```javascript
async loadDashboard() {
  this.setData({ loading: true, error: '' });
  try {
    const dashboard = await api.get('/dashboard?date=' + today());
    this.setData(dashboardViewModel(dashboard));
  } catch (error) {
    this.setData({ error: error.message });
  } finally {
    this.setData({ loading: false });
  }
}
```

Implement live saves, menu re-fetch, evidence detail, targeted disposal, upload/recognition/manual fallback, report download and explicit loading/empty/error/retry states.

- [ ] **Step 4: Run page-model tests and WXML/WXSS compilers**

Run: `node --test tests/page-models.test.mjs tests/miniprogram-services.test.mjs`  
Expected: all Node tests pass.

Run: WeChat `wcc.exe` for every `.wxml` and `wcsc.exe -lc` for every `.wxss`.  
Expected: every file compiles with exit code 0.

- [ ] **Step 5: Record Task 7 verification**

Run: all Node and static compiler checks again.  
Expected: no errors or warnings introduced by Task 7.

### Task 8: Run scripts, seed data, documentation, and end-to-end verification

**Files:**
- Create: `backend/run.py`
- Create: `backend/app/seed.py`
- Create: `backend/tests/test_end_to_end.py`
- Create: `start-backend.ps1`
- Modify: `README.md`
- Modify: `project.config.json`
- Modify: `project.private.config.json`

**Interfaces:**
- Produces: deterministic local startup, seeded development data, documented environment setup and full business-path test.

- [ ] **Step 1: Write failing end-to-end business test**

```python
def test_menu_to_sample_to_disposal_to_report(client, auth_headers, png_bytes):
    client.put('/api/v1/menus/2026-09-10/lunch', json={'items': ['米饭']}, headers=auth_headers)
    upload = client.post('/api/v1/uploads', files={'file': ('label.png', png_bytes, 'image/png')}, headers=auth_headers).json()
    sample = client.post('/api/v1/samples', json=manual_sample(upload['id']), headers={**auth_headers, 'Idempotency-Key': 'e2e-1'}).json()
    evidence = client.get(f"/api/v1/samples/{sample['id']}", headers=auth_headers).json()
    assert evidence['audit_events'][0]['action'] == 'created'
    client.post(f"/api/v1/samples/{sample['id']}/dispose", json={'method': 'discard', 'note': '到期废弃', 'reviewer_name': '张海涛'}, headers=auth_headers)
    report = client.post('/api/v1/reports', json={'date_from': '2026-09-10', 'date_to': '2026-09-12'}, headers=auth_headers)
    assert report.status_code == 201
```

- [ ] **Step 2: Run end-to-end test and verify missing startup/seed behavior**

Run: `python -m pytest backend/tests/test_end_to_end.py -q`  
Expected: failure until seed/startup and final endpoint contracts are connected.

- [ ] **Step 3: Implement deterministic seed, startup script, environment documentation, and config corrections**

```powershell
$env:APP_ENV = if ($env:APP_ENV) { $env:APP_ENV } else { 'development' }
python backend/run.py
```

Document local backend URL, development login, production variables, WeChat request domain, AI configuration, database migration path, image retention, and external verification limits. Correct README claims about `touristappid`, record counts and simulated backend.

- [ ] **Step 4: Run end-to-end and complete regression suites**

Run: `python -m pytest backend/tests -q`  
Expected: full backend suite passes.

Run: `node --test tests/*.test.mjs`  
Expected: full mini-program logic suite passes.

- [ ] **Step 5: Run final static and API smoke verification**

Run: JavaScript syntax, JSON parse, WXML/WXSS compilers, then start FastAPI and call `/health`, `/auth/dev`, `/dashboard`, `/samples`, `/reports`.  
Expected: all checks pass; produced Excel is readable by openpyxl and database data survives a server restart.

