import React, { useEffect, useState, lazy, Suspense } from 'react';
import { useParams, useLocation, useNavigate, Link } from 'react-router-dom';
import {
  LayoutDashboard,
  Search,
  FileText,
  Sparkles,
  BarChart3,
  FolderOpen,
  Bot,
  FileBarChart,
  Inbox,
  CheckSquare,
  Send,
  RefreshCw,
  Users,
  ClipboardList,
  Radio,
  DollarSign,
  UserCheck,
  Target,
  AlertTriangle,
  Activity,
  Shield,
  Settings,
  ScrollText,
  Bell,
  Check,
  ChevronDown,
  LogOut,
  ChevronRight,
  Zap,
  Filter,
  FolderPlus,
  ExternalLink,
} from 'lucide-react';

// 角色配置
const roleConfig = {
  planner: { name: '策划', color: '#8B5CF6', icon: Sparkles },
  executor: { name: '执行', color: '#06B6D4', icon: Zap },
  media: { name: '媒介', color: '#EC4899', icon: Radio },
  manager: { name: '管理层', color: '#3B82F6', icon: BarChart3 },
  admin: { name: '超级管理员', color: '#F59E0B', icon: Shield },
  screening: { name: '达人筛选', color: '#10B981', icon: Filter },
};

// 导航配置
const navConfig = {
  planner: [
    { icon: LayoutDashboard, label: '工作概览', path: 'overview' },
    { icon: Search, label: '舆情洞察', path: 'insight' },
    { icon: FileText, label: 'Brief 中心', path: 'brief' },
    { icon: Sparkles, label: '创意策略', path: 'creative' },
    { icon: BarChart3, label: '社媒看板', path: 'social' },
    { divider: true },
    { icon: FolderOpen, label: '项目中心', path: 'projects' },
    { icon: Bot, label: 'Agent 中心', path: 'agents' },
    { icon: FileBarChart, label: '报告中心', path: 'reports' },
  ],
  executor: [
    { icon: LayoutDashboard, label: '工作概览', path: 'overview' },
    { icon: Inbox, label: '需求接入', path: 'gateway' },
    { icon: Bot, label: 'Agent 编排', path: 'agent-orch' },
    { icon: CheckSquare, label: '任务看板', path: 'tasks' },
    { icon: Send, label: 'Daily Push', path: 'daily-push' },
    { icon: RefreshCw, label: '执行跟进', path: 'follow-up' },
    { divider: true },
    { icon: FolderOpen, label: '项目中心', path: 'projects' },
    { icon: FileBarChart, label: '报告中心', path: 'reports' },
  ],
  media: [
    { icon: LayoutDashboard, label: '工作概览', path: 'overview' },
    { icon: Users, label: '达人建联', path: 'influencer' },
    { icon: ClipboardList, label: '项目进度', path: 'progress' },
    { icon: Radio, label: '广告追踪', path: 'ad-tracking' },
    { icon: DollarSign, label: '预算优化', path: 'budget' },
    { divider: true },
    { icon: FolderOpen, label: '项目中心', path: 'projects' },
    { icon: UserCheck, label: '达人资产', path: 'kol-assets' },
    { icon: FileBarChart, label: '报告中心', path: 'reports' },
  ],
  manager: [
    { icon: LayoutDashboard, label: '经营总览', path: 'overview' },
    { icon: Target, label: 'KPI 监控', path: 'kpi' },
    { icon: AlertTriangle, label: '风险分布', path: 'risks' },
    { icon: Activity, label: '项目健康度', path: 'health' },
    { divider: true },
    { icon: FolderOpen, label: '项目中心', path: 'projects' },
    { icon: FileBarChart, label: '报告中心', path: 'reports' },
  ],
  admin: [
    { icon: LayoutDashboard, label: '系统概览', path: 'overview' },
    { icon: Users, label: '账号管理', path: 'accounts' },
    { icon: Shield, label: '权限配置', path: 'permissions' },
    { icon: Bot, label: 'Agent 编排', path: 'agent-config' },
    { icon: Settings, label: '系统配置', path: 'settings' },
    { icon: ScrollText, label: '审计日志', path: 'audit' },
  ],
  screening: [
    { icon: FolderOpen, label: '项目预览', path: 'projects' },
    { icon: LayoutDashboard, label: '采集工作台', path: 'overview' },
    { icon: Users, label: '筛选工作台', path: 'screening-review' },
    { icon: UserCheck, label: '审号工作台', path: 'creator-audit' },
    { icon: BarChart3, label: '项目达人池', path: 'score-preview' },
    { icon: FolderPlus, label: '项目配置', path: 'project-setup' },
    { divider: true },
    { icon: ScrollText, label: '操作日志', path: 'audit-log' },
    { icon: ExternalLink, label: '高级配置（原工作台）', path: 'legacy' },
  ],
};

