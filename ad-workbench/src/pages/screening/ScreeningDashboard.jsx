import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Users, BarChart3, FolderPlus, ScrollText, ExternalLink,
  Filter, CheckCircle2, XCircle, AlertTriangle, Clock, ChevronRight,
  FileText, Upload, Bot, Sparkles, Target, DollarSign, Calendar,
  TrendingUp, Eye, Edit3, Save, Plus, Search, ArrowRight, RefreshCw,
  Link2, Copy, Download, ThumbsUp, ThumbsDown, MessageSquare, Star,
  FolderOpen, ChevronDown, Grid3X3, List, MoreHorizontal, Trash2, Play,
  UserCheck, UserX, Ban, Bookmark, RotateCcw, Send, Settings, Database,
  Shield, Zap, Activity, FileSpreadsheet, ClipboardCheck, ArrowUpRight,
  ArrowDownRight, Minus, Info, X, ChevronUp, ChevronLeft, KeyRound, Globe,
  ToggleLeft, ToggleRight
} from 'lucide-react';
import StatCard from '../../components/StatCard';
import DataTable from '../../components/DataTable';
import Badge from '../../components/Badge';
import ProgressBar from '../../components/ProgressBar';

const STEPS = ['立项', '绑定飞书', '生成计划', '蒲公英采集', '初筛评分', '人工筛选', '项目达人池'];
const PROJECT_ID = 'youdao_001';

async function api(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) {
    const detail = payload.detail || payload;
    const message = detail?.message || detail?.error || payload.message || payload.error || response.statusText || '请求失败';
    const error = new Error(message);
    error.detail = detail;
    throw error;
  }
  return payload;
}

function formatApiErrorMessage(payload, fallback = '请求失败') {
  if (!payload) return fallback;
  if (typeof payload === 'string') return payload;
  if (payload instanceof Error) return payload.message || fallback;

  const detail = payload.detail && typeof payload.detail === 'object' ? payload.detail : payload;
  const directMessage = detail.message || detail.error || payload.message || payload.error;
  if (typeof directMessage === 'string') return directMessage;
  if (directMessage && typeof directMessage === 'object') {
    return formatApiErrorMessage(directMessage, fallback);
  }
  try {
    return JSON.stringify(detail);
  } catch {
    return fallback;
  }
}

function compactNumber(value) {
  const number = Number(value || 0);
  if (!number) return '待填';
  if (number >= 10000) return `${(number / 10000).toFixed(number >= 100000 ? 1 : 2).replace(/\.0$/, '')}万`;
  return String(number);
}

function formatCurrency(value) {
  const number = Number(value || 0);
  return number ? `¥${number.toLocaleString('zh-CN')}` : '待填';
}

function formatDateTime(value) {
  if (!value) return '未记录';
  const normalized = String(value).trim().replace('T', ' ').replace(/\.\d+Z?$/, '');
  return normalized || '未记录';
}

function getDateKey(value) {
  if (!value) return '';
  const normalized = String(value).trim().replace('T', ' ');
  const match = normalized.match(/^(\d{4}-\d{2}-\d{2})/);
  if (match) return match[1];
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '';
  return parsed.toISOString().slice(0, 10);
}

function formatDateLabel(value) {
  const key = getDateKey(value);
  if (!key) return '未记录';
  return key.replace(/-/g, '.');
}

function reviewVariantFromStatus(status) {
  return { 已通过: 'green', 已写回飞书: 'green', 已驳回: 'red', 备选: 'amber', 待审核: 'blue', 待补数据: 'default' }[status] || 'default';
}

function normalizeDimensionScore(value, weight) {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  const normalized = number <= weight ? (number / weight) * 100 : number;
  return Math.max(0, Math.min(100, Math.round(normalized)));
}

function formatCompleteness(value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) return '待补';
  const ratio = number > 1 ? number / 100 : number;
  return `${Math.round(ratio * 100)}%`;
}

function deriveDimensionScores(item) {
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

function mapBackendCreator(item) {
  const score = Math.round(Number(item.total_score || 0));
  const type = item.creator_type || (Number(item.followers_count || 0) >= 100000 ? 'KOL' : 'KOC');
  const risks = [];
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

function normalizeProjectBrief(item, base) {
  const savedBrief = typeof item.brief === 'string' ? item.brief.trim() : '';
  const baseBrief = base.brief && typeof base.brief === 'object' ? base.brief : {};
  return {
    ...baseBrief,
    projectId: item.project_id,
    projectName: item.project_name,
    template: baseBrief.template || '自定义',
    description: savedBrief || baseBrief.description || base.description || '',
  };
}

function mapBackendProject(item, creators = [], feishuConfig = null) {
  const base = initialProjects[0];
  const linked = Boolean(feishuConfig?.feishu_url);
  const normalizedBrief = normalizeProjectBrief(item, base);
  return {
    ...base,
    id: item.project_id,
    name: item.project_name,
    product: '有道答疑笔Pro',
    creatorCount: item.target_qualified_creator_count || 10,
    periodStart: item.period_start || base.periodStart,
    periodEnd: item.period_end || base.periodEnd,
    period: `${item.period_start || '2026-05-07'} 至 ${item.period_end || '2026-05-19'}`,
    createdAt: item.created_at || '',
    updatedAt: item.updated_at || '',
    archivedAt: item.archived_at || '',
    status: item.archived_at ? '已归档' : base.status,
    description: normalizedBrief.description || base.description,
    brief: normalizedBrief,
    currentStep: linked ? 6 : 4,
    creators,
    feishuBinding: {
      linked,
      tableUrl: feishuConfig?.feishu_url || '',
      tableName: linked ? '有道答疑笔达人池' : '',
      baseToken: feishuConfig?.target?.token || '',
      tableId: feishuConfig?.target?.table_id || '',
      viewId: '',
      fieldMapping: base.feishuBinding.fieldMapping,
    },
    stats: {
      total: item.creator_pool_count || creators.length,
      passed: item.qualified_creator_count || 0,
      ratio: item.qualified_ratio || 0,
    },
    screeningPlan: parseStoredScreeningPlan(item.screening_plan, base.screeningPlan),
  };
}

function parseStoredScreeningPlan(value, fallback = {}) {
  if (!value) return fallback || {};
  if (typeof value === 'object') return value;
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === 'object' && Object.keys(parsed).length ? parsed : fallback || {};
  } catch {
    return fallback || {};
  }
}

// ==================== 初始项目数据 ====================

const initialProjects = [
  {
    id: 'youdao_001', name: '有道答疑笔5-6月合作', product: '有道答疑笔Pro',
    poolType: 'shared', sharedPoolId: 'education_mom',
    budget: 600000, singleBudget: 20000, creatorCount: 30,
    period: '2026.05 - 2026.06', periodStart: '2026-05-01', periodEnd: '2026-06-30',
    status: '进行中', currentStep: 3,
    cooperationType: '合作笔记',
    description: '教育/母婴类达人推广有道答疑笔，面向小学1-6年级学生家长',
    brief: {
      projectId: 'youdao_001', projectName: '有道答疑笔5-6月合作', template: '有道',
      description: '我们需要找一批教育/母婴类的达人来推广有道答疑笔，主要面向小学1-6年级学生的家长。达人需要有真实的教育或育儿背景，粉丝画像中30-40岁宝妈占比要高。'
    },
    screeningPlan: {
      briefType: 'complex', hardFilters: [
        { field: '35岁以上粉丝占比', condition: '>=', value: '40%', required: true },
        { field: '平台报价', condition: '<=', value: '¥20,000', required: true },
        { field: '蒲公英链接', condition: '必须存在', value: '', required: true },
      ],
      scoringWeights: { budget: 20, fans: 20, cpe: 15, engagement: 15, persona: 20, content: 10 },
    },
    feishuBinding: {
      linked: true, tableUrl: 'https://example.feishu.cn/base/abc123', tableName: '有道答疑笔达人池',
      baseToken: 'abc123', tableId: 'tbl001', viewId: 'vew001',
      fieldMapping: [
        { standard: '达人昵称', feishu: '博主名称', writable: true, type: 'text' },
        { standard: '粉丝数', feishu: '粉丝数量', writable: true, type: 'number' },
        { standard: '平台报价', feishu: '报价', writable: true, type: 'number' },
        { standard: '审核状态', feishu: '状态', writable: true, type: 'select' },
        { standard: '评分总分', feishu: '评分', writable: false, type: 'formula' },
      ],
    },
  },
  {
    id: 'ai_course_q2', name: 'AI课程推广Q2', product: 'AI精品课程包',
    poolType: 'shared', sharedPoolId: 'education_mom',
    budget: 450000, singleBudget: 18000, creatorCount: 25,
    period: '2026.04 - 2026.06', periodStart: '2026-04-01', periodEnd: '2026-06-30',
    status: '已完成', currentStep: 7,
    cooperationType: '视频+图文',
    description: '科技教育类达人推广AI编程课程，面向6-12岁学生家长',
    brief: {
      projectId: 'ai_course_q2', projectName: 'AI课程推广Q2', template: 'AI课程',
      description: '推广AI编程课程，面向6-12岁学生家长。需要科技教育类达人，有编程或STEM教育背景优先。'
    },
    screeningPlan: { briefType: 'simple', hardFilters: [], scoringWeights: { budget: 25, fans: 15, cpe: 20, engagement: 15, persona: 15, content: 10 } },
    feishuBinding: { linked: true, tableUrl: 'https://example.feishu.cn/base/def456', tableName: 'AI课程Q2达人', baseToken: 'def456', tableId: 'tbl002', viewId: 'vew002', fieldMapping: [] },
  },
  {
    id: 'baby_food_001', name: '母婴产品种草', product: '婴儿辅食机',
    poolType: 'shared', sharedPoolId: 'baby_care',
    budget: 300000, singleBudget: 15000, creatorCount: 20,
    period: '2026.06 - 2026.08', periodStart: '2026-06-01', periodEnd: '2026-08-31',
    status: '待启动', currentStep: 1,
    cooperationType: '合作笔记',
    description: '真实宝妈人设推广婴儿辅食机，有辅食制作内容经验',
    brief: {
      projectId: 'baby_food_001', projectName: '母婴产品种草', template: '通用母婴',
      description: '婴儿辅食机产品种草，面向0-3岁宝宝家长。需要真实宝妈人设，有辅食制作内容经验。'
    },
    screeningPlan: { briefType: 'complex', hardFilters: [], scoringWeights: {} },
    feishuBinding: { linked: false, tableUrl: '', tableName: '', baseToken: '', tableId: '', viewId: '', fieldMapping: [] },
  },
  {
    id: 'luxury_skincare', name: '高端护肤品牌合作', product: '抗老精华套装',
    poolType: 'isolated', sharedPoolId: null,
    budget: 800000, singleBudget: 50000, creatorCount: 15,
    period: '2026.07 - 2026.09', periodStart: '2026-07-01', periodEnd: '2026-09-30',
    status: '待启动', currentStep: 1,
    cooperationType: '报备',
    description: '美妆护肤垂直达人推广高端护肤品，面向25-40岁都市女性',
    brief: {
      projectId: 'luxury_skincare', projectName: '高端护肤品牌合作', template: '自定义',
      description: '高端护肤品牌推广，面向25-40岁都市女性。需要美妆护肤垂直达人，有高端产品测评经验。'
    },
    screeningPlan: { briefType: 'complex', hardFilters: [], scoringWeights: {} },
    feishuBinding: { linked: false, tableUrl: '', tableName: '', baseToken: '', tableId: '', viewId: '', fieldMapping: [] },
  },
];

// ==================== 达人池数据（含评分维度）====================

const sharedPoolEducationMom = [
  { id: 1, name: '陪读妈妈莫小柒', type: 'KOL', typeVariant: 'purple', followers: '52.3万', followersNum: 523000, quote: '¥18,000', quoteNum: 18000, baseScore: 92, risk: ['高粉量', '母婴垂直'],
    scores: { budget: 95, fans: 88, cpe: 90, engagement: 92, persona: 96, content: 88 }, aiReason: '人设高度匹配教育场景，粉丝画像中30-40岁宝妈占比65%，内容质量稳定，互动率高于同类达人平均水平。' },
  { id: 2, name: '教育达人小王', type: 'KOL', typeVariant: 'purple', followers: '38.7万', followersNum: 387000, quote: '¥15,000', quoteNum: 15000, baseScore: 88, risk: ['教育垂直'],
    scores: { budget: 92, fans: 82, cpe: 85, engagement: 88, persona: 94, content: 86 }, aiReason: '教育领域深耕3年，有教师资格认证，粉丝粘性高，CPE数据优秀。' },
  { id: 3, name: '学霸妈妈日记', type: 'KOC', typeVariant: 'blue', followers: '8.2万', followersNum: 82000, quote: '¥5,000', quoteNum: 5000, baseScore: 85, risk: ['低粉量'],
    scores: { budget: 98, fans: 72, cpe: 88, engagement: 90, persona: 92, content: 80 }, aiReason: '真实宝妈人设，陪读日记内容真实度高，粉丝互动活跃，性价比优秀。' },
  { id: 4, name: '育儿百科全书', type: 'KOL', typeVariant: 'purple', followers: '120.5万', followersNum: 1205000, quote: '¥35,000', quoteNum: 35000, baseScore: 82, risk: ['报价偏高', '泛母婴'],
    scores: { budget: 65, fans: 95, cpe: 78, engagement: 82, persona: 80, content: 85 }, aiReason: '粉丝量大但偏泛母婴，教育垂直度不足，报价超出单达人预算上限。' },
  { id: 5, name: '小学老师张老师', type: 'KOC', typeVariant: 'blue', followers: '5.6万', followersNum: 56000, quote: '¥3,500', quoteNum: 3500, baseScore: 79, risk: ['低粉量', '教育垂直'],
    scores: { budget: 98, fans: 65, cpe: 82, engagement: 78, persona: 88, content: 75 }, aiReason: '有教师背景，教育垂直度高，但粉丝量偏小，影响力有限。' },
  { id: 6, name: '亲子时光Alice', type: 'KOL', typeVariant: 'purple', followers: '67.1万', followersNum: 671000, quote: '¥22,000', quoteNum: 22000, baseScore: 76, risk: ['报价偏高'],
    scores: { budget: 72, fans: 88, cpe: 75, engagement: 78, persona: 76, content: 80 }, aiReason: '亲子内容优质，但报价偏高且内容偏亲子娱乐，教育属性较弱。' },
  { id: 7, name: '英语启蒙小课堂', type: 'KOC', typeVariant: 'blue', followers: '3.1万', followersNum: 31000, quote: '¥2,000', quoteNum: 2000, baseScore: 71, risk: ['低粉量', '内容单一'],
    scores: { budget: 98, fans: 58, cpe: 72, engagement: 70, persona: 75, content: 65 }, aiReason: '英语启蒙垂直度高但内容单一，粉丝量小，内容创新度不足。' },
  { id: 8, name: '家有二宝', type: 'KOC', typeVariant: 'blue', followers: '2.8万', followersNum: 28000, quote: '¥1,800', quoteNum: 1800, baseScore: 65, risk: ['低粉量', '互动率低'],
    scores: { budget: 98, fans: 52, cpe: 65, engagement: 60, persona: 68, content: 58 }, aiReason: '互动率持续下降，近30天笔记表现低于历史水平，疑似限流。' },
  { id: 9, name: '全职妈妈小丽', type: 'KOC', typeVariant: 'blue', followers: '1.5万', followersNum: 15000, quote: '¥1,200', quoteNum: 1200, baseScore: 58, risk: ['低粉量', '无蒲公英'],
    scores: { budget: 98, fans: 45, cpe: 55, engagement: 52, persona: 60, content: 48 }, aiReason: '无蒲公英链接，无法验证数据真实性，粉丝量极小。' },
  { id: 10, name: '宝妈好物推荐', type: 'KOC', typeVariant: 'blue', followers: '4.2万', followersNum: 42000, quote: '¥2,500', quoteNum: 2500, baseScore: 52, risk: ['广告过多', '信任度低'],
    scores: { budget: 95, fans: 55, cpe: 48, engagement: 45, persona: 50, content: 42 }, aiReason: '近30天广告占比超过70%，粉丝信任度下降明显，不适合教育类产品推广。' },
];

const sharedPoolBabyCare = [
  { id: 11, name: '新手妈妈日记', type: 'KOL', typeVariant: 'purple', followers: '45.2万', followersNum: 452000, quote: '¥16,000', quoteNum: 16000, baseScore: 90, risk: ['母婴垂直'],
    scores: { budget: 90, fans: 88, cpe: 92, engagement: 90, persona: 94, content: 86 }, aiReason: '真实新手妈妈人设，辅食制作内容丰富，粉丝画像精准匹配0-3岁宝宝家长。' },
  { id: 12, name: '育儿专家李医生', type: 'KOL', typeVariant: 'purple', followers: '89.5万', followersNum: 895000, quote: '¥28,000', quoteNum: 28000, baseScore: 87, risk: ['报价偏高'],
    scores: { budget: 75, fans: 92, cpe: 88, engagement: 86, persona: 90, content: 88 }, aiReason: '儿科医生背景，专业背书强，但报价偏高，需要评估ROI。' },
  { id: 13, name: '宝宝辅食日记', type: 'KOC', typeVariant: 'blue', followers: '12.3万', followersNum: 123000, quote: '¥6,500', quoteNum: 6500, baseScore: 84, risk: [],
    scores: { budget: 92, fans: 78, cpe: 85, engagement: 86, persona: 88, content: 82 }, aiReason: '辅食制作内容专业度高，有营养师认证，性价比优秀。' },
  { id: 14, name: '母乳喂养指导', type: 'KOC', typeVariant: 'blue', followers: '8.7万', followersNum: 87000, quote: '¥4,500', quoteNum: 4500, baseScore: 81, risk: ['内容单一'],
    scores: { budget: 95, fans: 72, cpe: 80, engagement: 82, persona: 82, content: 78 }, aiReason: '母乳喂养领域专业，但内容范围较窄，与辅食机产品匹配度一般。' },
  { id: 15, name: '婴儿睡眠训练师', type: 'KOL', typeVariant: 'purple', followers: '35.6万', followersNum: 356000, quote: '¥19,000', quoteNum: 19000, baseScore: 78, risk: ['报价偏高'],
    scores: { budget: 78, fans: 82, cpe: 76, engagement: 78, persona: 80, content: 76 }, aiReason: '婴儿睡眠领域专业，但与辅食机产品关联度不高，报价接近预算上限。' },
];

const isolatedPoolLuxury = [
  { id: 101, name: '美妆博主Vivi', type: 'KOL', typeVariant: 'purple', followers: '156.8万', followersNum: 1568000, quote: '¥45,000', quoteNum: 45000, baseScore: 94, risk: ['高粉量', '美妆垂直'],
    scores: { budget: 85, fans: 96, cpe: 94, engagement: 95, persona: 96, content: 92 }, aiReason: '高端美妆领域头部达人，有多次高端护肤品合作经验，粉丝画像精准匹配25-40岁都市女性。' },
  { id: 102, name: '护肤成分党', type: 'KOL', typeVariant: 'purple', followers: '78.3万', followersNum: 783000, quote: '¥32,000', quoteNum: 32000, baseScore: 91, risk: ['专业度高'],
    scores: { budget: 90, fans: 90, cpe: 92, engagement: 90, persona: 94, content: 90 }, aiReason: '成分分析专业度高，粉丝信任度强，适合抗老精华这类需要专业背书的产品。' },
  { id: 103, name: '都市丽人Lisa', type: 'KOL', typeVariant: 'purple', followers: '92.5万', followersNum: 925000, quote: '¥38,000', quoteNum: 38000, baseScore: 89, risk: ['报价偏高'],
    scores: { budget: 82, fans: 92, cpe: 88, engagement: 88, persona: 90, content: 86 }, aiReason: '都市生活方式博主，粉丝画像匹配度高，但报价偏高需评估性价比。' },
  { id: 104, name: '成分实验室', type: 'KOC', typeVariant: 'blue', followers: '15.6万', followersNum: 156000, quote: '¥12,000', quoteNum: 12000, baseScore: 86, risk: [],
    scores: { budget: 95, fans: 78, cpe: 88, engagement: 86, persona: 88, content: 84 }, aiReason: '成分测评内容专业，性价比高，适合作为KOC矩阵补充。' },
  { id: 105, name: '30+护肤日记', type: 'KOC', typeVariant: 'blue', followers: '22.4万', followersNum: 224000, quote: '¥15,000', quoteNum: 15000, baseScore: 83, risk: [],
    scores: { budget: 92, fans: 80, cpe: 84, engagement: 82, persona: 86, content: 80 }, aiReason: '30+女性护肤经验分享，人设真实，粉丝互动活跃，性价比优秀。' },
];

const initialScreeningStatus = {
  youdao_001: {
    1: { review: '已通过', reviewVariant: 'green', finalScore: 92, reason: '人设高度匹配', reviewer: '张策划', reviewedAt: '2026-05-06 14:30' },
    2: { review: '已通过', reviewVariant: 'green', finalScore: 88, reason: '教育领域深耕', reviewer: '张策划', reviewedAt: '2026-05-06 14:35' },
    3: { review: '已通过', reviewVariant: 'green', finalScore: 85, reason: '真实宝妈人设', reviewer: '李媒介', reviewedAt: '2026-05-06 15:00' },
    4: { review: '已驳回', reviewVariant: 'red', finalScore: 82, reason: '报价超出预算', reviewer: '张策划', reviewedAt: '2026-05-06 15:10' },
    5: { review: '备选', reviewVariant: 'amber', finalScore: 79, reason: '影响力有限', reviewer: '李媒介', reviewedAt: '2026-05-06 15:20' },
  },
  ai_course_q2: {
    1: { review: '已通过', reviewVariant: 'green', finalScore: 90, reason: 'AI课程经验丰富', reviewer: '张策划', reviewedAt: '2026-04-20 10:00' },
    2: { review: '已通过', reviewVariant: 'green', finalScore: 89, reason: '科技教育优质', reviewer: '张策划', reviewedAt: '2026-04-20 10:05' },
  },
  baby_food_001: {
    11: { review: '已通过', reviewVariant: 'green', finalScore: 91, reason: '辅食经验丰富', reviewer: '王运营', reviewedAt: '2026-05-07 09:00' },
    12: { review: '人工复核', reviewVariant: 'amber', finalScore: 88, reason: '专家背书强', reviewer: null, reviewedAt: null },
  },
  luxury_skincare: {
    101: { review: '已通过', reviewVariant: 'green', finalScore: 95, reason: '高端测评经验', reviewer: '赵媒介', reviewedAt: '2026-05-07 11:00' },
    102: { review: '已通过', reviewVariant: 'green', finalScore: 93, reason: '成分分析专业', reviewer: '赵媒介', reviewedAt: '2026-05-07 11:05' },
  },
};

const mockAuditLogs = [
  { id: 1, type: 'review', action: '审核通过', target: '陪读妈妈莫小柒', user: '张策划', time: '2026-05-06 14:30', detail: '人设高度匹配，评分92分，建议通过', status: 'success' },
  { id: 2, type: 'review', action: '审核通过', target: '教育达人小王', user: '张策划', time: '2026-05-06 14:35', detail: '教育领域深耕3年，评分88分', status: 'success' },
  { id: 3, type: 'review', action: '审核通过', target: '学霸妈妈日记', user: '李媒介', time: '2026-05-06 15:00', detail: '真实宝妈人设，性价比优秀', status: 'success' },
  { id: 4, type: 'review', action: '审核驳回', target: '育儿百科全书', user: '张策划', time: '2026-05-06 15:10', detail: '报价¥35,000超出单达人预算¥20,000上限', status: 'warning' },
  { id: 5, type: 'review', action: '加入备选', target: '小学老师张老师', user: '李媒介', time: '2026-05-06 15:20', detail: '有教师背景但影响力有限，列入备选观察', status: 'info' },
  { id: 6, type: 'screening', action: 'AI初筛完成', target: '教育母婴池', user: '系统', time: '2026-05-06 12:00', detail: '共10位达人完成AI评分，建议通过3位，人工复核2位，默认淘汰5位', status: 'success' },
  { id: 7, type: 'feishu', action: '飞书写回', target: '有道答疑笔达人池', user: '系统', time: '2026-05-06 16:00', detail: '成功写回3条达人记录，0条重复跳过', status: 'success' },
  { id: 8, type: 'project', action: '创建项目', target: '有道答疑笔5-6月合作', user: '张策划', time: '2026-05-01 09:00', detail: '项目创建成功，达人池类型：共享池（教育母婴）', status: 'success' },
  { id: 9, type: 'feishu', action: '绑定飞书表格', target: '有道答疑笔达人池', user: '张策划', time: '2026-05-02 10:00', detail: '成功绑定飞书多维表格，读取到5个字段', status: 'success' },
  { id: 10, type: 'screening', action: '量化标准生成', target: '有道答疑笔5-6月合作', user: 'AI', time: '2026-05-03 11:00', detail: 'Brief类型：复杂，生成3条硬性条件，6维评分权重', status: 'success' },
  { id: 11, type: 'review', action: '批量审核', target: '6位待审核达人', user: '李媒介', time: '2026-05-06 15:30', detail: '批量通过3位（评分>=85），驳回1位（报价超标），备选2位', status: 'info' },
  { id: 12, type: 'feishu', action: '飞书写回失败', target: '有道答疑笔达人池', user: '系统', time: '2026-05-05 14:00', detail: '达人"育儿百科全书"写回失败：字段"评分总分"为公式字段不可写', status: 'error' },
];

// ==================== 工具函数 ====================

function getProjectCreators(project) {
  if (!project) return [];
  if (project.creators) return project.creators;
  if (project.poolType === 'isolated') {
    if (project.id === 'luxury_skincare') return isolatedPoolLuxury;
    return project.creators || [];
  } else {
    if (project.sharedPoolId === 'education_mom') return sharedPoolEducationMom;
    if (project.sharedPoolId === 'baby_care') return sharedPoolBabyCare;
    return [];
  }
}

function getCreatorStatus(projectId, creatorId, statusMap) {
  const map = statusMap || initialScreeningStatus;
  return map[projectId]?.[creatorId] || null;
}

function getDefaultCreatorStatus() {
  return {
    review: '待审核', reviewVariant: 'default', finalScore: null, reason: '', reviewer: null, reviewedAt: null,
  };
}

function getProjectStats(project, statusMap) {
  const creators = getProjectCreators(project);
  if (project.stats) {
    const backup = creators.filter(c => c.review === '备选').length;
    const rejected = creators.filter(c => c.review === '已驳回').length;
    const review = creators.filter(c => c.review === '待审核').length;
    const pending = creators.filter(c => c.review === '待补数据').length;
    return { total: project.stats.total, passed: project.stats.passed, rejected, backup, review, pending };
  }
  const sm = (statusMap || initialScreeningStatus)[project.id] || {};
  const passed = Object.values(sm).filter(s => s.review === '已通过').length;
  const rejected = Object.values(sm).filter(s => s.review === '已驳回' || s.review === '默认淘汰').length;
  const backup = Object.values(sm).filter(s => s.review === '备选').length;
  const review = Object.values(sm).filter(s => s.review === '人工复核').length;
  const pending = creators.length - passed - rejected - backup - review;
  return { total: creators.length, passed, rejected, backup, review, pending };
}

function briefTextFromProject(project) {
  const brief = project?.brief;
  const briefDescription = typeof brief === 'string'
    ? brief
    : [brief?.description, brief?.goal, brief?.requirement].filter(Boolean).join(' ');
  return [project?.description, briefDescription].filter(Boolean).join(' ');
}

function extractFirstNumber(text, patterns = []) {
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) {
      return Number(match[1]);
    }
  }
  return null;
}

