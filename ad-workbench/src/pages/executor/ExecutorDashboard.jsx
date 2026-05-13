import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Inbox, CheckSquare, Clock, Bot, Brain, CalendarDays, Send,
  FileSpreadsheet, MessageSquare, Mic, FileText, Upload, Sparkles,
  Users, Image, AlertTriangle, Bell, ChevronRight, Eye, GitBranch,
  BarChart3, Zap, LayoutDashboard, ClipboardList, Play, Settings,
  RefreshCw, CheckCircle2, XCircle, Timer, Link2, Filter, Plus,
  ListTodo, Activity, Save
} from 'lucide-react';
import StatCard from '../../components/StatCard';
import DataTable from '../../components/DataTable';
import Badge from '../../components/Badge';
import ProgressBar from '../../components/ProgressBar';
import TabBar from '../../components/TabBar';
import PageHeader from '../../components/PageHeader';
import AgentCard from '../../components/AgentCard';
import ProjectWorkspacePanel from '../../components/ProjectWorkspacePanel';
import { ClickSurface, useWorkbenchActions } from '../../components/WorkbenchActionKit';
import { projectWorkspaceApi, useProjectWorkspace } from '../../shared/projectWorkspace';

/* ============================================================
   Mock Data
   ============================================================ */

const tabs = [
  { key: 'overview', label: '工作概览', icon: <LayoutDashboard size={14} /> },
  { key: 'requirement', label: '需求接入', icon: <Inbox size={14} /> },
  { key: 'agent', label: 'Agent 编排', icon: <Bot size={14} /> },
  { key: 'kanban', label: '任务看板', icon: <ClipboardList size={14} /> },
  { key: 'daily', label: 'Daily Push', icon: <Send size={14} /> },
  { key: 'followup', label: '执行跟进', icon: <ListTodo size={14} /> },
];

// Tab 1 - 工作概览: 紧急任务列表
const urgentTasks = [
  { id: 1, task: '花西子 Q2 品牌焕新方案终稿', project: '花西子', assignee: '张明', deadline: '2026-04-13', status: 'urgent' },
  { id: 2, task: '618 大促达人名单确认', project: '完美日记', assignee: '李芳', deadline: '2026-04-13', status: 'in_progress' },
  { id: 3, task: '珀莱雅新品素材回收', project: '珀莱雅', assignee: '王磊', deadline: '2026-04-14', status: 'pending' },
  { id: 4, task: '薇诺娜危机公关稿件审核', project: '薇诺娜', assignee: '赵琳', deadline: '2026-04-13', status: 'urgent' },
  { id: 5, task: '橘朵 Z 世代调研报告', project: '橘朵', assignee: '陈浩', deadline: '2026-04-15', status: 'in_progress' },
  { id: 6, task: '飞书项目同步任务更新', project: '多项目', assignee: '系统', deadline: '2026-04-13', status: 'completed' },
];

// Tab 2 - 需求接入: 已接入需求列表
const requirementData = [
  { id: 'REQ-001', source: 'feishu', sourceLabel: '飞书文档', type: '品牌推广', project: '花西子', status: 'processing', time: '2026-04-13 14:30' },
  { id: 'REQ-002', source: 'excel', sourceLabel: 'Excel', type: '新品上市', project: '珀莱雅', status: 'pending', time: '2026-04-13 13:15' },
  { id: 'REQ-003', source: 'chat', sourceLabel: '聊天记录', type: '活动营销', project: '完美日记', status: 'processing', time: '2026-04-13 11:40' },
  { id: 'REQ-004', source: 'voice', sourceLabel: '语音转写', type: '日常维护', project: '薇诺娜', status: 'completed', time: '2026-04-13 10:20' },
  { id: 'REQ-005', source: 'feishu', sourceLabel: '飞书文档', type: '品牌推广', project: '橘朵', status: 'pending', time: '2026-04-13 09:50' },
  { id: 'REQ-006', source: 'excel', sourceLabel: 'Excel', type: '新品上市', project: '花西子', status: 'processing', time: '2026-04-12 18:30' },
  { id: 'REQ-007', source: 'chat', sourceLabel: '聊天记录', type: '活动营销', project: '珀莱雅', status: 'completed', time: '2026-04-12 16:45' },
  { id: 'REQ-008', source: 'voice', sourceLabel: '语音转写', type: '日常维护', project: '完美日记', status: 'pending', time: '2026-04-12 15:10' },
];

// Tab 3 - Agent 编排: Agent 配置
const agentConfigs = [
  {
    id: 1,
    name: '洞察 Agent',
    icon: Brain,
    type: '数据分析',
    enabled: true,
    frequency: '实时',
    outputFormat: '报告',
    notify: '飞书群',
  },
  {
    id: 2,
    name: '排期 Agent',
    icon: CalendarDays,
    type: '任务调度',
    enabled: true,
    frequency: '每日',
    outputFormat: '甘特图',
    notify: '飞书群',
  },
  {
    id: 3,
    name: '汇报 Agent',
    icon: BarChart3,
    type: '数据汇总',
    enabled: false,
    frequency: '每周',
    outputFormat: 'PPT',
    notify: '邮件',
  },
  {
    id: 4,
    name: '协同 Agent',
    icon: RefreshCw,
    type: '流程同步',
    enabled: true,
    frequency: '实时',
    outputFormat: '任务列表',
    notify: '飞书群',
  },
];

// Tab 3 - 编排模板
const orchestrationTemplates = [
  {
    id: 1,
    name: '品牌推广标准流程',
    description: '适用于品牌年度/季度推广项目',
    agents: ['洞察 Agent', '排期 Agent', '汇报 Agent', '协同 Agent'],
    color: 'var(--accent-purple)',
  },
  {
    id: 2,
    name: '新品上市快闪流程',
    description: '适用于新品快速上市推广',
    agents: ['洞察 Agent', '排期 Agent', '协同 Agent'],
    color: 'var(--accent-cyan)',
  },
  {
    id: 3,
    name: '日常维护轻量流程',
    description: '适用于日常品牌维护与内容更新',
    agents: ['汇报 Agent', '协同 Agent'],
    color: 'var(--accent-green)',
  },
];

