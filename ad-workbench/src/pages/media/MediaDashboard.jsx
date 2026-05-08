import React, { useState } from 'react';
import {
  Users, FolderOpen, DollarSign, AlertTriangle, Search, Filter,
  ArrowRight, ChevronRight, MessageSquare, Phone, Mail,
  Eye, CheckCircle, XCircle, Clock, Play, Pause,
  BarChart3, TrendingUp, TrendingDown, Star, Globe,
  LayoutDashboard, UserPlus, ClipboardCheck, Radio, Wallet,
  AlertCircle, ArrowUpRight, RefreshCw, Download, MoreHorizontal,
  Send, Calendar, Target, Zap
} from 'lucide-react';
import StatCard from '../../components/StatCard';
import DataTable from '../../components/DataTable';
import Badge from '../../components/Badge';
import ProgressBar from '../../components/ProgressBar';
import TabBar from '../../components/TabBar';
import PageHeader from '../../components/PageHeader';
import KpiCard from '../../components/KpiCard';

/* ============================================================
   Tab Definitions
   ============================================================ */
const tabs = [
  { key: 'overview', label: '工作概览', icon: <LayoutDashboard size={14} /> },
  { key: 'kol', label: '达人建联', icon: <UserPlus size={14} /> },
  { key: 'progress', label: '项目进度', icon: <ClipboardCheck size={14} /> },
  { key: 'tracking', label: '广告追踪', icon: <Radio size={14} /> },
  { key: 'budget', label: '预算优化', icon: <Wallet size={14} /> },
];

/* ============================================================
   Status Badge Helpers
   ============================================================ */
const statusBadgeMap = {
  active: { variant: 'green', label: '进行中' },
  completed: { variant: 'cyan', label: '已完成' },
  pending: { variant: 'amber', label: '待处理' },
  paused: { variant: 'neutral', label: '已暂停' },
  urgent: { variant: 'red', label: '紧急' },
  contacting: { variant: 'blue', label: '建联中' },
  negotiating: { variant: 'amber', label: '洽谈中' },
  cooperated: { variant: 'cyan', label: '已合作' },
  rejected: { variant: 'red', label: '已拒绝' },
  running: { variant: 'green', label: '运行中' },
  error: { variant: 'red', label: '错误' },
  done: { variant: 'cyan', label: '完成' },
  normal: { variant: 'green', label: '正常' },
  warning: { variant: 'amber', label: '关注' },
  abnormal: { variant: 'red', label: '异常' },
  overspend: { variant: 'red', label: '超支预警' },
  ontrack: { variant: 'green', label: '正常投放' },
  lowperform: { variant: 'amber', label: '效果偏低' },
};

function renderStatusBadge(status) {
  const config = statusBadgeMap[status] || { variant: 'neutral', label: status };
  return <Badge variant={config.variant}>{config.label}</Badge>;
}

/* ============================================================
   Mock Data - Tab 1: 工作概览
   ============================================================ */
const activeProjects = [
  { id: 1, project: '花西子Q2品牌焕新', brand: '花西子', kols: 12, budget: '¥80,000', roi: '3.5x', status: 'active' },
  { id: 2, project: '完美日记618大促', brand: '完美日记', kols: 25, budget: '¥150,000', roi: '2.8x', status: 'active' },
  { id: 3, project: '珀莱雅新品种草', brand: '珀莱雅', kols: 8, budget: '¥45,000', roi: '4.1x', status: 'completed' },
  { id: 4, project: '薇诺娜敏感肌计划', brand: '薇诺娜', kols: 15, budget: '¥65,000', roi: '3.2x', status: 'active' },
  { id: 5, project: '橘朵Z世代营销', brand: '橘朵', kols: 20, budget: '¥55,000', roi: '2.5x', status: 'pending' },
  { id: 6, project: '自然堂夏季推广', brand: '自然堂', kols: 10, budget: '¥35,000', roi: '3.8x', status: 'paused' },
];

/* ============================================================
   Mock Data - Tab 2: 达人建联
   ============================================================ */
const kolList = [
  { id: 1, name: '程十安', avatar: null, platform: '小红书', followers: '1,234万', category: '美妆护肤', price: '¥15,000/篇', schedule: '4月下旬可约', history: 3, status: 'cooperated' },
  { id: 2, name: '老爸评测', avatar: null, platform: 'B站', followers: '890万', category: '测评科普', price: '¥25,000/期', schedule: '5月中旬', history: 1, status: 'contacting' },
  { id: 3, name: '骆王宇', avatar: null, platform: '抖音', followers: '2,100万', category: '美妆种草', price: '¥35,000/条', schedule: '已满', history: 5, status: 'cooperated' },
  { id: 4, name: '深夜发媸', avatar: null, platform: '小红书', followers: '680万', category: '时尚穿搭', price: '¥12,000/篇', schedule: '5月初可约', history: 2, status: 'negotiating' },
  { id: 5, name: '李佳琦', avatar: null, platform: '抖音', followers: '5,600万', category: '直播带货', price: '¥80,000/场', schedule: '需预约', history: 0, status: 'contacting' },
  { id: 6, name: '成分党Kiki', avatar: null, platform: 'B站', followers: '320万', category: '成分测评', price: '¥8,000/期', schedule: '4月底可约', history: 4, status: 'cooperated' },
  { id: 7, name: '大嘴博士', avatar: null, platform: '微博', followers: '450万', category: '护肤科普', price: '¥10,000/条', schedule: '5月上旬', history: 0, status: 'negotiating' },
  { id: 8, name: '董子初', avatar: null, platform: '抖音', followers: '1,800万', category: '美妆教程', price: '¥20,000/条', schedule: '已满', history: 2, status: 'rejected' },
];

