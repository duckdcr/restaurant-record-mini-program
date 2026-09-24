Page({
  data: { leaving: false, loginError: '' },
  onLoad() {
    this.start();
  },
  start() {
    this.setData({ leaving: false, loginError: '' });
    const minimum = new Promise((resolve) => {
      this._t1 = setTimeout(resolve, 1800);
    });
    Promise.all([getApp().ensureAuthenticated(), minimum])
      .then(() => {
        this.setData({ leaving: true });
        this._t2 = setTimeout(() => wx.switchTab({ url: '/pages/tasks/tasks' }), 280);
      })
      .catch((error) => {
        this.setData({ loginError: error.message || '登录失败，请检查后端服务' });
      });
  },
  retry() {
    this.start();
  },
  onUnload() {
    clearTimeout(this._t1);
    clearTimeout(this._t2);
  }
});
