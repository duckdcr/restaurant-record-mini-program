// 自定义导航栏：还原原型 .app-head（A2 品牌行 + 动态标题 + 头像身份提示）
Component({
  properties: {
    title: { type: String, value: 'A2 台账 AI' }
  },
  data: {
    statusBarHeight: 20,
    person: '用户',
    toast: '',
    toastShow: false
  },
  lifetimes: {
    attached() {
      const win = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync();
      const app = getApp();
      const user = app.globalData.user;
      this.setData({ statusBarHeight: win.statusBarHeight || 20, person: user ? user.display_name : '用户' });
    }
  },
  methods: {
    onAvatar() {
      const app = getApp();
      const user = app.globalData.user;
      this.showToast('当前用户：' + (user ? user.display_name : '登录中'));
    },
    showToast(msg) {
      clearTimeout(this._t);
      this.setData({ toast: msg, toastShow: true });
      this._t = setTimeout(() => this.setData({ toastShow: false }), 2400);
    }
  }
});