function parseBriefTaskTargets(project) {
  const text = briefTextFromProject(project);
  const targetCreators = extractFirstNumber(text, [
    /(?:目标|需要|合作|筛选|招募)[^\d]{0,12}(\d+)\s*(?:位|个|名)?\s*达人/i,
    /(\d+)\s*(?:位|个|名)\s*(?:合格|合作|目标)?达人/i,
  ]);
  const roiMatch = text.match(/(?:ROI|roi|投产比|投入产出比)[^\d]*(\d+(?:\.\d+)?)(?:\s*[:：]\s*(\d+(?:\.\d+)?))?/);
  const cpe = extractFirstNumber(text, [
    /(?:CPE|cpe)[^\d]*(\d+(?:\.\d+)?)/,
    /互动成本[^\d]*(\d+(?:\.\d+)?)/,
  ]);
  const exposure = extractFirstNumber(text, [
    /(?:曝光|播放|阅读)[^\d]*(\d+(?:\.\d+)?)(?:\s*万)?/,
  ]);

  return {
    targetCreators: targetCreators || project.creatorCount || project.stats?.target || project.stats?.total || 0,
    targetRoi: roiMatch ? Number(roiMatch[2] || roiMatch[1]) : null,
    targetCpe: cpe,
    targetExposure: exposure,
    hasExplicitMetric: Boolean(roiMatch || cpe || exposure),
  };
}

function getProjectTaskSummary(project, statusMap) {
  const creators = getProjectCreators(project);
  const stats = getProjectStats(project, statusMap);
  const targets = parseBriefTaskTargets(project);
  const statusById = (statusMap || initialScreeningStatus)[project.id] || {};
  const collaboratorStatuses = new Set(['已合作', '合作中', '已通过', '已写回飞书']);
  const rejectedStatuses = new Set(['已驳回', '默认淘汰', '不合作']);
  const creatorReview = (creator) => statusById[creator.id]?.review || creator.review || creator.raw?.status || '';

  const collaboratedFromCreators = creators.filter(creator => collaboratorStatuses.has(creatorReview(creator))).length;
  const rejectedFromCreators = creators.filter(creator => rejectedStatuses.has(creatorReview(creator))).length;
  const collaborated = project.stats?.passed ?? collaboratedFromCreators;
  const total = project.stats?.total ?? creators.length;
  const rejected = project.stats ? stats.rejected : rejectedFromCreators;
  const pendingScreening = Math.max(total - collaborated - rejected, 0);
  const targetCreators = Math.max(targets.targetCreators || collaborated || 1, 1);

  const actualRoi = Number(project.metrics?.roi || project.stats?.roi || project.roi || 0) || null;
  const collaboratorProgress = Math.min(collaborated / targetCreators, 1);
  const roiProgress = actualRoi && targets.targetRoi ? Math.min(actualRoi / targets.targetRoi, 1) : null;
  const progressRatio = roiProgress === null
    ? collaboratorProgress
    : collaboratorProgress * 0.7 + roiProgress * 0.3;

  const briefMetric = targets.targetRoi
    ? `ROI ${targets.targetRoi}x`
    : targets.targetCpe
      ? `CPE <= ${targets.targetCpe}`
      : targets.targetExposure
        ? `曝光 ${targets.targetExposure}万`
        : 'Brief未写明';

  return {
    total,
    pendingScreening,
    collaborated,
    targetCreators,
    progress: Math.round(progressRatio * 100),
    progressText: `${collaborated}/${targetCreators} · ${Math.round(progressRatio * 100)}%`,
    progressDetail: actualRoi && targets.targetRoi
      ? `合作达人 + ROI ${actualRoi}x/${targets.targetRoi}x`
      : `按已合作达人推进，指标：${briefMetric}`,
    briefMetric,
  };
}

function getScoreColor(score) {
  if (score >= 100) return '#10B981';
  if (score >= 90) return '#3B82F6';
  if (score >= 80) return '#F59E0B';
  if (score >= 70) return '#D97706';
  return '#EF4444';
}

function getScoreTier(score) {
  if (score >= 100) return { key: 'S', label: 'S档', variant: 'green', text: '必须补采', color: '#10B981' };
  if (score >= 90) return { key: 'A', label: 'A档', variant: 'blue', text: '优先补采', color: '#3B82F6' };
  if (score >= 80) return { key: 'B+', label: 'B+档', variant: 'amber', text: '高潜补采', color: '#F59E0B' };
  if (score >= 70) return { key: 'B', label: 'B档', variant: 'amber', text: '暂缓补采', color: '#D97706' };
  return { key: 'C', label: 'C档', variant: 'red', text: '不补采', color: '#EF4444' };
}

function isValidPgyDetailUrl(value) {
  if (!value || value === '待填') return false;
  try {
    const url = new URL(value);
    return url.hostname === 'pgy.xiaohongshu.com' && url.pathname.includes('/solar/pre-trade/blogger-detail/');
  } catch {
    return false;
  }
}

function getPgyUrl(creator) {
  const candidates = [
    creator.raw?.pgy_url,
    creator.raw?.profile_url,
    creator.pgyUrl,
    creator.profileUrl,
  ];
  return candidates.find(isValidPgyDetailUrl) || '';
}

function pickCreatorValue(creator, keys, fallback = '') {
  for (const key of keys) {
    const value = creator?.[key] ?? creator?.raw?.[key];
    if (value !== undefined && value !== null && value !== '') return value;
  }
  return fallback;
}

function getCreatorRawPayload(creator) {
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

function splitCreatorTags(value) {
  return String(value || '')
    .split(/[\/,，、\s]+/)
    .map(item => item.trim())
    .filter(Boolean);
}

function uniqueCompactItems(items, limit = 10) {
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

function formatPercentValue(value) {
  if (value === undefined || value === null || value === '') return '';
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  const percent = number <= 1 ? number * 100 : number;
  return `${Math.round(percent)}%`;
}

function getCreatorLocation(creator) {
  const explicit = pickCreatorValue(creator, ['ipCity', 'ip_city', 'IP城市']);
  if (explicit) return explicit;
  if (/上海|沪/.test(creator.name)) return '上海';
  if (/北京|海淀|胡同/.test(creator.name)) return '北京';
  return '其他';
}

function getCreatorCategory(creator) {
  const creatorType = pickCreatorValue(creator, ['creator_type', '达人类型', 'type'], creator.type);
  if (creatorType) return String(creatorType).replace(/\s+/g, '');
  const tags = splitCreatorTags(pickCreatorValue(creator, ['personaTags', 'persona_tags', '人设标签']));
  return tags[0] || '达人';
}

function getCreatorCollectedAt(creator) {
  return pickCreatorValue(creator, ['collectedAt', 'collected_at', 'createdAt', 'created_at']);
}

function getCreatorXhsId(creator) {
  const explicit = pickCreatorValue(creator, ['xiaohongshuId', 'xiaohongshu_id', '小红书号']);
  if (explicit) return explicit;
  return '待采集';
}

function getCreatorIntro(creator) {
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

function getCreatorAvatarUrl(creator) {
  return pickCreatorValue(creator, ['avatarUrl', 'avatar_url']);
}

function getCreatorMetricChips(creator) {
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
  const direction = pickCreatorValue(creator, ['cooperation_direction', '合作方向']);
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
  if (direction) chips.push(direction);
  return uniqueCompactItems(chips, 8);
}

function getCreatorTags(creator) {
  const personaTags = splitCreatorTags(pickCreatorValue(creator, ['personaTags', 'persona_tags', '人设标签']));
  const categoryTags = splitCreatorTags(pickCreatorValue(creator, ['category_tags', 'content_tags', '内容标签', '类目标签']));
  const riskTags = Array.isArray(creator.risk) ? creator.risk : splitCreatorTags(pickCreatorValue(creator, ['risk_tags', 'risk', '风险标签']));
  const derivedTags = [];
  const intro = getCreatorIntro(creator);
  const creatorType = getCreatorCategory(creator);
  const location = getCreatorLocation(creator);
  const budgetStatus = pickCreatorValue(creator, ['budget_status', '预算状态']);
  const mcnStatus = pickCreatorValue(creator, ['mcn_status', 'MCN状态']);

  if (creatorType && creatorType !== '达人') derivedTags.push(creatorType);
  if (location && location !== '其他') derivedTags.push(location);
  if (budgetStatus) derivedTags.push(budgetStatus);
  if (mcnStatus) derivedTags.push(mcnStatus);
  if (/老师|教师|教资|班主任/.test(intro + creator.name)) derivedTags.push('教师人设');
  if (/妈妈|宝妈|陪读|亲子|家庭/.test(intro + creator.name)) derivedTags.push('家庭教育');
  if (/小升初|初中|高中|升学|作业/.test(intro)) derivedTags.push('升学场景');
  if (/测评|开箱|好物|种草/.test(intro)) derivedTags.push('测评种草');

  return uniqueCompactItems([
    ...getCreatorMetricChips(creator),
    ...personaTags,
    ...categoryTags,
    ...derivedTags,
    ...riskTags,
  ], 10);
}

function creatorHasTag(creator, tag) {
  if (!tag) return true;
  return getCreatorTags(creator).includes(tag);
}

function getCreatorProfileFacts(creator, tier) {
  return uniqueCompactItems([
    getCreatorXhsId(creator) ? `小红书号：${getCreatorXhsId(creator)}` : '',
    getCreatorLocation(creator) ? `地区：${getCreatorLocation(creator)}` : '',
    getCreatorCategory(creator) ? `类型：${getCreatorCategory(creator)}` : '',
    creator.followers ? `粉丝：${creator.followers}` : '',
    creator.quote ? `报价：${creator.quote}` : '',
    tier?.label ? `评分：${creator.baseScore} / ${tier.label}` : '',
  ], 6);
}

function getPoolStage(creator, index = 0) {
  if (creator.poolStage || creator.pool_stage) return creator.poolStage || creator.pool_stage;
  if (['已驳回', '默认淘汰'].includes(creator.review)) return '观察暂缓';
  if (['已通过', '已写回飞书'].includes(creator.review)) return '已合作跟进中';
  if (creator.review === '备选' || creator.baseScore >= 90) return '合格达人待合作';
  if (creator.baseScore >= 70 || creator.review === '人工复核') return '待建联达人';
  return '观察暂缓';
}

function getCreatorUpdateLog(creator, index = 0) {
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

function getReviewVariant(review) {
  const map = { '已通过': 'green', '已写回飞书': 'green', '已驳回': 'red', '备选': 'amber', '人工复核': 'blue', '默认淘汰': 'red', '待审核': 'default', '待确认': 'amber', '待补数据': 'default' };
  return map[review] || 'default';
}

// ==================== 项目预览组件 ====================

function ProjectsPreview({ projects, onSelectProject, onCreateProject, onArchiveProject, onRestoreProject, onDeleteProject }) {
  const [viewMode, setViewMode] = useState('grid');
  const [filter, setFilter] = useState('全部');
  const [search, setSearch] = useState('');

  const filteredProjects = projects.filter(p => {
    if (filter === '归档') {
      if (!p.archivedAt) return false;
    } else {
      if (p.archivedAt) return false;
      if (filter !== '全部' && p.status !== filter) return false;
    }
    if (search && !p.name.includes(search) && !p.product.includes(search)) return false;
    return true;
  });
  const activeProjects = projects.filter(p => !p.archivedAt);
  const archivedProjects = projects.filter(p => p.archivedAt);

  const stats = {
    total: activeProjects.length,
    active: activeProjects.filter(p => p.status === '进行中').length,
    completed: activeProjects.filter(p => p.status === '已完成').length,
    pending: archivedProjects.length,
  };

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
        <StatCard title="项目总数" value={stats.total} subtitle="个项目" icon={FolderOpen} color="blue" />
        <StatCard title="进行中" value={stats.active} subtitle="个项目" icon={Play} color="green" />
        <StatCard title="已完成" value={stats.completed} subtitle="个项目" icon={CheckCircle2} color="cyan" />
        <StatCard title="已归档" value={stats.pending} subtitle="个项目" icon={Clock} color="amber" />
      </div>

      <div className="card" style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <div className="search-box" style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
            <input
              className="search-input"
              placeholder="搜索项目名称或产品..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ paddingLeft: 30, width: 200 }}
            />
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            {['全部', '进行中', '已完成', '待启动', '归档'].map(status => (
              <button key={status} onClick={() => setFilter(status)}
                className={`btn btn-sm ${filter === status ? 'btn-primary' : 'btn-ghost'}`}>{status}</button>
            ))}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className={`btn btn-sm ${viewMode === 'grid' ? 'btn-secondary' : 'btn-ghost'}`} onClick={() => setViewMode('grid')}><Grid3X3 size={16} /></button>
          <button className={`btn btn-sm ${viewMode === 'list' ? 'btn-secondary' : 'btn-ghost'}`} onClick={() => setViewMode('list')}><List size={16} /></button>
        </div>
      </div>

      {filteredProjects.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: 48 }}>
          <FolderOpen size={48} style={{ color: 'var(--text-muted)', marginBottom: 16 }} />
          <h4 style={{ color: 'var(--text-primary)', marginBottom: 8 }}>暂无匹配项目</h4>
          <p style={{ color: 'var(--text-secondary)' }}>尝试调整筛选条件或创建新项目</p>
        </div>
      ) : viewMode === 'grid' ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
          {filteredProjects.map(project => (
            <ProjectCard
              key={project.id}
              project={project}
              onClick={() => onSelectProject(project)}
              onArchive={() => onArchiveProject(project)}
              onRestore={() => onRestoreProject(project)}
              onDelete={() => onDeleteProject(project)}
            />
          ))}
        </div>
      ) : (
        <div className="card">
          <DataTable
            columns={[
              { key: 'name', label: '项目名称', render: (v, row) => (
                <div>
                  <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{v}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{row.product}</div>
                </div>
              )},
              { key: 'status', label: '状态', render: (v, row) => <Badge variant={row.archivedAt ? 'default' : v === '进行中' ? 'blue' : v === '已完成' ? 'green' : 'amber'}>{row.archivedAt ? '已归档' : v}</Badge> },
              { key: 'poolType', label: '达人池', render: v => <Badge variant={v === 'shared' ? 'blue' : 'purple'}>{v === 'shared' ? '共享' : '独立'}</Badge> },
              { key: 'createdAt', label: '创建时间', render: v => <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{formatDateTime(v)}</span> },
              { key: 'budget', label: '预算', render: v => `¥${v.toLocaleString()}` },
              { key: 'progress', label: '进度', render: (v, row) => {
                const s = getProjectStats(row);
                return (<div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><ProgressBar value={s.total > 0 ? (s.passed / s.total) * 100 : 0} size="sm" /><span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{s.passed}/{s.total}</span></div>);
              }},
              { key: 'action', label: '', render: (v, row) => (
                <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                  <button className="btn btn-sm btn-primary" onClick={(e) => { e.stopPropagation(); onSelectProject(row); }}>进入 <ArrowRight size={14} /></button>
                  <button className="btn btn-sm btn-ghost" onClick={(e) => { e.stopPropagation(); row.archivedAt ? onRestoreProject(row) : onArchiveProject(row); }}>{row.archivedAt ? '恢复' : '归档'}</button>
                  <button className="btn btn-sm btn-ghost" onClick={(e) => { e.stopPropagation(); onDeleteProject(row); }}><Trash2 size={14} /></button>
                </div>
              )},
            ]}
            data={filteredProjects}
            onRowClick={(row) => onSelectProject(row)}
          />
        </div>
      )}
    </div>
  );
}

function ProjectCard({ project, onClick, onArchive, onRestore, onDelete }) {
  const taskSummary = getProjectTaskSummary(project);
  const statusVariant = project.archivedAt ? 'default' : project.status === '进行中' ? 'blue' : project.status === '已完成' ? 'green' : 'amber';
  const poolLabel = project.poolType === 'shared' ? '共享池' : '独立池';

  return (
    <article className="project-task-card" onClick={onClick}>
      <div className="project-task-card-accent" />

      <div className="project-task-card-top">
        <div className="project-task-card-kicker">
          <FolderOpen size={14} />
          <span>{poolLabel}</span>
        </div>
        <div className="project-task-actions">
          <Badge variant={statusVariant}>{project.archivedAt ? '已归档' : project.status}</Badge>
          <button
            className="btn btn-sm btn-icon btn-ghost"
            title={project.archivedAt ? '恢复项目' : '归档项目'}
            onClick={(event) => {
              event.stopPropagation();
              project.archivedAt ? onRestore?.() : onArchive?.();
            }}
          >
            <Clock size={14} />
          </button>
          <button
            className="btn btn-sm btn-icon btn-ghost"
            title="删除项目"
            onClick={(event) => {
              event.stopPropagation();
              onDelete?.();
            }}
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      <div className="project-task-card-main">
        <div className="project-task-card-title-row">
          <h4>{project.name}</h4>
          <ArrowUpRight size={16} />
        </div>
        <div className="project-task-card-product">{project.product}</div>
        <p>{project.description}</p>
      </div>

      <div className="project-task-metrics">
        <div className="project-task-metric">
          <span>待筛选达人</span>
          <strong>{taskSummary.pendingScreening}人</strong>
        </div>
        <div className="project-task-metric">
          <span>已合作达人</span>
          <strong>{taskSummary.collaborated}人</strong>
        </div>
        <div className="project-task-metric project-task-metric-wide">
          <span>Brief拆解指标</span>
          <strong>{taskSummary.briefMetric}</strong>
        </div>
      </div>

      <div className="project-task-progress">
        <div className="project-task-progress-head">
          <span>任务进度</span>
          <strong>{taskSummary.progressText}</strong>
        </div>
        <div className="project-task-progress-track">
          <div className="project-task-progress-fill" style={{ width: `${taskSummary.progress}%` }} />
        </div>
        <div className="project-task-progress-note">{taskSummary.progressDetail}</div>
      </div>

      <div className="project-task-meta">
        <span><Clock size={13} />创建 {formatDateTime(project.createdAt)}</span>
        {project.archivedAt && <span><Clock size={13} />归档 {formatDateTime(project.archivedAt)}</span>}
        <span><Calendar size={13} />{project.period}</span>
        {project.feishuBinding?.linked && <span><Link2 size={13} />已绑定飞书</span>}
      </div>
    </article>
  );
}

// ==================== 新建项目弹窗 ====================

