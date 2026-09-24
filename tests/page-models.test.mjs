import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';

const require = createRequire(import.meta.url);

test('dashboard meals and disposal tasks match existing page fields', () => {
  const { dashboardViewModel } = require('../utils/sample.js');
  const result = dashboardViewModel({
    summary: { registered_count: 1, total_count: 3, warning_count: 0, expired_count: 1, missing_count: 2 },
    meals: [{ key: 'lunch', name: '午餐', registered: 1, total: 3, percent: 33, missing: ['米饭'] }],
    tasks: [{ id: 'sample-9', type: 'danger', title: '米饭已超过 48 小时', sub: '午餐', time: '+1.0h', action: 'dispose', record_id: 9 }],
  });

  assert.deepEqual(result.meals[0], { name: '午餐', stat: '1 / 3 已登记', pct: 33, incomplete: true });
  assert.equal(result.tasks[0].record, 9);
});

test('ledger record view model presents persisted disposal data', () => {
  const { recordViewModel } = require('../utils/sample.js');
  const result = recordViewModel({
    id: 7, dish_name: '茶叶蛋', meal_label: '早餐', sampled_at: '2026-09-08T08:42:00',
    expires_at: '2026-09-10T08:42:00', keeper: { display_name: '王丽' }, amount_g: 125,
    status: 'disposed', disposal: { method: 'discard', reviewer_name: '张海涛', disposed_at: '2026-09-10T09:00:00' },
  });

  assert.equal(result.statusText, '已处置');
  assert.equal(result.hasDispose, false);
  assert.match(result.meta.map((item) => item.value).join(' '), /张海涛/);
});

test('manual fallback keeps required confirmations and no recognition run', () => {
  const { manualRecognition, buildSamplePayload } = require('../utils/sample.js');
  const recognition = manualRecognition();
  const payload = buildSamplePayload({
    dish: '清炒时蔬', meal: 'lunch', sampledAt: '2026-09-10T10:48:00', uploadId: 3,
    recognition, confirmAmount: true, confirmTemp: true,
  });

  assert.equal(payload.recognition_run_id, null);
  assert.equal(payload.fields.amount_g.source, 'default');
  assert.deepEqual(payload.confirmed_fields, ['amount_g', 'temperature_c']);
});

test('menu parser trims separators and rejects empty segments', () => {
  const { parseMenuItems } = require('../utils/sample.js');
  assert.deepEqual(parseMenuItems('米饭、 清炒时蔬，\n番茄蛋汤'), ['米饭', '清炒时蔬', '番茄蛋汤']);
});

test('evidence timeline is built from real audit and image hashes', () => {
  const { evidenceViewModel } = require('../utils/sample.js');
  const result = evidenceViewModel({
    audit_events: [{ action: 'created', created_at: '2026-09-10T10:48:00', actor_id: 1 }],
    images: [{ sha256: 'abcdef1234567890', size_bytes: 2048 }],
  });
  assert.equal(result.length, 2);
  assert.match(result[1].desc, /abcdef123456/);
});
