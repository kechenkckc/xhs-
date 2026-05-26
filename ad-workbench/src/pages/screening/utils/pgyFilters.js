import {
  HARD_FILTER_OPTIONS,
  HARD_FILTER_CONDITIONS_BY_KIND,
  DEFAULT_HARD_FILTER_CONDITIONS,
  PGY_REQUIRED_FILTER_FIELDS,
  PGY_ADDITIONAL_FILTER_FIELDS,
  pgyFilterKey,
} from '../constants/screeningConstants';
import {
  PGY_FILTER_CATALOG_BY_FIELD,
  PGY_BLOGGER_CATEGORY_SUBCATEGORY_OPTIONS,
  PGY_MARKETING_GOAL_DEFAULT_METRIC,
  PGY_SINGLE_VALUE_CONTROLS,
} from '../constants/pgyConstants';

export { pgyFilterKey };

export function getHardFilterConditionKind(item = {}) {
  const text = `${item.field || ''} ${item.feishuField || ''} ${item.value || ''}`.toLowerCase();
  if (text.includes('链接') || text.includes('url')) return 'existence';
  if (text.includes('限流') || text.includes('违规') || text.includes('风险') || text.includes('剔除') || text.includes('规避')) return 'avoid';
  if (/[<>≤≥=]|%|¥|￥|\d/.test(String(item.value || ''))) return 'number';
  if (/(预算|报价|价格|成本|cpc|cpe|占比|比例|粉丝数|阅读|互动|roi|投产|金额|单价|效率)/i.test(text)) return 'number';
  return 'text';
}

export function hardFilterConditionsFor(item = {}) {
  const option = getHardFilterOptionMeta(item);
  if (option?.conditions?.length) return option.conditions;
  if (option?.valueControl === 'multi') return ['匹配', '包含', '不包含'];
  if (option?.valueControl === 'none') return ['必须存在'];
  const options = HARD_FILTER_CONDITIONS_BY_KIND[getHardFilterConditionKind(item)] || DEFAULT_HARD_FILTER_CONDITIONS;
  return options.includes(item.condition) || !item.condition ? options : [item.condition, ...options];
}

export function defaultHardFilterCondition(item = {}) {
  return hardFilterConditionsFor(item)[0] || '匹配';
}

export function getHardFilterOptionMeta(item = {}) {
  return HARD_FILTER_OPTIONS.find(option => option.field === item.field)
    || HARD_FILTER_OPTIONS.find(option => option.pgyField && option.pgyField === item.pgyField)
    || HARD_FILTER_OPTIONS.find(option => option.feishuField && option.feishuField === item.feishuField)
    || null;
}

export function splitHardFilterValue(value = '') {
  return String(value || '')
    .split(/[、,，;；/|｜]+/)
    .map(item => item.trim())
    .filter(Boolean);
}

export function normalizeHardFilterValue(option, value) {
  if (option?.valueControl === 'multi') {
    const selected = Array.isArray(value) ? value : splitHardFilterValue(value);
    return selected.join('、');
  }
  return String(value ?? '');
}

export function cloneHardFilterOption(option = {}) {
  return {
    field: option.field || '',
    condition: option.condition || defaultHardFilterCondition(option),
    value: option.value || '',
    required: option.required !== false,
    feishuField: option.feishuField || '',
    pgyField: option.pgyField || '',
    valueControl: option.valueControl || '',
    subField: option.subField || '',
  };
}

export function mergeDefaultHardFilters(filters = []) {
  const normalized = (filters || []).map(item => {
    const option = getHardFilterOptionMeta(item) || {};
    return {
      field: item.field || option.field || '',
      condition: item.condition || option.condition || defaultHardFilterCondition({ ...option, ...item }),
      value: item.value ?? option.value ?? '',
      required: item.required !== false,
      feishuField: item.feishuField || option.feishuField || '',
      pgyField: item.pgyField || option.pgyField || '',
      valueControl: item.valueControl || option.valueControl || '',
      subField: item.subField || option.subField || '',
    };
  });
  const seen = new Set(normalized.map(item => item.pgyField || item.field).filter(Boolean));
  const missing = HARD_FILTER_OPTIONS
    .filter(option => !seen.has(option.pgyField || option.field))
    .map(cloneHardFilterOption);
  return [...normalized, ...missing];
}