function CreateProjectModal({ isOpen, onClose, onCreate }) {
  const [form, setForm] = useState({ name: '', product: '', poolType: 'shared', sharedPoolId: 'education_mom', budget: '', singleBudget: '', creatorCount: '', periodStart: '', periodEnd: '', cooperationType: '合作笔记', description: '' });

  if (!isOpen) return null;

  const handleSubmit = () => {
    const id = `proj_${Date.now()}`;
    onCreate({
      id, ...form, budget: Number(form.budget), singleBudget: Number(form.singleBudget), creatorCount: Number(form.creatorCount),
      period: `${form.periodStart} - ${form.periodEnd}`, status: '待启动', currentStep: 1,
      brief: { projectId: id, projectName: form.name, template: '自定义', description: form.description },
      screeningPlan: { briefType: 'simple', hardFilters: [], scoringWeights: { budget: 20, fans: 20, cpe: 15, engagement: 15, persona: 20, content: 10 } },
      feishuBinding: { linked: false, tableUrl: '', tableName: '', baseToken: '', tableId: '', viewId: '', fieldMapping: [] },
    });
    onClose();
  };

  const labelStyle = { fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 640, maxHeight: '90vh', overflow: 'auto' }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>新建筛选项目</h3>
          <button className="btn btn-ghost btn-sm modal-close" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="modal-body">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16, marginBottom: 16 }}>
            <div><label style={labelStyle}>项目名称 *</label><input className="input-field" value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="如：有道答疑笔5-6月合作" /></div>
            <div><label style={labelStyle}>产品名称 *</label><input className="input-field" value={form.product} onChange={e => setForm({...form, product: e.target.value})} placeholder="如：有道答疑笔Pro" /></div>
            <div><label style={labelStyle}>达人池类型 *</label>
              <select className="select-field" value={form.poolType} onChange={e => setForm({...form, poolType: e.target.value})}>
                <option value="shared">共享池（与其他项目共用达人库）</option>
                <option value="isolated">独立池（项目专属达人库）</option>
              </select>
            </div>
            {form.poolType === 'shared' ? (
              <div><label style={labelStyle}>选择共享池 *</label>
                <select className="select-field" value={form.sharedPoolId} onChange={e => setForm({...form, sharedPoolId: e.target.value})}>
                  <option value="education_mom">教育母婴池（10位达人）</option>
                  <option value="baby_care">母婴护理池（5位达人）</option>
                </select>
              </div>
            ) : (
              <div><label style={labelStyle}>合作形式</label>
                <select className="select-field" value={form.cooperationType} onChange={e => setForm({...form, cooperationType: e.target.value})}>
                  <option value="合作笔记">合作笔记</option><option value="视频+图文">视频+图文</option><option value="报备">报备</option><option value="直播带货">直播带货</option>
                </select>
              </div>
            )}
            <div><label style={labelStyle}>总预算（元）*</label><input className="input-field" type="number" value={form.budget} onChange={e => setForm({...form, budget: e.target.value})} placeholder="如：600000" /></div>
            <div><label style={labelStyle}>单达人预算上限（元）</label><input className="input-field" type="number" value={form.singleBudget} onChange={e => setForm({...form, singleBudget: e.target.value})} placeholder="如：20000" /></div>
            <div><label style={labelStyle}>目标达人数量 *</label><input className="input-field" type="number" value={form.creatorCount} onChange={e => setForm({...form, creatorCount: e.target.value})} placeholder="如：30" /></div>
            <div><label style={labelStyle}>合作形式</label>
              <select className="select-field" value={form.cooperationType} onChange={e => setForm({...form, cooperationType: e.target.value})}>
                <option value="合作笔记">合作笔记</option><option value="视频+图文">视频+图文</option><option value="报备">报备</option><option value="直播带货">直播带货</option>
              </select>
            </div>
            <div><label style={labelStyle}>开始日期</label><input className="input-field" type="date" value={form.periodStart} onChange={e => setForm({...form, periodStart: e.target.value})} /></div>
            <div><label style={labelStyle}>结束日期</label><input className="input-field" type="date" value={form.periodEnd} onChange={e => setForm({...form, periodEnd: e.target.value})} /></div>
          </div>
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>客户 Brief（口语化需求描述）</label>
            <textarea className="input-field" rows={3} value={form.description} onChange={e => setForm({...form, description: e.target.value})} placeholder="如：我们需要找一批教育/母婴类的达人来推广有道答疑笔..." style={{ resize: 'none' }} />
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>取消</button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={!form.name || !form.product || !form.budget || !form.creatorCount}>创建项目</button>
        </div>
      </div>
    </div>
  );
}

// ==================== 采集工作台 ====================

const DEFAULT_PGY_DISPLAY_METRICS = [
  '全部非直播指标',
];

const WEIGHT_LABELS = { budget: '预算匹配', fans: '粉丝量级', cpe: 'CPE效率', engagement: '互动质量', persona: '人设匹配', content: '内容风格' };

const PGY_FOLLOWER_RANGE_OPTIONS = ['100万以上', '50万～100万', '10万～50万', '1万～10万', '0.5万～1万', '0.1万～0.5万'];
const PGY_FAN_AGE_OPTIONS = ['<18 占比高', '18～24 占比高', '25～34 占比高', '35～44 占比高', '>44 占比高'];
const PGY_MATERNAL_STAGE_OPTIONS = ['备孕', '0-6月', '7-12月', '1-3岁', '4-6岁', '7-12岁', '孕早期', '孕晚期'];
const PGY_BLOGGER_CATEGORY_OPTIONS = ['教育', '母婴', '生活记录', '科技数码', '职场', '商业财经', '健康养生', '文化艺术'];
const PGY_REGION_OPTIONS = ['北京', '上海', '广东', '浙江', '江苏', '四川', '湖北', '湖南', '山东', '河南'];
const PGY_MARKETING_GOAL_OPTIONS = ['曝光', '种草', '转化'];
const PGY_FAMILY_IDENTITY_OPTIONS = ['妈妈', '萌娃', '爸爸', '奶奶'];
const PGY_CAREER_IDENTITY_OPTIONS = ['教育科研', '互联网', '金融法律', '企业创业', '文化传媒', '医疗健康', '工程师', 'HR'];
const PGY_SPECIAL_BACKGROUND_OPTIONS = ['备考经验', '留学背景', '海外华人', '孕妈', '独居人群', '兴趣爱好'];
const PGY_PRICE_RANGE_OPTIONS = ['0.1万～0.5万', '0.5万～1万', '1万～2万', '2万～5万', '5万以上'];
const PGY_UNIT_PRICE_OPTIONS = ['0.5以下', '0.5～1.0', '1.0～1.5', '1.5～2.0', '2.0以上'];
const PGY_NOTE_COUNT_RANGE_OPTIONS = ['5万以上', '1万～5万', '0.5万～1万', '0.1万～0.5万'];
const PGY_INTERACTION_RANGE_OPTIONS = ['2000以上', '1000～2000', '500～1000', '200～500', '100～200'];

const HARD_FILTER_OPTIONS = [
  { field: '营销目标', condition: '包含', value: '种草', required: true, feishuField: '营销目标', label: '蒲公英：营销目标', valueControl: 'multi', options: PGY_MARKETING_GOAL_OPTIONS, pgyField: '营销目标' },
  { field: '博主类目', condition: '包含', value: '教育', required: true, feishuField: '账号类型', label: '蒲公英：博主类目', valueControl: 'multi', options: PGY_BLOGGER_CATEGORY_OPTIONS, pgyField: '博主类目' },
  { field: '粉丝年龄', condition: '匹配', value: '35～44 占比高', required: true, feishuField: '粉丝年龄34岁以上占比', label: '蒲公英：粉丝年龄区间', valueControl: 'multi', options: PGY_FAN_AGE_OPTIONS, pgyField: '粉丝年龄' },
  { field: '合作报价', condition: '<=', value: '图文笔记：0.1万～2万', required: true, feishuField: '平台报价', label: '蒲公英：合作报价', valueControl: 'range', presets: PGY_PRICE_RANGE_OPTIONS, subField: '图文笔记', pgyField: '合作报价' },
  { field: '粉丝量', condition: '匹配', value: '1万～10万', required: false, feishuField: '粉丝数', label: '蒲公英：粉丝量档位', valueControl: 'multi', options: PGY_FOLLOWER_RANGE_OPTIONS, pgyField: '粉丝量' },
  { field: '家庭身份', condition: '包含', value: '妈妈', required: false, feishuField: '家庭身份', label: '蒲公英：家庭身份', valueControl: 'multi', options: PGY_FAMILY_IDENTITY_OPTIONS, pgyField: '家庭身份' },
  { field: '职业身份', condition: '包含', value: '教育科研', required: false, feishuField: '职业身份', label: '蒲公英：职业身份', valueControl: 'multi', options: PGY_CAREER_IDENTITY_OPTIONS, pgyField: '职业身份' },
  { field: '特色背景', condition: '包含', value: '备考经验', required: false, feishuField: '特色背景', label: '蒲公英：特色背景', valueControl: 'multi', options: PGY_SPECIAL_BACKGROUND_OPTIONS, pgyField: '特色背景' },
  { field: '母婴阶段', condition: '包含', value: '7-12岁', required: false, feishuField: '孩子年级', label: '蒲公英：母婴阶段', valueControl: 'multi', options: PGY_MATERNAL_STAGE_OPTIONS, pgyField: '母婴阶段' },
  { field: '粉丝地域', condition: '匹配', value: '北京、上海', required: false, feishuField: '粉丝地域', label: '蒲公英：粉丝地域', valueControl: 'multi', options: PGY_REGION_OPTIONS, pgyField: '粉丝地域' },
  { field: '预估阅读单价', condition: '<=', value: '图文笔记阅读单价≤2', required: false, feishuField: '合作笔记自然CPC', label: '蒲公英：预估阅读单价', valueControl: 'number', presets: PGY_UNIT_PRICE_OPTIONS, unit: '元', subField: '图文笔记阅读单价', pgyField: '预估阅读单价' },
  { field: '预估互动单价', condition: '<=', value: '图文笔记互动单价≤20', required: false, feishuField: '合作笔记自然CPE', label: '蒲公英：预估互动单价', valueControl: 'number', unit: '元', subField: '图文笔记互动单价', pgyField: '预估互动单价' },
  { field: '阅读中位数', condition: '>=', value: '0.5万～1万', required: false, feishuField: '阅读中位数（日常）', label: '蒲公英：阅读中位数', valueControl: 'range', presets: PGY_NOTE_COUNT_RANGE_OPTIONS, pgyField: '阅读中位数' },
  { field: '互动中位数', condition: '>=', value: '500～1000', required: false, feishuField: '互动中位数（日常）', label: '蒲公英：互动中位数', valueControl: 'range', presets: PGY_INTERACTION_RANGE_OPTIONS, pgyField: '互动中位数' },
  { field: '曝光中位数', condition: '>=', value: '1万～5万', required: false, feishuField: '曝光中位数（日常）', label: '蒲公英：曝光中位数', valueControl: 'range', presets: PGY_NOTE_COUNT_RANGE_OPTIONS, pgyField: '曝光中位数' },
  { field: '蒲公英链接', condition: '必须存在', value: '', required: true, feishuField: '蒲公英链接', label: '入库：必须有蒲公英链接', valueControl: 'none' },
  { field: '限流风险', condition: '规避', value: '疑似限流、异常流量', required: false, feishuField: '品牌备注', label: '入库：规避限流/异常流量', valueControl: 'multi', options: ['疑似限流', '异常流量', '违规', '低活博主', '掉粉博主'] },
];

const HARD_FILTER_CONDITIONS_BY_KIND = {
  number: ['>=', '<=', '>', '<', '='],
  existence: ['必须存在'],
  text: ['匹配', '包含', '不包含'],
  avoid: ['规避', '不包含'],
};
const DEFAULT_HARD_FILTER_CONDITIONS = ['匹配', '包含', '必须存在'];

function getHardFilterConditionKind(item = {}) {
  const text = `${item.field || ''} ${item.feishuField || ''} ${item.value || ''}`.toLowerCase();
  if (text.includes('链接') || text.includes('url')) return 'existence';
  if (text.includes('限流') || text.includes('违规') || text.includes('风险') || text.includes('剔除') || text.includes('规避')) return 'avoid';
  if (/[<>≤≥=]|%|¥|￥|\d/.test(String(item.value || ''))) return 'number';
  if (/(预算|报价|价格|成本|cpc|cpe|占比|比例|粉丝数|阅读|互动|roi|投产|金额|单价|效率)/i.test(text)) return 'number';
  return 'text';
}

function hardFilterConditionsFor(item = {}) {
  const option = getHardFilterOptionMeta(item);
  if (option?.conditions?.length) return option.conditions;
  if (option?.valueControl === 'multi') return ['匹配', '包含', '不包含'];
  if (option?.valueControl === 'none') return ['必须存在'];
  const options = HARD_FILTER_CONDITIONS_BY_KIND[getHardFilterConditionKind(item)] || DEFAULT_HARD_FILTER_CONDITIONS;
  return options.includes(item.condition) || !item.condition ? options : [item.condition, ...options];
}

function defaultHardFilterCondition(item = {}) {
  return hardFilterConditionsFor(item)[0] || '匹配';
}

function getHardFilterOptionMeta(item = {}) {
  return HARD_FILTER_OPTIONS.find(option => option.field === item.field)
    || HARD_FILTER_OPTIONS.find(option => option.pgyField && option.pgyField === item.pgyField)
    || HARD_FILTER_OPTIONS.find(option => option.feishuField && option.feishuField === item.feishuField)
    || null;
}

function splitHardFilterValue(value = '') {
  return String(value || '')
    .split(/[、,，;；/|｜]+/)
    .map(item => item.trim())
    .filter(Boolean);
}

function normalizeHardFilterValue(option, value) {
  if (option?.valueControl === 'multi') {
    const selected = Array.isArray(value) ? value : splitHardFilterValue(value);
    return selected.join('、');
  }
  return String(value ?? '');
}

