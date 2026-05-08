import React, { useState } from 'react';
import {
  Search, FileText, Sparkles, AlertCircle, TrendingUp, BarChart3,
  Eye, Brain, Bot, Globe, Video, Image, Radio, Plus, Filter,
  Hash, Users, Clock, Target, Zap, MessageSquare, Heart, ThumbsUp,
  ThumbsDown, Share2, Star, ArrowUpRight, ArrowDownRight, ChevronRight,
  LayoutDashboard, Lightbulb, ClipboardList, Palette, Monitor
} from 'lucide-react';
import StatCard from '../../components/StatCard';
import DataTable from '../../components/DataTable';
import Badge from '../../components/Badge';
import ProgressBar from '../../components/ProgressBar';
import TabBar from '../../components/TabBar';
import PageHeader from '../../components/PageHeader';
import AgentCard from '../../components/AgentCard';
import KpiCard from '../../components/KpiCard';

/* ============================================================
   Mock Data
   ============================================================ */

const tabs = [
  { key: 'overview', label: '工作概览', icon: <LayoutDashboard size={14} /> },
  { key: 'insight', label: '舆情洞察', icon: <Eye size={14} /> },
  { key: 'brief', label: 'Brief 中心', icon: <ClipboardList size={14} /> },
  { key: 'creative', label: '创意策略', icon: <Lightbulb size={14} /> },
  { key: 'social', label: '社媒看板', icon: <Monitor size={14} /> },
];

// Tab 1 - 工作概览
const recentBriefs = [
  { id: 1, name: 'Q2 品牌焕新传播方案', brand: '花西子', status: 'active', date: '2026-04-13 14:30' },
  { id: 2, name: '618 大促社媒投放策略', brand: '完美日记', status: 'review', date: '2026-04-13 11:20' },
  { id: 3, name: '新品上市口碑种草计划', brand: '珀莱雅', status: 'draft', date: '2026-04-12 18:45' },
  { id: 4, name: '品牌危机公关预案', brand: '薇诺娜', status: 'urgent', date: '2026-04-12 16:00' },
  { id: 5, name: 'Z世代消费者洞察报告', brand: '橘朵', status: 'active', date: '2026-04-12 10:15' },
];

// Tab 2 - 舆情洞察
const volumeData = [
  { day: '周一', value: 3200 },
  { day: '周二', value: 4500 },
  { day: '周三', value: 3800 },
  { day: '周四', value: 5200 },
  { day: '周五', value: 6100 },
  { day: '周六', value: 4800 },
  { day: '周日', value: 3900 },
];

const consumerPainPoints = [
  { rank: 1, text: '产品成分安全性', percentage: 78 },
  { rank: 2, text: '性价比与定价策略', percentage: 65 },
  { rank: 3, text: '包装设计与环保', percentage: 52 },
  { rank: 4, text: '客服响应速度', percentage: 41 },
  { rank: 5, text: '跨境物流体验', percentage: 35 },
];

const competitorSOV = [
  { brand: '花西子', sov: 34, color: 'var(--accent-purple)' },
  { brand: '完美日记', sov: 28, color: 'var(--accent-cyan)' },
  { brand: '珀莱雅', sov: 22, color: 'var(--accent-amber)' },
];

