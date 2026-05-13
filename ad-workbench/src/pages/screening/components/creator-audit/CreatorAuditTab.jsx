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
                {activeRow.match.noteCases.slice(0, 6).map((note, index) => (
                  <div className="creator-audit-note" key={`${note.title}-${index}`}>
                    <div className="creator-audit-note-cover">
                      {note.coverUrl ? <img src={note.coverUrl} alt={note.title} /> : <span>{note.brand.slice(0, 2)}</span>}
                      {note.promoted && <Badge variant="green">投流</Badge>}
                    </div>
                    <div className="creator-audit-note-body">
                      <strong>{note.link ? <a href={note.link} target="_blank" rel="noreferrer" onClick={event => event.stopPropagation()}>{note.title}<ExternalLink size={11} /></a> : note.title}</strong>
                      <span>{note.brand} · {note.publishedAt || '时间待补'}</span>
                      <div>
                        {note.readCount && <em>读 {compactNumber(note.readCount)}</em>}
                        {note.likeCount && <em>赞 {compactNumber(note.likeCount)}</em>}
                        {note.saveCount && <em>藏 {compactNumber(note.saveCount)}</em>}
                      </div>
                      {noteMedianComparisonText(note) && (
                        <small className={note.hasClearMedianContrast ? 'is-strong' : ''}>{noteMedianComparisonText(note)}</small>
                      )}
                    </div>
                  </div>
                ))}
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
    </div>
  );
}
