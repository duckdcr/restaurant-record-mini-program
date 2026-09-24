import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';

const require = createRequire(import.meta.url);


test('sample form never labels default values as AI values', () => {
  const { normalizeRecognition } = require('../utils/sample.js');
  const result = normalizeRecognition({
    fields: {
      dish_name: { value: '清炒时蔬', confidence: 0.61, source: 'menu_match', requires_confirmation: true },
      amount_g: { value: 125, confidence: 0, source: 'default', requires_confirmation: true },
      temperature_c: { value: 4, confidence: 0, source: 'default', requires_confirmation: true },
    },
  });

  assert.equal(result.amount.source, 'default');
  assert.equal(result.amount.requiresConfirmation, true);
  assert.equal(result.temperature.sourceLabel, '建议值');
});


test('dashboard view model uses server counts rather than fixture numbers', () => {
  const { dashboardViewModel } = require('../utils/sample.js');
  const result = dashboardViewModel({
    summary: { registered_count: 4, total_count: 9, warning_count: 1, expired_count: 2, missing_count: 5 },
    tasks: [],
    meals: [],
  });

  assert.deepEqual(result.stats.map((item) => item.value), ['4/9', '01', '02']);
  assert.match(result.summaryText, /还差 5 道/);
});


test('camera return does not request another launch overlay', () => {
  const { nextLaunchState } = require('../utils/sample.js');

  assert.equal(nextLaunchState({ firstLaunch: false, externalFlow: 'camera' }).showSplash, false);
  assert.equal(nextLaunchState({ firstLaunch: false, externalFlow: '' }).showSplash, true);
  assert.equal(nextLaunchState({ firstLaunch: true, externalFlow: '' }).showSplash, false);
});


test('api client maps server errors and clears an invalid session', async () => {
  const { createApiClient } = require('../services/api.js');
  let cleared = false;
  const wxApi = {
    request(options) {
      options.success({ statusCode: 401, data: { code: 'INVALID_SESSION', message: '登录状态已失效', retryable: false } });
    },
  };
  const api = createApiClient(wxApi, { apiBaseUrl: 'http://127.0.0.1:8000/api/v1' }, {
    getToken: () => 'bad-token',
    clearSession: () => { cleared = true; },
  });

  await assert.rejects(api.get('/auth/me'), (error) => error.code === 'INVALID_SESSION');
  assert.equal(cleared, true);
});


test('api client sends bearer token and returns successful data', async () => {
  const { createApiClient } = require('../services/api.js');
  const wxApi = {
    request(options) {
      assert.equal(options.header.Authorization, 'Bearer session-token');
      options.success({ statusCode: 200, data: { status: 'ok' } });
    },
  };
  const api = createApiClient(wxApi, { apiBaseUrl: 'http://127.0.0.1:8000/api/v1' }, {
    getToken: () => 'session-token', clearSession() {},
  });

  assert.deepEqual(await api.get('/health'), { status: 'ok' });
});
