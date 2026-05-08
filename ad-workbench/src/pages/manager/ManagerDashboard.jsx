import React, { useState } from 'react';
import {
  FolderOpen, DollarSign, TrendingUp, Star, AlertTriangle, AlertCircle,
  Info, Shield, Target, BarChart3, Activity, ArrowUpRight, ArrowDownRight,
  Minus, Eye, LayoutDashboard, PieChart, ClipboardList, Lightbulb,
  Megaphone, Users, ChevronRight
} from 'lucide-react';
import StatCard from '../../components/StatCard';
import DataTable from '../../components/DataTable';
import Badge from '../../components/Badge';
import ProgressBar from '../../components/ProgressBar';
import TabBar from '../../components/TabBar';
import PageHeader from '../../components/PageHeader';
import KpiCard from '../../components/KpiCard';

/* ============================================================
   Mock Data
   ============================================================ */

const tabs = [
  { key: 'overview', label: '经营总览', icon: <LayoutDashboard size={14} /> },
  { key: 'kpi', label: 'KPI 监控', icon: <BarChart3 size={14} /> },
  { key: 'risk', label: '风险分布', icon: <Shield size={14} /> },
  { key: 'health', label: '项目健康度', icon: <Activity size={14} /> },
];

// Tab 1 - 经营总览：项目概览表格数据
const projectTableData = [
  { id: 1, project: 'Q2 品牌焕新传播', brand: '花西子', phase: '执行中', budget: '¥500K', spent: '¥310K', roi: '3.5x', health: 92 },
  { id: 2, project: '618 大促社媒投放', brand: '完美日记', phase: '策划中', budget: '¥800K', spent: '¥120K', roi: '-', health: 85 },
  { id: 3, project: '新品上市种草计划', brand: '珀莱雅', phase: '执行中', budget: '¥300K', spent: '¥245K', roi: '2.8x', health: 68 },
  { id: 4, project: '品牌危机公关', brand: '薇诺娜', phase: '监控中', budget: '¥200K', spent: '¥180K', roi: '1.2x', health: 45 },
  { id: 5, project: 'Z世代消费者洞察', brand: '橘朵', phase: '已完成', budget: '¥150K', spent: '¥148K', roi: '4.1x', health: 95 },
  { id: 6, project: '双11 预热投放', brand: '花西子', phase: '策划中', budget: '¥1.2M', spent: '¥80K', roi: '-', health: 78 },
  { id: 7, project: '跨境品牌推广', brand: '珀莱雅', phase: '执行中', budget: '¥600K', spent: '¥420K', roi: '2.1x', health: 55 },
  { id: 8, project: '私域流量运营', brand: '完美日记', phase: '执行中', budget: '¥250K', spent: '¥190K', roi: '3.8x', health: 88 },
];

// Tab 2 - KPI 监控：按岗位 KPI 数据
const roleKpiData = [
  {
    role: '策划',
    icon: Lightbulb,
    color: 'purple',
    trend: '策略产出效率持续提升，本月达成率超目标 2 个百分点',
    kpis: [
      { name: '策略产出率', value: 92, target: 90, unit: '%' },
      { name: 'Brief 完成数', value: 18, target: 20, unit: '份' },
      { name: '创意通过率', value: 78, target: 85, unit: '%' },
      { name: '洞察报告数', value: 12, target: 10, unit: '份' },
    ],
  },
  {
    role: '执行',
    icon: ClipboardList,
    color: 'cyan',
    trend: '执行效率稳步提升，但创意通过率仍需关注',
    kpis: [
      { name: '执行效率', value: 78, target: 85, unit: '%' },
      { name: '任务完成率', value: 88, target: 90, unit: '%' },
      { name: '交付准时率', value: 82, target: 85, unit: '%' },
      { name: '质量评分', value: 4.2, target: 4.5, unit: '/5.0' },
    ],
  },
  {
    role: '媒介',
    icon: Megaphone,
    color: 'green',
    trend: '投放 ROI 表现优异，超出目标值',
    kpis: [
      { name: '投放 ROI', value: 3.2, target: 3.5, unit: 'x' },
      { name: 'CPA 控制率', value: 85, target: 80, unit: '%' },
      { name: '曝光完成率', value: 110, target: 100, unit: '%' },
      { name: '点击率', value: 3.8, target: 3.5, unit: '%' },
    ],
  },
];

// Tab 2 - KPI 趋势图数据（最近 30 天）
function generateTrendData() {
  const data = [];
  for (let i = 0; i < 30; i++) {
    data.push({
      day: `${i + 1}`,
      planner: 75 + Math.random() * 20,
      executor: 65 + Math.random() * 25,
      media: 70 + Math.random() * 22,
    });
  }
  return data;
}

const kpiTrendData = generateTrendData();