// Sidebar Header 组件
function SidebarHeader({ role }) {
  const roleInfo = roleConfig[role];

  return (
    <div className="sidebar-header">
      <div className="sidebar-logo-icon">AF</div>
      <div className="sidebar-brand">
        <div className="sidebar-brand-name">AdFlow AI</div>
        <div
          className="sidebar-brand-version"
          style={{ color: roleInfo.color }}
        >
          {roleInfo.name}
        </div>
      </div>
    </div>
  );
}

// Sidebar Nav 组件
function SidebarNav({ role, currentPath }) {
  const navItems = navConfig[role] || [];

  return (
    <nav className="sidebar-nav">
      {navItems.map((item, index) => {
        if (item.divider) {
          return (
            <div
              key={`divider-${index}`}
              style={{
                height: '1px',
                backgroundColor: 'var(--border-subtle)',
                margin: 'var(--space-3) var(--space-2)',
              }}
            />
          );
        }

        const IconComponent = item.icon;
        const isActive = currentPath === item.path;

        return (
          <Link
            key={item.path}
            to={`/workbench/${role}/${item.path}`}
            className={`sidebar-nav-item ${isActive ? 'active' : ''}`}
          >
            <div className="nav-icon">
              <IconComponent size={18} />
            </div>
            <span className="nav-label">{item.label}</span>
            {isActive && <ChevronRight size={14} style={{ opacity: 0.5 }} />}
          </Link>
        );
      })}
    </nav>
  );
}

// Sidebar User 组件
function SidebarUser({ role, onLogout }) {
  const roleInfo = roleConfig[role];

  return (
    <div className="sidebar-user" onClick={onLogout}>
      <div
        className="sidebar-user-avatar"
        style={{ backgroundColor: roleInfo.color }}
      >
        U
      </div>
      <div className="sidebar-user-info">
        <div className="sidebar-user-name">User Name</div>
        <div className="sidebar-user-role">{roleInfo.name}</div>
      </div>
      <div className="sidebar-user-menu">
        <LogOut size={18} />
      </div>
    </div>
  );
}

