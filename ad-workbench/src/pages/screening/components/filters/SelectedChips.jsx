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

export function SelectedChips({ items, getKey, getLabel, onRemove, emptyText }) {
  if (!items.length) return <span className="collection-empty-text">{emptyText}</span>;
  return (
    <div className="collection-selected-chip-row">
      {items.map(item => (
        <span className="collection-selected-chip" key={getKey(item)}>
          {getLabel(item)}
          <button type="button" onClick={() => onRemove(item)} title="移除"><X size={12} /></button>
        </span>
      ))}
    </div>
  );
}