// Tab 3 - Brief 中心
const briefCards = [
  {
    id: 1,
    brand: '花西子',
    status: 'active',
    briefName: 'Q2 品牌焕新传播方案',
    w2h: {
      what: '提升品牌在Z世代群体中的认知度与好感度',
      who: '18-28岁女性，一二线城市，关注国潮文化',
      when: '2026年5月-7月，为期3个月',
      where: '小红书、抖音、B站为主阵地',
      why: '品牌老化危机，需年轻化转型',
      how: 'KOL种草+UGC共创+跨界联名',
      howMuch: '预算500万，ROI目标1:3',
    },
    keywords: ['花西子', '国潮美妆', '东方美学', 'Z世代', '品牌焕新'],
    targetAudience: '18-28岁一二线城市年轻女性，热爱国潮文化，关注成分安全与东方美学，月均美妆消费300-800元。',
    sellingPoints: ['东方彩妆领导品牌', '苗族银饰工艺联名', '天然草本成分', '高定包装设计'],
    platforms: ['小红书 60%', '抖音 25%', 'B站 15%'],
    riskWords: ['最', '第一', '绝对', '永久', '100%'],
  },
  {
    id: 2,
    brand: '完美日记',
    status: 'review',
    briefName: '618 大促社媒投放策略',
    w2h: {
      what: '618期间全渠道社媒曝光与转化提升',
      who: '20-35岁女性消费者，价格敏感型',
      when: '2026年5月20日-6月20日',
      where: '抖音直播间+小红书种草+微博话题',
      why: '抢占618大促流量红利，冲击品类TOP3',
      how: '预售种草+直播带货+达人矩阵+话题营销',
      howMuch: '预算800万，GMV目标2400万',
    },
    keywords: ['完美日记', '618大促', '直播带货', '种草', '限时折扣'],
    targetAudience: '20-35岁女性，三四线城市渗透为主，价格敏感型消费者，偏好组合套装与赠品策略。',
    sellingPoints: ['大牌同源代工厂', '动物实验零残忍', '明星联名款', '会员专属优惠'],
    platforms: ['抖音 45%', '小红书 30%', '微博 25%'],
    riskWords: ['最低价', '全网首发', '秒杀', '抢购', '限量'],
  },
  {
    id: 3,
    brand: '珀莱雅',
    status: 'draft',
    briefName: '新品上市口碑种草计划',
    w2h: {
      what: '双抗精华3.0新品口碑建立与初期种草',
      who: '25-35岁抗初老需求女性，成分党',
      when: '2026年6月-8月',
      where: '小红书深度种草+知乎成分科普',
      why: '竞品迭代加速，需巩固成分心智',
      how: '成分科普+KOC测评+医生背书+社群运营',
      howMuch: '预算300万，种草笔记目标5000篇',
    },
    keywords: ['珀莱雅', '双抗精华', '抗初老', '成分党', '早C晚A'],
    targetAudience: '25-35岁一二线城市白领女性，有抗初老需求，关注成分配方，偏好科学护肤理念。',
    sellingPoints: ['麦角硫因+虾青素双抗配方', '三甲医院临床验证', '获奖无数', '回购率行业领先'],
    platforms: ['小红书 50%', '知乎 30%', '抖音 20%'],
    riskWords: ['医疗级', '药妆', '治愈', '修复', '特效'],
  },
];

// Tab 4 - 创意策略
const creativeCards = [
  {
    id: 1,
    title: '东方美学 x 赛博朋克',
    contentType: '图文',
    platform: '小红书',
    status: 'active',
    hook: '当千年苗银遇上霓虹灯光，花西子带你解锁国潮新次元',
    gradient: 'linear-gradient(135deg, #8B5CF6 0%, #EC4899 100%)',
    icon: <Sparkles size={32} />,
  },
  {
    id: 2,
    title: '成分实验室系列',
    contentType: '视频',
    platform: '抖音',
    status: 'review',
    hook: '显微镜下的完美日记：每一滴精华都经过7道质检，你看到的是第3步',
    gradient: 'linear-gradient(135deg, #06B6D4 0%, #3B82F6 100%)',
    icon: <Video size={32} />,
  },
  {
    id: 3,
    title: '素人改造挑战赛',
    contentType: '直播',
    platform: 'B站',
    status: 'active',
    hook: '3位UP主、72小时、1套珀莱雅 -- 真实记录皮肤变化，不剪辑不滤镜',
    gradient: 'linear-gradient(135deg, #10B981 0%, #06B6D4 100%)',
    icon: <Radio size={32} />,
  },
  {
    id: 4,
    title: '职场女性的5分钟',
    contentType: '视频',
    platform: '抖音',
    status: 'approved',
    hook: '早八人的护肤真相：不是你没时间，是你没选对 -- 珀莱雅双抗精华实测',
    gradient: 'linear-gradient(135deg, #F59E0B 0%, #EF4444 100%)',
    icon: <Zap size={32} />,
  },
];

// Tab 5 - 社媒看板
const socialVolumeData = [
  { day: '4/7', value: 5200 },
  { day: '4/8', value: 6100 },
  { day: '4/9', value: 5800 },
  { day: '4/10', value: 7200 },
  { day: '4/11', value: 8500 },
  { day: '4/12', value: 6900 },
  { day: '4/13', value: 5500 },
];

