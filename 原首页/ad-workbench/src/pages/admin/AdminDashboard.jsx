import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Users, FolderOpen, Bot, Cpu, Shield, LayoutDashboard,
  UserPlus, Search, Edit3, ChevronLeft, ChevronRight,
  Filter, Calendar, Clock, Activity, Database, HardDrive,
  Globe, Lock, Eye, AlertTriangle, Settings, Zap,
  UserCheck, UserX, BarChart3, FileText, RefreshCw
} from 'lucide-react';
import StatCard from '../../components/StatCard';
import DataTable from '../../components/DataTable';
import Badge from '../../components/Badge';
import ProgressBar from '../../components/ProgressBar';
import TabBar from '../../components/TabBar';
import PageHeader from '../../components/PageHeader';
import AgentCard from '../../components/AgentCard';

/* ============================================================
   Mock Data
   ============================================================ */

const tabs = [
  { key: 'overview', label: '系统概览', icon: <LayoutDashboard size={14} /> },
  { key: 'accounts', label: '账号管理', icon: <Users size={14} /> },
  { key: 'permissions', label: '权限配置', icon: <Shield size={14} /> },
  { key: 'agents', label: 'Agent 编排', icon: <Bot size={14} /> },
  { key: 'audit', label: '审计日志', icon: <FileText size={14} /> },
];

// Tab 1 - 系统概览：系统事件数据
const systemEventsData = [
  { id: 1, time: '2026-04-13 14:32:05', event: 'Agent 调度异常', level: 'error', source: 'Budget Agent', detail: 'API 连接超时，已自动重试 3 次' },
  { id: 2, time: '2026-04-13 14:15:22', event: '新用户注册', level: 'info', source: '用户系统', detail: '用户 zhangwei@example.com 完成注册' },
  { id: 3, time: '2026-04-13 13:58:10', event: '数据库备份完成', level: 'success', source: '运维系统', detail: '全量备份 2.3GB，耗时 4 分 12 秒' },
  { id: 4, time: '2026-04-13 13:42:33', event: '权限变更', level: 'warning', source: '权限系统', detail: '管理员将 user_0892 角色从普通用户提升为管理员' },
  { id: 5, time: '2026-04-13 12:30:00', event: '定时任务执行', level: 'success', source: 'Report Agent', detail: '日报生成任务完成，共生成 8 份报告' },
  { id: 6, time: '2026-04-13 11:20:45', event: '系统配置更新', level: 'info', source: '配置中心', detail: 'API 限流阈值从 1000/s 调整为 1500/s' },
  { id: 7, time: '2026-04-13 10:05:18', event: '磁盘空间预警', level: 'warning', source: '运维系统', detail: '/data 分区使用率达到 85%，建议清理' },
  { id: 8, time: '2026-04-13 09:00:00', event: '系统健康检查', level: 'success', source: '监控系统', detail: '所有核心服务运行正常，响应时间 < 200ms' },
];

// Tab 2 - 账号管理：账号列表数据
const accountData = [
  { id: 1, name: '张明', avatar: 'ZM', email: 'zhangming@ad.com', role: '策划', systemRole: '超级管理员', dataScope: '全部项目', lastLogin: '2026-04-13 14:20', status: 'active' },
  { id: 2, name: '李华', avatar: 'LH', email: 'lihua@ad.com', role: '执行', systemRole: '管理员', dataScope: '指定项目组', lastLogin: '2026-04-13 13:45', status: 'active' },
  { id: 3, name: '王芳', avatar: 'WF', email: 'wangfang@ad.com', role: '媒介', systemRole: '普通用户', dataScope: '仅自己负责', lastLogin: '2026-04-13 12:30', status: 'active' },
  { id: 4, name: '赵磊', avatar: 'ZL', email: 'zhaolei@ad.com', role: '管理层', systemRole: '管理员', dataScope: '全部项目', lastLogin: '2026-04-13 11:50', status: 'active' },
  { id: 5, name: '陈静', avatar: 'CJ', email: 'chenjing@ad.com', role: '策划', systemRole: '普通用户', dataScope: '指定项目组', lastLogin: '2026-04-12 18:20', status: 'active' },
  { id: 6, name: '刘洋', avatar: 'LY', email: 'liuyang@ad.com', role: '执行', systemRole: '普通用户', dataScope: '仅自己负责', lastLogin: '2026-04-12 17:00', status: 'active' },
  { id: 7, name: '周强', avatar: 'ZQ', email: 'zhouqiang@ad.com', role: '媒介', systemRole: '管理员', dataScope: '全部项目', lastLogin: '2026-04-12 16:30', status: 'active' },
  { id: 8, name: '吴敏', avatar: 'WM', email: 'wumin@ad.com', role: '策划', systemRole: '普通用户', dataScope: '指定项目组', lastLogin: '2026-04-11 14:00', status: 'disabled' },
  { id: 9, name: '孙伟', avatar: 'SW', email: 'sunwei@ad.com', role: '执行', systemRole: '普通用户', dataScope: '仅自己负责', lastLogin: '2026-04-10 09:30', status: 'disabled' },
  { id: 10, name: '郑丽', avatar: 'ZL', email: 'zhengli@ad.com', role: '管理层', systemRole: '超级管理员', dataScope: '全部项目', lastLogin: '2026-04-13 14:00', status: 'active' },
];

