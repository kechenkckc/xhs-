import { formatCompleteness, formatCurrency, compactNumber, formatDateLabel, formatDateTime, formatPercentValue, parseCountValue } from './formatters';
import { normalizeWorkbenchPlan } from './screeningPlan';
import { hardFilterLabel } from '../constants/screeningConstants';

export { parseCountValue };

export function reviewVariantFromStatus(status) {
  return { 已通过: 'green', 已写回飞书: 'green', 已邀约: 'blue', 已驳回: 'red', 备选: 'amber', 待审核: 'blue', 待补数据: 'default' }[status] || 'default';
}

export function normalizeDimensionScore(value, weight) {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  const normalized = number <= weight ? (number / weight) * 100 : number;
  return Math.max(0, Math.min(100, Math.round(normalized)));
}

export function deriveDimensionScores(item) {
  const scores = {
    budget: normalizeDimensionScore(item.budget_score, 15),
    fans: normalizeDimensionScore(item.fans_score, 5),
    cpe: normalizeDimensionScore(item.cpe_score, 20),
    engagement: normalizeDimensionScore(item.traffic_score, 30),
    persona: normalizeDimensionScore(item.persona_score, 20),
    content: normalizeDimensionScore(item.content_score, 10),
  };
  const hasBackendScores = Object.values(scores).some(value => value !== null);
  if (hasBackendScores) {
    return Object.fromEntries(Object.entries(scores).map(([key, value]) => [key, value ?? 0]));
  }

  const fallback = Number(item.total_score || 0);
  if (fallback > 0) {
    return {
      budget: Math.round(fallback),
      fans: Math.round(fallback),
      cpe: Math.round(fallback),
      engagement: Math.round(fallback),
      persona: Math.round(fallback),
      content: Math.round(fallback),
    };
  }
  return null;
}

export function normalizeScoreTierKey(value, score) {
  const text = String(value ?? '').trim().replace(/\s+/g, '').toUpperCase();
  if (['S', 'A', 'B+', 'B', 'C'].includes(text)) return text;
  if (['S档', 'S級', 'S级'].includes(text)) return 'S';
  if (['A档', 'A級', 'A级'].includes(text)) return 'A';
  if (['B+档', 'B＋档', 'B+級', 'B+级', 'B＋級', 'B＋级'].includes(text)) return 'B+';
  if (['B档', 'B級', 'B级'].includes(text)) return 'B';
  if (['C档', 'C級', 'C级'].includes(text)) return 'C';
  if (/未评分|待评分|UNSCORED|PENDING/.test(text)) return '未评分';
  if (/最高优先级/.test(text)) return 'S';
  if (/高优先级/.test(text) && !/中高/.test(text)) return 'A';
  if (/中高优先级/.test(text)) return 'B+';
  if (/中优先级/.test(text)) return 'B';
  if (/低优先级/.test(text)) return 'C';

  if (score === null || score === undefined || score === '') return '';
  const number = Number(score);
  if (!Number.isFinite(number)) return '';
  if (number >= 95) return 'S';
  if (number >= 80) return 'A';
  if (number >= 75) return 'B+';
  if (number >= 70) return 'B';
  return 'C';
}

export function sanitizeCreatorType(value) {
  const text = String(value || '').trim().replace(/\s+/g, '');
  if (!text) return '';
  if (text.length > 36) return '';
  if (/获赞|收藏|邀约|合作报价|一口价|相似的博主|查看更多|粉丝数|阅读中位数|互动中位数|曝光中位数/.test(text)) return '';
  if (/[¥￥]/.test(text)) return '';
  if (/(^|\/)\d+(?:\.\d+)?(?:w|W|万|%)?(\/|$)/.test(text)) return '';
  return text;
}

export function getCreatorDisplayType(item) {
  const explicit = sanitizeCreatorType(item.creator_type || item['达人类型'] || item.type);
  if (explicit && /^(KOL|KOC)$/i.test(explicit)) return explicit.toUpperCase();
  return Number(item.followers_count || item.followersNum || 0) >= 100000 ? 'KOL' : 'KOC';
}

export function getCreatorCategoryType(item) {
  const explicit = sanitizeCreatorType(item.creator_type || item['达人类型']);
  if (explicit && !/^(KOL|KOC)$/i.test(explicit)) return explicit;
  return '';
}

const SCORING_RISK_STANDARDS = {
  audience: '目标人群匹配',
  traffic: '真实流量质量',
  efficiency: '成本效率',
  direction: '内容方向弱匹配',
  execution: '执行确定性',
};

const SCORING_STANDARD_SCORE_KEYS = {
  [SCORING_RISK_STANDARDS.audience]: ['fans'],
  [SCORING_RISK_STANDARDS.traffic]: ['engagement'],
  [SCORING_RISK_STANDARDS.efficiency]: ['cpe'],
  [SCORING_RISK_STANDARDS.direction]: ['persona', 'content'],
  [SCORING_RISK_STANDARDS.execution]: ['budget'],
};

const DEFAULT_PRODUCT_PROFILE = {
  name: '学习工具产品',
  keywords: ['学习', '工具', '作业', '阅读', '孩子', '家长'],
  scenarios: ['真实学习场景', '家长陪伴决策', '工具使用过程'],
  presentation: ['使用过程', '问题解决前后', '孩子反馈', '家长口吻'],
};

function getProjectProductProfile(project = {}) {
  const text = `${project.projectName || project.project_name || project.name || ''} ${project.brief || ''} ${project.summary || ''}`;
  if (/点读笔|词典笔|听力宝|绘本|阅读笔/.test(text)) {
    return {
      name: text.match(/有道[^，。；;\s]{0,8}(?:点读笔|词典笔|听力宝|阅读笔)/)?.[0] || '有道点读笔',
      keywords: ['点读', '阅读', '绘本', '英语', '发音', '跟读', '查词', '单词', '听力', '孩子自主学'],
      scenarios: ['亲子阅读', '英语启蒙/跟读', '孩子自主阅读', '查词发音'],
      presentation: ['点读演示', '孩子使用过程', '发音/跟读反馈', '家长陪伴视角'],
    };
  }
  if (/答疑笔|学习笔|错题|作业答疑|拍照答疑/.test(text)) {
    return {
      name: text.match(/有道[^，。；;\s]{0,8}(?:答疑笔|学习笔)/)?.[0] || '有道答疑笔',
      keywords: ['答疑', '作业', '错题', '解题', '学习规划', '自主学习', '家长辅导', '小初高'],
      scenarios: ['家庭作业答疑', '错题讲解', '孩子自主学习', '家长辅导减负'],
      presentation: ['解题过程', '使用前后对比', '孩子独立使用', '家长真实反馈'],
    };
  }
  return DEFAULT_PRODUCT_PROFILE;
}

function normalizeRiskLabel(text) {
  const value = String(text || '').replace(/^【(?:通用初筛|大模型分析)】/, '').trim();
  if (!value) return '';
  if (/35岁以上|34岁以上|粉丝年龄|粉丝画像|目标人群|人群画像|家长决策|宝妈|妈妈|父母/.test(value)) {
    return SCORING_RISK_STANDARDS.audience;
  }
  if (/阅读|互动|曝光|近30天|流量|T级|P25|P50|P75|搜索\+推荐|搜索推荐|搜推|限流|违规|异常/.test(value)) {
    return SCORING_RISK_STANDARDS.traffic;
  }
  if (/报价|预算|CPC|CPE|CPM|成本|效率|阅读单价|互动单价|超硬上限|偏高/i.test(value)) {
    return SCORING_RISK_STANDARDS.efficiency;
  }
  if (/人设|内容|类目|标签|场景|方向|Brief|教育|母婴|亲子|家庭|孩子|笔记|主页|简介|垂直|硬广/.test(value)) {
    return SCORING_RISK_STANDARDS.direction;
  }
  if (/蒲公英|链接|资料|完整度|执行|回复|身份|邀约|联系|待补|缺字段|采集/.test(value)) {
    return SCORING_RISK_STANDARDS.execution;
  }
  return '';
}

function isRiskReasonClause(text) {
  const value = String(text || '').replace(/^【(?:通用初筛|大模型分析)】/, '').trim();
  if (!value) return false;
  if (/高分依据|加成|基础信息匹配/.test(value)) return false;
  return /未|不足|偏高|风险|异常|限流|违规|超过|高于|低于|弱|缺少|待核|暂缓|不匹配|封顶|规避|硬性|明显低/.test(value);
}

function collectScoreReasonRisks(scoreReason) {
  return String(scoreReason || '')
    .split(/[；;]/)
    .filter(isRiskReasonClause)
    .map(normalizeRiskLabel)
    .filter(Boolean);
}

function deriveScoringRiskLabels(item, scores) {
  const risks = [];
  const scoreValue = (key) => Number(scores?.[key]);
  if (Number.isFinite(scoreValue('fans')) && scoreValue('fans') > 0 && scoreValue('fans') < 75) {
    risks.push(SCORING_RISK_STANDARDS.audience);
  }
  if (Number.isFinite(scoreValue('engagement')) && scoreValue('engagement') > 0 && scoreValue('engagement') < 75) {
    risks.push(SCORING_RISK_STANDARDS.traffic);
  }
  if (Number.isFinite(scoreValue('cpe')) && scoreValue('cpe') > 0 && scoreValue('cpe') < 75) {
    risks.push(SCORING_RISK_STANDARDS.efficiency);
  }
  if (
    (Number.isFinite(scoreValue('persona')) && scoreValue('persona') > 0 && scoreValue('persona') < 75)
    || (Number.isFinite(scoreValue('content')) && scoreValue('content') > 0 && scoreValue('content') < 75)
  ) {
    risks.push(SCORING_RISK_STANDARDS.direction);
  }
  if (Number.isFinite(scoreValue('budget')) && scoreValue('budget') > 0 && scoreValue('budget') < 75) {
    risks.push(SCORING_RISK_STANDARDS.execution);
  }
  if (!item.pgy_url && !item.pgyUrl && !item['蒲公英链接']) {
    risks.push(SCORING_RISK_STANDARDS.execution);
  }
  return risks;
}

