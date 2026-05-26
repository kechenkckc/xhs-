import {
  PGY_MARKETING_GOAL_OPTIONS,
  PGY_BLOGGER_CATEGORY_OPTIONS,
  PGY_FAN_AGE_OPTIONS,
  PGY_PRICE_RANGE_OPTIONS,
  PGY_FOLLOWER_RANGE_OPTIONS,
  PGY_FAMILY_IDENTITY_OPTIONS,
  PGY_CAREER_IDENTITY_OPTIONS,
  PGY_SPECIAL_BACKGROUND_OPTIONS,
  PGY_MATERNAL_STAGE_OPTIONS,
  PGY_REGION_OPTIONS,
  PGY_UNIT_PRICE_OPTIONS,
  PGY_NOTE_COUNT_RANGE_OPTIONS,
  PGY_INTERACTION_RANGE_OPTIONS,
} from './pgyConstants';

export const WEIGHT_LABELS = { budget: '预算匹配', fans: '粉丝量级', cpe: 'CPE效率', engagement: '互动质量', persona: '人设匹配', content: '内容风格' };

export const HARD_FILTER_OPTIONS = [
  { field: '营销目标', condition: '包含', value: '种草', required: false, feishuField: '营销目标', label: '蒲公英：营销目标', valueControl: 'multi', options: PGY_MARKETING_GOAL_OPTIONS, pgyField: '营销目标' },
  { field: '博主类目', condition: '包含', value: '教育', required: true, feishuField: '账号类型', label: '蒲公英：博主类目', valueControl: 'multi', options: PGY_BLOGGER_CATEGORY_OPTIONS, pgyField: '博主类目' },
  { field: '粉丝年龄', condition: '匹配', value: '35～44 占比高', required: true, feishuField: '粉丝年龄34岁以上占比', label: '蒲公英：粉丝年龄区间', valueControl: 'multi', options: PGY_FAN_AGE_OPTIONS, pgyField: '粉丝年龄' },
  { field: '合作报价', condition: '<=', value: '图文笔记：0.1万～2万', required: true, feishuField: '平台报价', label: '蒲公英：合作报价', valueControl: 'range', presets: PGY_PRICE_RANGE_OPTIONS, subField: '图文笔记', pgyField: '合作报价' },
  { field: '粉丝量', condition: '>=', value: '1万以上', required: false, feishuField: '粉丝数', label: '蒲公英：粉丝量下限', valueControl: 'range', options: PGY_FOLLOWER_RANGE_OPTIONS, pgyField: '粉丝量' },
  { field: '家庭身份', condition: '包含', value: '妈妈', required: false, feishuField: '家庭身份', label: '蒲公英：家庭身份', valueControl: 'multi', options: PGY_FAMILY_IDENTITY_OPTIONS, pgyField: '家庭身份' },
  { field: '职业身份', condition: '包含', value: '学生', required: false, feishuField: '职业身份', label: '蒲公英：职业身份', valueControl: 'multi', options: PGY_CAREER_IDENTITY_OPTIONS, pgyField: '职业身份' },
  { field: '特色背景', condition: '包含', value: '留学背景', required: false, feishuField: '特色背景', label: '蒲公英：特色背景', valueControl: 'multi', options: PGY_SPECIAL_BACKGROUND_OPTIONS, pgyField: '特色背景' },
  { field: '母婴阶段', condition: '包含', value: '7-12岁', required: false, feishuField: '孩子年级', label: '蒲公英：母婴阶段', valueControl: 'multi', options: PGY_MATERNAL_STAGE_OPTIONS, pgyField: '母婴阶段' },
  { field: '粉丝地域', condition: '匹配', value: '北京、上海', required: false, feishuField: '粉丝地域', label: '蒲公英：粉丝地域', valueControl: 'multi', options: PGY_REGION_OPTIONS, pgyField: '粉丝地域' },
  { field: '预估阅读单价', condition: '<=', value: '图文笔记阅读单价≤2', required: false, feishuField: '合作笔记自然CPC', label: '蒲公英：预估阅读单价', valueControl: 'number', presets: PGY_UNIT_PRICE_OPTIONS, unit: '元', subField: '图文笔记阅读单价', pgyField: '预估阅读单价' },
  { field: '预估互动单价', condition: '<=', value: '图文笔记互动单价≤20', required: false, feishuField: '合作笔记自然CPE', label: '蒲公英：预估互动单价', valueControl: 'number', unit: '元', subField: '图文笔记互动单价', pgyField: '预估互动单价' },
  { field: '阅读中位数', condition: '>=', value: '0.5万以上', required: false, feishuField: '阅读中位数（日常）', label: '蒲公英：阅读中位数', valueControl: 'range', presets: PGY_NOTE_COUNT_RANGE_OPTIONS, pgyField: '阅读中位数' },
  { field: '互动中位数', condition: '>=', value: '500以上', required: false, feishuField: '互动中位数（日常）', label: '蒲公英：互动中位数', valueControl: 'range', presets: PGY_INTERACTION_RANGE_OPTIONS, pgyField: '互动中位数' },
  { field: '曝光中位数', condition: '>=', value: '1万以上', required: false, feishuField: '曝光中位数（日常）', label: '蒲公英：曝光中位数', valueControl: 'range', presets: PGY_NOTE_COUNT_RANGE_OPTIONS, pgyField: '曝光中位数' },
  { field: '详情页证据', condition: '完善', value: '用于人设/内容分析，不作为硬性淘汰', required: false, feishuField: '蒲公英链接', label: '评分：详情页证据完善', valueControl: 'none' },
  { field: '限流风险', condition: '规避', value: '疑似限流、异常流量', required: false, feishuField: '品牌备注', label: '评分：规避限流/异常流量', valueControl: 'multi', options: ['疑似限流', '异常流量', '违规', '低活博主', '掉粉博主'] },
];

