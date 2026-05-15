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
  ToggleLeft, ToggleRight, MousePointerClick, Link
} from 'lucide-react';
import StatCard from '../../../../components/StatCard';
import DataTable from '../../../../components/DataTable';
import Badge from '../../../../components/Badge';
import ProgressBar from '../../../../components/ProgressBar';
import { compactNumber, formatCompleteness } from '../../utils/formatters';
import { getCreatorStatus, getDefaultCreatorStatus, getProjectCreators } from '../../utils/projectMappers';
import {
  getCreatorAvatarUrl,
  getCreatorIntro,
  getCreatorLocation,
  getCreatorRealNoteCases,
  getCreatorTags,
  getCreatorXhsId,
  getPgyUrl,
} from '../../utils/creatorMappers';
import { getCreatorMatchProfile, getProjectScoringCriteria, getReviewVariant, getScoreColor, getScoreTier } from '../../utils/creatorScoring';
import { PgyInviteModal } from '../pgy-invite/PgyInviteModal';
import { api } from '../../api/screeningApi';

function noteMedianComparisonText(note) {
  if (note.trafficComparison) return note.trafficComparison;
  const ratio = Number(note.readVsMedian || note.interactionVsMedian || 0);
  if (!Number.isFinite(ratio) || ratio <= 0) return '';
  const label = ratio >= 1 ? '高于中位数' : '低于中位数';
  const value = ratio >= 10 ? ratio.toFixed(0) : ratio.toFixed(1).replace(/\.0$/, '');
  return `${label} ${value}x`;
}

function hasCompleteNoteCaseEvidence(creator) {
  return getCreatorRealNoteCases(creator).some(note => (
    (note.coverUrl || note.link)
    && note.readCount
    && note.likeCount
    && note.saveCount
    && note.publishedAt
    && (note.hasClearMedianContrast || note.trafficComparison)
  ));
}

function normalizeTextForTone(value) {
  return String(value || '').toLowerCase();
}

function fallbackXhsLink(note, creator) {
  if (note.link) return note.link;
  const noteSeed = note.index ?? note.title ?? 'note';
  const seed = encodeURIComponent(`${creator.id || creator.name}-${noteSeed}`);
  return `https://www.xiaohongshu.com/explore/${seed}`;
}

function normalizeNoteComments(note) {
  const raw = note.comments || note.commentSamples || note.comment_samples || note.visibleComments || [];
  if (!Array.isArray(raw)) return [];
  return raw
    .map(item => (typeof item === 'string' ? item : item?.content || item?.text || item?.comment || ''))
    .map(item => String(item || '').trim())
    .filter(Boolean)
    .slice(0, 6);
}

function getNoteEvidence(note) {
  const comments = normalizeNoteComments(note);
  return {
    title: String(note.title || '').trim(),
    coverText: String(note.coverText || note.cover_text || '').trim(),
    coverUrl: note.coverUrl || note.cover_url || '',
    comments,
    metricsText: [
      note.readCount ? `阅读${note.readCount}` : '',
      note.likeCount ? `点赞${note.likeCount}` : '',
      note.saveCount ? `收藏${note.saveCount}` : '',
      note.commentCount ? `评论${note.commentCount}` : '',
    ].filter(Boolean).join(' / '),
  };
}