// Tab 3 - 风险详情数据
const riskTableData = [
  { id: 1, risk: '预算超支风险：珀莱雅新品种草计划消耗已达 82%', project: '新品上市种草计划', level: 'high', owner: '张明', impact: '预算超支 15%', status: 'tracking' },
  { id: 2, risk: '舆情危机：薇诺娜品牌负面评论增长 200%', project: '品牌危机公关', level: 'high', owner: '李华', impact: '品牌声誉受损', status: 'handling' },
  { id: 3, risk: 'KOL 合作风险：头部达人档期冲突', project: '618 大促社媒投放', level: 'medium', owner: '王芳', impact: '曝光量下降 30%', status: 'tracking' },
  { id: 4, risk: '投放素材合规风险：部分创意未过审', project: '跨境品牌推广', level: 'medium', owner: '赵磊', impact: '投放延迟', status: 'resolved' },
  { id: 5, risk: '竞品动态：竞对加大投放力度', project: 'Q2 品牌焕新传播', level: 'medium', owner: '陈静', impact: '市场份额下降', status: 'tracking' },
  { id: 6, risk: '团队资源不足：618 期间人力缺口 3 人', project: '618 大促社媒投放', level: 'medium', owner: '刘洋', impact: '交付延迟', status: 'tracking' },
  { id: 7, risk: '数据安全：第三方数据接口不稳定', project: 'Z世代消费者洞察', level: 'medium', owner: '周强', impact: '数据采集中断', status: 'resolved' },
  { id: 8, risk: '平台政策变更：小红书算法调整', project: '私域流量运营', level: 'low', owner: '吴敏', impact: '流量下降 10%', status: 'monitoring' },
  { id: 9, risk: '供应商延迟：物料制作周期延长', project: '双11 预热投放', level: 'low', owner: '孙伟', impact: '上线延迟 3 天', status: 'monitoring' },
  { id: 10, risk: '客户需求变更：花西子增加直播场次', project: 'Q2 品牌焕新传播', level: 'low', owner: '郑丽', impact: '预算增加 8%', status: 'monitoring' },
];

// Tab 4 - 项目健康度数据
const projectHealthData = [
  {
    id: 1, project: 'Q2 品牌焕新传播', brand: '花西子', score: 92, trend: 'up',
    dimensions: { strategy: 95, execution: 88, media: 94, client: 91 },
    risks: ['竞品动态：竞对加大投放力度'],
  },
  {
    id: 2, project: '618 大促社媒投放', brand: '完美日记', score: 85, trend: 'stable',
    dimensions: { strategy: 82, execution: 80, media: 90, client: 88 },
    risks: ['KOL 合作风险：头部达人档期冲突', '团队资源不足：618 期间人力缺口 3 人'],
  },
  {
    id: 3, project: '新品上市种草计划', brand: '珀莱雅', score: 68, trend: 'down',
    dimensions: { strategy: 75, execution: 65, media: 60, client: 72 },
    risks: ['预算超支风险：消耗已达 82%'],
  },
  {
    id: 4, project: '品牌危机公关', brand: '薇诺娜', score: 45, trend: 'down',
    dimensions: { strategy: 50, execution: 40, media: 42, client: 48 },
    risks: ['舆情危机：负面评论增长 200%', '预算消耗过快'],
  },
  {
    id: 5, project: 'Z世代消费者洞察', brand: '橘朵', score: 95, trend: 'up',
    dimensions: { strategy: 96, execution: 94, media: 95, client: 95 },
    risks: [],
  },
  {
    id: 6, project: '私域流量运营', brand: '完美日记', score: 88, trend: 'stable',
    dimensions: { strategy: 85, execution: 90, media: 86, client: 91 },
    risks: ['平台政策变更：小红书算法调整'],
  },
];

/* ============================================================
   Helper Functions
   ============================================================ */

const phaseBadgeMap = {
  '策划中': 'purple',
  '执行中': 'cyan',
  '监控中': 'amber',
  '已完成': 'green',
};

const riskLevelBadgeMap = {
  high: { variant: 'red', label: '高' },
  medium: { variant: 'amber', label: '中' },
  low: { variant: 'blue', label: '低' },
};

const riskStatusBadgeMap = {
  tracking: { variant: 'amber', label: '追踪中' },
  handling: { variant: 'red', label: '处理中' },
  resolved: { variant: 'green', label: '已解决' },
  monitoring: { variant: 'blue', label: '监控中' },
};

function getHealthColor(score) {
  if (score >= 80) return 'green';
  if (score >= 60) return 'amber';
  return 'red';
}

function getHealthLabel(score) {
  if (score >= 80) return '健康';
  if (score >= 60) return '关注';
  return '预警';
}