// Tab 4 - 任务看板
const kanbanData = {
  todo: [
    { id: 1, title: '花西子 Q2 种草方案', project: '花西子', assignee: '张明', deadline: '2026-04-16', priority: 'high', deps: 0 },
    { id: 2, title: '完美日记 618 达人筛选', project: '完美日记', assignee: '李芳', deadline: '2026-04-17', priority: 'medium', deps: 1 },
    { id: 3, title: '薇诺娜舆情周报', project: '薇诺娜', assignee: '赵琳', deadline: '2026-04-15', priority: 'low', deps: 0 },
  ],
  in_progress: [
    { id: 4, title: '珀莱雅双抗精华 KOL 对接', project: '珀莱雅', assignee: '王磊', deadline: '2026-04-14', priority: 'high', deps: 2 },
    { id: 5, title: '橘朵 Z 世代调研报告', project: '橘朵', assignee: '陈浩', deadline: '2026-04-15', priority: 'medium', deps: 1 },
    { id: 6, title: '花西子竞品分析更新', project: '花西子', assignee: '张明', deadline: '2026-04-14', priority: 'high', deps: 0 },
    { id: 7, title: '完美日记直播脚本撰写', project: '完美日记', assignee: '李芳', deadline: '2026-04-16', priority: 'medium', deps: 3 },
  ],
  review: [
    { id: 8, title: '薇诺娜危机公关稿件', project: '薇诺娜', assignee: '赵琳', deadline: '2026-04-13', priority: 'high', deps: 1 },
    { id: 9, title: '珀莱雅新品素材审核', project: '珀莱雅', assignee: '王磊', deadline: '2026-04-14', priority: 'medium', deps: 0 },
  ],
  done: [
    { id: 10, title: '花西子 3 月数据复盘', project: '花西子', assignee: '张明', deadline: '2026-04-10', priority: 'low', deps: 0 },
    { id: 11, title: '完美日记达人合同签署', project: '完美日记', assignee: '李芳', deadline: '2026-04-09', priority: 'medium', deps: 0 },
    { id: 12, title: '橘朵社媒内容排期', project: '橘朵', assignee: '陈浩', deadline: '2026-04-08', priority: 'low', deps: 0 },
    { id: 13, title: '薇诺娜月度汇报 PPT', project: '薇诺娜', assignee: '赵琳', deadline: '2026-04-07', priority: 'medium', deps: 2 },
    { id: 14, title: '珀莱雅竞品声量监控', project: '珀莱雅', assignee: '王磊', deadline: '2026-04-06', priority: 'low', deps: 0 },
  ],
};

// Tab 5 - Daily Push: 今日推送预览
const dailyPushPreview = {
  hotTopics: [
    { rank: 1, text: '国货美妆出海趋势加速，东南亚市场成新增长极' },
    { rank: 2, text: '抖音美妆直播新规落地，达人带货门槛提高' },
    { rank: 3, text: '成分党崛起：烟酰胺、视黄醇搜索量环比增长 45%' },
    { rank: 4, text: '小红书种草笔记算法调整，质量权重提升' },
    { rank: 5, text: 'Z 世代消费报告：理性消费成主流，性价比优先' },
  ],
  projectProgress: [
    { name: '花西子 Q2 品牌焕新', progress: 72, color: 'purple' },
    { name: '完美日记 618 大促', progress: 45, color: 'cyan' },
    { name: '珀莱雅新品上市', progress: 88, color: 'green' },
  ],
  alerts: [
    { id: 1, text: '薇诺娜舆情预警：负面评论较昨日上升 32%', level: 'high' },
    { id: 2, text: '花西子达人对接超时：3 位达人未确认档期', level: 'medium' },
  ],
};

// Tab 5 - 历史推送记录
const pushHistory = [
  { id: 1, date: '2026-04-12', time: '09:00', content: '行业热点 + 进度 + 预警', status: 'sent', readRate: '92%' },
  { id: 2, date: '2026-04-11', time: '09:00', content: '行业热点 + 进度', status: 'sent', readRate: '88%' },
  { id: 3, date: '2026-04-10', time: '09:00', content: '行业热点 + 进度 + 预警 + 待办', status: 'sent', readRate: '95%' },
  { id: 4, date: '2026-04-09', time: '09:00', content: '行业热点 + 进度', status: 'sent', readRate: '90%' },
  { id: 5, date: '2026-04-08', time: '09:00', content: '行业热点 + 进度 + 预警', status: 'sent', readRate: '87%' },
  { id: 6, date: '2026-04-07', time: '09:00', content: '行业热点 + 进度', status: 'sent', readRate: '91%' },
  { id: 7, date: '2026-04-06', time: '09:00', content: '行业热点 + 进度 + 预警', status: 'sent', readRate: '89%' },
];

// Tab 6 - 执行跟进: 跟进事项列表
const followupItems = [
  { id: 1, item: '花西子 KOL 档期确认', type: '达人对接', project: '花西子', person: '张明 / 达人A', status: 'pending', action: '催办' },
  { id: 2, item: '完美日记直播素材回收', type: '素材回收', project: '完美日记', person: '李芳 / 摄影师B', status: 'overdue', action: '紧急催办' },
  { id: 3, item: '珀莱雅新品文案审核', type: '内容审核', project: '珀莱雅', person: '王磊 / 策划C', status: 'in_progress', action: '查看' },
  { id: 4, item: '薇诺娜危机公关跟进', type: '异常处理', project: '薇诺娜', person: '赵琳 / PR团队', status: 'urgent', action: '立即处理' },
  { id: 5, item: '橘朵调研问卷回收', type: '数据收集', project: '橘朵', person: '陈浩 / 数据组', status: 'completed', action: '归档' },
  { id: 6, item: '花西子竞品数据更新', type: '数据收集', project: '花西子', person: '张明 / 洞察Agent', status: 'in_progress', action: '查看' },
  { id: 7, item: '完美日记达人合同签署', type: '达人对接', project: '完美日记', person: '李芳 / 法务', status: 'completed', action: '归档' },
  { id: 8, item: '珀莱雅排期方案确认', type: '排期管理', project: '珀莱雅', person: '王磊 / 客户', status: 'pending', action: '催办' },
  { id: 9, item: '薇诺娜舆情日报发送', type: '日常维护', project: '薇诺娜', person: '赵琳 / 系统自动', status: 'completed', action: '查看' },
  { id: 10, item: '橘朵社媒内容排期', type: '排期管理', project: '橘朵', person: '陈浩 / 排期Agent', status: 'pending', action: '催办' },
];

