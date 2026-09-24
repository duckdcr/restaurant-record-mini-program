// 通用底部抽屉（还原原型 .overlay + .drawer：遮罩、底部滑入、标题、圆形关闭按钮）
Component({
  options: { multipleSlots: false },
  properties: {
    visible: { type: Boolean, value: false },
    title: { type: String, value: '' }
  },
  data: { rendered: false },
  observers: {
    visible(v) {
      if (v) this.setData({ rendered: true });
    }
  },
  methods: {
    onClose() {
      this.triggerEvent('close');
    },
    onMask() {
      this.triggerEvent('close');
    },
    noop() {}
  }
});
