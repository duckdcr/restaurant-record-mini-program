const config = require('../config/index.js');
const session = require('./session.js');

function uploadError(message, code, retryable) {
  const error = new Error(message || '图片上传失败');
  error.code = code || 'UPLOAD_FAILED';
  error.retryable = Boolean(retryable);
  return error;
}

function compressImage(filePath) {
  if (typeof wx.compressImage !== 'function') return Promise.resolve(filePath);
  return new Promise((resolve) => {
    wx.compressImage({
      src: filePath,
      quality: 82,
      success: (result) => resolve(result.tempFilePath || filePath),
      fail: () => resolve(filePath),
    });
  });
}

async function uploadImage(filePath) {
  const uploadPath = await compressImage(filePath);
  return new Promise((resolve, reject) => {
    const token = session.getToken();
    wx.uploadFile({
      url: `${String(config.apiBaseUrl).replace(/\/+$/, '')}/uploads`,
      filePath: uploadPath,
      name: 'file',
      header: token ? { Authorization: `Bearer ${token}` } : {},
      timeout: config.requestTimeout,
      success(response) {
        let body = {};
        try { body = JSON.parse(response.data || '{}'); } catch (_) { /* invalid body handled below */ }
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(body);
          return;
        }
        if (response.statusCode === 401) session.clearSession();
        reject(uploadError(body.message, body.code, body.retryable));
      },
      fail(cause) {
        reject(uploadError(cause.errMsg || '图片上传失败', 'NETWORK_ERROR', true));
      },
    });
  });
}

module.exports = { uploadImage };