// Tab 2 - 账号统计
const accountStatsByRole = [
  { label: '策划', count: 8, color: 'var(--accent-purple)' },
  { label: '执行', count: 12, color: 'var(--accent-cyan)' },
  { label: '媒介', count: 15, color: 'var(--accent-green)' },
  { label: '管理层', count: 5, color: 'var(--accent-amber)' },
  { label: '管理员', count: 3, color: 'var(--accent-red)' },
];

const accountStatsByStatus = [
  { label: '活跃', count: 42, color: 'var(--accent-green)' },
  { label: '禁用', count: 6, color: 'var(--accent-red)' },
];

// Tab 3 - 权限配置数据
const systemRoles = [
  { id: 1, name: '超级管理员', description: '拥有系统全部权限，可管理所有模块、用户和配置', permissionCount: 128, color: 'red' },
  { id: 2, name: '管理员', description: '可管理用户、查看报表、配置业务规则，无法修改系统配置', permissionCount: 86, color: 'amber' },
  { id: 3, name: '普通用户', description: '仅可访问被授权的业务模块和数据', permissionCount: 32, color: 'blue' },
];

const businessRoles = [
  { id: 1, name: '策划', description: '负责策略制定、创意策划、Brief 输出', modules: ['项目管理', '创意工单', 'Brief 管理', '洞察报告', '知识库'] },
  { id: 2, name: '执行', description: '负责项目执行、任务跟进、交付管理', modules: ['项目管理', '任务中心', '素材管理', '交付验收', '日程管理'] },
  { id: 3, name: '媒介', description: '负责媒介投放、数据监控、KOL 管理', modules: ['媒介投放', '数据看板', 'KOL 管理', '预算管理', '效果报告'] },
  { id: 4, name: '管理层', description: '负责全局监控、审批决策、资源调配', modules: ['经营总览', 'KPI 监控', '风险中心', '审批中心', '资源管理'] },
];

const dataScopes = [
  { id: 1, name: '全部项目', description: '可查看和操作系统中所有项目的数据', applicableRoles: ['超级管理员', '管理层'] },
  { id: 2, name: '指定项目组', description: '仅可查看和操作被分配的项目组数据', applicableRoles: ['管理员', '策划组长', '媒介组长'] },
  { id: 3, name: '仅自己负责', description: '仅可查看和操作自己负责的项目和任务', applicableRoles: ['普通用户', '执行', '策划', '媒介'] },
];

