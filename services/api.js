const config = require('../config/index.js');
const session = require('./session.js');

function trimSlash(value) {
  return String(value || '').replace(/\/+$/, '');
}

function requestError(response) {
  const body = response && response.data && typeof response.data === 'object' ? response.data : {};
  const error = new Error(body.message || `请求失败（${response.statusCode || 0}）`);
  error.code = body.code || 'REQUEST_FAILED';
  error.retryable = Boolean(body.retryable);
  error.details = body.details || null;
  error.statusCode = response.statusCode || 0;
  return error;
}

function networkError(cause) {
  const error = new Error((cause && cause.errMsg) || '网络连接失败，请稍后重试');
  error.code = 'NETWORK_ERROR';
  error.retryable = true;
  error.details = null;
  error.statusCode = 0;
  return error;
}

function createApiClient(wxApi, clientConfig, sessionProvider) {
  const baseUrl = trimSlash(clientConfig.apiBaseUrl);
  const timeout = clientConfig.requestTimeout || 15000;

  function request(method, path, data, options) {
    const requestOptions = options || {};
    return new Promise((resolve, reject) => {
      const token = sessionProvider.getToken();
      const header = Object.assign({ 'Content-Type': 'application/json' }, requestOptions.header || {});
      if (token) header.Authorization = `Bearer ${token}`;
      wxApi.request({
        url: `${baseUrl}${path}`,
        method,
        data,
        header,
        timeout,
        success(response) {
          if (response.statusCode >= 200 && response.statusCode < 300) {
            resolve(response.data);
            return;
          }
          if (response.statusCode === 401) sessionProvider.clearSession();
          reject(requestError(response));
        },
        fail(cause) {
          reject(networkError(cause));
        },
      });
    });
  }

  return {
    request,
    get: (path, options) => request('GET', path, undefined, options),
    post: (path, data, options) => request('POST', path, data, options),
    put: (path, data, options) => request('PUT', path, data, options),
    delete: (path, data, options) => request('DELETE', path, data, options),
  };
}

let runtimeClient = null;
function getRuntimeClient() {
  if (!runtimeClient) {
    if (typeof wx === 'undefined') throw new Error('微信运行环境尚未初始化');
    runtimeClient = createApiClient(wx, config, session);
  }
  return runtimeClient;
}

module.exports = {
  createApiClient,
  request: (...args) => getRuntimeClient().request(...args),
  get: (...args) => getRuntimeClient().get(...args),
  post: (...args) => getRuntimeClient().post(...args),
  put: (...args) => getRuntimeClient().put(...args),
  delete: (...args) => getRuntimeClient().delete(...args),
};