export function mapBackendCreator(item) {
  const hasScore = item.total_score !== null && item.total_score !== undefined && item.total_score !== '';
  const score = hasScore ? Math.round(Number(item.total_score || 0)) : null;
  const ruleGroupScore = item.rule_group_score !== null && item.rule_group_score !== undefined && item.rule_group_score !== ''
    ? Math.round(Number(item.rule_group_score || 0))
    : score;
  const type = getCreatorDisplayType(item);
  const categoryType = getCreatorCategoryType(item);
  const scores = deriveDimensionScores(item);
  const risks = [];
  const rawPayload = getCreatorRawPayload({ raw: item });
  const collectionIssues = Array.isArray(rawPayload.collection_hard_filter_issues) ? rawPayload.collection_hard_filter_issues : [];
  collectionIssues.forEach(issue => {
    if (issue) risks.push(normalizeRiskLabel(issue));
  });
  if (item.hard_filter_passed === 0 || item.hard_filter_passed === false) {
    risks.push(...collectScoreReasonRisks(item.score_reason).slice(0, 4));
    if (!risks.length) risks.push(SCORING_RISK_STANDARDS.execution);
  }
  const pgyUrl = getPgyUrl({ raw: item });
  if (!pgyUrl) risks.push(SCORING_RISK_STANDARDS.execution);
  if (Number(item.quote_price || 0) >= 20000) risks.push(SCORING_RISK_STANDARDS.efficiency);
  if (item.rate_limit_risk && !['无', '无明显', '低风险'].includes(item.rate_limit_risk)) risks.push(normalizeRiskLabel(item.rate_limit_risk));
  risks.push(...deriveScoringRiskLabels({ ...item, pgy_url: pgyUrl }, scores));
  const uniqueRisks = uniqueCompactItems(risks, 4);
  return {
    id: item.creator_id,
    name: item.nickname || item.creator_id,
    type,
    typeVariant: type === 'KOL' ? 'purple' : 'blue',
    followers: compactNumber(item.followers_count),
    followersNum: Number(item.followers_count || 0),
    quote: formatCurrency(item.quote_price),
    quoteNum: Number(item.quote_price || 0),
    baseScore: score,
    ruleGroupScore,
    scorePending: !hasScore,
    baseOnlyScore: Math.round(Number(item.base_score || 0)),
    bonusScore: Math.round(Number(item.bonus_score || 0)),
    informationCompleteness: item.information_completeness,
    informationCompletenessLabel: formatCompleteness(item.information_completeness),
    initialTier: normalizeScoreTierKey(item.initial_tier || item.tier || item.detail_collection_priority, score),
    detailCollectionPriority: item.detail_collection_priority || '',
    risk: uniqueRisks,
    scores,
    aiReason: item.score_reason || '待补充蒲公英详情数据后生成完整评分说明。',
    review: item.status || '待补数据',
    reviewVariant: reviewVariantFromStatus(item.status),
    poolStage: item.pool_stage || null,
    finalScore: hasScore ? score : null,
    reason: item.review_reason || item.score_reason || '',
    reviewer: item.reviewer,
    reviewedAt: item.reviewed_at,
    createdAt: item.created_at || '',
    updatedAt: item.updated_at || '',
    collectedAt: item.collected_at || item.created_at || '',
    xiaohongshuId: item.xiaohongshu_id || '',
    ipCity: item.ip_city || '',
    personaTags: item.persona_tags || '',
    categoryTags: categoryType,
    avatarUrl: item.avatar_url || '',
    topicPoint: item.topic_point || '',
    childGrade: item.child_grade || '',
    childGradeConfidence: item.child_grade_confidence || '',
    childGradeEvidence: item.child_grade_evidence || '',
    naturalCpe: item.natural_cpe,
    effectiveCpc: item.effective_cpc,
    effectiveCpcSource: item.effective_cpc_source || '',
    effectiveCpe: item.effective_cpe,
    effectiveCpeSource: item.effective_cpe_source || '',
    fans35PlusRatio: item.fans_35_plus_ratio,
    fans35PlusRatioSource: item.fans_35_plus_ratio_source || '',
    contentSceneTags: item.content_scene_tags || '',
    contentSceneEvidence: item.content_scene_evidence || '',
    presentationStyleTags: item.presentation_style_tags || '',
    searchReviewStatus: item.search_recommend_review_status || '',
    searchReviewNote: item.search_recommend_review_note || '',
    rateLimitRiskReason: item.rate_limit_risk_reason || '',
    llmManualReviewItems: parseStructuredList(item.manual_review_items),
    llmEvidenceQuotes: parseStructuredList(item.evidence_quotes),
    llmConfidence: item.llm_confidence,
    llmPromptVersion: item.llm_prompt_version || '',
    llmSchemaVersion: item.llm_schema_version || '',
    raw: item,
  };
}

export function getScoreColor(score) {
  if (score === null || score === undefined || score === '') return '#64748B';
  if (score >= 95) return '#10B981';
  if (score >= 80) return '#3B82F6';
  if (score >= 75) return '#F59E0B';
  if (score >= 70) return '#D97706';
  return '#EF4444';
}

export function getScoreTier(score) {
  if (score === null || score === undefined || score === '') return { key: '未评分', label: '未评分', variant: 'default', text: '待评分', color: '#64748B' };
  if (score >= 95) return { key: 'S', label: 'S档', variant: 'green', text: '最高优先级', color: '#10B981' };
  if (score >= 80) return { key: 'A', label: 'A档', variant: 'blue', text: '高优先级', color: '#3B82F6' };
  if (score >= 75) return { key: 'B+', label: 'B+档', variant: 'amber', text: '中高优先级', color: '#F59E0B' };
  if (score >= 70) return { key: 'B', label: 'B档', variant: 'amber', text: '中优先级', color: '#D97706' };
  return { key: 'C', label: 'C档', variant: 'red', text: '低优先级', color: '#EF4444' };
}

export function getCreatorDisplayTier(creator) {
  if (!creator || creator.scorePending) return getScoreTier(null);
  const normalizedTier = normalizeScoreTierKey(creator.initialTier, creator.baseScore);
  if (!normalizedTier) return getScoreTier(creator.baseScore);
  const labels = {
    S: { key: 'S', label: 'S档', variant: 'green', text: '最高优先级', color: '#10B981' },
    A: { key: 'A', label: 'A档', variant: 'blue', text: '高优先级', color: '#3B82F6' },
    'B+': { key: 'B+', label: 'B+档', variant: 'amber', text: '中高优先级', color: '#F59E0B' },
    B: { key: 'B', label: 'B档', variant: 'amber', text: '中优先级', color: '#D97706' },
    C: { key: 'C', label: 'C档', variant: 'red', text: '低优先级', color: '#EF4444' },
  };
  return labels[normalizedTier] || getScoreTier(creator.baseScore);
}

export function getCreatorPrioritySignals(creator) {
  const reason = String(creator?.aiReason || creator?.reason || creator?.raw?.score_reason || '');
  const text = `${creator?.name || ''} ${getCreatorIntro(creator)} ${getCreatorTags(creator).join(' ')} ${reason}`;
  const signals = [];
  if (/听课宝优先级1|S档依据|留学|留学生|海外|国外|美本|英本|海本|国际学校|overseas/i.test(text)) {
    signals.push({ label: '留学/留学生背景', tone: 'primary' });
  }
  if (/听课宝优先级2|Brief|学习|听课|课堂|上课|笔记|复盘|备考|essay|assignment|教程|干货/i.test(text)) {
    signals.push({ label: '命中Brief学习场景', tone: 'content' });
  }
  if (/听课宝优先级3|综合数据|成本效率|阅读\/互动|CPM|CPC|CPE|平均阅读|平均互动|中位阅读|互动/i.test(text)) {
    signals.push({ label: '阅读互动与成本优秀', tone: 'metric' });
  }
  return signals.slice(0, 3);
}

export function getCreatorDetailStatus(creator) {
  const completeness = creator.informationCompletenessLabel || formatCompleteness(creator.informationCompleteness);
  if (!getPgyUrl(creator)) return { label: '缺详情链接', variant: 'red' };
  const noteCount = getCreatorRealNoteCases(creator).length;
  if (hasCreatorDetailEvidence(creator)) {
    return { label: noteCount ? `详情已完善 · ${noteCount}篇` : '详情已完善', variant: 'green' };
  }
  if (completeness === '待补') return { label: '详情待补', variant: 'amber' };
  const number = Number(String(completeness).replace('%', ''));
  if (Number.isFinite(number) && number >= 80) return { label: `详情已完善 · ${completeness}`, variant: 'green' };
  if (Number.isFinite(number) && number >= 50) return { label: `详情部分 ${completeness}`, variant: 'blue' };
  return { label: `详情待补 ${completeness}`, variant: 'amber' };
}

function hasMeaningfulDetailValue(value) {
  if (value === null || value === undefined) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'object') return Object.values(value).some(hasMeaningfulDetailValue);
  return String(value).trim() !== '';
}

