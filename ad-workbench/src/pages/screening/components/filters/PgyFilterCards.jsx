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
import Badge from '../../../../components/Badge';
import { CONTROL_TYPE_LABELS, pgyFilterKey, pgyFilterLabel } from '../../constants/screeningConstants';

export function PgyFilterCards({ items, onRemove }) {
  if (!items.length) return <span className="collection-empty-text">暂无蒲公英条件，可从下拉菜单勾选。</span>;
  return (
    <div className="collection-pgy-filter-card-grid">
      {items.map(item => {
        const inputValues = Array.isArray(item.input_values) ? item.input_values.filter(Boolean) : [];
        return (
          <div className="collection-pgy-filter-card" key={pgyFilterKey(item)}>
            <div className="collection-pgy-filter-card-main">
              <strong>{pgyFilterLabel(item)}</strong>
              <button type="button" onClick={() => onRemove(item)} title="移除"><X size={12} /></button>
            </div>
            <div className="collection-pgy-filter-card-meta">
              {item.control_type && <span>{CONTROL_TYPE_LABELS[item.control_type] || item.control_type}</span>}
              {item.sub_field && <span>{item.sub_field}</span>}
              {inputValues.length > 0 && <span>{inputValues.join('、')}</span>}
              {Array.isArray(item.competitor_values) && item.competitor_values.length > 0 && <span>竞品：{item.competitor_values.join('、')}</span>}
              {item.pending_detail && <span className="is-pending">{item.pending_detail}</span>}
            </div>
            {item.reason && <p>{item.reason}</p>}
          </div>
        );
      })}
    </div>
  );
}
