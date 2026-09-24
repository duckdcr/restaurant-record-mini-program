const SOURCE_LABELS = {
  ai: 'AI识别',
  menu_match: '菜单匹配',
  default: '建议值',
  manual: '人工填写',
};

function normalizedField(field, fallback) {
  const value = field && field.value !== undefined && field.value !== null ? field.value : fallback;
  const source = field && field.source ? field.source : 'manual';
  return {
    value,
    confidence: field && Number.isFinite(field.confidence) ? field.confidence : 0,
    source,
    sourceLabel: SOURCE_LABELS[source] || '人工确认',
    requiresConfirmation: Boolean(field && field.requires_confirmation),
  };
}

function normalizeRecognition(payload) {
  const fields = (payload && payload.fields) || {};
  return {
    dishName: normalizedField(fields.dish_name, ''),
    amount: normalizedField(fields.amount_g, 125),
    temperature: normalizedField(fields.temperature_c, 4),
    notes: normalizedField(fields.notes, ''),
    runId: payload && (payload.run_id || payload.id) ? (payload.run_id || payload.id) : '',
  };
}

function padCount(value) {
  return String(Number(value) || 0).padStart(2, '0');
}

function dashboardViewModel(payload) {
  const summary = (payload && payload.summary) || {};
  const registered = Number(summary.registered_count) || 0;
  const total = Number(summary.total_count) || 0;
  const warning = Number(summary.warning_count) || 0;
  const expired = Number(summary.expired_count) || 0;
  const missing = Number(summary.missing_count) || 0;
  return {
    stats: [
      { value: `${registered}/${total}`, label: '今日已登记' },
      { value: padCount(warning), label: '即将到期' },
      { value: padCount(expired), label: '等待处置' },
    ],
    summaryText: missing
      ? `今日已完成 ${registered} 道，还差 ${missing} 道；${expired} 份等待处置`
      : `今日 ${registered} 道已全部登记；${expired} 份等待处置`,
    tasks: ((payload && payload.tasks) || []).map((task) => Object.assign({}, task, {
      record: task.record_id || '',
    })),
    meals: ((payload && payload.meals) || []).map((meal) => ({
      name: meal.name,
      stat: meal.total === 0
        ? '暂无菜单'
        : `${meal.registered} / ${meal.total} ${meal.registered === meal.total ? '完成' : '已登记'}`,
      pct: meal.percent || 0,
      incomplete: meal.registered < meal.total,
    })),
    raw: payload || {},
  };
}

function dateTimeParts(value) {
  const text = String(value || '');
  return {
    date: text.slice(0, 10),
    time: text.slice(11, 16),
    short: text ? `${text.slice(5, 7)}月${text.slice(8, 10)}日 ${text.slice(11, 16)}` : '',
  };
}

function recordViewModel(record) {
  const statusLabels = {
    active: ['留样在柜', 'ok'],
    warning: ['即将到期', 'warn'],
    expired: ['等待处置', 'bad'],
    disposed: ['已处置', 'done'],
  };
  const status = statusLabels[record.status] || [record.status || '未知', 'done'];
  const sampled = dateTimeParts(record.sampled_at);
  const expires = dateTimeParts(record.expires_at);
  let meta = [
    { label: '留样人', value: (record.keeper && record.keeper.display_name) || '—' },
    { label: '留样量', value: `${Number(record.amount_g) || 0}g` },
    { label: '到期', value: expires.short || '—' },
  ];
  if (record.status === 'disposed' && record.disposal) {
    const methods = { discard: '废弃', retain_for_test: '送检留存', quarantine: '异常封存' };
    meta = [
      { label: '处置方式', value: methods[record.disposal.method] || record.disposal.method },
      { label: '复核人', value: record.disposal.reviewer_name },
      { label: '处置时间', value: dateTimeParts(record.disposal.disposed_at).short },
    ];
  }
  return {
    id: record.id,
    name: record.dish_name,
    meal: record.meal_label || record.meal,
    time: sampled.short,
    status: record.status,
    statusText: status[0],
    statusClass: status[1],
    search: `${record.dish_name} ${(record.keeper && record.keeper.display_name) || ''} ${record.meal_label || ''}`,
    meta,
    hasDispose: record.status === 'expired' || record.status === 'warning',
    summary: `${record.meal_label || record.meal} · ${sampled.short}`,
    raw: record,
  };
}

function manualRecognition() {
  return normalizeRecognition({
    fields: {
      dish_name: { value: '', confidence: 0, source: 'manual', requires_confirmation: true },
      amount_g: { value: 125, confidence: 0, source: 'default', requires_confirmation: true },
      temperature_c: { value: 4, confidence: 0, source: 'default', requires_confirmation: true },
    },
  });
}

function evidenceField(field) {
  return {
    raw_value: field && field.value !== undefined ? field.value : null,
    source: (field && field.source) || 'manual',
    confidence: field && Number.isFinite(field.confidence) ? field.confidence : null,
  };
}

function buildSamplePayload(input) {
  const recognition = input.recognition || manualRecognition();
  const confirmed = [];
  if (input.confirmAmount) confirmed.push('amount_g');
  if (input.confirmTemp) confirmed.push('temperature_c');
  return {
    menu_item_id: input.menuItemId || null,
    dish_name: String(input.dish || '').trim(),
    meal: input.meal,
    sampled_at: input.sampledAt,
    amount_g: Number(recognition.amount.value),
    temperature_c: Number(recognition.temperature.value),
    note: input.note || '',
    upload_id: input.uploadId,
    recognition_run_id: recognition.runId ? Number(recognition.runId) : null,
    fields: {
      dish_name: evidenceField(recognition.dishName),
      meal: { raw_value: input.meal, source: 'manual', confidence: null },
      sampled_at: { raw_value: input.sampledAt, source: 'manual', confidence: null },
      amount_g: evidenceField(recognition.amount),
      temperature_c: evidenceField(recognition.temperature),
    },
    confirmed_fields: confirmed,
  };
}

function parseMenuItems(text) {
  return String(text || '').split(/[、,，;；\n]/).map((item) => item.trim()).filter(Boolean);
}

function evidenceViewModel(detail) {
  const actionTitles = { created: '台账已保存', disposed: '到期处置已留痕', deleted: '记录已软删除' };
  const events = ((detail && detail.audit_events) || []).map((event) => ({
    title: actionTitles[event.action] || `操作：${event.action}`,
    desc: `${String(event.created_at || '').replace('T', ' ').slice(0, 16)} · 操作人 #${event.actor_id}`,
  }));
  ((detail && detail.images) || []).forEach((item) => {
    events.push({
      title: '标签照片已归档',
      desc: `SHA-256 ${String(item.sha256 || '').slice(0, 12)} · ${Math.ceil((item.size_bytes || 0) / 1024)}KB`,
    });
  });
  return events;
}

function nextLaunchState(input) {
  const state = input || {};
  return {
    showSplash: !state.firstLaunch && !state.externalFlow,
    firstLaunch: false,
    externalFlow: '',
  };
}

function localDate(date) {
  const value = date || new Date();
  const pad = (number) => String(number).padStart(2, '0');
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}

function idempotencyKey(prefix) {
  return `${prefix || 'request'}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

module.exports = {
  SOURCE_LABELS,
  normalizeRecognition,
  dashboardViewModel,
  recordViewModel,
  manualRecognition,
  buildSamplePayload,
  parseMenuItems,
  evidenceViewModel,
  nextLaunchState,
  localDate,
  idempotencyKey,
};