function hasDetailSummaryEvidence(payload) {
  const summary = payload?.detail_collection_summary || payload?.detailCollectionSummary;
  if (!summary || typeof summary !== 'object') return false;
  const count = Number(summary.module_count ?? summary.moduleCount ?? summary.field_count ?? summary.fieldCount ?? summary.note_count ?? summary.noteCount ?? 0);
  if (Number.isFinite(count) && count > 0) return true;
  if (hasMeaningfulDetailValue(summary.collected_at || summary.collectedAt || summary.completed_at || summary.completedAt)) return true;
  const status = String(summary.status || '').toLowerCase();
  return /success|complete|completed|done|collected|已完成|完成|成功/.test(status);
}

export function hasCreatorDetailEvidence(creator) {
  const rawPayload = getCreatorRawPayload(creator);
  const nestedPayloads = collectNestedPayloads(rawPayload, creator.raw, creator.rawPayload, creator.raw_payload);

  if (nestedPayloads.flatMap(collectNoteCaseArrays).length > 0) return true;
  if (nestedPayloads.some(hasDetailSummaryEvidence)) return true;

  const detailFields = [
    'personal_intro',
    'profile_intro',
    'xhs_profile_intro',
    'blogger_profile',
    'user_profile',
    'audience_profile_chart_metrics',
    'cooperation_note_case_pages',
    'cooperation_note_cases',
    'recent_note_cases',
    'recent_notes',
    'fans_age_distribution',
    'fans_gender_distribution',
    'content_scene_evidence',
    'child_grade_evidence',
  ];
  return nestedPayloads.some(payload => (
    detailFields.some(key => hasMeaningfulDetailValue(payload[key]))
    || hasMeaningfulDetailValue(payload.detail)
  ));
}

export function isValidPgyDetailUrl(value) {
  if (!value || value === '待填') return false;
  try {
    const url = new URL(value);
    if (url.hostname !== 'pgy.xiaohongshu.com') return false;
    return url.pathname.includes('/solar/pre-trade/blogger-detail/') || url.pathname.includes('/creator/');
  } catch {
    return false;
  }
}

export function getPgyUrl(creator) {
  const candidates = [
    creator.raw?.pgy_url,
    creator.raw?.profile_url,
    creator.pgyUrl,
    creator.profileUrl,
  ];
  return candidates.find(isValidPgyDetailUrl) || '';
}

export function pickCreatorValue(creator, keys, fallback = '') {
  for (const key of keys) {
    const value = creator?.[key] ?? creator?.raw?.[key];
    if (value !== undefined && value !== null && value !== '') return value;
  }
  return fallback;
}

export function getCreatorRawPayload(creator) {
  const payload = creator?.raw?.raw_payload ?? creator?.rawPayload ?? creator?.raw_payload;
  return parsePayloadObject(payload);
}

