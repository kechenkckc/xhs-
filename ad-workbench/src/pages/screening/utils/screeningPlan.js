import { DEFAULT_PGY_DISPLAY_METRICS } from '../constants/pgyConstants';
import {
  HARD_FILTER_OPTIONS,
  DEFAULT_COLLECTION_HARD_FILTER_FIELDS,
  DEFAULT_SCORING_HARD_FILTER_FIELDS,
  PGY_REQUIRED_FILTER_FIELDS,
  PGY_ADDITIONAL_FILTER_FIELDS,
} from '../constants/screeningConstants';
import {
  cloneHardFilterOption,
  defaultHardFilterCondition,
  getHardFilterOptionMeta,
  hardFilterConditionsFor,
  normalizePgyFilters,
  syncCollectionHardFiltersFromPgyFilters,
} from './pgyFilters';

export { defaultHardFilterCondition, hardFilterConditionsFor };

export function normalizeHardFilterItem(item = {}) {
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
}

export function normalizeHardFilterList(filters = [], defaultOptions = []) {
  const normalized = (filters || []).map(normalizeHardFilterItem);
  const seen = new Set(normalized.map(item => item.pgyField || item.field).filter(Boolean));
  const missing = defaultOptions
    .filter(option => !seen.has(option.pgyField || option.field))
    .map(cloneHardFilterOption);
  return [...normalized, ...missing];
}

export function looksLikeCollectionHardFilter(item = {}) {
  const option = getHardFilterOptionMeta(item);
  return Boolean(item.pgyField || option?.pgyField);
}

export function getLegacyCollectionHardFilters(plan = {}) {
  const pgyHardFilters = plan.pgyCollectionPlan?.hard_filters || plan.pgyCollectionPlan?.hardFilters || [];
  if (Array.isArray(plan.collectionHardFilters) && plan.collectionHardFilters.length) return plan.collectionHardFilters;
  if (Array.isArray(pgyHardFilters) && pgyHardFilters.length) return pgyHardFilters;
  return (plan.hardFilters || []).filter(looksLikeCollectionHardFilter);
}

export function getLegacyScoringHardFilters(plan = {}) {
  if (Array.isArray(plan.scoringHardFilters) && plan.scoringHardFilters.length) return plan.scoringHardFilters;
  const hardRules = plan.scoringCriteria?.hard_rules || plan.scoringCriteria?.hardRules || [];
  if (Array.isArray(hardRules) && hardRules.length) return hardRules;
  return plan.hardFilters || [];
}

export function hardFilterOptionsFor(defaultFields) {
  return HARD_FILTER_OPTIONS.filter(option => defaultFields.has(option.field));
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

export function normalizeWorkbenchPlan(plan = {}) {
  const pgyPlan = plan.pgyCollectionPlan || {};
  const collectionDefaults = hardFilterOptionsFor(DEFAULT_COLLECTION_HARD_FILTER_FIELDS);
  const scoringDefaults = hardFilterOptionsFor(DEFAULT_SCORING_HARD_FILTER_FIELDS);
  const collectionHardFilters = normalizeHardFilterList(getLegacyCollectionHardFilters(plan), collectionDefaults);
  const scoringHardFilters = normalizeHardFilterList(getLegacyScoringHardFilters(plan), scoringDefaults);
  return {
    ...plan,
    briefType: plan.briefType || 'complex',
    collectionHardFilters,
    scoringHardFilters,
    hardFilters: scoringHardFilters,
    scoringWeights: { ...(plan.scoringWeights || {}) },
    scoringCriteria: plan.scoringCriteria || {},
    fieldMappings: plan.fieldMappings || [],
    pgyCollectionPlan: {
      ...pgyPlan,
      hard_filters: collectionHardFilters,
      filters: normalizePgyFilters(pgyPlan.filters || []).map(item => ({
        field: item.field || '',
        value: item.value || '',
        reason: item.reason || '',
        control_type: item.control_type || '',
        input_values: item.input_values || [],
        pending_detail: item.pending_detail || '',
        sub_field: item.sub_field || '',
        min_items: item.min_items || undefined,
        manual: item.manual === true,
        source: item.source || '',
      })),
      display_metrics: pgyPlan.display_metrics || DEFAULT_PGY_DISPLAY_METRICS,
      detail_fields: pgyPlan.detail_fields || ['基础画像', '粉丝画像', '报价', '合作表现', '内容表现'],
      filter_catalog: pgyPlan.filter_catalog || [],
    },
  };
}

export function syncScreeningCriteria(plan = {}) {
  const normalizeForSave = (filters = []) => normalizeHardFilterList(filters, [])
    .map(item => ({
      field: String(item.field || '').trim(),
      condition: String(item.condition || '').trim(),
      value: String(item.value || '').trim(),
      required: item.required !== false,
      feishuField: String(item.feishuField || '').trim(),
      pgyField: String(item.pgyField || '').trim(),
      valueControl: String(item.valueControl || '').trim(),
      subField: String(item.subField || '').trim(),
    }))
    .filter(item => item.field || item.value);
  const scoringHardFilters = normalizeForSave(plan.scoringHardFilters || getLegacyScoringHardFilters(plan));
  const scoringWeights = { ...(plan.scoringWeights || {}) };
  const scoringCriteria = plan.scoringCriteria && typeof plan.scoringCriteria === 'object' ? plan.scoringCriteria : {};
  const pgyCollectionPlan = plan.pgyCollectionPlan && typeof plan.pgyCollectionPlan === 'object' ? plan.pgyCollectionPlan : {};
  const pgyFilters = Array.isArray(pgyCollectionPlan.filters) ? normalizePgyFilters(pgyCollectionPlan.filters) : [];
  const collectionSource = pgyFilters.length
    ? syncCollectionHardFiltersFromPgyFilters(pgyFilters, plan.collectionHardFilters || getLegacyCollectionHardFilters(plan))
    : plan.collectionHardFilters || getLegacyCollectionHardFilters(plan);
  const collectionHardFilters = normalizeForSave(collectionSource);
  return {
    ...plan,
    collectionHardFilters,
    scoringHardFilters,
    hardFilters: scoringHardFilters,
    scoringWeights,
    pgyCollectionPlan: {
      ...pgyCollectionPlan,
      filters: pgyFilters.length ? pgyFilters : pgyCollectionPlan.filters,
      hard_filters: collectionHardFilters,
    },
    scoringCriteria: {
      ...scoringCriteria,
      hard_rules: scoringHardFilters,
      dimension_weights: scoringCriteria.dimension_weights || scoringWeights,
    },
  };
}
