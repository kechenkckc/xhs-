import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  FolderOpen, DollarSign, TrendingUp, Star, AlertTriangle, AlertCircle,
  Info, Shield, BarChart3, Activity, ArrowUpRight, ArrowDownRight,
  Minus, LayoutDashboard, ClipboardList, Lightbulb,
  Megaphone, Download, RefreshCw, X, CheckCircle2, CalendarDays,
  SlidersHorizontal, Send
} from 'lucide-react';
import StatCard from '../../components/StatCard';
import DataTable from '../../components/DataTable';
import Badge from '../../components/Badge';
import ProgressBar from '../../components/ProgressBar';
import TabBar from '../../components/TabBar';
import PageHeader from '../../components/PageHeader';
import KpiCard from '../../components/KpiCard';
import Modal from '../../components/Modal';
import ProjectWorkspacePanel from '../../components/ProjectWorkspacePanel';
import { getProjectBrand, projectWorkspaceApi, useProjectWorkspace } from '../../shared/projectWorkspace';

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
  { id: 1, project: 'Q2 品牌焕新传播', brand: '花西子', phase: '执行中', budget: '¥500K', spent: '¥310K', roi: '3.5x', health: 92, owner: '陈静', schedule: 86, nextMilestone: '达人内容二审', blockers: 1 },
  { id: 2, project: '618 大促社媒投放', brand: '完美日记', phase: '策划中', budget: '¥800K', spent: '¥120K', roi: '-', health: 85, owner: '刘洋', schedule: 42, nextMilestone: '策略定稿会', blockers: 2 },
  { id: 3, project: '新品上市种草计划', brand: '珀莱雅', phase: '执行中', budget: '¥300K', spent: '¥245K', roi: '2.8x', health: 68, owner: '张明', schedule: 73, nextMilestone: '预算复核', blockers: 3 },
  { id: 4, project: '品牌危机公关', brand: '薇诺娜', phase: '监控中', budget: '¥200K', spent: '¥180K', roi: '1.2x', health: 45, owner: '李华', schedule: 58, nextMilestone: '舆情日报复盘', blockers: 4 },
  { id: 5, project: 'Z世代消费者洞察', brand: '橘朵', phase: '已完成', budget: '¥150K', spent: '¥148K', roi: '4.1x', health: 95, owner: '周强', schedule: 100, nextMilestone: '归档报告', blockers: 0 },
  { id: 6, project: '双11 预热投放', brand: '花西子', phase: '策划中', budget: '¥1.2M', spent: '¥80K', roi: '-', health: 78, owner: '郑丽', schedule: 24, nextMilestone: '供应商比稿', blockers: 1 },
  { id: 7, project: '跨境品牌推广', brand: '珀莱雅', phase: '执行中', budget: '¥600K', spent: '¥420K', roi: '2.1x', health: 55, owner: '赵磊', schedule: 64, nextMilestone: '素材合规复审', blockers: 3 },
  { id: 8, project: '私域流量运营', brand: '完美日记', phase: '执行中', budget: '¥250K', spent: '¥190K', roi: '3.8x', health: 88, owner: '吴敏', schedule: 81, nextMilestone: '小红书策略调优', blockers: 1 },
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

const managerStatDetails = {
  projects: {
    title: '活跃项目钻取',
    accent: 'blue',
    rows: [
      ['执行中', '5 个', '+2 vs 上月'],
      ['策划中', '2 个', '平均启动周期 4.5 天'],
      ['监控中', '1 个', '高优先级待处理'],
      ['已完成', '12 个', '归档率 96%'],
    ],
  },
  budget: {
    title: '预算消耗明细',
    accent: 'green',
    rows: [
      ['总预算', '¥2.5M', '年度池'],
      ['已消耗', '¥1.55M', '62%'],
      ['本周新增', '¥180K', '3 个项目'],
      ['预计结余', '¥430K', '按当前节奏'],
    ],
  },
  efficiency: {
    title: '团队效能结构',
    accent: 'cyan',
    rows: [
      ['策划', '92%', '高于目标'],
      ['执行', '78%', '需关注'],
      ['媒介', '88%', '稳定'],
      ['跨岗协同', '83%', '待提升'],
    ],
  },
  satisfaction: {
    title: '客户满意度反馈',
    accent: 'amber',
    rows: [
      ['评分', '4.5/5.0', '+0.2'],
      ['正向反馈', '18 条', '创意与响应速度'],
      ['待回访客户', '3 位', '本周内完成'],
      ['低分原因', '交付节奏', '集中在 2 个项目'],
    ],
  },
};