const kolDetail = {
  name: '程十安',
  platform: '小红书',
  followers: '1,234万',
  interactionRate: '8.2%',
  avgPlay: '52.3万',
  avatar: null,
  history: [
    { id: 1, project: '花西子Q1种草', date: '2026-01', result: 'ROI 3.2x', status: 'completed' },
    { id: 2, project: '珀莱雅双抗推广', date: '2025-11', result: 'ROI 4.5x', status: 'completed' },
    { id: 3, project: '薇诺娜敏感肌', date: '2025-09', result: 'ROI 2.8x', status: 'completed' },
  ],
  recommendedScript: '您好！我们是XX品牌方，非常欣赏您在美妆领域的内容创作。我们近期有一个新品推广项目，与您的内容风格非常契合，希望能有机会合作详谈。期待您的回复！',
  timeline: [
    { id: 1, time: '2026-04-13 14:30', type: 'message', content: '已发送合作邀请邮件，附上Brief文档', user: '我' },
    { id: 2, time: '2026-04-13 10:15', type: 'phone', content: '电话沟通合作意向，对方表示有兴趣', user: '我' },
    { id: 3, time: '2026-04-12 16:00', type: 'reply', content: '达人回复：需要查看具体合作方案和报价', user: '达人' },
  ],
};

/* ============================================================
   Mock Data - Tab 3: 项目进度
   ============================================================ */
const projectProgressData = [
  {
    id: 1,
    name: '花西子Q2品牌焕新',
    brand: '花西子',
    stage: 'active',
    stageLabel: '发稿中',
    overallProgress: 65,
    milestones: [
      { label: '建联', status: 'done', date: '03-15' },
      { label: '签约', status: 'done', date: '03-25' },
      { label: '排期', status: 'done', date: '04-01' },
      { label: '发稿', status: 'running', date: '04-10' },
      { label: '回链', status: 'pending', date: '04-20' },
      { label: '结案', status: 'pending', date: '05-01' },
    ],
    kols: [
      { name: '程十安', platform: '小红书', status: 'active', progress: 80 },
      { name: '骆王宇', platform: '抖音', status: 'active', progress: 60 },
      { name: '成分党Kiki', platform: 'B站', status: 'pending', progress: 30 },
      { name: '深夜发媸', platform: '小红书', status: 'active', progress: 90 },
    ],
  },
  {
    id: 2,
    name: '完美日记618大促',
    brand: '完美日记',
    stage: 'active',
    stageLabel: '排期中',
    overallProgress: 40,
    milestones: [
      { label: '建联', status: 'done', date: '03-20' },
      { label: '签约', status: 'done', date: '04-01' },
      { label: '排期', status: 'running', date: '04-10' },
      { label: '发稿', status: 'pending', date: '05-15' },
      { label: '回链', status: 'pending', date: '06-10' },
      { label: '结案', status: 'pending', date: '06-25' },
    ],
    kols: [
      { name: '李佳琦', platform: '抖音', status: 'negotiating', progress: 20 },
      { name: '董子初', platform: '抖音', status: 'active', progress: 50 },
      { name: '大嘴博士', platform: '微博', status: 'pending', progress: 10 },
    ],
  },
  {
    id: 3,
    name: '珀莱雅新品种草',
    brand: '珀莱雅',
    stage: 'completed',
    stageLabel: '已结案',
    overallProgress: 100,
    milestones: [
      { label: '建联', status: 'done', date: '01-10' },
      { label: '签约', status: 'done', date: '01-20' },
      { label: '排期', status: 'done', date: '02-01' },
      { label: '发稿', status: 'done', date: '02-15' },
      { label: '回链', status: 'done', date: '03-01' },
      { label: '结案', status: 'done', date: '03-15' },
    ],
    kols: [
      { name: '程十安', platform: '小红书', status: 'completed', progress: 100 },
      { name: '成分党Kiki', platform: 'B站', status: 'completed', progress: 100 },
      { name: '骆王宇', platform: '抖音', status: 'completed', progress: 100 },
    ],
  },
];

/* ============================================================
   Mock Data - Tab 4: 广告追踪
   ============================================================ */
