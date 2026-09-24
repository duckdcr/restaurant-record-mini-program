const api = require('../../services/api.js');
const { downloadReport } = require('../../services/download.js');
const timeUtil = require('../../utils/time.js');
const { parseMenuItems } = require('../../utils/sample.js');

Page({
  data: {
    adminTab: 'menu', menuDate: '', breakfastMenu: '', lunchMenu: '', dinnerMenu: '',
    breakfastCount: 0, lunchCount: 0, dinnerCount: 0,
    saveLabel: '保存今日菜单', saveDisabled: false, menuLoading: false,
    exportFrom: '', exportTo: '', exportLabel: '生成 Excel 报送表', exportDisabled: false,
    showSplash: false,
    policies: [
      { key: '留样量', desc: '每个品种不少于 125g；默认值必须人工确认。' },
      { key: '冷藏条件', desc: '当前设置为 0–8℃；异常温度进入待核验。' },
      { key: '保存时间', desc: '冷藏保存 48 小时以上；提前 4 小时提醒。' },
      { key: '审计记录', desc: '登记、修改、处置和导出均记录操作人与时间。' },
    ],
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) this.getTabBar().setData({ selected: 3 });
    const today = timeUtil.isoDate(new Date());
    const next = {
      menuDate: this.data.menuDate || today,
      exportTo: this.data.exportTo || today,
      showSplash: getApp().consumeSplash(),
    };
    if (!this.data.exportFrom) next.exportFrom = `${today.slice(0, 8)}01`;
    this.setData(next, () => this.loadMenu());
  },

  onSplashFinish() { this.setData({ showSplash: false }); },
  switchAdmin(e) { this.setData({ adminTab: e.currentTarget.dataset.admin }); },
  countDishes(text) { return parseMenuItems(text).length; },
  onMenuDate(e) { this.setData({ menuDate: e.detail.value }, () => this.loadMenu()); },
  onBreakfast(e) { this.setData({ breakfastMenu: e.detail.value, breakfastCount: this.countDishes(e.detail.value) }); },
  onLunch(e) { this.setData({ lunchMenu: e.detail.value, lunchCount: this.countDishes(e.detail.value) }); },
  onDinner(e) { this.setData({ dinnerMenu: e.detail.value, dinnerCount: this.countDishes(e.detail.value) }); },

  applyMenus(result) {
    const meals = result.meals || {};
    const text = (key) => meals[key] ? meals[key].items.map((item) => item.dish_name).join('、') : '';
    const breakfastMenu = text('breakfast');
    const lunchMenu = text('lunch');
    const dinnerMenu = text('dinner');
    this.setData({
      breakfastMenu, lunchMenu, dinnerMenu,
      breakfastCount: this.countDishes(breakfastMenu),
      lunchCount: this.countDishes(lunchMenu),
      dinnerCount: this.countDishes(dinnerMenu),
    });
  },

  async loadMenu() {
    this.setData({ menuLoading: true });
    try {
      await getApp().ensureAuthenticated();
      this.applyMenus(await api.get(`/menus/${this.data.menuDate}`));
    } catch (error) {
      this.selectComponent('#pageToast').show(error.message || '菜单加载失败');
    } finally {
      this.setData({ menuLoading: false });
    }
  },

  async copyYesterday() {
    try {
      const result = await api.post(`/menus/${this.data.menuDate}/copy-previous`, {});
      this.applyMenus(result);
      getApp().notifyDataChanged();
      this.selectComponent('#pageToast').show('已复制最近一日菜单，请核对');
    } catch (error) {
      this.selectComponent('#pageToast').show(error.message || '没有可复制的历史菜单');
    }
  },

  async saveMenu() {
    if (this.data.saveDisabled) return;
    const menus = {
      breakfast: parseMenuItems(this.data.breakfastMenu),
      lunch: parseMenuItems(this.data.lunchMenu),
      dinner: parseMenuItems(this.data.dinnerMenu),
    };
    if (Object.values(menus).some((items) => items.length === 0)) {
      this.selectComponent('#pageToast').show('早餐、午餐和晚餐都至少填写一道菜');
      return;
    }
    this.setData({ saveDisabled: true, saveLabel: '保存中…' });
    try {
      await Promise.all(Object.keys(menus).map((meal) => api.put(`/menus/${this.data.menuDate}/${meal}`, { items: menus[meal] })));
      getApp().notifyDataChanged();
      this.selectComponent('#pageToast').show('菜单已保存，漏记提醒已重新核对');
    } catch (error) {
      this.selectComponent('#pageToast').show(error.message || '菜单保存失败');
    } finally {
      this.setData({ saveDisabled: false, saveLabel: '保存今日菜单' });
    }
  },

  onExportFrom(e) { this.setData({ exportFrom: e.detail.value }); },
  onExportTo(e) { this.setData({ exportTo: e.detail.value }); },
  async exportReport() {
    const { exportFrom, exportTo } = this.data;
    if (!exportFrom || !exportTo || exportFrom > exportTo) {
      this.selectComponent('#pageToast').show('请检查导出日期范围');
      return;
    }
    if (this.data.exportDisabled) return;
    this.setData({ exportDisabled: true, exportLabel: '正在生成…' });
    try {
      const report = await api.post('/reports', { date_from: exportFrom, date_to: exportTo });
      await downloadReport(report.download_url);
      this.selectComponent('#pageToast').show('Excel 报送表已生成并打开');
    } catch (error) {
      this.selectComponent('#pageToast').show(error.message || '报表生成失败');
    } finally {
      this.setData({ exportDisabled: false, exportLabel: '生成 Excel 报送表' });
    }
  },
});
