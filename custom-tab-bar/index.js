Component({
  data: {
    selected: 0,
    list: [
      { pagePath: '/pages/tasks/tasks', code: '01', text: '待办' },
      { pagePath: '/pages/scan/scan', code: '02', text: '登记' },
      { pagePath: '/pages/ledger/ledger', code: '03', text: '台账' },
      { pagePath: '/pages/admin/admin', code: '04', text: '管理' }
    ]
  },
  methods: {
    switchTab(e) {
      const path = e.currentTarget.dataset.path;
      const index = e.currentTarget.dataset.index;
      wx.switchTab({ url: path });
      this.setData({ selected: index });
    }
  }
});
