Component({
  properties: {
    visible: { type: Boolean, value: false, observer: 'onVisibleChange' },
  },
  data: { leaving: false },
  lifetimes: {
    detached() {
      clearTimeout(this._holdTimer);
      clearTimeout(this._leaveTimer);
    },
  },
  methods: {
    onVisibleChange(visible) {
      clearTimeout(this._holdTimer);
      clearTimeout(this._leaveTimer);
      if (!visible) {
        this.setData({ leaving: false });
        return;
      }
      this.setData({ leaving: false });
      this._holdTimer = setTimeout(() => {
        this.setData({ leaving: true });
        this._leaveTimer = setTimeout(() => this.triggerEvent('finish'), 280);
      }, 1800);
    },
  },
});