export const HARD_FILTER_CONDITIONS_BY_KIND = {
  number: ['>=', '<=', '>', '<', '='],
  existence: ['必须存在'],
  text: ['匹配', '包含', '不包含'],
  avoid: ['规避', '不包含'],
};
export const DEFAULT_HARD_FILTER_CONDITIONS = ['匹配', '包含', '必须存在'];

export const hardFilterKey = (item) => `${item.field || ''}|${item.condition || ''}|${item.value || ''}|${item.subField || item.sub_field || ''}`;
export const pgyFilterKey = (item) => `${item.field || ''}|${item.value || ''}|${item.sub_value || item.subValue || ''}|${item.sub_field || item.subField || ''}|${item.country || ''}|${item.province || ''}|${item.city || ''}`;
export const metricKey = (item) => String(item?.value || item || '');
export const hardFilterLabel = (item) => item.label || `${item.field}${item.condition ? ` ${item.condition}` : ''}${item.value ? ` ${item.value}` : ''}`;
export const pgyFilterLabel = (item) => {
  if (['地域', '粉丝地域'].includes(item.field) && item.country) {
    const detail = item.city || item.province || item.value;
    return detail && detail !== item.country ? `${item.field}：${item.country}-${detail}` : `${item.field}：${item.country}`;
  }
  if (item.field === '营销目标' && (item.goal || item.parent_value || item.parentValue)) {
    return `${item.field}：${item.goal || item.parent_value || item.parentValue}-${item.value}`;
  }
  if (item.field === '博主类目' && (item.sub_value || item.subValue)) {
    return `${item.field}：${item.value}-${item.sub_value || item.subValue}`;
  }
  return item.label || `${item.field}：${item.value}`;
};
export const PGY_REQUIRED_FILTER_FIELDS = new Set(['博主类目', '粉丝量', '粉丝年龄', '合作报价']);
export const PGY_ADDITIONAL_FILTER_FIELDS = new Set(['预估阅读单价', '预估互动单价', '阅读中位数', '互动中位数', '曝光中位数', '常规剔除', '地域', '粉丝地域']);
export const DEFAULT_COLLECTION_HARD_FILTER_FIELDS = new Set(['博主类目', '粉丝量', '粉丝年龄', '合作报价']);
export const DEFAULT_SCORING_HARD_FILTER_FIELDS = new Set([
  '合作报价',
  '预估阅读单价',
  '预估互动单价',
  '详情页证据',
  '限流风险',
]);
export const CONTROL_TYPE_LABELS = {
  tag: '标签',
  tag_select_with_hover_subcategory: '类目/二级类目',
  checkbox: '复选',
  checkbox_popover: '弹层多选',
  brand_search_recommendation: '品牌/竞品推荐',
  dropdown: '下拉',
  single_select_popover: '弹层单选',
  dropdown_single: '单选下拉',
  select_popover: '弹层选择',
  cascade_checkbox_popover: '二级下拉',
  three_level_cascade_checkbox_popover: '三级级联',
  range_select_pair: '区间',
  number_range: '数值区间',
  preset_or_number_range: '档位/区间',
  preset_or_percent_range: '比例区间',
  subfield_preset_or_number_range: '子筛选区间',
  subfield_preset_or_percent_range: '子筛选比例',
  multi_subfield_preset_or_number_range: '多子项区间',
  text_multi_with_exclude: '填空',
  searchable_multi_select_with_exclude: '搜索多选',
  nested_select_popover: '需继续下拉',
  marketing_goal_metric: '目标指标',
};