function parsePayloadObject(payload, depth = 0) {
  if (!payload || depth > 4) return {};
  if (typeof payload === 'object') return payload;
  if (typeof payload !== 'string') return {};
  try {
    const parsed = JSON.parse(payload);
    if (typeof parsed === 'string') return parsePayloadObject(parsed, depth + 1);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function collectNestedPayloads(...items) {
  const payloads = [];
  const seen = new Set();
  const visit = (item, depth = 0) => {
    if (!item || depth > 4) return;
    const payload = typeof item === 'string' ? parsePayloadObject(item) : item;
    if (!payload || typeof payload !== 'object') return;
    if (seen.has(payload)) return;
    seen.add(payload);
    payloads.push(payload);
    ['detail', 'raw_payload', 'rawPayload', 'payload', 'data', 'parsed'].forEach((key) => visit(payload[key], depth + 1));
  };
  items.forEach(item => visit(item));
  return payloads;
}

export function parseStructuredList(value) {
  if (!value) return [];
  if (Array.isArray(value)) {
    return value.map(item => String(item || '').trim()).filter(Boolean);
  }
  if (typeof value === 'object') {
    return Object.values(value).map(item => String(item || '').trim()).filter(Boolean);
  }
  if (typeof value !== 'string') return [];
  const text = value.trim();
  if (!text) return [];
  try {
    const parsed = JSON.parse(text);
    return parseStructuredList(parsed);
  } catch {
    return text.split(/[；;\n]+/).map(item => item.trim()).filter(Boolean);
  }
}

export function splitCreatorTags(value) {
  return String(value || '')
    .split(/[\/,，、\s]+/)
    .map(item => item.trim())
    .filter(Boolean);
}

export function uniqueCompactItems(items, limit = 10) {
  const seen = new Set();
  const result = [];
  items.forEach(item => {
    const text = String(item || '').trim();
    if (!text || seen.has(text)) return;
    seen.add(text);
    result.push(text);
  });
  return result.slice(0, limit);
}

export function getCreatorLocation(creator) {
  const explicit = pickCreatorValue(creator, ['ipCity', 'ip_city', 'IP城市']);
  if (explicit) return explicit;
  if (/上海|沪/.test(creator.name)) return '上海';
  if (/北京|海淀|胡同/.test(creator.name)) return '北京';
  return '其他';
}

export function getCreatorCategory(creator) {
  const creatorType = getCreatorCategoryType({
    creator_type: pickCreatorValue(creator, ['categoryTags', 'category_tags', 'content_tags', 'creator_type', '达人类型']),
  });
  if (creatorType) return creatorType;
  const tags = splitCreatorTags(pickCreatorValue(creator, ['personaTags', 'persona_tags', '人设标签']));
  return tags[0] || '达人';
}

export function getCreatorCollectedAt(creator) {
  return pickCreatorValue(creator, ['collectedAt', 'collected_at', 'createdAt', 'created_at']);
}

export function getCreatorXhsId(creator) {
  const explicit = pickCreatorValue(creator, ['xiaohongshuId', 'xiaohongshu_id', '小红书号']);
  if (explicit && !/^(pgy:list|pgy-export|GEN-)/.test(String(explicit))) return explicit;
  return '待采集';
}

export function getCreatorDisplayId(creator) {
  const xhsId = getCreatorXhsId(creator);
  if (xhsId && xhsId !== '待采集') return `小红书号：${xhsId}`;
  const pgyBloggerId = pickCreatorValue(creator, ['pgy_blogger_id', 'pgyBloggerId', '蒲公英博主ID']);
  if (pgyBloggerId) return `蒲公英ID：${pgyBloggerId}`;
  const rawId = String(creator?.id || creator?.creator_id || '');
  if (/^(pgy:list|pgy-export|GEN-)/.test(rawId)) return '小红书号待采集';
  return rawId ? `ID：${rawId}` : '小红书号待采集';
}

export function getCreatorIntro(creator) {
  const rawPayload = getCreatorRawPayload(creator);
  const nestedPayloads = collectNestedPayloads(rawPayload, creator.raw);
  const intro = [
    creator.personalIntro,
    creator.personal_intro,
    creator.profileIntro,
    creator.profile_intro,
    creator.bio,
    creator.signature,
    creator.description,
    creator.raw?.personal_intro,
    creator.raw?.profile_intro,
    creator.raw?.bio,
    creator.raw?.signature,
    ...nestedPayloads.flatMap(payload => [
      payload.personal_intro,
      payload.profile_intro,
      payload.xhs_profile_intro,
      payload.bio,
      payload.signature,
      payload.blogger_profile,
      payload.user_profile,
      payload.profile?.intro,
      payload.profile?.bio,
    ]),
  ].find(value => String(value || '').trim());
  return intro ? String(intro).trim() : '暂无详情页个人简介';
}

export function getCreatorAvatarUrl(creator) {
  return pickCreatorValue(creator, ['avatarUrl', 'avatar_url']);
}

export function getCreatorMetricChips(creator) {
  const chips = [];
  const grade = pickCreatorValue(creator, ['childGrade', 'child_grade', '孩子年级']);
  const cpe = pickCreatorValue(creator, ['effectiveCpe', 'effective_cpe', 'naturalCpe', 'natural_cpe', '合作笔记自然CPE', 'image_interaction_unit_price', 'video_interaction_unit_price']);
  const cpc = pickCreatorValue(creator, ['effectiveCpc', 'effective_cpc', 'natural_cpc', '合作笔记自然CPC', 'image_read_unit_price', 'video_read_unit_price']);
  const searchReviewStatus = pickCreatorValue(creator, ['searchReviewStatus', 'search_recommend_review_status']);
  const traffic = pickCreatorValue(creator, ['traffic_stability', '近30天流量稳定性']);
  const rateLimit = pickCreatorValue(creator, ['rateLimitRisk', 'rate_limit_risk', '限流风险判断']);
  const cpeNumber = Number(cpe);
  const cpcNumber = Number(cpc);
  if (grade) chips.push(`年级 ${grade}`);
  if (Number.isFinite(cpeNumber)) chips.push(cpeNumber <= 10 ? '互动成本优秀' : cpeNumber <= 20 ? '互动成本达标' : '互动成本偏高');
  if (Number.isFinite(cpcNumber)) chips.push(cpcNumber <= 2 ? '阅读成本优秀' : cpcNumber <= 3 ? '阅读成本达标' : '阅读成本偏高');
  if (searchReviewStatus && searchReviewStatus !== '已复核') chips.push('搜推待复核');
  if (traffic) chips.push(`流量${traffic}`);
  if (rateLimit && !['无', '低', '低风险'].includes(String(rateLimit))) chips.push(`风险${rateLimit}`);
  return uniqueCompactItems(chips, 8);
}

export function getCreatorTags(creator) {
  const budgetStatus = pickCreatorValue(creator, ['budget_status', '预算状态']);
  const mcnStatus = pickCreatorValue(creator, ['mcn_status', 'MCN状态']);
  const tagGroups = getCreatorTagGroups(creator);
  return uniqueCompactItems([
    ...tagGroups.persona,
    ...tagGroups.content,
    ...tagGroups.metric,
    ...tagGroups.risk,
    budgetStatus,
    mcnStatus,
  ], 20);
}

export function creatorHasTag(creator, tag) {
  if (!tag) return true;
  return getCreatorTags(creator).includes(tag);
}

export function projectBrandHint(creator) {
  const text = `${creator.name || ''} ${getCreatorIntro(creator)}`;
  if (/有道|答疑|学习|教育|作业/.test(text)) return '教育学习';
  if (/母婴|育儿|宝宝/.test(text)) return '母婴亲子';
  if (/美妆|护肤/.test(text)) return '美妆护肤';
  return '内容样本';
}

export function getCreatorNoteCases(creator) {
  const realCases = getCreatorRealNoteCases(creator);
  if (realCases.length) return realCases;

  const tags = getCreatorTags(creator);
  const direction = pickCreatorValue(creator, ['cooperation_direction', '合作方向']);
  return [
    {
      brand: projectBrandHint(creator),
      title: direction || `${creator.name}的日常内容与项目场景`,
      readCount: pickCreatorValue(creator, ['cooperation_read_median', '合作阅读中位数']) || pickCreatorValue(creator, ['image_daily_read_median']),
      likeCount: pickCreatorValue(creator, ['cooperation_interaction_median', '合作互动中位数']),
      saveCount: '',
      publishedAt: formatDateLabel(getCreatorCollectedAt(creator)),
      promoted: true,
      coverUrl: getCreatorAvatarUrl(creator),
      source: 'fallback',
    },
    ...tags.slice(0, 3).map((tag, index) => ({
      brand: '证据标签',
      title: `${tag}：${getCreatorIntro(creator).slice(0, 34) || '详情完善后生成更多证据'}`,
      readCount: '',
      likeCount: '',
      saveCount: '',
      publishedAt: index === 0 ? '详情页快照' : '规则命中',
      promoted: false,
      coverUrl: '',
      source: 'fallback',
    })),
  ].slice(0, 6);
}

export function collectNoteCaseArrays(payload = {}) {
  if (!payload || typeof payload !== 'object') return [];
  const pages = Array.isArray(payload.cooperation_note_case_pages)
    ? payload.cooperation_note_case_pages.flatMap(page => page?.cases || [])
    : [];
  const dataPages = Array.isArray(payload.data?.cooperation_note_case_pages)
    ? payload.data.cooperation_note_case_pages.flatMap(page => page?.cases || [])
    : [];
  return [
    ...(Array.isArray(payload.recent_note_cases) ? payload.recent_note_cases : []),
    ...(Array.isArray(payload.recent_notes) ? payload.recent_notes : []),
    ...(Array.isArray(payload.recent_note_briefs) ? payload.recent_note_briefs : []),
    ...(Array.isArray(payload.cooperation_note_cases) ? payload.cooperation_note_cases : []),
    ...(Array.isArray(payload.note_cases) ? payload.note_cases : []),
    ...(Array.isArray(payload.notes) ? payload.notes : []),
    ...(Array.isArray(payload.note_list) ? payload.note_list : []),
    ...(Array.isArray(payload.noteList) ? payload.noteList : []),
    ...(Array.isArray(payload.data?.recent_notes) ? payload.data.recent_notes : []),
    ...(Array.isArray(payload.data?.cooperation_note_cases) ? payload.data.cooperation_note_cases : []),
    ...(Array.isArray(payload.data?.note_cases) ? payload.data.note_cases : []),
    ...pages,
    ...dataPages,
  ];
}

export function getCreatorRealNoteCases(creator) {
  const rawPayload = getCreatorRawPayload(creator);
  const nestedPayloads = collectNestedPayloads(rawPayload, creator.raw, creator.rawPayload, creator.raw_payload);
  const rawCases = [
    ...nestedPayloads.flatMap(collectNoteCaseArrays),
  ];
  const seen = new Set();
  const cases = rawCases
    .map((item, index) => {
      if (typeof item === 'string') return { brand: '笔记', title: item, index };
      if (!item || typeof item !== 'object') return null;
      const noteId = item.note_id || item.noteId || item.noteID || item.id || item.note_id_str || '';
      const rawComments = Array.isArray(item.comments)
        ? item.comments
        : Array.isArray(item.comment_samples)
          ? item.comment_samples
          : Array.isArray(item.commentSamples)
            ? item.commentSamples
            : Array.isArray(item.visibleComments)
              ? item.visibleComments
              : [];
      const title = item.title || item.note_title || item.noteTitle || item.name || item.content_title || item.contentTitle || item.display_title || item.desc_title || (noteId ? `笔记 ${String(noteId).slice(-6)}` : '未命名笔记');
      const cover = item.cover_url || item.coverUrl || item.imgUrl || item.imageUrl || item.image || item.image_url || item.cover || item.pic_url || item.picUrl || item.thumbnail || item.thumbnail_url || item.thumbnailUrl || '';
      const content = item.content || item.text || item.desc || item.description || item.note_content || item.note_text || item.body || item.caption || item.rich_text || item.richText || '';
      return {
        index,
        noteId,
        brand: item.brand || item.cooperation_brand || item.brandName || item.category || item.content_category || item.contentTag || item.note_type || '近期笔记',
        title,
        readCount: item.read_count ?? item.readCount ?? item.read ?? item.readNum ?? item.read_num ?? item.viewCount ?? item.view_count ?? item.third_read_user_num ?? '',
        likeCount: item.like_count ?? item.likeCount ?? item.likes ?? item.likeNum ?? item.like_num ?? '',
        saveCount: item.save_count ?? item.saveCount ?? item.saves ?? item.favNum ?? item.fav_num ?? item.collectNum ?? item.collect_num ?? '',
        commentCount: item.comment_count ?? item.commentCount ?? item.cmtNum ?? item.cmt_num ?? (Array.isArray(item.comments) ? item.comments.length : item.comments) ?? '',
        shareCount: item.share_count ?? item.shareCount ?? item.shares ?? item.shareNum ?? item.share_num ?? '',
        exposureCount: item.exposure_count ?? item.exposureCount ?? item.impression_count ?? item.impressionCount ?? item.impNum ?? item.imp_num ?? '',
        followCount: item.follow_count ?? item.followCount ?? item.followCnt ?? item.follow_cnt ?? '',
        publishedAt: item.published_at || item.publish_time || item.publishTime || item.createTime || item.date || item.time || '',
        promoted: Boolean(item.has_promoted_traffic || item.promoted || item.isAdvertise),
        crossDomain: Boolean(item.cross_domain || item.crossDomain || item.is_cross_domain),
        noteType: item.note_type || item.type || item.media_type || (item.video_url || item.videoUrl ? '视频笔记' : '图文笔记'),
        contentCategory: item.content_category || item.contentCategory || item.contentTag || item.category || item.brand || '全部类目',
        coverUrl: cover,
        link: item.url || item.note_url || item.noteUrl || item.noteLink || item.link || item.source_url || item.sourceUrl || item.case_section_url || '',
        content,
        summary: item.summary || item.note_summary || item.excerpt || '',
        description: item.description || item.note_description || '',
        commentSummary: item.comment_summary || item.commentSummary || '',
        comments: rawComments,
        topics: Array.isArray(item.topics) ? item.topics : Array.isArray(item.tags) ? item.tags : Array.isArray(item.feature_tags) ? item.feature_tags : Array.isArray(item.featureTags) ? item.featureTags : [],
        industryTags: Array.isArray(item.industry_tags) ? item.industry_tags : [],
        featureTags: Array.isArray(item.feature_tags) ? item.feature_tags : Array.isArray(item.featureTags) ? item.featureTags : [],
        trafficComparison: item.traffic_comparison || item.trafficComparison || '',
        readVsMedian: item.read_vs_median ?? item.readVsMedian ?? null,
        interactionVsMedian: item.interaction_vs_median ?? item.interactionVsMedian ?? null,
        hasClearMedianContrast: Boolean(item.has_clear_median_contrast || item.hasClearMedianContrast),
        trafficMedianReference: item.traffic_median_reference || item.trafficMedianReference || null,
        source: item.source || 'detail_payload',
      };
    })
    .filter(Boolean)
    .filter(item => (item.title && item.title !== '未命名笔记') || item.coverUrl || item.noteId)
    .filter((item) => {
      const key = item.noteId || item.link || `${item.brand}|${item.title}|${item.publishedAt}|${item.coverUrl}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

  return cases.slice(0, 12);
}

function noteTextBlob(note = {}) {
  return `${note.title || ''} ${note.content || ''} ${note.brand || ''} ${note.contentCategory || ''}`;
}

function contentThemeFor(text) {
  const themes = [];
  if (/学习|作业|答疑|效率|自主|知识|课程|教辅|方法/.test(text)) themes.push('学习工具/学习方法');
  if (/升学|小升初|初中|高中|中考|高考|备考|规划/.test(text)) themes.push('升学规划');
  if (/陪读|家长|妈妈|爸爸|亲子|家庭|孩子/.test(text)) themes.push('家庭教育');
  if (/测评|对比|开箱|体验|好物|工具/.test(text)) themes.push('测评种草');
  if (/焦虑|崩溃|情绪|沟通|习惯|拖拉|磨蹭/.test(text)) themes.push('家长痛点/情绪共鸣');
  return uniqueCompactItems(themes, 3);
}

function contentSceneFor(text) {
  const scenes = [];
  if (/作业|写题|答疑|错题|练习/.test(text)) scenes.push('家庭作业');
  if (/备考|考试|冲刺|复习/.test(text)) scenes.push('备考冲刺');
  if (/陪读|辅导|家长/.test(text)) scenes.push('家长陪读');
  if (/开箱|测评|体验|使用|对比/.test(text)) scenes.push('工具体验');
  if (/课堂|学校|老师|同学/.test(text)) scenes.push('课堂学习');
  return uniqueCompactItems(scenes, 3);
}

function expressionStyleFor(text) {
  const styles = [];
  if (/为什么|怎么办|方法|解决|攻略|技巧|清单/.test(text)) styles.push('痛点解决');
  if (/对比|测评|横评|实测|体验/.test(text)) styles.push('测评对比');
  if (/我家|我娃|孩子|真实|终于|以前|现在/.test(text)) styles.push('故事叙事');
  if (/避坑|不要|建议|收藏|干货/.test(text)) styles.push('避坑干货');
  return uniqueCompactItems(styles, 3);
}

function noteNumber(value) {
  const number = parseCountValue(value);
  return Number.isFinite(Number(number)) ? Number(number) : 0;
}

export function getCreatorNoteAnalysis(creator, noteCases = getCreatorRealNoteCases(creator)) {
  return noteCases.slice(0, 5).map(note => {
    const text = noteTextBlob(note);
    const themes = contentThemeFor(text);
    const scenes = contentSceneFor(text);
    const styles = expressionStyleFor(text);
    const read = noteNumber(note.readCount);
    const interactions = noteNumber(note.likeCount) + noteNumber(note.saveCount) + noteNumber(note.commentCount) + noteNumber(note.shareCount);
    const themeScore = Math.min(20, themes.length * 8);
    const sceneScore = Math.min(20, scenes.length * 9);
    const styleScore = Math.min(15, styles.length * 6);
    const seedingScore = /工具|测评|体验|方法|解决|效率|答疑|好物/.test(text) ? 18 : /学习|家庭|孩子|作业/.test(text) ? 13 : 8;
    const interactionScore = interactions >= 1000 || read >= 10000 ? 15 : interactions >= 200 || read >= 3000 ? 11 : interactions > 0 || read > 0 ? 7 : 4;
    const riskPenalty = /娱乐|美妆|护肤|穿搭|低幼|辅食|孕期/.test(text) ? 6 : 0;
    const noteValueScore = Math.max(35, Math.min(100, Math.round(themeScore + sceneScore + styleScore + seedingScore + interactionScore + 10 - riskPenalty)));
    return {
      noteTitle: note.title,
      noteUrl: note.link,
      contentType: styles[0] || '内容样本',
      mainTopic: themes[0] || note.contentCategory || '待识别主题',
      scene: scenes[0] || '场景待补',
      expressionStyle: styles.join(' + ') || '表达结构待补',
      audienceValue: /家长|孩子|作业|学习|升学|拖拉|焦虑/.test(text) ? '能承接家长学习/陪伴痛点' : '受众价值待结合正文确认',
      brandFit: /工具|测评|体验|方法|效率|答疑/.test(text) ? '适合自然植入学习工具' : '需要补充正文判断品牌植入方式',
      interactionSignal: interactions || read ? `阅读${formatCountMetric(read || note.readCount)} / 互动${formatCountMetric(interactions)}` : '互动数据待补',
      evidence: uniqueCompactItems([...themes, ...scenes, ...styles], 5),
      risks: riskPenalty ? ['内容方向可能偏离项目场景'] : [],
      noteValueScore,
    };
  });
}

export function getCreatorContentValueModel(creator, noteCases = getCreatorRealNoteCases(creator)) {
  const tags = getCreatorTagGroups(creator);
  const intro = getCreatorIntro(creator);
  const text = `${creator.name || ''} ${intro} ${tags.persona.join(' ')} ${tags.content.join(' ')} ${noteCases.map(noteTextBlob).join(' ')}`;
  const noteAnalysis = getCreatorNoteAnalysis(creator, noteCases);
  const contentStrengths = uniqueCompactItems([
    ...contentThemeFor(text),
    ...contentSceneFor(text),
    ...expressionStyleFor(text),
    ...tags.content,
  ], 5);
  const avgNoteScore = noteAnalysis.length
    ? Math.round(noteAnalysis.reduce((sum, note) => sum + note.noteValueScore, 0) / noteAnalysis.length)
    : 0;
  const baseContent = Number(creator.scores?.content || 0);
  const persona = Number(creator.scores?.persona || 0);
  const contentValueScore = Math.max(
    45,
    Math.min(100, Math.round((avgNoteScore || baseContent || 65) * 0.55 + (baseContent || 65) * 0.25 + (persona || 65) * 0.2))
  );
  const hasDeepEvidence = noteCases.length >= 3 || /简介|详情/.test(intro);
  return {
    contentStrengths: contentStrengths.length ? contentStrengths : ['内容样本待补'],
    mainTopics: uniqueCompactItems(contentThemeFor(text), 4),
    topicDepth: noteCases.length >= 5 || contentStrengths.length >= 4 ? 'high' : noteCases.length >= 2 ? 'medium' : 'low',
    scenarioAuthenticity: /我家|我娃|孩子|家长|陪读|真实|作业|备考/.test(text) ? 'high' : noteCases.length ? 'medium' : 'low',
    storytellingAbility: /我|孩子|终于|以前|现在|经历|方法|避坑/.test(text) ? 'high' : noteCases.length ? 'medium' : 'low',
    productSeedingFit: /工具|测评|体验|方法|解决|效率|答疑|好物/.test(text) ? 'high' : /学习|作业|家庭|孩子/.test(text) ? 'medium' : 'low',
    audienceResonance: /家长|孩子|拖拉|焦虑|作业|升学|陪读/.test(text) ? 'high' : 'medium',
    commercialContentRisk: /硬广|无关|娱乐|美妆|护肤|穿搭|低幼|孕期/.test(text) ? 'medium' : 'low',
    contentValueScore,
    bestContentAngles: uniqueCompactItems([
      /拖拉|作业|效率/.test(text) ? '孩子作业效率和学习习惯痛点' : '',
      /陪读|家长|焦虑/.test(text) ? '家长陪读压力下的工具辅助' : '',
      /测评|体验|对比|工具/.test(text) ? '学习工具体验测评和前后对比' : '',
      /升学|备考|初中|高中|小升初/.test(text) ? '升学备考和学习规划场景' : '',
      contentStrengths[0] ? `${contentStrengths[0]}方向延展` : '',
    ], 4),
    weakContentAngles: uniqueCompactItems([
      '纯功能硬讲解',
      hasDeepEvidence ? '' : '无正文证据的泛标签种草',
      /低幼|孕期|辅食/.test(text) ? '低幼母婴场景' : '',
    ], 4),
    evidenceCompleteness: Math.min(1, Math.round(((noteCases.length ? 0.35 : 0) + (intro && intro !== '暂无详情页个人简介' ? 0.2 : 0) + (tags.persona.length ? 0.15 : 0) + (tags.content.length ? 0.15 : 0) + (baseContent ? 0.15 : 0)) * 100) / 100),
    noteAnalysis,
  };
}

export function getCreatorLightProfile(creator, project) {
  const noteCases = getCreatorRealNoteCases(creator);
  const contentModel = getCreatorContentValueModel(creator, noteCases);
  const tier = getScoreTier(Number(creator.baseScore || 0));
  const recommendation = getCreatorAdRecommendation(creator, noteCases);
  const risks = uniqueCompactItems([...(creator.risk || []), ...recommendation.weaknesses], 3);
  const strengths = uniqueCompactItems([
    ...contentModel.contentStrengths,
    ...recommendation.strengths,
  ], 3);
  const action = getCreatorRecommendation(creator, getPoolStage(creator));
  return {
    decision: creator.raw?.recommend_level || creator.raw?.recommendLevel || (Number(creator.baseScore || 0) >= 90 ? '强推荐' : Number(creator.baseScore || 0) >= 80 ? '推荐' : Number(creator.baseScore || 0) >= 70 ? '备选' : '暂缓'),
    totalScore: Number(creator.baseScore || 0),
    tier: tier.label,
    contentValueScore: contentModel.contentValueScore,
    dataLayer: Number(creator.scores?.engagement || 0) >= 85 ? 'A' : Number(creator.scores?.engagement || 0) >= 70 ? 'B' : '待补',
    mainStrengths: strengths.length ? strengths : ['待补充详情后判断优势'],
    mainRisks: risks.length ? risks : ['暂无明显硬风险'],
    nextAction: action,
    evidenceCompleteness: contentModel.evidenceCompleteness,
    contentTags: contentModel.contentStrengths,
    hasDeepProfile: noteCases.length >= 3,
  };
}

export function getCreatorModelProfile(creator, project) {
  const noteCases = getCreatorRealNoteCases(creator);
  const lightProfile = getCreatorLightProfile(creator, project);
  const contentValueModel = getCreatorContentValueModel(creator, noteCases);
  const tags = getCreatorTagGroups(creator);
  const match = getCreatorMatchProfile(creator, project);
  const recommendation = getCreatorAdRecommendation(creator, noteCases);
  const evidenceChain = [
    {
      claim: '达人内容价值判断',
      confidence: contentValueModel.evidenceCompleteness >= 0.7 ? 'high' : contentValueModel.evidenceCompleteness >= 0.45 ? 'medium' : 'low',
      evidence: contentValueModel.noteAnalysis.slice(0, 3).map(note => ({ source: 'note_analysis', field: '代表笔记', value: note.noteTitle })),
      missingEvidence: noteCases.length ? [] : ['近期笔记标题/正文'],
    },
    {
      claim: '人设与项目匹配',
      confidence: tags.persona.length || match.matchedSignals.length ? 'medium' : 'low',
      evidence: [...tags.persona, ...match.matchedSignals].slice(0, 4).map(value => ({ source: 'profile', field: '人设/匹配信号', value })),
      missingEvidence: tags.persona.length ? [] : ['主页简介', '长期内容主题'],
    },
  ];
  return {
    lightProfile,
    identityModel: {
      positioning: tags.persona[0] || getCreatorCategory(creator),
      persona: tags.persona,
      personaConfidence: tags.persona.length >= 2 ? 'high' : tags.persona.length ? 'medium' : 'low',
      evidence: uniqueCompactItems([getCreatorIntro(creator), ...tags.persona].filter(item => item && item !== '暂无详情页个人简介'), 4),
      uncertainItems: tags.persona.length ? [] : ['达人核心人设待补'],
    },
    audienceModel: {
      followerTier: creator.followers || '待补',
      parentAudienceFit: /35\+|妈妈|家长|家庭/.test(`${tags.persona.join(' ')} ${tags.metric.join(' ')}`) ? 'high' : 'medium',
      ageFit: pickCreatorValue(creator, ['fans35PlusRatio', 'fans_35_plus_ratio']) ? '粉丝年龄已采集' : '粉丝年龄待补',
      geoFit: getCreatorLocation(creator),
      risks: (creator.risk || []).filter(item => /粉丝|35|地域/.test(item)),
    },
    contentValueModel,
    performanceModel: {
      dataLayer: lightProfile.dataLayer,
      trafficStability: pickCreatorValue(creator, ['traffic_stability', '近30天流量稳定性'], '待补'),
      benchmarkConclusion: recommendation.noteSummary,
      detailCollectionPriority: creator.detailCollectionPriority || lightProfile.nextAction,
    },
    commercialModel: {
      quoteFit: (creator.risk || []).some(item => /报价/.test(item)) ? 'risk' : 'pass',
      quoteEfficiency: recommendation.verdict,
      valueLevel: contentValueModel.contentValueScore >= 85 ? 'high' : contentValueModel.contentValueScore >= 70 ? 'medium' : 'low',
      negotiationSuggestion: recommendation.verdict.includes('偏高') ? '优先谈价或补充效果证据' : '报价可进入后续沟通，重点谈内容质量和权益',
    },
    projectFitModel: {
      fitLevel: match.tier,
      matchedPreferences: match.matchedSignals,
      negativeHits: match.riskSignals,
      unverifiedItems: lightProfile.evidenceCompleteness < 0.7 ? ['内容正文或人设证据仍需补充'] : [],
      fitReason: match.reason,
    },
    riskModel: {
      riskLevel: match.riskSignals.length >= 3 ? 'high' : match.riskSignals.length ? 'medium' : 'low',
      risks: match.riskSignals,
      mitigation: match.riskSignals.length ? '补采详情并人工复核关键风险' : '可按当前证据推进',
    },
    evidenceChain,
    actionRecommendation: {
      decision: lightProfile.decision,
      nextAction: lightProfile.nextAction,
      reviewFocus: uniqueCompactItems(['孩子阶段', '教育内容浓度', '合作笔记表现', ...match.riskSignals], 4),
      cooperationAngle: contentValueModel.bestContentAngles[0] || '围绕达人稳定内容场景设计合作',
      avoidAngle: contentValueModel.weakContentAngles[0] || '避免泛化硬广',
    },
  };
}

export function getProjectScoringCriteria(project) {
  const plan = normalizeWorkbenchPlan(project?.screeningPlan || {});
  const hardFilters = [
    ...(plan.scoringHardFilters || []),
    ...(plan.hardFilters || []),
    ...((plan.scoringCriteria && Array.isArray(plan.scoringCriteria.hardFilters)) ? plan.scoringCriteria.hardFilters : []),
  ];
  return {
    hardFilters: uniqueCompactItems(hardFilters.map(item => hardFilterLabel(item)), 8),
    weights: plan.scoringWeights || plan.weights || plan.scoringCriteria?.weights || {},
  };
}

export function getCreatorMatchProfile(creator, project) {
  const score = Math.max(0, Math.min(100, Math.round(Number(creator.baseScore || creator.finalScore || 0))));
  const scores = creator.scores || {};
  const persona = Number(scores.persona ?? score);
  const content = Number(scores.content ?? score);
  const cpe = Number(scores.cpe ?? score);
  const budget = Number(scores.budget ?? score);
  const noteCases = getCreatorNoteCases(creator);
  const criteria = getProjectScoringCriteria(project);
  const matchedSignals = [];
  const riskSignals = [];
  const text = `${creator.name || ''} ${getCreatorIntro(creator)} ${getCreatorTags(creator).join(' ')} ${creator.aiReason || ''}`;
  const deepReason = getCreatorDeepAuditReason(creator, noteCases);

  if (/女|妈妈|宝妈|陪读|亲子|家庭/.test(text)) matchedSignals.push('人设/家庭场景命中');
  if (/教育|学习|老师|教师|作业|小升初|初中|高中/.test(text)) matchedSignals.push('教育学习内容命中');
  if (noteCases.length >= 3) matchedSignals.push(`${noteCases.length}条笔记证据`);
  if (creator.informationCompletenessLabel && creator.informationCompletenessLabel !== '待补') matchedSignals.push(`资料完整度${creator.informationCompletenessLabel}`);
  if (Number.isFinite(cpe) && cpe >= 80) matchedSignals.push('互动成本表现较好');
  if (Number.isFinite(budget) && budget >= 80) matchedSignals.push('报价预算匹配');
  (creator.risk || []).forEach(item => riskSignals.push(item));
  if (!noteCases.length) riskSignals.push('缺少合作笔记证据');

  const noteEvidenceBonus = Math.min(noteCases.length * 2, 8);
  const matchScore = Math.round(Math.min(100, score * 0.45 + persona * 0.22 + content * 0.2 + cpe * 0.08 + noteEvidenceBonus));
  const tier = matchScore >= 85 ? '强匹配' : matchScore >= 70 ? '较匹配' : matchScore >= 55 ? '需复核' : '不匹配';
  return {
    matchScore,
    tier,
    noteCases,
    matchedSignals: uniqueCompactItems(matchedSignals, 5),
    riskSignals: uniqueCompactItems(riskSignals, 4),
    reason: deepReason.summary,
    reasonSections: deepReason.sections,
    criteria,
  };
}

export function getMetricText(value, label, formatter = value => value) {
  if (value === undefined || value === null || value === '') return '';
  return `${label}${formatter(value)}`;
}

function getReasonMetricValue(reason, label) {
  const match = String(reason || '').match(new RegExp(`${label}\\s*[：:]?\\s*(?:¥|￥)?\\s*(\\d+(?:\\.\\d+)?)`, 'i'));
  return match ? match[1] : '';
}

function getNumericMetric(creator, keys, reasonLabel = '') {
  const explicit = pickCreatorValue(creator, keys);
  if (explicit !== undefined && explicit !== null && explicit !== '') return explicit;
  return reasonLabel ? getReasonMetricValue(creator.aiReason || creator.reason, reasonLabel) : '';
}

function formatCostMetric(value) {
  if (value === undefined || value === null || value === '') return '待补';
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  return number >= 10 ? number.toFixed(1).replace(/\.0$/, '') : number.toFixed(2).replace(/0$/, '').replace(/\.0$/, '');
}

function formatCountMetric(value) {
  if (value === undefined || value === null || value === '') return '待补';
  return compactNumber(parseCountValue(value) || value);
}

function metricNumber(value) {
  if (value === undefined || value === null || value === '') return null;
  const number = parseCountValue(value);
  return Number.isFinite(number) && number > 0 ? number : null;
}

function medianValue(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function averageValue(values) {
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function getCreatorMetricNumber(creator, keys) {
  return metricNumber(pickCreatorValue(creator, keys));
}

function summarizeNoteAverages(creator, noteCases = []) {
  const readValues = noteCases.map(note => metricNumber(note.readCount)).filter(value => value !== null);
  const interactionValues = noteCases
    .map(note => metricNumber(note.likeCount) + metricNumber(note.saveCount) + metricNumber(note.commentCount))
    .filter(value => Number.isFinite(value) && value > 0);
  const readMedian = medianValue(readValues) ?? getCreatorMetricNumber(creator, ['cooperation_read_median', 'daily_read_median', 'image_daily_read_median', 'video_daily_read_median', '合作阅读中位数', '阅读中位数（合作）']);
  const interactionMedian = medianValue(interactionValues) ?? getCreatorMetricNumber(creator, ['cooperation_interaction_median', 'daily_interaction_median', 'image_daily_interaction_median', 'video_daily_interaction_median', '合作互动中位数', '互动中位数（合作）']);
  const readAverage = averageValue(readValues) ?? readMedian;
  const interactionAverage = averageValue(interactionValues) ?? interactionMedian;
  return {
    sampleCount: noteCases.length,
    metrics: [
      { label: '平均阅读', value: formatCountMetric(readAverage), rawValue: readAverage },
      { label: '阅读中位', value: formatCountMetric(readMedian), rawValue: readMedian },
      { label: '平均互动', value: formatCountMetric(interactionAverage), rawValue: interactionAverage },
      { label: '互动中位', value: formatCountMetric(interactionMedian), rawValue: interactionMedian },
    ],
  };
}

function getCostTone(label, value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 'muted';
  if (label === '互动单价') return number <= 10 ? 'good' : number <= 20 ? 'ok' : 'bad';
  if (label === '阅读单价') return number <= 2 ? 'good' : number <= 3 ? 'ok' : 'bad';
  if (label === 'CPM') return number <= 80 ? 'good' : number <= 150 ? 'ok' : 'bad';
  return 'muted';
}

function costToneText(tone) {
  return { good: '优秀', ok: '达标', bad: '偏高', muted: '待补' }[tone] || '待补';
}

function compactSentence(value, maxLength = 48) {
  const text = String(value || '')
    .replace(/^【[^】]+】/, '')
    .replace(/^(效率判断|近期\/合作数据|高分依据|加成|风险\/动作|数据表现|人设匹配|内容贴合)[：:]/, '')
    .trim();
  if (!text) return '';
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

function reasonClauses(reason) {
  return String(reason || '')
    .replace(/^【(?:大模型分析|通用初筛)】/, '')
    .split(/[；;]/)
    .map(item => compactSentence(item))
    .filter(Boolean);
}

function buildMetricStrengths(creator) {
  const scores = creator.scores || {};
  const items = [];
  if (Number(scores.budget) >= 85) items.push('预算与报价匹配度较好');
  if (Number(scores.cpe) >= 85) items.push('CPM/CPC/CPE 成本效率较好');
  if (Number(scores.engagement) >= 85) items.push('互动质量和流量基础较好');
  if (Number(scores.persona) >= 85) items.push('达人身份与项目人群匹配');
  if (Number(scores.content) >= 85) items.push('内容风格贴合项目场景');
  return items;
}

function buildMetricWeaknesses(creator) {
  const scores = creator.scores || {};
  const items = [];
  if (Number(scores.budget) > 0 && Number(scores.budget) < 75) items.push('报价或预算效率需要复核');
  if (Number(scores.cpe) > 0 && Number(scores.cpe) < 75) items.push('CPM/CPC/CPE 成本效率偏弱');
  if (Number(scores.engagement) > 0 && Number(scores.engagement) < 75) items.push('近期互动或阅读表现不够稳');
  if (Number(scores.persona) > 0 && Number(scores.persona) < 75) items.push('达人身份与目标人群匹配度不足');
  if (Number(scores.content) > 0 && Number(scores.content) < 75) items.push('内容垂直度或场景贴合度不足');
  return items;
}

function standardScore(creator, standard) {
  const scores = creator.scores || {};
  const values = (SCORING_STANDARD_SCORE_KEYS[standard] || [])
    .map(key => Number(scores[key]))
    .filter(value => Number.isFinite(value) && value > 0);
  if (!values.length) return null;
  return Math.round(values.reduce((sum, value) => sum + value, 0) / values.length);
}

function getPrimaryScoringStandard(creator) {
  const riskStandard = (creator.risk || []).find(item => Object.values(SCORING_RISK_STANDARDS).includes(item));
  if (riskStandard) return riskStandard;
  const standards = Object.values(SCORING_RISK_STANDARDS)
    .map(standard => ({ standard, score: standardScore(creator, standard) }))
    .filter(item => item.score !== null);
  if (!standards.length) return SCORING_RISK_STANDARDS.direction;
  const weak = standards.filter(item => item.score < 85).sort((a, b) => a.score - b.score)[0];
  if (weak) return weak.standard;
  return standards.sort((a, b) => b.score - a.score)[0].standard;
}

function scoringStandardEvidence(creator, standard, clauses = []) {
  const score = standardScore(creator, standard);
  const clause = clauses.find(item => {
    if (standard === SCORING_RISK_STANDARDS.audience) return /人群|粉丝|35|画像|家长|妈妈|父母/.test(item);
    if (standard === SCORING_RISK_STANDARDS.traffic) return /阅读|互动|曝光|流量|T级|搜推/.test(item);
    if (standard === SCORING_RISK_STANDARDS.efficiency) return /成本|报价|预算|CPC|CPE|CPM|单价/.test(item);
    if (standard === SCORING_RISK_STANDARDS.direction) return /内容|人设|标签|类目|场景|笔记|Brief/.test(item);
    return /执行|蒲公英|链接|完整|回复|采集|资料/.test(item);
  });
  if (clause) return clause;
  if (score !== null) {
    if (score >= 85) return `${standard}得分 ${score}，可作为当前主要通过依据。`;
    if (score >= 75) return `${standard}得分 ${score}，建议结合详情页证据复核。`;
    return `${standard}得分 ${score}，是当前优先处理的短板。`;
  }
  return `${standard}证据不足，需补充详情页和笔记样本后复核。`;
}

function buildNoteContentWeaknesses(noteCases = [], productProfile = DEFAULT_PRODUCT_PROFILE) {
  if (!noteCases.length) return [`缺少可核验笔记标题/正文，暂不能判断是否适合${productProfile.name}呈现`];
  const text = noteCases.map(note => noteTextBlob(note)).join(' ');
  const types = uniqueCompactItems(noteCases.map(note => note.noteType || ''), 4);
  const items = [];
  if (!productProfile.keywords.some(keyword => text.includes(keyword))) {
    items.push(`笔记主题未明显承接${productProfile.name}的${productProfile.scenarios.slice(0, 2).join('、')}`);
  }
  if (!/学习|作业|答疑|教辅|方法|规划|考试|升学|阅读|绘本|英语|单词|发音|听力/.test(text)) {
    items.push('笔记主题与学习工具使用场景关联不足');
  }
  if (!/孩子|家长|妈妈|爸爸|家庭|陪读|亲子|学生/.test(text)) {
    items.push('呈现视角缺少真实家庭/家长使用场景');
  }
  if (!productProfile.presentation.some(keyword => text.includes(keyword.replace(/视角|过程|反馈|演示|对比/g, '')))) {
    items.push(`呈现方式需补看是否有${productProfile.presentation.slice(0, 3).join('、')}`);
  }
  if (/福利|秒杀|低价|冲|必买|闭眼入|全网/.test(text)) {
    items.push('部分标题或表达偏促销，需控制硬广感');
  }
  if (noteCases.every(note => String(note.content || note.summary || note.description || '').trim().length < 24)) {
    items.push('笔记正文信息偏少，卖点承接和使用过程待确认');
  }
  if (types.length === 1 && noteCases.length >= 3) {
    items.push(`呈现形式集中在${types[0]}，可补看是否有过程型/测评型内容`);
  }
  return uniqueCompactItems(items, 3);
}

export function getCreatorAdRecommendation(creator, noteCases = [], project = {}) {
  const rawReason = String(creator.aiReason || creator.reason || '').replace(/^【(?:大模型分析|通用初筛)】/, '').trim();
  const productProfile = getProjectProductProfile(project);
  const cpe = getNumericMetric(creator, ['effectiveCpe', 'effective_cpe', 'naturalCpe', 'natural_cpe', '合作笔记自然CPE', 'image_interaction_unit_price', 'video_interaction_unit_price'], 'CPE');
  const cpc = getNumericMetric(creator, ['effectiveCpc', 'effective_cpc', 'natural_cpc', '合作笔记自然CPC', 'image_read_unit_price', 'video_read_unit_price'], 'CPC');
  const cpm = getNumericMetric(creator, ['image_cpm', 'video_cpm', '预估CPM', '图文预估CPM价格', '视频预估CPM价格'], 'CPM');
  const costMetrics = [
    { label: '互动单价', value: formatCostMetric(cpe), tone: getCostTone('互动单价', cpe) },
    { label: 'CPM', value: formatCostMetric(cpm), tone: getCostTone('CPM', cpm) },
    { label: '阅读单价', value: formatCostMetric(cpc), tone: getCostTone('阅读单价', cpc) },
  ];
  const knownTones = costMetrics.map(item => item.tone).filter(tone => tone !== 'muted');
  const costVerdict = knownTones.includes('bad') ? '成本偏高' : knownTones.includes('good') ? '成本优秀' : knownTones.includes('ok') ? '成本达标' : '成本待补';
  const noteMetricProfile = summarizeNoteAverages(creator, noteCases);
  const noteMetrics = noteMetricProfile.metrics;

  const clauses = reasonClauses(rawReason);
  const positiveClauses = clauses.filter(item => /达标|低于|匹配|高分|加成|专业|垂直|强|优质|精准|讨论度|真实|性价比|优势/.test(item) && !/未|不足|偏高|风险|缺少|待核/.test(item));
  const negativeClauses = clauses.filter(item => /未|不足|偏高|风险|缺少|待核|不匹配|暂缓|弱|下降/.test(item));
  const primaryStandard = getPrimaryScoringStandard(creator);
  const standardEvidence = scoringStandardEvidence(creator, primaryStandard, clauses);
  const noteContentWeaknesses = buildNoteContentWeaknesses(noteCases, productProfile);
  const tagGroups = getCreatorTagGroups(creator);
  const tagAdvantage = uniqueCompactItems([...tagGroups.persona, ...tagGroups.content], 4);
  const strengths = uniqueCompactItems([
    ...buildMetricStrengths(creator),
    tagAdvantage.length ? `人设/内容标签：${tagAdvantage.join('、')}` : '',
    ...positiveClauses,
  ], 4);
  const weaknesses = uniqueCompactItems([
    ...noteContentWeaknesses,
    ...(creator.risk || []),
    ...buildMetricWeaknesses(creator),
    ...negativeClauses,
  ], 4);
  const noteTitles = noteCases.length
    ? noteCases.slice(0, 2).map(note => note.title).join('、')
    : '';
  const action = getCreatorRecommendation(creator, getPoolStage(creator));
  const noteSummary = noteTitles
    ? `基于 ${noteCases.length} 条笔记样本计算平均数/中位数；重点复核 ${noteTitles} 是否能自然呈现${productProfile.name}。`
    : `缺少可核验合作笔记样本，需补看是否能自然呈现${productProfile.name}。`;
  const searchReviewStatus = pickCreatorValue(creator, ['searchReviewStatus', 'search_recommend_review_status']) || '待复核';
  const searchReviewNote = pickCreatorValue(creator, ['searchReviewNote', 'search_recommend_review_note']) || '需人工在蒲公英页面复核搜索+推荐占比';
  const manualReviewItems = [
    `搜索+推荐占比：${searchReviewStatus}`,
    searchReviewStatus !== '已复核' ? searchReviewNote : '',
  ].filter(Boolean);

  return {
    verdict: primaryStandard,
    standard: primaryStandard,
    standardEvidence,
    productName: productProfile.name,
    costVerdict,
    costMetrics: costMetrics.map(item => ({ ...item, status: costToneText(item.tone) })),
    noteMetrics,
    noteSummary,
    strengths: strengths.length ? strengths : ['暂未提取到明确优势，建议完善详情页和笔记证据。'],
    weaknesses: weaknesses.length ? weaknesses : ['暂无明显硬风险，仍需结合内容样本复核。'],
    manualReviewItems,
    action,
    summary: `${primaryStandard}：${standardEvidence} 重点看${productProfile.name}场景。`,
  };
}

export function getCreatorDeepAuditReason(creator, noteCases = []) {
  const rawReason = String(creator.aiReason || creator.reason || '').replace(/^【(?:大模型分析|通用初筛)】/, '').trim();
  const recommendation = getCreatorAdRecommendation(creator, noteCases);
  const tags = getCreatorTagGroups(creator);
  const intro = getCreatorIntro(creator);
  const metrics = uniqueCompactItems([
    getMetricText(creator.followers, '粉丝 ', value => value),
    getMetricText(creator.quote, '报价 ', value => value),
    getMetricText(pickCreatorValue(creator, ['effectiveCpe', 'effective_cpe', 'naturalCpe', 'natural_cpe']), '互动单价 ', value => value),
    getMetricText(pickCreatorValue(creator, ['effectiveCpc', 'effective_cpc', 'natural_cpc']), '阅读单价 ', value => value),
    getMetricText(pickCreatorValue(creator, ['video_completion_rate']), '视频完播 ', formatPercentValue),
    getMetricText(pickCreatorValue(creator, ['searchReviewStatus', 'search_recommend_review_status']), '搜推 ', value => value),
  ], 6);
  const noteText = noteCases.length
    ? `${noteCases.slice(0, 2).map(note => note.title).join('、')} 等 ${noteCases.length} 条内容可作样本`
    : '暂无可核验的视频/笔记案例，需要详情页与内容样本证据';
  const risks = uniqueCompactItems([...(creator.risk || [])], 4);
  const action = getCreatorRecommendation(creator, getPoolStage(creator));
  const sections = [
    { title: '投流效果', text: recommendation.costMetrics.map(item => `${item.label} ${item.value}（${item.status}）`).join(' / ') || (metrics.length ? metrics.join(' / ') : '关键投放数据待补，暂不能只凭基础分判断效率。') },
    { title: '合作笔记数据', text: `${recommendation.noteMetrics.map(item => `${item.label} ${item.value}`).join(' / ')}；${recommendation.noteSummary || noteText}` },
    { title: '达人优势', text: recommendation.strengths.join('；') || `${[...tags.persona, ...tags.content].slice(0, 5).join('、') || '人设标签待补'}；简介：${intro}` },
    { title: '短板/风险', text: recommendation.weaknesses.join('；') || (risks.length ? risks.join('、') : '暂无明显硬风险') },
    { title: '推进建议', text: action },
  ];
  return {
    summary: rawReason || sections.map(item => `${item.title}：${item.text}`).join('；'),
    sections,
  };
}

export function parseAuditReasonSections(reason) {
  if (!reason) return [];
  const titles = ['数据表现', '人设匹配', '内容贴合', '风险/动作', '风险动作', '内容适配', '视频/笔记'];
  const sections = [];
  titles.forEach((title, index) => {
    const escaped = title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const nextTitles = titles.slice(index + 1).map(item => item.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
    const regex = nextTitles
      ? new RegExp(`(?:【${escaped}】|${escaped}[：:])([\\s\\S]*?)(?=【(?:${nextTitles})】|(?:${nextTitles})[：:]|$)`)
      : new RegExp(`(?:【${escaped}】|${escaped}[：:])([\\s\\S]*)`);
    const match = reason.match(regex);
    if (match?.[1]?.trim()) {
      sections.push({ title: title === '风险动作' ? '风险/动作' : title, text: match[1].trim().replace(/[；;]$/, '') });
    }
  });
  return uniqueCompactItems(sections.map(item => `${item.title}|${item.text}`), 4).map(item => {
    const [title, ...rest] = item.split('|');
    return { title, text: rest.join('|') };
  });
}

export function getCreatorRecommendation(creator, stage) {
  const score = Number(creator.baseScore || 0);
  if ((creator.risk || []).some(item => /无蒲公英|限流|报价偏高/.test(item))) return '先核风险';
  if (stage === '已合作跟进中') return '跟进数据';
  if (stage === '待建联达人') return score >= 80 ? '优先建联' : '补充判断';
  if (stage === '合格达人待合作') return score >= 90 ? '优先排期' : '排期沟通';
  if (score >= 100) return '强匹配';
  if (score >= 90) return '优先推进';
  if (score >= 80) return '高潜备选';
  return '暂缓观察';
}

export function getCreatorFollowupInfo(creator, stage) {
  const owner = pickCreatorValue(creator, ['owner', '负责人', 'reviewer'], creator.reviewer || '待分配');
  const rawStatus = pickCreatorValue(creator, ['contact_status', '建联状态', 'portfolio_role'], creator.raw?.portfolio_role || '');
  const statusByStage = {
    '已合作跟进中': '已确认合作',
    '合格达人待合作': '待排期/商务推进',
    '待建联达人': '待建联',
    '观察暂缓': '暂缓观察',
  };
  const lastRaw = pickCreatorValue(creator, ['last_contacted_at', '最近跟进时间', 'reviewedAt', 'updatedAt', 'updated_at'], creator.reviewedAt || creator.updatedAt || creator.createdAt);
  const lastAt = lastRaw ? formatDateTime(lastRaw) : '待记录';
  return {
    owner,
    status: rawStatus || statusByStage[stage] || '待跟进',
    lastAt,
    note: pickCreatorValue(creator, ['note', '备注', 'reason'], creator.reason || ''),
  };
}

export function getCreatorTagGroups(creator) {
  const metricTags = getCreatorMetricChips(creator);
  const personaTags = splitCreatorTags(pickCreatorValue(creator, ['personaTags', 'persona_tags', '人设标签']));
  const contentTags = splitCreatorTags(pickCreatorValue(creator, ['categoryTags', 'category_tags', 'content_tags', '内容标签', '类目标签']));
  const riskTags = Array.isArray(creator.risk) ? creator.risk : splitCreatorTags(pickCreatorValue(creator, ['risk_tags', 'risk', '风险标签']));
  const intro = getCreatorIntro(creator);
  const derivedPersona = [];
  const derivedContent = [];
  const category = getCreatorCategory(creator);
  const location = getCreatorLocation(creator);

  if (/老师|教师|教资|班主任/.test(intro + creator.name)) derivedPersona.push('教师人设');
  if (/妈妈|宝妈|陪读|亲子|家庭/.test(intro + creator.name)) derivedPersona.push('家庭教育');
  if (/小升初|初中|高中|升学|作业/.test(intro)) derivedContent.push('升学场景');
  if (/测评|开箱|好物|种草/.test(intro)) derivedContent.push('测评种草');

  return {
    persona: uniqueCompactItems([...personaTags, ...derivedPersona, location !== '其他' ? location : ''], 5),
    content: uniqueCompactItems([category !== '达人' ? category : '', ...contentTags, ...derivedContent], 5),
    metric: uniqueCompactItems(metricTags, 6),
    risk: uniqueCompactItems(riskTags, 4),
  };
}

export function getPoolStage(creator, index = 0) {
  if (creator.poolStage || creator.pool_stage) return creator.poolStage || creator.pool_stage;
  if (['待补数据', '待审核', '人工复核'].includes(creator.review)) return '筛选工作台';
  if (['已驳回', '默认淘汰'].includes(creator.review)) return '观察暂缓';
  if (creator.review === '已写回飞书') return '已合作跟进中';
  if (['已通过', '备选'].includes(creator.review)) return '合格达人待合作';
  if (creator.review === '已邀约') return '待建联达人';
  if (creator.review === '待建联') return '待建联达人';
  return '观察暂缓';
}

export function getCreatorUpdateLog(creator, index = 0) {
  const seed = Number(String(creator.id).replace(/\D/g, '').slice(-2)) || index + 3;
  const followerDelta = ((seed % 7) - 2) * 320;
  const interactionDelta = ((seed % 5) - 1) * 0.18;
  const quoteDelta = seed % 4 === 0 ? -500 : seed % 3 === 0 ? 800 : 0;
  return [
    {
      label: '近7天粉丝',
      value: followerDelta >= 0 ? `+${followerDelta.toLocaleString('zh-CN')}` : followerDelta.toLocaleString('zh-CN'),
      direction: followerDelta >= 0 ? 'up' : 'down',
    },
    {
      label: '互动率',
      value: `${interactionDelta >= 0 ? '+' : ''}${interactionDelta.toFixed(2)}%`,
      direction: interactionDelta >= 0 ? 'up' : 'down',
    },
    {
      label: '报价变动',
      value: quoteDelta === 0 ? '持平' : `${quoteDelta > 0 ? '+' : '-'}¥${Math.abs(quoteDelta).toLocaleString('zh-CN')}`,
      direction: quoteDelta <= 0 ? 'up' : 'down',
    },
  ];
}

export function getReviewVariant(review) {
  const map = { '已通过': 'green', '已写回飞书': 'green', '已邀约': 'blue', '已驳回': 'red', '备选': 'amber', '人工复核': 'blue', '默认淘汰': 'red', '待审核': 'default', '待确认': 'amber', '待补数据': 'default' };
  return map[review] || 'default';
}
