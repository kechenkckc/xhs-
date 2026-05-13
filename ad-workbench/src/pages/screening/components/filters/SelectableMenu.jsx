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

export function SelectableMenu({ menuId, openMenu, setOpenMenu, label, summary, options, selectedKeys, getKey, getLabel, onToggle }) {
  const open = openMenu === menuId;
  return (
    <div className="collection-select-menu">
      <button type="button" className="collection-select-trigger" onClick={() => setOpenMenu(open ? null : menuId)}>
        <span>{label}</span>
        <small>{summary}</small>
        <ChevronDown size={15} className={open ? 'is-open' : ''} />
      </button>
      {open && (
        <div className="collection-select-popover">
          {options.map(option => {
            const key = getKey(option);
            const checked = selectedKeys.has(key);
            return (
              <label key={key} className="collection-select-option">
                <input type="checkbox" checked={checked} onChange={() => onToggle(option, checked)} />
                <span>{getLabel(option)}</span>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}
