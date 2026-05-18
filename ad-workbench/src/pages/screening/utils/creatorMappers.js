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

function normalizeRiskLabel(text) {
  const value = String(text || '').replace(/^【(?:通用初筛|大模型分析)】/, '').trim();
  if (!value) return '';
  if (/报价.*(?:超过|偏高|高于)/.test(value)) return '报价超预算';
  if (/35岁以上粉丝占比.*(?:低于|不足)|粉丝年龄画像/.test(value)) return '35+占比不足/待核';
  if (/CPC.*(?:未低于|偏高|未进入)/i.test(value)) return 'CPC效率待核';
  if (/CPE.*(?:未低于|偏高|未进入)/i.test(value)) return 'CPE效率待核';
  if (/CPM.*偏高/i.test(value)) return 'CPM偏高';
  if (/搜索\+推荐|搜索推荐|搜推/.test(value)) return '搜推占比待核';
  if (/限流|违规|异常流量|高风险|流量风险/.test(value)) return '限流/异常风险';
  if (/近期笔记阅读未达|阅读数据未进入|缺少较好阅读数据/.test(value)) return '阅读数据不足';
  if (/未识别到匹配信息|人设|内容垂直|场景/.test(value)) return '人设内容待核';
  return value.length > 18 ? `${value.slice(0, 18)}...` : value;
}

function collectScoreReasonRisks(scoreReason) {
  return String(scoreReason || '')
    .split(/[；;]/)
    .map(normalizeRiskLabel)
    .filter(Boolean)
    .filter(label => !/高分依据|加成|基础信息匹配|效率判断：报价.*(?:低于|达标)|近期\/合作数据/.test(label));
}