// Tab 4 - Agent 执行日志数据
const agentLogData = [
  { id: 1, time: '2026-04-13 14:30:00', agent: 'Insight Node', action: '舆情数据抓取', duration: '2m 15s', status: 'success', output: '抓取 1,234 条舆情数据' },
  { id: 2, time: '2026-04-13 14:25:00', agent: 'Brief Parser', action: 'Brief 解析', duration: '45s', status: 'success', output: '解析完成，生成 3 个创意方向' },
  { id: 3, time: '2026-04-13 14:20:00', agent: 'Schedule Agent', action: '排期生成', duration: '1m 30s', status: 'success', output: '生成 5 月排期表，共 28 个任务' },
  { id: 4, time: '2026-04-13 14:10:00', agent: 'Budget Agent', action: '预算同步', duration: '30s', status: 'error', output: 'API 连接超时，同步失败' },
  { id: 5, time: '2026-04-13 14:00:00', agent: 'Sync Agent', action: '飞书数据同步', duration: '3m 05s', status: 'success', output: '同步 156 条任务数据' },
  { id: 6, time: '2026-04-13 13:50:00', agent: 'Report Agent', action: '日报生成', duration: '5m 20s', status: 'success', output: '生成 8 份项目日报' },
  { id: 7, time: '2026-04-13 13:40:00', agent: 'Insight Node', action: '竞品监控', duration: '1m 45s', status: 'success', output: '发现 3 条竞品动态' },
  { id: 8, time: '2026-04-13 13:30:00', agent: 'Brief Parser', action: 'Brief 归档', duration: '20s', status: 'success', output: '归档 5 份已完结 Brief' },
  { id: 9, time: '2026-04-13 13:20:00', agent: 'Budget Agent', action: '预算预警检查', duration: '15s', status: 'error', output: 'API 连接超时' },
  { id: 10, time: '2026-04-13 13:00:00', agent: 'Sync Agent', action: '客户数据同步', duration: '2m 10s', status: 'success', output: '同步 89 条客户信息' },
];

// Tab 5 - 审计日志数据
const auditLogData = [
  { id: 1, time: '2026-04-13 14:32:05', operator: '张明', action: '登录', module: '认证系统', target: '管理员账号', detail: 'IP: 192.168.1.100', ip: '192.168.1.100' },
  { id: 2, time: '2026-04-13 14:20:00', operator: '张明', action: '修改', module: '权限系统', target: '用户 user_0892', detail: '角色从普通用户提升为管理员', ip: '192.168.1.100' },
  { id: 3, time: '2026-04-13 13:58:10', operator: '系统', action: '备份', module: '运维系统', target: '全量数据库', detail: '备份大小 2.3GB', ip: '127.0.0.1' },
  { id: 4, time: '2026-04-13 13:42:33', operator: '郑丽', action: '创建', module: '项目系统', target: 'Q3 品牌传播方案', detail: '新建项目，预算 ¥600K', ip: '192.168.1.105' },
  { id: 5, time: '2026-04-13 12:30:00', operator: '系统', action: '执行', module: 'Agent 系统', target: 'Report Agent', detail: '定时日报生成任务', ip: '127.0.0.1' },
  { id: 6, time: '2026-04-13 11:20:45', operator: '张明', action: '配置', module: '配置中心', target: 'API 限流阈值', detail: '从 1000/s 调整为 1500/s', ip: '192.168.1.100' },
  { id: 7, time: '2026-04-13 10:30:00', operator: '李华', action: '删除', module: '素材系统', target: '过期素材 23 份', detail: '清理 30 天前过期素材', ip: '192.168.1.102' },
  { id: 8, time: '2026-04-13 10:05:18', operator: '系统', action: '预警', module: '运维系统', target: '/data 分区', detail: '磁盘使用率 85%', ip: '127.0.0.1' },
  { id: 9, time: '2026-04-13 09:45:00', operator: '赵磊', action: '审批', module: '审批中心', target: '预算申请 #20260413-003', detail: '审批通过，金额 ¥120K', ip: '192.168.1.108' },
  { id: 10, time: '2026-04-13 09:30:00', operator: '周强', action: '修改', module: '媒介投放', target: '花西子 618 投放计划', detail: '调整投放预算分配', ip: '192.168.1.110' },
  { id: 11, time: '2026-04-12 18:20:00', operator: '陈静', action: '创建', module: 'Brief 系统', target: 'Brief #B20260412-008', detail: '新建 Brief：花西子社媒传播', ip: '192.168.1.115' },
  { id: 12, time: '2026-04-12 17:00:00', operator: '刘洋', action: '更新', module: '任务系统', target: '任务 #T20260412-015', detail: '更新任务状态为已完成', ip: '192.168.1.120' },
  { id: 13, time: '2026-04-12 16:30:00', operator: '系统', action: '同步', module: 'Agent 系统', target: 'Sync Agent', detail: '飞书数据同步完成', ip: '127.0.0.1' },
  { id: 14, time: '2026-04-12 15:00:00', operator: '张明', action: '禁用', module: '用户系统', target: '用户 sunwei@ad.com', detail: '账号因长期未登录被禁用', ip: '192.168.1.100' },
  { id: 15, time: '2026-04-12 14:00:00', operator: '郑丽', action: '导出', module: '报表系统', target: 'Q1 经营数据报表', detail: '导出 Excel，共 1,250 行数据', ip: '192.168.1.105' },
];

