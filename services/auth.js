const config = require('../config/index.js');
const api = require('./api.js');
const session = require('./session.js');

function wechatLogin() {
  return new Promise((resolve, reject) => {
    wx.login({
      success(result) {
        if (result.code) resolve(result.code);
        else reject(new Error('微信登录未返回有效凭证'));
      },
      fail: reject,
    });
  });
}

async function login() {
  let result;
  if (config.authMode === 'wechat') {
    result = await api.post('/auth/wechat', { code: await wechatLogin() });
  } else {
    result = await api.post('/auth/dev', { display_name: config.devDisplayName });
  }
  session.setSession(result);
  return result;
}

async function ensureAuthenticated() {
  const current = session.getSession();
  if (current && current.access_token) {
    try {
      const user = await api.get('/auth/me');
      const refreshed = Object.assign({}, current, { user });
      session.setSession(refreshed);
      return refreshed;
    } catch (error) {
      if (error.statusCode !== 401) throw error;
    }
  }
  return login();
}

module.exports = { login, ensureAuthenticated, clearSession: session.clearSession };