// Header 组件
function Header({
  role,
  currentPath,
  projects = [],
  selectedProjectId,
  onSelectProject,
}) {
  const roleInfo = roleConfig[role];
  const navItems = navConfig[role] || [];
  const currentPage = navItems.find((item) => item.path === currentPath);
  const [projectMenuOpen, setProjectMenuOpen] = useState(false);
  const selectedProject = projects.find(project => project.project_id === selectedProjectId) || projects[0];

  return (
    <header
      className="page-header"
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 'var(--z-sticky)',
      }}
    >
      {/* 面包屑导航 */}
      {projects.length > 0 ? (
        <div className="breadcrumb project-switcher">
          <span className="breadcrumb-item">当前项目</span>
          <span className="breadcrumb-separator">/</span>
          <button
            type="button"
            className="breadcrumb-item active project-switcher-trigger"
            onClick={() => setProjectMenuOpen((open) => !open)}
          >
            <span>{selectedProject?.project_name || '点击切换项目'}</span>
            <ChevronDown size={14} />
          </button>
          {projectMenuOpen && (
            <div className="project-switcher-menu">
              <div className="project-switcher-title">点击切换项目</div>
              {projects.length > 0 ? (
                projects.map((project) => {
                  const isSelected = project.project_id === selectedProject?.project_id;
                  return (
                    <button
                      type="button"
                      key={project.project_id}
                      className={`project-switcher-option ${isSelected ? 'active' : ''}`}
                      onClick={() => {
                        onSelectProject?.(project.project_id);
                        setProjectMenuOpen(false);
                      }}
                    >
                      <FolderOpen size={15} />
                      <span className="project-switcher-option-main">
                        <span className="project-switcher-option-name">{project.project_name}</span>
                        <span className="project-switcher-option-meta">
                          {project.period_start || '待定'} 至 {project.period_end || '待定'}
                        </span>
                      </span>
                      {isSelected && <Check size={15} />}
                    </button>
                  );
                })
              ) : (
                <div className="project-switcher-empty">暂无项目</div>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="breadcrumb">
          <span className="breadcrumb-item">{roleInfo.name}</span>
          <span className="breadcrumb-separator">/</span>
          <span className="breadcrumb-item active">
            {currentPage?.label || '工作概览'}
          </span>
        </div>
      )}

      {/* 右侧操作区 */}
      <div className="page-header-actions">
        {/* 搜索框 */}
        <div className="search-box">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            className="search-input"
            placeholder="搜索..."
            style={{ width: '240px' }}
          />
        </div>

        {/* 通知铃铛 */}
        <button className="btn btn-icon btn-ghost notification-dot">
          <Bell size={20} />
        </button>

        {/* 用户下拉 */}
        <div className="dropdown">
          <button className="btn btn-icon btn-ghost">
            <div
              className="avatar avatar-sm"
              style={{ backgroundColor: roleInfo.color }}
            >
              U
            </div>
          </button>
        </div>
      </div>
    </header>
  );
}

// Lazy load 各角色面板
const PlannerDashboard = lazy(() => import('./planner/PlannerDashboard'));
const ExecutorDashboard = lazy(() => import('./executor/ExecutorDashboard'));
const MediaDashboard = lazy(() => import('./media/MediaDashboard'));
const ManagerDashboard = lazy(() => import('./manager/ManagerDashboard'));
const AdminDashboard = lazy(() => import('./admin/AdminDashboard'));
const ScreeningDashboard = lazy(() => import('./screening/ScreeningDashboard'));

const roleDashboardMap = {
  planner: PlannerDashboard,
  executor: ExecutorDashboard,
  media: MediaDashboard,
  manager: ManagerDashboard,
  admin: AdminDashboard,
  screening: ScreeningDashboard,
};

// 主布局组件
export default function WorkbenchLayout() {
  const { role } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(() => {
    try {
      return window.localStorage.getItem('adflow-selected-project') || window.localStorage.getItem('adflow-selected-screening-project') || '';
    } catch {
      return '';
    }
  });

  // 获取当前路径的最后一部分作为当前页面
  const currentPath = location.pathname.split('/').pop() || 'overview';

  // 处理退出登录
  const handleLogout = () => {
    navigate('/');
  };

  useEffect(() => {
    let cancelled = false;
    fetch('/api/projects')
      .then((response) => response.json())
      .then((payload) => {
        if (cancelled) return;
        const nextProjects = payload.projects || [];
        setProjects(nextProjects);
        setSelectedProjectId((currentId) => (
          currentId || nextProjects[0]?.project_id || 'youdao_001'
        ));
      })
      .catch(() => {
        if (!cancelled) {
          setProjects([]);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedProjectId) return;
    try {
      window.localStorage.setItem('adflow-selected-project', selectedProjectId);
      window.localStorage.setItem('adflow-selected-screening-project', selectedProjectId);
    } catch {
      // Local storage is optional; the page still works without persistence.
    }
  }, [selectedProjectId]);

  const handleSelectProject = (projectId) => {
    setSelectedProjectId(projectId);
    if (role === 'screening' && currentPath === 'projects') {
      navigate('/workbench/screening/overview');
    }
  };

  // 如果 role 无效，重定向到角色选择页
  if (!role || !roleConfig[role]) {
    navigate('/select-role');
    return null;
  }

  const DashboardComponent = roleDashboardMap[role];

  return (
    <div className="app-layout">
      {/* 左侧 Sidebar */}
      <aside className="sidebar">
        <SidebarHeader role={role} />
        <SidebarNav role={role} currentPath={currentPath} />
        <SidebarUser role={role} onLogout={handleLogout} />
      </aside>

      {/* 右侧主内容区 */}
      <main className="main-content">
        <Header
          role={role}
          currentPath={currentPath}
          projects={projects}
          selectedProjectId={selectedProjectId}
          onSelectProject={handleSelectProject}
        />
        <div className="page-body">
          <Suspense fallback={<div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '400px',
            color: 'var(--text-muted)',
            fontSize: '14px'
          }}>加载面板中...</div>}>
            <DashboardComponent
              key={currentPath}
              selectedProjectId={selectedProjectId}
              onSelectedProjectIdChange={setSelectedProjectId}
            />
          </Suspense>
        </div>
      </main>
    </div>
  );
}
