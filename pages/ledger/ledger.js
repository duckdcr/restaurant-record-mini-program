const api = require('../../services/api.js');
const { recordViewModel, evidenceViewModel } = require('../../utils/sample.js');

const DISPOSAL_VALUES = ['discard', 'retain_for_test', 'quarantine'];

Page({
  data: {
    eyeline: '0 RECORDS · LIVE STATUS', keyword: '',
    filters: [
      { key: 'all', label: '全部' }, { key: 'active', label: '在柜' },
      { key: 'warning', label: '即将到期' }, { key: 'expired', label: '等待处置' },
      { key: 'disposed', label: '已处置' },
    ],
    activeFilter: 'all', records: [], visibleCount: 0, isEmpty: false,
    loading: true, loadError: '', showSplash: false,
    detailVisible: false, detailTitle: '', detailSummary: '', events: [],
    disposalVisible: false, disposalDish: '', disposalRecord: '', disposalMethodIndex: 0,
    disposalMethods: ['按规定废弃', '送检留存', '异常封存'], disposalNote: '', reviewerIndex: 0,
    reviewers: ['张海涛 · 食安员', '李娟 · 食安员'], disposalSaving: false,
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) this.getTabBar().setData({ selected: 2 });
    const app = getApp();
    let filter = this.data.activeFilter;
    if (app.globalData.ledgerPendingFilter) {
      filter = app.globalData.ledgerPendingFilter;
      app.globalData.ledgerPendingFilter = '';
    }
    this.setData({ activeFilter: filter, showSplash: app.consumeSplash() });
    this.loadRecords();
  },

  onUnload() { clearTimeout(this._searchTimer); },
  onSplashFinish() { this.setData({ showSplash: false }); },

  onSearchInput(e) {
    this.setData({ keyword: e.detail.value });
    clearTimeout(this._searchTimer);
    this._searchTimer = setTimeout(() => this.loadRecords(), 280);
  },
  onFilterTap(e) {
    this.setData({ activeFilter: e.currentTarget.dataset.key }, () => this.loadRecords());
  },

  async loadRecords() {
    this.setData({ loading: true, loadError: '' });
    try {
      await getApp().ensureAuthenticated();
      const params = [];
      if (this.data.activeFilter !== 'all') params.push(`status=${encodeURIComponent(this.data.activeFilter)}`);
      if (this.data.keyword.trim()) params.push(`keyword=${encodeURIComponent(this.data.keyword.trim())}`);
      const result = await api.get(`/samples${params.length ? `?${params.join('&')}` : ''}`);
      const records = result.items.map((item) => Object.assign(recordViewModel(item), { visible: true }));
      this.setData({
        records, visibleCount: records.length, isEmpty: records.length === 0,
        eyeline: `${result.total} RECORDS · LIVE STATUS`, loading: false,
      });
    } catch (error) {
      this.setData({ loading: false, loadError: error.message || '台账加载失败', records: [], visibleCount: 0, isEmpty: true });
    }
  },

  async openDetail(e) {
    const id = Number(e.currentTarget.dataset.record);
    const record = this.data.records.find((item) => item.id === id);
    this.setData({
      detailVisible: true,
      detailTitle: `${record ? record.name : ''} · 留样证据`,
      detailSummary: record ? `${record.summary}，记录状态：${record.statusText}。` : '正在读取记录详情…',
      events: [],
    });
    try {
      const detail = await api.get(`/samples/${id}`);
      this.setData({ events: evidenceViewModel(detail) });
    } catch (error) {
      this.setData({ events: [{ title: '证据读取失败', desc: error.message || '请稍后重试' }] });
    }
  },
  closeDetail() { this.setData({ detailVisible: false }); },
  openDisposal(e) {
    const id = Number(e.currentTarget.dataset.record);
    const record = this.data.records.find((item) => item.id === id);
    this.setData({ disposalVisible: true, disposalRecord: id, disposalDish: record ? record.name : '' });
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
        method: DISPOSAL_VALUES[this.data.disposalMethodIndex], note: this.data.disposalNote,
        reviewer_name: this.data.reviewers[this.data.reviewerIndex],
      });
      getApp().notifyDataChanged();
      this.setData({ disposalVisible: false, disposalNote: '' });
      this.selectComponent('#pageToast').show('处置完成，操作人与复核人已留痕');
      await this.loadRecords();
    } catch (error) {
      this.selectComponent('#pageToast').show(error.message || '处置失败');
    } finally {
      this.setData({ disposalSaving: false });
    }
  },
});
