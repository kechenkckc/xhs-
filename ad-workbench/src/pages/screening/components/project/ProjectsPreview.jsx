import React, { useState } from 'react';
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
import StatCard from '../../../../components/StatCard';
import DataTable from '../../../../components/DataTable';
import Badge from '../../../../components/Badge';
import ProgressBar from '../../../../components/ProgressBar';
import { formatDateTime } from '../../utils/formatters';
import { getProjectStats } from '../../utils/projectMappers';
import { ProjectCard } from './ProjectCard';

export function ProjectsPreview({ projects, onSelectProject, onCreateProject, onArchiveProject, onRestoreProject, onDeleteProject }) {
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
        {onCreateProject && (
          <button className="btn btn-sm btn-primary" onClick={onCreateProject}>
            <Plus size={14} />新建项目
          </button>
        )}
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