/* ============================================================
   Status Badge Renderers
   ============================================================ */
const taskStatusMap = {
  urgent: { variant: 'red', label: '紧急' },
  in_progress: { variant: 'blue', label: '进行中' },
  pending: { variant: 'amber', label: '待处理' },
  completed: { variant: 'green', label: '已完成' },
};

const requirementStatusMap = {
  processing: { variant: 'blue', label: '处理中' },
  pending: { variant: 'amber', label: '待处理' },
  completed: { variant: 'green', label: '已完成' },
};

const requirementTypeMap = {
  '品牌推广': { variant: 'purple', label: '品牌推广' },
  '新品上市': { variant: 'cyan', label: '新品上市' },
  '活动营销': { variant: 'amber', label: '活动营销' },
  '日常维护': { variant: 'neutral', label: '日常维护' },
};

const priorityMap = {
  high: { variant: 'red', label: '高' },
  medium: { variant: 'amber', label: '中' },
  low: { variant: 'neutral', label: '低' },
};

const followupStatusMap = {
  pending: { variant: 'amber', label: '待处理' },
  in_progress: { variant: 'blue', label: '进行中' },
  completed: { variant: 'green', label: '已完成' },
  overdue: { variant: 'red', label: '已逾期' },
  urgent: { variant: 'red', label: '紧急' },
};

const followupTypeMap = {
  '达人对接': { variant: 'pink', label: '达人对接' },
  '素材回收': { variant: 'amber', label: '素材回收' },
  '内容审核': { variant: 'purple', label: '内容审核' },
  '异常处理': { variant: 'red', label: '异常处理' },
  '数据收集': { variant: 'cyan', label: '数据收集' },
  '排期管理': { variant: 'blue', label: '排期管理' },
  '日常维护': { variant: 'neutral', label: '日常维护' },
};

function renderBadge(map, value) {
  const config = map[value] || { variant: 'neutral', label: value };
  return <Badge variant={config.variant}>{config.label}</Badge>;
}

/* ============================================================
   Source Icon Renderer
   ============================================================ */
const sourceIconMap = {
  feishu: { icon: <FileText size={12} />, color: 'var(--accent-blue)' },
  excel: { icon: <FileSpreadsheet size={12} />, color: 'var(--accent-green)' },
  chat: { icon: <MessageSquare size={12} />, color: 'var(--accent-purple)' },
  voice: { icon: <Mic size={12} />, color: 'var(--accent-amber)' },
};

function renderSource(value, row) {
  const config = sourceIconMap[row.source] || sourceIconMap.feishu;
  return (
    <span className="flex items-center gap-2">
      <span style={{ color: config.color }}>{config.icon}</span>
      <span>{row.sourceLabel}</span>
    </span>
  );
}

/* ============================================================
   Tab 1: 工作概览
   ============================================================ */
function TabOverview({ actions, workspace }) {
  const summary = workspace.metrics?.summary || {};
  const pending = workspace.handoffs.filter((item) => item.to_role === 'executor' && item.status === 'pending');
  const blocked = workspace.tasks.filter((item) => item.status === 'blocked');
  const taskColumns = [
    { key: 'task', label: '任务名称', render: (val) => <span className="font-medium text-primary">{val}</span> },
    { key: 'project', label: '所属项目', render: (val) => <Badge variant="neutral">{val}</Badge> },
    { key: 'assignee', label: '负责人' },
    { key: 'deadline', label: '截止时间', render: (val) => <span className="font-mono">{val}</span> },
    { key: 'status', label: '状态', render: (val) => renderBadge(taskStatusMap, val) },
  ];

  return (
    <div className="flex flex-col gap-6">
      {/* Top StatCards */}
      <div className="grid grid-cols-4 gap-4">
        <ClickSurface onClick={() => actions.openDetail('待处理需求', { 数量: 7, 今日新增: 3, 状态: '待分配' })}>
          <StatCard title="待接收交接" value={pending.length} icon={Inbox} color="cyan" />
        </ClickSurface>
        <ClickSurface onClick={() => actions.openDetail('进行中任务', { 数量: 23, 占比: '45%', 今日更新: 8 })}>
          <StatCard title="进行中任务" value={workspace.tasks.filter((item) => item.status === 'doing').length} icon={CheckSquare} color="blue" />
        </ClickSurface>
        <ClickSurface onClick={() => actions.openForm('今日到期处理', ['任务名称', '负责人', '延期原因', '处理动作'])}>
          <StatCard title="阻塞事项" value={blocked.length} icon={Clock} color="red" />
        </ClickSurface>
        <ClickSurface onClick={() => actions.openDetail('Agent 运行状态', { 运行中: '4', 总数: '6', 状态: '正常运行' })}>
          <StatCard title="完成率" value={`${summary.execution_score ?? 0}%`} icon={Bot} color="green" />
        </ClickSurface>
      </div>

      {/* Agent Team Status */}
      <div>
        <div className="section-title">Agent 团队状态</div>
        <div className="grid grid-cols-4 gap-4">
          {[
            { name: '洞察 Agent', type: '数据分析', status: 'running', description: '正在分析竞品数据', icon: Brain },
            { name: '排期 Agent', type: '任务调度', status: 'running', description: '已生成 3 个排期方案', icon: CalendarDays },
            { name: '汇报 Agent', type: '数据汇总', status: 'idle', description: '上次汇报: 昨日 18:00', icon: BarChart3 },
            { name: '协同 Agent', type: '流程同步', status: 'running', description: '已同步 12 条任务到飞书', icon: RefreshCw },
          ].map((agent) => (
            <ClickSurface key={agent.name} onClick={() => actions.openForm(`${agent.name}操作`, ['操作类型', '运行范围', '通知对象', '备注'], agent)}>
              <AgentCard {...agent} />
            </ClickSurface>
          ))}
        </div>
      </div>

      {/* Urgent Task Table */}
      <div>
        <div className="section-title">当前项目任务</div>
        <DataTable columns={taskColumns} data={(workspace.tasks.length ? workspace.tasks.map((task) => ({ ...task, task: task.title, assignee: task.owner || '未分配', deadline: task.due_at || '待定' })) : urgentTasks)} onRowClick={(row) => actions.openForm(row.task || row.title, ['处理动作', '负责人', '预计完成', '备注'], row)} />
      </div>
    </div>
  );
}