function getTrendIcon(trend) {
  if (trend === 'up') return <ArrowUpRight size={14} style={{ color: 'var(--accent-green)' }} />;
  if (trend === 'down') return <ArrowDownRight size={14} style={{ color: 'var(--accent-red)' }} />;
  return <Minus size={14} style={{ color: 'var(--accent-amber)' }} />;
}

function getTrendLabel(trend) {
  if (trend === 'up') return '健康';
  if (trend === 'down') return '下降';
  return '稳定';
}

/* ============================================================
   Tab 1: 经营总览
   ============================================================ */
function TabOverview() {
  const projectColumns = [
    { key: 'project', label: '项目名称', render: (val) => <span className="font-medium text-primary">{val}</span> },
    { key: 'brand', label: '品牌' },
    { key: 'phase', label: '阶段', render: (val) => <Badge variant={phaseBadgeMap[val] || 'neutral'}>{val}</Badge> },
    { key: 'budget', label: '预算', render: (val) => <span className="font-mono text-primary">{val}</span> },
    { key: 'spent', label: '消耗', render: (val) => <span className="font-mono text-secondary">{val}</span> },
    { key: 'roi', label: 'ROI', render: (val) => <span className="font-mono" style={{ color: val === '-' ? 'var(--text-muted)' : 'var(--accent-green)' }}>{val}</span> },
    {
      key: 'health', label: '健康度',
      render: (val) => (
        <div className="flex items-center gap-2">
          <ProgressBar value={val} color={getHealthColor(val)} size="sm" showLabel={false} style={{ width: 60 }} />
          <span className="font-mono text-xs" style={{ color: val >= 80 ? 'var(--accent-green)' : val >= 60 ? 'var(--accent-amber)' : 'var(--accent-red)' }}>
            {val}
          </span>
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      {/* 全局核心指标 */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          title="活跃项目"
          value="20"
          change={3}
          changeLabel="本月"
          icon={FolderOpen}
          color="blue"
        />
        <StatCard
          title="总预算"
          value="¥2.5M"
          subtitle="已消耗 62%"
          icon={DollarSign}
          color="green"
        />
        <StatCard
          title="团队效能"
          value="87%"
          change={5}
          changeLabel="vs 上月"
          icon={TrendingUp}
          color="cyan"
        />
        <StatCard
          title="客户满意度"
          value="4.5/5.0"
          icon={Star}
          color="amber"
        />
      </div>

      {/* 跨岗位 KPI 概览 */}
      <div className="grid grid-cols-3 gap-4">
        <KpiCard
          title="策略产出"
          value="92%"
          target={90}
          current={92}
          color="purple"
          trend={[
            { value: 80 }, { value: 83 }, { value: 85 }, { value: 88 }, { value: 90 }, { value: 92 },
          ]}
        />
        <KpiCard
          title="执行效率"
          value="78%"
          target={85}
          current={78}
          color="cyan"
          trend={[
            { value: 70 }, { value: 72 }, { value: 74 }, { value: 76 }, { value: 77 }, { value: 78 },
          ]}
        />
        <KpiCard
          title="投放 ROI"
          value="3.2x"
          target={3.5}
          current={3.2}
          color="green"
          trend={[
            { value: 2.5 }, { value: 2.7 }, { value: 2.9 }, { value: 3.0 }, { value: 3.1 }, { value: 3.2 },
          ]}
        />
      </div>

      {/* 项目概览表格 */}
      <div>
        <div className="section-title">项目概览</div>
        <DataTable columns={projectColumns} data={projectTableData} />
      </div>
    </div>
  );
}

/* ============================================================
   Tab 2: KPI 监控
   ============================================================ */
function TabKpi() {
  const [kpiView, setKpiView] = useState('role');

  const kpiViewOptions = [
    { key: 'role', label: '按岗位' },
    { key: 'project', label: '按项目' },
    { key: 'time', label: '按时间' },
  ];

  // KPI 趋势图 SVG 参数
  const chartWidth = 700;
  const chartHeight = 200;
  const padding = 40;
  const drawWidth = chartWidth - padding * 2;
  const drawHeight = chartHeight - padding * 2;

  // 找到所有数据的最大最小值
  const allValues = kpiTrendData.flatMap((d) => [d.planner, d.executor, d.media]);
  const minVal = Math.floor(Math.min(...allValues) / 10) * 10;
  const maxVal = Math.ceil(Math.max(...allValues) / 10) * 10;
  const rangeVal = maxVal - minVal || 1;

  function buildLinePoints(dataKey) {
    return kpiTrendData
      .map((d, i) => {
        const x = padding + (i / (kpiTrendData.length - 1)) * drawWidth;
        const y = padding + drawHeight - ((d[dataKey] - minVal) / rangeVal) * drawHeight;
        return `${x},${y}`;
      })
      .join(' ');
  }

  function buildAreaPoints(dataKey) {
    const linePoints = kpiTrendData
      .map((d, i) => {
        const x = padding + (i / (kpiTrendData.length - 1)) * drawWidth;
        const y = padding + drawHeight - ((d[dataKey] - minVal) / rangeVal) * drawHeight;
        return `${x},${y}`;
      })
      .join(' ');
    return `${padding},${padding + drawHeight} ${linePoints} ${padding + drawWidth},${padding + drawHeight}`;
  }

  // Y 轴刻度
  const yTicks = [];
  for (let i = 0; i <= 4; i++) {
    yTicks.push(minVal + (rangeVal / 4) * i);
  }

  // X 轴标签（每 5 天显示一个）
  const xLabels = kpiTrendData.filter((_, i) => i % 5 === 0 || i === kpiTrendData.length - 1);

  return (
    <div className="flex flex-col gap-6">
      {/* KPI 维度切换 */}
      <div className="flex items-center gap-2">
        {kpiViewOptions.map((opt) => (
          <button
            key={opt.key}
            className={`btn btn-sm ${kpiView === opt.key ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setKpiView(opt.key)}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* 按岗位视图 */}
      {kpiView === 'role' && (
        <>
          {/* 3 个岗位 KPI 卡片 */}
          <div className="grid grid-cols-3 gap-4">
            {roleKpiData.map((role) => (
              <div key={role.role} className="card">
                <div className="card-header">
                  <div className="flex items-center gap-3">
                    <div
                      className="flex items-center justify-center"
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: 'var(--radius-md)',
                        backgroundColor: `var(--accent-${role.color}-subtle)`,
                        color: `var(--accent-${role.color})`,
                      }}
                    >
                      <role.icon size={18} />
                    </div>
                    <div>
                      <h4 className="text-md font-semibold text-primary">{role.role}岗位</h4>
                      <span className="text-xs text-muted">核心 KPI 指标</span>
                    </div>
                  </div>
                </div>
                <div className="card-body">
                  <div className="flex flex-col gap-4">
                    {role.kpis.map((kpi) => {
                      const rate = typeof kpi.value === 'number' && kpi.target
                        ? Math.round((kpi.value / kpi.target) * 100)
                        : 0;
                      const isExceeded = rate >= 100;
                      return (
                        <div key={kpi.name}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-sm text-secondary">{kpi.name}</span>
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-sm font-semibold text-primary">
                                {kpi.value}{kpi.unit}
                              </span>
                              <span className="text-xs text-muted">
                                / {kpi.target}{kpi.unit}
                              </span>
                            </div>
                          </div>
                          <ProgressBar
                            value={Math.min(rate, 100)}
                            color={isExceeded ? 'green' : role.color}
                            size="sm"
                          />
                          <div className="text-xs text-muted mt-1 font-mono">
                            达成率 {rate}%
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <div
                    className="mt-4 pt-3 text-xs text-secondary"
                    style={{ borderTop: '1px solid var(--border-subtle)', lineHeight: 'var(--leading-relaxed)' }}
                  >
                    {role.trend}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* KPI 趋势图 */}
          <div className="chart-container">
            <div className="chart-header">
              <h3>KPI 趋势图（最近 30 天）</h3>
              <div className="flex items-center gap-4">
                <div className="chart-legend-item">
                  <span className="chart-legend-dot" style={{ backgroundColor: 'var(--accent-purple)' }} />
                  <span>策划</span>
                </div>
                <div className="chart-legend-item">
                  <span className="chart-legend-dot" style={{ backgroundColor: 'var(--accent-cyan)' }} />
                  <span>执行</span>
                </div>
                <div className="chart-legend-item">
                  <span className="chart-legend-dot" style={{ backgroundColor: 'var(--accent-green)' }} />
                  <span>媒介</span>
                </div>
              </div>
            </div>
            <div className="chart-body" style={{ padding: 'var(--space-4) var(--space-5)' }}>
              <svg width="100%" viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="xMidYMid meet">
                <defs>
                  <linearGradient id="purpleGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--accent-purple)" stopOpacity="0.2" />
                    <stop offset="100%" stopColor="var(--accent-purple)" stopOpacity="0" />
                  </linearGradient>
                  <linearGradient id="cyanGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--accent-cyan)" stopOpacity="0.2" />
                    <stop offset="100%" stopColor="var(--accent-cyan)" stopOpacity="0" />
                  </linearGradient>
                  <linearGradient id="greenGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--accent-green)" stopOpacity="0.2" />
                    <stop offset="100%" stopColor="var(--accent-green)" stopOpacity="0" />
                  </linearGradient>
                </defs>

                {/* Grid lines */}
                {yTicks.map((val, i) => {
                  const y = padding + (i / 4) * drawHeight;
                  return (
                    <g key={i}>
                      <line
                        x1={padding}
                        y1={y}
                        x2={padding + drawWidth}
                        y2={y}
                        stroke="var(--border-subtle)"
                        strokeWidth="1"
                      />
                      <text
                        x={padding - 8}
                        y={y + 4}
                        textAnchor="end"
                        fill="var(--text-muted)"
                        fontSize="10"
                        fontFamily="var(--font-mono)"
                      >
                        {Math.round(val)}
                      </text>
                    </g>
                  );
                })}

                {/* X-axis labels */}
                {xLabels.map((d, i) => {
                  const idx = kpiTrendData.indexOf(d);
                  const x = padding + (idx / (kpiTrendData.length - 1)) * drawWidth;
                  return (
                    <text
                      key={i}
                      x={x}
                      y={chartHeight - 8}
                      textAnchor="middle"
                      fill="var(--text-muted)"
                      fontSize="10"
                    >
                      {d.day}日
                    </text>
                  );
                })}

                {/* Area fills */}
                <polygon points={buildAreaPoints('planner')} fill="url(#purpleGrad)" />
                <polygon points={buildAreaPoints('executor')} fill="url(#cyanGrad)" />
                <polygon points={buildAreaPoints('media')} fill="url(#greenGrad)" />

                {/* Lines */}
                <polyline
                  points={buildLinePoints('planner')}
                  fill="none"
                  stroke="var(--accent-purple)"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <polyline
                  points={buildLinePoints('executor')}
                  fill="none"
                  stroke="var(--accent-cyan)"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <polyline
                  points={buildLinePoints('media')}
                  fill="none"
                  stroke="var(--accent-green)"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
          </div>
        </>
      )}

      {/* 按项目视图 */}
      {kpiView === 'project' && (
        <div className="card">
          <div className="card-body">
            <div className="flex flex-col gap-4">
              {projectTableData.map((p) => (
                <div key={p.id} className="flex items-center gap-4 py-3" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <div className="flex-1">
                    <div className="text-sm font-medium text-primary">{p.project}</div>
                    <div className="text-xs text-muted">{p.brand}</div>
                  </div>
                  <Badge variant={phaseBadgeMap[p.phase] || 'neutral'}>{p.phase}</Badge>
                  <div className="text-sm font-mono text-secondary">{p.budget}</div>
                  <div className="text-sm font-mono text-secondary">{p.spent}</div>
                  <div className="text-sm font-mono" style={{ color: p.roi === '-' ? 'var(--text-muted)' : 'var(--accent-green)' }}>{p.roi}</div>
                  <div className="flex items-center gap-2" style={{ width: 100 }}>
                    <ProgressBar value={p.health} color={getHealthColor(p.health)} size="sm" />
                    <span className="font-mono text-xs" style={{ color: `var(--accent-${getHealthColor(p.health)})` }}>{p.health}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 按时间视图 */}
      {kpiView === 'time' && (
        <div className="chart-container">
          <div className="chart-header">
            <h3>KPI 月度趋势（近 6 个月）</h3>
          </div>
          <div className="chart-body">
            <div className="flex flex-col gap-6">
              {['策略产出率', '执行效率', '投放 ROI'].map((metric, idx) => {
                const colors = ['purple', 'cyan', 'green'];
                const values = [
                  [80, 83, 85, 88, 90, 92],
                  [70, 72, 74, 76, 77, 78],
                  [2.5, 2.7, 2.9, 3.0, 3.1, 3.2],
                ];
                const months = ['11月', '12月', '1月', '2月', '3月', '4月'];
                const maxV = Math.max(...values[idx]);
                return (
                  <div key={metric}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-secondary">{metric}</span>
                      <span className="font-mono text-sm font-semibold" style={{ color: `var(--accent-${colors[idx]})` }}>
                        {values[idx][values[idx].length - 1]}
                      </span>
                    </div>
                    <div className="flex items-end gap-3" style={{ height: 80 }}>
                      {values[idx].map((v, i) => (
                        <div key={i} className="flex flex-col items-center gap-1 flex-1">
                          <div
                            style={{
                              width: '100%',
                              maxWidth: 40,
                              height: `${(v / maxV) * 60}px`,
                              backgroundColor: `var(--accent-${colors[idx]})`,
                              borderRadius: 'var(--radius-sm) var(--radius-sm) 0 0',
                              opacity: i === values[idx].length - 1 ? 1 : 0.5,
                              transition: 'height 0.4s ease',
                            }}
                          />
                          <span className="text-xs text-muted">{months[i]}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ============================================================
   Tab 3: 风险分布
   ============================================================ */
function TabRisk() {
  // 风险矩阵数据
  const riskMatrix = {
    highImpactHighProb: [
      { id: 1, text: '预算超支风险' },
      { id: 2, text: '舆情危机' },
    ],
    highImpactLowProb: [
      { id: 3, text: '数据安全事件' },
    ],
    lowImpactHighProb: [
      { id: 4, text: 'KOL 档期冲突' },
      { id: 5, text: '团队资源不足' },
      { id: 6, text: '平台政策变更' },
    ],
    lowImpactLowProb: [
      { id: 7, text: '供应商延迟' },
      { id: 8, text: '客户需求变更' },
      { id: 9, text: '素材合规风险' },
      { id: 10, text: '竞品动态' },
    ],
  };

  const riskColumns = [
    { key: 'risk', label: '风险描述', render: (val) => <span className="text-sm text-primary">{val}</span> },
    { key: 'project', label: '关联项目' },
    {
      key: 'level', label: '等级',
      render: (val) => {
        const config = riskLevelBadgeMap[val];
        return <Badge variant={config.variant}>{config.label}</Badge>;
      },
    },
    { key: 'owner', label: '负责人' },
    { key: 'impact', label: '影响' },
    {
      key: 'status', label: '状态',
      render: (val) => {
        const config = riskStatusBadgeMap[val];
        return <Badge variant={config.variant}>{config.label}</Badge>;
      },
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      {/* 风险统计 */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard
          title="高风险"
          value="2"
          icon={AlertTriangle}
          color="red"
        />
        <StatCard
          title="中风险"
          value="5"
          icon={AlertCircle}
          color="amber"
        />
        <StatCard
          title="低风险"
          value="8"
          icon={Info}
          color="blue"
        />
      </div>

      {/* 风险矩阵图 */}
      <div>
        <div className="section-title">风险矩阵</div>
        <div className="card">
          <div className="card-body">
            {/* 矩阵标签 */}
            <div className="flex items-center gap-4 mb-4">
              <div
                className="flex items-center justify-center text-xs font-medium text-muted uppercase tracking-wide"
                style={{ width: 60, height: 20 }}
              >
                影响
              </div>
              <div className="flex-1 flex items-center justify-center text-xs text-muted">
                概率
              </div>
            </div>

            {/* 2x2 矩阵 */}
            <div
              className="grid gap-2"
              style={{
                gridTemplateColumns: '1fr 1fr',
                gridTemplateRows: '1fr 1fr',
                height: 240,
              }}
            >
              {/* 高影响-低概率（左上） */}
              <div
                className="rounded-lg p-4 flex flex-col gap-2"
                style={{
                  backgroundColor: 'var(--accent-amber-subtle)',
                  border: '1px solid rgba(245, 158, 11, 0.2)',
                }}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold" style={{ color: 'var(--accent-amber)' }}>高影响 / 低概率</span>
                  <span className="font-mono text-xs text-muted">{riskMatrix.highImpactLowProb.length}</span>
                </div>
                <div className="flex flex-col gap-1 flex-1">
                  {riskMatrix.highImpactLowProb.map((r) => (
                    <div key={r.id} className="flex items-center gap-2">
                      <span className="flex-shrink-0" style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: 'var(--accent-amber)' }} />
                      <span className="text-xs text-secondary">{r.text}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* 高影响-高概率（右上） */}
              <div
                className="rounded-lg p-4 flex flex-col gap-2"
                style={{
                  backgroundColor: 'var(--accent-red-subtle)',
                  border: '1px solid rgba(239, 68, 68, 0.2)',
                }}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold" style={{ color: 'var(--accent-red)' }}>高影响 / 高概率</span>
                  <span className="font-mono text-xs text-muted">{riskMatrix.highImpactHighProb.length}</span>
                </div>
                <div className="flex flex-col gap-1 flex-1">
                  {riskMatrix.highImpactHighProb.map((r) => (
                    <div key={r.id} className="flex items-center gap-2">
                      <span className="flex-shrink-0" style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: 'var(--accent-red)' }} />
                      <span className="text-xs text-secondary">{r.text}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* 低影响-低概率（左下） */}
              <div
                className="rounded-lg p-4 flex flex-col gap-2"
                style={{
                  backgroundColor: 'var(--accent-blue-subtle)',
                  border: '1px solid rgba(59, 130, 246, 0.2)',
                }}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold" style={{ color: 'var(--accent-blue)' }}>低影响 / 低概率</span>
                  <span className="font-mono text-xs text-muted">{riskMatrix.lowImpactLowProb.length}</span>
                </div>
                <div className="flex flex-col gap-1 flex-1">
                  {riskMatrix.lowImpactLowProb.map((r) => (
                    <div key={r.id} className="flex items-center gap-2">
                      <span className="flex-shrink-0" style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: 'var(--accent-blue)' }} />
                      <span className="text-xs text-secondary">{r.text}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* 低影响-高概率（右下） */}
              <div
                className="rounded-lg p-4 flex flex-col gap-2"
                style={{
                  backgroundColor: 'var(--accent-amber-subtle)',
                  border: '1px solid rgba(245, 158, 11, 0.15)',
                }}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold" style={{ color: 'var(--accent-amber)' }}>低影响 / 高概率</span>
                  <span className="font-mono text-xs text-muted">{riskMatrix.lowImpactHighProb.length}</span>
                </div>
                <div className="flex flex-col gap-1 flex-1">
                  {riskMatrix.lowImpactHighProb.map((r) => (
                    <div key={r.id} className="flex items-center gap-2">
                      <span className="flex-shrink-0" style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: 'var(--accent-amber)' }} />
                      <span className="text-xs text-secondary">{r.text}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* 轴标签 */}
            <div className="flex items-center justify-between mt-3">
              <span className="text-xs text-muted">低</span>
              <span className="text-xs text-muted uppercase tracking-wide">影响程度</span>
              <span className="text-xs text-muted">高</span>
            </div>
          </div>
        </div>
      </div>

      {/* 风险详情列表 */}
      <div>
        <div className="section-title">风险详情</div>
        <DataTable columns={riskColumns} data={riskTableData} />
      </div>
    </div>
  );
}

/* ============================================================
   Tab 4: 项目健康度
   ============================================================ */
function TabHealth() {
  // 环形图参数
  const healthDistribution = [
    { label: '健康', count: 12, percentage: 60, color: 'var(--accent-green)' },
    { label: '关注', count: 5, percentage: 25, color: 'var(--accent-amber)' },
    { label: '预警', count: 3, percentage: 15, color: 'var(--accent-red)' },
  ];

  // SVG 环形图
  const ringRadius = 70;
  const ringStroke = 20;
  const ringCircumference = 2 * Math.PI * ringRadius;
  let accumulatedOffset = 0;

  return (
    <div className="flex flex-col gap-6">
      {/* 健康度分布 - 环形图 */}
      <div className="grid gap-4" style={{ gridTemplateColumns: '2fr 3fr' }}>
        <div className="card">
          <div className="card-header">
            <h3>健康度分布</h3>
          </div>
          <div className="card-body flex flex-col items-center justify-center">
            {/* SVG 环形图 */}
            <div className="relative" style={{ width: 180, height: 180 }}>
              <svg width="180" height="180" viewBox="0 0 180 180">
                {/* 背景圆环 */}
                <circle
                  cx="90"
                  cy="90"
                  r={ringRadius}
                  fill="none"
                  stroke="var(--bg-elevated)"
                  strokeWidth={ringStroke}
                />
                {/* 健康段 */}
                {healthDistribution.map((seg, i) => {
                  const dashLength = (seg.percentage / 100) * ringCircumference;
                  const dashGap = ringCircumference - dashLength;
                  const offset = -accumulatedOffset;
                  accumulatedOffset += dashLength;
                  return (
                    <circle
                      key={i}
                      cx="90"
                      cy="90"
                      r={ringRadius}
                      fill="none"
                      stroke={seg.color}
                      strokeWidth={ringStroke}
                      strokeDasharray={`${dashLength} ${dashGap}`}
                      strokeDashoffset={offset}
                      strokeLinecap="round"
                      transform="rotate(-90 90 90)"
                      style={{ transition: 'stroke-dasharray 0.6s ease' }}
                    />
                  );
                })}
              </svg>
              {/* 中心文字 */}
              <div
                className="absolute flex flex-col items-center justify-center"
                style={{ inset: 0 }}
              >
                <span className="font-mono text-2xl font-bold text-primary">20</span>
                <span className="text-xs text-muted">总项目</span>
              </div>
            </div>

            {/* 图例 */}
            <div className="flex items-center gap-6 mt-6">
              {healthDistribution.map((seg) => (
                <div key={seg.label} className="flex items-center gap-2">
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      backgroundColor: seg.color,
                    }}
                  />
                  <span className="text-xs text-secondary">{seg.label}</span>
                  <span className="font-mono text-xs font-semibold text-primary">{seg.count}</span>
                  <span className="text-xs text-muted">({seg.percentage}%)</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 健康度概要统计 */}
        <div className="card">
          <div className="card-header">
            <h3>健康度概要</h3>
          </div>
          <div className="card-body">
            <div className="grid grid-cols-3 gap-6">
              <div className="flex flex-col items-center gap-3 p-4 rounded-lg" style={{ backgroundColor: 'var(--accent-green-subtle)' }}>
                <span className="font-mono text-3xl font-bold" style={{ color: 'var(--accent-green)' }}>12</span>
                <span className="text-sm text-secondary">健康项目</span>
                <span className="text-xs text-muted">占比 60%</span>
              </div>
              <div className="flex flex-col items-center gap-3 p-4 rounded-lg" style={{ backgroundColor: 'var(--accent-amber-subtle)' }}>
                <span className="font-mono text-3xl font-bold" style={{ color: 'var(--accent-amber)' }}>5</span>
                <span className="text-sm text-secondary">关注项目</span>
                <span className="text-xs text-muted">占比 25%</span>
              </div>
              <div className="flex flex-col items-center gap-3 p-4 rounded-lg" style={{ backgroundColor: 'var(--accent-red-subtle)' }}>
                <span className="font-mono text-3xl font-bold" style={{ color: 'var(--accent-red)' }}>3</span>
                <span className="text-sm text-secondary">预警项目</span>
                <span className="text-xs text-muted">占比 15%</span>
              </div>
            </div>
            <div className="mt-6 pt-4 flex flex-col gap-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
              <div className="flex items-center justify-between">
                <span className="text-sm text-secondary">平均健康度评分</span>
                <span className="font-mono text-lg font-bold text-primary">78.8</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-secondary">较上月变化</span>
                <span className="flex items-center gap-1 font-mono text-sm" style={{ color: 'var(--accent-green)' }}>
                  <ArrowUpRight size={14} />
                  +2.3
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-secondary">需重点关注</span>
                <span className="font-mono text-sm font-semibold" style={{ color: 'var(--accent-red)' }}>3 个项目</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 项目健康度卡片列表 */}
      <div>
        <div className="section-title">项目健康度详情</div>
        <div className="grid grid-cols-2 gap-4">
          {projectHealthData.map((proj) => {
            const healthColor = getHealthColor(proj.score);
            const healthColorVar = `var(--accent-${healthColor})`;
            return (
              <div key={proj.id} className="card">
                <div className="card-header">
                  <div className="flex items-center gap-3">
                    <div>
                      <h4 className="text-md font-semibold text-primary">{proj.project}</h4>
                      <span className="text-xs text-muted">{proj.brand}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {getTrendIcon(proj.trend)}
                    <span className="text-xs text-muted">{getTrendLabel(proj.trend)}</span>
                  </div>
                </div>
                <div className="card-body">
                  {/* 健康度评分 */}
                  <div className="flex items-center gap-4 mb-5">
                    <span
                      className="font-mono font-bold"
                      style={{ fontSize: 'var(--text-3xl)', color: healthColorVar, lineHeight: 1 }}
                    >
                      {proj.score}
                    </span>
                    <div className="flex-1">
                      <ProgressBar value={proj.score} color={healthColor} size="md" />
                      <span className="text-xs text-muted mt-1">{getHealthLabel(proj.score)}</span>
                    </div>
                  </div>

                  {/* 4 个维度评分 */}
                  <div className="grid grid-cols-2 gap-3 mb-4">
                    {[
                      { key: 'strategy', label: '策略' },
                      { key: 'execution', label: '执行' },
                      { key: 'media', label: '媒介' },
                      { key: 'client', label: '客户' },
                    ].map((dim) => (
                      <div key={dim.key}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs text-muted">{dim.label}</span>
                          <span className="font-mono text-xs font-semibold text-primary">{proj.dimensions[dim.key]}</span>
                        </div>
                        <ProgressBar
                          value={proj.dimensions[dim.key]}
                          color={proj.dimensions[dim.key] >= 80 ? 'green' : proj.dimensions[dim.key] >= 60 ? 'amber' : 'red'}
                          size="sm"
                        />
                      </div>
                    ))}
                  </div>

                  {/* 最近风险事件 */}
                  {proj.risks.length > 0 && (
                    <div className="pt-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                      <div className="text-xs text-muted mb-2 font-medium uppercase tracking-wide">最近风险事件</div>
                      <div className="flex flex-col gap-1">
                        {proj.risks.map((risk, i) => (
                          <div key={i} className="flex items-start gap-2 text-xs text-secondary">
                            <AlertCircle size={12} className="flex-shrink-0 mt-0.5" style={{ color: 'var(--accent-amber)' }} />
                            <span>{risk}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {proj.risks.length === 0 && (
                    <div className="pt-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                      <div className="text-xs text-muted">暂无风险事件</div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Main Component
   ============================================================ */
export default function ManagerDashboard() {
  const [activeTab, setActiveTab] = useState('overview');

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview': return <TabOverview />;
      case 'kpi': return <TabKpi />;
      case 'risk': return <TabRisk />;
      case 'health': return <TabHealth />;
      default: return <TabOverview />;
    }
  };

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="管理层工作台"
        subtitle="全局总览 | 跨岗位 KPI | 风险监控 | 项目健康度"
        breadcrumbs={[
          { label: '工作台' },
          { label: '管理层工作台' },
        ]}
      />
      <TabBar tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />
      <div className="page-body">
        {renderTabContent()}
      </div>
    </div>
  );
}
