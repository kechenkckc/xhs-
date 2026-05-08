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
  ArrowDownRight, Minus, Info, X, ChevronUp, ChevronLeft, KeyRound, Globe
} from 'lucide-react';
import StatCard from '../../components/StatCard';
import DataTable from '../../components/DataTable';
import Badge from '../../components/Badge';
import ProgressBar from '../../components/ProgressBar';
import TabBar from '../../components/TabBar';
import PageHeader from '../../components/PageHeader';

const tabs = [
  { key: 'projects', label: '项目预览', icon: <Grid3X3 size={14} /> },
  { key: 'overview', label: '流程工作台', icon: <LayoutDashboard size={14} /> },
  { key: 'screening-review', label: '初筛评分 + 人工筛选', icon: <Users size={14} /> },
  { key: 'score-preview', label: '候选评分预览', icon: <BarChart3 size={14} /> },
  { key: 'project-setup', label: '立项 + 标准 + 飞书绑定', icon: <FolderPlus size={14} /> },
  { key: 'audit-log', label: '操作日志', icon: <ScrollText size={14} /> },
  { key: 'legacy', label: '高级配置', icon: <KeyRound size={14} /> },
];

const STEPS = ['立项', '绑定飞书', '量化标准', '蒲公英初筛', '补全评分', '人工审核', '写回飞书'];
const PROJECT_ID = 'youdao_001';

async function api(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw payload.detail || payload;
  return payload;
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

function reviewVariantFromStatus(status) {
  return { 已通过: 'green', 已写回飞书: 'green', 已驳回: 'red', 备选: 'amber', 待审核: 'blue', 待补数据: 'default' }[status] || 'default';
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
    risk: risks,
    scores: {
      budget: Math.round(Number(item.budget_score || 0) * 5),
      fans: Math.round(Number(item.fans_score || 0) * 5),
      cpe: Math.round(Number(item.cpe_score || 0) * 6.67),
      engagement: Math.round(Number(item.traffic_score || 0) * 6.67),
      persona: Math.round(Number(item.persona_score || 0) * 5),
      content: Math.round(Number(item.content_score || 0) * 10),
    },
    aiReason: item.score_reason || '待补充蒲公英详情数据后生成完整评分说明。',
    review: item.status || '待补数据',
    reviewVariant: reviewVariantFromStatus(item.status),
    finalScore: score || null,
    reason: item.review_reason || item.score_reason || '',
    reviewer: item.reviewer,
    reviewedAt: item.reviewed_at,
    raw: item,
  };
}

