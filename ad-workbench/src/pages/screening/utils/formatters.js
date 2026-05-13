export function compactNumber(value) {
  const number = Number(value || 0);
  if (!number) return '待填';
  if (number >= 10000) return `${(number / 10000).toFixed(number >= 100000 ? 1 : 2).replace(/\.0$/, '')}万`;
  return String(number);
}

export function formatCurrency(value) {
  const number = Number(value || 0);
  return number ? `¥${number.toLocaleString('zh-CN')}` : '待填';
}

export function formatDateTime(value) {
  if (!value) return '未记录';
  const normalized = String(value).trim().replace('T', ' ').replace(/\.\d+Z?$/, '');
  return normalized || '未记录';
}

export function getDateKey(value) {
  if (!value) return '';
  const normalized = String(value).trim().replace('T', ' ');
  const match = normalized.match(/^(\d{4}-\d{2}-\d{2})/);
  if (match) return match[1];
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '';
  return parsed.toISOString().slice(0, 10);
}

export function formatDateLabel(value) {
  const key = getDateKey(value);
  if (!key) return '未记录';
  return key.replace(/-/g, '.');
}

export function formatCompleteness(value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) return '待补';
  const ratio = number > 1 ? number / 100 : number;
  return `${Math.round(ratio * 100)}%`;
}

export function formatPercentValue(value) {
  if (value === undefined || value === null || value === '') return '';
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  const percent = number <= 1 ? number * 100 : number;
  return `${Math.round(percent)}%`;
}

export function parseCountValue(value) {
  if (value === undefined || value === null || value === '') return 0;
  const text = String(value).replace(/,/g, '').trim();
  const number = parseFloat(text);
  if (!Number.isFinite(number)) return 0;
  return /万|w/i.test(text) ? number * 10000 : number;
}

export function formatNoteMetric(value) {
  if (value === undefined || value === null || value === '') return '-';
  const number = parseCountValue(value);
  if (!number) return String(value);
  return number >= 10000 ? `${(number / 10000).toFixed(number >= 100000 ? 1 : 2).replace(/\.0$/, '')}万` : number.toLocaleString('zh-CN');
}

export function normalizeNoteType(value = '') {
  const text = String(value || '');
  if (/视频/.test(text)) return '视频笔记';
  if (/图文|图片|笔记/.test(text)) return '图文笔记';
  return '图文笔记';
}
