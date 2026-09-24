const api = require('../../services/api.js');
const timeUtil = require('../../utils/time.js');
const { dashboardViewModel, localDate } = require('../../utils/sample.js');

const DISPOSAL_VALUES = ['discard', 'retain_for_test', 'quarantine'];

Page({
  data: {
    eyeline: '', greet: '', person: '用户', summaryText: '正在读取今日留样进度…',
    stats: [{ value: '0/0', label: '今日已登记' }, { value: '00', label: '即将到期' }, { value: '00', label: '等待处置' }],
    tasks: [], meals: [], loading: true, loadError: '', showSplash: false,
    disposalVisible: false, disposalDish: '', disposalRecord: '', disposalMethodIndex: 0,
    disposalMethods: ['按规定废弃', '送检留存', '异常封存'], disposalNote: '', reviewerIndex: 0,
    reviewers: ['张海涛 · 食安员', '李娟 · 食安员'], disposalSaving: false,
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) this.getTabBar().setData({ selected: 0 });
    const app = getApp();
    this.setData({
      eyeline: timeUtil.eyeline(), greet: timeUtil.greeting(),
      person: app.globalData.user ? app.globalData.user.display_name : '用户',
      showSplash: app.consumeSplash(),
    });
    this.loadDashboard();
  },

  onSplashFinish() { this.setData({ showSplash: false }); },

  async loadDashboard() {
    this.setData({ loading: true, loadError: '' });
    try {
      const app = getApp();
      const current = await app.ensureAuthenticated();
      const payload = await api.get(`/dashboard?date=${localDate()}`);
      const view = dashboardViewModel(payload);
      this.setData(Object.assign({}, view, {
        loading: false,
        person: current.user.display_name,
      }));
    } catch (error) {
      this.setData({ loading: false, loadError: error.message || '今日数据加载失败' });
    }
  },

  openDisposal(e) {
    const recordId = Number(e.currentTarget.dataset.record);
    const task = this.data.tasks.find((item) => item.record === recordId);
    this.setData({ disposalVisible: true, disposalRecord: recordId, disposalDish: task ? task.title.replace(/已超过 48 小时$/, '') : '该留样' });
  },
  closeDisposal() { if (!this.data.disposalSaving) this.setData({ disposalVisible: false }); },
  onMethodChange(e) { this.setData({ disposalMethodIndex: Number(e.detail.value) }); },
  onReviewerChange(e) { this.setData({ reviewerIndex: Number(e.detail.value) }); },
  onNoteInput(e) { this.setData({ disposalNote: e.detail.value }); },

  async confirmDisposal() {
    if (this.data.disposalSaving) return;
    this.setData({ disposalSaving: true });
    try {
      await api.post(`/samples/${this.data.disposalRecord}/dispose`, {
        method: DISPOSAL_VALUES[this.data.disposalMethodIndex],
        note: this.data.disposalNote,
        reviewer_name: this.data.reviewers[this.data.reviewerIndex],
      });
      getApp().notifyDataChanged();
      this.setData({ disposalVisible: false, disposalNote: '' });
      this.selectComponent('#pageToast').show('处置完成，操作人与复核人已留痕');
      await this.loadDashboard();
    } catch (error) {
      this.selectComponent('#pageToast').show(error.message || '处置失败');
    } finally {
      this.setData({ disposalSaving: false });
    }
  },

  onTaskTap(e) {
    const action = e.currentTarget.dataset.action;
    if (action === 'dispose') this.openDisposal(e);
    else if (action === 'ledger-warning') {
      getApp().globalData.ledgerPendingFilter = 'warning';
      wx.switchTab({ url: '/pages/ledger/ledger' });
    } else if (action === 'scan') wx.switchTab({ url: '/pages/scan/scan' });
  },
  goScan() { wx.switchTab({ url: '/pages/scan/scan' }); },
  goAdmin() { wx.switchTab({ url: '/pages/admin/admin' }); },
});
