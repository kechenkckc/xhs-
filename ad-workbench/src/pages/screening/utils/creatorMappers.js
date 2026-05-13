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
    budget: normalizeDimensionScore(item.budget_score, 10),
    fans: normalizeDimensionScore(item.fans_score, 15),
    cpe: normalizeDimensionScore(item.cpe_score, 10),
    engagement: normalizeDimensionScore(item.traffic_score, 15),
    persona: normalizeDimensionScore(item.persona_score, 30),
    content: normalizeDimensionScore(item.content_score, 20),
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

export function mapBackendCreator(item) {
  const score = Math.round(Number(item.total_score || 0));
  const type = item.creator_type || (Number(item.followers_count || 0) >= 100000 ? 'KOL' : 'KOC');
  const risks = [];
  const rawPayload = getCreatorRawPayload({ raw: item });
  const collectionIssues = Array.isArray(rawPayload.collection_hard_filter_issues) ? rawPayload.collection_hard_filter_issues : [];
  collectionIssues.forEach(issue => {
    if (issue) risks.push(`条件不符：${issue}`);
  });
  if (item.hard_filter_passed === 0 || item.hard_filter_passed === false) risks.push('筛选条件待复核');
  if (!item.pgy_url || item.pgy_url === '待填') risks.push('无蒲公英');
  if (Number(item.quote_price || 0) >= 20000) risks.push('报价偏高');
  if (item.rate_limit_risk && !['无', '无明显'].includes(item.rate_limit_risk)) risks.push(item.rate_limit_risk);
  if (!risks.length && item.persona_tags) risks.push(item.persona_tags.split(/[\/,，]/)[0]);
  return {
    id: item.creator_id,
    name: item.nickname || item.creator_id,
    type,
    typeVariant: type === 'KOL' ? 'purple' : 'blue',
    followers: compactNumber(item.followers_count),
    followersNum: Number(item.followers_count || 0),
    quote: formatCurrency(item.quote_price),
    quoteNum: Number(item.quote_price || 0),
    baseScore: score || 0,
    baseOnlyScore: Math.round(Number(item.base_score || 0)),
    bonusScore: Math.round(Number(item.bonus_score || 0)),
    informationCompleteness: item.information_completeness,
    informationCompletenessLabel: formatCompleteness(item.information_completeness),
    initialTier: item.initial_tier || item.tier || '',
    detailCollectionPriority: item.detail_collection_priority || '',
    risk: risks,
    scores: deriveDimensionScores(item),
    aiReason: item.score_reason || '待补充蒲公英详情数据后生成完整评分说明。',
    review: item.status || '待补数据',
    reviewVariant: reviewVariantFromStatus(item.status),
    poolStage: item.pool_stage || null,
    finalScore: score || null,
    reason: item.review_reason || item.score_reason || '',
    reviewer: item.reviewer,
    reviewedAt: item.reviewed_at,
    createdAt: item.created_at || '',
    updatedAt: item.updated_at || '',
    collectedAt: item.collected_at || item.created_at || '',
    xiaohongshuId: item.xiaohongshu_id || '',
    ipCity: item.ip_city || '',
    personaTags: item.persona_tags || '',
    avatarUrl: item.avatar_url || '',
    topicPoint: item.topic_point || '',
    childGrade: item.child_grade || '',
    naturalCpe: item.natural_cpe,
    fans35PlusRatio: item.fans_35_plus_ratio,
    raw: item,
  };
}

export function getScoreColor(score) {
  if (score >= 100) return '#10B981';
  if (score >= 90) return '#3B82F6';
  if (score >= 80) return '#F59E0B';
  if (score >= 70) return '#D97706';
  return '#EF4444';
}

export function getScoreTier(score) {
  if (score >= 100) return { key: 'S', label: 'S档', variant: 'green', text: '必须补采', color: '#10B981' };
  if (score >= 90) return { key: 'A', label: 'A档', variant: 'blue', text: '优先补采', color: '#3B82F6' };
  if (score >= 80) return { key: 'B+', label: 'B+档', variant: 'amber', text: '高潜补采', color: '#F59E0B' };
  if (score >= 70) return { key: 'B', label: 'B档', variant: 'amber', text: '暂缓补采', color: '#D97706' };
  return { key: 'C', label: 'C档', variant: 'red', text: '不补采', color: '#EF4444' };
}

export function getCreatorDetailStatus(creator) {
  const completeness = creator.informationCompletenessLabel || formatCompleteness(creator.informationCompleteness);
  if (!getPgyUrl(creator)) return { label: '缺详情链接', variant: 'red' };
  if (completeness === '待补') return { label: '详情待补', variant: 'amber' };
  const number = Number(String(completeness).replace('%', ''));
  if (Number.isFinite(number) && number >= 80) return { label: `详情完整 ${completeness}`, variant: 'green' };
  if (Number.isFinite(number) && number >= 50) return { label: `详情部分 ${completeness}`, variant: 'blue' };
  return { label: `详情待补 ${completeness}`, variant: 'amber' };
}

