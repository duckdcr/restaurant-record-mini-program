const api = require('../../services/api.js');
const { uploadImage } = require('../../services/upload.js');
const timeUtil = require('../../utils/time.js');
const {
  normalizeRecognition, manualRecognition, buildSamplePayload, idempotencyKey,
} = require('../../utils/sample.js');

const MEAL_KEYS = ['breakfast', 'lunch', 'dinner', 'snack'];

Page({
  data: {
    photoPath: '', hasImage: false, scanning: false, uploading: false,
    recognizeLabel: 'AI 识别', recognizeDisabled: false,
    aiState: '照片将安全上传，用于读取标签和菜单核对', resultShow: false,
    mealOptions: ['早餐', '午餐', '晚餐', '加餐'], mealIndex: 1,
    dish: '', sampleDate: '', sampleTime: '', keeperOptions: ['当前用户'], keeperIndex: 0,
    amount: 125, temperature: 4, amountSourceLabel: '建议值', temperatureSourceLabel: '建议值',
    amountNeedsConfirmation: true, tempNeedsConfirmation: true,
    confirmAmount: false, confirmTemp: false, canSave: false, saving: false,
    savedShow: false, savedTitle: '', savedExpire: '', showSplash: false,
    uploadId: 0, recognition: null,
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) this.getTabBar().setData({ selected: 1 });
    const now = new Date();
    const app = getApp();
    const userName = app.globalData.user ? app.globalData.user.display_name : '当前用户';
    this.setData({
      sampleDate: this.data.sampleDate || timeUtil.isoDate(now),
      sampleTime: this.data.sampleTime || `${timeUtil.pad(now.getHours())}:${timeUtil.pad(now.getMinutes())}`,
      keeperOptions: [userName],
      showSplash: app.consumeSplash(),
    });
  },

  onSplashFinish() { this.setData({ showSplash: false }); },

  choosePhoto() {
    const app = getApp();
    app.markExternalFlow('camera');
    wx.chooseMedia({
      count: 1, mediaType: ['image'], sourceType: ['album', 'camera'],
      success: (res) => {
        const file = res.tempFiles && res.tempFiles[0];
        if (!file) return;
        this.setData({
          photoPath: file.tempFilePath, hasImage: true, uploadId: 0, recognition: null,
          resultShow: false, savedShow: false, aiState: 'IMG · 已就绪，等待安全上传',
        });
      },
      complete: () => { app.globalData.externalFlow = ''; },
    });
  },

  async ensureUpload() {
    if (this.data.uploadId) return this.data.uploadId;
    this.setData({ uploading: true, aiState: '正在安全上传标签照片…' });
    const upload = await uploadImage(this.data.photoPath);
    this.setData({ uploadId: upload.id, uploading: false });
    return upload.id;
  },

  async startRecognition() {
    if (this.data.recognizeDisabled) return;
    if (!this.data.hasImage) {
      this.selectComponent('#pageToast').show('请先拍摄或选择标签照片');
      return;
    }
    this.setData({ recognizeDisabled: true, recognizeLabel: '正在识别…', scanning: true, resultShow: false, savedShow: false });
    try {
      await getApp().ensureAuthenticated();
      const uploadId = await this.ensureUpload();
      const result = await api.post('/recognitions', {
        upload_id: uploadId, meal: MEAL_KEYS[this.data.mealIndex], menu_date: this.data.sampleDate,
      });
      this.applyRecognition(normalizeRecognition(result), '识别完成，请核对标记字段');
    } catch (error) {
      if (error.code === 'AI_NOT_CONFIGURED' || error.code === 'AI_INVALID_RESPONSE') {
        this.applyRecognition(manualRecognition(), `${error.message}；125g/4℃为建议值`);
      } else {
        this.setData({ aiState: error.message || '识别失败，请重试' });
        this.selectComponent('#pageToast').show(error.message || '识别失败');
      }
    } finally {
      this.setData({ scanning: false, uploading: false, recognizeDisabled: false, recognizeLabel: '重新识别' });
    }
  },

  applyRecognition(recognition, message) {
    const dish = recognition.dishName.value || this.data.dish || '';
    this.setData({
      recognition, dish, amount: recognition.amount.value, temperature: recognition.temperature.value,
      amountSourceLabel: recognition.amount.sourceLabel, temperatureSourceLabel: recognition.temperature.sourceLabel,
      amountNeedsConfirmation: recognition.amount.requiresConfirmation,
      tempNeedsConfirmation: recognition.temperature.requiresConfirmation,
      confirmAmount: !recognition.amount.requiresConfirmation,
      confirmTemp: !recognition.temperature.requiresConfirmation,
      resultShow: true, aiState: message,
      canSave: !recognition.amount.requiresConfirmation && !recognition.temperature.requiresConfirmation && Boolean(dish.trim()),
    });
  },

  onMealChange(e) { this.setData({ mealIndex: Number(e.detail.value) }); },
  onDishInput(e) { this.setData({ dish: e.detail.value }, () => this.updateSaveState()); },
  onDateChange(e) { this.setData({ sampleDate: e.detail.value }); },
  onTimeChange(e) { this.setData({ sampleTime: e.detail.value }); },
  onKeeperChange(e) { this.setData({ keeperIndex: Number(e.detail.value) }); },
  onConfirmAmount(e) { this.setData({ confirmAmount: e.detail.value.length > 0 }, () => this.updateSaveState()); },
  onConfirmTemp(e) { this.setData({ confirmTemp: e.detail.value.length > 0 }, () => this.updateSaveState()); },
  updateSaveState() {
    const d = this.data;
    this.setData({
      canSave: Boolean((d.dish || '').trim())
        && (!d.amountNeedsConfirmation || d.confirmAmount)
        && (!d.tempNeedsConfirmation || d.confirmTemp),
    });
  },

  async findMenuItemId() {
    const result = await api.get(`/menus/${this.data.sampleDate}`);
    const menu = result.meals && result.meals[MEAL_KEYS[this.data.mealIndex]];
    const dish = (this.data.dish || '').trim();
    const item = menu && menu.items.find((candidate) => candidate.dish_name.trim() === dish);
    return item ? item.id : null;
  },

  async saveSample() {
    if (!this.data.canSave || this.data.saving) return;
    this.setData({ saving: true });
    try {
      const menuItemId = await this.findMenuItemId();
      const payload = buildSamplePayload({
        dish: this.data.dish, meal: MEAL_KEYS[this.data.mealIndex],
        sampledAt: `${this.data.sampleDate}T${this.data.sampleTime}:00`,
        uploadId: this.data.uploadId, recognition: this.data.recognition || manualRecognition(),
        confirmAmount: this.data.confirmAmount, confirmTemp: this.data.confirmTemp, menuItemId,
      });
      const saved = await api.post('/samples', payload, { header: { 'Idempotency-Key': idempotencyKey('sample') } });
      getApp().notifyDataChanged();
      this.setData({
        resultShow: false, savedShow: true, savedTitle: `${saved.dish_name}已登记`,
        savedExpire: timeUtil.cnStamp(new Date(saved.expires_at)),
      });
      this.selectComponent('#pageToast').show('台账已保存，并记录字段来源与人工核验');
    } catch (error) {
      this.selectComponent('#pageToast').show(error.message || '台账保存失败');
    } finally {
      this.setData({ saving: false });
    }
  },

  resetScan() {
    this.setData({
      resultShow: false, savedShow: false, confirmAmount: false, confirmTemp: false,
      canSave: false, dish: '', aiState: '已保留餐次与当前用户，请拍摄下一道菜',
      hasImage: false, photoPath: '', uploadId: 0, recognition: null,
    });
  },
  goLedger() { wx.switchTab({ url: '/pages/ledger/ledger' }); },
});