export function mapBackendCreator(item) {
  const score = Math.round(Number(item.total_score || 0));
  const type = getCreatorDisplayType(item);
  const categoryType = getCreatorCategoryType(item);
  const risks = [];
  const rawPayload = getCreatorRawPayload({ raw: item });
  const collectionIssues = Array.isArray(rawPayload.collection_hard_filter_issues) ? rawPayload.collection_hard_filter_issues : [];
  collectionIssues.forEach(issue => {
    if (issue) risks.push(normalizeRiskLabel(issue));
  });
  if (item.hard_filter_passed === 0 || item.hard_filter_passed === false) {
    risks.push(...collectScoreReasonRisks(item.score_reason).slice(0, 4));
    if (!risks.length) risks.push('硬性条件待核');
  }
  if (!item.pgy_url || item.pgy_url === '待填') risks.push('无蒲公英');
  if (Number(item.quote_price || 0) >= 20000) risks.push('报价偏高');
  if (item.rate_limit_risk && !['无', '无明显'].includes(item.rate_limit_risk)) risks.push(normalizeRiskLabel(item.rate_limit_risk));
  if (!risks.length && item.persona_tags) risks.push(item.persona_tags.split(/[\/,，]/)[0]);
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
    baseScore: score || 0,
    baseOnlyScore: Math.round(Number(item.base_score || 0)),
    bonusScore: Math.round(Number(item.bonus_score || 0)),
    informationCompleteness: item.information_completeness,
    informationCompletenessLabel: formatCompleteness(item.information_completeness),
    initialTier: item.initial_tier || item.tier || '',
    detailCollectionPriority: item.detail_collection_priority || '',
    risk: uniqueRisks,
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
    categoryTags: categoryType,
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
  if (score >= 70) return { key: 'B', label: 'B档', variant: 'amber', text: '暂缓观察', color: '#D97706' };
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
        coverUrl: item.cover_url || item.coverUrl || item.imgUrl || item.imageUrl || item.image || item.image_url || '',
        link: item.url || item.note_url || item.link || item.source_url || item.case_section_url || '',
        content: item.content || item.text || item.desc || item.description || item.note_content || item.note_text || item.body || '',
        summary: item.summary || item.note_summary || item.excerpt || '',
        description: item.description || item.note_description || '',
        topics: Array.isArray(item.topics) ? item.topics : Array.isArray(item.tags) ? item.tags : [],
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
      ageFit: pickCreatorValue(creator, ['fans35PlusRatio', 'fans_35_plus_ratio']) ? `35+ ${formatPercentValue(pickCreatorValue(creator, ['fans35PlusRatio', 'fans_35_plus_ratio']))}` : '粉丝年龄待补',
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

function getCostTone(label, value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 'muted';
  if (label === 'CPE') return number <= 10 ? 'good' : number <= 20 ? 'ok' : 'bad';
  if (label === 'CPC') return number <= 2 ? 'good' : number <= 3 ? 'ok' : 'bad';
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

export function getCreatorAdRecommendation(creator, noteCases = []) {
  const rawReason = String(creator.aiReason || creator.reason || '').replace(/^【(?:大模型分析|通用初筛)】/, '').trim();
  const cpe = getNumericMetric(creator, ['naturalCpe', 'natural_cpe', '合作笔记自然CPE', 'image_interaction_unit_price', 'video_interaction_unit_price'], 'CPE');
  const cpc = getNumericMetric(creator, ['natural_cpc', '合作笔记自然CPC', 'image_read_unit_price', 'video_read_unit_price'], 'CPC');
  const cpm = getNumericMetric(creator, ['image_cpm', 'video_cpm', '预估CPM', '图文预估CPM价格', '视频预估CPM价格'], 'CPM');
  const costMetrics = [
    { label: 'CPE', value: formatCostMetric(cpe), tone: getCostTone('CPE', cpe) },
    { label: 'CPM', value: formatCostMetric(cpm), tone: getCostTone('CPM', cpm) },
    { label: 'CPC', value: formatCostMetric(cpc), tone: getCostTone('CPC', cpc) },
  ];
  const knownTones = costMetrics.map(item => item.tone).filter(tone => tone !== 'muted');
  const verdict = knownTones.includes('bad') ? '成本偏高' : knownTones.includes('good') ? '成本优秀' : knownTones.includes('ok') ? '成本达标' : '成本待补';

  const noteMetrics = [
    { label: '合作曝光', value: formatCountMetric(pickCreatorValue(creator, ['cooperation_exposure_median', '合作曝光中位数', '曝光中位数（合作）'])) },
    { label: '合作阅读', value: formatCountMetric(pickCreatorValue(creator, ['cooperation_read_median', '合作阅读中位数', '阅读中位数（合作）'])) },
    { label: '合作互动', value: formatCountMetric(pickCreatorValue(creator, ['cooperation_interaction_median', '合作互动中位数', '互动中位数（合作）'])) },
    { label: '搜推占比', value: formatPercentValue(pickCreatorValue(creator, ['search_recommend_ratio', '搜索+推荐占比'])) || '待补' },
  ];
  if (noteMetrics.every(item => item.value === '待补')) {
    noteMetrics.splice(0, 3,
      { label: '近30天曝光', value: formatCountMetric(pickCreatorValue(creator, ['image_daily_exposure_median', 'video_daily_exposure_median'])) },
      { label: '近30天阅读', value: formatCountMetric(pickCreatorValue(creator, ['daily_read_median', 'image_daily_read_median', 'video_daily_read_median'])) },
      { label: '近30天互动', value: formatCountMetric(pickCreatorValue(creator, ['daily_interaction_median', 'image_daily_interaction_median', 'video_daily_interaction_median'])) },
    );
  }

  const clauses = reasonClauses(rawReason);
  const positiveClauses = clauses.filter(item => /达标|低于|匹配|高分|加成|专业|垂直|强|优质|精准|讨论度|真实|性价比|优势/.test(item) && !/未|不足|偏高|风险|缺少|待核/.test(item));
  const negativeClauses = clauses.filter(item => /未|不足|偏高|风险|缺少|待核|不匹配|暂缓|弱|下降/.test(item));
  const tagGroups = getCreatorTagGroups(creator);
  const tagAdvantage = uniqueCompactItems([...tagGroups.persona, ...tagGroups.content], 4);
  const strengths = uniqueCompactItems([
    ...buildMetricStrengths(creator),
    tagAdvantage.length ? `人设/内容标签：${tagAdvantage.join('、')}` : '',
    ...positiveClauses,
  ], 4);
  const weaknesses = uniqueCompactItems([
    ...(creator.risk || []),
    ...buildMetricWeaknesses(creator),
    ...negativeClauses,
  ], 4);
  const noteTitles = noteCases.length
    ? noteCases.slice(0, 2).map(note => note.title).join('、')
    : '';
  const action = getCreatorRecommendation(creator, getPoolStage(creator));
  const noteSummary = noteTitles
    ? `可参考 ${noteTitles} 等 ${noteCases.length} 条笔记样本。`
    : '合作笔记标题/正文样本待补，先按中位数和成本指标判断。';

  return {
    verdict,
    costMetrics: costMetrics.map(item => ({ ...item, status: costToneText(item.tone) })),
    noteMetrics,
    noteSummary,
    strengths: strengths.length ? strengths : ['暂未提取到明确优势，建议完善详情页和笔记证据。'],
    weaknesses: weaknesses.length ? weaknesses : ['暂无明显硬风险，仍需结合内容样本复核。'],
    action,
    summary: rawReason || `${verdict}；${noteSummary}；建议：${action}`,
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
    getMetricText(pickCreatorValue(creator, ['naturalCpe', 'natural_cpe']), 'CPE ', value => value),
    getMetricText(pickCreatorValue(creator, ['natural_cpc']), 'CPC ', value => value),
    getMetricText(pickCreatorValue(creator, ['video_completion_rate']), '视频完播 ', formatPercentValue),
    getMetricText(pickCreatorValue(creator, ['fans35PlusRatio', 'fans_35_plus_ratio']), '35+ ', formatPercentValue),
    getMetricText(pickCreatorValue(creator, ['search_recommend_ratio']), '搜推 ', formatPercentValue),
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