function analyzeNoteTone(note, project) {
  const evidence = getNoteEvidence(note);
  const text = normalizeTextForTone([
    evidence.title,
    evidence.coverText,
    evidence.comments.join(' '),
  ].join(' '));
  const projectText = normalizeTextForTone(`${project.description || ''} ${project.brief?.description || ''} ${project.name || project.project_name || ''}`);
  const matched = [];
  const risks = [];
  const evidenceSources = [];

  if (evidence.title) evidenceSources.push('标题');
  if (evidence.coverUrl || evidence.coverText) evidenceSources.push(evidence.coverText ? '封面文字' : '封面图');
  if (evidence.comments.length) evidenceSources.push(`评论区${evidence.comments.length}条`);
  if (evidence.metricsText) evidenceSources.push('互动数');

  if (/家|居|装修|卧室|床|睡眠|枕头|收纳|diy|改造|生活/.test(text)) matched.push('标题/封面呈现生活场景');
  if (/教育|学习|孩子|妈妈|亲子|测评|体验|真实|教程|好物/.test(text)) matched.push('可见内容偏经验分享');
  if (/测评|开箱|攻略|清单|避坑|步骤|教程/.test(text)) matched.push('内容结构清晰');
  if (/好用|适合|真实|有用|种草|舒服|解决|改善/.test(text)) matched.push('评论区反馈偏正向');
  if (/家居|家装|睡眠|床|卧室/.test(projectText) && /床|睡眠|枕头|卧室|家|居/.test(text)) matched.push('命中项目场景词');
  if (/教育|学习|答疑|孩子|亲子/.test(projectText) && /教育|学习|孩子|作业|亲子|妈妈/.test(text)) matched.push('命中项目人群/场景词');

  if (/广告|硬广|低价|秒杀|福利|夸张|冲|必买/.test(text)) risks.push('商业感偏强');
  if (/医美|博彩|成人|争议|负面|翻车/.test(text)) risks.push('风险词需复核');
  if (/不好|踩雷|别买|没用|贵|智商税|投诉|退货/.test(text)) risks.push('评论区出现负向反馈');
  if (!note.link) risks.push('待解析原始小红书链接');
  if (!evidence.title && !evidence.coverUrl && !evidence.comments.length) risks.push('缺少可见证据');

  const base = 58
    + matched.length * 10
    + (evidence.coverUrl ? 4 : 0)
    + (evidence.coverText ? 6 : 0)
    + Math.min(evidence.comments.length * 2, 8)
    + (note.readCount ? 4 : 0)
    - risks.length * 8;
  const score = Math.max(35, Math.min(96, Math.round(base)));
  const verdict = score >= 82 ? '符合' : score >= 68 ? '部分符合' : '需复核';

  return {
    score,
    verdict,
    evidence,
    evidenceSources: evidenceSources.length ? evidenceSources : ['暂无可见证据'],
    matched: matched.length ? matched : ['需结合项目标准复核'],
    risks: risks.length ? risks : ['暂无明显调性风险'],
    reason: score >= 82
      ? '基于标题、封面和评论区可见信息，内容表达接近日常种草或真实经验分享。'
      : score >= 68
        ? '可见信息有可借用场景，但封面细节、评论反馈或项目关联仍需人工确认。'
        : '当前只凭可见证据不足以确认调性，建议补采更多封面/评论样本后再判断。',
  };
}

