import React, { useEffect, useMemo, useState } from 'react';
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
import { formatNoteMetric, normalizeNoteType } from '../../utils/formatters';
import { parseCountValue, uniqueCompactItems } from '../../utils/creatorMappers';

export function CreatorRecentNotesPanel({ notes = [] }) {
  const [groupMode, setGroupMode] = useState('type');
  const [typeFilter, setTypeFilter] = useState('全部类型');
  const [categoryFilter, setCategoryFilter] = useState('全部类目');
  const [sortMode, setSortMode] = useState('latest');
  const [trafficMode, setTrafficMode] = useState('all');
  const [crossOnly, setCrossOnly] = useState(false);
  const [page, setPage] = useState(1);
  const pageSize = 8;
  const categoryOptions = useMemo(() => ['全部类目', ...uniqueCompactItems(notes.map(note => note.contentCategory || note.brand), 12)], [notes]);

  const filteredNotes = useMemo(() => {
    let list = [...notes];
    if (typeFilter !== '全部类型') list = list.filter(note => normalizeNoteType(note.noteType) === typeFilter);
    if (categoryFilter !== '全部类目') list = list.filter(note => (note.contentCategory || note.brand) === categoryFilter);
    if (trafficMode === 'promoted') list = list.filter(note => note.promoted);
    if (trafficMode === 'natural') list = list.filter(note => !note.promoted);
    if (crossOnly) list = list.filter(note => note.crossDomain);
    list.sort((a, b) => {
      if (sortMode === 'read') return parseCountValue(b.readCount) - parseCountValue(a.readCount);
      if (sortMode === 'interaction') {
        const bValue = parseCountValue(b.likeCount) + parseCountValue(b.saveCount) + parseCountValue(b.commentCount);
        const aValue = parseCountValue(a.likeCount) + parseCountValue(a.saveCount) + parseCountValue(a.commentCount);
        return bValue - aValue;
      }
      return String(b.publishedAt || '').localeCompare(String(a.publishedAt || ''));
    });
    return list;
  }, [categoryFilter, crossOnly, notes, sortMode, trafficMode, typeFilter]);

  useEffect(() => {
    setPage(1);
  }, [categoryFilter, crossOnly, sortMode, trafficMode, typeFilter]);

  const totalPages = Math.max(1, Math.ceil(filteredNotes.length / pageSize));
  const visibleNotes = filteredNotes.slice((page - 1) * pageSize, page * pageSize);

  return (
    <div className="creator-recent-notes-panel">
      <div className="creator-recent-notes-toolbar">
        <div className="creator-recent-mode-tabs">
          <button type="button" className={groupMode === 'type' ? 'is-active' : ''} onClick={() => setGroupMode('type')}>按笔记类型</button>
          <button type="button" className={groupMode === 'category' ? 'is-active' : ''} onClick={() => setGroupMode('category')}>按内容类目</button>
        </div>
        <div className="creator-recent-selects">
          <select className="select-field" value={sortMode} onChange={e => setSortMode(e.target.value)}>
            <option value="latest">最新发布</option>
            <option value="read">阅读最高</option>
            <option value="interaction">互动最高</option>
          </select>
          <select className="select-field" value={trafficMode} onChange={e => setTrafficMode(e.target.value)}>
            <option value="all">全部流量</option>
            <option value="natural">自然流量</option>
            <option value="promoted">投流笔记</option>
          </select>
        </div>
      </div>
      <div className="creator-recent-subbar">
        {groupMode === 'type' ? (
          <div className="creator-recent-filter-tabs">
            {['全部类型', '合作笔记', '图文笔记', '视频笔记'].map(item => (
              <button key={item} type="button" className={typeFilter === item ? 'is-active' : ''} onClick={() => setTypeFilter(item)}>{item}</button>
            ))}
          </div>
        ) : (
          <div className="creator-recent-filter-tabs">
            {categoryOptions.map(item => (
              <button key={item} type="button" className={categoryFilter === item ? 'is-active' : ''} onClick={() => setCategoryFilter(item)}>{item}</button>
            ))}
          </div>
        )}
        <label className="creator-recent-switch">
          <input type="checkbox" checked={crossOnly} onChange={e => setCrossOnly(e.target.checked)} />
          <span />
          仅展示跨域合作笔记
        </label>
      </div>
      {visibleNotes.length ? (
        <>
          <div className="creator-recent-note-grid">
            {visibleNotes.map((note, index) => (
              <article className="creator-recent-note-card" key={`${note.title}-${index}`}>
                <div className="creator-recent-note-cover">
                  {note.coverUrl ? <img src={note.coverUrl} alt={note.title} /> : <FileText size={30} />}
                </div>
                <div className="creator-recent-note-body">
                  <strong>{note.title}</strong>
                  <div className="creator-recent-note-metrics">
                    <span>阅读</span><em>{formatNoteMetric(note.readCount)}</em>
                    <span>点赞</span><em>{formatNoteMetric(note.likeCount)}</em>
                    <span>收藏</span><em>{formatNoteMetric(note.saveCount)}</em>
                    <span>发布时间</span><em>{note.publishedAt || '-'}</em>
                    {note.trafficComparison && <><span>中位数对比</span><em>{note.trafficComparison}</em></>}
                  </div>
                  <div className="creator-recent-note-tags">
                    <Badge variant={normalizeNoteType(note.noteType) === '视频笔记' ? 'purple' : 'blue'}>{normalizeNoteType(note.noteType)}</Badge>
                    {note.promoted && <Badge variant="amber">投流</Badge>}
                    {note.hasClearMedianContrast && <Badge variant="green">中位数差异明显</Badge>}
                    {note.crossDomain && <Badge variant="green">跨域合作</Badge>}
                  </div>
                  {note.link && <a href={note.link} target="_blank" rel="noreferrer">查看笔记 <ExternalLink size={12} /></a>}
                </div>
              </article>
            ))}
          </div>
          <div className="creator-recent-pagination">
            <button type="button" disabled={page <= 1} onClick={() => setPage(value => Math.max(1, value - 1))}><ChevronLeft size={16} /></button>
            {Array.from({ length: Math.min(totalPages, 9) }, (_, index) => index + 1).map(item => (
              <button key={item} type="button" className={page === item ? 'is-active' : ''} onClick={() => setPage(item)}>{item}</button>
            ))}
            <button type="button" disabled={page >= totalPages} onClick={() => setPage(value => Math.min(totalPages, value + 1))}><ChevronRight size={16} /></button>
          </div>
        </>
      ) : (
        <div className="creator-detail-empty">
          <FileText size={28} />
          <strong>当前筛选下无笔记</strong>
          <p>请切换笔记类型、内容类目或流量筛选。</p>
        </div>
      )}
    </div>
  );
}
