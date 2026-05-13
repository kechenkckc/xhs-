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
import {
  defaultHardFilterCondition,
  hardFilterConditionsFor,
  normalizeHardFilterItem,
} from '../../utils/screeningPlan';
import { HARD_FILTER_OPTIONS, hardFilterKey, hardFilterLabel } from '../../constants/screeningConstants';
import { HardFilterValueControl } from './HardFilterValueControl';

export function HardFilterEditor({
  filters = [],
  onChange,
  options = HARD_FILTER_OPTIONS,
  emptyText = '暂未设置硬性条件，可从可选项添加或手工新增',
  fieldHeader = '筛选项',
  evidenceHeader = '依据字段',
  evidencePlaceholder = '关联字段',
}) {
  const updateFilter = (index, patch) => {
    const nextFilters = [...(filters || [])];
    const next = { ...(nextFilters[index] || {}), ...patch };
    if (patch.field !== undefined || patch.value !== undefined || patch.feishuField !== undefined) {
      const conditions = hardFilterConditionsFor(next);
      if (!conditions.includes(next.condition)) {
        next.condition = defaultHardFilterCondition(next);
      }
    }
    nextFilters[index] = next;
    onChange?.(nextFilters);
  };

  const addFilter = (option = {}) => {
    const item = normalizeHardFilterItem(option);
    item.condition = hardFilterConditionsFor(item).includes(item.condition) ? item.condition : defaultHardFilterCondition(item);
    onChange?.([...(filters || []), item]);
  };

  const removeFilter = (index) => {
    onChange?.((filters || []).filter((_, itemIndex) => itemIndex !== index));
  };

  return (
    <>
      <div className="standard-hard-filter-toolbar">
        <select
          className="select-field"
          value=""
          onChange={e => {
            const option = options.find(item => hardFilterKey(item) === e.target.value);
            if (option) addFilter(option);
          }}
        >
          <option value="">从可选项添加条件</option>
          {options.map(option => (
            <option key={hardFilterKey(option)} value={hardFilterKey(option)}>{hardFilterLabel(option)}</option>
          ))}
        </select>
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => addFilter()}>
          <Plus size={14} style={{ marginRight: 4 }} />手工新增
        </button>
      </div>
      <div className="standard-hard-filter-list">
        {(filters || []).length > 0 && (
          <div className="standard-hard-filter-header">
            <span>{fieldHeader}</span>
            <span>判断方式</span>
            <span>标准/阈值</span>
            <span>{evidenceHeader}</span>
            <span>硬性必过</span>
            <span>操作</span>
          </div>
        )}
        {(filters || []).map((f, i) => (
          <div key={`hard-filter-${i}`} className="standard-hard-filter-row">
            <input className="input-field" value={f.field || ''} onChange={e => updateFilter(i, { field: e.target.value })} placeholder="字段/规则名" />
            <select className="select-field" value={f.condition || ''} onChange={e => updateFilter(i, { condition: e.target.value })}>
              {hardFilterConditionsFor(f).map(condition => <option key={condition} value={condition}>{condition}</option>)}
            </select>
            <HardFilterValueControl filter={f} onChange={patch => updateFilter(i, patch)} />
            <input className="input-field" value={f.feishuField || ''} onChange={e => updateFilter(i, { feishuField: e.target.value })} placeholder={evidencePlaceholder} />
            <label className="standard-hard-filter-required">
              <input type="checkbox" checked={f.required !== false} onChange={e => updateFilter(i, { required: e.target.checked })} />
              <span>必过</span>
            </label>
            <button type="button" className="btn btn-ghost btn-icon btn-sm" title="删除条件" onClick={() => removeFilter(i)}>
              <Trash2 size={14} />
            </button>
          </div>
        ))}
        {(filters || []).length === 0 && (
          <div style={{ padding: 16, background: 'var(--bg-elevated)', borderRadius: 6, textAlign: 'center', color: 'var(--text-muted)' }}>
            {emptyText}
          </div>
        )}
      </div>
    </>
  );
}
