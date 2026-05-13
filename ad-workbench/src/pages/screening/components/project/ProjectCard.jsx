import React from 'react';
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
import { getProjectTaskSummary } from '../../utils/projectMappers';

export function ProjectCard({ project, onClick, onArchive, onRestore, onDelete }) {
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