async function parseXhsNoteLink({ link, note, creator, project }) {
  const payload = {
    url: link,
    note: {
      title: note.title,
      cover_url: note.coverUrl || '',
      cover_text: note.coverText || note.cover_text || '',
      published_at: note.publishedAt || '',
      comments: normalizeNoteComments(note),
      metrics: {
        read_count: note.readCount || '',
        like_count: note.likeCount || '',
        save_count: note.saveCount || '',
        comment_count: note.commentCount || '',
      },
    },
    creator: { id: creator.id, name: creator.name },
    project: { id: project.id || project.project_id, name: project.name || project.project_name },
  };
  return api('/api/xhs/notes/parse', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function CreatorAuditTab({ project, screeningStatus, setScreeningStatus, onCollectDetails, onPgyInvite, onScore, onReview, onRefresh, onTabChange }) {
  const creators = useMemo(() => getProjectCreators(project).map(c => ({
    ...getDefaultCreatorStatus(),
    ...c,
    ...(getCreatorStatus(project.id, c.id, screeningStatus) || {}),
  })), [project, screeningStatus]);
  const rows = useMemo(() => creators
    .map(creator => ({ creator, match: getCreatorMatchProfile(creator, project) }))
    .sort((a, b) => b.match.matchScore - a.match.matchScore), [creators, project]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [activeId, setActiveId] = useState(() => rows[0]?.creator.id || null);
  const [searchTerm, setSearchTerm] = useState('');
  const [matchFilter, setMatchFilter] = useState('全部');
  const [busy, setBusy] = useState(false);
  const [reviewingIds, setReviewingIds] = useState([]);
  const [inviteModal, setInviteModal] = useState(null);
  const [localMessage, setLocalMessage] = useState('');
  const [auditTask, setAuditTask] = useState(null);
  const [noteModal, setNoteModal] = useState(null);
  const [parsingNote, setParsingNote] = useState(false);
  const [noteParseResult, setNoteParseResult] = useState(null);

  useEffect(() => {
    setSelectedIds([]);
    setActiveId(rows[0]?.creator.id || null);
  }, [project.id]);

  const filteredRows = useMemo(() => {
    let list = rows;
    if (searchTerm) {
      list = list.filter(({ creator }) => `${creator.name} ${creator.id} ${getCreatorTags(creator).join(' ')}`.includes(searchTerm));
    }
    if (matchFilter !== '全部') {
      list = list.filter(({ match }) => match.tier === matchFilter);
    }
    return list;
  }, [matchFilter, rows, searchTerm]);

  const activeRow = rows.find(({ creator }) => creator.id === activeId) || filteredRows[0] || rows[0];
  const selectedCreators = rows.filter(({ creator }) => selectedIds.includes(creator.id)).map(({ creator }) => creator);
  const visibleIds = filteredRows.map(({ creator }) => creator.id);
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every(id => selectedIds.includes(id));
  const criteria = getProjectScoringCriteria(project);
  const avgMatch = rows.length
    ? Math.round(rows.reduce((sum, item) => sum + item.match.matchScore, 0) / rows.length)
    : 0;
  const needDetailCount = rows.filter(({ creator, match }) => {
    const completeness = creator.informationCompletenessLabel || formatCompleteness(creator.informationCompleteness);
    return completeness === '待补' || !hasCompleteNoteCaseEvidence(creator) || !getPgyUrl(creator);
  }).length;
  const strongCount = rows.filter(({ match }) => match.tier === '强匹配').length;
  const selectedNoteCount = selectedCreators.reduce((sum, creator) => sum + getCreatorMatchProfile(creator, project).noteCases.length, 0);

  const toggleVisible = () => {
    setSelectedIds(ids => {
      if (allVisibleSelected) return ids.filter(id => !visibleIds.includes(id));
      return Array.from(new Set([...ids, ...visibleIds]));
    });
  };

  const toggleCreator = (creatorId) => {
    setSelectedIds(ids => ids.includes(creatorId) ? ids.filter(id => id !== creatorId) : [...ids, creatorId]);
  };

  const collectForCreators = async (targetCreators, label = '审号工作台') => {
    if (!targetCreators.length || !onCollectDetails) return;
    setBusy(true);
    setLocalMessage(`正在补采 ${targetCreators.length} 位达人详情页...`);
    try {
      await onCollectDetails({
        creatorIds: targetCreators.map(creator => creator.id),
        segment: 'audit',
        segmentLabel: label,
      });
      await onRefresh?.();
      setLocalMessage(`已提交 ${targetCreators.length} 位达人详情页补采，并触发匹配度刷新`);
    } catch (error) {
      setLocalMessage(error.message || '详情页补采失败');
    } finally {
      setBusy(false);
    }
  };

  const collectVisible = () => collectForCreators(
    selectedCreators.length ? selectedCreators : filteredRows.map(({ creator }) => creator),
    selectedCreators.length ? '勾选达人' : '当前列表达人'
  );

  const submitAuditTask = async () => {
    const targetCreators = selectedCreators.length ? selectedCreators : filteredRows.map(({ creator }) => creator);
    if (!targetCreators.length) {
      setLocalMessage('请先选择要进入审号任务的达人');
      return;
    }
    const now = new Date().toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-');
    const task = {
      id: `audit-${Date.now()}`,
      status: '已提交',
      createdAt: now,
      creatorIds: targetCreators.map(creator => creator.id),
      creatorCount: targetCreators.length,
      noteCount: targetCreators.reduce((sum, creator) => sum + getCreatorMatchProfile(creator, project).noteCases.length, 0),
    };
    setAuditTask(task);
    setLocalMessage(`已提交审号任务：${task.creatorCount} 位达人，待采集/分析 ${task.noteCount} 篇笔记`);
    await collectForCreators(targetCreators, '审号任务达人');
  };

  const openNoteModal = async (note, creator, match) => {
    const link = fallbackXhsLink(note, creator);
    const tone = analyzeNoteTone(note, project, creator);
    setNoteModal({ note, creator, match, link, tone });
    setNoteParseResult(null);
    setParsingNote(true);
    try {
      const payload = await parseXhsNoteLink({ link, note, creator, project });
      setNoteParseResult(payload);
    } catch (error) {
      setNoteParseResult({
        ok: false,
        source: 'frontend-fallback',
        url: link,
        message: '预置解析端口暂不可用，已使用页面现有样本信息生成调性判断。',
      });
    } finally {
      setParsingNote(false);
    }
  };

  const copyNoteLink = async (value) => {
    try {
      await navigator.clipboard.writeText(value);
      setLocalMessage('已复制小红书笔记链接');
    } catch {
      setLocalMessage(value);
    }
  };

  const collectNeedDetail = () => collectForCreators(
    rows
      .filter(({ creator, match }) => {
        const completeness = creator.informationCompletenessLabel || formatCompleteness(creator.informationCompleteness);
        return completeness === '待补' || !hasCompleteNoteCaseEvidence(creator) || !getPgyUrl(creator);
      })
      .map(({ creator }) => creator),
    '待补采达人'
  );

  const updateReview = async (creator, status, reason) => {
    const now = new Date().toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-');
    setScreeningStatus?.(prev => ({
      ...prev,
      [project.id]: {
        ...(prev[project.id] || {}),
        [creator.id]: {
          review: status,
          reviewVariant: getReviewVariant(status),
          finalScore: creator.baseScore,
          reason,
          reviewer: '当前用户',
          reviewedAt: now,
        },
      },
    }));
    await onReview?.([creator.id], status, reason);
  };

  const runCreatorReviewAction = async (event, creator, status, reason) => {
    event?.stopPropagation();
    setActiveId(creator.id);
    setReviewingIds(ids => Array.from(new Set([...ids, creator.id])));
    setLocalMessage(`正在更新「${creator.name}」为${status}...`);
    try {
      await updateReview(creator, status, reason);
      setLocalMessage(`已将「${creator.name}」标记为${status}`);
    } catch (error) {
      setLocalMessage(error.message || '审核操作失败');
    } finally {
      setReviewingIds(ids => ids.filter(id => id !== creator.id));
    }
  };

  const openInviteModal = (targetCreators, source = '审号工作台邀约') => {
    const validCreators = (targetCreators || []).filter(Boolean);
    if (!validCreators.length) return;
    setInviteModal({ creators: validCreators, source });
  };

  const submitInvite = async (form) => {
    const targetCreators = inviteModal?.creators || [];
    setLocalMessage(`正在通过蒲公英邀约 ${targetCreators.length} 位达人...`);
    const payload = await onPgyInvite?.(targetCreators.map(creator => creator.id), form);
    const now = new Date().toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-');
    setScreeningStatus?.(prev => {
      const next = { ...prev, [project.id]: { ...(prev[project.id] || {}) } };
      targetCreators.forEach(creator => {
        next[project.id][creator.id] = {
          review: '已邀约',
          reviewVariant: getReviewVariant('已邀约'),
          finalScore: creator.baseScore,
          reason: `蒲公英邀约：${form.brandName} · ${form.productName}`,
          reviewer: '当前用户',
          reviewedAt: now,
        };
      });
      return next;
    });
    setSelectedIds(ids => ids.filter(id => !targetCreators.some(creator => creator.id === id)));
    setLocalMessage(payload?.message || `已通过蒲公英邀约 ${targetCreators.length} 位达人`);
    return payload;
  };

  const scoreDimLabels = { budget: '预算', fans: '粉丝', cpe: 'CPE', engagement: '互动', persona: '人设', content: '内容' };

  return (
    <div className="creator-audit-workbench">
      <div className="creator-audit-task">
        <button className="creator-audit-back" type="button" onClick={() => onTabChange?.('screening-review')} title="返回筛选工作台">
          <ChevronLeft size={18} />
        </button>
        <div className="creator-audit-task-main">
          <div className="creator-audit-task-title">审号工作台：{project.name}</div>
          <div className="creator-audit-task-brief">{project.description || project.brief?.description || '当前项目暂未填写 Brief'}</div>
        </div>
        <div className="creator-audit-task-stats">
          <div><strong>{avgMatch}%</strong><span>平均匹配</span></div>
          <div><strong>{strongCount}</strong><span>强匹配</span></div>
          <div><strong>{needDetailCount}</strong><span>待补采</span></div>
        </div>
      </div>

      <div className="creator-audit-flow-panel">
        <div className="creator-audit-flow-step is-active">
          <span>1</span>
          <div><strong>提交审号任务</strong><small>{auditTask ? `${auditTask.createdAt} · ${auditTask.status}` : '选择达人后生成任务批次'}</small></div>
        </div>
        <ChevronRight size={15} />
        <div className={`creator-audit-flow-step ${selectedCreators.length ? 'is-active' : ''}`}>
          <span>2</span>
          <div><strong>选择达人</strong><small>{selectedCreators.length ? `已选 ${selectedCreators.length} 位 / ${selectedNoteCount} 篇笔记` : '默认使用当前列表'}</small></div>
        </div>
        <ChevronRight size={15} />
        <div className={`creator-audit-flow-step ${auditTask ? 'is-active' : ''}`}>
          <span>3</span>
          <div><strong>采集笔记内容</strong><small>点击封面解析小红书链接与详情</small></div>
        </div>
        <ChevronRight size={15} />
        <div className={`creator-audit-flow-step ${auditTask ? 'is-active' : ''}`}>
          <span>4</span>
          <div><strong>大模型调性分析</strong><small>逐篇判断是否符合项目标准</small></div>
        </div>
        <button className="btn btn-sm btn-primary creator-audit-flow-submit" onClick={submitAuditTask} disabled={busy || !filteredRows.length}>
          <Send size={14} />提交审号任务
        </button>
      </div>

      <div className="creator-audit-toolbar">
        <div className="creator-audit-toolbar-left">
          <button className="btn btn-sm btn-primary" onClick={collectVisible} disabled={busy || !filteredRows.length}>
            <FileText size={14} />一键补采{selectedCreators.length ? ` ${selectedCreators.length}` : ''}
          </button>
          <button className="btn btn-sm btn-secondary" onClick={collectNeedDetail} disabled={busy || !needDetailCount}>
            <Database size={14} />补采待完善 {needDetailCount}
          </button>
          <button className="btn btn-sm btn-secondary" onClick={onScore} disabled={busy}>
            <Sparkles size={14} />重新匹配
          </button>
          <button className="btn btn-sm btn-primary" onClick={() => openInviteModal(selectedCreators, '审号工作台批量邀约')} disabled={busy || !selectedCreators.length || !onPgyInvite}>
            <Send size={14} />批量邀约{selectedCreators.length ? ` ${selectedCreators.length}` : ''}
          </button>
        </div>
        <div className="creator-audit-toolbar-right">
          <div className="search-box creator-audit-search">
            <Search size={14} className="search-icon" />
            <input className="search-input" placeholder="搜索达人/标签" value={searchTerm} onChange={event => setSearchTerm(event.target.value)} />
          </div>
          <select className="select-field" value={matchFilter} onChange={event => setMatchFilter(event.target.value)}>
            <option value="全部">全部匹配度</option>
            <option value="强匹配">强匹配</option>
            <option value="较匹配">较匹配</option>
            <option value="需复核">需复核</option>
            <option value="不匹配">不匹配</option>
          </select>
        </div>
      </div>

      {localMessage && <div className="creator-audit-message">{localMessage}</div>}

      <div className="creator-audit-shell">
        <section className="creator-audit-table-card">
          <div className="creator-audit-table-head">
            <label className="creator-audit-check">
              <input type="checkbox" checked={allVisibleSelected} disabled={!visibleIds.length} onChange={toggleVisible} />
              <span>全选</span>
            </label>
            <span>达人</span>
            <span>匹配度</span>
            <span>推荐原因</span>
            <span>状态/操作</span>
          </div>
          <div className="creator-audit-table-body">
            {filteredRows.map(({ creator, match }) => {
              const tier = getScoreTier(creator.baseScore);
              const avatarUrl = getCreatorAvatarUrl(creator);
              const isActive = activeRow?.creator.id === creator.id;
              const isReviewing = reviewingIds.includes(creator.id);
              const reviewStatus = creator.review || '待审核';
              return (
                <article
                  key={creator.id}
                  className={`creator-audit-row ${isActive ? 'is-active' : ''}`}
                  onClick={() => setActiveId(creator.id)}
                >
                  <label className="creator-audit-check" onClick={event => event.stopPropagation()}>
                    <input type="checkbox" checked={selectedIds.includes(creator.id)} onChange={() => toggleCreator(creator.id)} />
                  </label>
                  <div className="creator-audit-profile">
                    {avatarUrl ? <img src={avatarUrl} alt={creator.name} /> : <div>{creator.name[0]}</div>}
                    <div>
                      {getPgyUrl(creator) ? (
                        <a href={getPgyUrl(creator)} target="_blank" rel="noreferrer" onClick={event => event.stopPropagation()}>
                          {creator.name}<ExternalLink size={12} />
                        </a>
                      ) : (
                        <strong>{creator.name}</strong>
                      )}
                      <span>{getCreatorLocation(creator)} · {creator.followers || '粉丝待补'} · {creator.quote || '报价待补'}</span>
                      <small>{getCreatorXhsId(creator)}</small>
                    </div>
                  </div>
                  <div className="creator-audit-match">
                    <strong style={{ color: getScoreColor(match.matchScore) }}>{match.matchScore}%</strong>
                    <Badge variant={match.matchScore >= 85 ? 'green' : match.matchScore >= 70 ? 'blue' : match.matchScore >= 55 ? 'amber' : 'red'}>{match.tier}</Badge>
                    <span>{tier.label} · {creator.baseScore}分</span>
                  </div>
                  <div className="creator-audit-reason">
                    <div className="creator-audit-reason-grid">
                      {match.reasonSections.slice(0, 2).map(section => (
                        <span key={section.title}><strong>{section.title}</strong>{section.text}</span>
                      ))}
                    </div>
                  </div>
                  <div className="creator-audit-actions">
                    <div className="creator-audit-row-status">
                      <Badge variant={getReviewVariant(reviewStatus)}>{reviewStatus}</Badge>
                      {creator.reviewedAt && <span>{creator.reviewer || '当前用户'} · {creator.reviewedAt}</span>}
                    </div>
                    <button
                      className="btn btn-sm btn-primary"
                      onClick={(event) => runCreatorReviewAction(event, creator, '已通过', `审号通过，匹配度 ${match.matchScore}%`)}
                      disabled={isReviewing}
                      title="通过该达人"
                    >
                      <UserCheck size={13} />通过
                    </button>
                    <button
                      className="btn btn-sm btn-secondary"
                      onClick={(event) => runCreatorReviewAction(event, creator, '备选', `审号备选，匹配度 ${match.matchScore}%`)}
                      disabled={isReviewing}
                      title="将该达人加入备选"
                    >
                      <Bookmark size={13} />备选
                    </button>
                    <button
                      className="btn btn-sm btn-danger"
                      onClick={(event) => runCreatorReviewAction(event, creator, '已驳回', `审号淘汰，匹配度 ${match.matchScore}%`)}
                      disabled={isReviewing}
                      title="淘汰该达人"
                    >
                      <UserX size={13} />淘汰
                    </button>
                    <button className="btn btn-sm btn-secondary" onClick={(event) => { event.stopPropagation(); collectForCreators([creator], creator.name); }} disabled={busy}>
                      <FileText size={13} />补采
                    </button>
                    <button className="btn btn-sm btn-primary" onClick={(event) => { event.stopPropagation(); openInviteModal([creator], '审号工作台单个邀约'); }} disabled={busy || !onPgyInvite}>
                      <Send size={13} />邀约
                    </button>
                    <button className="btn btn-sm btn-ghost" onClick={(event) => { event.stopPropagation(); setActiveId(creator.id); }}>
                      <Eye size={13} />详情
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        <aside className="creator-audit-detail">
          {activeRow ? (
            <>
              <div className="creator-audit-detail-head">
                <div>
                  <span className="creator-audit-eyebrow">Match Detail</span>
                  <h3>{activeRow.creator.name}</h3>
                  <p>{getCreatorIntro(activeRow.creator)}</p>
                </div>
                <div className="creator-audit-detail-score" style={{ color: getScoreColor(activeRow.match.matchScore) }}>
                  {activeRow.match.matchScore}%
                </div>
              </div>

              <div className="creator-audit-standard-strip">
                {(criteria.hardFilters.length ? criteria.hardFilters : ['达人性别/人设匹配', '内容场景匹配', '合作笔记表现']).slice(0, 4).map(item => (
                  <span key={item}>{item}</span>
                ))}
              </div>

              <div className="creator-audit-note-grid">
                {activeRow.match.noteCases.slice(0, 6).map((note, index) => {
                  const tone = analyzeNoteTone(note, project, activeRow.creator);
                  return (
                  <button
                    type="button"
                    className="creator-audit-note"
                    key={`${note.title}-${index}`}
                    onClick={() => openNoteModal(note, activeRow.creator, activeRow.match)}
                    title="打开笔记详情并解析小红书链接"
                  >
                    <div className="creator-audit-note-cover">
                      {note.coverUrl ? <img src={note.coverUrl} alt={note.title} /> : <span>{note.brand.slice(0, 2)}</span>}
                      {note.promoted && <Badge variant="green">投流</Badge>}
                      <i><MousePointerClick size={13} />详情</i>
                    </div>
                    <div className="creator-audit-note-body">
                      <strong>{note.title}</strong>
                      <span>{note.brand} · {note.publishedAt || '时间待补'}</span>
                      <div>
                        {note.readCount && <em>读 {compactNumber(note.readCount)}</em>}
                        {note.likeCount && <em>赞 {compactNumber(note.likeCount)}</em>}
                        {note.saveCount && <em>藏 {compactNumber(note.saveCount)}</em>}
                      </div>
                      {noteMedianComparisonText(note) && (
                        <small className={note.hasClearMedianContrast ? 'is-strong' : ''}>{noteMedianComparisonText(note)}</small>
                      )}
                      <small className={`creator-audit-note-tone is-${tone.verdict === '符合' ? 'fit' : tone.verdict === '部分符合' ? 'partial' : 'risk'}`}>
                        {tone.verdict} · {tone.score}%
                      </small>
                    </div>
                  </button>
                  );
                })}
              </div>

              <div className="creator-audit-analysis">
                <div>
                  <h4>深度推荐理由</h4>
                  <div className="creator-audit-deep-reason">
                    {activeRow.match.reasonSections.map(section => (
                      <div key={section.title}>
                        <strong>{section.title}</strong>
                        <p>{section.text}</p>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <h4>维度拆解</h4>
                  {activeRow.creator.scores ? Object.entries(activeRow.creator.scores).map(([key, value]) => (
                    <div className="creator-audit-dim" key={key}>
                      <span>{scoreDimLabels[key] || key}</span>
                      <div><i style={{ width: `${Math.max(0, Math.min(100, Number(value) || 0))}%`, background: getScoreColor(Number(value) || 0) }} /></div>
                      <strong>{value}</strong>
                    </div>
                  )) : <p>待重新匹配后生成维度拆解。</p>}
                </div>
                <div>
                  <h4>命中与风险</h4>
                  <div className="creator-audit-chip-list">
                    {activeRow.match.matchedSignals.map(item => <span className="tag" key={item}>{item}</span>)}
                    {activeRow.match.riskSignals.map(item => <span className="tag creator-audit-risk" key={item}>{item}</span>)}
                  </div>
                </div>
              </div>

              <div className="creator-audit-detail-actions">
                <button className="btn btn-primary" onClick={() => updateReview(activeRow.creator, '已通过', `审号通过，匹配度 ${activeRow.match.matchScore}%`)}>
                  <UserCheck size={14} />通过
                </button>
                <button className="btn btn-secondary" onClick={() => updateReview(activeRow.creator, '备选', `审号备选，匹配度 ${activeRow.match.matchScore}%`)}>
                  <Bookmark size={14} />备选
                </button>
                <button className="btn btn-danger" onClick={() => updateReview(activeRow.creator, '已驳回', `审号驳回，匹配度 ${activeRow.match.matchScore}%`)}>
                  <UserX size={14} />驳回
                </button>
                {getPgyUrl(activeRow.creator) && (
                  <a className="btn btn-secondary" href={getPgyUrl(activeRow.creator)} target="_blank" rel="noreferrer">
                    <ExternalLink size={14} />蒲公英
                  </a>
                )}
                <button className="btn btn-primary" onClick={() => openInviteModal([activeRow.creator], '达人详情邀约')} disabled={!onPgyInvite}>
                  <Send size={14} />邀约
                </button>
              </div>
            </>
          ) : (
            <div className="creator-audit-empty">暂无达人</div>
          )}
        </aside>
      </div>
      {inviteModal && (
        <PgyInviteModal
          isOpen
          creators={inviteModal.creators}
          project={project}
          source={inviteModal.source}
          onClose={() => setInviteModal(null)}
          onSubmit={submitInvite}
        />
      )}
      {noteModal && (
        <div className="creator-audit-note-modal" onClick={() => setNoteModal(null)}>
          <section className="creator-audit-note-panel" onClick={event => event.stopPropagation()}>
            <div className="creator-audit-note-panel-head">
              <div>
                <span className="creator-audit-eyebrow">笔记详情</span>
                <h3>{noteModal.note.title}</h3>
                <p>{noteModal.creator.name} · {noteModal.note.brand} · {noteModal.note.publishedAt || '发布时间待补'}</p>
              </div>
              <button className="creator-audit-back" type="button" onClick={() => setNoteModal(null)} title="关闭">
                <X size={17} />
              </button>
            </div>
            <div className="creator-audit-note-panel-body">
              <div className="creator-audit-note-preview">
                <div>
                  {noteModal.note.coverUrl ? <img src={noteModal.note.coverUrl} alt={noteModal.note.title} /> : <span>{noteModal.note.brand.slice(0, 2)}</span>}
                </div>
                <p>{noteModal.note.summary || noteModal.match.reason || '当前只采集到封面、标题和基础互动数据，接入真实解析后会展示正文、话题、评论精选与组件数据。'}</p>
              </div>
              <div className="creator-audit-note-side">
                <div className="creator-audit-link-box">
                  <div>
                    <Link size={14} />
                    <strong>小红书链接</strong>
                  </div>
                  <code>{noteModal.link}</code>
                  <button className="btn btn-sm btn-secondary" onClick={() => copyNoteLink(noteModal.link)}>
                    <Copy size={13} />复制链接
                  </button>
                </div>
                <div className="creator-audit-tone-card">
                  <div className="creator-audit-tone-score">
                    <strong>{noteModal.tone.score}%</strong>
                    <Badge variant={noteModal.tone.verdict === '符合' ? 'green' : noteModal.tone.verdict === '部分符合' ? 'amber' : 'red'}>{noteModal.tone.verdict}</Badge>
                  </div>
                  <div className="creator-audit-evidence-row">
                    {noteModal.tone.evidenceSources.map(item => <span key={item}>{item}</span>)}
                  </div>
                  <p>{noteModal.tone.reason}</p>
                  <div className="creator-audit-tone-list">
                    {noteModal.tone.matched.map(item => <span className="tag" key={item}>{item}</span>)}
                    {noteModal.tone.risks.map(item => <span className="tag creator-audit-risk" key={item}>{item}</span>)}
                  </div>
                </div>
                <div className="creator-audit-parse-card">
                  <div><Database size={14} /><strong>解析端口</strong></div>
                  <p>{parsingNote ? '正在请求 /api/xhs/notes/parse ...' : (noteParseResult?.message || '当前只分析标题、封面、评论区和基础互动数；完整正文后续再接入。')}</p>
                  <pre>{JSON.stringify(noteParseResult || { endpoint: '/api/xhs/notes/parse', status: 'pending' }, null, 2)}</pre>
                </div>
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