export function mergeOptionItems(current = [], options = [], keyFn = item => item.value || item.label) {
  const seen = new Set();
  return [...options, ...current].filter(item => {
    const key = keyFn(item);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function normalizePgyFilterItem(item = {}) {
  const field = item.field || '';
  const value = item.value || '';
  const base = { ...item, field, value, reason: item.reason || '' };
  if (field === '营销目标') {
    const metric = PGY_MARKETING_GOAL_DEFAULT_METRIC[value] || value;
    const parent = item.goal || item.parent_value || item.parentValue || (
      PGY_MARKETING_GOAL_DEFAULT_METRIC[value] ? value : ''
    );
    const fallbackParent = !parent && metric === '曝光表现' ? '曝光' : !parent && metric === '互动表现' ? '种草' : !parent && metric === '外溢进店表现' ? '转化' : parent;
    return {
      ...base,
      value: metric,
      goal: fallbackParent,
      parent_value: fallbackParent,
      control_type: 'marketing_goal_metric',
      priority: item.priority || 'low',
    };
  }
  if (field === '博主人设') {
    const map = {
      家庭身份: { field: '家庭身份', value: '妈妈', control_type: 'checkbox_popover' },
      职业身份: { field: '职业身份', value: '学生', control_type: 'checkbox_popover' },
      特色背景: { field: '特色背景', value: '留学背景', control_type: 'checkbox_popover' },
    };
    return { ...base, ...(map[value] || {}) };
  }
  if (field === '博主类目') {
    let mainValue = value;
    let subValue = item.sub_value || item.subValue || '';
    if (!PGY_BLOGGER_CATEGORY_SUBCATEGORY_OPTIONS[mainValue]) {
      const parent = Object.entries(PGY_BLOGGER_CATEGORY_SUBCATEGORY_OPTIONS)
        .find(([, options]) => options.includes(mainValue));
      if (parent) {
        mainValue = parent[0];
        subValue = value;
      }
    }
    const validSubcategories = PGY_BLOGGER_CATEGORY_SUBCATEGORY_OPTIONS[mainValue] || [];
    if (subValue && !validSubcategories.includes(subValue)) subValue = '';
    const { subValue: _subValue, sub_value: _sub_value, ...rest } = base;
    return {
      ...rest,
      value: mainValue,
      control_type: 'tag_select_with_hover_subcategory',
      ...(subValue ? { sub_value: subValue } : {}),
    };
  }
  if (field === '数据表现' && ['预估阅读/互动单价', 'CPC<2/CPE<20'].includes(value)) {
    return {
      ...base,
      field: '预估阅读单价',
      value: '图文笔记阅读单价≤2',
      control_type: 'subfield_preset_or_number_range',
      sub_field: '图文笔记阅读单价',
      pending_detail: '预估互动单价需作为独立条件补充',
    };
  }
  if (field === '报价') {
    return { ...base, field: '合作报价', value: '图文笔记：0.1万～2万', control_type: 'subfield_preset_or_number_range', sub_field: '图文笔记' };
  }
  if (field === '粉丝年龄' && ['35岁以上优先', '35岁以上≥40%'].includes(value)) {
    return { ...base, value: '35～44 占比高', control_type: 'dropdown' };
  }
  if (field === '地域' && value.includes('优先')) {
    return { ...base, control_type: 'three_level_cascade_checkbox_popover' };
  }
  return base;
}

const PGY_REGION_ALIAS_VALUES = {
  '北京/上海优先': ['北京', '上海'],
  '北京上海优先': ['北京', '上海'],
  北上广深: ['北京', '上海', '广州', '深圳'],
  一线: ['北京', '上海', '广州', '深圳'],
  一线城市: ['北京', '上海', '广州', '深圳'],
};

const REGION_PROVINCE_BY_CITY = {
  北京: '北京',
  上海: '上海',
  广州: '广东',
  深圳: '广东',
};

function standardRegionItem(item = {}, value) {
  const clean = String(value || item.city || item.province || item.value || '')
    .replace(/^中国[：:-]/, '')
    .trim();
  const province = item.province || REGION_PROVINCE_BY_CITY[clean] || clean;
  return {
    ...item,
    field: item.field,
    value: clean,
    country: item.country || '中国',
    province,
    ...(item.city ? { city: item.city } : {}),
    level: item.level || 'province',
    control_type: 'three_level_cascade_checkbox_popover',
    label: '',
  };
}

function expandPgyRegionFilterItem(item = {}) {
  if (!['地域', '粉丝地域'].includes(item.field)) return [normalizePgyFilterItem(item)];
  const value = String(item.value || '');
  if (item.country && value) return [standardRegionItem(normalizePgyFilterItem(item), value)];
  const aliasValues = PGY_REGION_ALIAS_VALUES[value] || PGY_REGION_ALIAS_VALUES[value.replace(/\s+/g, '')];
  if (aliasValues?.length) {
    return aliasValues.map(region => standardRegionItem(normalizePgyFilterItem(item), region));
  }
  if (/^中国[：:-]/.test(value)) {
    return [standardRegionItem(normalizePgyFilterItem(item), value)];
  }
  return [normalizePgyFilterItem(item)];
}

export function normalizePgyFilters(filters = []) {
  const expanded = [];
  filters.forEach(item => {
    expanded.push(...expandPgyRegionFilterItem(item));
    if (item.field === '数据表现' && ['预估阅读/互动单价', 'CPC<2/CPE<20'].includes(item.value)) {
      expanded.push({
        field: '预估互动单价',
        value: '图文笔记互动单价≤20',
        reason: item.reason || '',
        control_type: 'subfield_preset_or_number_range',
        sub_field: '图文笔记互动单价',
      });
    }
  });
  return mergeOptionItems([], expanded, pgyFilterKey);
}

export function markManualPgyFilters(filters = []) {
  return normalizePgyFilters(filters).map(item => ({
    ...item,
    manual: true,
    source: item.source || 'frontend',
  }));
}

export function hardFilterToPgyFilter(item = {}) {
  const option = getHardFilterOptionMeta(item) || {};
  const field = item.pgyField || option.pgyField || item.field || option.field || '';
  const value = item.value ?? option.value ?? '';
  if (!field || !value) return null;
  return normalizePgyFilterItem({
    field,
    value,
    reason: item.reason || option.reason || '',
    control_type: item.control_type || item.controlType || option.control_type || '',
    input_values: item.input_values || [],
    pending_detail: item.pending_detail || '',
    sub_field: item.sub_field || item.subField || option.subField || '',
    min_items: item.min_items || undefined,
  });
}

export function collectionHardFiltersToPgyFilters(filters = []) {
  return normalizePgyFilters((filters || []).map(hardFilterToPgyFilter).filter(Boolean));
}

export function syncCollectionHardFiltersFromPgyFilters(pgyFilters = [], currentHardFilters = []) {
  const hardFilterSyncKey = (item = {}) => `${item.pgyField || item.field || ''}|${item.subField || item.sub_field || ''}|${item.value || ''}`;
  const currentByField = new Map(
    (currentHardFilters || []).map(item => [hardFilterSyncKey(item), item])
  );
  return normalizePgyFilters(pgyFilters).map(item => {
    const option = getHardFilterOptionMeta({ field: item.field, pgyField: item.field }) || {};
    const current = currentByField.get(hardFilterSyncKey({ ...item, pgyField: item.field })) || {};
    return {
      field: option.field || current.field || item.field,
      condition: current.condition || option.condition || defaultHardFilterCondition({ ...option, field: item.field, value: item.value }),
      value: item.value || current.value || option.value || '',
      required: current.required !== undefined ? current.required !== false : option.required !== false,
      feishuField: current.feishuField || option.feishuField || '',
      pgyField: option.pgyField || current.pgyField || item.field,
      valueControl: current.valueControl || option.valueControl || '',
      subField: item.sub_field || current.subField || option.subField || '',
    };
  });
}

export function getSchemeRequiredFilters(scheme = {}) {
  const explicit = scheme.required_filters || scheme.base_filters;
  if (Array.isArray(explicit) && explicit.length) return explicit;
  return (scheme.filters || []).filter(item => PGY_REQUIRED_FILTER_FIELDS.has(item.field));
}

export function getSchemeAdditionalFilters(scheme = {}) {
  const explicit = scheme.additional_filters || scheme.extra_filters;
  if (Array.isArray(explicit)) return explicit;
  return (scheme.filters || []).filter(item => PGY_ADDITIONAL_FILTER_FIELDS.has(item.field));
}

export function getPgyFilterMeta(field) {
  return PGY_FILTER_CATALOG_BY_FIELD[field] || null;
}

export function getPgySelectedItems(filters = [], field) {
  return (filters || []).filter(item => item.field === field);
}

export function formatPgyFilterValue(field, value, subField) {
  if (field === '地域' || field === '粉丝地域') return value;
  if (!subField) return value;
  if (String(value).startsWith(`${subField}：`)) return value;
  return `${subField}：${value}`;
}

export function makePgyFilterItem(meta, value, subField) {
  const nextSubField = subField || meta.sub_fields?.[0] || '';
  if (meta.field === '营销目标') {
    const metric = PGY_MARKETING_GOAL_DEFAULT_METRIC[value] || value;
    const parent = subField || (PGY_MARKETING_GOAL_DEFAULT_METRIC[value] ? value : '');
    const fallbackParent = !parent && metric === '曝光表现' ? '曝光' : !parent && metric === '互动表现' ? '种草' : !parent && metric === '外溢进店表现' ? '转化' : parent;
    return {
      field: meta.field,
      value: metric,
      control_type: meta.control_type,
      ...(fallbackParent ? { goal: fallbackParent, parent_value: fallbackParent } : {}),
      priority: 'low',
    };
  }
  if (meta.field === '博主类目') {
    let mainValue = value;
    let subValue = subField || '';
    if (!PGY_BLOGGER_CATEGORY_SUBCATEGORY_OPTIONS[mainValue]) {
      const parent = Object.entries(PGY_BLOGGER_CATEGORY_SUBCATEGORY_OPTIONS)
        .find(([, options]) => options.includes(mainValue));
      if (parent) {
        mainValue = parent[0];
        subValue = value;
      }
    }
    const validSubcategories = PGY_BLOGGER_CATEGORY_SUBCATEGORY_OPTIONS[mainValue] || [];
    if (subValue && !validSubcategories.includes(subValue)) subValue = '';
    return {
      field: meta.field,
      value: mainValue,
      control_type: meta.control_type || 'tag_select_with_hover_subcategory',
      ...(subValue ? { sub_value: subValue } : {}),
    };
  }
  return {
    field: meta.field,
    value: formatPgyFilterValue(meta.field, value, nextSubField),
    control_type: meta.control_type,
    ...(nextSubField ? { sub_field: nextSubField } : {}),
  };
}

export function makePgyFilterItemsFromValues(meta, values = [], subField = '') {
  if (!meta) return [];
  return (values || [])
    .filter(value => value && value !== '不限')
    .map(value => makePgyFilterItem(meta, value, subField));
}

export function replacePgyFieldFilters(filters = [], meta, nextItems = []) {
  if (meta.field === '营销目标') {
    const parents = new Set((nextItems || []).map(item => item.goal || item.parent_value || item.parentValue || '').filter(Boolean));
    return [
      ...(filters || []).filter(item => item.field !== meta.field || !parents.has(item.goal || item.parent_value || item.parentValue || '')),
      ...(nextItems || []),
    ];
  }
  const subFields = new Set((nextItems || []).map(item => item.sub_field || '').filter(Boolean));
  if (subFields.size) {
    return [
      ...(filters || []).filter(item => item.field !== meta.field || !subFields.has(item.sub_field || '')),
      ...(nextItems || []),
    ];
  }
  return [
    ...(filters || []).filter(item => item.field !== meta.field),
    ...(nextItems || []),
  ];
}

export function togglePgyCollectionFilter(filters = [], meta, value, options = {}) {
  const currentFilters = Array.isArray(filters) ? filters : [];
  if (!meta || !meta.field) return currentFilters;
  const subField = options.subField || options.sub_field || '';
  const nextItem = makePgyFilterItem(meta, value, subField);
  const nextKey = pgyFilterKey(nextItem);
  const isSelected = currentFilters.some(item => pgyFilterKey(item) === nextKey);
  const isSingle = Boolean(options.single ?? PGY_SINGLE_VALUE_CONTROLS.has(meta.control_type));

  if (!value || value === '不限') {
    return currentFilters.filter(item => item.field !== meta.field);
  }
  if (isSingle) {
    if (isSelected) {
      return currentFilters.filter(item => item.field !== meta.field);
    }
    return replacePgyFieldFilters(currentFilters, meta, [nextItem]);
  }
  if (isSelected) {
    return currentFilters.filter(item => pgyFilterKey(item) !== nextKey);
  }
  return [...currentFilters, nextItem];
}
