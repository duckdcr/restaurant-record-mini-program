// 时间工具：还原原型眼线行 WED · SEP 09 · 10:48 与动态问候语
const WEEK = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
const MONTH = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];

function pad(n) { return n < 10 ? '0' + n : '' + n; }

// "WED · SEP 09 · 10:48"
function eyeline(date) {
  const d = date || new Date();
  return WEEK[d.getDay()] + ' · ' + MONTH[d.getMonth()] + ' ' + pad(d.getDate()) + ' · ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
}

// 上午好 / 中午好 / 下午好 / 晚上好
function greeting(date) {
  const h = (date || new Date()).getHours();
  if (h < 11) return '上午好';
  if (h < 13) return '中午好';
  if (h < 18) return '下午好';
  return '晚上好';
}

// "2026-09-09"
function isoDate(date) {
  const d = date || new Date();
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
}

// "09月11日 10:48"
function cnStamp(date) {
  const d = date || new Date();
  return pad(d.getMonth() + 1) + '月' + pad(d.getDate()) + '日 ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
}

module.exports = { eyeline, greeting, isoDate, cnStamp, pad };
