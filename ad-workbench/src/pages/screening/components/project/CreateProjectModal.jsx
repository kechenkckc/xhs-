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

export function CreateProjectModal({ isOpen, onClose, onCreate }) {
  const [form, setForm] = useState({ name: '', product: '', poolType: 'shared', sharedPoolId: 'education_mom', budget: '', singleBudget: '', creatorCount: '', periodStart: '', periodEnd: '', cooperationType: '合作笔记', description: '' });

  if (!isOpen) return null;

  const handleSubmit = () => {
    const id = `proj_${Date.now()}`;
    onCreate({
      id, ...form, budget: Number(form.budget), singleBudget: Number(form.singleBudget), creatorCount: Number(form.creatorCount),
      period: `${form.periodStart} - ${form.periodEnd}`, status: '待启动', currentStep: 1,
      brief: { projectId: id, projectName: form.name, template: '自定义', description: form.description },
      screeningPlan: { briefType: 'simple', hardFilters: [], scoringWeights: { budget: 20, fans: 20, cpe: 15, engagement: 15, persona: 20, content: 10 } },
      feishuBinding: { linked: false, tableUrl: '', tableName: '', baseToken: '', tableId: '', viewId: '', fieldMapping: [] },
    });
    onClose();
  };

  const labelStyle = { fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 640, maxHeight: '90vh', overflow: 'auto' }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>新建筛选项目</h3>
          <button className="btn btn-ghost btn-sm modal-close" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="modal-body">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16, marginBottom: 16 }}>
            <div><label style={labelStyle}>项目名称 *</label><input className="input-field" value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="如：有道答疑笔5-6月合作" /></div>
            <div><label style={labelStyle}>产品名称 *</label><input className="input-field" value={form.product} onChange={e => setForm({...form, product: e.target.value})} placeholder="如：有道答疑笔Pro" /></div>
            <div><label style={labelStyle}>达人池类型 *</label>
              <select className="select-field" value={form.poolType} onChange={e => setForm({...form, poolType: e.target.value})}>
                <option value="shared">共享池（与其他项目共用达人库）</option>
                <option value="isolated">独立池（项目专属达人库）</option>
              </select>
            </div>
            {form.poolType === 'shared' ? (
              <div><label style={labelStyle}>选择共享池 *</label>
                <select className="select-field" value={form.sharedPoolId} onChange={e => setForm({...form, sharedPoolId: e.target.value})}>
                  <option value="education_mom">教育母婴池（10位达人）</option>
                  <option value="baby_care">母婴护理池（5位达人）</option>
                </select>
              </div>
            ) : (
              <div><label style={labelStyle}>合作形式</label>
                <select className="select-field" value={form.cooperationType} onChange={e => setForm({...form, cooperationType: e.target.value})}>
                  <option value="合作笔记">合作笔记</option><option value="视频+图文">视频+图文</option><option value="报备">报备</option><option value="直播带货">直播带货</option>
                </select>
              </div>
            )}
            <div><label style={labelStyle}>总预算（元）*</label><input className="input-field" type="number" value={form.budget} onChange={e => setForm({...form, budget: e.target.value})} placeholder="如：600000" /></div>
            <div><label style={labelStyle}>单达人预算上限（元）</label><input className="input-field" type="number" value={form.singleBudget} onChange={e => setForm({...form, singleBudget: e.target.value})} placeholder="如：20000" /></div>
            <div><label style={labelStyle}>目标达人数量 *</label><input className="input-field" type="number" value={form.creatorCount} onChange={e => setForm({...form, creatorCount: e.target.value})} placeholder="如：30" /></div>
            <div><label style={labelStyle}>合作形式</label>
              <select className="select-field" value={form.cooperationType} onChange={e => setForm({...form, cooperationType: e.target.value})}>
                <option value="合作笔记">合作笔记</option><option value="视频+图文">视频+图文</option><option value="报备">报备</option><option value="直播带货">直播带货</option>
              </select>
            </div>
            <div><label style={labelStyle}>开始日期</label><input className="input-field" type="date" value={form.periodStart} onChange={e => setForm({...form, periodStart: e.target.value})} /></div>
            <div><label style={labelStyle}>结束日期</label><input className="input-field" type="date" value={form.periodEnd} onChange={e => setForm({...form, periodEnd: e.target.value})} /></div>
          </div>
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>客户 Brief（口语化需求描述）</label>
            <textarea className="input-field" rows={3} value={form.description} onChange={e => setForm({...form, description: e.target.value})} placeholder="如：我们需要找一批教育/母婴类的达人来推广有道答疑笔..." style={{ resize: 'none' }} />
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>取消</button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={!form.name || !form.product || !form.budget || !form.creatorCount}>创建项目</button>
        </div>
      </div>
    </div>
  );
}
