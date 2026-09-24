const appEnvConfigByAppId = Object.freeze({
  'wx0dc97fb0b4143502': {
    appEnv: 'production',
    apiBaseUrl: 'https://a2-backend-temp.vercel.app/api/v1',
    authMode: 'wechat',
    devDisplayName: '微信用户',
  },
  'wx-替换为你的测试APPID': {
    appEnv: 'development',
    apiBaseUrl: 'http://127.0.0.1:8000/api/v1',
    authMode: 'dev',
    devDisplayName: '王丽',
  },
});

if (typeof globalThis === 'object') {
  globalThis.__A2_CONFIG__ = Object.assign({
    appEnv: 'development',
    apiBaseUrl: 'http://127.0.0.1:8000/api/v1',
    authMode: 'dev',
    devDisplayName: '王丽',
    requestTimeout: 15000,
  }, (typeof globalThis.__A2_CONFIG__ === 'object' && globalThis.__A2_CONFIG__) || {});

  try {
    const accountInfo = wx.getAccountInfoSync && wx.getAccountInfoSync();
    const appId = accountInfo && accountInfo.miniProgram && accountInfo.miniProgram.appId;
    if (appId && appEnvConfigByAppId[appId]) {
      globalThis.__A2_CONFIG__ = Object.assign({}, globalThis.__A2_CONFIG__, appEnvConfigByAppId[appId]);
    }
  } catch (_error) {
    // 开发环境可能不具备 wx API，保持默认配置不阻塞启动
  }
}

const auth = require('./services/auth.js');
const { nextLaunchState } = require('./utils/sample.js');

App({
  globalData: {
    place: '博涵实验学校 · 第一食堂',
    session: null,
    user: null,
    firstLaunch: true,
    externalFlow: '',
    showSplash: false,
    dataVersion: 0,
    ledgerPendingFilter: '',
  },

  onLaunch() {
    this.ensureAuthenticated().catch(() => {});
  },

  onShow() {
    const next = nextLaunchState({
      firstLaunch: this.globalData.firstLaunch,
      externalFlow: this.globalData.externalFlow,
    });
    this.globalData.firstLaunch = next.firstLaunch;
    this.globalData.externalFlow = next.externalFlow;
    this.globalData.showSplash = next.showSplash;
  },

  ensureAuthenticated() {
    if (!this._authPromise) {
      this._authPromise = auth.ensureAuthenticated()
        .then((currentSession) => {
          this.globalData.session = currentSession;
          this.globalData.user = currentSession.user || null;
          return currentSession;
        })
        .finally(() => { this._authPromise = null; });
    }
    return this._authPromise;
  },

  markExternalFlow(kind) {
    this.globalData.externalFlow = kind || 'external';
  },

  consumeSplash() {
    const visible = this.globalData.showSplash;
    this.globalData.showSplash = false;
    return visible;
  },

  notifyDataChanged() {
    this.globalData.dataVersion += 1;
    return this.globalData.dataVersion;
  },
});