/* ============================================================
   Helper Functions
   ============================================================ */

const eventLevelBadgeMap = {
  error: 'red',
  warning: 'amber',
  success: 'green',
  info: 'blue',
};

const roleBadgeMap = {
  '策划': 'purple',
  '执行': 'cyan',
  '媒介': 'green',
  '管理层': 'amber',
};

const systemRoleBadgeMap = {
  '超级管理员': 'red',
  '管理员': 'amber',
  '普通用户': 'blue',
};

const statusBadgeMap = {
  active: 'green',
  disabled: 'red',
};

const auditActionBadgeMap = {
  '登录': 'blue',
  '修改': 'amber',
  '备份': 'cyan',
  '创建': 'green',
  '执行': 'purple',
  '配置': 'amber',
  '删除': 'red',
  '预警': 'red',
  '审批': 'green',
  '更新': 'cyan',
  '同步': 'blue',
  '禁用': 'red',
  '导出': 'purple',
};

const agentStatusBadgeMap = {
  success: 'green',
  error: 'red',
  running: 'cyan',
};

/* ============================================================
   Tab 1: 系统概览
   ============================================================ */
function TabOverview() {
  const eventColumns = [
    { key: 'time', label: '时间', render: (val) => <span className="font-mono text-xs text-muted">{val}</span> },
    { key: 'event', label: '事件', render: (val) => <span className="text-sm font-medium text-primary">{val}</span> },
    {
      key: 'level', label: '级别',
      render: (val) => {
        const labelMap = { error: '错误', warning: '警告', success: '成功', info: '信息' };
        return <Badge variant={eventLevelBadgeMap[val] || 'neutral'}>{labelMap[val] || val}</Badge>;
      },
    },
    { key: 'source', label: '来源', render: (val) => <span className="text-sm text-secondary">{val}</span> },
    { key: 'detail', label: '详情', render: (val) => <span className="text-sm text-muted">{val}</span> },
  ];

  return (
    <div className="flex flex-col gap-6">
      {/* 顶部 4 个 StatCard */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          title="注册用户"
          value="48"
          change={5}
          changeLabel="本月"
          icon={Users}
          color="blue"
        />
        <StatCard
          title="活跃项目"
          value="20"
          icon={FolderOpen}
          color="green"
        />
        <StatCard
          title="Agent 运行"
          value="12/18"
          subtitle="运行中 / 总数"
          icon={Bot}
          color="cyan"
        />
        <StatCard
          title="系统负载"
          value="67%"
          icon={Cpu}
          color="amber"
        />
      </div>

      {/* 系统资源监控 */}
      <div className="grid grid-cols-2 gap-4">
        <div className="card">
          <div className="card-header">
            <div className="flex items-center gap-2">
              <Cpu size={16} className="text-secondary" />
              <h3>CPU 使用率</h3>
            </div>
          </div>
          <div className="card-body">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-secondary">当前使用</span>
              <span className="font-mono text-sm font-semibold text-primary">67%</span>
            </div>
            <ProgressBar value={67} color="amber" size="md" showLabel={false} />
          </div>
        </div>
        <div className="card">
          <div className="card-header">
            <div className="flex items-center gap-2">
              <Database size={16} className="text-secondary" />
              <h3>内存使用</h3>
            </div>
          </div>
          <div className="card-body">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-secondary">12.8GB / 16GB</span>
              <span className="font-mono text-sm font-semibold text-primary">80%</span>
            </div>
            <ProgressBar value={80} color="cyan" size="md" showLabel={false} />
          </div>
        </div>
        <div className="card">
          <div className="card-header">
            <div className="flex items-center gap-2">
              <HardDrive size={16} className="text-secondary" />
              <h3>磁盘使用</h3>
            </div>
          </div>
          <div className="card-body">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-secondary">234GB / 500GB</span>
              <span className="font-mono text-sm font-semibold text-primary">46.8%</span>
            </div>
            <ProgressBar value={46.8} color="green" size="md" showLabel={false} />
          </div>
        </div>
        <div className="card">
          <div className="card-header">
            <div className="flex items-center gap-2">
              <Activity size={16} className="text-secondary" />
              <h3>API 调用</h3>
            </div>
          </div>
          <div className="card-body">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-secondary">1.2M / 2M 本月</span>
              <span className="font-mono text-sm font-semibold text-primary">60%</span>
            </div>
            <ProgressBar value={60} color="blue" size="md" showLabel={false} />
          </div>
        </div>
      </div>

      {/* 最近系统事件 */}
      <div>
        <div className="section-title">最近系统事件</div>
        <DataTable columns={eventColumns} data={systemEventsData} />
      </div>
    </div>
  );
}

/* ============================================================
   Tab 2: 账号管理
   ============================================================ */
function TabAccounts() {
  const [searchText, setSearchText] = useState('');

  const filteredAccounts = accountData.filter((acc) =>
    acc.name.includes(searchText) || acc.email.includes(searchText)
  );

  const accountColumns = [
    {
      key: 'name', label: '姓名',
      render: (val, row) => (
        <div className="flex items-center gap-2">
          <div
            className="flex items-center justify-center"
            style={{
              width: 32,
              height: 32,
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'var(--accent-blue-subtle)',
              color: 'var(--accent-blue)',
              fontSize: 12,
              fontWeight: 600,
              flexShrink: 0,
            }}
          >
            {row.avatar}
          </div>
          <span className="text-sm font-medium text-primary">{val}</span>
        </div>
      ),
    },
    { key: 'email', label: '邮箱', render: (val) => <span className="text-sm text-muted">{val}</span> },
    {
      key: 'role', label: '业务岗位',
      render: (val) => <Badge variant={roleBadgeMap[val] || 'neutral'}>{val}</Badge>,
    },
    {
      key: 'systemRole', label: '系统角色',
      render: (val) => <Badge variant={systemRoleBadgeMap[val] || 'neutral'}>{val}</Badge>,
    },
    { key: 'dataScope', label: '数据范围', render: (val) => <span className="text-sm text-secondary">{val}</span> },
    { key: 'lastLogin', label: '最后登录', render: (val) => <span className="font-mono text-xs text-muted">{val}</span> },
    {
      key: 'status', label: '状态',
      render: (val) => <Badge variant={statusBadgeMap[val] || 'neutral'}>{val === 'active' ? '活跃' : '禁用'}</Badge>,
    },
    {
      key: 'actions', label: '操作',
      render: (_, row) => (
        <div className="flex items-center gap-2">
          <button className="btn btn-sm btn-secondary" title="编辑">
            <Edit3 size={14} />
          </button>
          <button
            className="btn btn-sm btn-secondary"
            title={row.status === 'active' ? '禁用' : '启用'}
          >
            {row.status === 'active' ? <UserX size={14} /> : <UserCheck size={14} />}
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      {/* 顶部操作栏 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button className="btn btn-primary">
            <UserPlus size={14} />
            <span>新建账号</span>
          </button>
        </div>
        <div className="flex items-center gap-2" style={{ position: 'relative', width: 280 }}>
          <Search size={14} style={{ position: 'absolute', left: 10, color: 'var(--text-muted)' }} />
          <input
            type="text"
            className="input"
            placeholder="搜索姓名或邮箱..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ paddingLeft: 32, width: '100%' }}
          />
        </div>
      </div>

      {/* 主内容区：表格 + 右侧统计 */}
      <div className="flex gap-4" style={{ alignItems: 'flex-start' }}>
        {/* 账号列表 */}
        <div className="flex-1">
          <DataTable columns={accountColumns} data={filteredAccounts} />
        </div>

        {/* 右侧浮动面板：账号统计 */}
        <div style={{ width: 260, flexShrink: 0 }}>
          <div className="card">
            <div className="card-header">
              <h3>账号统计</h3>
            </div>
            <div className="card-body">
              {/* 按岗位分布 */}
              <div className="mb-5">
                <div className="text-xs text-muted font-medium uppercase tracking-wide mb-3">按岗位分布</div>
                <div className="flex flex-col gap-3">
                  {accountStatsByRole.map((item) => (
                    <div key={item.label}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm text-secondary">{item.label}</span>
                        <span className="font-mono text-sm font-semibold text-primary">{item.count}</span>
                      </div>
                      <div
                        style={{
                          width: '100%',
                          height: 6,
                          borderRadius: 'var(--radius-sm)',
                          backgroundColor: 'var(--bg-elevated)',
                          overflow: 'hidden',
                        }}
                      >
                        <div
                          style={{
                            width: `${(item.count / 15) * 100}%`,
                            height: '100%',
                            backgroundColor: item.color,
                            borderRadius: 'var(--radius-sm)',
                            transition: 'width 0.3s ease',
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* 按状态分布 */}
              <div>
                <div className="text-xs text-muted font-medium uppercase tracking-wide mb-3">按状态分布</div>
                <div className="flex flex-col gap-3">
                  {accountStatsByStatus.map((item) => (
                    <div key={item.label} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span
                          style={{
                            width: 8,
                            height: 8,
                            borderRadius: '50%',
                            backgroundColor: item.color,
                          }}
                        />
                        <span className="text-sm text-secondary">{item.label}</span>
                      </div>
                      <span className="font-mono text-sm font-semibold text-primary">{item.count}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Tab 3: 权限配置
   ============================================================ */
function TabPermissions() {
  return (
    <div className="flex flex-col gap-6">
      {/* 顶部说明 */}
      <div
        className="card"
        style={{ backgroundColor: 'var(--accent-blue-subtle)', border: '1px solid rgba(59, 130, 246, 0.15)' }}
      >
        <div className="card-body">
          <div className="flex items-center gap-3">
            <Shield size={18} style={{ color: 'var(--accent-blue)' }} />
            <div>
              <div className="text-sm font-semibold text-primary">三层权限模型：系统角色 + 业务岗位 + 数据范围</div>
              <div className="text-xs text-muted mt-1">
                系统角色控制功能访问权限，业务岗位决定可操作模块，数据范围限定可见数据边界。三者组合形成完整的权限控制体系。
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Card 1: 系统角色 */}
      <div className="card">
        <div className="card-header">
          <div className="flex items-center gap-2">
            <Lock size={16} className="text-secondary" />
            <h3>系统角色</h3>
          </div>
        </div>
        <div className="card-body">
          <div className="flex flex-col gap-0">
            {systemRoles.map((role, index) => (
              <div
                key={role.id}
                className="flex items-center gap-4 py-4"
                style={{
                  borderBottom: index < systemRoles.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                }}
              >
                <div
                  className="flex items-center justify-center"
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: `var(--accent-${role.color}-subtle)`,
                    color: `var(--accent-${role.color})`,
                    flexShrink: 0,
                  }}
                >
                  <Shield size={18} />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-primary">{role.name}</span>
                    <Badge variant={role.color}>{role.permissionCount} 项权限</Badge>
                  </div>
                  <div className="text-xs text-muted mt-1">{role.description}</div>
                </div>
                <button className="btn btn-sm btn-secondary">
                  <Edit3 size={14} />
                  <span>编辑</span>
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Card 2: 业务岗位 */}
      <div className="card">
        <div className="card-header">
          <div className="flex items-center gap-2">
            <Users size={16} className="text-secondary" />
            <h3>业务岗位</h3>
          </div>
        </div>
        <div className="card-body">
          <div className="flex flex-col gap-0">
            {businessRoles.map((role, index) => (
              <div
                key={role.id}
                className="py-4"
                style={{
                  borderBottom: index < businessRoles.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                }}
              >
                <div className="flex items-center gap-4 mb-2">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-primary">{role.name}</span>
                    </div>
                    <div className="text-xs text-muted mt-1">{role.description}</div>
                  </div>
                  <button className="btn btn-sm btn-secondary">
                    <Edit3 size={14} />
                    <span>编辑</span>
                  </button>
                </div>
                <div className="flex items-center gap-2 flex-wrap mt-2">
                  {role.modules.map((mod) => (
                    <span
                      key={mod}
                      className="badge badge-neutral"
                      style={{ fontSize: 11 }}
                    >
                      {mod}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Card 3: 数据范围 */}
      <div className="card">
        <div className="card-header">
          <div className="flex items-center gap-2">
            <Eye size={16} className="text-secondary" />
            <h3>数据范围</h3>
          </div>
        </div>
        <div className="card-body">
          <div className="flex flex-col gap-0">
            {dataScopes.map((scope, index) => (
              <div
                key={scope.id}
                className="flex items-center gap-4 py-4"
                style={{
                  borderBottom: index < dataScopes.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                }}
              >
                <div
                  className="flex items-center justify-center"
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--accent-blue-subtle)',
                    color: 'var(--accent-blue)',
                    flexShrink: 0,
                  }}
                >
                  <Globe size={18} />
                </div>
                <div className="flex-1">
                  <div className="text-sm font-semibold text-primary">{scope.name}</div>
                  <div className="text-xs text-muted mt-1">{scope.description}</div>
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-xs text-muted">适用角色：</span>
                    {scope.applicableRoles.map((r) => (
                      <Badge key={r} variant="blue">{r}</Badge>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Tab 4: Agent 编排
   ============================================================ */
function TabAgents() {
  const agentColumns = [
    { key: 'time', label: '时间', render: (val) => <span className="font-mono text-xs text-muted">{val}</span> },
    { key: 'agent', label: 'Agent', render: (val) => <span className="text-sm font-medium text-primary">{val}</span> },
    { key: 'action', label: '动作', render: (val) => <span className="text-sm text-secondary">{val}</span> },
    { key: 'duration', label: '耗时', render: (val) => <span className="font-mono text-xs text-muted">{val}</span> },
    {
      key: 'status', label: '状态',
      render: (val) => {
        const labelMap = { success: '成功', error: '失败', running: '运行中' };
        return <Badge variant={agentStatusBadgeMap[val] || 'neutral'}>{labelMap[val] || val}</Badge>;
      },
    },
    { key: 'output', label: '输出摘要', render: (val) => <span className="text-sm text-muted">{val}</span> },
  ];

  return (
    <div className="flex flex-col gap-6">
      {/* 全局 Agent 状态统计 */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard
          title="运行中"
          value="12"
          icon={Bot}
          color="green"
        />
        <StatCard
          title="空闲"
          value="4"
          icon={Bot}
          color="blue"
        />
        <StatCard
          title="异常"
          value="2"
          icon={Bot}
          color="red"
        />
      </div>

      {/* Agent 列表 (2x3 网格) */}
      <div>
        <div className="section-title">Agent 列表</div>
        <div className="grid grid-cols-3 gap-4">
          <AgentCard
            name="Insight Node"
            type="数据采集"
            status="running"
            description="舆情数据抓取正常"
            lastRun="2026-04-13 14:30"
            output="抓取 1,234 条舆情数据"
          />
          <AgentCard
            name="Brief Parser"
            type="文档解析"
            status="running"
            description="已处理 156 份 Brief"
            lastRun="2026-04-13 14:25"
            output="解析完成，生成 3 个创意方向"
          />
          <AgentCard
            name="Schedule Agent"
            type="排期管理"
            status="running"
            description="排期生成中"
            lastRun="2026-04-13 14:20"
            output="生成 5 月排期表"
          />
          <AgentCard
            name="Report Agent"
            type="报告生成"
            status="idle"
            description="等待下次定时任务"
            lastRun="2026-04-13 13:50"
            output="生成 8 份项目日报"
          />
          <AgentCard
            name="Sync Agent"
            type="数据同步"
            status="running"
            description="飞书同步正常"
            lastRun="2026-04-13 14:00"
            output="同步 156 条任务数据"
          />
          <AgentCard
            name="Budget Agent"
            type="预算管理"
            status="error"
            description="API 连接超时"
            lastRun="2026-04-13 14:10"
            output="同步失败，需人工介入"
          />
        </div>
      </div>

      {/* Agent 执行日志 */}
      <div>
        <div className="section-title">Agent 执行日志</div>
        <DataTable columns={agentColumns} data={agentLogData} />
      </div>
    </div>
  );
}

/* ============================================================
   Tab 5: 审计日志
   ============================================================ */
function TabAudit() {
  const [timeRange, setTimeRange] = useState('today');
  const [actionType, setActionType] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  const filteredLogs = auditLogData.filter((log) => {
    if (actionType !== 'all' && log.action !== actionType) return false;
    return true;
  });

  const totalPages = Math.ceil(filteredLogs.length / pageSize);
  const pagedLogs = filteredLogs.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  const auditColumns = [
    { key: 'time', label: '时间', render: (val) => <span className="font-mono text-xs text-muted">{val}</span> },
    { key: 'operator', label: '操作人', render: (val) => <span className="text-sm font-medium text-primary">{val}</span> },
    {
      key: 'action', label: '操作类型',
      render: (val) => <Badge variant={auditActionBadgeMap[val] || 'neutral'}>{val}</Badge>,
    },
    { key: 'module', label: '模块', render: (val) => <span className="text-sm text-secondary">{val}</span> },
    { key: 'target', label: '操作对象', render: (val) => <span className="text-sm text-secondary">{val}</span> },
    { key: 'detail', label: '详情', render: (val) => <span className="text-sm text-muted">{val}</span> },
    { key: 'ip', label: 'IP', render: (val) => <span className="font-mono text-xs text-muted">{val}</span> },
  ];

  return (
    <div className="flex flex-col gap-6">
      {/* 筛选条件 */}
      <div className="card">
        <div className="card-body">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <Calendar size={14} className="text-muted" />
              <span className="text-sm text-secondary">时间范围：</span>
              <select
                className="input"
                style={{ width: 140 }}
                value={timeRange}
                onChange={(e) => setTimeRange(e.target.value)}
              >
                <option value="today">今天</option>
                <option value="week">最近 7 天</option>
                <option value="month">最近 30 天</option>
                <option value="custom">自定义</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <Filter size={14} className="text-muted" />
              <span className="text-sm text-secondary">操作类型：</span>
              <select
                className="input"
                style={{ width: 120 }}
                value={actionType}
                onChange={(e) => setActionType(e.target.value)}
              >
                <option value="all">全部</option>
                <option value="登录">登录</option>
                <option value="创建">创建</option>
                <option value="修改">修改</option>
                <option value="删除">删除</option>
                <option value="配置">配置</option>
                <option value="审批">审批</option>
                <option value="导出">导出</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <Users size={14} className="text-muted" />
              <span className="text-sm text-secondary">操作人：</span>
              <input
                type="text"
                className="input"
                placeholder="输入操作人..."
                style={{ width: 140 }}
              />
            </div>
            <div className="flex items-center gap-2">
              <Settings size={14} className="text-muted" />
              <span className="text-sm text-secondary">模块：</span>
              <select className="input" style={{ width: 140 }}>
                <option value="all">全部模块</option>
                <option value="auth">认证系统</option>
                <option value="user">用户系统</option>
                <option value="permission">权限系统</option>
                <option value="project">项目系统</option>
                <option value="agent">Agent 系统</option>
                <option value="ops">运维系统</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* 审计日志表格 */}
      <DataTable columns={auditColumns} data={pagedLogs} />

      {/* 分页控件 */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted">
          共 {filteredLogs.length} 条记录，第 {currentPage} / {totalPages} 页
        </div>
        <div className="flex items-center gap-2">
          <button
            className="btn btn-sm btn-secondary"
            disabled={currentPage <= 1}
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
          >
            <ChevronLeft size={14} />
            <span>上一页</span>
          </button>
          <div className="flex items-center gap-1">
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
              <button
                key={page}
                className={`btn btn-sm ${currentPage === page ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setCurrentPage(page)}
                style={{ minWidth: 32 }}
              >
                {page}
              </button>
            ))}
          </div>
          <button
            className="btn btn-sm btn-secondary"
            disabled={currentPage >= totalPages}
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
          >
            <span>下一页</span>
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Main Component
   ============================================================ */
export default function AdminDashboard() {
  const { tab } = useParams();
  const [activeTab, setActiveTab] = useState(tab || 'overview');

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview': return <TabOverview />;
      case 'accounts': return <TabAccounts />;
      case 'permissions': return <TabPermissions />;
      case 'agents': return <TabAgents />;
      case 'audit': return <TabAudit />;
      default: return <TabOverview />;
    }
  };

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="超级管理员工作台"
        subtitle="账号管理 | 权限配置 | Agent 编排 | 审计日志"
        breadcrumbs={[
          { label: '工作台' },
          { label: '超级管理员工作台' },
        ]}
      />
      <TabBar tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />
      <div className="page-body">
        {renderTabContent()}
      </div>
    </div>
  );
}
