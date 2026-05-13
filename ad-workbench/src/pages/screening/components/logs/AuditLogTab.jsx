import React, { useMemo, useState } from 'react';
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
import { mockAuditLogs } from '../../constants/projectConstants';

export function AuditLogTab({ project }) {
  const [typeFilter, setTypeFilter] = useState('全部');

  const logs = useMemo(() => {
    return (window.__screeningLogs || mockAuditLogs)
      .filter(l => typeFilter === '全部' || l.type === typeFilter)
      .sort((a, b) => new Date(b.time) - new Date(a.time));
  }, [typeFilter]);

  const typeConfig = {
    review: { label: '审核操作', icon: <ClipboardCheck size={14} />, color: '#3B82F6' },
    screening: { label: '筛选任务', icon: <Bot size={14} />, color: '#8B5CF6' },
    feishu: { label: '飞书操作', icon: <Link2 size={14} />, color: '#10B981' },
    project: { label: '项目管理', icon: <FolderPlus size={14} />, color: '#F59E0B' },
  };

  const statusConfig = {
    success: { label: '成功', variant: 'green' },
    error: { label: '失败', variant: 'red' },
    warning: { label: '警告', variant: 'amber' },
    info: { label: '信息', variant: 'blue' },
  };

  return (
    <div>
      {/* 筛选栏 */}
      <div className="card" style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className={`btn btn-sm ${typeFilter === '全部' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setTypeFilter('全部')}>全部</button>
          {Object.entries(typeConfig).map(([key, cfg]) => (
            <button key={key} className={`btn btn-sm ${typeFilter === key ? 'btn-secondary' : 'btn-ghost'}`} onClick={() => setTypeFilter(key)}>
              {cfg.icon} {cfg.label}
            </button>
          ))}
        </div>
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>共 {logs.length} 条记录</span>
      </div>

      {/* 时间线 */}
      <div className="card" style={{ padding: '24px 24px 24px 32px' }}>
        {logs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32, color: 'var(--text-muted)' }}>
            <ScrollText size={32} style={{ marginBottom: 8 }} />
            <div>暂无操作日志</div>
          </div>
        ) : (
          <div style={{ position: 'relative' }}>
            {/* 时间线竖线 */}
            <div style={{ position: 'absolute', left: 7, top: 8, bottom: 8, width: 2, background: 'var(--border-primary)' }} />

            {logs.map((log, idx) => {
              const cfg = typeConfig[log.type] || typeConfig.project;
              const scfg = statusConfig[log.status] || statusConfig.info;
              return (
                <div key={log.id} className="timeline-item" style={{ position: 'relative', paddingLeft: 28, paddingBottom: idx < logs.length - 1 ? 24 : 0 }}>
                  {/* 时间线圆点 */}
                  <div className="timeline-dot" style={{
                    position: 'absolute', left: 0, top: 6, width: 16, height: 16, borderRadius: '50%',
                    background: log.status === 'error' ? '#EF4444' : cfg.color,
                    border: '3px solid var(--bg-secondary)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    {log.status === 'error' && <X size={8} color="#fff" />}
                  </div>

                  {/* 日志内容 */}
                  <div className="timeline-content">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ color: 'var(--text-primary)', fontWeight: 500, fontSize: 14 }}>{log.action}</span>
                        <Badge variant={scfg.variant}>{scfg.label}</Badge>
                      </div>
                      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{log.time}</span>
                    </div>
                    <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 4 }}>
                      <span style={{ color: 'var(--text-secondary)' }}>对象：</span>{log.target}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{log.detail}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>操作人：{log.user}</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