/* ============================================================
   Tab 2: 需求接入
   ============================================================ */
function TabRequirement({ actions, workspace }) {
  const [aiBusy, setAiBusy] = useState(false);
  const [aiTasks, setAiTasks] = useState([]);
  const executorHandoffs = workspace.handoffs.filter((item) => item.to_role === 'executor');
  const handleAccept = async (handoff) => {
    await projectWorkspaceApi.acceptHandoff(workspace.projectId, handoff.handoff_id, '执行');
    await workspace.reloadCurrentProject();
    actions.notify('交接已接收');
  };
  const handleCreateTasks = async (handoff) => {
    await projectWorkspaceApi.createTasksFromHandoff(workspace.projectId, handoff.handoff_id, '执行');
    await workspace.reloadCurrentProject();
    actions.notify('已从交接单生成执行任务');
  };
  const handleAiCreateTasks = async (handoff) => {
    setAiBusy(true);
    try {
      const result = await projectWorkspaceApi.aiTasks(workspace.projectId, {
        payload: { handoff },
        persist: true,
        operator: '执行',
      });
      setAiTasks(result.tasks || []);
      await workspace.reloadCurrentProject();
      actions.notify(result.source === 'llm' ? 'AI 已拆解执行任务' : '已用规则生成执行任务');
    } catch (error) {
      actions.notify(error.message || 'AI 任务拆解失败');
    } finally {
      setAiBusy(false);
    }
  };
  const reqColumns = [
    { key: 'id', label: '编号', render: (val) => <span className="font-mono text-primary">{val}</span> },
    { key: 'source', label: '来源', render: renderSource },
    { key: 'type', label: '需求类型', render: (val) => renderBadge(requirementTypeMap, val) },
    { key: 'project', label: '项目卡', render: (val) => <Badge variant="neutral">{val}</Badge> },
    { key: 'status', label: '状态', render: (val) => renderBadge(requirementStatusMap, val) },
    { key: 'time', label: '接入时间', render: (val) => <span className="font-mono text-muted">{val}</span> },
  ];

  const pieData = [
    { label: '品牌推广', percentage: 35, color: 'var(--accent-purple)' },
    { label: '新品上市', percentage: 25, color: 'var(--accent-cyan)' },
    { label: '活动营销', percentage: 20, color: 'var(--accent-amber)' },
    { label: '日常维护', percentage: 20, color: 'var(--accent-green)' },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="section-title">项目交接接入</div>
        <div className="handoff-grid">
          {executorHandoffs.map((handoff) => (
            <div className="handoff-card" key={handoff.handoff_id}>
              <div className="handoff-card-head">
                <div>
                  <h4>{handoff.title}</h4>
                  <p>{handoff.summary || '暂无摘要'}</p>
                </div>
                {renderBadge(requirementStatusMap, handoff.status === 'pending' ? 'pending' : handoff.status === 'completed' ? 'completed' : 'processing')}
              </div>
              <div className="text-xs text-muted">来源：{handoff.from_role} · {handoff.created_at}</div>
              <div className="handoff-card-actions">
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => actions.openDetail(handoff.title, handoff.payload)}>详情</button>
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => handleAccept(handoff)}>接收</button>
                <button type="button" className="btn btn-primary btn-sm" onClick={() => handleCreateTasks(handoff)}>生成任务</button>
                <button type="button" className="btn btn-secondary btn-sm" disabled={aiBusy} onClick={() => handleAiCreateTasks(handoff)}>
                  <Bot size={14} />
                  AI 拆任务
                </button>
              </div>
            </div>
          ))}
          {!executorHandoffs.length && <div className="empty-state"><div className="empty-state-text">暂无执行交接</div></div>}
        </div>
      </div>

      {aiTasks.length > 0 && (
        <div className="card ai-result-panel">
          <div className="card-header">
            <h3>AI 任务拆解结果</h3>
            <Badge variant="green">{aiTasks.length} 项</Badge>
          </div>
          <div className="card-body">
            <pre>{JSON.stringify(aiTasks, null, 2)}</pre>
          </div>
        </div>
      )}

      {/* Upload Area */}
      <div className="card">
        <div className="card-body">
          <button
            type="button"
            className="flex flex-col items-center justify-center gap-4 py-8"
            onClick={() => actions.openForm('需求文件接入', ['接入来源', '需求类型', '关联项目', '补充说明'])}
            style={{
              width: '100%',
              border: '2px dashed var(--border-primary)',
              borderRadius: 'var(--radius-lg)',
              backgroundColor: 'var(--bg-secondary)',
              cursor: 'pointer',
              transition: 'var(--transition-base)',
            }}
          >
            <div className="flex items-center gap-6">
              <div className="flex flex-col items-center gap-2">
                <div
                  className="flex items-center justify-center"
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: 'var(--radius-lg)',
                    backgroundColor: 'var(--accent-blue-subtle)',
                    color: 'var(--accent-blue)',
                  }}
                >
                  <FileText size={24} />
                </div>
                <span className="text-xs text-muted">文档</span>
              </div>
              <div className="flex flex-col items-center gap-2">
                <div
                  className="flex items-center justify-center"
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: 'var(--radius-lg)',
                    backgroundColor: 'var(--accent-green-subtle)',
                    color: 'var(--accent-green)',
                  }}
                >
                  <FileSpreadsheet size={24} />
                </div>
                <span className="text-xs text-muted">表格</span>
              </div>
              <div className="flex flex-col items-center gap-2">
                <div
                  className="flex items-center justify-center"
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: 'var(--radius-lg)',
                    backgroundColor: 'var(--accent-purple-subtle)',
                    color: 'var(--accent-purple)',
                  }}
                >
                  <MessageSquare size={24} />
                </div>
                <span className="text-xs text-muted">聊天记录</span>
              </div>
              <div className="flex flex-col items-center gap-2">
                <div
                  className="flex items-center justify-center"
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: 'var(--radius-lg)',
                    backgroundColor: 'var(--accent-amber-subtle)',
                    color: 'var(--accent-amber)',
                  }}
                >
                  <Mic size={24} />
                </div>
                <span className="text-xs text-muted">语音转写</span>
              </div>
            </div>
            <div className="flex flex-col items-center gap-2">
              <div className="flex items-center gap-2">
                <Upload size={16} style={{ color: 'var(--text-muted)' }} />
                <span className="text-sm text-secondary">拖拽文件到此处，或点击上传</span>
              </div>
              <span className="text-xs text-muted">自动识别需求类型</span>
            </div>
          </button>
        </div>
      </div>

      {/* Requirement List + Pie Chart */}
      <div className="grid gap-4" style={{ gridTemplateColumns: '1fr 320px' }}>
        {/* Requirement List */}
        <div className="card">
          <div className="card-header">
            <h3>已接入需求</h3>
            <span className="text-xs font-mono text-muted">共 8 条</span>
          </div>
        <DataTable columns={reqColumns} data={requirementData} onRowClick={(row) => actions.openForm(`${row.id} 需求处理`, ['处理动作', '分配执行人', '截止时间', '处理备注'], row)} />
        </div>

        {/* Pie Chart (CSS Simulated) */}
        <div className="card">
          <div className="card-header">
            <h3>需求类型分布</h3>
          </div>
          <div className="card-body">
            <div className="flex flex-col items-center gap-5">
              {/* CSS Pie Chart */}
              <div
                style={{
                  width: 160,
                  height: 160,
                  borderRadius: '50%',
                  background: `conic-gradient(
                    var(--accent-purple) 0% 35%,
                    var(--accent-cyan) 35% 60%,
                    var(--accent-amber) 60% 80%,
                    var(--accent-green) 80% 100%
                  )`,
                  position: 'relative',
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    inset: 30,
                    borderRadius: '50%',
                    backgroundColor: 'var(--bg-tertiary)',
                  }}
                />
              </div>
              {/* Legend */}
              <div className="flex flex-col gap-3 w-full">
                {pieData.map((item) => (
                  <div key={item.label} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span
                        style={{
                          width: 10,
                          height: 10,
                          borderRadius: '50%',
                          backgroundColor: item.color,
                          flexShrink: 0,
                        }}
                      />
                      <span className="text-sm text-secondary">{item.label}</span>
                    </div>
                    <span className="text-sm font-mono font-semibold text-primary">{item.percentage}%</span>
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
   Tab 3: Agent 编排
   ============================================================ */
function TabAgent({ actions }) {
  const [agentStates, setAgentStates] = useState(
    agentConfigs.reduce((acc, a) => ({ ...acc, [a.id]: a.enabled }), {})
  );

  const toggleAgent = (id) => {
    setAgentStates((prev) => ({ ...prev, [id]: !prev[id] }));
    actions.notify('Agent 状态已切换');
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Description */}
      <div className="card">
        <div className="card-body">
          <div className="flex items-center gap-3">
            <div
              className="flex items-center justify-center flex-shrink-0"
              style={{
                width: 36,
                height: 36,
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--accent-blue-subtle)',
                color: 'var(--accent-blue)',
              }}
            >
              <Settings size={18} />
            </div>
            <p className="text-sm text-secondary mb-0" style={{ lineHeight: 'var(--leading-relaxed)' }}>
              按项目类型自动组合 Agent 团队，配置执行策略。启用后 Agent 将按配置的频率自动运行并输出结果。
            </p>
          </div>
        </div>
      </div>

      {/* Agent Configuration Cards */}
      <div className="grid grid-cols-4 gap-4">
        {agentConfigs.map((agent) => {
          const isEnabled = agentStates[agent.id];
          const IconComp = agent.icon;
          return (
            <ClickSurface key={agent.id} as="div" className="card" onClick={() => actions.openForm(`${agent.name}配置`, ['频率', '输出格式', '通知渠道', '说明'], agent)} style={{ opacity: isEnabled ? 1 : 0.6 }}>
              <div className="card-body">
                {/* Header: Name + Toggle */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div
                      className="flex items-center justify-center flex-shrink-0"
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: 'var(--radius-md)',
                        backgroundColor: isEnabled ? 'var(--accent-blue-subtle)' : 'var(--bg-elevated)',
                        color: isEnabled ? 'var(--accent-blue)' : 'var(--text-muted)',
                      }}
                    >
                      <IconComp size={18} />
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-primary">{agent.name}</div>
                      <div className="text-xs text-muted">{agent.type}</div>
                    </div>
                  </div>
                  {/* Toggle Switch */}
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        toggleAgent(agent.id);
                      }}
                    style={{
                      width: 40,
                      height: 22,
                      borderRadius: 'var(--radius-full)',
                      backgroundColor: isEnabled ? 'var(--accent-blue)' : 'var(--bg-elevated)',
                      border: `1px solid ${isEnabled ? 'var(--accent-blue)' : 'var(--border-primary)'}`,
                      position: 'relative',
                      transition: 'var(--transition-base)',
                      cursor: 'pointer',
                      padding: 0,
                    }}
                  >
                    <div
                      style={{
                        width: 16,
                        height: 16,
                        borderRadius: '50%',
                        backgroundColor: '#ffffff',
                        position: 'absolute',
                        top: 2,
                        left: isEnabled ? 20 : 2,
                        transition: 'var(--transition-base)',
                      }}
                    />
                  </button>
                </div>

                {/* Config Items */}
                <div className="flex flex-col gap-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted">执行频率</span>
                    <span className="text-xs font-mono text-secondary">{agent.frequency}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted">输出格式</span>
                    <span className="text-xs font-mono text-secondary">{agent.outputFormat}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted">通知方式</span>
                    <span className="text-xs font-mono text-secondary">{agent.notify}</span>
                  </div>
                </div>

                {/* Status Indicator */}
                <div className="flex items-center gap-2 mt-4 pt-3" style={{ borderTop: '1px solid var(--border-subtle)' }}>
                  <span
                    className="status-dot"
                    style={{
                      backgroundColor: isEnabled ? 'var(--accent-green)' : 'var(--text-muted)',
                      animation: isEnabled ? 'pulse 2s ease-in-out infinite' : 'none',
                    }}
                  />
                  <span className="text-xs" style={{ color: isEnabled ? 'var(--accent-green)' : 'var(--text-muted)' }}>
                    {isEnabled ? '已启用' : '已停用'}
                  </span>
                </div>
              </div>
            </ClickSurface>
          );
        })}
      </div>

      {/* Orchestration Templates */}
      <div>
        <div className="section-title">编排模板</div>
        <div className="grid grid-cols-3 gap-4">
          {orchestrationTemplates.map((tpl) => (
            <ClickSurface key={tpl.id} className="card" onClick={() => actions.openForm(`套用${tpl.name}`, ['项目', '执行范围', '启用 Agent', '备注'], tpl)}>
              <div className="card-body">
                <div className="flex items-center gap-3 mb-3">
                  <div
                    className="flex items-center justify-center flex-shrink-0"
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: `${tpl.color}20`,
                      color: tpl.color,
                    }}
                  >
                    <GitBranch size={16} />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-primary">{tpl.name}</div>
                    <div className="text-xs text-muted">{tpl.description}</div>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 mt-3">
                  {tpl.agents.map((agentName) => (
                    <span
                      key={agentName}
                      className="tag"
                      style={{
                        borderColor: tpl.color,
                        color: tpl.color,
                        backgroundColor: `${tpl.color}15`,
                      }}
                    >
                      <Bot size={10} />
                      {agentName}
                    </span>
                  ))}
                </div>
              </div>
            </ClickSurface>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Tab 4: 任务看板
   ============================================================ */
function TabKanban({ actions, workspace }) {
  const columns = [
    { key: 'todo', title: '待处理', color: 'var(--text-muted)' },
    { key: 'doing', title: '进行中', color: 'var(--accent-blue)' },
    { key: 'review', title: '待审核', color: 'var(--accent-amber)' },
    { key: 'done', title: '已完成', color: 'var(--accent-green)' },
    { key: 'blocked', title: '阻塞', color: 'var(--accent-red)' },
  ];

  const avatarColors = ['#3B82F6', '#8B5CF6', '#EC4899', '#F59E0B', '#10B981', '#06B6D4'];

  const renderKanbanCard = (card) => {
    const pConfig = priorityMap[card.priority] || priorityMap.low;
    const avatarColor = avatarColors[card.assignee.charCodeAt(0) % avatarColors.length];

    return (
      <div key={card.id} className="kanban-card" onClick={() => actions.openForm(card.title, ['处理动作', '负责人', '截止时间', '备注'], card)}>
        {/* Title */}
        <div className="kanban-card-title">{card.title}</div>

        {/* Project Tag */}
        <div className="flex items-center gap-2 mb-3">
          <span className="tag" style={{ padding: '1px 6px', fontSize: 'var(--text-xs)' }}>
            {card.project}
          </span>
        </div>

        {/* Footer: Assignee + Deadline + Priority + Deps */}
        <div className="kanban-card-footer">
          <div className="flex items-center gap-2">
            {/* Avatar */}
            <div
              className="flex items-center justify-center flex-shrink-0"
              style={{
                width: 22,
                height: 22,
                borderRadius: '50%',
                backgroundColor: avatarColor,
                color: '#ffffff',
                fontSize: '10px',
                fontWeight: 600,
              }}
            >
              {card.assignee.charAt(0)}
            </div>
            <span className="text-xs text-muted font-mono">{card.deadline.slice(5)}</span>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={pConfig.variant}>{pConfig.label}</Badge>
            {card.deps > 0 && (
              <span className="flex items-center gap-1 text-xs text-muted">
                <Link2 size={10} />
                {card.deps}
              </span>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex gap-4" style={{ overflowX: 'auto', paddingBottom: 'var(--space-4)' }}>
      {columns.map((col) => {
        const cards = workspace.tasks.length
          ? workspace.tasks.filter((task) => task.status === col.key).map((task) => ({
            ...task,
            id: task.task_id,
            title: task.title,
            project: workspace.currentProject?.project_name || '当前项目',
            assignee: task.owner || '未分配',
            deadline: task.due_at || '待定',
            priority: task.priority || 'medium',
            deps: task.source_handoff_id ? 1 : 0,
          }))
          : (kanbanData[col.key === 'doing' ? 'in_progress' : col.key] || []);
        return (
          <div key={col.key} className="kanban-column">
            <div className="kanban-column-header">
              <div className="kanban-column-title">
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    backgroundColor: col.color,
                    flexShrink: 0,
                  }}
                />
                <span>{col.title}</span>
              </div>
              <span className="kanban-column-count">{cards.length}</span>
            </div>
            <div className="kanban-column-body">
              {cards.map(renderKanbanCard)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ============================================================
   Tab 5: Daily Push
   ============================================================ */
function TabDaily({ actions, workspace }) {
  const [pushConfig, setPushConfig] = useState({
    time: '09:00',
    hotTopics: true,
    progress: true,
    alerts: true,
    todo: false,
    channel: '飞书群',
  });

  const toggleConfig = (key) => {
    setPushConfig((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const pushColumns = [
    { key: 'date', label: '日期', render: (val) => <span className="font-mono text-primary">{val}</span> },
    { key: 'time', label: '推送时间', render: (val) => <span className="font-mono">{val}</span> },
    { key: 'content', label: '推送内容' },
    { key: 'status', label: '状态', render: () => <Badge variant="green">已发送</Badge> },
    { key: 'readRate', label: '阅读率', render: (val) => <span className="font-mono text-green">{val}</span> },
  ];

  return (
    <div className="flex flex-col gap-6">
      {/* Push Configuration */}
      <div className="card">
        <div className="card-header">
          <h3>推送配置</h3>
          <button className="btn btn-primary btn-sm" onClick={() => actions.notify('Daily Push 配置已保存')}>
            <Save size={14} />
            保存配置
          </button>
        </div>
        <div className="card-body">
          <div className="grid grid-cols-3 gap-6">
            {/* Push Time */}
            <div>
              <div className="text-xs text-muted mb-2 font-medium uppercase tracking-wide">推送时间</div>
              <div className="flex items-center gap-2">
                <Clock size={14} style={{ color: 'var(--text-muted)' }} />
                <span className="text-sm font-mono text-primary">每日 {pushConfig.time}</span>
              </div>
            </div>

            {/* Push Content */}
            <div>
              <div className="text-xs text-muted mb-2 font-medium uppercase tracking-wide">推送内容</div>
              <div className="flex flex-col gap-2">
                {[
                  { key: 'hotTopics', label: '行业 Top 5 热点' },
                  { key: 'progress', label: '项目执行进度' },
                  { key: 'alerts', label: '异常预警' },
                  { key: 'todo', label: '待办提醒' },
                ].map((item) => (
                  <label
                    key={item.key}
                    className="flex items-center gap-2 cursor-pointer"
                    onClick={() => {
                      toggleConfig(item.key);
                      actions.notify(`${item.label}已切换`);
                    }}
                  >
                    <div
                      style={{
                        width: 16,
                        height: 16,
                        borderRadius: 'var(--radius-sm)',
                        border: `1px solid ${pushConfig[item.key] ? 'var(--accent-blue)' : 'var(--border-primary)'}`,
                        backgroundColor: pushConfig[item.key] ? 'var(--accent-blue)' : 'transparent',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        transition: 'var(--transition-fast)',
                      }}
                    >
                      {pushConfig[item.key] && (
                        <CheckCircle2 size={12} style={{ color: '#ffffff' }} />
                      )}
                    </div>
                    <span className="text-sm text-secondary">{item.label}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Push Channel */}
            <div>
              <div className="text-xs text-muted mb-2 font-medium uppercase tracking-wide">推送渠道</div>
              <div className="flex items-center gap-2">
                <Send size={14} style={{ color: 'var(--accent-blue)' }} />
                <span className="text-sm text-primary">{pushConfig.channel}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Today's Push Preview */}
      <div className="card">
        <div className="card-header">
          <h3>今日推送预览</h3>
          <span className="text-xs font-mono text-muted">2026-04-13</span>
        </div>
        <div className="card-body">
          <div className="grid gap-6" style={{ gridTemplateColumns: '1fr 1fr 1fr' }}>
            {/* Hot Topics */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Zap size={14} style={{ color: 'var(--accent-amber)' }} />
                <span className="text-sm font-semibold text-primary">行业热点 Top 5</span>
              </div>
              <div className="flex flex-col gap-2">
                {dailyPushPreview.hotTopics.map((topic) => (
                  <div key={topic.rank} className="flex items-start gap-2">
                    <span
                      className="flex-shrink-0 flex items-center justify-center font-mono font-bold text-xs"
                      style={{
                        width: 18,
                        height: 18,
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: topic.rank <= 3 ? 'var(--accent-amber-subtle)' : 'var(--bg-elevated)',
                        color: topic.rank <= 3 ? 'var(--accent-amber)' : 'var(--text-muted)',
                        fontSize: '10px',
                      }}
                    >
                      {topic.rank}
                    </span>
                    <span className="text-xs text-secondary" style={{ lineHeight: 'var(--leading-relaxed)' }}>
                      {topic.text}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Project Progress */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Activity size={14} style={{ color: 'var(--accent-blue)' }} />
                <span className="text-sm font-semibold text-primary">项目进度摘要</span>
              </div>
              <div className="flex flex-col gap-4">
                {dailyPushPreview.projectProgress.map((proj) => (
                  <div key={proj.name}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-secondary">{proj.name}</span>
                      <span className="text-xs font-mono font-semibold text-primary">{proj.progress}%</span>
                    </div>
                    <ProgressBar value={proj.progress} color={proj.color} size="sm" />
                  </div>
                ))}
                {workspace.tasks.length > 0 && (
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-secondary">{workspace.currentProject?.project_name || '当前项目'}</span>
                      <span className="text-xs font-mono font-semibold text-primary">{workspace.metrics?.summary?.execution_score || 0}%</span>
                    </div>
                    <ProgressBar value={workspace.metrics?.summary?.execution_score || 0} color="cyan" size="sm" />
                  </div>
                )}
              </div>
            </div>

            {/* Alerts */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle size={14} style={{ color: 'var(--accent-red)' }} />
                <span className="text-sm font-semibold text-primary">异常预警</span>
              </div>
              <div className="flex flex-col gap-3">
                {dailyPushPreview.alerts.map((alert) => (
                  <div
                    key={alert.id}
                    className="flex items-start gap-2 p-3 rounded"
                    style={{
                      backgroundColor: 'var(--accent-red-subtle)',
                      border: '1px solid rgba(239, 68, 68, 0.2)',
                    }}
                  >
                    <AlertTriangle size={12} style={{ color: 'var(--accent-red)', flexShrink: 0, marginTop: 2 }} />
                    <span className="text-xs text-red">{alert.text}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Push History */}
      <div>
        <div className="section-title">历史推送记录（最近 7 天）</div>
        <DataTable columns={pushColumns} data={pushHistory} onRowClick={(row) => actions.openDetail(`${row.date} 推送记录`, row)} />
      </div>
    </div>
  );
}

/* ============================================================
   Tab 6: 执行跟进
   ============================================================ */
function TabFollowup({ actions }) {
  const followupColumns = [
    { key: 'item', label: '跟进事项', render: (val) => <span className="font-medium text-primary">{val}</span> },
    { key: 'type', label: '类型', render: (val) => renderBadge(followupTypeMap, val) },
    { key: 'project', label: '项目', render: (val) => <Badge variant="neutral">{val}</Badge> },
    { key: 'person', label: '相关人' },
    { key: 'status', label: '状态', render: (val) => renderBadge(followupStatusMap, val) },
    {
      key: 'action',
      label: '操作',
      render: (val, row) => {
        const isUrgent = row.status === 'urgent' || row.status === 'overdue';
        return (
          <button
            className={`btn btn-sm ${isUrgent ? 'btn-danger' : 'btn-secondary'}`}
            onClick={(event) => {
              event.stopPropagation();
              actions.openForm(row.item, ['跟进动作', '通知对象', '催办时间', '备注'], row);
            }}
          >
            {val}
          </button>
        );
      },
    },
  ];

  const reminderStats = [
    { label: '待催办', count: 5, color: 'var(--accent-amber)' },
    { label: '已催办', count: 3, color: 'var(--accent-blue)' },
    { label: '已响应', count: 8, color: 'var(--accent-green)' },
    { label: '超时未响应', count: 2, color: 'var(--accent-red)' },
  ];

  return (
    <div className="flex flex-col gap-6">
      {/* Top StatCards */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard
          title="达人待对接"
          value="15"
          change={2}
          changeLabel="本周新增"
          icon={Users}
          color="pink"
        />
        <StatCard
          title="素材待回收"
          value="8"
          change={-1}
          changeLabel="vs 昨日"
          icon={Image}
          color="amber"
        />
        <StatCard
          title="异常节点"
          value="3"
          change={0}
          changeLabel="需立即处理"
          icon={AlertTriangle}
          color="red"
        />
      </div>

      {/* Followup List + Reminder Panel */}
      <div className="grid gap-4" style={{ gridTemplateColumns: '1fr 280px' }}>
        {/* Followup Items Table */}
        <div className="card">
          <div className="card-header">
            <h3>跟进事项列表</h3>
            <span className="text-xs font-mono text-muted">共 10 条</span>
          </div>
        <DataTable columns={followupColumns} data={followupItems} onRowClick={(row) => actions.openForm(row.item, ['跟进动作', '通知对象', '催办时间', '备注'], row)} />
        </div>

        {/* Reminder Status Panel */}
        <div className="card">
          <div className="card-header">
            <h3>催办状态</h3>
          </div>
          <div className="card-body">
            <div className="flex flex-col gap-4">
              {reminderStats.map((stat) => (
                <div key={stat.label}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-secondary">{stat.label}</span>
                    <span
                      className="text-sm font-mono font-bold"
                      style={{ color: stat.color }}
                    >
                      {stat.count} 条
                    </span>
                  </div>
                  <div
                    style={{
                      width: '100%',
                      height: 6,
                      backgroundColor: 'var(--bg-elevated)',
                      borderRadius: 'var(--radius-full)',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        width: `${(stat.count / 18) * 100}%`,
                        height: '100%',
                        backgroundColor: stat.color,
                        borderRadius: 'var(--radius-full)',
                        transition: 'width 0.4s ease',
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>

            {/* Summary */}
            <div
              className="mt-5 pt-4 flex items-center justify-between"
              style={{ borderTop: '1px solid var(--border-subtle)' }}
            >
              <span className="text-xs text-muted">总计</span>
              <span className="text-sm font-mono font-bold text-primary">18 条</span>
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
export default function ExecutorDashboard({ selectedProjectId, onSelectedProjectIdChange }) {
  const navigate = useNavigate();
  const { tab } = useParams();
  const navToTab = { gateway: 'requirement', 'agent-orch': 'agent', tasks: 'kanban', 'daily-push': 'daily', 'follow-up': 'followup' };
  const tabToNav = { requirement: 'gateway', agent: 'agent-orch', kanban: 'tasks', daily: 'daily-push', followup: 'follow-up' };
  const initialTab = navToTab[tab] || (tabs.some((item) => item.key === tab) ? tab : 'overview');
  const [activeTab, setActiveTab] = useState(initialTab);
  const actions = useWorkbenchActions();
  const workspace = useProjectWorkspace(selectedProjectId, onSelectedProjectIdChange);

  useEffect(() => {
    const nextTab = navToTab[tab] || tab;
    if (tabs.some((item) => item.key === nextTab)) {
      setActiveTab(nextTab);
    }
  }, [tab]);

  const handleTabChange = (nextTab) => {
    setActiveTab(nextTab);
    navigate(`/workbench/executor/${tabToNav[nextTab] || nextTab}`);
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview': return <TabOverview actions={actions} workspace={workspace} />;
      case 'requirement': return <TabRequirement actions={actions} workspace={workspace} />;
      case 'agent': return <TabAgent actions={actions} />;
      case 'kanban': return <TabKanban actions={actions} workspace={workspace} />;
      case 'daily': return <TabDaily actions={actions} workspace={workspace} />;
      case 'followup': return <TabFollowup actions={actions} />;
      default: return <TabOverview actions={actions} workspace={workspace} />;
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="page-body">
        {renderTabContent()}
      </div>
      {actions.toastNode}
      {actions.modalNode}
    </div>
  );
}