const overviewKpiDetails = {
  strategy: {
    title: '策略产出测试界面',
    metric: '策略产出',
    value: '92%',
    color: 'purple',
    fields: ['策略方向', '目标人群', '关键洞察', '预计提交时间'],
  },
  execution: {
    title: '执行效率测试界面',
    metric: '执行效率',
    value: '78%',
    color: 'cyan',
    fields: ['任务类型', '负责人', '阻塞原因', '需要协同部门'],
  },
  roi: {
    title: '投放 ROI 测试界面',
    metric: '投放 ROI',
    value: '3.2x',
    color: 'green',
    fields: ['投放平台', '预算区间', '优化动作', '预期 ROI'],
  },
};

const projectKpiRows = projectTableData.map((project, index) => ({
  ...project,
  strategy: [92, 84, 76, 58, 96, 80, 72, 88][index],
  execution: [88, 74, 65, 40, 94, 70, 55, 90][index],
  media: [94, 90, 60, 42, 95, 82, 58, 86][index],
}));

const timeKpiMetrics = [
  { key: 'strategy', label: '策略产出率', color: 'purple', values: [80, 83, 85, 88, 90, 92], target: 90, unit: '%' },
  { key: 'execution', label: '执行效率', color: 'cyan', values: [70, 72, 74, 76, 77, 78], target: 85, unit: '%' },
  { key: 'roi', label: '投放 ROI', color: 'green', values: [2.5, 2.7, 2.9, 3.0, 3.1, 3.2], target: 3.5, unit: 'x' },
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

function ActionToast({ message, onClose }) {
  if (!message) return null;

  return (
    <div className="manager-toast" role="status">
      <CheckCircle2 size={16} />
      <span>{message}</span>
      <button type="button" className="manager-icon-button" onClick={onClose} aria-label="关闭提示">
        <X size={14} />
      </button>
    </div>
  );
}

function InfoGrid({ items }) {
  return (
    <div className="manager-info-grid">
      {items.map((item) => (
        <div key={item.label} className="manager-info-cell">
          <span className="manager-info-label">{item.label}</span>
          <span className="manager-info-value">{item.value}</span>
          {item.meta && <span className="manager-info-meta">{item.meta}</span>}
        </div>
      ))}
    </div>
  );
}

function TestWorkbench({ title, fields, onSubmit }) {
  const [formData, setFormData] = useState(() => (
    fields.reduce((acc, field) => ({ ...acc, [field]: '' }), {})
  ));

  return (
    <div className="manager-test-panel">
      <div className="manager-test-panel-head">
        <div>
          <div className="section-title" style={{ marginBottom: 4 }}>{title}</div>
          <p>这里先作为后续真实功能的测试界面，所有控件都可以填写和提交。</p>
        </div>
        <Badge variant="blue">测试界面</Badge>
      </div>
      <div className="manager-form-grid">
        {fields.map((field, index) => (
          <label key={field} className="manager-field">
            <span>{field}</span>
            {index === fields.length - 1 ? (
              <textarea
                value={formData[field]}
                rows={3}
                onChange={(event) => setFormData({ ...formData, [field]: event.target.value })}
                placeholder={`填写${field}`}
              />
            ) : (
              <input
                value={formData[field]}
                onChange={(event) => setFormData({ ...formData, [field]: event.target.value })}
                placeholder={`输入${field}`}
              />
            )}
          </label>
        ))}
      </div>
      <div className="manager-test-actions">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => setFormData(fields.reduce((acc, field) => ({ ...acc, [field]: '' }), {}))}
        >
          <RefreshCw size={14} />
          重置
        </button>
        <button type="button" className="btn btn-primary" onClick={onSubmit}>
          <Send size={14} />
          提交测试
        </button>
      </div>
    </div>
  );
}

function MetricShell({ children, onClick, ariaLabel }) {
  return (
    <button type="button" className="manager-click-shell" onClick={onClick} aria-label={ariaLabel}>
      {children}
    </button>
  );
}