const kolData = [
  { id: 1, name: '程十安', platform: '小红书', fans: '1,234万', interaction: '8.2%', status: '合作中', score: 4.8 },
  { id: 2, name: '老爸评测', platform: 'B站', fans: '890万', interaction: '6.5%', status: '合作中', score: 4.6 },
  { id: 3, name: '骆王宇', platform: '抖音', fans: '2,100万', interaction: '5.8%', status: '待续约', score: 4.5 },
  { id: 4, name: '深夜发媸', platform: '小红书', fans: '680万', interaction: '7.1%', status: '已合作', score: 4.3 },
  { id: 5, name: '李佳琦', platform: '抖音', fans: '5,600万', interaction: '4.2%', status: '洽谈中', score: 4.9 },
];

const topicTags = [
  { text: '国潮美妆', size: 'lg', color: 'purple' },
  { text: '成分党', size: 'xl', color: 'cyan' },
  { text: '早C晚A', size: 'md', color: 'green' },
  { text: '平价替代', size: 'lg', color: 'amber' },
  { text: '敏感肌', size: 'md', color: 'red' },
  { text: '抗初老', size: 'xl', color: 'purple' },
  { text: '素颜霜', size: 'sm', color: 'cyan' },
  { text: '防晒', size: 'lg', color: 'amber' },
  { text: '卸妆', size: 'sm', color: 'green' },
  { text: '口红试色', size: 'md', color: 'pink' },
  { text: '眼影盘', size: 'lg', color: 'purple' },
  { text: '精华推荐', size: 'xl', color: 'cyan' },
  { text: '面膜测评', size: 'md', color: 'green' },
  { text: '护肤步骤', size: 'sm', color: 'amber' },
  { text: '医美护肤', size: 'lg', color: 'red' },
  { text: '清洁泥膜', size: 'sm', color: 'pink' },
  { text: '防晒霜推荐', size: 'md', color: 'cyan' },
  { text: '大牌平替', size: 'lg', color: 'purple' },
  { text: '夏日护肤', size: 'xl', color: 'green' },
  { text: '控油', size: 'sm', color: 'amber' },
];

/* ============================================================
   Status Badge Renderer
   ============================================================ */
const statusBadgeMap = {
  active: { variant: 'green', label: '进行中' },
  review: { variant: 'amber', label: '审核中' },
  draft: { variant: 'neutral', label: '草稿' },
  urgent: { variant: 'red', label: '紧急' },
  approved: { variant: 'cyan', label: '已通过' },
};

function renderStatusBadge(status) {
  const config = statusBadgeMap[status] || statusBadgeMap.draft;
  return <Badge variant={config.variant}>{config.label}</Badge>;
}

/* ============================================================
   Tab 1: 工作概览
   ============================================================ */
function TabOverview() {
  const briefColumns = [
    { key: 'name', label: 'Brief 名称' },
    { key: 'brand', label: '品牌' },
    { key: 'status', label: '状态', render: (val) => renderStatusBadge(val) },
    { key: 'date', label: '更新时间' },
  ];

  return (
    <div className="flex flex-col gap-6">
      {/* Top StatCards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          title="监控品牌数"
          value="12"
          change={2}
          changeLabel="本月"
          icon={Search}
          color="purple"
        />
        <StatCard
          title="活跃 Brief"
          value="8"
          change={3}
          changeLabel="本周"
          icon={FileText}
          color="cyan"
        />
        <StatCard
          title="创意方案"
          value="23"
          change={-5}
          changeLabel="vs 上月"
          icon={Sparkles}
          color="amber"
        />
        <StatCard
          title="待审核"
          value="5"
          change={0}
          changeLabel="紧急"
          icon={AlertCircle}
          color="red"
        />
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-4">
        <KpiCard
          title="声量覆盖率"
          value="78%"
          target={85}
          current={78}
          color="purple"
          trend={[
            { value: 65 }, { value: 70 }, { value: 68 }, { value: 72 }, { value: 75 }, { value: 78 },
          ]}
        />
        <KpiCard
          title="策略产出效率"
          value="92%"
          target={90}
          current={92}
          color="green"
          trend={[
            { value: 80 }, { value: 85 }, { value: 82 }, { value: 88 }, { value: 90 }, { value: 92 },
          ]}
        />
      </div>

      {/* Agent Status */}
      <div>
        <div className="section-title">Agent 状态</div>
        <div className="grid grid-cols-2 gap-4">
          <AgentCard
            name="Insight Node"
            type="舆情数据采集"
            status="running"
            lastRun="10 分钟前"
            output="已抓取 1,234 条数据"
            icon={Brain}
          />
          <AgentCard
            name="Brief Parser"
            type="Brief 智能解析"
            status="idle"
            lastRun="2 小时前"
            output="已解析 8 份 Brief"
            icon={Bot}
          />
        </div>
      </div>

      {/* Recent Briefs Table */}
      <div>
        <div className="section-title">最近 Brief</div>
        <DataTable columns={briefColumns} data={recentBriefs} />
      </div>
    </div>
  );
}