function mapBackendProject(item, creators = [], feishuConfig = null) {
  const base = initialProjects[0];
  const linked = Boolean(feishuConfig?.feishu_url);
  return {
    ...base,
    id: item.project_id,
    name: item.project_name,
    product: '有道答疑笔Pro',
    creatorCount: item.target_qualified_creator_count || 10,
    periodStart: item.period_start || base.periodStart,
    periodEnd: item.period_end || base.periodEnd,
    period: `${item.period_start || '2026-05-07'} 至 ${item.period_end || '2026-05-19'}`,
    description: item.brief || base.description,
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
  };
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
  return map[projectId]?.[creatorId] || {
    review: '待审核', reviewVariant: 'default', finalScore: null, reason: '', reviewer: null, reviewedAt: null
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

function getScoreColor(score) {
  if (score >= 85) return '#10B981';
  if (score >= 70) return '#F59E0B';
  return '#EF4444';
}

function getReviewVariant(review) {
  const map = { '已通过': 'green', '已驳回': 'red', '备选': 'amber', '人工复核': 'blue', '默认淘汰': 'red', '待审核': 'default', '待确认': 'amber' };
  return map[review] || 'default';
}

// ==================== 项目预览组件 ====================

function ProjectsPreview({ projects, onSelectProject, onCreateProject }) {
  const [viewMode, setViewMode] = useState('grid');
  const [filter, setFilter] = useState('全部');
  const [search, setSearch] = useState('');

  const filteredProjects = projects.filter(p => {
    if (filter !== '全部' && p.status !== filter) return false;
    if (search && !p.name.includes(search) && !p.product.includes(search)) return false;
    return true;
  });

  const stats = {
    total: projects.length,
    active: projects.filter(p => p.status === '进行中').length,
    completed: projects.filter(p => p.status === '已完成').length,
    pending: projects.filter(p => p.status === '待启动').length,
  };

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
        <StatCard title="项目总数" value={stats.total} subtitle="个项目" icon={FolderOpen} color="blue" />
        <StatCard title="进行中" value={stats.active} subtitle="个项目" icon={Play} color="green" />
        <StatCard title="已完成" value={stats.completed} subtitle="个项目" icon={CheckCircle2} color="cyan" />
        <StatCard title="待启动" value={stats.pending} subtitle="个项目" icon={Clock} color="amber" />
      </div>

      <div className="card" style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <div className="search-box" style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#8B95A5' }} />
            <input
              className="search-input"
              placeholder="搜索项目名称或产品..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ paddingLeft: 30, width: 200 }}
            />
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            {['全部', '进行中', '已完成', '待启动'].map(status => (
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
          <FolderOpen size={48} style={{ color: '#5A6478', marginBottom: 16 }} />
          <h4 style={{ color: '#E8ECF1', marginBottom: 8 }}>暂无匹配项目</h4>
          <p style={{ color: '#8B95A5' }}>尝试调整筛选条件或创建新项目</p>
        </div>
      ) : viewMode === 'grid' ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
          {filteredProjects.map(project => (
            <ProjectCard key={project.id} project={project} onClick={() => onSelectProject(project)} />
          ))}
        </div>
      ) : (
        <div className="card">
          <DataTable
            columns={[
              { key: 'name', label: '项目名称', render: (v, row) => (
                <div>
                  <div style={{ fontWeight: 500, color: '#E8ECF1' }}>{v}</div>
                  <div style={{ fontSize: 12, color: '#8B95A5' }}>{row.product}</div>
                </div>
              )},
              { key: 'status', label: '状态', render: v => <Badge variant={v === '进行中' ? 'blue' : v === '已完成' ? 'green' : 'amber'}>{v}</Badge> },
              { key: 'poolType', label: '达人池', render: v => <Badge variant={v === 'shared' ? 'blue' : 'purple'}>{v === 'shared' ? '共享' : '独立'}</Badge> },
              { key: 'budget', label: '预算', render: v => `¥${v.toLocaleString()}` },
              { key: 'progress', label: '进度', render: (v, row) => {
                const s = getProjectStats(row);
                return (<div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><ProgressBar value={s.total > 0 ? (s.passed / s.total) * 100 : 0} size="sm" /><span style={{ fontSize: 12, color: '#8B95A5' }}>{s.passed}/{s.total}</span></div>);
              }},
              { key: 'action', label: '', render: (v, row) => (
                <button className="btn btn-sm btn-primary" onClick={(e) => { e.stopPropagation(); onSelectProject(row); }}>进入项目 <ArrowRight size={14} /></button>
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

function ProjectCard({ project, onClick }) {
  const stats = getProjectStats(project);
  const progress = stats.total > 0 ? (stats.passed / stats.total) * 100 : 0;

  return (
    <div className="card" onClick={onClick}
      style={{ cursor: 'pointer', transition: 'all 0.2s ease', border: '1px solid #2A3040' }}
      onMouseEnter={e => { e.currentTarget.style.borderColor = '#3B82F6'; e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 8px 24px rgba(0,0,0,0.3)'; }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = '#2A3040'; e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none'; }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h4 style={{ margin: 0, color: '#E8ECF1', fontSize: 16, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{project.name}</h4>
          <p style={{ margin: '4px 0 0', color: '#8B95A5', fontSize: 12 }}>{project.product}</p>
        </div>
        <Badge variant={project.status === '进行中' ? 'blue' : project.status === '已完成' ? 'green' : 'amber'}>{project.status}</Badge>
      </div>
      <p style={{ margin: '0 0 12px', color: '#8B95A5', fontSize: 13, lineHeight: 1.5, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{project.description}</p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, marginBottom: 12 }}>
        <div style={{ padding: 8, background: '#12161C', borderRadius: 6 }}>
          <div style={{ fontSize: 11, color: '#8B95A5' }}>预算</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#E8ECF1' }}>¥{(project.budget / 10000).toFixed(0)}万</div>
        </div>
        <div style={{ padding: 8, background: '#12161C', borderRadius: 6 }}>
          <div style={{ fontSize: 11, color: '#8B95A5' }}>目标达人</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#E8ECF1' }}>{project.creatorCount}人</div>
        </div>
      </div>
      <div style={{ marginBottom: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#8B95A5', marginBottom: 4 }}>
          <span>筛选进度 {stats.passed}/{stats.total}</span><span>{progress.toFixed(0)}%</span>
        </div>
        <ProgressBar value={progress} size="sm" />
      </div>
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
        <Badge variant={project.poolType === 'shared' ? 'blue' : 'purple'}>{project.poolType === 'shared' ? '共享池' : '独立池'}</Badge>
        <span className="tag" style={{ fontSize: 11 }}>{project.period}</span>
        {project.feishuBinding?.linked && <span className="tag" style={{ fontSize: 11, color: '#10B981', borderColor: '#10B98133' }}>已绑定飞书</span>}
      </div>
      <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid #2A3040' }}>
        <div style={{ display: 'flex', gap: 4, overflow: 'hidden' }}>
          {STEPS.map((step, idx) => (
            <div key={step} style={{ width: 20, height: 4, borderRadius: 2, background: idx < project.currentStep ? '#10B981' : '#2A3040', flexShrink: 0 }} title={step} />
          ))}
        </div>
        <div style={{ fontSize: 11, color: '#8B95A5', marginTop: 4 }}>当前步骤：{STEPS[project.currentStep - 1]}</div>
      </div>
    </div>
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

  const labelStyle = { fontSize: 12, color: '#8B95A5', display: 'block', marginBottom: 4 };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 640, maxHeight: '90vh', overflow: 'auto' }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3 style={{ margin: 0, color: '#E8ECF1' }}>新建筛选项目</h3>
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

// ==================== 流程工作台 ====================

function OverviewTab({ project, onTabChange }) {
  const creators = useMemo(() => getProjectCreators(project), [project]);
  const stats = getProjectStats(project);

  return (
    <div>
      {/* 项目概览 */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
          <div>
            <h3 style={{ margin: 0, color: '#E8ECF1', fontSize: 20 }}>{project.name}</h3>
            <p style={{ margin: '6px 0 0', color: '#8B95A5', fontSize: 14 }}>{project.product} · {project.period} · <Badge variant={project.poolType === 'shared' ? 'blue' : 'purple'} style={{ marginLeft: 4 }}>{project.poolType === 'shared' ? '共享池' : '独立池'}</Badge></p>
          </div>
          <Badge variant={project.status === '进行中' ? 'blue' : project.status === '已完成' ? 'green' : 'amber'} style={{ fontSize: 13 }}>{project.status}</Badge>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
          <StatCard title="总合格达人数" value={stats.passed} subtitle={`目标${project.creatorCount}人`} icon={UserCheck} color="green" />
          <StatCard title="现有达人池" value={stats.total} subtitle="人" icon={Users} color="purple" />
          <StatCard title="合格占比" value={`${Math.round((project.stats?.ratio || (project.creatorCount ? stats.passed / project.creatorCount : 0)) * 100)}%`} icon={Target} color="blue" />
          <StatCard title="待审核" value={stats.pending + stats.review} subtitle="人" icon={Clock} color="amber" />
        </div>
      </div>

      {/* 7步流程进度 */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h4 style={{ margin: 0, color: '#E8ECF1' }}>筛选流程进度</h4>
          <span style={{ fontSize: 12, color: '#8B95A5' }}>步骤 {project.currentStep} / {STEPS.length}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 0 }}>
          {STEPS.map((step, idx) => {
            const done = idx < project.currentStep;
            const current = idx === project.currentStep - 1;
            return (
              <React.Fragment key={step}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, flex: '0 0 auto', minWidth: 60 }}>
                  <div style={{
                    width: 36, height: 36, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: done ? '#10B981' : current ? '#3B82F6' : '#1A1F2B',
                    border: current ? '2px solid #3B82F6' : '2px solid transparent',
                    color: done ? '#fff' : current ? '#3B82F6' : '#5A6478',
                    transition: 'all 0.2s', cursor: 'pointer',
                  }}>
                    {done ? <CheckCircle2 size={18} /> : current ? <Play size={16} /> : <Clock size={16} />}
                  </div>
                  <span style={{ fontSize: 11, color: done || current ? '#E8ECF1' : '#5A6478', textAlign: 'center', fontWeight: current ? 600 : 400 }}>{step}</span>
                </div>
                {idx < STEPS.length - 1 && (
                  <div style={{ flex: 1, height: 2, background: idx + 1 < project.currentStep ? '#10B981' : '#1A1F2B', marginTop: 18, minWidth: 12 }} />
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Brief 需求展示 */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h4 style={{ margin: 0, color: '#E8ECF1', display: 'flex', alignItems: 'center', gap: 8 }}><FileText size={16} /> 客户 Brief</h4>
          <Badge variant={project.brief?.template === '有道' ? 'blue' : project.brief?.template === 'AI课程' ? 'purple' : 'default'}>模板：{project.brief?.template || '自定义'}</Badge>
        </div>
        <div style={{ padding: 16, background: '#12161C', borderRadius: 8, borderLeft: '3px solid #3B82F6' }}>
          <p style={{ margin: 0, color: '#C8CDD5', fontSize: 14, lineHeight: 1.7 }}>{project.brief?.description || project.description}</p>
        </div>
      </div>

      {/* 达人池预览 */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h4 style={{ margin: 0, color: '#E8ECF1' }}>达人池预览 <span style={{ color: '#8B95A5', fontWeight: 400, fontSize: 14 }}>（{creators.length}人）</span></h4>
          <button className="btn btn-sm btn-secondary" onClick={() => onTabChange('screening-review')}>查看全部筛选 <ArrowRight size={14} /></button>
        </div>
        <DataTable
          columns={[
            { key: 'name', label: '达人昵称', render: (v, row) => (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 28, height: 28, borderRadius: '50%', background: '#2A3040', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, color: '#8B95A5', fontWeight: 600 }}>{v[0]}</div>
                <span style={{ color: '#E8ECF1' }}>{v}</span>
              </div>
            )},
            { key: 'type', label: '类型', render: (v, row) => <Badge variant={row.typeVariant}>{v}</Badge> },
            { key: 'followers', label: '粉丝数' },
            { key: 'quote', label: '报价' },
            { key: 'baseScore', label: '评分', render: v => <span style={{ fontWeight: 600, color: getScoreColor(v) }}>{v}</span> },
            { key: 'risk', label: '风险', render: v => v?.length > 0 ? v.map((t, i) => <span key={i} className="tag" style={{ marginRight: 4, fontSize: 11 }}>{t}</span>) : <span style={{ color: '#5A6478' }}>-</span> },
          ]}
          data={creators.slice(0, 5)}
        />
        {creators.length > 5 && (
          <div style={{ textAlign: 'center', padding: '12px 0 0', borderTop: '1px solid #2A3040' }}>
            <button className="btn btn-sm btn-ghost" onClick={() => onTabChange('score-preview')}>还有 {creators.length - 5} 位达人，查看完整评分 <ArrowRight size={14} /></button>
          </div>
        )}
      </div>
    </div>
  );
}

// ==================== 初筛评分 + 人工筛选 ====================

function ScreeningReviewTab({ project, screeningStatus, setScreeningStatus, onReview, onRefresh, onScore, onImport, onCollect }) {
  const creators = useMemo(() => getProjectCreators(project).map(c => ({
    ...c, ...getCreatorStatus(project.id, c.id, screeningStatus)
  })), [project, screeningStatus]);

  const [statusFilter, setStatusFilter] = useState('全部');
  const [typeFilter, setTypeFilter] = useState('全部');
  const [searchTerm, setSearchTerm] = useState('');
  const [sortField, setSortField] = useState('baseScore');
  const [sortDir, setSortDir] = useState('desc');
  const [selectedIds, setSelectedIds] = useState([]);
  const [expandedId, setExpandedId] = useState(null);
  const [reviewModal, setReviewModal] = useState(null); // { creator, action }
  const [reviewComment, setReviewComment] = useState('');

  const filtered = useMemo(() => {
    let list = [...creators];
    if (statusFilter !== '全部') list = list.filter(c => c.review === statusFilter);
    if (typeFilter !== '全部') list = list.filter(c => c.type === typeFilter);
    if (searchTerm) list = list.filter(c => c.name.includes(searchTerm));
    list.sort((a, b) => {
      const av = a[sortField], bv = b[sortField];
      if (typeof av === 'number' && typeof bv === 'number') return sortDir === 'desc' ? bv - av : av - bv;
      return sortDir === 'desc' ? String(bv).localeCompare(String(av)) : String(av).localeCompare(String(bv));
    });
    return list;
  }, [creators, statusFilter, typeFilter, searchTerm, sortField, sortDir]);

  const stats = useMemo(() => {
    const s = { total: creators.length, passed: 0, rejected: 0, backup: 0, review: 0, pending: 0 };
    creators.forEach(c => {
      if (c.review === '已通过') s.passed++;
      else if (c.review === '已驳回' || c.review === '默认淘汰') s.rejected++;
      else if (c.review === '备选') s.backup++;
      else if (c.review === '人工复核') s.review++;
      else s.pending++;
    });
    return s;
  }, [creators]);

  const handleReview = async (creator, action) => {
    const status = action === 'pass' ? '已通过' : action === 'reject' ? '已驳回' : action === 'backup' ? '备选' : '待审核';
    if (onReview) {
      await onReview([creator.id], status, reviewComment || (action === 'pass' ? '人工审核通过' : action === 'reject' ? '人工审核驳回' : '加入备选'));
      setReviewModal(null);
      setReviewComment('');
      return;
    }
    const newStatus = { ...screeningStatus };
    if (!newStatus[project.id]) newStatus[project.id] = {};
    const now = new Date().toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-');
    newStatus[project.id][creator.id] = {
      review: action === 'pass' ? '已通过' : action === 'reject' ? '已驳回' : action === 'backup' ? '备选' : '人工复核',
      reviewVariant: action === 'pass' ? 'green' : action === 'reject' ? 'red' : 'amber',
      finalScore: creator.baseScore,
      reason: reviewComment || (action === 'pass' ? '人工审核通过' : action === 'reject' ? '人工审核驳回' : '加入备选'),
      reviewer: '当前用户',
      reviewedAt: now,
    };
    setScreeningStatus(newStatus);
    setReviewModal(null);
    setReviewComment('');
  };

  const handleBatchPass = async () => {
    if (onReview) {
      const ids = creators.filter(c => ['待审核', '待补数据'].includes(c.review) && c.baseScore >= 85 && !c.risk.includes('无蒲公英') && !c.risk.includes('广告过多')).map(c => c.id);
      if (ids.length) await onReview(ids, '已通过', '批量通过（评分>=85，无硬性淘汰项）');
      return;
    }
    const newStatus = { ...screeningStatus };
    if (!newStatus[project.id]) newStatus[project.id] = {};
    const now = new Date().toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-');
    let count = 0;
    creators.filter(c => c.review === '待审核' && c.baseScore >= 85 && !c.risk.includes('无蒲公英') && !c.risk.includes('广告过多')).forEach(c => {
      newStatus[project.id][c.id] = { review: '已通过', reviewVariant: 'green', finalScore: c.baseScore, reason: '批量通过（评分>=85，无硬性淘汰项）', reviewer: '当前用户', reviewedAt: now };
      count++;
    });
    setScreeningStatus(newStatus);
    setSelectedIds([]);
  };

  const handleBatchReject = async () => {
    if (onReview) {
      const ids = creators.filter(c => ['待审核', '待补数据'].includes(c.review) && (c.baseScore < 70 || c.risk.includes('无蒲公英') || c.risk.includes('广告过多') || c.risk.includes('信任度低'))).map(c => c.id);
      if (ids.length) await onReview(ids, '已驳回', '批量淘汰（评分<70或命中硬性淘汰项）');
      return;
    }
    const newStatus = { ...screeningStatus };
    if (!newStatus[project.id]) newStatus[project.id] = {};
    const now = new Date().toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-');
    let count = 0;
    creators.filter(c => c.review === '待审核' && (c.baseScore < 70 || c.risk.includes('无蒲公英') || c.risk.includes('广告过多') || c.risk.includes('信任度低'))).forEach(c => {
      newStatus[project.id][c.id] = { review: '已驳回', reviewVariant: 'red', finalScore: c.baseScore, reason: '批量淘汰（评分<70或命中硬性淘汰项）', reviewer: '当前用户', reviewedAt: now };
      count++;
    });
    setScreeningStatus(newStatus);
    setSelectedIds([]);
  };

  const toggleSort = (field) => {
    if (sortField === field) setSortDir(d => d === 'desc' ? 'asc' : 'desc');
    else { setSortField(field); setSortDir('desc'); }
  };

  const SortIcon = ({ field }) => {
    if (sortField !== field) return <ChevronDown size={12} style={{ color: '#5A6478', marginLeft: 2 }} />;
    return sortDir === 'desc' ? <ChevronDown size={12} style={{ color: '#3B82F6', marginLeft: 2 }} /> : <ChevronUp size={12} style={{ color: '#3B82F6', marginLeft: 2 }} />;
  };

  const scoreDimLabels = { budget: '预算匹配', fans: '粉丝量级', cpe: 'CPE效率', engagement: '互动质量', persona: '人设匹配', content: '内容风格' };

  return (
    <div>
      {/* 统计概览 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12, marginBottom: 20 }}>
        {[
          { label: '达人总数', value: stats.total, color: '#8B95A5' },
          { label: '已通过', value: stats.passed, color: '#10B981' },
          { label: '已驳回', value: stats.rejected, color: '#EF4444' },
          { label: '备选', value: stats.backup, color: '#F59E0B' },
          { label: '人工复核', value: stats.review, color: '#3B82F6' },
          { label: '待审核', value: stats.pending, color: '#5A6478' },
        ].map(s => (
          <div key={s.label} className="card" style={{ padding: '12px 16px', textAlign: 'center' }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: s.color }}>{s.value}</div>
            <div style={{ fontSize: 12, color: '#8B95A5', marginTop: 2 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* 工具栏 */}
      <div className="card" style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <div className="search-box" style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#8B95A5' }} />
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
          <button className="btn btn-sm btn-ghost" onClick={onRefresh}><RefreshCw size={14} /></button>
          <button className="btn btn-sm btn-secondary" onClick={handleBatchPass} title="批量通过评分>=85且无硬性淘汰项的达人"><UserCheck size={14} style={{ marginRight: 4 }} />批量通过</button>
          <button className="btn btn-sm btn-danger" onClick={handleBatchReject} title="批量淘汰评分<70或命中硬性淘汰项的达人"><UserX size={14} style={{ marginRight: 4 }} />批量淘汰</button>
        </div>
      </div>

      {/* 达人列表 */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #2A3040' }}>
              <th style={{ padding: '12px 16px', textAlign: 'left', color: '#8B95A5', fontWeight: 500, fontSize: 12 }}>达人</th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: '#8B95A5', fontWeight: 500, fontSize: 12 }}>类型</th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: '#8B95A5', fontWeight: 500, fontSize: 12, cursor: 'pointer' }} onClick={() => toggleSort('followersNum')}>粉丝数 <SortIcon field="followersNum" /></th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: '#8B95A5', fontWeight: 500, fontSize: 12, cursor: 'pointer' }} onClick={() => toggleSort('quoteNum')}>报价 <SortIcon field="quoteNum" /></th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: '#8B95A5', fontWeight: 500, fontSize: 12, cursor: 'pointer' }} onClick={() => toggleSort('baseScore')}>评分 <SortIcon field="baseScore" /></th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: '#8B95A5', fontWeight: 500, fontSize: 12 }}>风险</th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: '#8B95A5', fontWeight: 500, fontSize: 12 }}>审核状态</th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: '#8B95A5', fontWeight: 500, fontSize: 12 }}>审核意见</th>
              <th style={{ padding: '12px 16px', textAlign: 'center', color: '#8B95A5', fontWeight: 500, fontSize: 12 }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(creator => (
              <React.Fragment key={creator.id}>
                <tr style={{ borderBottom: '1px solid #1A1F2B', cursor: 'pointer', transition: 'background 0.15s' }}
                  onMouseEnter={e => e.currentTarget.style.background = '#12161C'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                  <td style={{ padding: '12px 16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{ width: 32, height: 32, borderRadius: '50%', background: '#2A3040', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: '#C8CDD5', fontWeight: 600, flexShrink: 0 }}>{creator.name[0]}</div>
                      <div>
                        <div style={{ color: '#E8ECF1', fontWeight: 500 }}>{creator.name}</div>
                        <div style={{ fontSize: 11, color: '#5A6478' }}>ID: {creator.id}</div>
                      </div>
                    </div>
                  </td>
                  <td style={{ padding: '12px' }}><Badge variant={creator.typeVariant}>{creator.type}</Badge></td>
                  <td style={{ padding: '12px', color: '#C8CDD5' }}>{creator.followers}</td>
                  <td style={{ padding: '12px', color: '#C8CDD5' }}>{creator.quote}</td>
                  <td style={{ padding: '12px' }}>
                    <span style={{ fontWeight: 700, fontSize: 15, color: getScoreColor(creator.baseScore) }}>{creator.baseScore}</span>
                  </td>
                  <td style={{ padding: '12px' }}>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {creator.risk.map((t, i) => <span key={i} className="tag" style={{ fontSize: 10, color: t.includes('无') || t.includes('低') || t.includes('过多') || t.includes('低') ? '#EF4444' : '#F59E0B' }}>{t}</span>)}
                    </div>
                  </td>
                  <td style={{ padding: '12px' }}><Badge variant={getReviewVariant(creator.review)}>{creator.review}</Badge></td>
                  <td style={{ padding: '12px', maxWidth: 140 }}>
                    <div style={{ fontSize: 12, color: '#8B95A5', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{creator.reason || '-'}</div>
                    {creator.reviewer && <div style={{ fontSize: 10, color: '#5A6478', marginTop: 2 }}>{creator.reviewer} · {creator.reviewedAt}</div>}
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
                        <button className="btn btn-sm btn-ghost" style={{ color: '#8B95A5' }} onClick={(e) => { e.stopPropagation(); setReviewModal({ creator, action: 'reset' }); }} title="重置"><RotateCcw size={15} /></button>
                      )}
                      <button className="btn btn-sm btn-ghost" onClick={(e) => { e.stopPropagation(); setExpandedId(expandedId === creator.id ? null : creator.id); }}><ChevronDown size={15} style={{ transform: expandedId === creator.id ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} /></button>
                    </div>
                  </td>
                </tr>
                {expandedId === creator.id && (
                  <tr style={{ background: '#0D1117' }}>
                    <td colSpan={9} style={{ padding: '16px 24px', borderBottom: '1px solid #2A3040' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
                        {/* 评分维度 */}
                        <div>
                          <div style={{ fontSize: 12, color: '#8B95A5', marginBottom: 12, fontWeight: 600 }}>评分维度明细</div>
                          {creator.scores && Object.entries(creator.scores).map(([key, val]) => (
                            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                              <span style={{ fontSize: 12, color: '#8B95A5', width: 70, flexShrink: 0 }}>{scoreDimLabels[key] || key}</span>
                              <div style={{ flex: 1, height: 6, background: '#1A1F2B', borderRadius: 3, overflow: 'hidden' }}>
                                <div style={{ width: `${val}%`, height: '100%', background: getScoreColor(val), borderRadius: 3, transition: 'width 0.3s' }} />
                              </div>
                              <span style={{ fontSize: 12, fontWeight: 600, color: getScoreColor(val), width: 28, textAlign: 'right' }}>{val}</span>
                            </div>
                          ))}
                        </div>
                        {/* AI 推荐理由 */}
                        <div>
                          <div style={{ fontSize: 12, color: '#8B95A5', marginBottom: 12, fontWeight: 600 }}>AI 推荐理由</div>
                          <div style={{ padding: 12, background: '#12161C', borderRadius: 8, borderLeft: '3px solid #8B5CF6' }}>
                            <p style={{ margin: 0, color: '#C8CDD5', fontSize: 13, lineHeight: 1.7 }}>{creator.aiReason || '暂无 AI 评估'}</p>
                          </div>
                          {creator.risk.length > 0 && (
                            <div style={{ marginTop: 12 }}>
                              <div style={{ fontSize: 12, color: '#8B95A5', marginBottom: 6 }}>风险提示</div>
                              {creator.risk.map((r, i) => (
                                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                                  <AlertTriangle size={12} style={{ color: '#F59E0B', flexShrink: 0 }} />
                                  <span style={{ fontSize: 12, color: '#C8CDD5' }}>{r}</span>
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
          <div style={{ textAlign: 'center', padding: 48, color: '#5A6478' }}>
            <Users size={32} style={{ marginBottom: 8 }} />
            <div>暂无匹配达人</div>
          </div>
        )}
        <div style={{ padding: '12px 16px', borderTop: '1px solid #2A3040', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12, color: '#8B95A5' }}>
          <span>共 {filtered.length} 位达人</span>
          <span>筛选自 {creators.length} 位达人池</span>
        </div>
      </div>

      {/* 审核确认弹窗 */}
      {reviewModal && (
        <div className="modal-overlay" onClick={() => setReviewModal(null)}>
          <div className="modal" style={{ maxWidth: 420 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ margin: 0, color: '#E8ECF1' }}>
                {reviewModal.action === 'pass' && '确认通过'}
                {reviewModal.action === 'reject' && '确认驳回'}
                {reviewModal.action === 'backup' && '加入备选'}
                {reviewModal.action === 'reset' && '重置审核'}
              </h3>
              <button className="btn btn-ghost btn-sm modal-close" onClick={() => setReviewModal(null)}><X size={16} /></button>
            </div>
            <div className="modal-body">
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, padding: 12, background: '#12161C', borderRadius: 8 }}>
                <div style={{ width: 40, height: 40, borderRadius: '50%', background: '#2A3040', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, color: '#C8CDD5', fontWeight: 600 }}>{reviewModal.creator.name[0]}</div>
                <div>
                  <div style={{ color: '#E8ECF1', fontWeight: 500 }}>{reviewModal.creator.name}</div>
                  <div style={{ fontSize: 12, color: '#8B95A5' }}>{reviewModal.creator.type} · {reviewModal.creator.followers} · 评分 {reviewModal.creator.baseScore}</div>
                </div>
              </div>
              <div>
                <label style={{ fontSize: 12, color: '#8B95A5', display: 'block', marginBottom: 4 }}>审核备注</label>
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

// ==================== 候选评分预览 ====================

function ScorePreviewTab({ project }) {
  const creators = useMemo(() => getProjectCreators(project), [project]);

  const scoreDistribution = useMemo(() => {
    const dist = { excellent: 0, good: 0, average: 0, poor: 0 };
    creators.forEach(c => {
      if (c.baseScore >= 85) dist.excellent++;
      else if (c.baseScore >= 70) dist.good++;
      else if (c.baseScore >= 55) dist.average++;
      else dist.poor++;
    });
    return dist;
  }, [creators]);

  const avgScore = useMemo(() => {
    if (creators.length === 0) return 0;
    return (creators.reduce((sum, c) => sum + c.baseScore, 0) / creators.length).toFixed(1);
  }, [creators]);

  const [sortBy, setSortBy] = useState('baseScore');
  const [sortDir, setSortDir] = useState('desc');

  const sorted = useMemo(() => {
    return [...creators].sort((a, b) => sortDir === 'desc' ? b[sortBy] - a[sortBy] : a[sortBy] - b[sortBy]);
  }, [creators, sortBy, sortDir]);

  const scoreDimLabels = { budget: '预算匹配', fans: '粉丝量级', cpe: 'CPE效率', engagement: '互动质量', persona: '人设匹配', content: '内容风格' };

  return (
    <div>
      {/* 评分统计概览 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
        <StatCard title="达人总数" value={creators.length} subtitle="人" icon={Users} color="blue" />
        <StatCard title="平均评分" value={avgScore} subtitle="分" icon={Star} color="purple" />
        <StatCard title="建议通过" value={scoreDistribution.excellent} subtitle={`≥85分`} icon={UserCheck} color="green" />
        <StatCard title="默认淘汰" value={scoreDistribution.poor + scoreDistribution.average} subtitle={`<70分`} icon={UserX} color="red" />
      </div>

      {/* 评分分布 */}
      <div className="card" style={{ marginBottom: 24 }}>
        <h4 style={{ margin: '0 0 16px', color: '#E8ECF1' }}>评分分布</h4>
        <div style={{ display: 'flex', gap: 16, alignItems: 'flex-end', height: 120 }}>
          {[
            { label: '优秀 (≥85)', count: scoreDistribution.excellent, color: '#10B981' },
            { label: '良好 (70-84)', count: scoreDistribution.good, color: '#3B82F6' },
            { label: '一般 (55-69)', count: scoreDistribution.average, color: '#F59E0B' },
            { label: '较差 (<55)', count: scoreDistribution.poor, color: '#EF4444' },
          ].map(item => (
            <div key={item.label} style={{ flex: 1, textAlign: 'center' }}>
              <div style={{ fontSize: 20, fontWeight: 700, color: item.color, marginBottom: 8 }}>{item.count}</div>
              <div style={{ height: 60, background: '#1A1F2B', borderRadius: 4, overflow: 'hidden', display: 'flex', alignItems: 'flex-end' }}>
                <div style={{ width: '100%', height: `${creators.length > 0 ? (item.count / creators.length) * 100 : 0}%`, background: item.color, borderRadius: 4, minHeight: item.count > 0 ? 8 : 0, transition: 'height 0.3s' }} />
              </div>
              <div style={{ fontSize: 11, color: '#8B95A5', marginTop: 6 }}>{item.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 评分排名列表 */}
      <div className="card" style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ margin: 0, color: '#E8ECF1' }}>评分排名</h4>
        <div style={{ display: 'flex', gap: 8 }}>
          {['baseScore', 'quoteNum', 'followersNum'].map(field => (
            <button key={field} className={`btn btn-sm ${sortBy === field ? 'btn-secondary' : 'btn-ghost'}`}
              onClick={() => { if (sortBy === field) setSortDir(d => d === 'desc' ? 'asc' : 'desc'); else { setSortBy(field); setSortDir('desc'); } }}>
              {field === 'baseScore' ? '评分' : field === 'quoteNum' ? '报价' : '粉丝'}
              {sortBy === field && (sortDir === 'desc' ? ' ↓' : ' ↑')}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
        {sorted.map((creator, idx) => (
          <div key={creator.id} className="card" style={{ padding: 16, border: '1px solid #2A3040' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{
                  width: 28, height: 28, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 12, fontWeight: 700, color: idx < 3 ? '#fff' : '#8B95A5',
                  background: idx === 0 ? '#F59E0B' : idx === 1 ? '#94A3B8' : idx === 2 ? '#CD7F32' : '#2A3040',
                }}>{idx + 1}</div>
                <div>
                  <div style={{ color: '#E8ECF1', fontWeight: 500, fontSize: 14 }}>{creator.name}</div>
                  <div style={{ fontSize: 11, color: '#5A6478' }}>{creator.type} · {creator.followers}</div>
                </div>
              </div>
              <span style={{ fontSize: 22, fontWeight: 700, color: getScoreColor(creator.baseScore) }}>{creator.baseScore}</span>
            </div>
            {/* 维度小条 */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
              {creator.scores && Object.entries(creator.scores).slice(0, 6).map(([key, val]) => (
                <div key={key} style={{ textAlign: 'center' }}>
                  <div style={{ height: 3, background: '#1A1F2B', borderRadius: 2, marginBottom: 3, overflow: 'hidden' }}>
                    <div style={{ width: `${val}%`, height: '100%', background: getScoreColor(val), borderRadius: 2 }} />
                  </div>
                  <span style={{ fontSize: 10, color: '#5A6478' }}>{scoreDimLabels[key]}</span>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10, paddingTop: 10, borderTop: '1px solid #1A1F2B' }}>
              <span style={{ fontSize: 12, color: '#C8CDD5' }}>{creator.quote}</span>
              <div style={{ display: 'flex', gap: 4 }}>
                {creator.risk.map((t, i) => <span key={i} className="tag" style={{ fontSize: 10 }}>{t}</span>)}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ==================== 立项 + 标准 + 飞书绑定 ====================

function ProjectSetupTab({ project, feishuConfig, feishuFields, feishuTables, onSaveProject, onSaveFeishu, onTestFeishu, onLoadTables, onLoadFields, onWriteBack }) {
  const [activeSection, setActiveSection] = useState('info');
  const [screeningPlan, setScreeningPlan] = useState(project.screeningPlan || {});
  const [standardStatus, setStandardStatus] = useState('');
  const [optimizingStandard, setOptimizingStandard] = useState(false);
  const [form, setForm] = useState({
    name: project.name, product: project.product, budget: project.budget,
    singleBudget: project.singleBudget || '', creatorCount: project.creatorCount,
    periodStart: project.periodStart || '', periodEnd: project.periodEnd || '',
    cooperationType: project.cooperationType || '合作笔记', description: project.description,
  });
  const [saved, setSaved] = useState(false);
  const [feishuForm, setFeishuForm] = useState({
    feishu_url: feishuConfig?.feishu_url || project.feishuBinding?.tableUrl || '',
    app_id: feishuConfig?.app_id || '',
    app_secret: '',
    table_id: project.feishuBinding?.tableId || '',
  });

  useEffect(() => {
    setScreeningPlan(project.screeningPlan || {});
    setFeishuForm(old => ({
      ...old,
      feishu_url: feishuConfig?.feishu_url || project.feishuBinding?.tableUrl || '',
      app_id: feishuConfig?.app_id || old.app_id || '',
      table_id: project.feishuBinding?.tableId || old.table_id || '',
    }));
  }, [feishuConfig, project.feishuBinding?.tableId, project.feishuBinding?.tableUrl, project.screeningPlan]);

  const sections = [
    { key: 'info', label: '立项信息', icon: <FileText size={14} /> },
    { key: 'standard', label: '量化标准', icon: <Target size={14} /> },
    { key: 'feishu', label: '飞书绑定', icon: <Link2 size={14} /> },
  ];

  const labelStyle = { fontSize: 12, color: '#8B95A5', display: 'block', marginBottom: 4 };

  const optimizeStandard = async () => {
    setOptimizingStandard(true);
    setStandardStatus('正在读取飞书字段并调用大模型优化...');
    try {
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
      setScreeningPlan(result.screeningPlan || {});
      setStandardStatus(result.source === 'llm' ? '已调用大模型，并结合飞书字段完成优化' : result.message || '已生成兜底量化标准');
    } catch (error) {
      setStandardStatus(error.message || error.message_cn || error.detail?.message || '优化量化标准失败，请检查大模型配置和飞书绑定');
    } finally {
      setOptimizingStandard(false);
    }
  };

  return (
    <div>
      {/* 分段 Tab */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 24, borderBottom: '1px solid #2A3040', paddingBottom: 0 }}>
        {sections.map(s => (
          <button key={s.key} onClick={() => setActiveSection(s.key)}
            style={{
              padding: '10px 20px', background: 'none', border: 'none', cursor: 'pointer',
              color: activeSection === s.key ? '#E8ECF1' : '#8B95A5', fontSize: 14, fontWeight: activeSection === s.key ? 600 : 400,
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
            <h4 style={{ margin: 0, color: '#E8ECF1' }}>项目立项信息</h4>
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
              <h4 style={{ margin: 0, color: '#E8ECF1' }}>Brief 量化标准</h4>
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
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginTop: 10 }}>
                <span style={{ fontSize: 12, color: standardStatus.includes('失败') ? '#FCA5A5' : '#8B95A5' }}>{standardStatus || '会结合当前 Brief、项目预算和飞书字段优化量化标准'}</span>
                <button className="btn btn-secondary" onClick={optimizeStandard} disabled={optimizingStandard || !form.description?.trim()}>
                  <Sparkles size={14} style={{ marginRight: 4 }} />{optimizingStandard ? '优化中...' : 'AI 优化量化标准'}
                </button>
              </div>
            </div>
            {screeningPlan?.briefType ? (
              <div>
                {/* 硬性条件 */}
                <div style={{ marginBottom: 20 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#E8ECF1', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Shield size={14} style={{ color: '#EF4444' }} /> 硬性筛选条件
                  </div>
                  {(screeningPlan.hardFilters || []).length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {(screeningPlan.hardFilters || []).map((f, i) => (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px', background: '#12161C', borderRadius: 6 }}>
                          <Badge variant="red" style={{ flexShrink: 0 }}>硬性</Badge>
                          <span style={{ color: '#C8CDD5', fontSize: 13 }}>{f.field}</span>
                          <span style={{ color: '#8B95A5', fontSize: 13 }}>{f.condition}</span>
                          <span style={{ color: '#E8ECF1', fontSize: 13, fontWeight: 600 }}>{f.value}</span>
                          {f.feishuField && <span className="tag" style={{ marginLeft: 'auto', fontSize: 11 }}>飞书：{f.feishuField}</span>}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ padding: 16, background: '#12161C', borderRadius: 6, textAlign: 'center', color: '#5A6478' }}>
                      暂未设置硬性条件，可在 Brief 中描述后由 AI 自动生成
                    </div>
                  )}
                </div>

                {/* 评分权重 */}
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#E8ECF1', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Activity size={14} style={{ color: '#3B82F6' }} /> 评分维度权重
                  </div>
                  {Object.keys(screeningPlan.scoringWeights || {}).length > 0 ? (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                      {Object.entries(screeningPlan.scoringWeights || {}).map(([key, weight]) => {
                        const labels = { budget: '预算匹配', fans: '粉丝量级', cpe: 'CPE效率', engagement: '互动质量', persona: '人设匹配', content: '内容风格' };
                        return (
                          <div key={key} style={{ padding: 12, background: '#12161C', borderRadius: 6 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                              <span style={{ fontSize: 12, color: '#8B95A5' }}>{labels[key] || key}</span>
                              <span style={{ fontSize: 16, fontWeight: 700, color: '#3B82F6' }}>{weight}%</span>
                            </div>
                            <ProgressBar value={weight} size="sm" color="blue" />
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div style={{ padding: 16, background: '#12161C', borderRadius: 6, textAlign: 'center', color: '#5A6478' }}>
                      暂未生成评分标准
                    </div>
                  )}
                </div>
                {(screeningPlan.fieldMappings || []).length > 0 && (
                  <div style={{ marginTop: 20 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#E8ECF1', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
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
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: 32 }}>
                <Bot size={32} style={{ color: '#5A6478', marginBottom: 12 }} />
                <p style={{ color: '#8B95A5', marginBottom: 16 }}>尚未生成量化标准，请先在 Brief 中描述需求</p>
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
              <h4 style={{ margin: 0, color: '#E8ECF1' }}>飞书表格绑定</h4>
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
                <button className="btn btn-secondary" onClick={() => onTestFeishu?.(feishuForm)}><CheckCircle2 size={14} style={{ marginRight: 4 }} />测试连接</button>
                <button className="btn btn-secondary" onClick={onLoadTables}><Database size={14} style={{ marginRight: 4 }} />读取子表</button>
                <button className="btn btn-primary" onClick={() => onWriteBack?.(feishuForm.table_id)}><Send size={14} style={{ marginRight: 4 }} />写回飞书</button>
              </div>

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
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#E8ECF1', marginBottom: 12 }}>字段映射关系</div>
                  {(project.feishuBinding.fieldMapping || []).length > 0 ? (
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid #2A3040' }}>
                          <th style={{ padding: '8px 12px', textAlign: 'left', color: '#8B95A5', fontWeight: 500, fontSize: 12 }}>标准字段</th>
                          <th style={{ padding: '8px 12px', textAlign: 'left', color: '#8B95A5', fontWeight: 500, fontSize: 12 }}>飞书字段</th>
                          <th style={{ padding: '8px 12px', textAlign: 'left', color: '#8B95A5', fontWeight: 500, fontSize: 12 }}>类型</th>
                          <th style={{ padding: '8px 12px', textAlign: 'left', color: '#8B95A5', fontWeight: 500, fontSize: 12 }}>可写</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(project.feishuBinding.fieldMapping || []).map((fm, i) => {
                          const matched = (feishuFields || []).find(field => [field.field_name, field.name].includes(fm.standard) || [field.field_name, field.name].includes(fm.feishu));
                          return (
                          <tr key={i} style={{ borderBottom: '1px solid #1A1F2B' }}>
                            <td style={{ padding: '8px 12px', color: '#E8ECF1' }}>{fm.standard}</td>
                            <td style={{ padding: '8px 12px', color: '#C8CDD5' }}>{matched?.field_name || matched?.name || fm.feishu}</td>
                            <td style={{ padding: '8px 12px' }}><Badge variant="default">{fm.type}</Badge></td>
                            <td style={{ padding: '8px 12px' }}>
                              <Badge variant={matched ? 'green' : 'amber'}>{matched ? '可写' : '待匹配'}</Badge>
                            </td>
                          </tr>
                        )})}
                      </tbody>
                    </table>
                  ) : (
                    <div style={{ padding: 16, background: '#12161C', borderRadius: 6, textAlign: 'center', color: '#5A6478' }}>暂无字段映射</div>
                  )}
                </div>

              </div>
            </div>

          {/* 写回校验清单 */}
          {project.feishuBinding?.linked && (
            <div className="card">
              <h4 style={{ margin: '0 0 16px', color: '#E8ECF1' }}>写回前校验清单</h4>
              {[
                { label: '字段映射已确认', done: true },
                { label: '写回字段均为可写字段', done: true },
                { label: '达人记录已通过审核', done: false },
                { label: '已按蒲公英链接或达人 ID 去重', done: true },
                { label: '必填字段不为空', done: false },
                { label: '项目 ID 和采集批次完整', done: true },
              ].map((item, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: i < 5 ? '1px solid #1A1F2B' : 'none' }}>
                  <div style={{ width: 20, height: 20, borderRadius: '50%', border: item.done ? 'none' : '2px solid #5A6478', background: item.done ? '#10B981' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {item.done && <CheckCircle2 size={12} color="#fff" />}
                  </div>
                  <span style={{ color: item.done ? '#8B95A5' : '#C8CDD5', fontSize: 13, textDecoration: item.done ? 'line-through' : 'none' }}>{item.label}</span>
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
        <span style={{ fontSize: 12, color: '#8B95A5' }}>共 {logs.length} 条记录</span>
      </div>

      {/* 时间线 */}
      <div className="card" style={{ padding: '24px 24px 24px 32px' }}>
        {logs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32, color: '#5A6478' }}>
            <ScrollText size={32} style={{ marginBottom: 8 }} />
            <div>暂无操作日志</div>
          </div>
        ) : (
          <div style={{ position: 'relative' }}>
            {/* 时间线竖线 */}
            <div style={{ position: 'absolute', left: 7, top: 8, bottom: 8, width: 2, background: '#2A3040' }} />

            {logs.map((log, idx) => {
              const cfg = typeConfig[log.type] || typeConfig.project;
              const scfg = statusConfig[log.status] || statusConfig.info;
              return (
                <div key={log.id} className="timeline-item" style={{ position: 'relative', paddingLeft: 28, paddingBottom: idx < logs.length - 1 ? 24 : 0 }}>
                  {/* 时间线圆点 */}
                  <div className="timeline-dot" style={{
                    position: 'absolute', left: 0, top: 6, width: 16, height: 16, borderRadius: '50%',
                    background: log.status === 'error' ? '#EF4444' : cfg.color,
                    border: '3px solid #0B0E11',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    {log.status === 'error' && <X size={8} color="#fff" />}
                  </div>

                  {/* 日志内容 */}
                  <div className="timeline-content">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ color: '#E8ECF1', fontWeight: 500, fontSize: 14 }}>{log.action}</span>
                        <Badge variant={scfg.variant}>{scfg.label}</Badge>
                      </div>
                      <span style={{ fontSize: 12, color: '#5A6478' }}>{log.time}</span>
                    </div>
                    <div style={{ fontSize: 13, color: '#C8CDD5', marginBottom: 4 }}>
                      <span style={{ color: '#8B95A5' }}>对象：</span>{log.target}
                    </div>
                    <div style={{ fontSize: 12, color: '#8B95A5', lineHeight: 1.6 }}>{log.detail}</div>
                    <div style={{ fontSize: 11, color: '#5A6478', marginTop: 4 }}>操作人：{log.user}</div>
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
      if (!response.ok) throw new Error(result.error || result.detail || '保存 API 配置失败');
      applyRemoteConfig(result);
      setFeedback(result.message || 'API 配置已保存');
    } catch (error) {
      localStorage.setItem('adflow-api-config', JSON.stringify({ ...config, api_key: '' }));
      setMeta((prev) => ({
        ...prev,
        api_key_configured: prev.api_key_configured || Boolean(config.api_key || config.api_key_env),
        api_key_source: config.api_key ? 'inline' : (config.api_key_env ? 'env' : 'none'),
      }));
      setFeedback(`${error.message || '后端暂不可用'}，已先保存到本地工作台配置。`);
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
      if (!response.ok || result.ok === false) throw new Error(result.error || result.detail || 'API 连接测试失败');
      setFeedback(result.message || 'API 连接测试成功');
    } catch (error) {
      setFeedback(error.message || 'API 连接测试失败');
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
              <KeyRound size={16} style={{ color: '#8B95A5' }} />
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
              <Activity size={16} style={{ color: '#8B95A5' }} />
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

function ScreeningDashboard() {
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

  const selectedProjectId = currentProject?.id || PROJECT_ID;

  const loadData = useCallback(async () => {
    const projectsPayload = await api('/api/projects');
    const rawProjects = (projectsPayload.projects || []).filter(item => item.project_id === PROJECT_ID);
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
      : [mapBackendProject({ project_id: PROJECT_ID, project_name: '有道答疑笔5-6月合作', target_qualified_creator_count: 10 }, [], null)];
    const currentId = currentProject?.id;
    const shouldAutoSelectProject = tab && tab !== 'projects';
    const nextCurrent = currentId
      ? nextProjects.find(project => project.id === currentId)
      : shouldAutoSelectProject
        ? nextProjects[0]
        : null;
    setProjects(nextProjects);
    setCurrentProject(nextCurrent || null);
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
  }, [currentProject?.id, tab]);

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
    setCurrentProject(project);
    loadProjectSideData(project.id).catch(error => setMessage(error.message || '读取项目数据失败'));
    handleTabChange('overview');
  };

  const handleCreateProject = (newProject) => {
    setProjects([...projects, newProject]);
  };

  const handleTabChange = (newTab) => {
    setActiveTab(newTab);
    navigate(`/workbench/screening/${newTab}`, { replace: false });
  };

  const runAction = async (label, action) => {
    setMessage(`${label}中...`);
    try {
      await action();
      await loadData();
      setMessage(`${label}完成`);
    } catch (error) {
      setMessage(error.message || error.message_cn || JSON.stringify(error));
    }
  };

  const handleReview = (creatorIds, reviewStatus, reviewReason) => runAction('审核更新', () => api(`/api/projects/${selectedProjectId}/creators/review`, {
    method: 'POST',
    body: JSON.stringify({ creator_ids: creatorIds, review_status: reviewStatus, review_reason: reviewReason, reviewer: '当前用户' }),
  }));

  const handleImport = () => runAction('导入达人模板', () => api(`/api/projects/${selectedProjectId}/creators/import`, { method: 'POST', body: JSON.stringify({}) }));
  const handleScore = () => runAction('重新评分', () => api(`/api/projects/${selectedProjectId}/creators/score`, { method: 'POST' }));
  const handleCollect = () => runAction('蒲公英采集', () => api('/api/pgy/collect/batch', { method: 'POST', body: JSON.stringify({}) }));
  const handleSaveProject = (payload) => runAction('保存立项信息', () => api(`/api/projects/${selectedProjectId}`, { method: 'POST', body: JSON.stringify(payload) }));
  const handleSaveFeishu = (payload) => runAction('保存飞书配置', async () => {
    const result = await api('/api/projects/feishu/connection', { method: 'POST', body: JSON.stringify({ project_id: selectedProjectId, ...payload }) });
    setFeishuConfig(result.config);
  });
  const handleTestFeishu = (payload) => runAction('飞书校验', async () => {
    const result = await api('/api/projects/feishu/test', { method: 'POST', body: JSON.stringify({ project_id: selectedProjectId, ...payload }) });
    setFeishuFields(result.fields || []);
  });
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
        />
      );
    }

    if (!currentProject) {
      return (
        <div className="card" style={{ textAlign: 'center', padding: 48 }}>
          <FolderOpen size={48} style={{ color: '#5A6478', marginBottom: 16 }} />
          <h4 style={{ color: '#E8ECF1', marginBottom: 8 }}>请先选择项目</h4>
          <p style={{ color: '#8B95A5', marginBottom: 16 }}>进入「项目预览」选择一个项目开始工作</p>
          <button className="btn btn-primary" onClick={() => handleTabChange('projects')}>前往项目预览</button>
        </div>
      );
    }

    switch (activeTab) {
      case 'overview': return <OverviewTab project={currentProject} onTabChange={handleTabChange} />;
      case 'screening-review': return <ScreeningReviewTab project={currentProject} screeningStatus={screeningStatus} setScreeningStatus={setScreeningStatus} onReview={handleReview} onRefresh={loadData} onScore={handleScore} onImport={handleImport} onCollect={handleCollect} />;
      case 'score-preview': return <ScorePreviewTab project={currentProject} />;
      case 'project-setup': return <ProjectSetupTab project={currentProject} feishuConfig={feishuConfig} feishuFields={feishuFields} feishuTables={feishuTables} onSaveProject={handleSaveProject} onSaveFeishu={handleSaveFeishu} onTestFeishu={handleTestFeishu} onLoadTables={handleLoadTables} onLoadFields={handleLoadFields} onWriteBack={handleWriteBack} />;
      case 'audit-log': return <AuditLogTab project={currentProject} />;
      case 'legacy': return <AdvancedConfigTab />;
      default: return <OverviewTab project={currentProject} onTabChange={handleTabChange} />;
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <PageHeader
          title="达人筛选执行工作台"
          subtitle={currentProject ? `当前项目：${currentProject.name}` : "按项目维度管理达人池和筛选流程"}
          breadcrumbs={[{ label: '工作台', path: '/' }, { label: '达人筛选' }]}
        />
        {currentProject && (
          <button className="btn btn-secondary" onClick={() => handleTabChange('projects')}>
            <FolderOpen size={16} style={{ marginRight: 4 }} />切换项目
          </button>
        )}
      </div>

      {message && <div className="card" style={{ padding: 12, marginBottom: 16, color: message.includes('失败') ? '#FCA5A5' : '#C8CDD5' }}>{message}</div>}

      <TabBar tabs={tabs} activeTab={activeTab} onChange={handleTabChange} />

      <div style={{ marginTop: 24 }}>
        {renderTabContent()}
      </div>

      <CreateProjectModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreate={handleCreateProject}
      />
    </div>
  );
}

export default ScreeningDashboard;