function cloneHardFilterOption(option = {}) {
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

function mergeDefaultHardFilters(filters = []) {
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

const PGY_FILTER_OPTIONS = [
  { field: '营销目标', value: '曝光', reason: 'Brief 提到曝光/声量目标', label: '营销目标：曝光', control_type: 'tag' },
  { field: '营销目标', value: '转化', reason: 'Brief 提到转化目标', label: '营销目标：转化', control_type: 'tag' },
  { field: '按博主粉丝推荐', value: '待选择合作品牌/竞品', reason: '根据品牌或竞品粉丝画像找博主', label: '人群目标：按博主粉丝推荐', control_type: 'brand_search_recommendation', input_values: [], pending_detail: '右上角搜索合作品牌或竞品品牌' },
  { field: '博主类目', value: '教育', reason: 'Brief 命中教育场景', label: '博主类目：教育', control_type: 'tag' },
  { field: '博主类目', value: '母婴', reason: 'Brief 命中母婴/亲子场景', label: '博主类目：母婴', control_type: 'tag' },
  { field: '家庭身份', value: '妈妈', reason: 'Brief 命中家庭身份画像', label: '家庭身份：妈妈', control_type: 'checkbox_popover' },
  { field: '职业身份', value: '教育科研', reason: 'Brief 命中教师/专家画像', label: '职业身份：教育科研', control_type: 'checkbox_popover' },
  { field: '特色背景', value: '备考经验', reason: 'Brief 命中高知/升学画像', label: '特色背景：备考经验', control_type: 'checkbox_popover' },
  { field: '地域', value: '北京/上海优先', reason: 'Brief 提到北京、上海或一线城市', label: '地域：北京/上海优先', control_type: 'cascade_checkbox_popover', pending_detail: '需要展开国内城市二级选项' },
  { field: '粉丝年龄', value: '35～44 占比高', reason: 'Brief 要求家长/35岁以上粉丝', label: '粉丝年龄：35～44 占比高', control_type: 'dropdown' },
  { field: '合作报价', value: '图文笔记：0.1万～2万', reason: '单达人预算上限', label: '合作报价：图文 ≤ 2万', control_type: 'subfield_preset_or_number_range', sub_field: '图文笔记' },
  { field: '预估阅读单价', value: '图文笔记阅读单价≤2', reason: 'Brief 要求控制 CPC', label: '预估阅读单价：图文 ≤ 2', control_type: 'subfield_preset_or_number_range', sub_field: '图文笔记阅读单价' },
  { field: '预估互动单价', value: '图文笔记互动单价≤20', reason: 'Brief 要求控制 CPE', label: '预估互动单价：图文 ≤ 20', control_type: 'subfield_preset_or_number_range', sub_field: '图文笔记互动单价' },
  { field: '近期合作品牌', value: '待填品牌', reason: '记录或剔除近期合作品牌', label: '近期合作品牌：待填', control_type: 'searchable_multi_select_with_exclude', input_values: [], min_items: 3, pending_detail: '至少补足3个品牌' },
  { field: '行业推荐博主', value: '我的行业', reason: '使用行业推荐入口', label: '行业推荐博主：我的行业', control_type: 'nested_select_popover', pending_detail: '打开后继续选择我的行业' },
  { field: '常规剔除', value: '剔除低活博主', reason: '规避低活账号', label: '常规剔除：低活博主', control_type: 'checkbox' },
  { field: '常规剔除', value: '剔除掉粉博主', reason: '规避掉粉账号', label: '常规剔除：掉粉博主', control_type: 'checkbox' },
];

const DISPLAY_METRIC_OPTIONS = [
  { value: '全部非直播指标', label: '全部非直播指标' },
  { value: '粉丝数', label: '粉丝数' },
  { value: '阅读中位数（日常）', label: '阅读中位数（日常）' },
  { value: '互动中位数（日常）', label: '互动中位数（日常）' },
  { value: '全部报价', label: '全部报价' },
  { value: '曝光中位数', label: '曝光中位数' },
  { value: '合作信用度', label: '合作信用度' },
  { value: '近期合作行业', label: '近期合作行业' },
  { value: '近期合作品牌', label: '近期合作品牌' },
];

const hardFilterKey = (item) => `${item.field || ''}|${item.condition || ''}|${item.value || ''}`;
const pgyFilterKey = (item) => `${item.field || ''}|${item.value || ''}`;
const metricKey = (item) => String(item?.value || item || '');
const hardFilterLabel = (item) => item.label || `${item.field}${item.condition ? ` ${item.condition}` : ''}${item.value ? ` ${item.value}` : ''}`;
const pgyFilterLabel = (item) => item.label || `${item.field}：${item.value}`;
const DEFAULT_COLLECTION_HARD_FILTER_FIELDS = new Set(
  HARD_FILTER_OPTIONS.filter(option => option.pgyField).map(option => option.field)
);
const DEFAULT_SCORING_HARD_FILTER_FIELDS = new Set([
  '合作报价',
  '粉丝年龄',
  '预估阅读单价',
  '预估互动单价',
  '蒲公英链接',
  '限流风险',
]);
const CONTROL_TYPE_LABELS = {
  tag: '标签',
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
};

function mergeOptionItems(current = [], options = [], keyFn = item => item.value || item.label) {
  const seen = new Set();
  return [...options, ...current].filter(item => {
    const key = keyFn(item);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function normalizePgyFilterItem(item = {}) {
  const field = item.field || '';
  const value = item.value || '';
  const base = { ...item, field, value, reason: item.reason || '' };
  if (field === '博主人设') {
    const map = {
      家庭身份: { field: '家庭身份', value: '妈妈', control_type: 'checkbox_popover' },
      职业身份: { field: '职业身份', value: '教育科研', control_type: 'checkbox_popover' },
      特色背景: { field: '特色背景', value: '备考经验', control_type: 'checkbox_popover' },
    };
    return { ...base, ...(map[value] || {}) };
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
    return { ...base, control_type: 'cascade_checkbox_popover', pending_detail: '需要展开国内城市二级选项' };
  }
  return base;
}

function normalizePgyFilters(filters = []) {
  const expanded = [];
  filters.forEach(item => {
    expanded.push(normalizePgyFilterItem(item));
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

function SelectableMenu({ menuId, openMenu, setOpenMenu, label, summary, options, selectedKeys, getKey, getLabel, onToggle }) {
  const open = openMenu === menuId;
  return (
    <div className="collection-select-menu">
      <button type="button" className="collection-select-trigger" onClick={() => setOpenMenu(open ? null : menuId)}>
        <span>{label}</span>
        <small>{summary}</small>
        <ChevronDown size={15} className={open ? 'is-open' : ''} />
      </button>
      {open && (
        <div className="collection-select-popover">
          {options.map(option => {
            const key = getKey(option);
            const checked = selectedKeys.has(key);
            return (
              <label key={key} className="collection-select-option">
                <input type="checkbox" checked={checked} onChange={() => onToggle(option, checked)} />
                <span>{getLabel(option)}</span>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}

function SelectedChips({ items, getKey, getLabel, onRemove, emptyText }) {
  if (!items.length) return <span className="collection-empty-text">{emptyText}</span>;
  return (
    <div className="collection-selected-chip-row">
      {items.map(item => (
        <span className="collection-selected-chip" key={getKey(item)}>
          {getLabel(item)}
          <button type="button" onClick={() => onRemove(item)} title="移除"><X size={12} /></button>
        </span>
      ))}
    </div>
  );
}

function PgyFilterCards({ items, onRemove }) {
  if (!items.length) return <span className="collection-empty-text">暂无蒲公英条件，可从下拉菜单勾选。</span>;
  return (
    <div className="collection-pgy-filter-card-grid">
      {items.map(item => {
        const inputValues = Array.isArray(item.input_values) ? item.input_values.filter(Boolean) : [];
        return (
          <div className="collection-pgy-filter-card" key={pgyFilterKey(item)}>
            <div className="collection-pgy-filter-card-main">
              <strong>{pgyFilterLabel(item)}</strong>
              <button type="button" onClick={() => onRemove(item)} title="移除"><X size={12} /></button>
            </div>
            <div className="collection-pgy-filter-card-meta">
              {item.control_type && <span>{CONTROL_TYPE_LABELS[item.control_type] || item.control_type}</span>}
              {item.sub_field && <span>{item.sub_field}</span>}
              {inputValues.length > 0 && <span>{inputValues.join('、')}</span>}
              {Array.isArray(item.competitor_values) && item.competitor_values.length > 0 && <span>竞品：{item.competitor_values.join('、')}</span>}
              {item.pending_detail && <span className="is-pending">{item.pending_detail}</span>}
            </div>
            {item.reason && <p>{item.reason}</p>}
          </div>
        );
      })}
    </div>
  );
}

function normalizeHardFilterItem(item = {}) {
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

function normalizeHardFilterList(filters = [], defaultOptions = []) {
  const normalized = (filters || []).map(normalizeHardFilterItem);
  const seen = new Set(normalized.map(item => item.pgyField || item.field).filter(Boolean));
  const missing = defaultOptions
    .filter(option => !seen.has(option.pgyField || option.field))
    .map(cloneHardFilterOption);
  return [...normalized, ...missing];
}

function looksLikeCollectionHardFilter(item = {}) {
  const option = getHardFilterOptionMeta(item);
  return Boolean(item.pgyField || option?.pgyField);
}

function getLegacyCollectionHardFilters(plan = {}) {
  const pgyHardFilters = plan.pgyCollectionPlan?.hard_filters || plan.pgyCollectionPlan?.hardFilters || [];
  if (Array.isArray(plan.collectionHardFilters) && plan.collectionHardFilters.length) return plan.collectionHardFilters;
  if (Array.isArray(pgyHardFilters) && pgyHardFilters.length) return pgyHardFilters;
  return (plan.hardFilters || []).filter(looksLikeCollectionHardFilter);
}

function getLegacyScoringHardFilters(plan = {}) {
  if (Array.isArray(plan.scoringHardFilters) && plan.scoringHardFilters.length) return plan.scoringHardFilters;
  const hardRules = plan.scoringCriteria?.hard_rules || plan.scoringCriteria?.hardRules || [];
  if (Array.isArray(hardRules) && hardRules.length) return hardRules;
  return plan.hardFilters || [];
}

function hardFilterOptionsFor(defaultFields) {
  return HARD_FILTER_OPTIONS.filter(option => defaultFields.has(option.field));
}

function HardFilterValueControl({ filter, onChange }) {
  const option = getHardFilterOptionMeta(filter) || {};
  const control = filter.valueControl || option.valueControl || '';
  if (control === 'none') {
    return <span className="standard-hard-filter-static">无需填写</span>;
  }
  if (control === 'multi' && option.options?.length) {
    const selected = splitHardFilterValue(filter.value);
    return (
      <div className="standard-hard-filter-multi">
        {option.options.map(value => {
          const checked = selected.includes(value);
          return (
            <label key={value}>
              <input
                type="checkbox"
                checked={checked}
                onChange={e => {
                  const next = e.target.checked
                    ? [...selected, value]
                    : selected.filter(item => item !== value);
                  onChange({ value: normalizeHardFilterValue(option, next) });
                }}
              />
              <span>{value}</span>
            </label>
          );
        })}
      </div>
    );
  }
  if (control === 'range') {
    const value = filter.value || '';
    return (
      <div className="standard-hard-filter-range">
        <select
          className="select-field"
          value={option.presets?.includes(value.replace(`${option.subField || ''}：`, '')) ? value.replace(`${option.subField || ''}：`, '') : ''}
          onChange={e => onChange({ value: option.subField ? `${option.subField}：${e.target.value}` : e.target.value })}
        >
          <option value="">选择网页档位</option>
          {(option.presets || []).map(item => <option key={item} value={item}>{item}</option>)}
        </select>
        <input className="input-field" value={value} onChange={e => onChange({ value: e.target.value })} placeholder="或填写自定义区间" />
      </div>
    );
  }
  if (control === 'number') {
    return (
      <div className="standard-hard-filter-range">
        {option.presets?.length ? (
          <select className="select-field" value="" onChange={e => e.target.value && onChange({ value: `${option.subField || filter.field}≤${e.target.value.replace('以下', '').replace('以上', '')}` })}>
            <option value="">网页档位</option>
            {option.presets.map(item => <option key={item} value={item}>{item}</option>)}
          </select>
        ) : null}
        <input className="input-field" value={filter.value || ''} onChange={e => onChange({ value: e.target.value })} placeholder={`填写数值${option.unit ? `（${option.unit}）` : ''}`} />
      </div>
    );
  }
  return <input className="input-field" value={filter.value || ''} onChange={e => onChange({ value: e.target.value })} placeholder="阈值或规则" />;
}

function HardFilterEditor({
  filters = [],
  onChange,
  options = HARD_FILTER_OPTIONS,
  emptyText = '暂未设置硬性条件，可从可选项添加或手工新增',
  fieldHeader = '筛选项',
  evidenceHeader = '依据字段',
  evidencePlaceholder = '关联字段',
}) {
  const updateFilter = (index, patch) => {
    const nextFilters = [...(filters || [])];
    const next = { ...(nextFilters[index] || {}), ...patch };
    if (patch.field !== undefined || patch.value !== undefined || patch.feishuField !== undefined) {
      const conditions = hardFilterConditionsFor(next);
      if (!conditions.includes(next.condition)) {
        next.condition = defaultHardFilterCondition(next);
      }
    }
    nextFilters[index] = next;
    onChange?.(nextFilters);
  };

  const addFilter = (option = {}) => {
    const item = normalizeHardFilterItem(option);
    item.condition = hardFilterConditionsFor(item).includes(item.condition) ? item.condition : defaultHardFilterCondition(item);
    onChange?.([...(filters || []), item]);
  };

  const removeFilter = (index) => {
    onChange?.((filters || []).filter((_, itemIndex) => itemIndex !== index));
  };

  return (
    <>
      <div className="standard-hard-filter-toolbar">
        <select
          className="select-field"
          value=""
          onChange={e => {
            const option = options.find(item => hardFilterKey(item) === e.target.value);
            if (option) addFilter(option);
          }}
        >
          <option value="">从可选项添加条件</option>
          {options.map(option => (
            <option key={hardFilterKey(option)} value={hardFilterKey(option)}>{hardFilterLabel(option)}</option>
          ))}
        </select>
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => addFilter()}>
          <Plus size={14} style={{ marginRight: 4 }} />手工新增
        </button>
      </div>
      <div className="standard-hard-filter-list">
        {(filters || []).length > 0 && (
          <div className="standard-hard-filter-header">
            <span>{fieldHeader}</span>
            <span>判断方式</span>
            <span>标准/阈值</span>
            <span>{evidenceHeader}</span>
            <span>硬性必过</span>
            <span>操作</span>
          </div>
        )}
        {(filters || []).map((f, i) => (
          <div key={`hard-filter-${i}`} className="standard-hard-filter-row">
            <input className="input-field" value={f.field || ''} onChange={e => updateFilter(i, { field: e.target.value })} placeholder="字段/规则名" />
            <select className="select-field" value={f.condition || ''} onChange={e => updateFilter(i, { condition: e.target.value })}>
              {hardFilterConditionsFor(f).map(condition => <option key={condition} value={condition}>{condition}</option>)}
            </select>
            <HardFilterValueControl filter={f} onChange={patch => updateFilter(i, patch)} />
            <input className="input-field" value={f.feishuField || ''} onChange={e => updateFilter(i, { feishuField: e.target.value })} placeholder={evidencePlaceholder} />
            <label className="standard-hard-filter-required">
              <input type="checkbox" checked={f.required !== false} onChange={e => updateFilter(i, { required: e.target.checked })} />
              <span>必过</span>
            </label>
            <button type="button" className="btn btn-ghost btn-icon btn-sm" title="删除条件" onClick={() => removeFilter(i)}>
              <Trash2 size={14} />
            </button>
          </div>
        ))}
        {(filters || []).length === 0 && (
          <div style={{ padding: 16, background: 'var(--bg-elevated)', borderRadius: 6, textAlign: 'center', color: 'var(--text-muted)' }}>
            {emptyText}
          </div>
        )}
      </div>
    </>
  );
}

function normalizeWorkbenchPlan(plan = {}) {
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
      })),
      display_metrics: pgyPlan.display_metrics || DEFAULT_PGY_DISPLAY_METRICS,
      detail_fields: pgyPlan.detail_fields || ['基础画像', '粉丝画像', '报价', '合作表现', '内容表现'],
      filter_catalog: pgyPlan.filter_catalog || [],
    },
  };
}

function syncScreeningCriteria(plan = {}) {
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
  const collectionHardFilters = normalizeForSave(plan.collectionHardFilters || getLegacyCollectionHardFilters(plan));
  const scoringHardFilters = normalizeForSave(plan.scoringHardFilters || getLegacyScoringHardFilters(plan));
  const scoringWeights = { ...(plan.scoringWeights || {}) };
  const scoringCriteria = plan.scoringCriteria && typeof plan.scoringCriteria === 'object' ? plan.scoringCriteria : {};
  const pgyCollectionPlan = plan.pgyCollectionPlan && typeof plan.pgyCollectionPlan === 'object' ? plan.pgyCollectionPlan : {};
  return {
    ...plan,
    collectionHardFilters,
    scoringHardFilters,
    hardFilters: scoringHardFilters,
    scoringWeights,
    pgyCollectionPlan: {
      ...pgyCollectionPlan,
      hard_filters: collectionHardFilters,
    },
    scoringCriteria: {
      ...scoringCriteria,
      hard_rules: scoringHardFilters,
      dimension_weights: scoringCriteria.dimension_weights || scoringWeights,
    },
  };
}

function OverviewTab({ project, onCollect, onSavePlan }) {
  const creators = useMemo(() => getProjectCreators(project), [project]);
  const stats = getProjectStats(project);
  const [planDraft, setPlanDraft] = useState(() => normalizeWorkbenchPlan(project.screeningPlan || {}));
  const [planStatus, setPlanStatus] = useState('');
  const [planExpanded, setPlanExpanded] = useState(false);
  const [openPlanMenu, setOpenPlanMenu] = useState(null);

  useEffect(() => {
    setPlanDraft(normalizeWorkbenchPlan(project.screeningPlan || {}));
    setPlanStatus('');
    setOpenPlanMenu(null);
  }, [project.id, project.screeningPlan]);

  useEffect(() => {
    if (!planExpanded) setOpenPlanMenu(null);
  }, [planExpanded]);

  const savedPlan = useMemo(() => normalizeWorkbenchPlan(project.screeningPlan || {}), [project.screeningPlan]);
  const planDirty = JSON.stringify(planDraft) !== JSON.stringify(savedPlan);
  const pgyPlan = planDraft.pgyCollectionPlan || {};
  const collectionResult = {
    collected: creators.length,
    scored: creators.filter(item => Number(item.baseScore || 0) > 0).length,
    passedFilters: creators.filter(item => item.baseScore >= 90 && !item.risk?.includes('无蒲公英')).length,
    needsManual: creators.filter(item => item.baseScore < 90 || item.risk?.length).length,
  };
  const targetCount = Number(project.creatorCount || 0);
  const passRate = collectionResult.collected > 0 ? collectionResult.passedFilters / collectionResult.collected : 0;
  const qualifiedGap = Math.max(0, targetCount - collectionResult.passedFilters);
  const expectedShortage = qualifiedGap === 0 ? 0 : passRate > 0 ? Math.ceil(qualifiedGap / passRate) : qualifiedGap;
  const passRateLabel = collectionResult.collected > 0 ? `${Math.round(passRate * 100)}%` : '待采集';
  const collectionMetrics = [
    {
      title: '累计采集',
      value: collectionResult.collected,
      subtitle: '达人已入本项目',
      icon: Database,
      color: 'blue',
    },
    {
      title: '通过率',
      value: passRateLabel,
      subtitle: `${collectionResult.passedFilters} 位通过初筛`,
      icon: TrendingUp,
      color: 'green',
    },
    {
      title: '目标合格',
      value: targetCount,
      subtitle: `缺口 ${qualifiedGap} 位`,
      icon: Target,
      color: 'purple',
    },
    {
      title: '需补采',
      value: expectedShortage,
      subtitle: '按通过率推算',
      icon: AlertTriangle,
      color: expectedShortage > 0 ? 'amber' : 'green',
    },
  ];
  const collectionTaskResults = [
    ['已采集入库', collectionResult.collected, '去重达人'],
    ['已完成初评', collectionResult.scored, 'ABC 分档'],
    ['初筛可用', collectionResult.passedFilters, '>=90 或高潜'],
    ['需人工判断', collectionResult.needsManual, '风险或低分'],
  ];

  const selectedPgyKeys = useMemo(() => new Set((pgyPlan.filters || []).map(pgyFilterKey)), [pgyPlan.filters]);
  const selectedMetricKeys = useMemo(() => new Set((pgyPlan.display_metrics || []).map(metricKey)), [pgyPlan.display_metrics]);
  const collectionHardFilterOptions = useMemo(
    () => mergeOptionItems(planDraft.collectionHardFilters || [], hardFilterOptionsFor(DEFAULT_COLLECTION_HARD_FILTER_FIELDS), hardFilterKey),
    [planDraft.collectionHardFilters]
  );
  const pgyFilterOptions = useMemo(() => mergeOptionItems(pgyPlan.filters || [], PGY_FILTER_OPTIONS, pgyFilterKey), [pgyPlan.filters]);
  const metricOptions = useMemo(() => mergeOptionItems((pgyPlan.display_metrics || []).map(value => ({ value, label: value })), DISPLAY_METRIC_OPTIONS, item => item.value), [pgyPlan.display_metrics]);
  const planSummary = `${planDraft.collectionHardFilters?.length || 0} 个采集前条件 · ${pgyPlan.filters?.length || 0} 个蒲公英条件 · ${pgyPlan.display_metrics?.length || 0} 个展示指标`;

  const updateWeight = (key, value) => {
    const number = Math.max(0, Number(value || 0));
    setPlanDraft(old => ({ ...old, scoringWeights: { ...(old.scoringWeights || {}), [key]: number } }));
  };

  const togglePgyFilter = (option, checked) => {
    setPlanDraft(old => ({
      ...old,
      pgyCollectionPlan: {
        ...(old.pgyCollectionPlan || {}),
        filters: checked
          ? (old.pgyCollectionPlan?.filters || []).filter(item => pgyFilterKey(item) !== pgyFilterKey(option))
          : [...(old.pgyCollectionPlan?.filters || []), {
              field: option.field,
              value: option.value,
              reason: option.reason || '',
              control_type: option.control_type || '',
              input_values: option.input_values || [],
              pending_detail: option.pending_detail || '',
              sub_field: option.sub_field || '',
              min_items: option.min_items,
            }],
      },
    }));
  };

  const toggleMetric = (option, checked) => {
    const value = option.value || option.label;
    setPlanDraft(old => ({
      ...old,
      pgyCollectionPlan: {
        ...(old.pgyCollectionPlan || {}),
        display_metrics: checked
          ? (old.pgyCollectionPlan?.display_metrics || []).filter(item => item !== value)
          : [...(old.pgyCollectionPlan?.display_metrics || []), value],
      },
    }));
  };

  const applyPlan = async () => {
    setPlanStatus('正在应用筛选计划...');
    try {
      const nextPlan = syncScreeningCriteria(planDraft);
      await onSavePlan?.(nextPlan);
      setPlanDraft(nextPlan);
      setPlanStatus('采集计划已应用，后续采集将使用当前采集前筛选条件');
    } catch (error) {
      setPlanStatus(error.message || '筛选计划应用失败');
    }
  };

  return (
    <div>
      {/* 项目概览 */}
      <div className="card screening-section-card screening-project-summary" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
          <div>
            <h3 style={{ margin: 0, color: 'var(--text-primary)', fontSize: 20 }}>{project.name}</h3>
            <p style={{ margin: '6px 0 0', color: 'var(--text-secondary)', fontSize: 14 }}>{project.product} · {project.period} · <Badge variant={project.poolType === 'shared' ? 'blue' : 'purple'} style={{ marginLeft: 4 }}>{project.poolType === 'shared' ? '共享池' : '独立池'}</Badge></p>
          </div>
          <Badge variant={project.status === '进行中' ? 'blue' : project.status === '已完成' ? 'green' : 'amber'} style={{ fontSize: 13 }}>{project.status}</Badge>
        </div>
        <div className="collection-section-heading">
          <h4><Activity size={16} /> 指标预览</h4>
          <span>基于当前项目达人池与初筛通过率自动推算</span>
        </div>
        <div className="collection-metric-preview-grid">
          {collectionMetrics.map(metric => {
            const Icon = metric.icon;
            return (
              <div key={metric.title} className={`collection-metric-card collection-metric-card-${metric.color}`}>
                <div className="collection-metric-title" title={metric.title}>{metric.title}</div>
                <div className="collection-metric-main">
                  <div className="collection-metric-icon">
                    <Icon size={22} />
                  </div>
                  <strong>{metric.value}</strong>
                </div>
                <div className="collection-metric-subtitle">{metric.subtitle}</div>
              </div>
            );
          })}
        </div>
        <div className="collector-inline-panel">
          <div className="collector-inline-header">
            <h4><Bot size={16} /> 蒲公英采集执行</h4>
            <div className="collector-action-row">
              <button className="btn btn-primary collector-action collector-action-primary" onClick={() => onCollect(syncScreeningCriteria(planDraft))}>
                <Download size={16} />一键采集
              </button>
            </div>
          </div>
          <div className="collector-result-strip">
            {collectionTaskResults.map(([label, value, desc]) => (
              <div key={label} className="collector-result-item">
                <span>{label}</span>
                <strong>{value}</strong>
                <small>{desc}</small>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 当前筛选计划 */}
      <div className="collection-workbench-grid" style={{ marginBottom: 24 }}>
        <div className="card screening-section-card collection-plan-panel">
          <div className="collection-plan-collapsible-header">
            <button type="button" className="collection-plan-collapse-button" onClick={() => setPlanExpanded(value => !value)}>
              <Filter size={16} />
              <span>采集筛选计划</span>
              <small>{planSummary}</small>
              <ChevronDown size={16} className={planExpanded ? 'is-open' : ''} />
            </button>
            <div className="collection-plan-header-badges">
              <Badge variant={planDraft.briefType === 'complex' ? 'amber' : 'blue'}>{planDraft.briefType === 'complex' ? '复杂需求' : '标准需求'}</Badge>
              {planDirty && <Badge variant="purple">未应用</Badge>}
            </div>
          </div>
          {!planExpanded ? (
            <div className="collection-plan-compact">
              <SelectedChips
                items={(planDraft.collectionHardFilters || []).slice(0, 4)}
                getKey={hardFilterKey}
                getLabel={hardFilterLabel}
                onRemove={(item) => setPlanDraft(old => ({ ...old, collectionHardFilters: (old.collectionHardFilters || []).filter(next => hardFilterKey(next) !== hardFilterKey(item)) }))}
                emptyText="暂无采集前条件"
              />
              {(planDraft.collectionHardFilters || []).length > 4 && <span className="collection-compact-more">+{(planDraft.collectionHardFilters || []).length - 4}</span>}
            </div>
          ) : (
            <>
          <div className="collection-plan-block">
            <div className="collection-plan-title-row">
              <div>
                <div className="collection-plan-title">采集前筛选条件</div>
                <div className="collection-plan-subtitle">用于蒲公英采集后的入库前拦截，也会写入采集计划。</div>
              </div>
            </div>
            <HardFilterEditor
              filters={planDraft.collectionHardFilters || []}
              options={collectionHardFilterOptions}
              onChange={(filters) => setPlanDraft(old => ({ ...old, collectionHardFilters: filters }))}
              emptyText="暂无采集前筛选条件，可从可选项添加。"
              fieldHeader="采集筛选项"
              evidenceHeader="蒲公英/入库字段"
              evidencePlaceholder="关联蒲公英或入库字段"
            />
          </div>
          <div className="collection-plan-block">
            <div className="collection-plan-title">评分权重</div>
            <div className="collection-weight-edit-grid">
              {Object.entries(planDraft.scoringWeights || {}).map(([key, value]) => (
                <div key={key} className="collection-weight-edit-item">
                  <label>{WEIGHT_LABELS[key] || key}</label>
                  <input className="input-field" type="number" min="0" max="100" value={value} onChange={e => updateWeight(key, e.target.value)} />
                  <span>%</span>
                </div>
              ))}
            </div>
          </div>
          <div className="collection-plan-block">
            <div className="collection-plan-title-row">
              <div className="collection-plan-title">蒲公英后台筛选条件</div>
              <SelectableMenu
                menuId="pgy"
                openMenu={openPlanMenu}
                setOpenMenu={setOpenPlanMenu}
                label="选择蒲公英条件"
                summary={`${pgyPlan.filters?.length || 0} 已选`}
                options={pgyFilterOptions}
                selectedKeys={selectedPgyKeys}
                getKey={pgyFilterKey}
                getLabel={pgyFilterLabel}
                onToggle={togglePgyFilter}
              />
            </div>
            <PgyFilterCards
              items={pgyPlan.filters || []}
              onRemove={(item) => setPlanDraft(old => ({
                ...old,
                pgyCollectionPlan: {
                  ...(old.pgyCollectionPlan || {}),
                  filters: (old.pgyCollectionPlan?.filters || []).filter(next => pgyFilterKey(next) !== pgyFilterKey(item)),
                },
              }))}
            />
          </div>
          <div className="collection-plan-block">
            <div className="collection-plan-title-row">
              <div className="collection-plan-title">蒲公英展示指标</div>
              <SelectableMenu
                menuId="metrics"
                openMenu={openPlanMenu}
                setOpenMenu={setOpenPlanMenu}
                label="选择展示指标"
                summary={`${pgyPlan.display_metrics?.length || 0} 已选`}
                options={metricOptions}
                selectedKeys={selectedMetricKeys}
                getKey={item => item.value}
                getLabel={item => item.label || item.value}
                onToggle={toggleMetric}
              />
            </div>
            <SelectedChips
              items={(pgyPlan.display_metrics || []).map(value => ({ value, label: value }))}
              getKey={item => item.value}
              getLabel={item => item.label}
              onRemove={(item) => toggleMetric(item, true)}
              emptyText="默认使用全部非直播指标。"
            />
          </div>
            </>
          )}
          <div className="collection-plan-actions">
            <span className={planStatus.includes('失败') ? 'is-error' : ''}>{planStatus || '修改后点击应用，采集会使用当前筛选计划。'}</span>
            <button className="btn btn-primary" onClick={applyPlan} disabled={!planDirty && planStatus.includes('已应用')}>
              <Save size={14} style={{ marginRight: 4 }} />应用计划
            </button>
          </div>
        </div>
      </div>

      {/* 达人池预览 */}
      <div className="card screening-section-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h4 style={{ margin: 0, color: 'var(--text-primary)' }}>采集结果预览 <span style={{ color: 'var(--text-secondary)', fontWeight: 400, fontSize: 14 }}>（{creators.length}人）</span></h4>
          <button className="btn btn-sm btn-secondary" onClick={() => onTabChange('screening-review')}>人工筛选 <ArrowRight size={14} /></button>
        </div>
        <DataTable
          columns={[
            { key: 'name', label: '达人昵称', render: (v, row) => (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--border-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600 }}>{v[0]}</div>
                <span style={{ color: 'var(--text-primary)' }}>{v}</span>
              </div>
            )},
            { key: 'type', label: '类型', render: (v, row) => <Badge variant={row.typeVariant}>{v}</Badge> },
            { key: 'followers', label: '粉丝数' },
            { key: 'quote', label: '报价' },
            { key: 'baseScore', label: '初筛总分', render: v => {
              const tier = getScoreTier(v);
              return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><span style={{ fontWeight: 700, color: getScoreColor(v) }}>{v}</span><Badge variant={tier.variant}>{tier.label}</Badge></span>;
            } },
            { key: 'risk', label: '风险', render: v => v?.length > 0 ? v.map((t, i) => <span key={i} className="tag" style={{ marginRight: 4, fontSize: 11 }}>{t}</span>) : <span style={{ color: 'var(--text-muted)' }}>-</span> },
          ]}
          data={creators.slice(0, 5)}
        />
        {creators.length > 5 && (
          <div style={{ textAlign: 'center', padding: '12px 0 0', borderTop: '1px solid var(--border-primary)' }}>
            <button className="btn btn-sm btn-ghost" onClick={() => onTabChange('screening-review')}>还有 {creators.length - 5} 位达人，进入人工筛选 <ArrowRight size={14} /></button>
          </div>
        )}
      </div>
    </div>
  );
}

// ==================== 筛选工作台 ====================

function ScreeningReviewTab({ project, screeningStatus, setScreeningStatus, onReview, onRefresh, onScore, onImport, onCollect, onCollectDetails, onSavePlan, onTabChange }) {
  const creators = useMemo(() => getProjectCreators(project).map(c => ({
    ...getDefaultCreatorStatus(), ...c, ...(getCreatorStatus(project.id, c.id, screeningStatus) || {})
  })), [project, screeningStatus]);
  const screeningCandidates = useMemo(
    () => creators.filter(c => !['已通过', '已写回飞书', '已驳回', '默认淘汰', '备选'].includes(c.review)),
    [creators]
  );

  const [statusFilter, setStatusFilter] = useState('全部');
  const [tierFilter, setTierFilter] = useState('S');
  const [typeFilter, setTypeFilter] = useState('全部');
  const [searchTerm, setSearchTerm] = useState('');
  const [sortField, setSortField] = useState('baseScore');
  const [sortDir, setSortDir] = useState('desc');
  const [selectedIds, setSelectedIds] = useState([]);
  const [expandedId, setExpandedId] = useState(null);
  const [reviewModal, setReviewModal] = useState(null); // { creator, action }
  const [batchModal, setBatchModal] = useState(null); // { action, creators }
  const [reviewComment, setReviewComment] = useState('');
  const [planDraft, setPlanDraft] = useState(() => normalizeWorkbenchPlan(project.screeningPlan || {}));
  const [planExpanded, setPlanExpanded] = useState(false);
  const [planStatus, setPlanStatus] = useState('');

  useEffect(() => {
    setPlanDraft(normalizeWorkbenchPlan(project.screeningPlan || {}));
    setPlanStatus('');
  }, [project.id, project.screeningPlan]);

  useEffect(() => {
    setSelectedIds([]);
  }, [statusFilter, tierFilter, typeFilter, searchTerm]);

  const filtered = useMemo(() => {
    let list = [...screeningCandidates];
    if (statusFilter !== '全部') list = list.filter(c => c.review === statusFilter);
    list = list.filter(c => getScoreTier(c.baseScore).key === tierFilter);
    if (typeFilter !== '全部') list = list.filter(c => c.type === typeFilter);
    if (searchTerm) list = list.filter(c => c.name.includes(searchTerm));
    list.sort((a, b) => {
      const av = a[sortField], bv = b[sortField];
      if (typeof av === 'number' && typeof bv === 'number') return sortDir === 'desc' ? bv - av : av - bv;
      return sortDir === 'desc' ? String(bv).localeCompare(String(av)) : String(av).localeCompare(String(bv));
    });
    return list;
  }, [screeningCandidates, statusFilter, tierFilter, typeFilter, searchTerm, sortField, sortDir]);

  const stats = useMemo(() => {
    const s = {
      total: screeningCandidates.length,
      passed: creators.filter(c => ['已通过', '已写回飞书'].includes(c.review)).length,
      rejected: creators.filter(c => ['已驳回', '默认淘汰'].includes(c.review)).length,
      backup: 0,
      review: 0,
      pending: 0,
    };
    screeningCandidates.forEach(c => {
      if (c.review === '备选') s.backup++;
      else if (c.review === '人工复核') s.review++;
      else s.pending++;
    });
    return s;
  }, [creators.length, screeningCandidates]);

  const tierStats = useMemo(() => {
    const tiers = {
      S: { label: 'S档', desc: '100分以上，必须补采', count: 0, variant: 'green', color: '#10B981' },
      A: { label: 'A档', desc: '90-99分，优先补采', count: 0, variant: 'blue', color: '#3B82F6' },
      'B+': { label: 'B+档', desc: '80-89分，高潜补采', count: 0, variant: 'amber', color: '#F59E0B' },
      B: { label: 'B档', desc: '70-79分，暂缓补采', count: 0, variant: 'amber', color: '#D97706' },
      C: { label: 'C档', desc: '70分以下，不补采', count: 0, variant: 'red', color: '#EF4444' },
    };
    screeningCandidates.forEach(creator => {
      const tier = getScoreTier(creator.baseScore).key;
      tiers[tier].count += 1;
    });
    return tiers;
  }, [screeningCandidates]);
  const activeTier = tierStats[tierFilter] || null;
  const savedPlan = useMemo(() => normalizeWorkbenchPlan(project.screeningPlan || {}), [project.screeningPlan]);
  const planDirty = JSON.stringify(planDraft.scoringHardFilters || []) !== JSON.stringify(savedPlan.scoringHardFilters || []);
  const scoringHardFilterOptions = useMemo(
    () => mergeOptionItems(planDraft.scoringHardFilters || [], hardFilterOptionsFor(DEFAULT_SCORING_HARD_FILTER_FIELDS), hardFilterKey),
    [planDraft.scoringHardFilters]
  );
  const scoringPlanSummary = `${planDraft.scoringHardFilters?.length || 0} 个评分条件`;

  const applyLocalReviewStatus = (targetCreators, review, reviewVariant, fallbackReason) => {
    const now = new Date().toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-');
    setScreeningStatus(prev => {
      const next = { ...prev, [project.id]: { ...(prev[project.id] || {}) } };
      targetCreators.forEach(creator => {
        next[project.id][creator.id] = {
          review,
          reviewVariant,
          finalScore: creator.baseScore,
          reason: reviewComment || fallbackReason,
          reviewer: '当前用户',
          reviewedAt: now,
        };
      });
      return next;
    });
  };

  const handleReview = async (creator, action) => {
    const status = action === 'pass' ? '已通过' : action === 'reject' ? '已驳回' : action === 'backup' ? '备选' : '待审核';
    const variant = action === 'pass' ? 'green' : action === 'reject' ? 'red' : 'amber';
    const reason = reviewComment || (action === 'pass' ? '人工审核通过' : action === 'reject' ? '人工审核驳回' : '加入备选');
    applyLocalReviewStatus([creator], status, variant, reason);
    if (onReview) {
      await onReview([creator.id], status, reason);
      setReviewModal(null);
      setReviewComment('');
      return;
    }
    setReviewModal(null);
    setReviewComment('');
  };

  const handleBatchPass = async () => {
    const selectedCreators = creators.filter(c => selectedIds.includes(c.id));
    if (!selectedCreators.length) return;
    const reason = reviewComment || '批量通过，进入项目达人池';
    applyLocalReviewStatus(selectedCreators, '已通过', 'green', reason);
    if (onReview) {
      await onReview(selectedCreators.map(c => c.id), '已通过', reason);
      setBatchModal(null);
      setReviewComment('');
      setSelectedIds([]);
      return;
    }
    setBatchModal(null);
    setReviewComment('');
    setSelectedIds([]);
  };

  const handleBatchReject = async () => {
    const selectedCreators = creators.filter(c => selectedIds.includes(c.id));
    if (!selectedCreators.length) return;
    const reason = reviewComment || '批量淘汰，进入观察暂缓池';
    applyLocalReviewStatus(selectedCreators, '已驳回', 'red', reason);
    if (onReview) {
      await onReview(selectedCreators.map(c => c.id), '已驳回', reason);
      setBatchModal(null);
      setReviewComment('');
      setSelectedIds([]);
      return;
    }
    setBatchModal(null);
    setReviewComment('');
    setSelectedIds([]);
  };

  const openBatchModal = (action) => {
    const selectedCreators = creators.filter(c => selectedIds.includes(c.id));
    if (!selectedCreators.length) return;
    setBatchModal({ action, creators: selectedCreators });
    setReviewComment(action === 'pass' ? '批量通过，进入项目达人池' : '批量淘汰，进入观察暂缓池');
  };

  const handleCollectCurrentTierDetails = () => {
    if (!filtered.length || !onCollectDetails) return;
    const segmentLabel = activeTier?.label || `${tierFilter}档`;
    onCollectDetails({
      creatorIds: filtered.map(creator => creator.id),
      segment: tierFilter,
      segmentLabel,
    });
  };

  const applyScoringPlan = async (runScore = false) => {
    setPlanStatus(runScore ? '正在应用评分筛选条件并重新评分...' : '正在应用评分筛选条件...');
    try {
      const nextPlan = syncScreeningCriteria(planDraft);
      await onSavePlan?.(nextPlan);
      setPlanDraft(normalizeWorkbenchPlan(nextPlan));
      if (runScore) {
        await onScore?.();
        setPlanStatus('评分筛选条件已应用，并已触发重新评分');
      } else {
        setPlanStatus('评分筛选条件已应用，后续评分会使用当前条件');
      }
    } catch (error) {
      setPlanStatus(error.message || '评分筛选条件应用失败');
    }
  };

  const toggleSelectCreator = (creatorId) => {
    setSelectedIds(ids => ids.includes(creatorId) ? ids.filter(id => id !== creatorId) : [...ids, creatorId]);
  };

  const filteredIds = filtered.map(creator => creator.id);
  const allFilteredSelected = filteredIds.length > 0 && filteredIds.every(id => selectedIds.includes(id));
  const toggleSelectFiltered = () => {
    setSelectedIds(ids => {
      if (allFilteredSelected) return ids.filter(id => !filteredIds.includes(id));
      return Array.from(new Set([...ids, ...filteredIds]));
    });
  };

  const toggleSort = (field) => {
    if (sortField === field) setSortDir(d => d === 'desc' ? 'asc' : 'desc');
    else { setSortField(field); setSortDir('desc'); }
  };

  const SortIcon = ({ field }) => {
    if (sortField !== field) return <ChevronDown size={12} style={{ color: 'var(--text-muted)', marginLeft: 2 }} />;
    return sortDir === 'desc' ? <ChevronDown size={12} style={{ color: '#3B82F6', marginLeft: 2 }} /> : <ChevronUp size={12} style={{ color: '#3B82F6', marginLeft: 2 }} />;
  };

  const scoreDimLabels = { budget: '预算匹配', fans: '粉丝量级', cpe: 'CPE效率', engagement: '互动质量', persona: '人设匹配', content: '内容风格' };

  return (
    <div>
      <div className="screening-workbench-hero" style={{ marginBottom: 20 }}>
        <div>
          <div className="screening-workbench-eyebrow">Scoring & Human Review</div>
          <h3>筛选工作台</h3>
          <p>展示采集后的初步评分结果，按基础分100+加成分20分层，只让高分/高潜达人进入详情页补采。</p>
        </div>
        <button className="btn btn-primary" onClick={() => onTabChange?.('score-preview')}>
          <Users size={14} />查看项目达人池
        </button>
      </div>

      <div className="screening-tier-grid" style={{ marginBottom: 20 }}>
        {Object.entries(tierStats).map(([key, item]) => (
          <button
            key={key}
            type="button"
            className={`screening-tier-card ${tierFilter === key ? 'is-active' : ''}`}
            onClick={() => setTierFilter(key)}
          >
            <div>
              <Badge variant={item.variant}>{item.label}</Badge>
              <p>{item.desc}</p>
            </div>
            <strong style={{ color: item.color }}>{item.count}</strong>
          </button>
        ))}
      </div>

      <div className="card screening-section-card collection-plan-panel" style={{ marginBottom: 16 }}>
        <div className="collection-plan-collapsible-header">
          <button type="button" className="collection-plan-collapse-button" onClick={() => setPlanExpanded(value => !value)}>
            <Shield size={16} />
            <span>评分筛选条件</span>
            <small>{scoringPlanSummary}</small>
            <ChevronDown size={16} className={planExpanded ? 'is-open' : ''} />
          </button>
          <div className="collection-plan-header-badges">
            {planDirty && <Badge variant="purple">未应用</Badge>}
          </div>
        </div>
        {!planExpanded ? (
          <div className="collection-plan-compact">
            <SelectedChips
              items={(planDraft.scoringHardFilters || []).slice(0, 4)}
              getKey={hardFilterKey}
              getLabel={hardFilterLabel}
              onRemove={(item) => setPlanDraft(old => ({ ...old, scoringHardFilters: (old.scoringHardFilters || []).filter(next => hardFilterKey(next) !== hardFilterKey(item)) }))}
              emptyText="暂无评分筛选条件"
            />
            {(planDraft.scoringHardFilters || []).length > 4 && <span className="collection-compact-more">+{(planDraft.scoringHardFilters || []).length - 4}</span>}
          </div>
        ) : (
          <div className="collection-plan-block">
            <div className="collection-plan-title-row">
              <div>
                <div className="collection-plan-title">评分硬性条件</div>
                <div className="collection-plan-subtitle">用于初筛评分、硬性不符判断和 AI 推荐理由，不影响蒲公英页面采集条件。</div>
              </div>
            </div>
            <HardFilterEditor
              filters={planDraft.scoringHardFilters || []}
              options={scoringHardFilterOptions}
              onChange={(filters) => setPlanDraft(old => ({ ...old, scoringHardFilters: filters }))}
              emptyText="暂无评分筛选条件，可从可选项添加。"
              fieldHeader="评分筛选项"
              evidenceHeader="评分依据字段"
              evidencePlaceholder="关联评分/飞书字段"
            />
          </div>
        )}
        <div className="collection-plan-actions">
          <span className={planStatus.includes('失败') ? 'is-error' : ''}>{planStatus || '平时折叠；修改后应用，重新评分会使用当前条件。'}</span>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button className="btn btn-secondary" onClick={() => applyScoringPlan(false)} disabled={!planDirty && planStatus.includes('已应用')}>
              <Save size={14} style={{ marginRight: 4 }} />应用条件
            </button>
            <button className="btn btn-primary" onClick={() => applyScoringPlan(true)}>
              <Sparkles size={14} style={{ marginRight: 4 }} />应用并重新评分
            </button>
          </div>
        </div>
      </div>

      {/* 工具栏 */}
      <div className="card" style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <div className="search-box" style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input className="search-input" placeholder="搜索达人..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)} style={{ paddingLeft: 30, width: 160 }} />
          </div>
          <select className="select-field" style={{ width: 120 }} value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
            <option value="全部">全部状态</option>
            <option value="待审核">待审核</option>
            <option value="已通过">已通过</option>
            <option value="已驳回">已驳回</option>
            <option value="备选">备选</option>
            <option value="人工复核">人工复核</option>
          </select>
          <select className="select-field" style={{ width: 110 }} value={tierFilter} onChange={e => setTierFilter(e.target.value)}>
            <option value="S">S档</option>
            <option value="A">A档</option>
            <option value="B+">B+档</option>
            <option value="B">B档</option>
            <option value="C">C档</option>
          </select>
          <select className="select-field" style={{ width: 100 }} value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
            <option value="全部">全部类型</option>
            <option value="KOL">KOL</option>
            <option value="KOC">KOC</option>
          </select>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-sm btn-secondary" onClick={onImport}><Upload size={14} style={{ marginRight: 4 }} />导入模板</button>
          <button className="btn btn-sm btn-secondary" onClick={onCollect}><Bot size={14} style={{ marginRight: 4 }} />蒲公英采集</button>
          <button className="btn btn-sm btn-secondary" onClick={onScore}><Sparkles size={14} style={{ marginRight: 4 }} />重新评分</button>
          <button
            className="btn btn-sm btn-primary"
            onClick={handleCollectCurrentTierDetails}
            disabled={!filtered.length}
            title={`批量完善当前${activeTier?.label || tierFilter}分段的达人详情页`}
          >
            <FileText size={14} style={{ marginRight: 4 }} />完善{activeTier?.label || tierFilter}{filtered.length ? ` ${filtered.length}` : ''}
          </button>
          <button className="btn btn-sm btn-ghost" onClick={onRefresh}><RefreshCw size={14} /></button>
          <button className="btn btn-sm btn-secondary" onClick={() => openBatchModal('pass')} disabled={!selectedIds.length} title="批量通过当前勾选达人"><UserCheck size={14} style={{ marginRight: 4 }} />批量通过{selectedIds.length ? ` ${selectedIds.length}` : ''}</button>
          <button className="btn btn-sm btn-danger" onClick={() => openBatchModal('reject')} disabled={!selectedIds.length} title="批量淘汰当前勾选达人"><UserX size={14} style={{ marginRight: 4 }} />批量淘汰{selectedIds.length ? ` ${selectedIds.length}` : ''}</button>
        </div>
      </div>

      {/* 达人列表 */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-primary)' }}>
              <th style={{ padding: '12px 8px 12px 16px', width: 42, textAlign: 'center' }}>
                <input
                  type="checkbox"
                  checked={allFilteredSelected}
                  disabled={!filtered.length}
                  onChange={toggleSelectFiltered}
                  aria-label="选择当前列表达人"
                />
              </th>
              <th style={{ padding: '12px 16px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>达人</th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>类型</th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12, cursor: 'pointer' }} onClick={() => toggleSort('followersNum')}>粉丝数 <SortIcon field="followersNum" /></th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12, cursor: 'pointer' }} onClick={() => toggleSort('quoteNum')}>报价 <SortIcon field="quoteNum" /></th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12, cursor: 'pointer' }} onClick={() => toggleSort('baseScore')}>初筛总分 <SortIcon field="baseScore" /></th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>档位</th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>风险</th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>审核状态</th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>审核意见</th>
              <th style={{ padding: '12px 16px', textAlign: 'center', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(creator => (
              <React.Fragment key={creator.id}>
                <tr style={{ borderBottom: '1px solid var(--border-primary)', cursor: 'pointer', transition: 'background 0.15s' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                  <td style={{ padding: '12px 8px 12px 16px', textAlign: 'center' }}>
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(creator.id)}
                      onChange={() => toggleSelectCreator(creator.id)}
                      onClick={e => e.stopPropagation()}
                      aria-label={`选择${creator.name}`}
                    />
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{ width: 32, height: 32, borderRadius: '50%', background: '#243147', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: '#FFFFFF', fontWeight: 600, flexShrink: 0 }}>{creator.name[0]}</div>
                      <div>
                        <div style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{creator.name}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>ID: {creator.id}</div>
                      </div>
                    </div>
                  </td>
                  <td style={{ padding: '12px' }}><Badge variant={creator.typeVariant}>{creator.type}</Badge></td>
                  <td style={{ padding: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>{creator.followers}</td>
                  <td style={{ padding: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>{creator.quote}</td>
                  <td style={{ padding: '12px' }}>
                    <span style={{ fontWeight: 700, fontSize: 15, color: getScoreColor(creator.baseScore) }}>{creator.baseScore}</span>
                    <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>
                      基础 {creator.baseOnlyScore || 0} + 加成 {creator.bonusScore || 0} · 完整度 {creator.informationCompletenessLabel}
                    </span>
                  </td>
                  <td style={{ padding: '12px' }}>
                    {(() => {
                      const tier = getScoreTier(creator.baseScore);
                      return <Badge variant={tier.variant}>{tier.label} · {tier.text}</Badge>;
                    })()}
                    {creator.detailCollectionPriority && <Badge variant="default">{creator.detailCollectionPriority}</Badge>}
                  </td>
                  <td style={{ padding: '12px' }}>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {creator.risk.map((t, i) => <span key={i} className="tag" style={{ fontSize: 10, color: t.includes('无') || t.includes('低') || t.includes('过多') || t.includes('低') ? '#EF4444' : '#F59E0B' }}>{t}</span>)}
                    </div>
                  </td>
                  <td style={{ padding: '12px' }}><Badge variant={getReviewVariant(creator.review)}>{creator.review}</Badge></td>
                  <td style={{ padding: '12px', maxWidth: 140 }}>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{creator.reason || '-'}</div>
                    {creator.reviewer && <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{creator.reviewer} · {creator.reviewedAt}</div>}
                  </td>
                  <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                    <div style={{ display: 'flex', gap: 4, justifyContent: 'center' }}>
                      {creator.review === '待审核' ? (
                        <>
                          <button className="btn btn-sm btn-ghost" style={{ color: '#10B981' }} onClick={(e) => { e.stopPropagation(); setReviewModal({ creator, action: 'pass' }); }} title="通过"><UserCheck size={15} /></button>
                          <button className="btn btn-sm btn-ghost" style={{ color: '#EF4444' }} onClick={(e) => { e.stopPropagation(); setReviewModal({ creator, action: 'reject' }); }} title="驳回"><UserX size={15} /></button>
                          <button className="btn btn-sm btn-ghost" style={{ color: '#F59E0B' }} onClick={(e) => { e.stopPropagation(); setReviewModal({ creator, action: 'backup' }); }} title="备选"><Bookmark size={15} /></button>
                        </>
                      ) : (
                        <button className="btn btn-sm btn-ghost" style={{ color: 'var(--text-secondary)' }} onClick={(e) => { e.stopPropagation(); setReviewModal({ creator, action: 'reset' }); }} title="重置"><RotateCcw size={15} /></button>
                      )}
                      <button className="btn btn-sm btn-ghost" onClick={(e) => { e.stopPropagation(); setExpandedId(expandedId === creator.id ? null : creator.id); }}><ChevronDown size={15} style={{ transform: expandedId === creator.id ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} /></button>
                    </div>
                  </td>
                </tr>
                {expandedId === creator.id && (
                  <tr style={{ background: 'var(--bg-raised)' }}>
                    <td colSpan={11} style={{ padding: '16px 24px', borderBottom: '1px solid var(--border-primary)' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
                        {/* 评分维度 */}
                        <div>
                          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12, fontWeight: 600 }}>评分维度明细</div>
                          {creator.scores && Object.entries(creator.scores).map(([key, val]) => (
                            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                              <span style={{ fontSize: 12, color: 'var(--text-secondary)', width: 70, flexShrink: 0 }}>{scoreDimLabels[key] || key}</span>
                              <div style={{ flex: 1, height: 6, background: 'var(--bg-elevated)', borderRadius: 3, overflow: 'hidden' }}>
                                <div style={{ width: `${val}%`, height: '100%', background: getScoreColor(val), borderRadius: 3, transition: 'width 0.3s' }} />
                              </div>
                              <span style={{ fontSize: 12, fontWeight: 600, color: getScoreColor(val), width: 28, textAlign: 'right' }}>{val}</span>
                            </div>
                          ))}
                        </div>
                        {/* AI 推荐理由 */}
                        <div>
                          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12, fontWeight: 600 }}>AI 推荐理由</div>
                          <div style={{ padding: 12, background: 'var(--bg-secondary)', borderRadius: 8, borderLeft: '3px solid #8B5CF6' }}>
                            <p style={{ margin: 0, color: 'var(--text-primary)', fontSize: 13, lineHeight: 1.7 }}>{creator.aiReason || '暂无 AI 评估'}</p>
                          </div>
                          {creator.risk.length > 0 && (
                            <div style={{ marginTop: 12 }}>
                              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>风险提示</div>
                              {creator.risk.map((r, i) => (
                                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                                  <AlertTriangle size={12} style={{ color: '#F59E0B', flexShrink: 0 }} />
                                  <span style={{ fontSize: 12, color: 'var(--text-primary)' }}>{r}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-secondary)' }}>
            <Users size={32} style={{ marginBottom: 8 }} />
            <div>暂无匹配达人</div>
          </div>
        )}
        <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border-primary)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12, color: 'var(--text-secondary)' }}>
          <span>共 {filtered.length} 位达人，已勾选 {selectedIds.length} 位</span>
          <span>筛选自 {screeningCandidates.length} 位待筛候选，已入池 {stats.passed} 位</span>
        </div>
      </div>

      {/* 审核确认弹窗 */}
      {batchModal && (
        <div className="modal-overlay" onClick={() => setBatchModal(null)}>
          <div className="modal" style={{ maxWidth: 680 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>
                {batchModal.action === 'pass' ? '确认批量通过' : '确认批量淘汰'}
              </h3>
              <button className="btn btn-ghost btn-sm modal-close" onClick={() => setBatchModal(null)}><X size={16} /></button>
            </div>
            <div className="modal-body">
              <div style={{ marginBottom: 12, color: 'var(--text-secondary)', fontSize: 13 }}>
                本次将处理 {batchModal.creators.length} 位已勾选达人，确认后会从筛选工作台移出，并进入
                {batchModal.action === 'pass' ? '「项目达人池」' : '「观察暂缓」'}。
              </div>
              <div className="batch-review-list">
                {batchModal.creators.map(creator => {
                  const tier = getScoreTier(creator.baseScore);
                  return (
                    <div key={creator.id} className="batch-review-item">
                      <div className="batch-review-avatar">{creator.name[0]}</div>
                      <div className="batch-review-main">
                        <strong>{creator.name}</strong>
                        <span>{creator.type} · {creator.followers} · {creator.quote}</span>
                      </div>
                      <Badge variant={tier.variant}>{tier.label}</Badge>
                      <span style={{ color: getScoreColor(creator.baseScore), fontWeight: 700 }}>{creator.baseScore}</span>
                    </div>
                  );
                })}
              </div>
              <div style={{ marginTop: 16 }}>
                <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>批量处理备注</label>
                <textarea className="input-field" rows={3} value={reviewComment} onChange={e => setReviewComment(e.target.value)} placeholder="请输入批量处理意见..." style={{ resize: 'none' }} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setBatchModal(null)}>取消</button>
              <button className={`btn ${batchModal.action === 'pass' ? 'btn-primary' : 'btn-danger'}`} onClick={batchModal.action === 'pass' ? handleBatchPass : handleBatchReject}>
                {batchModal.action === 'pass' ? '确认通过并移入达人池' : '确认淘汰并移入观察暂缓'}
              </button>
            </div>
          </div>
        </div>
      )}

      {reviewModal && (
        <div className="modal-overlay" onClick={() => setReviewModal(null)}>
          <div className="modal" style={{ maxWidth: 420 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>
                {reviewModal.action === 'pass' && '确认通过'}
                {reviewModal.action === 'reject' && '确认驳回'}
                {reviewModal.action === 'backup' && '加入备选'}
                {reviewModal.action === 'reset' && '重置审核'}
              </h3>
              <button className="btn btn-ghost btn-sm modal-close" onClick={() => setReviewModal(null)}><X size={16} /></button>
            </div>
            <div className="modal-body">
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, padding: 12, background: 'var(--bg-elevated)', borderRadius: 8 }}>
                <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--border-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, color: 'var(--text-secondary)', fontWeight: 600 }}>{reviewModal.creator.name[0]}</div>
                <div>
                  <div style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{reviewModal.creator.name}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{reviewModal.creator.type} · {reviewModal.creator.followers} · 初筛总分 {reviewModal.creator.baseScore}</div>
                </div>
              </div>
              <div>
                <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>审核备注</label>
                <textarea className="input-field" rows={3} value={reviewComment} onChange={e => setReviewComment(e.target.value)} placeholder="请输入审核意见..." style={{ resize: 'none' }} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setReviewModal(null)}>取消</button>
              {reviewModal.action === 'reset' ? (
                <button className="btn btn-primary" onClick={() => {
                  const newStatus = { ...screeningStatus };
                  if (newStatus[project.id]) delete newStatus[project.id][reviewModal.creator.id];
                  setScreeningStatus(newStatus);
                  setReviewModal(null);
                }}>确认重置</button>
              ) : (
                <button className={`btn ${reviewModal.action === 'pass' ? 'btn-primary' : reviewModal.action === 'reject' ? 'btn-danger' : 'btn-secondary'}`}
                  onClick={() => handleReview(reviewModal.creator, reviewModal.action)}>
                  {reviewModal.action === 'pass' ? '确认通过' : reviewModal.action === 'reject' ? '确认驳回' : '确认备选'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ==================== 项目达人池 ====================

function ScorePreviewTab({ project, screeningStatus, onCollectDetails }) {
  const [poolData, setPoolData] = useState(null);
  const [poolMessage, setPoolMessage] = useState('');
  const creators = useMemo(() => {
    if (poolData?.groups) {
      return Object.values(poolData.groups).flat().map(mapBackendCreator);
    }
    return getProjectCreators(project).map((creator, index) => ({
      ...creator,
      ...(getCreatorStatus(project.id, creator.id, screeningStatus) || {}),
      poolStage: getPoolStage({ ...creator, ...(getCreatorStatus(project.id, creator.id, screeningStatus) || {}) }, index),
    }));
  }, [poolData, project, screeningStatus]);
  const [activeStage, setActiveStage] = useState('已合作跟进中');
  const [collectionDateFilter, setCollectionDateFilter] = useState('全部');
  const [activeTagFilter, setActiveTagFilter] = useState('');
  const [expandedId, setExpandedId] = useState(null);
  const [updateLogs, setUpdateLogs] = useState({});
  const [writebackSettings, setWritebackSettings] = useState({ auto_writeback_enabled: false });
  const [writebackBusy, setWritebackBusy] = useState(false);
  const [detailBusy, setDetailBusy] = useState(false);

  const stageConfig = {
    '已合作跟进中': { variant: 'green', icon: <RefreshCw size={14} />, desc: '已确认合作，持续追踪近期数据变化' },
    '合格达人待合作': { variant: 'blue', icon: <UserCheck size={14} />, desc: '人工筛选合格，等待排期或商务推进' },
    '待建联达人': { variant: 'amber', icon: <MessageSquare size={14} />, desc: '需要媒介建联并确认档期报价' },
    '观察暂缓': { variant: 'neutral', icon: <Clock size={14} />, desc: '低分或风险项较多，暂不进入合作池' },
  };

  const collectionDateOptions = useMemo(() => {
    const counts = new Map();
    creators.forEach(creator => {
      const key = getDateKey(getCreatorCollectedAt(creator));
      if (key) counts.set(key, (counts.get(key) || 0) + 1);
    });
    return Array.from(counts.entries()).sort((a, b) => b[0].localeCompare(a[0]));
  }, [creators]);

  const dateFilteredCreators = useMemo(() => {
    if (collectionDateFilter === '全部') return creators;
    return creators.filter(creator => getDateKey(getCreatorCollectedAt(creator)) === collectionDateFilter);
  }, [collectionDateFilter, creators]);

  useEffect(() => {
    if (collectionDateFilter !== '全部' && !collectionDateOptions.some(([date]) => date === collectionDateFilter)) {
      setCollectionDateFilter('全部');
    }
  }, [collectionDateFilter, collectionDateOptions]);

  const grouped = useMemo(() => {
    const result = Object.fromEntries(Object.keys(stageConfig).map(stage => [stage, []]));
    if (poolData?.groups) {
      Object.entries(poolData.groups).forEach(([stage, items]) => {
        result[stage] = (items || [])
          .map(mapBackendCreator)
          .filter(creator => collectionDateFilter === '全部' || getDateKey(getCreatorCollectedAt(creator)) === collectionDateFilter)
          .filter(creator => creatorHasTag(creator, activeTagFilter));
      });
      return result;
    }
    dateFilteredCreators.forEach((creator, index) => {
      if (!creatorHasTag(creator, activeTagFilter)) return;
      const stage = getPoolStage(creator, index);
      if (!result[stage]) result[stage] = [];
      result[stage].push(creator);
    });
    Object.values(result).forEach(list => list.sort((a, b) => b.baseScore - a.baseScore));
    return result;
  }, [activeTagFilter, collectionDateFilter, dateFilteredCreators, poolData]);

  const visibleStages = [activeStage];
  const activeStageCreators = grouped[activeStage] || [];
  const activeStageTotal = useMemo(() => {
    if (poolData?.groups) {
      return (poolData.groups[activeStage] || [])
        .map(mapBackendCreator)
        .filter(creator => collectionDateFilter === '全部' || getDateKey(getCreatorCollectedAt(creator)) === collectionDateFilter)
        .length;
    }
    return dateFilteredCreators.filter(creator => getPoolStage(creator) === activeStage).length;
  }, [activeStage, collectionDateFilter, dateFilteredCreators, poolData]);
  const avgScore = poolData?.stats?.avg_score ?? (creators.length ? (creators.reduce((sum, creator) => sum + Number(creator.baseScore || 0), 0) / creators.length).toFixed(1) : '0.0');

  const loadCreatorPool = useCallback(async () => {
    setPoolMessage('读取达人池中...');
    try {
      const payload = await api(`/api/projects/${project.id}/creator-pool`);
      setPoolData(payload);
      setPoolMessage('');
    } catch (error) {
      setPoolMessage(error.message || '读取达人池失败');
    }
  }, [project.id]);

  const loadWritebackSettings = useCallback(async () => {
    try {
      const payload = await api(`/api/projects/feishu/writeback-settings?project_id=${project.id}`);
      setWritebackSettings(payload.settings || { auto_writeback_enabled: false });
    } catch (error) {
      setPoolMessage(error.message || '读取写回设置失败');
    }
  }, [project.id]);

  useEffect(() => {
    loadCreatorPool();
    loadWritebackSettings();
  }, [loadCreatorPool, loadWritebackSettings]);

  const handleToggleAutoWriteback = async () => {
    const nextEnabled = !writebackSettings.auto_writeback_enabled;
    setWritebackBusy(true);
    try {
      const payload = await api('/api/projects/feishu/writeback-settings', {
        method: 'POST',
        body: JSON.stringify({ project_id: project.id, auto_writeback_enabled: nextEnabled }),
      });
      setWritebackSettings(payload.settings || { auto_writeback_enabled: nextEnabled });
      setPoolMessage(nextEnabled ? '已开启自动写回：合格达人完成详情补采后会写入飞书' : '已关闭自动写回：可手动批量写入合格达人');
    } catch (error) {
      setPoolMessage(error.message || '写回设置保存失败');
    } finally {
      setWritebackBusy(false);
    }
  };

  const handleManualWriteback = async () => {
    setWritebackBusy(true);
    setPoolMessage('正在批量写回合格达人...');
    try {
      const payload = await api('/api/projects/feishu/writeback', {
        method: 'POST',
        body: JSON.stringify({ project_id: project.id, quality_only: true, rows: [] }),
      });
      await loadCreatorPool();
      setPoolMessage(`已写回 ${payload.written_count || 0} 位合格达人`);
    } catch (error) {
      setPoolMessage(error.message || '写回飞书失败');
    } finally {
      setWritebackBusy(false);
    }
  };

  const handleUpdateCreator = async (creator) => {
    const now = new Date().toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-');
    const nextFollowers = Math.max(0, Number(creator.followersNum || 0) + 320);
    try {
      await api(`/api/projects/${project.id}/creator-pool/${creator.id}/update-metrics`, {
        method: 'POST',
        body: JSON.stringify({ data: { followers_count: nextFollowers }, operator: '当前用户' }),
      });
      setUpdateLogs(prev => ({
        ...prev,
        [creator.id]: [
          { time: now, metrics: getCreatorUpdateLog({ ...creator, followersNum: nextFollowers }, (prev[creator.id] || []).length), operator: '当前用户' },
          ...(prev[creator.id] || []),
        ],
      }));
      await loadCreatorPool();
      setPoolMessage('数据已更新并写入历史快照');
    } catch (error) {
      setPoolMessage(error.message || '更新达人数据失败');
    } finally {
      setExpandedId(creator.id);
    }
  };

  const handleExportCsv = () => {
    window.open(`/api/projects/${project.id}/exports/creator-pool.csv`, '_blank');
  };

  const handleCollectPoolDetails = async (targetCreators, label) => {
    if (!targetCreators.length || !onCollectDetails) return;
    setDetailBusy(true);
    setPoolMessage(`正在完善${label}详情...`);
    try {
      await onCollectDetails({
        creatorIds: targetCreators.map(creator => creator.id),
        segment: `pool:${label}`,
        segmentLabel: label,
      });
      await loadCreatorPool();
      setPoolMessage(`已提交${label}详情页完善，共 ${targetCreators.length} 位达人`);
    } finally {
      setDetailBusy(false);
    }
  };

  const handleTagFilter = (tag) => {
    setActiveTagFilter(current => (current === tag ? '' : tag));
    setExpandedId(null);
  };

  return (
    <div>
      <div className="creator-pool-hero" style={{ marginBottom: 20 }}>
        <div>
          <div className="creator-pool-eyebrow">Project Creator Pool</div>
          <h3>项目达人池</h3>
          <p>沉淀当前项目可合作达人，按合作进度分层管理，并保留合作中达人的近期数据更新记录。</p>
        </div>
        <div className="creator-pool-hero-stats">
          <div><strong>{creators.length}</strong><span>池内达人</span></div>
          <div><strong>{avgScore}</strong><span>平均评分</span></div>
          <div><strong>{grouped['已合作跟进中']?.length || 0}</strong><span>跟进中</span></div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>{poolMessage || `后端达人池已同步至 ${poolData?.updated_at || '当前页面'}`}</span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <select
            className="select-field"
            style={{ width: 168 }}
            value={collectionDateFilter}
            onChange={event => setCollectionDateFilter(event.target.value)}
          >
            <option value="全部">全部采集日期</option>
            {collectionDateOptions.map(([date, count]) => (
              <option key={date} value={date}>{formatDateLabel(date)} · {count}人</option>
            ))}
          </select>
          <button
            className={`creator-pool-writeback-toggle ${writebackSettings.auto_writeback_enabled ? 'is-on' : ''}`}
            onClick={handleToggleAutoWriteback}
            disabled={writebackBusy}
            title="开启后，详情补采完成且评分合格的真实达人会自动写入飞书"
          >
            {writebackSettings.auto_writeback_enabled ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
            <span>{writebackSettings.auto_writeback_enabled ? '自动写回已开' : '自动写回已关'}</span>
          </button>
          <button className="btn btn-sm btn-secondary" onClick={handleManualWriteback} disabled={writebackBusy}>
            <FileSpreadsheet size={14} />写回合格达人
          </button>
          <button
            className="btn btn-sm btn-primary"
            onClick={() => handleCollectPoolDetails(activeStageCreators, activeStage)}
            disabled={detailBusy || !activeStageCreators.length}
            title="手动完善当前分组内所有达人详情，不受自动补采优先级限制"
          >
            <FileText size={14} />完善当前分组{activeStageCreators.length ? ` ${activeStageCreators.length}` : ''}
          </button>
          <button className="btn btn-sm btn-secondary" onClick={loadCreatorPool}><RefreshCw size={14} />刷新</button>
          <button className="btn btn-sm btn-primary" onClick={handleExportCsv}><Download size={14} />导出 CSV</button>
        </div>
      </div>

      <div className="creator-pool-stage-tabs" style={{ marginBottom: 16 }}>
        {Object.keys(stageConfig).map(stage => (
          <button key={stage} className={activeStage === stage ? 'is-active' : ''} onClick={() => setActiveStage(stage)}>
            {stageConfig[stage].icon}
            <span>{stage}</span>
            <strong>{grouped[stage]?.length || 0}</strong>
          </button>
        ))}
      </div>

      <div className="creator-pool-board">
        {visibleStages.map(stage => {
          const cfg = stageConfig[stage];
          const stageCreators = grouped[stage] || [];
          return (
            <section key={stage} className="creator-pool-section">
              <div className="creator-pool-section-head">
                <div>
                  <h4>{cfg.icon}{stage}<Badge variant={cfg.variant}>{stageCreators.length}人</Badge></h4>
                  <p>{cfg.desc}</p>
                </div>
              </div>
              {activeTagFilter && (
                <div className="creator-pool-filter-bar">
                  <span>已筛选标签</span>
                  <strong>{activeTagFilter}</strong>
                  <em>{stageCreators.length}/{activeStageTotal} 人</em>
                  <button type="button" onClick={() => setActiveTagFilter('')}>清除</button>
                </div>
              )}
              {stageCreators.length === 0 ? (
                <div className="creator-pool-empty">{activeTagFilter ? `暂无「${activeTagFilter}」标签达人` : '暂无达人'}</div>
              ) : (
                <div className="creator-pool-grid">
                  {stageCreators.map((creator, index) => {
                    const tier = getScoreTier(creator.baseScore);
                    const logs = updateLogs[creator.id] || (stage === '已合作跟进中' ? [{ time: '2026-05-09 10:00:00', metrics: getCreatorUpdateLog(creator, index), operator: '系统同步' }] : []);
                    const avatarUrl = getCreatorAvatarUrl(creator);
                    const location = getCreatorLocation(creator);
                    const category = getCreatorCategory(creator);
                    const xhsId = getCreatorXhsId(creator);
                    const intro = getCreatorIntro(creator);
                    const tags = getCreatorTags(creator);
                    const platformMark = String(creator.type || '达').replace(/[\/\s].*$/, '').slice(0, 2);
                    const pgyUrl = getPgyUrl(creator);
                    const collectedAt = getCreatorCollectedAt(creator);
                    return (
                      <article key={creator.id} className="creator-pool-card">
                        <div className="creator-pool-profile">
                          <div className="creator-pool-avatar-wrap">
                            {avatarUrl ? (
                              <img className="creator-pool-photo" src={avatarUrl} alt={creator.name} />
                            ) : (
                              <div className="creator-pool-photo creator-pool-photo-fallback">{creator.name[0]}</div>
                            )}
                            <span className="creator-pool-platform-mark">{platformMark}</span>
                          </div>
                          <div className="creator-pool-profile-main">
                            <div className="creator-pool-title-line">
                              <span className="creator-pool-name-hover">
                                {pgyUrl ? (
                                  <a className="creator-pool-name-link" href={pgyUrl} target="_blank" rel="noreferrer" onClick={event => event.stopPropagation()}>
                                    {creator.name}<ExternalLink size={13} />
                                  </a>
                                ) : (
                                  <span className="creator-pool-name-link creator-pool-name-link-disabled">
                                    {creator.name}
                                  </span>
                                )}
                                <span className="creator-pool-profile-popover" role="tooltip">
                                  <strong>{creator.name}</strong>
                                  <span>{intro}</span>
                                </span>
                              </span>
                              <span className="creator-pool-location">{location}</span>
                              <Badge variant="neutral">{category}</Badge>
                            </div>
                            <div className="creator-pool-xhs-line">
                              <span>小红书号：</span>
                              <strong>{xhsId}</strong>
                              <Copy size={13} />
                            </div>
                            <div className="creator-pool-intro">{intro}</div>
                          </div>
                          <div className="creator-pool-score-panel">
                            <div className="creator-pool-score" style={{ color: getScoreColor(creator.baseScore) }}>{creator.baseScore}</div>
                            <span>{tier.label}</span>
                          </div>
                        </div>

                        <div className="creator-pool-card-meta">
                          <span className="creator-pool-stat"><strong>{creator.followers}</strong><em>粉丝</em></span>
                          <span className="creator-pool-stat"><strong>{creator.quote}</strong><em>报价</em></span>
                          <span className="creator-pool-stat"><strong>{formatDateLabel(collectedAt)}</strong><em>采集时间</em></span>
                          <Badge variant={tier.variant}>{tier.text}</Badge>
                          <Badge variant={getReviewVariant(creator.review)}>{creator.review || '待审核'}</Badge>
                        </div>

                        <div className="creator-pool-risk-row">
                          {tags.length
                            ? tags.map(item => (
                              <button
                                type="button"
                                className={`tag creator-pool-tag ${activeTagFilter === item ? 'is-active' : ''}`}
                                key={item}
                                onClick={() => handleTagFilter(item)}
                                title={`筛选${item}标签达人`}
                              >
                                {item}
                              </button>
                            ))
                            : <span className="creator-pool-safe">暂无明显风险</span>}
                        </div>

                        <div className="creator-pool-actions">
                          <button
                            className="btn btn-sm btn-secondary"
                            onClick={() => handleCollectPoolDetails([creator], creator.name)}
                            disabled={detailBusy}
                            title="手动完善该达人详情，不受自动补采优先级限制"
                          >
                            <FileText size={13} />完善详情
                          </button>
                          {stage === '已合作跟进中' && (
                            <button className="btn btn-sm btn-primary" onClick={() => handleUpdateCreator(creator)}>
                              <RefreshCw size={13} />更新数据
                            </button>
                          )}
                          {stage === '合格达人待合作' && (
                            <button className="btn btn-sm btn-secondary"><Calendar size={13} />排期沟通</button>
                          )}
                          {stage === '待建联达人' && (
                            <button className="btn btn-sm btn-secondary"><MessageSquare size={13} />记录建联</button>
                          )}
                          <button className="btn btn-sm btn-ghost" onClick={() => setExpandedId(expandedId === creator.id ? null : creator.id)}>
                            {expandedId === creator.id ? '收起' : '详情'}<ChevronDown size={13} style={{ transform: expandedId === creator.id ? 'rotate(180deg)' : 'none' }} />
                          </button>
                        </div>

                        {expandedId === creator.id && (
                          <div className="creator-pool-detail">
                            <div className="creator-pool-detail-title">近期数据记录</div>
                            {logs.length ? logs.map((log, logIndex) => (
                              <div className="creator-pool-log" key={`${creator.id}-${log.time}-${logIndex}`}>
                                <div className="creator-pool-log-head">
                                  <span>{log.time}</span>
                                  <strong>{log.operator}</strong>
                                </div>
                                <div className="creator-pool-log-metrics">
                                  {log.metrics.map(metric => (
                                    <div key={metric.label} className={metric.direction === 'up' ? 'is-up' : 'is-down'}>
                                      <span>{metric.label}</span>
                                      <strong>{metric.value}</strong>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )) : (
                              <div className="creator-pool-no-log">暂无更新记录，进入合作后可在此追踪数据变化。</div>
                            )}
                          </div>
                        )}
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          );
        })}
      </div>
    </div>
  );
}

// ==================== 立项 + 标准 + 飞书绑定 ====================

function ProjectSetupTab({ project, feishuConfig, feishuFields, feishuTables, onSaveProject, onSaveScreeningPlan, onSaveFeishu, onTestFeishu, onLoadTables, onLoadFields, onWriteBack }) {
  const [activeSection, setActiveSection] = useState('info');
  const [screeningPlan, setScreeningPlan] = useState(project.screeningPlan || {});
  const [standardStatus, setStandardStatus] = useState('');
  const [feishuTestResult, setFeishuTestResult] = useState(null);
  const [optimizingStandard, setOptimizingStandard] = useState(false);
  const [form, setForm] = useState({
    name: project.name, product: project.product, budget: project.budget,
    singleBudget: project.singleBudget || '', creatorCount: project.creatorCount,
    periodStart: project.periodStart || '', periodEnd: project.periodEnd || '',
    cooperationType: project.cooperationType || '合作笔记', description: project.description,
  });
  const [saved, setSaved] = useState(false);
  const [savingStandard, setSavingStandard] = useState(false);
  const [feishuForm, setFeishuForm] = useState({
    feishu_url: feishuConfig?.feishu_url || project.feishuBinding?.tableUrl || '',
    app_id: feishuConfig?.app_id || '',
    app_secret: '',
    table_id: project.feishuBinding?.tableId || '',
  });

  useEffect(() => {
    setScreeningPlan(normalizeWorkbenchPlan(project.screeningPlan || {}));
    setFeishuForm(old => ({
      ...old,
      feishu_url: feishuConfig?.feishu_url || project.feishuBinding?.tableUrl || '',
      app_id: feishuConfig?.app_id || old.app_id || '',
      table_id: project.feishuBinding?.tableId || old.table_id || '',
    }));
  }, [feishuConfig, project.feishuBinding?.tableId, project.feishuBinding?.tableUrl, project.screeningPlan]);

  useEffect(() => {
    setForm({
      name: project.name,
      product: project.product,
      budget: project.budget,
      singleBudget: project.singleBudget || '',
      creatorCount: project.creatorCount,
      periodStart: project.periodStart || '',
      periodEnd: project.periodEnd || '',
      cooperationType: project.cooperationType || '合作笔记',
      description: project.brief?.description || project.description || '',
    });
  }, [
    project.id,
    project.name,
    project.product,
    project.budget,
    project.singleBudget,
    project.creatorCount,
    project.periodStart,
    project.periodEnd,
    project.cooperationType,
    project.description,
    project.brief?.description,
  ]);

  const sections = [
    { key: 'info', label: '立项信息', icon: <FileText size={14} /> },
    { key: 'standard', label: '量化标准', icon: <Target size={14} /> },
    { key: 'feishu', label: '飞书绑定', icon: <Link2 size={14} /> },
  ];

  const labelStyle = { fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 };

  const runFeishuTest = async () => {
    if (!onTestFeishu) return;
    try {
      const result = await onTestFeishu(feishuForm);
      setFeishuTestResult(result);
    } catch (error) {
      setFeishuTestResult(error.detail || { ok: false, message: error.message });
    }
  };

  const optimizeStandard = async () => {
    setOptimizingStandard(true);
    setStandardStatus('正在保存 Brief，并读取飞书字段生成量化标准...');
    try {
      if (onSaveProject) {
        await onSaveProject({
          project_name: form.name,
          target_qualified_creator_count: Number(form.creatorCount || 10),
          period_start: form.periodStart,
          period_end: form.periodEnd,
          brief: form.description,
        });
      }
      let fields = feishuFields || [];
      if ((!fields || fields.length === 0) && onLoadFields) {
        await onLoadFields(feishuForm.table_id);
        const data = await api(`/api/projects/feishu/fields?project_id=${project.id}${feishuForm.table_id ? `&table_id=${feishuForm.table_id}` : ''}`);
        fields = data.fields || [];
      }
      const result = await api(`/api/projects/${project.id}/screening-standard/optimize`, {
        method: 'POST',
        body: JSON.stringify({
          project_id: project.id,
          brief: form.description,
          project: {
            name: form.name,
            product: form.product,
            budget: form.budget,
            singleBudget: form.singleBudget,
            creatorCount: form.creatorCount,
            periodStart: form.periodStart,
            periodEnd: form.periodEnd,
          },
          feishu_fields: fields,
        }),
      });
      setScreeningPlan(normalizeWorkbenchPlan(syncScreeningCriteria(result.screeningPlan || {})));
      setStandardStatus(result.source === 'llm' ? '已调用大模型，并结合飞书字段完成优化' : result.message || '测试阶段已生成量化标准');
    } catch (error) {
      setStandardStatus(error.message || error.message_cn || error.detail?.message || '优化量化标准失败，请检查大模型配置和飞书绑定');
    } finally {
      setOptimizingStandard(false);
    }
  };

  const saveStandard = async () => {
    if (!onSaveScreeningPlan || !screeningPlan?.briefType) return;
    setSavingStandard(true);
    setStandardStatus('正在保存量化标准...');
    try {
      const nextPlan = syncScreeningCriteria(screeningPlan);
      await onSaveScreeningPlan(nextPlan, {
        project_name: form.name,
        target_qualified_creator_count: Number(form.creatorCount || 10),
        period_start: form.periodStart,
        period_end: form.periodEnd,
        brief: form.description,
      });
      setScreeningPlan(normalizeWorkbenchPlan(nextPlan));
      setStandardStatus('量化标准已保存，刷新后会自动恢复');
    } catch (error) {
      setStandardStatus(error.message || error.message_cn || error.detail?.message || '保存量化标准失败');
    } finally {
      setSavingStandard(false);
    }
  };

  const updateHardFilterGroup = (key, filters) => {
    setScreeningPlan(old => syncScreeningCriteria({
      ...old,
      [key]: filters,
    }));
  };

  return (
    <div>
      {/* 分段 Tab */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 24, borderBottom: '1px solid var(--border-primary)', paddingBottom: 0 }}>
        {sections.map(s => (
          <button key={s.key} onClick={() => setActiveSection(s.key)}
            style={{
              padding: '10px 20px', background: 'none', border: 'none', cursor: 'pointer',
              color: activeSection === s.key ? 'var(--text-primary)' : 'var(--text-secondary)', fontSize: 14, fontWeight: activeSection === s.key ? 600 : 400,
              borderBottom: activeSection === s.key ? '2px solid #3B82F6' : '2px solid transparent',
              display: 'flex', alignItems: 'center', gap: 6, marginBottom: -1, transition: 'all 0.2s',
            }}>
            {s.icon} {s.label}
          </button>
        ))}
      </div>

      {/* 立项信息 */}
      {activeSection === 'info' && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <h4 style={{ margin: 0, color: 'var(--text-primary)' }}>项目立项信息</h4>
            <Badge variant={project.status === '进行中' ? 'blue' : project.status === '已完成' ? 'green' : 'amber'}>{project.status}</Badge>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16, marginBottom: 16 }}>
            <div><label style={labelStyle}>项目 ID</label><input className="input-field" value={project.id} disabled /></div>
            <div><label style={labelStyle}>项目名称 *</label><input className="input-field" value={form.name} onChange={e => setForm({...form, name: e.target.value})} /></div>
            <div><label style={labelStyle}>产品名称 *</label><input className="input-field" value={form.product} onChange={e => setForm({...form, product: e.target.value})} /></div>
            <div><label style={labelStyle}>达人池类型</label>
              <select className="select-field" value={project.poolType} disabled>
                <option value="shared">共享池</option><option value="isolated">独立池</option>
              </select>
            </div>
            <div><label style={labelStyle}>总预算（元）</label><input className="input-field" type="number" value={form.budget} onChange={e => setForm({...form, budget: e.target.value})} /></div>
            <div><label style={labelStyle}>单达人预算上限（元）</label><input className="input-field" type="number" value={form.singleBudget} onChange={e => setForm({...form, singleBudget: e.target.value})} /></div>
            <div><label style={labelStyle}>目标达人数量</label><input className="input-field" type="number" value={form.creatorCount} onChange={e => setForm({...form, creatorCount: e.target.value})} /></div>
            <div><label style={labelStyle}>合作形式</label>
              <select className="select-field" value={form.cooperationType} onChange={e => setForm({...form, cooperationType: e.target.value})}>
                <option value="合作笔记">合作笔记</option><option value="视频+图文">视频+图文</option><option value="报备">报备</option><option value="直播带货">直播带货</option>
              </select>
            </div>
            <div><label style={labelStyle}>开始日期</label><input className="input-field" type="date" value={form.periodStart} onChange={e => setForm({...form, periodStart: e.target.value})} /></div>
            <div><label style={labelStyle}>结束日期</label><input className="input-field" type="date" value={form.periodEnd} onChange={e => setForm({...form, periodEnd: e.target.value})} /></div>
          </div>
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>项目描述</label>
            <textarea className="input-field" rows={3} value={form.description} onChange={e => setForm({...form, description: e.target.value})} style={{ resize: 'none' }} />
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <button className="btn btn-primary" onClick={async () => {
              if (onSaveProject) await onSaveProject({
                project_name: form.name,
                target_qualified_creator_count: Number(form.creatorCount || 10),
                period_start: form.periodStart,
                period_end: form.periodEnd,
                brief: form.description,
              });
              setSaved(true);
            }}><Save size={14} style={{ marginRight: 4 }} />保存立项信息</button>
            {saved && <span style={{ fontSize: 12, color: '#10B981' }}>✓ 已保存</span>}
          </div>
        </div>
      )}

      {/* 量化标准 */}
      {activeSection === 'standard' && (
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <h4 style={{ margin: 0, color: 'var(--text-primary)' }}>Brief 量化标准</h4>
              <Badge variant={screeningPlan?.briefType === 'complex' ? 'amber' : 'blue'}>
                {screeningPlan?.briefType === 'complex' ? '复杂需求' : '简单需求'}
              </Badge>
            </div>
            <div style={{ marginBottom: 20 }}>
              <label style={labelStyle}>客户 Brief（用于生成量化标准）</label>
              <textarea
                className="input-field"
                rows={4}
                value={form.description}
                onChange={e => setForm({ ...form, description: e.target.value })}
                placeholder="请输入客户需求、目标人群、达人画像、预算限制等，用于生成量化筛选标准"
                style={{ resize: 'vertical', minHeight: 92 }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginTop: 10, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 12, color: standardStatus.includes('失败') ? '#FCA5A5' : 'var(--text-secondary)' }}>{standardStatus || '会结合当前 Brief、项目预算和飞书字段优化量化标准'}</span>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  <button className="btn btn-secondary" onClick={optimizeStandard} disabled={optimizingStandard || !form.description?.trim()}>
                    <Sparkles size={14} style={{ marginRight: 4 }} />{optimizingStandard ? '优化中...' : 'AI 优化量化标准'}
                  </button>
                  <button className="btn btn-primary" onClick={saveStandard} disabled={savingStandard || !screeningPlan?.briefType}>
                    <Save size={14} style={{ marginRight: 4 }} />{savingStandard ? '保存中...' : '保存标准'}
                  </button>
                </div>
              </div>
            </div>
            {screeningPlan?.briefType ? (
              <div>
                {/* 硬性条件 */}
                <div style={{ marginBottom: 20 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                      <Shield size={14} style={{ color: '#EF4444' }} /> 硬性筛选条件
                    </span>
                    <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>已拆分为采集前筛选条件与评分筛选条件，保存后分别应用到采集/评分</span>
                  </div>
                  <div className="standard-hard-filter-group">
                    <div className="standard-hard-filter-group-title">
                      <span><Download size={14} />采集前筛选条件</span>
                      <small>采集工作台展示并编辑，采集入库前使用</small>
                    </div>
                    <HardFilterEditor
                      filters={screeningPlan.collectionHardFilters || []}
                      options={mergeOptionItems(screeningPlan.collectionHardFilters || [], hardFilterOptionsFor(DEFAULT_COLLECTION_HARD_FILTER_FIELDS), hardFilterKey)}
                      onChange={(filters) => updateHardFilterGroup('collectionHardFilters', filters)}
                      emptyText="暂无采集前筛选条件，可从可选项添加或手工新增"
                      fieldHeader="采集筛选项"
                      evidenceHeader="蒲公英/入库字段"
                      evidencePlaceholder="关联蒲公英或入库字段"
                    />
                  </div>
                  <div className="standard-hard-filter-group">
                    <div className="standard-hard-filter-group-title">
                      <span><Sparkles size={14} />评分筛选条件</span>
                      <small>筛选工作台展示并编辑，重新评分时使用</small>
                    </div>
                    <HardFilterEditor
                      filters={screeningPlan.scoringHardFilters || []}
                      options={mergeOptionItems(screeningPlan.scoringHardFilters || [], hardFilterOptionsFor(DEFAULT_SCORING_HARD_FILTER_FIELDS), hardFilterKey)}
                      onChange={(filters) => updateHardFilterGroup('scoringHardFilters', filters)}
                      emptyText="暂无评分筛选条件，可从可选项添加或手工新增"
                      fieldHeader="评分筛选项"
                      evidenceHeader="评分依据字段"
                      evidencePlaceholder="关联评分/飞书字段"
                    />
                  </div>
                </div>

                {/* 评分权重 */}
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Activity size={14} style={{ color: '#3B82F6' }} /> 评分维度权重
                  </div>
                  {Object.keys(screeningPlan.scoringWeights || {}).length > 0 ? (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                      {Object.entries(screeningPlan.scoringWeights || {}).map(([key, weight]) => {
                        const labels = { budget: '预算匹配', fans: '粉丝量级', cpe: 'CPE效率', engagement: '互动质量', persona: '人设匹配', content: '内容风格' };
                        return (
                          <div key={key} style={{ padding: 12, background: 'var(--bg-elevated)', borderRadius: 6 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{labels[key] || key}</span>
                              <span style={{ fontSize: 16, fontWeight: 700, color: '#3B82F6' }}>{weight}%</span>
                            </div>
                            <ProgressBar value={weight} size="sm" color="blue" />
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div style={{ padding: 16, background: 'var(--bg-elevated)', borderRadius: 6, textAlign: 'center', color: 'var(--text-muted)' }}>
                      暂未生成评分标准
                    </div>
                  )}
                </div>
                {(screeningPlan.fieldMappings || []).length > 0 && (
                  <div style={{ marginTop: 20 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <FileSpreadsheet size={14} style={{ color: '#10B981' }} /> 飞书字段匹配
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      {(screeningPlan.fieldMappings || []).map((item, i) => (
                        <span key={i} className="tag" style={{ fontSize: 12 }}>
                          {item.standard} → {item.feishu || '未匹配'}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {screeningPlan.pgyCollectionPlan && (
                  <div style={{ marginTop: 20 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Bot size={14} style={{ color: '#3B82F6' }} /> 蒲公英采集计划
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                      <div style={{ padding: 14, background: 'var(--bg-elevated)', borderRadius: 8 }}>
                        <div style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 8 }}>页面筛选条件</div>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          {(screeningPlan.pgyCollectionPlan.filters || []).map((item, i) => (
                            <span key={`${item.field}-${item.value}-${i}`} className="tag">{item.field}：{item.value}</span>
                          ))}
                        </div>
                      </div>
                      <div style={{ padding: 14, background: 'var(--bg-elevated)', borderRadius: 8 }}>
                        <div style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 8 }}>展示指标</div>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          {(screeningPlan.pgyCollectionPlan.display_metrics || []).map(item => <span key={item} className="tag">{item}</span>)}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: 32 }}>
                <Bot size={32} style={{ color: 'var(--text-muted)', marginBottom: 12 }} />
                <p style={{ color: 'var(--text-secondary)', marginBottom: 16 }}>尚未生成量化标准，请先在 Brief 中描述需求</p>
                <button className="btn btn-primary" onClick={optimizeStandard} disabled={optimizingStandard || !form.description?.trim()}>
                  <Sparkles size={14} style={{ marginRight: 4 }} />{optimizingStandard ? '生成中...' : 'AI 生成筛选标准'}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 飞书绑定 */}
      {activeSection === 'feishu' && (
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <h4 style={{ margin: 0, color: 'var(--text-primary)' }}>飞书表格绑定</h4>
              <Badge variant={project.feishuBinding?.linked ? 'green' : 'default'}>
                {project.feishuBinding?.linked ? '已绑定' : '未绑定'}
              </Badge>
            </div>

            <div>
              <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr', gap: 12, marginBottom: 20 }}>
                <div><label style={labelStyle}>飞书链接</label><input className="input-field" value={feishuForm.feishu_url} onChange={e => setFeishuForm({ ...feishuForm, feishu_url: e.target.value })} placeholder="粘贴电子表格或多维表格链接" /></div>
                <div><label style={labelStyle}>App ID</label><input className="input-field" value={feishuForm.app_id} onChange={e => setFeishuForm({ ...feishuForm, app_id: e.target.value })} placeholder="cli_xxx" /></div>
                <div><label style={labelStyle}>App Secret</label><input className="input-field" type="password" value={feishuForm.app_secret} onChange={e => setFeishuForm({ ...feishuForm, app_secret: e.target.value })} placeholder={feishuConfig?.app_secret_configured ? '已配置，留空沿用' : '请输入'} /></div>
              </div>

              <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
                <button className="btn btn-primary" onClick={() => onSaveFeishu?.(feishuForm)}><Save size={14} style={{ marginRight: 4 }} />保存绑定</button>
                <button className="btn btn-secondary" onClick={runFeishuTest}><CheckCircle2 size={14} style={{ marginRight: 4 }} />测试连接</button>
                <button className="btn btn-secondary" onClick={onLoadTables}><Database size={14} style={{ marginRight: 4 }} />读取子表</button>
                <button className="btn btn-primary" onClick={() => onWriteBack?.(feishuForm.table_id)}><Send size={14} style={{ marginRight: 4 }} />写回飞书</button>
              </div>

              {feishuTestResult && (
                <div style={{ marginBottom: 20, padding: 14, border: `1px solid ${feishuTestResult.ok ? '#10B98155' : '#F59E0B55'}`, background: 'var(--bg-elevated)', borderRadius: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', marginBottom: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-primary)', fontWeight: 600 }}>
                      {feishuTestResult.ok ? <CheckCircle2 size={16} style={{ color: '#10B981' }} /> : <AlertTriangle size={16} style={{ color: '#F59E0B' }} />}
                      {feishuTestResult.message || (feishuTestResult.ok ? '飞书连接测试通过' : '飞书连接测试未通过')}
                    </div>
                    {feishuTestResult.failed_step && <Badge variant="amber">卡在：{feishuTestResult.failed_step}</Badge>}
                  </div>
                  <div style={{ display: 'grid', gap: 8 }}>
                    {(feishuTestResult.steps || []).map(step => (
                      <div key={step.key} style={{ display: 'grid', gridTemplateColumns: '20px 160px 1fr', gap: 8, alignItems: 'start', fontSize: 12 }}>
                        <span style={{ color: step.status === 'success' ? '#10B981' : step.status === 'failed' ? '#EF4444' : 'var(--text-muted)' }}>
                          {step.status === 'success' ? '✓' : step.status === 'failed' ? '!' : '·'}
                        </span>
                        <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{step.label || step.key}</span>
                        <span style={{ color: 'var(--text-secondary)' }}>{step.message || step.status}</span>
                      </div>
                    ))}
                  </div>
                  {(feishuTestResult.error || feishuTestResult.write_error) && (
                    <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border-subtle)', display: 'grid', gap: 8 }}>
                      {(() => {
                        const error = feishuTestResult.error || feishuTestResult.write_error || {};
                        const urls = error.permission_urls || (error.console_url ? [error.console_url] : []);
                        return (
                          <>
                            {error.required_scope && <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>需要权限：<code>{error.required_scope}</code></div>}
                            {(error.permission_violations || []).length > 0 && <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>飞书返回缺失权限：{error.permission_violations.map(item => item.scope || item.permission || JSON.stringify(item)).join('、')}</div>}
                            {(error.fix_actions || []).map((item, index) => <div key={index} style={{ fontSize: 12, color: 'var(--text-secondary)' }}>处理方式：{item}</div>)}
                            {urls.length > 0 && (
                              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                {urls.map((url, index) => (
                                  <a key={url} className="btn btn-sm btn-primary" href={url} target="_blank" rel="noreferrer">
                                    <ExternalLink size={13} /> 打开飞书权限配置{urls.length > 1 ? ` ${index + 1}` : ''}
                                  </a>
                                ))}
                              </div>
                            )}
                          </>
                        );
                      })()}
                    </div>
                  )}
                </div>
              )}

              {(feishuTables || []).length > 0 && (
                <div style={{ marginBottom: 20 }}>
                  <label style={labelStyle}>选择子表</label>
                  <select className="select-field" value={feishuForm.table_id} onChange={e => {
                    const tableId = e.target.value;
                    setFeishuForm({ ...feishuForm, table_id: tableId });
                    onLoadFields?.(tableId);
                  }}>
                    <option value="">请选择子表</option>
                    {feishuTables.map(table => {
                      const id = table.table_id || table.sheet_id || table.id;
                      return <option key={id} value={id}>{table.name || table.title || id}</option>;
                    })}
                  </select>
                </div>
              )}

                {/* 字段映射 */}
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>字段映射关系</div>
                  {(project.feishuBinding.fieldMapping || []).length > 0 ? (
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border-primary)' }}>
                          <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 500, fontSize: 12 }}>标准字段</th>
                          <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 500, fontSize: 12 }}>飞书字段</th>
                          <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 500, fontSize: 12 }}>类型</th>
                          <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 500, fontSize: 12 }}>可写</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(project.feishuBinding.fieldMapping || []).map((fm, i) => {
                          const matched = (feishuFields || []).find(field => [field.field_name, field.name].includes(fm.standard) || [field.field_name, field.name].includes(fm.feishu));
                          return (
                          <tr key={i} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                            <td style={{ padding: '8px 12px', color: 'var(--text-primary)' }}>{fm.standard}</td>
                            <td style={{ padding: '8px 12px', color: 'var(--text-secondary)' }}>{matched?.field_name || matched?.name || fm.feishu}</td>
                            <td style={{ padding: '8px 12px' }}><Badge variant="default">{fm.type}</Badge></td>
                            <td style={{ padding: '8px 12px' }}>
                              <Badge variant={matched ? 'green' : 'amber'}>{matched ? '可写' : '待匹配'}</Badge>
                            </td>
                          </tr>
                        )})}
                      </tbody>
                    </table>
                  ) : (
                    <div style={{ padding: 16, background: 'var(--bg-elevated)', borderRadius: 6, textAlign: 'center', color: 'var(--text-muted)' }}>暂无字段映射</div>
                  )}
                </div>

              </div>
            </div>

          {/* 写回校验清单 */}
          {project.feishuBinding?.linked && (
            <div className="card">
              <h4 style={{ margin: '0 0 16px', color: 'var(--text-primary)' }}>写回前校验清单</h4>
              {[
                { label: '字段映射已确认', done: true },
                { label: '写回字段均为可写字段', done: true },
                { label: '达人记录已通过审核', done: false },
                { label: '已按蒲公英链接或达人 ID 去重', done: true },
                { label: '必填字段不为空', done: false },
                { label: '项目 ID 和采集批次完整', done: true },
              ].map((item, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: i < 5 ? '1px solid var(--border-subtle)' : 'none' }}>
                  <div style={{ width: 20, height: 20, borderRadius: '50%', border: item.done ? 'none' : '2px solid var(--text-muted)', background: item.done ? '#10B981' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {item.done && <CheckCircle2 size={12} color="#fff" />}
                  </div>
                  <span style={{ color: item.done ? 'var(--text-secondary)' : 'var(--text-secondary)', fontSize: 13, textDecoration: item.done ? 'line-through' : 'none' }}>{item.label}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ==================== 操作日志 ====================

function AuditLogTab({ project }) {
  const [typeFilter, setTypeFilter] = useState('全部');

  const logs = useMemo(() => {
    return (window.__screeningLogs || mockAuditLogs)
      .filter(l => typeFilter === '全部' || l.type === typeFilter)
      .sort((a, b) => new Date(b.time) - new Date(a.time));
  }, [typeFilter]);

  const typeConfig = {
    review: { label: '审核操作', icon: <ClipboardCheck size={14} />, color: '#3B82F6' },
    screening: { label: '筛选任务', icon: <Bot size={14} />, color: '#8B5CF6' },
    feishu: { label: '飞书操作', icon: <Link2 size={14} />, color: '#10B981' },
    project: { label: '项目管理', icon: <FolderPlus size={14} />, color: '#F59E0B' },
  };

  const statusConfig = {
    success: { label: '成功', variant: 'green' },
    error: { label: '失败', variant: 'red' },
    warning: { label: '警告', variant: 'amber' },
    info: { label: '信息', variant: 'blue' },
  };

  return (
    <div>
      {/* 筛选栏 */}
      <div className="card" style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className={`btn btn-sm ${typeFilter === '全部' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setTypeFilter('全部')}>全部</button>
          {Object.entries(typeConfig).map(([key, cfg]) => (
            <button key={key} className={`btn btn-sm ${typeFilter === key ? 'btn-secondary' : 'btn-ghost'}`} onClick={() => setTypeFilter(key)}>
              {cfg.icon} {cfg.label}
            </button>
          ))}
        </div>
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>共 {logs.length} 条记录</span>
      </div>

      {/* 时间线 */}
      <div className="card" style={{ padding: '24px 24px 24px 32px' }}>
        {logs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32, color: 'var(--text-muted)' }}>
            <ScrollText size={32} style={{ marginBottom: 8 }} />
            <div>暂无操作日志</div>
          </div>
        ) : (
          <div style={{ position: 'relative' }}>
            {/* 时间线竖线 */}
            <div style={{ position: 'absolute', left: 7, top: 8, bottom: 8, width: 2, background: 'var(--border-primary)' }} />

            {logs.map((log, idx) => {
              const cfg = typeConfig[log.type] || typeConfig.project;
              const scfg = statusConfig[log.status] || statusConfig.info;
              return (
                <div key={log.id} className="timeline-item" style={{ position: 'relative', paddingLeft: 28, paddingBottom: idx < logs.length - 1 ? 24 : 0 }}>
                  {/* 时间线圆点 */}
                  <div className="timeline-dot" style={{
                    position: 'absolute', left: 0, top: 6, width: 16, height: 16, borderRadius: '50%',
                    background: log.status === 'error' ? '#EF4444' : cfg.color,
                    border: '3px solid var(--bg-secondary)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    {log.status === 'error' && <X size={8} color="#fff" />}
                  </div>

                  {/* 日志内容 */}
                  <div className="timeline-content">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ color: 'var(--text-primary)', fontWeight: 500, fontSize: 14 }}>{log.action}</span>
                        <Badge variant={scfg.variant}>{scfg.label}</Badge>
                      </div>
                      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{log.time}</span>
                    </div>
                    <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 4 }}>
                      <span style={{ color: 'var(--text-secondary)' }}>对象：</span>{log.target}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{log.detail}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>操作人：{log.user}</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ==================== AI 大模型 API 配置 ====================

function AdvancedConfigTab() {
  const [config, setConfig] = useState({
    protocol: 'openai-compatible',
    base_url: 'https://api.openai.com/v1',
    model: 'gpt-4.1-mini',
    api_key: '',
    api_key_env: 'OPENAI_API_KEY',
    temperature: 0.2,
    max_tokens: null,
    timeout_seconds: null,
  });
  const [meta, setMeta] = useState({
    path: 'config/ai_provider.yaml',
    api_key_configured: false,
    api_key_source: 'none',
  });
  const [feedback, setFeedback] = useState('');
  const [busy, setBusy] = useState(false);

  const protocolDefaults = {
    'openai-compatible': {
      base_url: 'https://api.openai.com/v1',
      model: 'gpt-4.1-mini',
      api_key_env: 'OPENAI_API_KEY',
    },
    gemini: {
      base_url: 'https://generativelanguage.googleapis.com/v1beta',
      model: 'gemini-2.5-flash',
      api_key_env: 'GEMINI_API_KEY',
    },
  };

  const applyRemoteConfig = (payload) => {
    const remote = payload?.config;
    if (!remote) return;
    setConfig((prev) => ({
      ...prev,
      protocol: remote.protocol || prev.protocol,
      base_url: remote.base_url || prev.base_url,
      model: remote.model || prev.model,
      api_key: '',
      api_key_env: remote.api_key_env || '',
      temperature: remote.temperature ?? prev.temperature,
      max_tokens: remote.max_tokens ?? prev.max_tokens,
      timeout_seconds: remote.timeout_seconds ?? prev.timeout_seconds,
    }));
    setMeta({
      path: remote.path || 'config/ai_provider.yaml',
      api_key_configured: Boolean(remote.api_key_configured),
      api_key_source: remote.api_key_source || 'none',
    });
  };

  useEffect(() => {
    const cached = localStorage.getItem('adflow-api-config');
    if (cached) {
      try {
        setConfig((prev) => ({ ...prev, ...JSON.parse(cached), api_key: '' }));
      } catch {
        // ignore stale local cache
      }
    }
    fetch('/api/llm/config')
      .then((response) => (response.ok ? response.json() : null))
      .then((payload) => applyRemoteConfig(payload))
      .catch(() => undefined);
  }, []);

  const updateConfig = (key, value) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  const switchProtocol = (protocol) => {
    setConfig((prev) => ({ ...prev, protocol, ...protocolDefaults[protocol] }));
  };

  const saveConfig = async () => {
    setBusy(true);
    setFeedback('');
    try {
      const response = await fetch('/api/llm/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...config, keep_existing_api_key: true }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(formatApiErrorMessage(result, '保存 API 配置失败'));
      applyRemoteConfig(result);
      setFeedback(result.message || 'API 配置已保存');
    } catch (error) {
      localStorage.setItem('adflow-api-config', JSON.stringify({ ...config, api_key: '' }));
      setMeta((prev) => ({
        ...prev,
        api_key_configured: prev.api_key_configured || Boolean(config.api_key || config.api_key_env),
        api_key_source: config.api_key ? 'inline' : (config.api_key_env ? 'env' : 'none'),
      }));
      setFeedback(`${formatApiErrorMessage(error, '后端暂不可用')}，已先保存到本地工作台配置。`);
    } finally {
      setConfig((prev) => ({ ...prev, api_key: '' }));
      setBusy(false);
    }
  };

  const testConfig = async () => {
    setBusy(true);
    setFeedback('');
    try {
      const response = await fetch('/api/llm/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      const result = await response.json();
      if (!response.ok || result.ok === false) throw new Error(formatApiErrorMessage(result, 'API 连接测试失败'));
      setFeedback(result.message || 'API 连接测试成功');
    } catch (error) {
      setFeedback(formatApiErrorMessage(error, 'API 连接测试失败'));
    } finally {
      setBusy(false);
    }
  };

  const keySource = meta.api_key_source === 'inline' ? '配置文件' : (config.api_key_env || '未配置');

  return (
    <div className="screening-api-settings">
      <div className="screening-api-hero">
        <div>
          <div className="screening-api-eyebrow">AI Model API</div>
          <h3>高级配置</h3>
          <p>配置达人筛选评分、Brief 解析和自动补全所使用的大模型 API。</p>
        </div>
        <div className="screening-api-actions">
          <button className="btn btn-secondary" type="button" disabled={busy} onClick={testConfig}>
            <RefreshCw size={14} style={{ marginRight: 4 }} />测试连接
          </button>
          <button className="btn btn-primary" type="button" disabled={busy} onClick={saveConfig}>
            <Save size={14} style={{ marginRight: 4 }} />保存配置
          </button>
        </div>
      </div>

      <div className="screening-api-grid">
        <div className="card screening-api-main">
          <div className="card-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <KeyRound size={16} style={{ color: 'var(--text-secondary)' }} />
              <h3>模型服务</h3>
            </div>
            <Badge variant={meta.api_key_configured ? 'green' : 'amber'}>
              {meta.api_key_configured ? 'Key 已配置' : 'Key 待配置'}
            </Badge>
          </div>
          <div className="card-body">
            <div className="screening-api-form">
              <div className="screening-api-provider-switch">
                <button className={config.protocol === 'openai-compatible' ? 'active' : ''} type="button" onClick={() => switchProtocol('openai-compatible')}>
                  <Globe size={14} /><span>OpenAI / 兼容</span>
                </button>
                <button className={config.protocol === 'gemini' ? 'active' : ''} type="button" onClick={() => switchProtocol('gemini')}>
                  <Sparkles size={14} /><span>Gemini</span>
                </button>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
                <label className="screening-api-control">
                  <span>Base URL</span>
                  <input className="input-field" value={config.base_url} onChange={(event) => updateConfig('base_url', event.target.value)} placeholder="https://api.openai.com/v1" />
                </label>
                <label className="screening-api-control">
                  <span>模型名</span>
                  <input className="input-field" value={config.model} onChange={(event) => updateConfig('model', event.target.value)} placeholder="gpt-4.1-mini 或 gemini-2.5-flash" />
                </label>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
                <label className="screening-api-control">
                  <span>API Key</span>
                  <input className="input-field" type="password" value={config.api_key} onChange={(event) => updateConfig('api_key', event.target.value)} placeholder={meta.api_key_configured ? '留空则保留已保存密钥' : '填写模型服务密钥'} autoComplete="new-password" />
                </label>
                <label className="screening-api-control">
                  <span>环境变量名</span>
                  <input className="input-field" value={config.api_key_env} onChange={(event) => updateConfig('api_key_env', event.target.value)} placeholder="OPENAI_API_KEY / GEMINI_API_KEY" />
                </label>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
                <label className="screening-api-control">
                  <span>Temperature</span>
                  <input className="input-field" type="number" step="0.1" min="0" max="2" value={config.temperature} onChange={(event) => updateConfig('temperature', Number(event.target.value))} />
                </label>
                <label className="screening-api-control">
                  <span>Max Tokens</span>
                  <input className="input-field" type="number" value={config.max_tokens ?? ''} onChange={(event) => updateConfig('max_tokens', event.target.value === '' ? null : Number(event.target.value))} placeholder="不限制" />
                </label>
                <label className="screening-api-control">
                  <span>超时秒数</span>
                  <input className="input-field" type="number" value={config.timeout_seconds ?? ''} onChange={(event) => updateConfig('timeout_seconds', event.target.value === '' ? null : Number(event.target.value))} placeholder="不限制" />
                </label>
              </div>

              {feedback && <div className="screening-api-feedback">{feedback}</div>}
            </div>
          </div>
        </div>

        <div className="card screening-api-status-card">
          <div className="card-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Activity size={16} style={{ color: 'var(--text-secondary)' }} />
              <h3>配置状态</h3>
            </div>
          </div>
          <div className="card-body">
            {[
              ['当前协议', config.protocol],
              ['配置文件', meta.path],
              ['Key 状态', meta.api_key_configured ? '已配置' : '待配置'],
              ['Key 来源', keySource],
            ].map(([label, value]) => (
              <div className="screening-api-status-row" key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
            <div className="screening-api-note">
              API Key 不会在页面读取时回显；保存新 Key 后输入框会自动清空。
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ==================== 主组件 ====================

function ScreeningDashboard({ selectedProjectId: externalSelectedProjectId, onSelectedProjectIdChange }) {
  const { tab } = useParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState(tab || 'projects');
  const [projects, setProjects] = useState([initialProjects[0]]);
  const [currentProject, setCurrentProject] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [screeningStatus, setScreeningStatus] = useState(initialScreeningStatus);
  const [feishuConfig, setFeishuConfig] = useState(null);
  const [feishuFields, setFeishuFields] = useState([]);
  const [feishuTables, setFeishuTables] = useState([]);
  const [message, setMessage] = useState('');

  const selectedProjectId = currentProject?.id || externalSelectedProjectId || PROJECT_ID;

  const loadData = useCallback(async () => {
    const projectsPayload = await api('/api/projects?include_archived=true');
    const rawProjects = projectsPayload.projects || [];
    const projectIds = rawProjects.map(item => item.project_id);
    const projectDetails = await Promise.all(projectIds.map(async (projectId) => {
      const [creatorsPayload, configPayload] = await Promise.all([
        api(`/api/projects/${projectId}/creators`),
        api(`/api/projects/feishu/connection?project_id=${projectId}`),
      ]);
      return {
        projectId,
        creators: (creatorsPayload.creators || []).map(mapBackendCreator),
        config: configPayload.config || null,
      };
    }));
    const detailMap = Object.fromEntries(projectDetails.map(item => [item.projectId, item]));
    const nextProjects = rawProjects.length
      ? rawProjects.map(item => mapBackendProject(item, detailMap[item.project_id]?.creators || [], detailMap[item.project_id]?.config || null))
      : [];
    const currentId = externalSelectedProjectId || currentProject?.id;
    const shouldAutoSelectProject = Boolean(externalSelectedProjectId) || (tab && tab !== 'projects');
    const nextCurrent = currentId
      ? nextProjects.find(project => project.id === currentId)
      : shouldAutoSelectProject
        ? nextProjects[0]
        : null;
    setProjects(nextProjects);
    setCurrentProject(nextCurrent || null);
    if (nextCurrent) {
      onSelectedProjectIdChange?.(nextCurrent.id);
    }
    setFeishuConfig(nextCurrent?.feishuBinding?.linked ? detailMap[nextCurrent.id]?.config || null : null);
    if (nextCurrent) {
      const logsPayload = await api(`/api/projects/${nextCurrent.id}/logs`);
      window.__screeningLogs = (logsPayload.logs || []).map((log, index) => ({
        id: log.log_id || index,
        type: log.action_type || 'project',
        action: log.action,
        target: log.target,
        user: log.operator,
        time: log.created_at,
        detail: log.detail,
        status: log.status,
      }));
    }
  }, [currentProject?.id, externalSelectedProjectId, onSelectedProjectIdChange, tab]);

  const loadProjectSideData = useCallback(async (projectId) => {
    const [logsPayload, configPayload] = await Promise.all([
      api(`/api/projects/${projectId}/logs`),
      api(`/api/projects/feishu/connection?project_id=${projectId}`),
    ]);
    setFeishuConfig(configPayload.config || null);
    window.__screeningLogs = (logsPayload.logs || []).map((log, index) => ({
      id: log.log_id || index,
      type: log.action_type || 'project',
      action: log.action,
      target: log.target,
      user: log.operator,
      time: log.created_at,
      detail: log.detail,
      status: log.status,
    }));
  }, []);

  useEffect(() => {
    loadData().catch(error => setMessage(error.message || '读取后端数据失败'));
  }, [loadData]);

  useEffect(() => {
    if (tab) setActiveTab(tab);
  }, [tab]);

  const handleSelectProject = (project) => {
    onSelectedProjectIdChange?.(project.id);
    setCurrentProject(project);
    loadProjectSideData(project.id).catch(error => setMessage(error.message || '读取项目数据失败'));
    handleTabChange('overview');
  };

  const handleCreateProject = (newProject) => {
    setProjects([...projects, newProject]);
  };

  const handleArchiveProject = async (project) => {
    try {
      await api(`/api/projects/${project.id}/archive`, { method: 'POST' });
      if (currentProject?.id === project.id) {
        setCurrentProject(null);
        onSelectedProjectIdChange?.(null);
      }
      await loadData();
      setMessage(`已归档项目：${project.name}`);
    } catch (error) {
      setMessage(error.message || '归档项目失败');
    }
  };

  const handleRestoreProject = async (project) => {
    try {
      await api(`/api/projects/${project.id}/restore`, { method: 'POST' });
      await loadData();
      setMessage(`已恢复项目：${project.name}`);
    } catch (error) {
      setMessage(error.message || '恢复项目失败');
    }
  };

  const handleDeleteProject = async (project) => {
    const confirmed = window.confirm(`确认删除项目「${project.name}」吗？删除后会清理该项目的达人、评分、日志和导出文件，无法从页面恢复。`);
    if (!confirmed) return;
    try {
      await api(`/api/projects/${project.id}`, { method: 'DELETE' });
      if (currentProject?.id === project.id) {
        setCurrentProject(null);
        onSelectedProjectIdChange?.(null);
      }
      await loadData();
      setMessage(`已删除项目：${project.name}`);
    } catch (error) {
      setMessage(error.message || '删除项目失败');
    }
  };

  const handleTabChange = (newTab) => {
    setActiveTab(newTab);
    navigate(`/workbench/screening/${newTab}`, { replace: false });
  };

  const runAction = async (label, action) => {
    setMessage(`${label}中...`);
    try {
      const result = await action();
      await loadData();
      setMessage(result?.message || `${label}完成`);
    } catch (error) {
      const fixActions = error.detail?.fix_actions || error.detail?.write_error?.fix_actions || [];
      const suffix = fixActions.length ? `。处理方式：${fixActions.join('；')}` : '';
      setMessage(`${error.message || error.message_cn || JSON.stringify(error)}${suffix}`);
    }
  };

  const handleReview = (creatorIds, reviewStatus, reviewReason) => runAction('审核更新', () => api(`/api/projects/${selectedProjectId}/creators/review`, {
    method: 'POST',
    body: JSON.stringify({ creator_ids: creatorIds, review_status: reviewStatus, review_reason: reviewReason, reviewer: '当前用户' }),
  }));

  const handleImport = () => runAction('导入达人模板', () => api(`/api/projects/${selectedProjectId}/creators/import`, { method: 'POST', body: JSON.stringify({}) }));
  const handleScore = () => runAction('重新评分', () => api(`/api/projects/${selectedProjectId}/creators/score`, { method: 'POST' }));
  const handleStartBrowser = () => runAction('启动蒲公英浏览器', () => api('/api/pgy/browser/start', { method: 'POST' }));
  const handleCollect = (screeningPlanOverride) => runAction('蒲公英采集', async () => {
    const result = await api('/api/pgy/collect/batch', {
      method: 'POST',
      body: JSON.stringify({
        project_id: selectedProjectId,
        screening_plan: screeningPlanOverride || currentProject?.screeningPlan || {},
        apply_filters: true,
        include_details: false,
        collect_profile_urls: false,
        export_metrics: true,
        limit: 100,
      }),
    });
    const count = result.creators?.length || result.batch?.success_count || 0;
    const applied = result.applied_filters?.length || 0;
    const skipped = result.skipped_filters?.length || 0;
    const selectedMetrics = result.selected_metrics?.length || 0;
    const skippedMetrics = result.skipped_metrics?.length || 0;
    return {
      ...result,
      message: result.message || `蒲公英采集完成，已入库 ${count} 个达人；筛选已应用 ${applied} 个、${skipped} 个需人工确认；展示指标已确认 ${selectedMetrics} 个、${skippedMetrics} 个未找到`,
    };
  });
  const handleCollectDetails = ({ creatorIds = [], segment = '', segmentLabel = '' } = {}) => runAction(
    segmentLabel ? `${segmentLabel}详情页完善` : '详情页完善',
    async () => {
      const result = await api('/api/pgy/collect/detail', {
        method: 'POST',
        body: JSON.stringify({
          project_id: selectedProjectId,
          creator_ids: creatorIds,
          segment,
          manual: true,
          limit: creatorIds.length ? creatorIds.length : 20,
        }),
      });
      return {
        ...result,
        message: result.message || `详情页完善完成，已更新 ${result.updated?.length || 0} 个${segmentLabel ? segmentLabel : '通过初筛'}达人`,
      };
    }
  );
  const handleSaveProject = (payload) => runAction('保存立项信息', () => api(`/api/projects/${selectedProjectId}`, { method: 'POST', body: JSON.stringify(payload) }));
  const handleSaveScreeningPlan = async (screeningPlan, projectPatch = {}) => {
    const result = await api(`/api/projects/${selectedProjectId}`, {
      method: 'POST',
      body: JSON.stringify({
        project_name: projectPatch.project_name || currentProject?.name,
        target_qualified_creator_count: Number(projectPatch.target_qualified_creator_count || currentProject?.creatorCount || 10),
        period_start: projectPatch.period_start || currentProject?.periodStart,
        period_end: projectPatch.period_end || currentProject?.periodEnd,
        brief: projectPatch.brief || currentProject?.description,
        screening_plan: screeningPlan,
      }),
    });
    const nextProject = mapBackendProject(result.project, currentProject?.creators || [], feishuConfig);
    nextProject.screeningPlan = screeningPlan;
    setCurrentProject(nextProject);
    setProjects(old => old.map(project => project.id === nextProject.id ? nextProject : project));
    setMessage('筛选计划已保存');
    return result;
  };
  const handleSaveFeishu = (payload) => runAction('保存飞书配置', async () => {
    const result = await api('/api/projects/feishu/connection', { method: 'POST', body: JSON.stringify({ project_id: selectedProjectId, ...payload }) });
    setFeishuConfig(result.config);
  });
  const handleTestFeishu = async (payload) => {
    setMessage('飞书校验中...');
    try {
      const result = await api('/api/projects/feishu/test', { method: 'POST', body: JSON.stringify({ project_id: selectedProjectId, ...payload }) });
      setFeishuFields(result.fields || []);
      await loadData();
      setMessage(result?.message || '飞书校验完成');
      return result;
    } catch (error) {
      setFeishuFields(error.detail?.fields || []);
      const testError = error.detail?.error || error.detail?.write_error || error.detail || {};
      const fixActions = testError.fix_actions || [];
      const suffix = fixActions.length ? `。处理方式：${fixActions.join('；')}` : '';
      setMessage(`${error.message || error.message_cn || JSON.stringify(error)}${suffix}`);
      throw error;
    }
  };
  const handleLoadTables = () => runAction('读取子表', async () => {
    const result = await api(`/api/projects/feishu/tables?project_id=${selectedProjectId}`);
    setFeishuTables(result.tables || []);
  });
  const handleLoadFields = (tableId) => runAction('读取字段', async () => {
    const result = await api(`/api/projects/feishu/fields?project_id=${selectedProjectId}${tableId ? `&table_id=${tableId}` : ''}`);
    setFeishuFields(result.fields || []);
  });
  const handleWriteBack = (tableId) => runAction('写回飞书', () => api('/api/projects/feishu/writeback', {
    method: 'POST',
    body: JSON.stringify({ project_id: selectedProjectId, table_id: tableId || null, rows: [], statuses: ['已通过', '备选'] }),
  }));

  const renderTabContent = () => {
    if (activeTab === 'projects') {
      return (
        <ProjectsPreview
          projects={projects}
          onSelectProject={handleSelectProject}
          onCreateProject={() => setShowCreateModal(true)}
          onArchiveProject={handleArchiveProject}
          onRestoreProject={handleRestoreProject}
          onDeleteProject={handleDeleteProject}
        />
      );
    }

    if (!currentProject) {
      return (
        <div className="card" style={{ textAlign: 'center', padding: 48 }}>
          <FolderOpen size={48} style={{ color: 'var(--text-muted)', marginBottom: 16 }} />
          <h4 style={{ color: 'var(--text-primary)', marginBottom: 8 }}>请先选择项目</h4>
          <p style={{ color: 'var(--text-secondary)', marginBottom: 16 }}>进入「项目预览」选择一个项目开始工作</p>
          <button className="btn btn-primary" onClick={() => handleTabChange('projects')}>前往项目预览</button>
        </div>
      );
    }

    switch (activeTab) {
      case 'overview': return <OverviewTab project={currentProject} onCollect={handleCollect} onSavePlan={handleSaveScreeningPlan} />;
      case 'screening-review': return <ScreeningReviewTab project={currentProject} screeningStatus={screeningStatus} setScreeningStatus={setScreeningStatus} onReview={handleReview} onRefresh={loadData} onScore={handleScore} onImport={handleImport} onCollect={handleCollect} onCollectDetails={handleCollectDetails} onSavePlan={handleSaveScreeningPlan} onTabChange={handleTabChange} />;
      case 'score-preview': return <ScorePreviewTab project={currentProject} screeningStatus={screeningStatus} onCollectDetails={handleCollectDetails} />;
      case 'project-setup': return <ProjectSetupTab project={currentProject} feishuConfig={feishuConfig} feishuFields={feishuFields} feishuTables={feishuTables} onSaveProject={handleSaveProject} onSaveScreeningPlan={handleSaveScreeningPlan} onSaveFeishu={handleSaveFeishu} onTestFeishu={handleTestFeishu} onLoadTables={handleLoadTables} onLoadFields={handleLoadFields} onWriteBack={handleWriteBack} />;
      case 'audit-log': return <AuditLogTab project={currentProject} />;
      case 'legacy': return <AdvancedConfigTab />;
      default: return <OverviewTab project={currentProject} onCollect={handleCollect} onSavePlan={handleSaveScreeningPlan} />;
    }
  };

  return (
    <div className="screening-dashboard" style={{ padding: 24 }}>
      {message && <div className="card" style={{ padding: 12, marginBottom: 16, color: message.includes('失败') ? '#FCA5A5' : 'var(--text-secondary)' }}>{message}</div>}

      {renderTabContent()}

      <CreateProjectModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreate={handleCreateProject}
      />
    </div>
  );
}

export default ScreeningDashboard;