export function isValidPgyDetailUrl(value) {
  if (!value || value === '待填') return false;
  try {
    const url = new URL(value);
    return url.hostname === 'pgy.xiaohongshu.com' && url.pathname.includes('/solar/pre-trade/blogger-detail/');
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
  if (!payload) return {};
  if (typeof payload === 'object') return payload;
  if (typeof payload !== 'string') return {};
  try {
    const parsed = JSON.parse(payload);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
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
  const creatorType = pickCreatorValue(creator, ['creator_type', '达人类型', 'type'], creator.type);
  if (creatorType) return String(creatorType).replace(/\s+/g, '');
  const tags = splitCreatorTags(pickCreatorValue(creator, ['personaTags', 'persona_tags', '人设标签']));
  return tags[0] || '达人';
}

export function getCreatorCollectedAt(creator) {
  return pickCreatorValue(creator, ['collectedAt', 'collected_at', 'createdAt', 'created_at']);
}

export function getCreatorXhsId(creator) {
  const explicit = pickCreatorValue(creator, ['xiaohongshuId', 'xiaohongshu_id', '小红书号']);
  if (explicit) return explicit;
  return '待采集';
}

export function getCreatorIntro(creator) {
  const rawPayload = getCreatorRawPayload(creator);
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
    rawPayload.personal_intro,
    rawPayload.profile_intro,
    rawPayload.xhs_profile_intro,
    rawPayload.bio,
    rawPayload.signature,
    rawPayload.blogger_profile,
    rawPayload.user_profile,
    rawPayload.profile?.intro,
    rawPayload.profile?.bio,
  ].find(value => String(value || '').trim());
  return intro ? String(intro).trim() : '暂无详情页个人简介';
}

export function getCreatorAvatarUrl(creator) {
  return pickCreatorValue(creator, ['avatarUrl', 'avatar_url']);
}

export function getCreatorMetricChips(creator) {
  const chips = [];
  const grade = pickCreatorValue(creator, ['childGrade', 'child_grade', '孩子年级']);
  const age = pickCreatorValue(creator, ['child_age', '孩子年龄']);
  const gender = pickCreatorValue(creator, ['child_gender', '孩子性别']);
  const fans35 = pickCreatorValue(creator, ['fans35PlusRatio', 'fans_35_plus_ratio', '35岁以上粉丝占比']);
  const cpe = pickCreatorValue(creator, ['naturalCpe', 'natural_cpe', '合作笔记自然CPE']);
  const cpc = pickCreatorValue(creator, ['natural_cpc', '合作笔记自然CPC']);
  const searchRatio = pickCreatorValue(creator, ['search_recommend_ratio', '搜索+推荐占比']);
  const traffic = pickCreatorValue(creator, ['traffic_stability', '近30天流量稳定性']);
  const rateLimit = pickCreatorValue(creator, ['rateLimitRisk', 'rate_limit_risk', '限流风险判断']);
  const shop30 = pickCreatorValue(creator, ['shop_cost_30d', '30天外溢进店成本']);
  if (grade) chips.push(`年级 ${grade}`);
  if (age) chips.push(`孩子${age}岁`);
  if (gender && gender !== '未披露') chips.push(`${gender}孩`);
  if (fans35) chips.push(`35+ ${formatPercentValue(fans35)}`);
  if (cpe) chips.push(`CPE ${cpe}`);
  if (cpc) chips.push(`CPC ${cpc}`);
  if (searchRatio) chips.push(`搜推 ${formatPercentValue(searchRatio)}`);
  if (traffic) chips.push(`流量${traffic}`);
  if (rateLimit && !['无', '低'].includes(String(rateLimit))) chips.push(`限流${rateLimit}`);
  if (shop30) chips.push(`进店¥${shop30}`);
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
      title: `${tag}：${getCreatorIntro(creator).slice(0, 34) || '待补采详情页后生成更多证据'}`,
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
  return [
    ...(Array.isArray(payload.recent_note_cases) ? payload.recent_note_cases : []),
    ...(Array.isArray(payload.recent_notes) ? payload.recent_notes : []),
    ...(Array.isArray(payload.cooperation_note_cases) ? payload.cooperation_note_cases : []),
    ...(Array.isArray(payload.note_cases) ? payload.note_cases : []),
    ...(Array.isArray(payload.notes) ? payload.notes : []),
    ...pages,
  ];
}

export function getCreatorRealNoteCases(creator) {
  const rawPayload = getCreatorRawPayload(creator);
  const nestedPayloads = [
    rawPayload,
    rawPayload.detail,
    rawPayload.raw_payload,
    creator.raw,
    creator.raw?.detail,
  ].filter(item => item && typeof item === 'object');
  const rawCases = [
    ...nestedPayloads.flatMap(collectNoteCaseArrays),
  ];
  const seen = new Set();
  const cases = rawCases
    .map((item, index) => {
      if (typeof item === 'string') return { brand: '笔记', title: item, index };
      if (!item || typeof item !== 'object') return null;
      return {
        index,
        brand: item.brand || item.cooperation_brand || item.category || item.note_type || '近期笔记',
        title: item.title || item.note_title || item.name || item.content_title || '未命名笔记',
        readCount: item.read_count ?? item.readCount ?? item.read ?? '',
        likeCount: item.like_count ?? item.likeCount ?? item.likes ?? '',
        saveCount: item.save_count ?? item.saveCount ?? item.saves ?? '',
        commentCount: item.comment_count ?? item.commentCount ?? item.comments ?? '',
        shareCount: item.share_count ?? item.shareCount ?? item.shares ?? '',
        publishedAt: item.published_at || item.publish_time || item.time || '',
        promoted: Boolean(item.has_promoted_traffic || item.promoted),
        crossDomain: Boolean(item.cross_domain || item.crossDomain || item.is_cross_domain),
        noteType: item.note_type || item.type || item.media_type || (item.video_url || item.videoUrl ? '视频笔记' : '图文笔记'),
        contentCategory: item.content_category || item.category || item.brand || '全部类目',
        coverUrl: item.cover_url || item.coverUrl || item.image || item.image_url || '',
        link: item.url || item.note_url || item.link || item.source_url || item.case_section_url || '',
        trafficComparison: item.traffic_comparison || item.trafficComparison || '',
        readVsMedian: item.read_vs_median ?? item.readVsMedian ?? null,
        interactionVsMedian: item.interaction_vs_median ?? item.interactionVsMedian ?? null,
        hasClearMedianContrast: Boolean(item.has_clear_median_contrast || item.hasClearMedianContrast),
        trafficMedianReference: item.traffic_median_reference || item.trafficMedianReference || null,
        source: item.source || 'detail_payload',
      };
    })
    .filter(Boolean)
    .filter(item => item.title && item.title !== '未命名笔记')
    .filter((item) => {
      const key = `${item.brand}|${item.title}|${item.publishedAt}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

  return cases.slice(0, 12);
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
  if (!getPgyUrl(creator)) riskSignals.push('缺少蒲公英详情链接');
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

export function getCreatorDeepAuditReason(creator, noteCases = []) {
  const rawReason = String(creator.aiReason || creator.reason || '').replace(/^【(?:大模型分析|通用初筛)】/, '').trim();
  const structured = parseAuditReasonSections(rawReason);
  if (structured.length >= 3) {
    return { summary: rawReason, sections: structured };
  }

  const tags = getCreatorTagGroups(creator);
  const intro = getCreatorIntro(creator);
  const metrics = uniqueCompactItems([
    getMetricText(creator.followers, '粉丝 ', value => value),
    getMetricText(creator.quote, '报价 ', value => value),
    getMetricText(pickCreatorValue(creator, ['naturalCpe', 'natural_cpe']), 'CPE ', value => value),
    getMetricText(pickCreatorValue(creator, ['natural_cpc']), 'CPC ', value => value),
    getMetricText(pickCreatorValue(creator, ['video_completion_rate']), '视频完播 ', formatPercentValue),
    getMetricText(pickCreatorValue(creator, ['fans35PlusRatio', 'fans_35_plus_ratio']), '35+ ', formatPercentValue),
    getMetricText(pickCreatorValue(creator, ['search_recommend_ratio']), '搜推 ', formatPercentValue),
  ], 6);
  const noteText = noteCases.length
    ? `${noteCases.slice(0, 2).map(note => note.title).join('、')} 等 ${noteCases.length} 条内容可作样本`
    : '暂无可核验的视频/笔记案例，需补采详情页与内容样本';
  const risks = uniqueCompactItems([...(creator.risk || []), !getPgyUrl(creator) ? '缺少蒲公英详情链接' : ''], 4);
  const action = getCreatorRecommendation(creator, getPoolStage(creator));
  const sections = [
    { title: '数据表现', text: metrics.length ? metrics.join(' / ') : '关键投放数据待补，暂不能只凭基础分判断效率。' },
    { title: '人设匹配', text: `${[...tags.persona, ...tags.content].slice(0, 5).join('、') || '人设标签待补'}；简介：${intro}` },
    { title: '内容贴合', text: noteText },
    { title: '风险/动作', text: `${risks.length ? risks.join('、') : '暂无明显硬风险'}；建议：${action}` },
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
  const contentTags = splitCreatorTags(pickCreatorValue(creator, ['category_tags', 'content_tags', '内容标签', '类目标签']));
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
  if (['已驳回', '默认淘汰'].includes(creator.review)) return '观察暂缓';
  if (['已通过', '已写回飞书'].includes(creator.review)) return '已合作跟进中';
  if (creator.review === '已邀约') return '待建联达人';
  if (creator.review === '备选' || creator.baseScore >= 90) return '合格达人待合作';
  if (creator.baseScore >= 70 || creator.review === '人工复核') return '待建联达人';
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