/* ============================================================
   Tab 2: 舆情洞察
   ============================================================ */
function TabInsight() {
  const [activePlatform, setActivePlatform] = useState('all');
  const platforms = [
    { key: 'all', label: '全部' },
    { key: 'bilibili', label: 'B站' },
    { key: 'xiaohongshu', label: '小红书' },
    { key: 'weibo', label: '微博' },
    { key: 'douyin', label: '抖音' },
  ];

  const maxVolume = Math.max(...volumeData.map((d) => d.value));

  return (
    <div className="flex flex-col gap-6">
      {/* Search + Platform Filter */}
      <div className="flex items-center gap-4">
        <div className="search-box" style={{ flex: 1, maxWidth: 360 }}>
          <span className="search-icon"><Search size={14} /></span>
          <input
            className="search-input"
            placeholder="搜索品牌、关键词、话题..."
          />
        </div>
        <div className="flex items-center gap-2">
          {platforms.map((p) => (
            <button
              key={p.key}
              className={`btn btn-sm ${activePlatform === p.key ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setActivePlatform(p.key)}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Volume Trend + Sentiment Distribution */}
      <div className="grid gap-4" style={{ gridTemplateColumns: '3fr 2fr' }}>
        {/* Volume Bar Chart */}
        <div className="chart-container">
          <div className="chart-header">
            <h3>声量走势 (近7天)</h3>
            <span className="text-xs text-muted font-mono">单位: 条</span>
          </div>
          <div className="chart-body">
            <div className="flex items-end gap-4" style={{ height: 180 }}>
              {volumeData.map((d) => (
                <div key={d.day} className="flex flex-col items-center gap-2 flex-1">
                  <span className="text-xs font-mono text-secondary">{(d.value / 1000).toFixed(1)}K</span>
                  <div
                    style={{
                      width: '100%',
                      maxWidth: 48,
                      height: `${(d.value / maxVolume) * 140}px`,
                      background: 'linear-gradient(180deg, var(--accent-purple) 0%, rgba(139, 92, 246, 0.3) 100%)',
                      borderRadius: 'var(--radius-sm) var(--radius-sm) 0 0',
                      transition: 'height 0.4s ease',
                    }}
                  />
                  <span className="text-xs text-muted">{d.day}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Sentiment Distribution */}
        <div className="card">
          <div className="card-header">
            <h3>情绪分布</h3>
          </div>
          <div className="card-body">
            <div className="flex flex-col gap-5">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-secondary flex items-center gap-2">
                    <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'var(--accent-green)' }} />
                    正面
                  </span>
                  <span className="text-sm font-mono font-semibold text-primary">62%</span>
                </div>
                <ProgressBar value={62} color="green" size="md" />
              </div>
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-secondary flex items-center gap-2">
                    <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'var(--text-muted)' }} />
                    中性
                  </span>
                  <span className="text-sm font-mono font-semibold text-primary">28%</span>
                </div>
                <ProgressBar value={28} color="blue" size="md" />
              </div>
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-secondary flex items-center gap-2">
                    <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'var(--accent-red)' }} />
                    负面
                  </span>
                  <span className="text-sm font-mono font-semibold text-primary">10%</span>
                </div>
                <ProgressBar value={10} color="red" size="md" />
              </div>
            </div>
            <div className="mt-6 pt-4" style={{ borderTop: '1px solid var(--border-subtle)' }}>
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted">数据来源</span>
                <span className="text-xs text-secondary">全平台聚合分析</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Consumer Pain Points + Competitor SOV */}
      <div className="grid grid-cols-2 gap-4">
        {/* Consumer Pain Points */}
        <div className="card">
          <div className="card-header">
            <h3>消费者痒点 Top 5</h3>
          </div>
          <div className="card-body">
            <div className="flex flex-col gap-4">
              {consumerPainPoints.map((item) => (
                <div key={item.rank} className="flex items-center gap-3">
                  <span
                    className="flex-shrink-0 flex items-center justify-center font-mono font-bold text-xs"
                    style={{
                      width: 24,
                      height: 24,
                      borderRadius: 'var(--radius-sm)',
                      backgroundColor: item.rank <= 3 ? 'var(--accent-purple-subtle)' : 'var(--bg-elevated)',
                      color: item.rank <= 3 ? 'var(--accent-purple)' : 'var(--text-muted)',
                    }}
                  >
                    {item.rank}
                  </span>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm text-primary">{item.text}</span>
                      <span className="text-xs font-mono text-muted">{item.percentage}%</span>
                    </div>
                    <ProgressBar value={item.percentage} color={item.rank === 1 ? 'purple' : 'blue'} size="sm" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Competitor SOV */}
        <div className="card">
          <div className="card-header">
            <h3>竞品 SOV 对比</h3>
          </div>
          <div className="card-body">
            <div className="flex flex-col gap-5">
              {competitorSOV.map((item) => (
                <div key={item.brand}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-primary font-medium">{item.brand}</span>
                    <span className="text-sm font-mono font-semibold" style={{ color: item.color }}>
                      {item.sov}%
                    </span>
                  </div>
                  <div style={{ width: '100%', height: 8, backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-full)', overflow: 'hidden' }}>
                    <div
                      style={{
                        width: `${item.sov}%`,
                        height: '100%',
                        backgroundColor: item.color,
                        borderRadius: 'var(--radius-full)',
                        transition: 'width 0.4s ease',
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-6 pt-4" style={{ borderTop: '1px solid var(--border-subtle)' }}>
              <div className="flex items-center gap-2 text-xs text-muted">
                <BarChart3 size={12} />
                <span>SOV = 品牌声量 / 品类总声量 x 100%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Tab 3: Brief 中心
   ============================================================ */
function TabBrief() {
  const w2hLabels = {
    what: 'What',
    who: 'Who',
    when: 'When',
    where: 'Where',
    why: 'Why',
    how: 'How',
    howMuch: 'How much',
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Action Bar */}
      <div className="flex items-center justify-between">
        <button className="btn btn-primary">
          <Plus size={14} />
          新建 Brief
        </button>
        <div className="search-box" style={{ width: 320 }}>
          <span className="search-icon"><Search size={14} /></span>
          <input className="search-input" placeholder="搜索 Brief..." />
        </div>
      </div>

      {/* Brief Cards */}
      <div className="flex flex-col gap-4">
        {briefCards.map((brief) => (
          <div key={brief.id} className="card">
            <div className="card-header">
              <div className="flex items-center gap-3">
                <span className="text-md font-semibold text-primary">{brief.brand}</span>
                {renderStatusBadge(brief.status)}
              </div>
              <span className="text-sm text-secondary">{brief.briefName}</span>
            </div>
            <div className="card-body">
              {/* 5W2H */}
              <div className="mb-5">
                <div className="section-title mb-3">5W2H 结构化摘要</div>
                <div className="grid grid-cols-2 gap-x-6 gap-y-2">
                  {Object.entries(brief.w2h).map(([key, val]) => (
                    <div key={key} className="flex items-start gap-3 py-2" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                      <span
                        className="flex-shrink-0 text-xs font-mono font-semibold px-2 py-0.5 rounded"
                        style={{
                          backgroundColor: 'var(--accent-purple-subtle)',
                          color: 'var(--accent-purple)',
                          minWidth: 72,
                          textAlign: 'center',
                        }}
                      >
                        {w2hLabels[key]}
                      </span>
                      <span className="text-sm text-secondary">{val}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Keywords */}
              <div className="mb-4">
                <div className="text-xs text-muted mb-2 font-medium uppercase tracking-wide">监测关键词</div>
                <div className="flex flex-wrap gap-2">
                  {brief.keywords.map((kw) => (
                    <span key={kw} className="tag">{kw}</span>
                  ))}
                </div>
              </div>

              {/* Target Audience */}
              <div className="mb-4">
                <div className="text-xs text-muted mb-2 font-medium uppercase tracking-wide">目标人群</div>
                <p className="text-sm text-secondary mb-0" style={{ lineHeight: 'var(--leading-relaxed)' }}>
                  {brief.targetAudience}
                </p>
              </div>

              {/* Selling Points */}
              <div className="mb-4">
                <div className="text-xs text-muted mb-2 font-medium uppercase tracking-wide">核心卖点</div>
                <div className="flex flex-col gap-1">
                  {brief.sellingPoints.map((sp, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm text-secondary">
                      <ChevronRight size={12} style={{ color: 'var(--accent-green)' }} />
                      <span>{sp}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Platforms */}
              <div className="mb-4">
                <div className="text-xs text-muted mb-2 font-medium uppercase tracking-wide">平台建议</div>
                <div className="flex flex-wrap gap-2">
                  {brief.platforms.map((p) => (
                    <span key={p} className="tag" style={{ borderColor: 'var(--accent-cyan)', color: 'var(--accent-cyan)' }}>{p}</span>
                  ))}
                </div>
              </div>

              {/* Risk Words */}
              <div>
                <div className="text-xs text-muted mb-2 font-medium uppercase tracking-wide">风险词</div>
                <div className="flex flex-wrap gap-2">
                  {brief.riskWords.map((rw) => (
                    <span
                      key={rw}
                      className="tag"
                      style={{
                        backgroundColor: 'var(--accent-red-subtle)',
                        borderColor: 'var(--accent-red)',
                        color: 'var(--accent-red)',
                      }}
                    >
                      {rw}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ============================================================
   Tab 4: 创意策略
   ============================================================ */
function TabCreative() {
  const contentTypeIcons = {
    '图文': <Image size={12} />,
    '视频': <Video size={12} />,
    '直播': <Radio size={12} />,
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Top StatCards */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard
          title="进行中方案"
          value="5"
          change={2}
          changeLabel="本周新增"
          icon={Sparkles}
          color="purple"
        />
        <StatCard
          title="待评审"
          value="3"
          change={0}
          changeLabel="需尽快处理"
          icon={FileText}
          color="amber"
        />
        <StatCard
          title="已通过"
          value="12"
          change={4}
          changeLabel="本月"
          icon={Target}
          color="green"
        />
      </div>

      {/* Creative Inspiration Board */}
      <div>
        <div className="section-title">创意灵感板</div>
        <div className="grid grid-cols-2 gap-4">
          {creativeCards.map((card) => (
            <div key={card.id} className="card" style={{ overflow: 'hidden' }}>
              {/* Cover Image Placeholder */}
              <div
                className="flex items-center justify-center"
                style={{
                  height: 140,
                  background: card.gradient,
                  color: '#ffffff',
                }}
              >
                {card.icon}
              </div>
              <div className="p-5">
                {/* Title + Status */}
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-md font-semibold text-primary">{card.title}</h4>
                  {renderStatusBadge(card.status)}
                </div>
                {/* Tags */}
                <div className="flex items-center gap-2 mb-3">
                  <span className="tag">
                    {contentTypeIcons[card.contentType]}
                    {card.contentType}
                  </span>
                  <span className="tag">
                    <Globe size={12} />
                    {card.platform}
                  </span>
                </div>
                {/* Hook */}
                <p className="text-sm text-secondary mb-0 line-clamp-2" style={{ lineHeight: 'var(--leading-relaxed)' }}>
                  {card.hook}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Tab 5: 社媒看板
   ============================================================ */
function TabSocial() {
  const maxSocialVolume = Math.max(...socialVolumeData.map((d) => d.value));

  // Build SVG polyline for line chart
  const chartWidth = 600;
  const chartHeight = 160;
  const padding = 30;
  const socialPoints = socialVolumeData.map((d, i) => {
    const x = padding + (i / (socialVolumeData.length - 1)) * (chartWidth - padding * 2);
    const y = chartHeight - padding - ((d.value - 4000) / (maxSocialVolume - 4000)) * (chartHeight - padding * 2);
    return `${x},${y}`;
  }).join(' ');

  // Area fill
  const areaPoints = `${padding},${chartHeight - padding} ${socialPoints} ${chartWidth - padding},${chartHeight - padding}`;

  const tagSizeMap = {
    sm: { fontSize: 'var(--text-xs)', padding: '2px 8px' },
    md: { fontSize: 'var(--text-sm)', padding: '3px 12px' },
    lg: { fontSize: 'var(--text-md)', padding: '4px 14px' },
    xl: { fontSize: 'var(--text-lg)', padding: '5px 16px' },
  };

  const tagColorMap = {
    purple: { bg: 'var(--accent-purple-subtle)', border: 'var(--accent-purple)', color: 'var(--accent-purple)' },
    cyan: { bg: 'var(--accent-cyan-subtle)', border: 'var(--accent-cyan)', color: 'var(--accent-cyan)' },
    green: { bg: 'var(--accent-green-subtle)', border: 'var(--accent-green)', color: 'var(--accent-green)' },
    amber: { bg: 'var(--accent-amber-subtle)', border: 'var(--accent-amber)', color: 'var(--accent-amber)' },
    red: { bg: 'var(--accent-red-subtle)', border: 'var(--accent-red)', color: 'var(--accent-red)' },
    pink: { bg: 'var(--accent-pink-subtle)', border: 'var(--accent-pink)', color: 'var(--accent-pink)' },
  };

  const kolColumns = [
    { key: 'name', label: 'KOL 名称', render: (val) => <span className="font-medium text-primary">{val}</span> },
    { key: 'platform', label: '平台', render: (val) => <Badge variant="neutral">{val}</Badge> },
    { key: 'fans', label: '粉丝数', render: (val) => <span className="font-mono text-primary">{val}</span> },
    { key: 'interaction', label: '互动率', render: (val) => <span className="font-mono text-green">{val}</span> },
    { key: 'status', label: '合作状态', render: (val) => {
      const map = { '合作中': 'green', '待续约': 'amber', '已合作': 'neutral', '洽谈中': 'cyan' };
      return <Badge variant={map[val] || 'neutral'}>{val}</Badge>;
    }},
    { key: 'score', label: '评分', render: (val) => (
      <span className="flex items-center gap-1 font-mono">
        <Star size={12} style={{ color: 'var(--accent-amber)', fill: 'var(--accent-amber)' }} />
        <span className="text-primary font-semibold">{val}</span>
      </span>
    )},
  ];

  return (
    <div className="flex flex-col gap-6">
      {/* Top StatCards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          title="总声量"
          value="45.2K"
          change={12}
          changeLabel="本周"
          icon={BarChart3}
          color="blue"
        />
        <StatCard
          title="正面情绪"
          value="62%"
          change={3}
          changeLabel="vs 上周"
          icon={Heart}
          color="green"
        />
        <StatCard
          title="KOL 合作"
          value="28"
          change={5}
          changeLabel="本月"
          icon={Users}
          color="purple"
        />
        <StatCard
          title="内容主题"
          value="156"
          change={-8}
          changeLabel="vs 上月"
          icon={Hash}
          color="cyan"
        />
      </div>

      {/* Volume Line Chart */}
      <div className="chart-container">
        <div className="chart-header">
          <h3>声量走势 (近7天)</h3>
          <div className="flex items-center gap-4">
            <div className="chart-legend-item">
              <span className="chart-legend-dot" style={{ backgroundColor: 'var(--accent-blue)' }} />
              <span>总声量</span>
            </div>
          </div>
        </div>
        <div className="chart-body" style={{ padding: 'var(--space-4) var(--space-5)' }}>
          <svg width="100%" viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="xMidYMid meet">
            {/* Grid lines */}
            {[0, 1, 2, 3, 4].map((i) => {
              const y = padding + (i / 4) * (chartHeight - padding * 2);
              return (
                <line
                  key={i}
                  x1={padding}
                  y1={y}
                  x2={chartWidth - padding}
                  y2={y}
                  stroke="var(--border-subtle)"
                  strokeWidth="1"
                />
              );
            })}
            {/* Y-axis labels */}
            {[maxSocialVolume, 7000, 6000, 5000, 4000].map((val, i) => {
              const y = padding + (i / 4) * (chartHeight - padding * 2);
              return (
                <text
                  key={i}
                  x={padding - 8}
                  y={y + 4}
                  textAnchor="end"
                  fill="var(--text-muted)"
                  fontSize="10"
                  fontFamily="var(--font-mono)"
                >
                  {(val / 1000).toFixed(0)}K
                </text>
              );
            })}
            {/* Area fill */}
            <polygon
              points={areaPoints}
              fill="url(#blueGradient)"
              opacity="0.3"
            />
            {/* Line */}
            <polyline
              points={socialPoints}
              fill="none"
              stroke="var(--accent-blue)"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            {/* Data points */}
            {socialVolumeData.map((d, i) => {
              const x = padding + (i / (socialVolumeData.length - 1)) * (chartWidth - padding * 2);
              const y = chartHeight - padding - ((d.value - 4000) / (maxSocialVolume - 4000)) * (chartHeight - padding * 2);
              return (
                <g key={i}>
                  <circle cx={x} cy={y} r="4" fill="var(--accent-blue)" stroke="var(--bg-tertiary)" strokeWidth="2" />
                  <text
                    x={x}
                    y={y - 10}
                    textAnchor="middle"
                    fill="var(--text-secondary)"
                    fontSize="10"
                    fontFamily="var(--font-mono)"
                  >
                    {(d.value / 1000).toFixed(1)}K
                  </text>
                </g>
              );
            })}
            {/* X-axis labels */}
            {socialVolumeData.map((d, i) => {
              const x = padding + (i / (socialVolumeData.length - 1)) * (chartWidth - padding * 2);
              return (
                <text
                  key={i}
                  x={x}
                  y={chartHeight - 8}
                  textAnchor="middle"
                  fill="var(--text-muted)"
                  fontSize="10"
                >
                  {d.day}
                </text>
              );
            })}
            {/* Gradient definition */}
            <defs>
              <linearGradient id="blueGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--accent-blue)" stopOpacity="0.4" />
                <stop offset="100%" stopColor="var(--accent-blue)" stopOpacity="0" />
              </linearGradient>
            </defs>
          </svg>
        </div>
      </div>

      {/* KOL Table + Topic Tags */}
      <div className="grid grid-cols-2 gap-4">
        {/* KOL Table */}
        <div className="card">
          <div className="card-header">
            <h3>KOL 评价体系</h3>
          </div>
          <DataTable columns={kolColumns} data={kolData} />
        </div>

        {/* Topic Tag Cloud */}
        <div className="card">
          <div className="card-header">
            <h3>内容主题聚类</h3>
          </div>
          <div className="card-body">
            <div className="flex flex-wrap gap-2 items-center justify-center" style={{ minHeight: 200 }}>
              {topicTags.map((tag, i) => {
                const sizeStyle = tagSizeMap[tag.size];
                const colorStyle = tagColorMap[tag.color];
                return (
                  <span
                    key={i}
                    className="tag"
                    style={{
                      fontSize: sizeStyle.fontSize,
                      padding: sizeStyle.padding,
                      backgroundColor: colorStyle.bg,
                      borderColor: colorStyle.border,
                      color: colorStyle.color,
                      cursor: 'default',
                    }}
                  >
                    {tag.text}
                  </span>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Main Component
   ============================================================ */
export default function PlannerDashboard() {
  const [activeTab, setActiveTab] = useState('overview');

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview': return <TabOverview />;
      case 'insight': return <TabInsight />;
      case 'brief': return <TabBrief />;
      case 'creative': return <TabCreative />;
      case 'social': return <TabSocial />;
      default: return <TabOverview />;
    }
  };

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="策划工作台"
        subtitle="品牌策略 | 舆情监控 | 创意管理"
        breadcrumbs={[
          { label: '工作台' },
          { label: '策划工作台' },
        ]}
        actions={
          <div className="flex items-center gap-3">
            <button className="btn btn-secondary btn-sm">
              <Filter size={14} />
              筛选
            </button>
            <button className="btn btn-primary btn-sm">
              <Plus size={14} />
              新建任务
            </button>
          </div>
        }
      />
      <TabBar tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />
      <div className="page-body">
        {renderTabContent()}
      </div>
    </div>
  );
}
