const config = require('../config/index.js');
const session = require('./session.js');

function downloadReport(downloadUrl) {
  const token = session.getToken();
  const base = String(config.apiBaseUrl).replace(/\/+$/, '');
  const origin = base.replace(/\/api\/v1$/, '');
  const url = /^https?:\/\//.test(downloadUrl)
    ? downloadUrl
    : `${String(downloadUrl).startsWith('/api/v1/') ? origin : base}${downloadUrl}`;
  return new Promise((resolve, reject) => {
    wx.downloadFile({
      url,
      header: token ? { Authorization: `Bearer ${token}` } : {},
      success(result) {
        if (result.statusCode !== 200) {
          reject(new Error(`报表下载失败（${result.statusCode}）`));
          return;
        }
        wx.openDocument({
          filePath: result.tempFilePath,
          fileType: 'xlsx',
          showMenu: true,
          success: () => resolve(result.tempFilePath),
          fail: reject,
        });
      },
      fail: reject,
    });
  });
}

module.exports = { downloadReport };
