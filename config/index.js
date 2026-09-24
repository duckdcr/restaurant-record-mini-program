const presets = {
  development: {
    apiBaseUrl: 'http://127.0.0.1:8000/api/v1',
    authMode: 'dev',
    devDisplayName: '王丽',
  },
  test: {
    apiBaseUrl: 'http://127.0.0.1:8000/api/v1',
    authMode: 'dev',
    devDisplayName: '测试用户',
  },
  production: {
    apiBaseUrl: '',
    authMode: 'wechat',
    devDisplayName: '微信用户',
  },
};

function normalizeUrl(value) {
  return String(value || '').trim().replace(/\/+$/, '');
}

const runtimeOverrides = typeof globalThis !== 'undefined' && globalThis.__A2_CONFIG__
  ? globalThis.__A2_CONFIG__
  : {};

const env = String(runtimeOverrides.appEnv || runtimeOverrides.APP_ENV || 'development').toLowerCase();
const baseDefaults = Object.prototype.hasOwnProperty.call(presets, env)
  ? presets[env]
  : presets.development;

const defaults = {
  appEnv: env,
  requestTimeout: 15000,
};

const merged = Object.assign({}, defaults, baseDefaults, runtimeOverrides);
merged.apiBaseUrl = normalizeUrl(merged.apiBaseUrl);

module.exports = Object.freeze(merged);
