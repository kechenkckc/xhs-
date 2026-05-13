import React, { useState } from 'react';
import { Activity, ChevronDown, FolderOpen, RefreshCw } from 'lucide-react';
import Badge from './Badge';
import ProgressBar from './ProgressBar';
import {
  formatProjectPeriod,
  getProjectBrand,
  getProjectDisplayName,
  healthColor,
  healthLabel,
} from '../shared/projectWorkspace';

export default function ProjectWorkspacePanel({ workspace, roleName = '当前岗位' }) {
  const [open, setOpen] = useState(false);
  const project = workspace.currentProject;
  const score = workspace.metrics?.summary?.health_score ?? 0;
  const summary = workspace.metrics?.summary || {};

  return (
    <div className="card project-context-panel">
      <div className="card-body">
        <div className="project-context-main">
          <div className="project-context-title">
            <div className="project-context-icon">
              <FolderOpen size={18} />
            </div>
            <div>
              <div className="text-xs text-muted">{roleName} · 当前项目</div>
              <h3>{getProjectDisplayName(project)}</h3>
              <div className="text-xs text-secondary">
                {getProjectBrand(project)} · {formatProjectPeriod(project)}
              </div>
            </div>
          </div>
          <div className="project-context-actions">
            <Badge variant={healthColor(score)}>{healthLabel(score)} {score}</Badge>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => setOpen((value) => !value)}>
              <ChevronDown size={14} />
              切换项目
            </button>
            <button type="button" className="btn btn-icon btn-ghost" onClick={() => workspace.reloadCurrentProject()}>
              <RefreshCw size={16} />
            </button>
          </div>
        </div>
        <div className="project-context-metrics">
          {[
            { label: '任务完成', value: `${summary.task_done || 0}/${summary.task_total || 0}`, progress: summary.task_total ? (summary.task_done / summary.task_total) * 100 : 0, color: 'cyan' },
            { label: '待接交接', value: summary.pending_handoffs || 0, progress: Math.min((summary.pending_handoffs || 0) * 20, 100), color: 'amber' },
            { label: '项目资产', value: summary.asset_count || 0, progress: Math.min((summary.asset_count || 0) * 20, 100), color: 'purple' },
            { label: '达人入池', value: summary.qualified_creator_count || 0, progress: summary.creator_pool_score || 0, color: 'green' },
          ].map((item) => (
            <div key={item.label} className="project-context-metric">
              <div className="flex items-center justify-between mb-1">
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
              <ProgressBar value={item.progress} color={item.color} size="sm" showLabel={false} />
            </div>
          ))}
        </div>
        {open && (
          <div className="project-switcher-inline">
            {workspace.projects.map((item) => (
              <button
                type="button"
                key={item.project_id}
                className={item.project_id === workspace.projectId ? 'active' : ''}
                onClick={() => {
                  workspace.selectProject(item.project_id);
                  setOpen(false);
                }}
              >
                <FolderOpen size={14} />
                <span>{getProjectDisplayName(item)}</span>
                <small>{formatProjectPeriod(item)}</small>
              </button>
            ))}
          </div>
        )}
        {workspace.error && (
          <div className="project-context-error">
            <Activity size={14} />
            <span>{workspace.error}</span>
          </div>
        )}
      </div>
    </div>
  );
}