function ProjectDetail({ project }) {
  const healthColor = getHealthColor(project.health || project.score);
  const matchedHealth = projectHealthData.find((item) => item.project === project.project);
  const dimensions = matchedHealth?.dimensions || project.dimensions;

  return (
    <div className="flex flex-col gap-5">
      <div className="manager-detail-hero">
        <div>
          <div className="section-title" style={{ marginBottom: 6 }}>{project.brand}</div>
          <h3>{project.project}</h3>
          <p>{project.nextMilestone || '下一步动作待确认'} · 负责人 {project.owner || '未分配'}</p>
        </div>
        <Badge variant={healthColor}>{getHealthLabel(project.health || project.score)}</Badge>
      </div>
      <InfoGrid
        items={[
          { label: '阶段', value: project.phase || getTrendLabel(project.trend), meta: '当前状态' },
          { label: '预算', value: project.budget || '¥500K', meta: `消耗 ${project.spent || '¥310K'}` },
          { label: 'ROI', value: project.roi || '2.8x', meta: '实时回传' },
          { label: '健康度', value: project.health || project.score, meta: `${project.blockers ?? project.risks?.length ?? 0} 个阻塞` },
        ]}
      />
      <div className="card">
        <div className="card-header">
          <h3>维度拆解</h3>
        </div>
        <div className="card-body flex flex-col gap-3">
          {[
            { key: 'strategy', label: '策略' },
            { key: 'execution', label: '执行' },
            { key: 'media', label: '媒介' },
            { key: 'client', label: '客户' },
          ].map((dim) => {
            const score = dimensions?.[dim.key] ?? project[dim.key] ?? project.health ?? project.score;
            return (
              <div key={dim.key}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm text-secondary">{dim.label}</span>
                  <span className="font-mono text-sm text-primary">{score}</span>
                </div>
                <ProgressBar value={score} color={getHealthColor(score)} size="sm" />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function RiskDetail({ risk, onResolve }) {
  const level = riskLevelBadgeMap[risk.level] || riskLevelBadgeMap.medium;
  const status = riskStatusBadgeMap[risk.status] || riskStatusBadgeMap.tracking;

  return (
    <div className="flex flex-col gap-5">
      <div className="manager-detail-hero">
        <div>
          <div className="section-title" style={{ marginBottom: 6 }}>{risk.project}</div>
          <h3>{risk.risk}</h3>
          <p>负责人 {risk.owner} · 影响：{risk.impact}</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={level.variant}>{level.label}风险</Badge>
          <Badge variant={status.variant}>{status.label}</Badge>
        </div>
      </div>
      <InfoGrid
        items={[
          { label: '发现时间', value: '今日 10:30', meta: '测试数据' },
          { label: '影响范围', value: risk.impact, meta: '需复核' },
          { label: '责任人', value: risk.owner, meta: '已通知' },
          { label: '处置 SLA', value: risk.level === 'high' ? '24h' : '72h', meta: '自动计算' },
        ]}
      />
      <TestWorkbench
        title="风险处置记录"
        fields={['处置动作', '协同人', '预计完成时间', '补充说明']}
        onSubmit={onResolve}
      />
    </div>
  );
}

/* ============================================================
   Tab 1: 经营总览
   ============================================================ */
function managementRows(management) {
  return (management?.projects || []).map((item) => {
    const project = item.project || {};
    const metrics = item.metrics || {};
    return {
      id: project.project_id,
      project: project.project_name || project.project_id,
      brand: getProjectBrand(project),
      phase: project.archived_at ? '已完成' : (metrics.pending_handoffs > 0 ? '待执行拆解' : '执行中'),
      budget: project.brief?.match(/预算[：: ]*([^，。\n]+)/)?.[1] || '待定',
      spent: `${metrics.asset_count || 0} 资产`,
      roi: '-',
      health: metrics.health_score || 0,
      owner: '项目组',
      schedule: metrics.execution_score || 0,
      nextMilestone: metrics.pending_handoffs ? '处理岗位交接' : '推进任务交付',
      blockers: metrics.blocked_tasks || 0,
      rawProject: project,
    };
  });
}

function TabOverview({ onSelectProject, onOpenMetric, onOpenTest, management }) {
  const overview = management?.overview || {};
  const rows = managementRows(management);
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
        <MetricShell onClick={() => onOpenMetric('projects')} ariaLabel="查看活跃项目">
          <StatCard
            title="活跃项目"
            value={overview.active_projects ?? 0}
            icon={FolderOpen}
            color="blue"
          />
        </MetricShell>
        <MetricShell onClick={() => onOpenMetric('budget')} ariaLabel="查看总预算">
          <StatCard
            title="总预算"
            value={overview.asset_total ?? 0}
            subtitle="项目资产总数"
            icon={DollarSign}
            color="green"
          />
        </MetricShell>
        <MetricShell onClick={() => onOpenMetric('efficiency')} ariaLabel="查看团队效能">
          <StatCard
            title="团队效能"
            value={`${overview.average_health ?? 0}%`}
            icon={TrendingUp}
            color="cyan"
          />
        </MetricShell>
        <MetricShell onClick={() => onOpenMetric('satisfaction')} ariaLabel="查看客户满意度">
          <StatCard
            title="客户满意度"
            value={overview.warning_projects ?? 0}
            subtitle="预警项目"
            icon={Star}
            color="amber"
          />
        </MetricShell>
      </div>

      {/* 跨岗位 KPI 概览 */}
      <div className="grid grid-cols-3 gap-4">
        <MetricShell onClick={() => onOpenTest('strategy')} ariaLabel="打开策略产出测试界面">
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
        </MetricShell>
        <MetricShell onClick={() => onOpenTest('execution')} ariaLabel="打开执行效率测试界面">
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
        </MetricShell>
        <MetricShell onClick={() => onOpenTest('roi')} ariaLabel="打开投放 ROI 测试界面">
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
        </MetricShell>
      </div>

      {/* 项目概览表格 */}
      <div>
        <div className="manager-section-head">
          <div className="section-title">项目概览</div>
          <button type="button" className="btn btn-sm btn-secondary" onClick={() => onOpenTest('projectCreate')}>
            <FolderOpen size={14} />
            新建测试项目
          </button>
        </div>
        <DataTable columns={projectColumns} data={rows.length ? rows : projectTableData} onRowClick={onSelectProject} />
      </div>
    </div>
  );
}

function AiManagementPanel({ workspace, onToast }) {
  const [busy, setBusy] = useState(false);
  const [advice, setAdvice] = useState(null);

  const generateAdvice = async () => {
    if (!workspace.projectId) return;
    setBusy(true);
    try {
      const result = await projectWorkspaceApi.aiManagementAdvice(workspace.projectId, {
        persist: true,
        operator: '管理层',
      });
      setAdvice(result.advice);
      await workspace.reloadCurrentProject();
      onToast(result.source === 'llm' ? 'AI 管理建议已生成' : '已用规则生成管理建议');
    } catch (error) {
      onToast(error.message || 'AI 管理建议生成失败');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card ai-result-panel">
      <div className="card-header">
        <h3>AI 管理解读</h3>
        <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={generateAdvice}>
          <Lightbulb size={14} />
          生成建议
        </button>
      </div>
      <div className="card-body">
        {advice ? (
          <pre>{JSON.stringify(advice, null, 2)}</pre>
        ) : (
          <div className="text-sm text-muted">基于当前项目任务、交接、资产、风险和健康度生成管理层摘要、风险优先级、行动建议和经营会议议程。</div>
        )}
      </div>
    </div>
  );
}

/* ============================================================
   Tab 2: KPI 监控
   ============================================================ */
function TabKpi({ onSelectProject, onOpenRole, onToast }) {
  const [kpiView, setKpiView] = useState('role');
  const [activeSeries, setActiveSeries] = useState({ planner: true, executor: true, media: true });
  const [selectedMonth, setSelectedMonth] = useState('4月');

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
  const seriesConfig = [
    { key: 'planner', label: '策划', color: 'purple' },
    { key: 'executor', label: '执行', color: 'cyan' },
    { key: 'media', label: '媒介', color: 'green' },
  ];
  const months = ['11月', '12月', '1月', '2月', '3月', '4月'];

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
              <button
                key={role.role}
                type="button"
                className="manager-card-button"
                onClick={() => onOpenRole(role)}
              >
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
              </button>
            ))}
          </div>

          {/* KPI 趋势图 */}
          <div className="chart-container">
            <div className="chart-header">
              <h3>KPI 趋势图（最近 30 天）</h3>
              <div className="flex items-center gap-4">
                {seriesConfig.map((series) => (
                  <button
                    type="button"
                    key={series.key}
                    className={`chart-legend-item manager-legend-toggle ${activeSeries[series.key] ? 'active' : ''}`}
                    onClick={() => setActiveSeries((current) => ({ ...current, [series.key]: !current[series.key] }))}
                  >
                    <span className="chart-legend-dot" style={{ backgroundColor: `var(--accent-${series.color})` }} />
                    <span>{series.label}</span>
                  </button>
                ))}
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
                {activeSeries.planner && <polygon points={buildAreaPoints('planner')} fill="url(#purpleGrad)" />}
                {activeSeries.executor && <polygon points={buildAreaPoints('executor')} fill="url(#cyanGrad)" />}
                {activeSeries.media && <polygon points={buildAreaPoints('media')} fill="url(#greenGrad)" />}

                {/* Lines */}
                {activeSeries.planner && (
                  <polyline
                    points={buildLinePoints('planner')}
                    fill="none"
                    stroke="var(--accent-purple)"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                )}
                {activeSeries.executor && (
                  <polyline
                    points={buildLinePoints('executor')}
                    fill="none"
                    stroke="var(--accent-cyan)"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                )}
                {activeSeries.media && (
                  <polyline
                    points={buildLinePoints('media')}
                    fill="none"
                    stroke="var(--accent-green)"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                )}
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
              {projectKpiRows.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className="manager-project-kpi-row"
                  onClick={() => onSelectProject(p)}
                >
                  <div className="flex-1">
                    <div className="text-sm font-medium text-primary">{p.project}</div>
                    <div className="text-xs text-muted">{p.brand}</div>
                  </div>
                  <Badge variant={phaseBadgeMap[p.phase] || 'neutral'}>{p.phase}</Badge>
                  <div className="manager-mini-score">
                    <span>策略</span>
                    <strong>{p.strategy}</strong>
                  </div>
                  <div className="manager-mini-score">
                    <span>执行</span>
                    <strong>{p.execution}</strong>
                  </div>
                  <div className="manager-mini-score">
                    <span>媒介</span>
                    <strong>{p.media}</strong>
                  </div>
                  <div className="text-sm font-mono text-secondary">{p.budget}</div>
                  <div className="text-sm font-mono text-secondary">{p.spent}</div>
                  <div className="text-sm font-mono" style={{ color: p.roi === '-' ? 'var(--text-muted)' : 'var(--accent-green)' }}>{p.roi}</div>
                  <div className="flex items-center gap-2" style={{ width: 100 }}>
                    <ProgressBar value={p.health} color={getHealthColor(p.health)} size="sm" />
                    <span className="font-mono text-xs" style={{ color: `var(--accent-${getHealthColor(p.health)})` }}>{p.health}</span>
                  </div>
                </button>
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
            <div className="flex items-center gap-2">
              {months.map((month) => (
                <button
                  key={month}
                  type="button"
                  className={`btn btn-sm ${selectedMonth === month ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => {
                    setSelectedMonth(month);
                    onToast(`已切换到 ${month} KPI 数据`);
                  }}
                >
                  {month}
                </button>
              ))}
            </div>
          </div>
          <div className="chart-body">
            <div className="flex flex-col gap-6">
              {timeKpiMetrics.map((metric) => {
                const maxV = Math.max(...metric.values);
                return (
                  <button
                    type="button"
                    key={metric.key}
                    className="manager-time-metric"
                    onClick={() => onOpenRole({
                      role: metric.label,
                      color: metric.color,
                      trend: `${selectedMonth} 当前值 ${metric.values[months.indexOf(selectedMonth)]}${metric.unit}，目标 ${metric.target}${metric.unit}`,
                      kpis: [
                        { name: '当前值', value: metric.values[months.indexOf(selectedMonth)], target: metric.target, unit: metric.unit },
                        { name: '上月值', value: metric.values[Math.max(months.indexOf(selectedMonth) - 1, 0)], target: metric.target, unit: metric.unit },
                      ],
                    })}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-secondary">{metric.label}</span>
                      <span className="font-mono text-sm font-semibold" style={{ color: `var(--accent-${metric.color})` }}>
                        {metric.values[months.indexOf(selectedMonth)]}{metric.unit}
                      </span>
                    </div>
                    <div className="flex items-end gap-3" style={{ height: 80 }}>
                      {metric.values.map((v, i) => (
                        <div key={i} className="flex flex-col items-center gap-1 flex-1">
                          <div
                            style={{
                              width: '100%',
                              maxWidth: 40,
                              height: `${(v / maxV) * 60}px`,
                              backgroundColor: `var(--accent-${metric.color})`,
                              borderRadius: 'var(--radius-sm) var(--radius-sm) 0 0',
                              opacity: months[i] === selectedMonth ? 1 : 0.5,
                              transition: 'height 0.4s ease',
                            }}
                          />
                          <span className="text-xs text-muted">{months[i]}</span>
                        </div>
                      ))}
                    </div>
                  </button>
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
function TabRisk({ onOpenRisk, onToast, management }) {
  const [levelFilter, setLevelFilter] = useState('all');
  const [matrixFilter, setMatrixFilter] = useState('all');
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
  const matrixLabels = {
    highImpactLowProb: '高影响 / 低概率',
    highImpactHighProb: '高影响 / 高概率',
    lowImpactLowProb: '低影响 / 低概率',
    lowImpactHighProb: '低影响 / 高概率',
  };
  const matrixRiskIds = matrixFilter === 'all' ? null : new Set(riskMatrix[matrixFilter].map((risk) => risk.id));
  const realRisks = (management?.risks || []).map((risk, index) => ({
    id: risk.risk_id || index,
    risk: risk.title,
    project: managementRows(management).find((row) => row.id === risk.project_id)?.project || risk.project_id,
    level: risk.level || 'medium',
    owner: '项目负责人',
    impact: risk.type || '协作风险',
    status: risk.status || 'tracking',
  }));
  const riskSource = realRisks.length ? realRisks : riskTableData;
  const filteredRisks = riskSource.filter((risk) => (
    (levelFilter === 'all' || risk.level === levelFilter)
    && (!matrixRiskIds || matrixRiskIds.has(risk.id))
  ));

  const handleMatrixClick = (key) => {
    setMatrixFilter((current) => current === key ? 'all' : key);
    onToast(`${matrixLabels[key]} 已${matrixFilter === key ? '取消筛选' : '应用筛选'}`);
  };

  return (
    <div className="flex flex-col gap-6">
      {/* 风险统计 */}
      <div className="grid grid-cols-3 gap-4">
        <MetricShell onClick={() => setLevelFilter(levelFilter === 'high' ? 'all' : 'high')} ariaLabel="筛选高风险">
          <StatCard
            title="高风险"
            value="2"
            icon={AlertTriangle}
            color="red"
          />
        </MetricShell>
        <MetricShell onClick={() => setLevelFilter(levelFilter === 'medium' ? 'all' : 'medium')} ariaLabel="筛选中风险">
          <StatCard
            title="中风险"
            value="5"
            icon={AlertCircle}
            color="amber"
          />
        </MetricShell>
        <MetricShell onClick={() => setLevelFilter(levelFilter === 'low' ? 'all' : 'low')} ariaLabel="筛选低风险">
          <StatCard
            title="低风险"
            value="8"
            icon={Info}
            color="blue"
          />
        </MetricShell>
      </div>

      {/* 风险矩阵图 */}
      <div>
        <div className="section-title">风险矩阵</div>
        <div className="card manager-risk-matrix-card">
          <div className="card-body manager-risk-matrix-body">
            {/* 矩阵标签 */}
            <div className="manager-risk-axis-top">
              <span>影响程度</span>
              <strong>发生概率</strong>
              <span>点击象限筛选</span>
            </div>

            {/* 2x2 矩阵 */}
            <div
              className="manager-risk-matrix-grid"
              style={{
                gridTemplateColumns: '1fr 1fr',
                gridTemplateRows: '1fr 1fr',
              }}
            >
              {/* 高影响-低概率（左上） */}
              <button
                type="button"
                className={`manager-risk-cell rounded-lg p-4 flex flex-col gap-2 ${matrixFilter === 'highImpactLowProb' ? 'active' : ''}`}
                onClick={() => handleMatrixClick('highImpactLowProb')}
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
              </button>

              {/* 高影响-高概率（右上） */}
              <button
                type="button"
                className={`manager-risk-cell rounded-lg p-4 flex flex-col gap-2 ${matrixFilter === 'highImpactHighProb' ? 'active' : ''}`}
                onClick={() => handleMatrixClick('highImpactHighProb')}
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
              </button>

              {/* 低影响-低概率（左下） */}
              <button
                type="button"
                className={`manager-risk-cell rounded-lg p-4 flex flex-col gap-2 ${matrixFilter === 'lowImpactLowProb' ? 'active' : ''}`}
                onClick={() => handleMatrixClick('lowImpactLowProb')}
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
              </button>

              {/* 低影响-高概率（右下） */}
              <button
                type="button"
                className={`manager-risk-cell rounded-lg p-4 flex flex-col gap-2 ${matrixFilter === 'lowImpactHighProb' ? 'active' : ''}`}
                onClick={() => handleMatrixClick('lowImpactHighProb')}
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
              </button>
            </div>

            <div className="manager-risk-axis-bottom">
              <span>左侧低概率，右侧高概率</span>
              <span>上方高影响，下方低影响</span>
            </div>
          </div>
        </div>
      </div>

      {/* 风险详情列表 */}
      <div>
        <div className="manager-section-head">
          <div>
            <div className="section-title">风险详情</div>
            <div className="text-xs text-muted">当前显示 {filteredRisks.length} 条，点击行可进入处置测试界面</div>
          </div>
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={() => {
              setLevelFilter('all');
              setMatrixFilter('all');
              onToast('风险筛选已清空');
            }}
          >
            <RefreshCw size={14} />
            清空筛选
          </button>
        </div>
        <DataTable columns={riskColumns} data={filteredRisks} onRowClick={onOpenRisk} emptyText="暂无匹配风险" />
      </div>
    </div>
  );
}

/* ============================================================
   Tab 4: 项目健康度
   ============================================================ */
function TabHealth({ onSelectProject, onToast, management }) {
  const [healthFilter, setHealthFilter] = useState('all');
  // 环形图参数
  const healthDistribution = [
    { key: 'green', label: '健康', count: 12, percentage: 60, color: 'var(--accent-green)' },
    { key: 'amber', label: '关注', count: 5, percentage: 25, color: 'var(--accent-amber)' },
    { key: 'red', label: '预警', count: 3, percentage: 15, color: 'var(--accent-red)' },
  ];

  // SVG 环形图
  const ringRadius = 70;
  const ringStroke = 20;
  const ringCircumference = 2 * Math.PI * ringRadius;
  let accumulatedOffset = 0;
  const realProjects = managementRows(management).map((row) => ({
    id: row.id,
    project: row.project,
    brand: row.brand,
    score: row.health,
    trend: row.health >= 80 ? 'up' : row.health >= 60 ? 'stable' : 'down',
    dimensions: {
      strategy: row.health,
      execution: row.schedule,
      media: Math.max(0, row.health - 5),
      client: Math.min(100, row.health + 5),
    },
    risks: row.blockers ? [`${row.blockers} 个阻塞事项待处理`] : [],
  }));
  const healthSource = realProjects.length ? realProjects : projectHealthData;
  const visibleProjects = healthSource.filter((project) => (
    healthFilter === 'all' || getHealthColor(project.score) === healthFilter
  ));
  const handleHealthFilter = (key, label) => {
    setHealthFilter((current) => current === key ? 'all' : key);
    onToast(`${label}项目已${healthFilter === key ? '取消筛选' : '应用筛选'}`);
  };

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
                      onClick={() => handleHealthFilter(seg.key, seg.label)}
                      style={{
                        transition: 'stroke-dasharray 0.6s ease, opacity 0.2s ease',
                        cursor: 'pointer',
                        opacity: healthFilter === 'all' || healthFilter === seg.key ? 1 : 0.3,
                      }}
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
                <button
                  type="button"
                  key={seg.label}
                  className={`manager-health-legend ${healthFilter === seg.key ? 'active' : ''}`}
                  onClick={() => handleHealthFilter(seg.key, seg.label)}
                >
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
                </button>
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
              <button type="button" className="manager-health-summary" onClick={() => handleHealthFilter('green', '健康')} style={{ backgroundColor: 'var(--accent-green-subtle)' }}>
                <span className="font-mono text-3xl font-bold" style={{ color: 'var(--accent-green)' }}>12</span>
                <span className="text-sm text-secondary">健康项目</span>
                <span className="text-xs text-muted">占比 60%</span>
              </button>
              <button type="button" className="manager-health-summary" onClick={() => handleHealthFilter('amber', '关注')} style={{ backgroundColor: 'var(--accent-amber-subtle)' }}>
                <span className="font-mono text-3xl font-bold" style={{ color: 'var(--accent-amber)' }}>5</span>
                <span className="text-sm text-secondary">关注项目</span>
                <span className="text-xs text-muted">占比 25%</span>
              </button>
              <button type="button" className="manager-health-summary" onClick={() => handleHealthFilter('red', '预警')} style={{ backgroundColor: 'var(--accent-red-subtle)' }}>
                <span className="font-mono text-3xl font-bold" style={{ color: 'var(--accent-red)' }}>3</span>
                <span className="text-sm text-secondary">预警项目</span>
                <span className="text-xs text-muted">占比 15%</span>
              </button>
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
        <div className="manager-section-head">
          <div>
            <div className="section-title">项目健康度详情</div>
            <div className="text-xs text-muted">当前显示 {visibleProjects.length} 个项目，点击卡片查看完整拆解</div>
          </div>
          {healthFilter !== 'all' && (
            <button type="button" className="btn btn-sm btn-secondary" onClick={() => setHealthFilter('all')}>
              <RefreshCw size={14} />
              全部项目
            </button>
          )}
        </div>
        <div className="grid grid-cols-2 gap-4">
          {visibleProjects.map((proj) => {
            const healthColor = getHealthColor(proj.score);
            const healthColorVar = `var(--accent-${healthColor})`;
            return (
              <button key={proj.id} type="button" className="manager-card-button" onClick={() => onSelectProject(proj)}>
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
              </button>
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
export default function ManagerDashboard({ selectedProjectId, onSelectedProjectIdChange }) {
  const navigate = useNavigate();
  const { tab } = useParams();
  const normalizeTab = (value) => (value === 'risks' ? 'risk' : value);
  const initialTab = normalizeTab(tab);
  const [activeTab, setActiveTab] = useState(tabs.some((item) => item.key === initialTab) ? initialTab : 'overview');
  const [modal, setModal] = useState(null);
  const [toast, setToast] = useState('');
  const [management, setManagement] = useState(null);
  const toastTimerRef = useRef(null);
  const workspace = useProjectWorkspace(selectedProjectId, onSelectedProjectIdChange);

  useEffect(() => {
    const nextTab = normalizeTab(tab);
    if (tabs.some((item) => item.key === nextTab)) {
      setActiveTab(nextTab);
    }
  }, [tab]);

  const showToast = (message) => {
    setToast(message);
    window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = window.setTimeout(() => setToast(''), 2600);
  };

  useEffect(() => {
    projectWorkspaceApi.getManagementOverview()
      .then(setManagement)
      .catch(() => setManagement(null));
  }, [workspace.metrics]);

  const handleTabChange = (nextTab) => {
    setActiveTab(nextTab);
    navigate(`/workbench/manager/${nextTab === 'risk' ? 'risks' : nextTab}`);
  };

  const openMetric = (metricKey) => {
    setModal({ type: 'metric', payload: managerStatDetails[metricKey] });
  };

  const openTest = (testKey) => {
    const fallback = {
      title: '功能测试界面',
      metric: '管理操作',
      value: 'Demo',
      color: 'blue',
      fields: ['操作名称', '业务对象', '负责人', '备注'],
    };
    setModal({ type: 'test', payload: overviewKpiDetails[testKey] || fallback });
  };

  const openProject = (project) => {
    setModal({ type: 'project', payload: project });
  };

  const openRole = (role) => {
    setModal({ type: 'role', payload: role });
  };

  const openRisk = (risk) => {
    setModal({ type: 'risk', payload: risk });
  };

  const closeModal = () => setModal(null);

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview': return <TabOverview onSelectProject={openProject} onOpenMetric={openMetric} onOpenTest={openTest} management={management} />;
      case 'kpi': return <TabKpi onSelectProject={openProject} onOpenRole={openRole} onToast={showToast} />;
      case 'risk': return <TabRisk onOpenRisk={openRisk} onToast={showToast} management={management} />;
      case 'health': return <TabHealth onSelectProject={openProject} onToast={showToast} management={management} />;
      default: return <TabOverview onSelectProject={openProject} onOpenMetric={openMetric} onOpenTest={openTest} management={management} />;
    }
  };

  const renderModalBody = () => {
    if (!modal?.payload) return null;

    if (modal.type === 'metric') {
      return (
        <div className="flex flex-col gap-5">
          <InfoGrid
            items={modal.payload.rows.map(([label, value, meta]) => ({ label, value, meta }))}
          />
          <TestWorkbench
            title="管理动作测试"
            fields={['动作名称', '目标范围', '指派负责人', '管理备注']}
            onSubmit={() => showToast(`${modal.payload.title}测试动作已提交`)}
          />
        </div>
      );
    }

    if (modal.type === 'test') {
      return (
        <div className="flex flex-col gap-5">
          <InfoGrid
            items={[
              { label: '指标', value: modal.payload.metric, meta: '当前模块' },
              { label: '当前值', value: modal.payload.value, meta: 'Mock 数据' },
              { label: '状态', value: '可测试', meta: '前端交互已接入' },
              { label: '后续', value: '待接 API', meta: '占位界面' },
            ]}
          />
          <TestWorkbench
            title={modal.payload.title}
            fields={modal.payload.fields}
            onSubmit={() => showToast(`${modal.payload.metric}测试表单已提交`)}
          />
        </div>
      );
    }

    if (modal.type === 'project') {
      return <ProjectDetail project={modal.payload} />;
    }

    if (modal.type === 'role') {
      const role = modal.payload;
      return (
        <div className="flex flex-col gap-5">
          <div className="manager-detail-hero">
            <div>
              <div className="section-title" style={{ marginBottom: 6 }}>KPI 明细</div>
              <h3>{role.role} {role.role?.includes('率') || role.role?.includes('ROI') ? '' : '岗位'}</h3>
              <p>{role.trend}</p>
            </div>
            <Badge variant={role.color || 'blue'}>可钻取</Badge>
          </div>
          <div className="card">
            <div className="card-body flex flex-col gap-4">
              {role.kpis.map((kpi) => {
                const rate = Math.round((kpi.value / kpi.target) * 100);
                return (
                  <div key={kpi.name}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm text-secondary">{kpi.name}</span>
                      <span className="font-mono text-sm text-primary">{kpi.value}{kpi.unit} / {kpi.target}{kpi.unit}</span>
                    </div>
                    <ProgressBar value={Math.min(rate, 100)} color={rate >= 100 ? 'green' : role.color || 'blue'} size="sm" />
                  </div>
                );
              })}
            </div>
          </div>
          <TestWorkbench
            title="KPI 调整测试"
            fields={['调整指标', '目标值', '适用范围', '调整原因']}
            onSubmit={() => showToast(`${role.role} KPI 调整已提交`)}
          />
        </div>
      );
    }

    if (modal.type === 'risk') {
      return (
        <RiskDetail
          risk={modal.payload}
          onResolve={() => showToast(`${modal.payload.risk}处置记录已提交`)}
        />
      );
    }

    return null;
  };

  return (
    <div className="flex flex-col h-full">
      <AiManagementPanel workspace={workspace} onToast={showToast} />
      <div className="page-body">
        {renderTabContent()}
      </div>
      <ActionToast message={toast} onClose={() => setToast('')} />
      <Modal
        isOpen={Boolean(modal)}
        onClose={closeModal}
        title={modal?.payload?.title || modal?.payload?.project || modal?.payload?.risk || '管理层测试界面'}
        size="lg"
        footer={(
          <>
            <button type="button" className="btn btn-secondary" onClick={closeModal}>
              关闭
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                showToast('已保存当前弹窗中的测试操作');
                closeModal();
              }}
            >
              保存测试
            </button>
          </>
        )}
      >
        {renderModalBody()}
      </Modal>
    </div>
  );
}
