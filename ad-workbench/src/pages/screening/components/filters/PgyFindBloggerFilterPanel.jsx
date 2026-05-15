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
import {
  getPgyFilterMeta,
  getPgySelectedItems,
  makePgyFilterItem,
  pgyFilterKey,
  replacePgyFieldFilters,
  togglePgyCollectionFilter,
} from '../../utils/pgyFilters';
import { PGY_FIND_BLOGGER_FILTER_GROUPS } from '../../constants/pgyConstants';
import { PgyFilterPopover } from './PgyFilterPopover';

export function PgyFindBloggerFilterPanel({ filters = [], onChange }) {
  const [openField, setOpenField] = useState(null);
  const [openAnchor, setOpenAnchor] = useState(null);

  const selectedKeys = useMemo(() => new Set((filters || []).map(pgyFilterKey)), [filters]);
  const selectedItems = useMemo(() => filters || [], [filters]);

  const renderFieldButton = (field, label = field, options = {}) => {
    const meta = getPgyFilterMeta(field);
    if (!meta) return renderMutedToken(label, field);
    const selectedItems = getPgySelectedItems(filters, field)
      .filter(item => !options.subField || [item.goal, item.parent_value, item.parentValue, item.sub_field, item.subField].includes(options.subField));
    const active = selectedItems.length > 0;
    const displayValue = active ? selectedItems.slice(0, 2).map(item => item.value).join('、') : '';
    const fieldKey = `${field}|${options.subField || ''}`;
    return (
      <span key={fieldKey} className="pgy-find-filter-popover-wrap">
        <button
          type="button"
          className={`pgy-find-filter-token has-chevron ${active ? 'is-active' : ''}`}
          title={active ? selectedItems.map(item => item.value).join('、') : label}
          onClick={(event) => {
            const nextField = openField === fieldKey ? null : fieldKey;
            setOpenField(nextField);
            setOpenAnchor(nextField ? event.currentTarget : null);
          }}
        >
          <span>{label}{displayValue ? `：${displayValue}${selectedItems.length > 2 ? '...' : ''}` : ''}</span>
          <ChevronDown size={14} className={openField === fieldKey ? 'is-open' : ''} />
        </button>
        {openField === fieldKey && (
          <PgyFilterPopover
            meta={meta}
            filters={filters}
            anchorEl={openAnchor}
            initialSubField={options.subField || ''}
            onApply={(nextItems) => onChange?.(replacePgyFieldFilters(filters, meta, nextItems))}
            onClear={() => onChange?.((filters || []).filter(item => item.field !== meta.field))}
            onClose={() => {
              setOpenField(null);
              setOpenAnchor(null);
            }}
          />
        )}
      </span>
    );
  };

  const renderMutedToken = (label, key = label, checkbox = false) => (
    <span key={key} className={`pgy-find-filter-token is-muted ${checkbox ? 'has-checkbox' : 'has-chevron'}`}>
      {checkbox && <span className="pgy-find-checkbox" />}
      <span>{label}</span>
      {!checkbox && <ChevronDown size={14} />}
    </span>
  );

  const renderRowContent = (row) => {
    if (row.kind === 'marketingGoal') {
      const meta = getPgyFilterMeta(row.field);
      const groups = meta?.option_groups || meta?.optionGroups || [];
      return (
        <>
          {groups.map(group => renderFieldButton(row.field, group.label, { subField: group.label }))}
        </>
      );
    }
    if (row.kind === 'tags') {
      const meta = getPgyFilterMeta(row.field);
      const values = row.values || meta?.options || [];
      const selectedFieldItems = getPgySelectedItems(filters, row.field);
      return (
        <>
          {row.showAll && (
            <button
              type="button"
              className={`pgy-find-filter-token is-all ${selectedFieldItems.length ? '' : 'is-active'}`}
              onClick={() => meta && onChange?.((filters || []).filter(item => item.field !== row.field))}
            >
              全部
            </button>
          )}
          {values.map(value => {
            const selected = meta ? selectedKeys.has(pgyFilterKey(makePgyFilterItem(meta, value))) : false;
            return (
              <button
                key={`${row.field}-${value}`}
                type="button"
                className={`pgy-find-filter-token ${selected ? 'is-active' : ''}`}
                onClick={() => meta && onChange?.(togglePgyCollectionFilter(filters, meta, value))}
              >
                {row.newValues?.includes(value) && <span className="pgy-find-new-badge">新</span>}
                <span>{value}</span>
              </button>
            );
          })}
        </>
      );
    }
    if (row.kind === 'fields') {
      return (
        <>
          {(row.fields || []).map(field => renderFieldButton(field))}
          {(row.muted || []).map(label => renderMutedToken(label))}
        </>
      );
    }
    if (row.kind === 'checks') {
      const meta = getPgyFilterMeta(row.field);
      return (
        <>
          {(meta?.options || []).map(value => {
            const item = meta ? makePgyFilterItem(meta, value) : {};
            const checked = selectedKeys.has(pgyFilterKey(item));
            return (
              <label key={`${row.field}-${value}`} className={`pgy-find-filter-check ${checked ? 'is-active' : ''}`}>
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => meta && onChange?.(togglePgyCollectionFilter(filters, meta, value))}
                />
                <span>{value}</span>
              </label>
            );
          })}
          {(row.appendFields || []).map(field => renderFieldButton(field))}
        </>
      );
    }
    return null;
  };

  return (
    <div className="pgy-find-filter-panel">
      {selectedItems.length > 0 && (
        <div className="pgy-find-selected-bar">
          <span>已选条件</span>
          <div className="pgy-find-selected-list">
            {selectedItems.map(item => (
              <button
                key={pgyFilterKey(item)}
                type="button"
                onClick={() => onChange?.((filters || []).filter(next => pgyFilterKey(next) !== pgyFilterKey(item)))}
              >
                {item.field}：{item.value}
                <X size={12} />
              </button>
            ))}
          </div>
          <button type="button" className="pgy-find-clear-all" onClick={() => onChange?.([])}>清空全部</button>
        </div>
      )}
      {PGY_FIND_BLOGGER_FILTER_GROUPS.map(group => (
        <div className="pgy-find-filter-section" key={group.section}>
          <div className="pgy-find-filter-section-label">{group.section}</div>
          <div className="pgy-find-filter-section-body">
            {group.rows.map(row => (
              <div className="pgy-find-filter-row" key={`${group.section}-${row.label}`}>
                <div className="pgy-find-filter-row-label">
                  {row.label}
                  {['营销目标', '博主类目', '日常笔记', '合作笔记'].includes(row.label) && <Info size={13} />}
                </div>
                <div className="pgy-find-filter-row-options">
                  {renderRowContent(row)}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