const trackingNodes = [
  { id: 1, label: '搜索节点', status: 'running', dataCount: '12,345 条', icon: <Search size={20} /> },
  { id: 2, label: '抓取节点', status: 'running', dataCount: '8,920 条', icon: <Download size={20} /> },
  { id: 3, label: '清洗节点', status: 'done', dataCount: '7,650 条', icon: <RefreshCw size={20} /> },
  { id: 4, label: '分析节点', status: 'error', dataCount: '5,230 条', icon: <BarChart3 size={20} /> },
];

const platformCompareData = [
  { id: 1, platform: 'B站', ads: 45, completion: '72%', interaction: '5.8%', sentiment: 'normal', anomaly: 'normal' },
  { id: 2, platform: '小红书', ads: 68, completion: '65%', interaction: '4.5%', sentiment: 'normal', anomaly: 'warning' },
  { id: 3, platform: '微博', ads: 32, completion: '58%', interaction: '3.2%', sentiment: 'warning', anomaly: 'normal' },
  { id: 4, platform: '抖音', ads: 56, completion: '75%', interaction: '4.8%', sentiment: 'normal', anomaly: 'normal' },
  { id: 5, platform: '快手', ads: 33, completion: '62%', interaction: '3.5%', sentiment: 'normal', anomaly: 'abnormal' },
];

const anomalyList = [
  { id: 1, type: '水军检测', icon: <Users size={16} />, severity: 'warning', content: '发现 3 条疑似水军评论，涉及抖音平台素材A', time: '10 分钟前' },
  { id: 2, type: '负面异常', icon: <AlertTriangle size={16} />, severity: 'urgent', content: '2 条负面评论需关注，小红书平台品牌口碑下降', time: '30 分钟前' },
  { id: 3, type: '数据异常', icon: <TrendingDown size={16} />, severity: 'warning', content: '1 个广告完播率异常偏低（12%），低于阈值 30%', time: '1 小时前' },
];

/* ============================================================
   Mock Data - Tab 5: 预算优化
   ============================================================ */
const budgetAllocationData = [
  { id: 1, item: '花西子Q2焕新', platform: '小红书', budget: '¥50,000', spent: '¥38,000', cpa: '¥22', cpe: '¥5.2', cpm: '¥35', status: 'ontrack' },
  { id: 2, item: '花西子Q2焕新', platform: '抖音', budget: '¥30,000', spent: '¥28,500', cpa: '¥35', cpe: '¥8.0', cpm: '¥48', status: 'overspend' },
  { id: 3, item: '完美日记618', platform: '抖音', budget: '¥80,000', spent: '¥52,000', cpa: '¥18', cpe: '¥4.5', cpm: '¥30', status: 'ontrack' },
  { id: 4, item: '完美日记618', platform: '小红书', budget: '¥45,000', spent: '¥32,000', cpa: '¥25', cpe: '¥6.8', cpm: '¥42', status: 'lowperform' },
  { id: 5, item: '完美日记618', platform: '微博', budget: '¥25,000', spent: '¥18,000', cpa: '¥28', cpe: '¥7.5', cpm: '¥45', status: 'lowperform' },
  { id: 6, item: '珀莱雅新品', platform: 'B站', budget: '¥25,000', spent: '¥25,000', cpa: '¥20', cpe: '¥4.8', cpm: '¥32', status: 'ontrack' },
  { id: 7, item: '薇诺娜敏感肌', platform: '小红书', budget: '¥40,000', spent: '¥24,500', cpa: '¥21', cpe: '¥5.0', cpm: '¥38', status: 'ontrack' },
  { id: 8, item: '橘朵Z世代', platform: '抖音', budget: '¥30,000', spent: '¥12,000', cpa: '¥19', cpe: '¥4.2', cpm: '¥28', status: 'ontrack' },
];

const warningList = [
  { id: 1, item: '素材A / 抖音', metric: 'CPA', current: '¥35', threshold: '¥25', suggestion: '建议替换素材' },
  { id: 2, item: '素材B / 小红书', metric: 'CPE', current: '¥8', threshold: '¥6', suggestion: '建议调低预算' },
  { id: 3, item: '达人C / 微博', metric: 'CPM', current: '¥50', threshold: '¥40', suggestion: '建议暂停投放' },
];

const optimizationSuggestions = [
  { id: 1, priority: 'high', title: '转移抖音素材A预算至素材D', description: '素材D的CPA为¥15，比素材A低57%，建议将超支部分转移至素材D。', expected: '预计节省 ¥12,000' },
  { id: 2, priority: 'medium', title: '增加B站平台投放占比', description: 'B站完播率和互动率均表现优异，建议将微博部分预算转移至B站。', expected: '预计提升ROI 0.3x' },
  { id: 3, priority: 'low', title: '优化小红书达人组合', description: '当前小红书投放中尾部达人占比过高，建议增加腰部达人比例。', expected: '预计降低CPE 15%' },
];

/* ============================================================
   Tab 1: 工作概览
   ============================================================ */
