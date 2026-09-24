// 页面级顶部 Toast（还原原型 .toast，2400ms 自动消失）
Component({
  data: { message: '', show: false },
  methods: {
    show(message) {
      clearTimeout(this._timer);
      this.setData({ message: message, show: true });
      this._timer = setTimeout(() => this.setData({ show: false }), 2400);
    }
  },
  lifetimes: { detached() { clearTimeout(this._timer); } }
});