function TabOverview() {
  const projectColumns = [
    { key: 'project', label: '项目名称', render: (val) => <span className="font-medium text-primary">{val}</span> },
    { key: 'brand', label: '品牌' },
    { key: 'kols', label: '合作达人', render: (val) => <span className="font-mono">{val} 人</span> },
    { key: 'budget', label: '预算', render: (val) => <span className="font-mono">{val}</span> },
    { key: 'roi', label: 'ROI', render: (val) => <span className="font-mono font-semibold" style={{ color: 'var(--accent-green)' }}>{val}</span> },
    { key: 'status', label: '状态', render: (val) => renderStatusBadge(val) },
  ];

  return (
    <div className="flex flex-col gap-6">
      {/* Top StatCards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          title="合作达人"
          value="156"
          change={12}
          changeLabel="本月"
          icon={Users}
          color="pink"
        />
        <StatCard
          title="进行中项目"
          value="8"
          subtitle="占总项目 40%"
          icon={FolderOpen}
          color="blue"
        />
        <StatCard
          title="平均 CPA"
          value="¥23.5"
          change={-8}
          changeLabel="vs 上月"
          icon={DollarSign}
          color="green"
        />
        <StatCard
          title="异常预警"
          value="3"
          subtitle="需处理"
          icon={AlertTriangle}
          color="red"
        />
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-4">
        <KpiCard
          title="投放 ROI"
          value="3.2x"
          target={3.5}
          current={3.2}
          color="green"
          trend={[
            { value: 2.5 }, { value: 2.8 }, { value: 2.6 }, { value: 3.0 }, { value: 3.1 }, { value: 3.2 },
          ]}
        />
        <KpiCard
          title="达人合作满意度"
          value="4.6/5.0"
          target={4.5}
          current={4.6}
          color="blue"
          trend={[
            { value: 4.2 }, { value: 4.3 }, { value: 4.4 }, { value: 4.5 }, { value: 4.5 }, { value: 4.6 },
          ]}
        />
      </div>

      {/* Active Projects Table */}
      <div>
        <div className="section-title">活跃项目列表</div>
        <DataTable columns={projectColumns} data={activeProjects} />
      </div>
    </div>
  );
}

/* ============================================================
   Tab 2: 达人建联
   ============================================================ */
function TabKol() {
  const [selectedKol, setSelectedKol] = useState(kolList[0]);
  const [searchText, setSearchText] = useState('');
  const [filterPlatform, setFilterPlatform] = useState('all');
  const [filterFollowers, setFilterFollowers] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterCategory, setFilterCategory] = useState('all');

  const kolColumns = [
    {
      key: 'name',
      label: '达人',
      render: (val, row) => (
        <div className="flex items-center gap-3">
          <div
            className="flex-shrink-0 flex items-center justify-center rounded-full"
            style={{
              width: 36,
              height: 36,
              backgroundColor: 'var(--accent-pink-subtle)',
              color: 'var(--accent-pink)',
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
            }}
          >
            {val.charAt(0)}
          </div>
          <div className="flex flex-col">
            <span className="font-medium text-primary text-sm">{val}</span>
            <Badge variant="neutral">{row.platform}</Badge>
          </div>
        </div>
      ),
    },
    { key: 'followers', label: '粉丝数', render: (val) => <span className="font-mono text-sm">{val}</span> },
    { key: 'category', label: '类目' },
    { key: 'price', label: '报价', render: (val) => <span className="font-mono text-sm">{val}</span> },
    { key: 'schedule', label: '档期', render: (val) => (
      <span className={`text-sm ${val === '已满' ? 'text-red' : 'text-secondary'}`}>{val}</span>
    )},
    { key: 'history', label: '历史合作', render: (val) => <span className="font-mono text-sm">{val} 次</span> },
    { key: 'status', label: '状态', render: (val) => renderStatusBadge(val) },
    {
      key: 'action',
      label: '操作',
      render: (_, row) => (
        <button
          className="btn btn-sm btn-secondary"
          onClick={(e) => {
            e.stopPropagation();
            setSelectedKol(row);
          }}
        >
          查看
        </button>
      ),
    },
  ];

  const timelineIconMap = {
    message: <Mail size={14} />,
    phone: <Phone size={14} />,
    reply: <MessageSquare size={14} />,
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Search + Filters */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-4">
          <div className="search-box" style={{ flex: 1, maxWidth: 360 }}>
            <span className="search-icon"><Search size={14} /></span>
            <input
              className="search-input"
              placeholder="搜索达人名称..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
            />
          </div>
          <button className="btn btn-secondary btn-sm">
            <Filter size={14} />
            筛选
          </button>
        </div>
        <div className="flex items-center gap-3">
          <select
            className="select-input"
            value={filterPlatform}
            onChange={(e) => setFilterPlatform(e.target.value)}
          >
            <option value="all">全部平台</option>
            <option value="小红书">小红书</option>
            <option value="抖音">抖音</option>
            <option value="B站">B站</option>
            <option value="微博">微博</option>
          </select>
          <select
            className="select-input"
            value={filterFollowers}
            onChange={(e) => setFilterFollowers(e.target.value)}
          >
            <option value="all">全部粉丝量级</option>
            <option value="100w+">100万+</option>
            <option value="500w+">500万+</option>
            <option value="1000w+">1000万+</option>
          </select>
          <select
            className="select-input"
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
          >
            <option value="all">全部状态</option>
            <option value="contacting">建联中</option>
            <option value="negotiating">洽谈中</option>
            <option value="cooperated">已合作</option>
            <option value="rejected">已拒绝</option>
          </select>
          <select
            className="select-input"
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
          >
            <option value="all">全部类目</option>
            <option value="美妆护肤">美妆护肤</option>
            <option value="测评科普">测评科普</option>
            <option value="时尚穿搭">时尚穿搭</option>
            <option value="直播带货">直播带货</option>
          </select>
        </div>
      </div>

      {/* Main Content: List + Detail */}
      <div className="grid gap-4" style={{ gridTemplateColumns: '65% 35%' }}>
        {/* KOL List */}
        <DataTable
          columns={kolColumns}
          data={kolList}
          onRowClick={(row) => setSelectedKol(row)}
        />

        {/* KOL Detail Panel */}
        <div className="card">
          <div className="card-header">
            <h3>达人详情</h3>
          </div>
          <div className="card-body">
            {/* Avatar + Name + Platform */}
            <div className="flex items-center gap-4 mb-5">
              <div
                className="flex-shrink-0 flex items-center justify-center rounded-full"
                style={{
                  width: 56,
                  height: 56,
                  backgroundColor: 'var(--accent-pink-subtle)',
                  color: 'var(--accent-pink)',
                  fontSize: 'var(--text-xl)',
                  fontWeight: 700,
                }}
              >
                {selectedKol.name.charAt(0)}
              </div>
              <div className="flex flex-col">
                <span className="text-lg font-semibold text-primary">{selectedKol.name}</span>
                <Badge variant="neutral">{selectedKol.platform}</Badge>
              </div>
            </div>

            {/* Stats Row */}
            <div className="grid grid-cols-3 gap-3 mb-5">
              <div className="flex flex-col items-center p-3 rounded-lg" style={{ backgroundColor: 'var(--bg-elevated)' }}>
                <span className="text-xs text-muted mb-1">粉丝数</span>
                <span className="font-mono font-semibold text-primary text-sm">{kolDetail.followers}</span>
              </div>
              <div className="flex flex-col items-center p-3 rounded-lg" style={{ backgroundColor: 'var(--bg-elevated)' }}>
                <span className="text-xs text-muted mb-1">互动率</span>
                <span className="font-mono font-semibold text-primary text-sm">{kolDetail.interactionRate}</span>
              </div>
              <div className="flex flex-col items-center p-3 rounded-lg" style={{ backgroundColor: 'var(--bg-elevated)' }}>
                <span className="text-xs text-muted mb-1">平均播放</span>
                <span className="font-mono font-semibold text-primary text-sm">{kolDetail.avgPlay}</span>
              </div>
            </div>

            {/* History Cooperation */}
            <div className="mb-5">
              <div className="text-xs text-muted mb-2 font-medium uppercase tracking-wide">历史合作记录</div>
              <div className="flex flex-col gap-2">
                {kolDetail.history.map((h) => (
                  <div
                    key={h.id}
                    className="flex items-center justify-between p-2 rounded"
                    style={{ backgroundColor: 'var(--bg-elevated)' }}
                  >
                    <div className="flex flex-col">
                      <span className="text-sm text-primary">{h.project}</span>
                      <span className="text-xs text-muted">{h.date}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono" style={{ color: 'var(--accent-green)' }}>{h.result}</span>
                      {renderStatusBadge(h.status)}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Recommended Script */}
            <div className="mb-5">
              <div className="text-xs text-muted mb-2 font-medium uppercase tracking-wide">推荐话术</div>
              <div
                className="p-3 rounded text-sm text-secondary"
                style={{
                  backgroundColor: 'var(--bg-elevated)',
                  lineHeight: 'var(--leading-relaxed)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                {kolDetail.recommendedScript}
              </div>
            </div>

            {/* Communication Timeline */}
            <div>
              <div className="text-xs text-muted mb-3 font-medium uppercase tracking-wide">沟通记录</div>
              <div className="flex flex-col gap-0">
                {kolDetail.timeline.map((item, index) => (
                  <div key={item.id} className="timeline-item flex gap-3">
                    <div className="flex flex-col items-center">
                      <div
                        className="flex-shrink-0 flex items-center justify-center rounded-full"
                        style={{
                          width: 28,
                          height: 28,
                          backgroundColor: item.user === '我' ? 'var(--accent-blue-subtle)' : 'var(--accent-amber-subtle)',
                          color: item.user === '我' ? 'var(--accent-blue)' : 'var(--accent-amber)',
                        }}
                      >
                        {timelineIconMap[item.type]}
                      </div>
                      {index < kolDetail.timeline.length - 1 && (
                        <div
                          style={{
                            width: 1,
                            flex: 1,
                            minHeight: 24,
                            backgroundColor: 'var(--border-subtle)',
                          }}
                        />
                      )}
                    </div>
                    <div className="flex flex-col pb-4">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-medium text-primary">{item.user}</span>
                        <span className="text-xs text-muted">{item.time}</span>
                      </div>
                      <span className="text-sm text-secondary">{item.content}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Tab 3: 项目进度
   ============================================================ */
function TabProgress() {
  const [selectedProject, setSelectedProject] = useState('all');
  const [viewMode, setViewMode] = useState('project');

  const milestoneStatusIcon = {
    done: <CheckCircle size={16} style={{ color: 'var(--accent-green)' }} />,
    running: <Play size={16} style={{ color: 'var(--accent-blue)' }} />,
    pending: <Clock size={16} style={{ color: 'var(--text-muted)' }} />,
    error: <XCircle size={16} style={{ color: 'var(--accent-red)' }} />,
  };

  const milestoneStatusColor = {
    done: 'var(--accent-green)',
    running: 'var(--accent-blue)',
    pending: 'var(--text-muted)',
    error: 'var(--accent-red)',
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Top Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <select
            className="select-input"
            value={selectedProject}
            onChange={(e) => setSelectedProject(e.target.value)}
          >
            <option value="all">全部项目</option>
            <option value="1">花西子Q2品牌焕新</option>
            <option value="2">完美日记618大促</option>
            <option value="3">珀莱雅新品种草</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <button
            className={`btn btn-sm ${viewMode === 'project' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setViewMode('project')}
          >
            按项目
          </button>
          <button
            className={`btn btn-sm ${viewMode === 'kol' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setViewMode('kol')}
          >
            按达人
          </button>
        </div>
      </div>

      {/* Project Cards */}
      <div className="flex flex-col gap-4">
        {projectProgressData
          .filter((p) => selectedProject === 'all' || String(p.id) === selectedProject)
          .map((project) => (
            <div key={project.id} className="card">
              <div className="card-header">
                <div className="flex items-center gap-3">
                  <span className="text-md font-semibold text-primary">{project.name}</span>
                  <span className="text-sm text-muted">{project.brand}</span>
                  <Badge variant={project.stage === 'completed' ? 'cyan' : 'green'}>{project.stageLabel}</Badge>
                </div>
              </div>
              <div className="card-body">
                {/* Overall Progress */}
                <div className="mb-5">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-secondary">整体完成度</span>
                    <span className="text-sm font-mono font-semibold text-primary">{project.overallProgress}%</span>
                  </div>
                  <ProgressBar
                    value={project.overallProgress}
                    color={project.overallProgress >= 80 ? 'green' : project.overallProgress >= 50 ? 'blue' : 'amber'}
                    size="md"
                  />
                </div>

                {/* Milestone Timeline */}
                <div className="mb-5">
                  <div className="text-xs text-muted mb-3 font-medium uppercase tracking-wide">里程碑节点</div>
                  <div className="flex items-center gap-0">
                    {project.milestones.map((ms, index) => (
                      <React.Fragment key={ms.label}>
                        <div className="flex flex-col items-center" style={{ minWidth: 72 }}>
                          <div className="mb-2">{milestoneStatusIcon[ms.status]}</div>
                          <span
                            className="text-xs font-medium mb-1"
                            style={{ color: milestoneStatusColor[ms.status] }}
                          >
                            {ms.label}
                          </span>
                          <span className="text-xs text-muted">{ms.date}</span>
                        </div>
                        {index < project.milestones.length - 1 && (
                          <div
                            className="flex-1 mb-5"
                            style={{
                              height: 2,
                              backgroundColor: ms.status === 'done' && project.milestones[index + 1].status !== 'pending'
                                ? 'var(--accent-green)'
                                : 'var(--border-subtle)',
                              marginTop: -20,
                            }}
                          />
                        )}
                      </React.Fragment>
                    ))}
                  </div>
                </div>

                {/* KOL Assignment Table */}
                <div>
                  <div className="text-xs text-muted mb-3 font-medium uppercase tracking-wide">达人分配</div>
                  <div className="data-table">
                    <table className="data-table-inner">
                      <thead>
                        <tr>
                          <th>达人</th>
                          <th>平台</th>
                          <th>状态</th>
                          <th style={{ width: 200 }}>进度</th>
                        </tr>
                      </thead>
                      <tbody>
                        {project.kols.map((kol, idx) => (
                          <tr key={idx}>
                            <td>
                              <span className="font-medium text-primary text-sm">{kol.name}</span>
                            </td>
                            <td>
                              <Badge variant="neutral">{kol.platform}</Badge>
                            </td>
                            <td>{renderStatusBadge(kol.status)}</td>
                            <td>
                              <div className="flex items-center gap-2">
                                <ProgressBar
                                  value={kol.progress}
                                  color={kol.progress >= 80 ? 'green' : kol.progress >= 50 ? 'blue' : 'amber'}
                                  size="sm"
                                />
                                <span className="text-xs font-mono text-muted" style={{ minWidth: 32 }}>{kol.progress}%</span>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
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
   Tab 4: 广告追踪
   ============================================================ */
function TabTracking() {
  const nodeStatusColor = {
    running: { bg: 'var(--accent-green-subtle)', border: 'var(--accent-green)', text: 'var(--accent-green)' },
    done: { bg: 'var(--accent-cyan-subtle)', border: 'var(--accent-cyan)', text: 'var(--accent-cyan)' },
    error: { bg: 'var(--accent-red-subtle)', border: 'var(--accent-red)', text: 'var(--accent-red)' },
  };

  const nodeStatusLabel = {
    running: '运行中',
    done: '完成',
    error: '错误',
  };

  const platformColumns = [
    { key: 'platform', label: '平台', render: (val) => <span className="font-medium text-primary">{val}</span> },
    { key: 'ads', label: '广告数', render: (val) => <span className="font-mono">{val}</span> },
    { key: 'completion', label: '完播率', render: (val) => <span className="font-mono">{val}</span> },
    { key: 'interaction', label: '互动率', render: (val) => <span className="font-mono">{val}</span> },
    { key: 'sentiment', label: '评论情绪', render: (val) => renderStatusBadge(val) },
    { key: 'anomaly', label: '异常', render: (val) => renderStatusBadge(val) },
  ];

  const anomalySeverityColor = {
    warning: 'var(--accent-amber)',
    urgent: 'var(--accent-red)',
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Top StatCards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          title="监测广告"
          value="234"
          change={15}
          changeLabel="本周新增"
          icon={Eye}
          color="blue"
        />
        <StatCard
          title="平均完播率"
          value="68%"
          change={5}
          changeLabel="vs 上周"
          icon={Play}
          color="green"
        />
        <StatCard
          title="平均互动率"
          value="4.2%"
          change={-2}
          changeLabel="vs 上周"
          icon={TrendingUp}
          color="purple"
        />
        <StatCard
          title="负面评论"
          value="12"
          change={3}
          changeLabel="需关注"
          icon={AlertTriangle}
          color="red"
        />
      </div>

      {/* Tracking Pipeline */}
      <div>
        <div className="section-title">追踪节点流程</div>
        <div className="flex items-center gap-3">
          {trackingNodes.map((node, index) => (
            <React.Fragment key={node.id}>
              <div className="card flex-1" style={{ padding: 'var(--space-4)' }}>
                <div className="flex items-center justify-between mb-3">
                  <div
                    className="flex items-center justify-center rounded-lg"
                    style={{
                      width: 40,
                      height: 40,
                      backgroundColor: nodeStatusColor[node.status].bg,
                      color: nodeStatusColor[node.status].text,
                    }}
                  >
                    {node.icon}
                  </div>
                  <Badge
                    variant={node.status === 'running' ? 'green' : node.status === 'done' ? 'cyan' : 'red'}
                  >
                    {nodeStatusLabel[node.status]}
                  </Badge>
                </div>
                <div className="text-sm font-medium text-primary mb-1">{node.label}</div>
                <div className="text-xs font-mono text-muted">{node.dataCount}</div>
              </div>
              {index < trackingNodes.length - 1 && (
                <ArrowRight size={20} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Bottom: Platform Compare + Anomaly Detection */}
      <div className="grid gap-4" style={{ gridTemplateColumns: '60% 40%' }}>
        {/* Platform Comparison Table */}
        <div className="card">
          <div className="card-header">
            <h3>平台效果对比</h3>
          </div>
          <DataTable columns={platformColumns} data={platformCompareData} />
        </div>

        {/* Anomaly Detection */}
        <div className="card">
          <div className="card-header">
            <h3>异常检测</h3>
          </div>
          <div className="card-body">
            <div className="flex flex-col gap-4">
              {anomalyList.map((item) => (
                <div
                  key={item.id}
                  className="flex items-start gap-3 p-3 rounded-lg"
                  style={{
                    backgroundColor: item.severity === 'urgent' ? 'var(--accent-red-subtle)' : 'var(--accent-amber-subtle)',
                    border: `1px solid ${anomalySeverityColor[item.severity]}`,
                  }}
                >
                  <div
                    className="flex-shrink-0 mt-0.5"
                    style={{ color: anomalySeverityColor[item.severity] }}
                  >
                    {item.icon}
                  </div>
                  <div className="flex flex-col flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-primary">{item.type}</span>
                      <Badge variant={item.severity === 'urgent' ? 'red' : 'amber'}>
                        {item.severity === 'urgent' ? '紧急' : '关注'}
                      </Badge>
                    </div>
                    <span className="text-sm text-secondary">{item.content}</span>
                    <span className="text-xs text-muted mt-1">{item.time}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Tab 5: 预算优化
   ============================================================ */
function TabBudget() {
  const budgetColumns = [
    { key: 'item', label: '投放项目', render: (val) => <span className="font-medium text-primary text-sm">{val}</span> },
    { key: 'platform', label: '平台', render: (val) => <Badge variant="neutral">{val}</Badge> },
    { key: 'budget', label: '预算', render: (val) => <span className="font-mono text-sm">{val}</span> },
    { key: 'spent', label: '已消耗', render: (val) => <span className="font-mono text-sm">{val}</span> },
    { key: 'cpa', label: 'CPA', render: (val) => <span className="font-mono text-sm">{val}</span> },
    { key: 'cpe', label: 'CPE', render: (val) => <span className="font-mono text-sm">{val}</span> },
    { key: 'cpm', label: 'CPM', render: (val) => <span className="font-mono text-sm">{val}</span> },
    { key: 'status', label: '状态', render: (val) => renderStatusBadge(val) },
  ];

  const priorityConfig = {
    high: { variant: 'red', label: '高优先' },
    medium: { variant: 'amber', label: '中优先' },
    low: { variant: 'neutral', label: '低优先' },
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Budget Overview */}
      <div className="card">
        <div className="card-header">
          <h3>总预算概览</h3>
        </div>
        <div className="card-body">
          <div className="grid grid-cols-3 gap-6 mb-5">
            <div className="flex flex-col">
              <span className="text-xs text-muted mb-1">总预算</span>
              <span className="text-xl font-mono font-semibold text-primary">¥500,000</span>
            </div>
            <div className="flex flex-col">
              <span className="text-xs text-muted mb-1">已消耗</span>
              <span className="text-xl font-mono font-semibold" style={{ color: 'var(--accent-amber)' }}>¥325,000</span>
              <span className="text-xs text-muted">65%</span>
            </div>
            <div className="flex flex-col">
              <span className="text-xs text-muted mb-1">剩余</span>
              <span className="text-xl font-mono font-semibold" style={{ color: 'var(--accent-green)' }}>¥175,000</span>
              <span className="text-xs text-muted">35%</span>
            </div>
          </div>
          <ProgressBar value={65} color="amber" size="lg" showLabel />
        </div>
      </div>

      {/* Budget Allocation Table */}
      <div>
        <div className="section-title">预算分配明细</div>
        <DataTable columns={budgetColumns} data={budgetAllocationData} />
      </div>

      {/* Bottom: Warnings + Optimization Suggestions */}
      <div className="grid grid-cols-2 gap-4">
        {/* Warning List */}
        <div className="card">
          <div className="card-header">
            <h3>预警列表</h3>
          </div>
          <div className="card-body">
            <div className="flex flex-col gap-3">
              {warningList.map((item) => (
                <div
                  key={item.id}
                  className="flex items-start gap-3 p-3 rounded-lg"
                  style={{
                    backgroundColor: 'var(--accent-red-subtle)',
                    border: '1px solid var(--accent-red)',
                  }}
                >
                  <AlertTriangle size={16} style={{ color: 'var(--accent-red)', flexShrink: 0, marginTop: 2 }} />
                  <div className="flex flex-col flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-primary">{item.item}</span>
                    </div>
                    <span className="text-sm text-secondary">
                      {item.metric} <span className="font-mono font-semibold" style={{ color: 'var(--accent-red)' }}>{item.current}</span> 超阈值{' '}
                      <span className="font-mono">{item.threshold}</span>
                    </span>
                    <span className="text-xs mt-1" style={{ color: 'var(--accent-green)' }}>
                      <Zap size={10} style={{ display: 'inline', verticalAlign: 'middle' }} /> {item.suggestion}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Optimization Suggestions */}
        <div className="card">
          <div className="card-header">
            <h3>优化建议</h3>
          </div>
          <div className="card-body">
            <div className="flex flex-col gap-4">
              {optimizationSuggestions.map((item) => (
                <div
                  key={item.id}
                  className="p-4 rounded-lg"
                  style={{ backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Badge variant={priorityConfig[item.priority].variant}>
                        {priorityConfig[item.priority].label}
                      </Badge>
                      <span className="text-sm font-medium text-primary">{item.title}</span>
                    </div>
                  </div>
                  <p className="text-sm text-secondary mb-3" style={{ lineHeight: 'var(--leading-relaxed)' }}>
                    {item.description}
                  </p>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono" style={{ color: 'var(--accent-green)' }}>
                      {item.expected}
                    </span>
                    <button className="btn btn-sm btn-primary">
                      执行优化
                    </button>
                  </div>
                </div>
              ))}
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
export default function MediaDashboard() {
  const [activeTab, setActiveTab] = useState('overview');

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview': return <TabOverview />;
      case 'kol': return <TabKol />;
      case 'progress': return <TabProgress />;
      case 'tracking': return <TabTracking />;
      case 'budget': return <TabBudget />;
      default: return <TabOverview />;
    }
  };

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="媒介工作台"
        subtitle="达人管理 | 项目进度 | 广告追踪 | 预算优化"
        breadcrumbs={[
          { label: '工作台' },
          { label: '媒介工作台' },
        ]}
        actions={
          <div className="flex items-center gap-3">
            <button className="btn btn-secondary btn-sm">
              <Download size={14} />
              导出报表
            </button>
            <button className="btn btn-primary btn-sm">
              <UserPlus size={14} />
              新建合作
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
