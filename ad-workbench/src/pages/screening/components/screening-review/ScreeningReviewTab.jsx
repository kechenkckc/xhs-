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
import { DEFAULT_SCORING_HARD_FILTER_FIELDS, hardFilterKey, hardFilterLabel } from '../../constants/screeningConstants';
import { getProjectCreators, getCreatorStatus, getDefaultCreatorStatus } from '../../utils/projectMappers';
import { getReviewVariant, getScoreColor, getScoreTier } from '../../utils/creatorScoring';
import { mergeOptionItems } from '../../utils/pgyFilters';
import { hardFilterOptionsFor, normalizeWorkbenchPlan, syncScreeningCriteria } from '../../utils/screeningPlan';
import { getCreatorAvatarUrl, getPgyUrl } from '../../utils/creatorMappers';
import { SelectedChips } from '../filters/SelectedChips';
import { HardFilterCheckPanel } from '../filters/HardFilterCheckPanel';
import { CreatorDetailModal } from './CreatorDetailModal';
import { PgyInviteModal } from '../pgy-invite/PgyInviteModal';

export function ScreeningReviewTab({ project, screeningStatus, setScreeningStatus, onReview, onRefresh, onScore, onImport, onCollect, onCollectDetails, onPgyInvite, onSavePlan, onTabChange }) {
  const creators = useMemo(() => getProjectCreators(project).map(c => ({
    ...getDefaultCreatorStatus(), ...c, ...(getCreatorStatus(project.id, c.id, screeningStatus) || {})
  })), [project, screeningStatus]);
  const screeningCandidates = useMemo(
    () => creators.filter(c => !['已通过', '已写回飞书', '已驳回', '默认淘汰', '备选'].includes(c.review)),
    [creators]
  );

  const [statusFilter, setStatusFilter] = useState('全部');
  const [tierFilter, setTierFilter] = useState('S');
  const [typeFilter, setTypeFilter] = useState('全部');
  const [searchTerm, setSearchTerm] = useState('');
  const [sortField, setSortField] = useState('baseScore');
  const [sortDir, setSortDir] = useState('desc');
  const [selectedIds, setSelectedIds] = useState([]);
  const [expandedId, setExpandedId] = useState(null);
  const [detailModalCreator, setDetailModalCreator] = useState(null);
  const [reviewModal, setReviewModal] = useState(null); // { creator, action }
  const [batchModal, setBatchModal] = useState(null); // { action, creators }
  const [inviteModal, setInviteModal] = useState(null); // { creators, source }
  const [reviewComment, setReviewComment] = useState('');
  const [planDraft, setPlanDraft] = useState(() => normalizeWorkbenchPlan(project.screeningPlan || {}));
  const [planExpanded, setPlanExpanded] = useState(false);
  const [planStatus, setPlanStatus] = useState('');

  useEffect(() => {
    setPlanDraft(normalizeWorkbenchPlan(project.screeningPlan || {}));
    setPlanStatus('');
  }, [project.id, project.screeningPlan]);

  useEffect(() => {
    setSelectedIds([]);
  }, [statusFilter, tierFilter, typeFilter, searchTerm]);

  const filtered = useMemo(() => {
    let list = [...screeningCandidates];
    if (statusFilter !== '全部') list = list.filter(c => c.review === statusFilter);
    list = list.filter(c => getScoreTier(c.baseScore).key === tierFilter);
    if (typeFilter !== '全部') list = list.filter(c => c.type === typeFilter);
    if (searchTerm) list = list.filter(c => c.name.includes(searchTerm));
    list.sort((a, b) => {
      const av = a[sortField], bv = b[sortField];
      if (typeof av === 'number' && typeof bv === 'number') return sortDir === 'desc' ? bv - av : av - bv;
      return sortDir === 'desc' ? String(bv).localeCompare(String(av)) : String(av).localeCompare(String(bv));
    });
    return list;
  }, [screeningCandidates, statusFilter, tierFilter, typeFilter, searchTerm, sortField, sortDir]);

  const stats = useMemo(() => {
    const s = {
      total: screeningCandidates.length,
      passed: creators.filter(c => ['已通过', '已写回飞书'].includes(c.review)).length,
      rejected: creators.filter(c => ['已驳回', '默认淘汰'].includes(c.review)).length,
      backup: 0,
      review: 0,
      pending: 0,
    };
    screeningCandidates.forEach(c => {
      if (c.review === '备选') s.backup++;
      else if (c.review === '人工复核') s.review++;
      else s.pending++;
    });
    return s;
  }, [creators.length, screeningCandidates]);

  const tierStats = useMemo(() => {
    const tiers = {
      S: { label: 'S档', desc: '100分以上，必须补采', count: 0, variant: 'green', color: '#10B981' },
      A: { label: 'A档', desc: '90-99分，优先补采', count: 0, variant: 'blue', color: '#3B82F6' },
      'B+': { label: 'B+档', desc: '80-89分，高潜补采', count: 0, variant: 'amber', color: '#F59E0B' },
      B: { label: 'B档', desc: '70-79分，暂缓补采', count: 0, variant: 'amber', color: '#D97706' },
      C: { label: 'C档', desc: '70分以下，不补采', count: 0, variant: 'red', color: '#EF4444' },
    };
    screeningCandidates.forEach(creator => {
      const tier = getScoreTier(creator.baseScore).key;
      tiers[tier].count += 1;
    });
    return tiers;
  }, [screeningCandidates]);
  const activeTier = tierStats[tierFilter] || null;
  const savedPlan = useMemo(() => normalizeWorkbenchPlan(project.screeningPlan || {}), [project.screeningPlan]);
  const planDirty = JSON.stringify(planDraft.scoringHardFilters || []) !== JSON.stringify(savedPlan.scoringHardFilters || []);
  const scoringHardFilterOptions = useMemo(
    () => mergeOptionItems(planDraft.scoringHardFilters || [], hardFilterOptionsFor(DEFAULT_SCORING_HARD_FILTER_FIELDS), hardFilterKey),
    [planDraft.scoringHardFilters]
  );
  const scoringPlanSummary = `${planDraft.scoringHardFilters?.length || 0} 个评分条件`;

  const applyLocalReviewStatus = (targetCreators, review, reviewVariant, fallbackReason) => {
    const now = new Date().toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-');
    setScreeningStatus(prev => {
      const next = { ...prev, [project.id]: { ...(prev[project.id] || {}) } };
      targetCreators.forEach(creator => {
        next[project.id][creator.id] = {
          review,
          reviewVariant,
          finalScore: creator.baseScore,
          reason: reviewComment || fallbackReason,
          reviewer: '当前用户',
          reviewedAt: now,
        };
      });
      return next;
    });
  };

  const handleReview = async (creator, action) => {
    const status = action === 'pass' ? '已通过' : action === 'reject' ? '已驳回' : action === 'backup' ? '备选' : '待审核';
    const variant = action === 'pass' ? 'green' : action === 'reject' ? 'red' : 'amber';
    const reason = reviewComment || (action === 'pass' ? '人工审核通过' : action === 'reject' ? '人工审核驳回' : '加入备选');
    applyLocalReviewStatus([creator], status, variant, reason);
    if (onReview) {
      await onReview([creator.id], status, reason);
      setReviewModal(null);
      setReviewComment('');
      return;
    }
    setReviewModal(null);
    setReviewComment('');
  };

  const handleBatchPass = async () => {
    const selectedCreators = creators.filter(c => selectedIds.includes(c.id));
    if (!selectedCreators.length) return;
    const reason = reviewComment || '批量通过，进入项目达人池';
    applyLocalReviewStatus(selectedCreators, '已通过', 'green', reason);
    if (onReview) {
      await onReview(selectedCreators.map(c => c.id), '已通过', reason);
      setBatchModal(null);
      setReviewComment('');
      setSelectedIds([]);
      return;
    }
    setBatchModal(null);
    setReviewComment('');
    setSelectedIds([]);
  };

  const handleBatchReject = async () => {
    const selectedCreators = creators.filter(c => selectedIds.includes(c.id));
    if (!selectedCreators.length) return;
    const reason = reviewComment || '批量淘汰，进入观察暂缓池';
    applyLocalReviewStatus(selectedCreators, '已驳回', 'red', reason);
    if (onReview) {
      await onReview(selectedCreators.map(c => c.id), '已驳回', reason);
      setBatchModal(null);
      setReviewComment('');
      setSelectedIds([]);
      return;
    }
    setBatchModal(null);
    setReviewComment('');
    setSelectedIds([]);
  };

  const openBatchModal = (action) => {
    const selectedCreators = creators.filter(c => selectedIds.includes(c.id));
    if (!selectedCreators.length) return;
    setBatchModal({ action, creators: selectedCreators });
    setReviewComment(action === 'pass' ? '批量通过，进入项目达人池' : '批量淘汰，进入观察暂缓池');
  };

  const openInviteModal = (targetCreators, source = '初筛找博主列表') => {
    const validCreators = (targetCreators || []).filter(Boolean);
    if (!validCreators.length) return;
    setInviteModal({ creators: validCreators, source });
  };

  const markInvitedLocally = (targetCreators, form) => {
    const now = new Date().toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-');
    const reason = `蒲公英邀约：${form.brandName} · ${form.productName} · ${form.cooperationType}`;
    setScreeningStatus(prev => {
      const next = { ...prev, [project.id]: { ...(prev[project.id] || {}) } };
      targetCreators.forEach(creator => {
        next[project.id][creator.id] = {
          review: '已邀约',
          reviewVariant: 'blue',
          finalScore: creator.baseScore,
          reason,
          reviewer: '当前用户',
          reviewedAt: now,
        };
      });
      return next;
    });
  };

  const submitInvite = async (form) => {
    const targetCreators = inviteModal?.creators || [];
    const payload = await onPgyInvite?.(targetCreators.map(creator => creator.id), form);
    markInvitedLocally(targetCreators, form);
    setSelectedIds(ids => ids.filter(id => !targetCreators.some(creator => creator.id === id)));
    return payload;
  };

  const handleCollectCurrentTierDetails = () => {
    if (!filtered.length || !onCollectDetails) return;
    const segmentLabel = activeTier?.label || `${tierFilter}档`;
    onCollectDetails({
      creatorIds: filtered.map(creator => creator.id),
      segment: tierFilter,
      segmentLabel,
    });
  };

  const saveScoringPlan = async (runScore = false) => {
    setPlanStatus(runScore ? '正在保存评分筛选条件并重新评分...' : '正在保存评分筛选条件...');
    try {
      const nextPlan = syncScreeningCriteria(planDraft);
      await onSavePlan?.(nextPlan);
      setPlanDraft(normalizeWorkbenchPlan(nextPlan));
      if (runScore) {
        await onScore?.();
        setPlanStatus('评分筛选条件已保存，并已触发重新评分');
      } else {
        setPlanStatus('评分筛选条件已保存，并同步到项目配置');
      }
    } catch (error) {
      setPlanStatus(error.message || '评分筛选条件保存失败');
    }
  };

  const toggleSelectCreator = (creatorId) => {
    setSelectedIds(ids => ids.includes(creatorId) ? ids.filter(id => id !== creatorId) : [...ids, creatorId]);
  };

  const filteredIds = filtered.map(creator => creator.id);
  const allFilteredSelected = filteredIds.length > 0 && filteredIds.every(id => selectedIds.includes(id));
  const toggleSelectFiltered = () => {
    setSelectedIds(ids => {
      if (allFilteredSelected) return ids.filter(id => !filteredIds.includes(id));
      return Array.from(new Set([...ids, ...filteredIds]));
    });
  };

  const toggleSort = (field) => {
    if (sortField === field) setSortDir(d => d === 'desc' ? 'asc' : 'desc');
    else { setSortField(field); setSortDir('desc'); }
  };

  const SortIcon = ({ field }) => {
    if (sortField !== field) return <ChevronDown size={12} style={{ color: 'var(--text-muted)', marginLeft: 2 }} />;
    return sortDir === 'desc' ? <ChevronDown size={12} style={{ color: '#3B82F6', marginLeft: 2 }} /> : <ChevronUp size={12} style={{ color: '#3B82F6', marginLeft: 2 }} />;
  };

  const renderCreatorAvatar = (creator, size = 32) => {
    const avatarUrl = getCreatorAvatarUrl(creator);
    const style = {
      width: size,
      height: size,
      borderRadius: '50%',
      background: '#243147',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: size >= 40 ? 16 : 13,
      color: '#FFFFFF',
      fontWeight: 600,
      flexShrink: 0,
      objectFit: 'cover',
    };
    return avatarUrl ? <img src={avatarUrl} alt={creator.name} style={style} /> : <div style={style}>{creator.name?.[0] || '达'}</div>;
  };

  const renderCreatorName = (creator, style = {}) => {
    const pgyUrl = getPgyUrl(creator);
    if (!pgyUrl) return <div style={style}>{creator.name}</div>;
    return (
      <a
        href={pgyUrl}
        target="_blank"
        rel="noreferrer"
        onClick={event => event.stopPropagation()}
        style={{ ...style, display: 'inline-flex', alignItems: 'center', gap: 4, textDecoration: 'none' }}
        title="打开蒲公英主页"
      >
        {creator.name}<ExternalLink size={12} />
      </a>
    );
  };

  const scoreDimLabels = { budget: '预算匹配', fans: '粉丝量级', cpe: 'CPE效率', engagement: '互动质量', persona: '人设匹配', content: '内容风格' };

  return (
    <div>
      <div className="screening-workbench-hero" style={{ marginBottom: 20 }}>
        <div>
          <div className="screening-workbench-eyebrow">Scoring & Human Review</div>
          <h3>筛选工作台</h3>
          <p>展示采集后的初步评分结果，按基础分100+加成分20分层，只让高分/高潜达人进入详情页补采。</p>
        </div>
        <button className="btn btn-primary" onClick={() => onTabChange?.('score-preview')}>
          <Users size={14} />查看项目达人池
        </button>
      </div>

      <div className="screening-tier-grid" style={{ marginBottom: 20 }}>
        {Object.entries(tierStats).map(([key, item]) => (
          <button
            key={key}
            type="button"
            className={`screening-tier-card ${tierFilter === key ? 'is-active' : ''}`}
            onClick={() => setTierFilter(key)}
          >
            <div>
              <Badge variant={item.variant}>{item.label}</Badge>
              <p>{item.desc}</p>
            </div>
            <strong style={{ color: item.color }}>{item.count}</strong>
          </button>
        ))}
      </div>

      <div className="card screening-section-card collection-plan-panel" style={{ marginBottom: 16 }}>
        <div className="collection-plan-collapsible-header">
          <button type="button" className="collection-plan-collapse-button" onClick={() => setPlanExpanded(value => !value)}>
            <Shield size={16} />
            <span>评分筛选条件</span>
            <small>{scoringPlanSummary}</small>
            <ChevronDown size={16} className={planExpanded ? 'is-open' : ''} />
          </button>
          <div className="collection-plan-header-badges">
            {planDirty && <Badge variant="purple">未应用</Badge>}
          </div>
        </div>
        {!planExpanded ? (
          <div className="collection-plan-compact">
            <SelectedChips
              items={(planDraft.scoringHardFilters || []).slice(0, 4)}
              getKey={hardFilterKey}
              getLabel={hardFilterLabel}
              onRemove={(item) => setPlanDraft(old => ({ ...old, scoringHardFilters: (old.scoringHardFilters || []).filter(next => hardFilterKey(next) !== hardFilterKey(item)) }))}
              emptyText="暂无评分筛选条件"
            />
            {(planDraft.scoringHardFilters || []).length > 4 && <span className="collection-compact-more">+{(planDraft.scoringHardFilters || []).length - 4}</span>}
          </div>
        ) : (
          <div className="collection-plan-block">
            <div className="collection-plan-title-row">
              <div>
                <div className="collection-plan-title">评分硬性条件</div>
                <div className="collection-plan-subtitle">用于初筛评分、硬性不符判断和 AI 推荐理由，不影响蒲公英页面采集条件。</div>
              </div>
            </div>
            <HardFilterCheckPanel
              filters={planDraft.scoringHardFilters || []}
              options={scoringHardFilterOptions}
              onChange={(filters) => {
                setPlanStatus('');
                setPlanDraft(old => ({ ...old, scoringHardFilters: filters }));
              }}
              emptyText="暂无评分筛选条件，可从可选项添加。"
            />
          </div>
        )}
        <div className="collection-plan-actions">
          <span className={planStatus.includes('失败') ? 'is-error' : ''}>{planStatus || '平时折叠；修改后保存，重新评分会使用当前条件。'}</span>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button className="btn btn-secondary" onClick={() => saveScoringPlan(false)} disabled={!planDirty && planStatus.includes('已保存')}>
              <Save size={14} style={{ marginRight: 4 }} />保存条件
            </button>
            <button className="btn btn-primary" onClick={() => saveScoringPlan(true)}>
              <Sparkles size={14} style={{ marginRight: 4 }} />保存并重新评分
            </button>
          </div>
        </div>
      </div>

      {/* 工具栏 */}
      <div className="card" style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <div className="search-box" style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input className="search-input" placeholder="搜索达人..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)} style={{ paddingLeft: 30, width: 160 }} />
          </div>
          <select className="select-field" style={{ width: 120 }} value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
            <option value="全部">全部状态</option>
            <option value="待审核">待审核</option>
            <option value="已通过">已通过</option>
            <option value="已驳回">已驳回</option>
            <option value="备选">备选</option>
            <option value="人工复核">人工复核</option>
          </select>
          <select className="select-field" style={{ width: 110 }} value={tierFilter} onChange={e => setTierFilter(e.target.value)}>
            <option value="S">S档</option>
            <option value="A">A档</option>
            <option value="B+">B+档</option>
            <option value="B">B档</option>
            <option value="C">C档</option>
          </select>
          <select className="select-field" style={{ width: 100 }} value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
            <option value="全部">全部类型</option>
            <option value="KOL">KOL</option>
            <option value="KOC">KOC</option>
          </select>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-sm btn-secondary" onClick={onImport}><Upload size={14} style={{ marginRight: 4 }} />导入模板</button>
          <button className="btn btn-sm btn-secondary" onClick={onCollect}><Bot size={14} style={{ marginRight: 4 }} />蒲公英采集</button>
          <button className="btn btn-sm btn-secondary" onClick={onScore}><Sparkles size={14} style={{ marginRight: 4 }} />重新评分</button>
          <button
            className="btn btn-sm btn-primary"
            onClick={() => openInviteModal(creators.filter(c => selectedIds.includes(c.id)), '初筛找博主批量邀约')}
            disabled={!selectedIds.length || !onPgyInvite}
            title="通过蒲公英邀约通道批量发起合作"
          >
            <Send size={14} style={{ marginRight: 4 }} />批量邀约{selectedIds.length ? ` ${selectedIds.length}` : ''}
          </button>
          <button
            className="btn btn-sm btn-primary"
            onClick={handleCollectCurrentTierDetails}
            disabled={!filtered.length}
            title={`批量完善当前${activeTier?.label || tierFilter}分段的达人详情页`}
          >
            <FileText size={14} style={{ marginRight: 4 }} />完善{activeTier?.label || tierFilter}{filtered.length ? ` ${filtered.length}` : ''}
          </button>
          <button className="btn btn-sm btn-ghost" onClick={onRefresh}><RefreshCw size={14} /></button>
          <button className="btn btn-sm btn-secondary" onClick={() => openBatchModal('pass')} disabled={!selectedIds.length} title="批量通过当前勾选达人"><UserCheck size={14} style={{ marginRight: 4 }} />批量通过{selectedIds.length ? ` ${selectedIds.length}` : ''}</button>
          <button className="btn btn-sm btn-danger" onClick={() => openBatchModal('reject')} disabled={!selectedIds.length} title="批量淘汰当前勾选达人"><UserX size={14} style={{ marginRight: 4 }} />批量淘汰{selectedIds.length ? ` ${selectedIds.length}` : ''}</button>
        </div>
      </div>

      {/* 达人列表 */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-primary)' }}>
              <th style={{ padding: '12px 8px 12px 16px', width: 42, textAlign: 'center' }}>
                <input
                  type="checkbox"
                  checked={allFilteredSelected}
                  disabled={!filtered.length}
                  onChange={toggleSelectFiltered}
                  aria-label="选择当前列表达人"
                />
              </th>
              <th style={{ padding: '12px 16px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>达人</th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>类型</th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12, cursor: 'pointer' }} onClick={() => toggleSort('followersNum')}>粉丝数 <SortIcon field="followersNum" /></th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12, cursor: 'pointer' }} onClick={() => toggleSort('quoteNum')}>报价 <SortIcon field="quoteNum" /></th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12, cursor: 'pointer' }} onClick={() => toggleSort('baseScore')}>初筛总分 <SortIcon field="baseScore" /></th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>档位</th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>风险</th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>审核状态</th>
              <th style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>审核意见</th>
              <th style={{ padding: '12px 16px', textAlign: 'center', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(creator => (
              <React.Fragment key={creator.id}>
                <tr style={{ borderBottom: '1px solid var(--border-primary)', cursor: 'pointer', transition: 'background 0.15s' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                  <td style={{ padding: '12px 8px 12px 16px', textAlign: 'center' }}>
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(creator.id)}
                      onChange={() => toggleSelectCreator(creator.id)}
                      onClick={e => e.stopPropagation()}
                      aria-label={`选择${creator.name}`}
                    />
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      {renderCreatorAvatar(creator)}
                      <div>
                        {renderCreatorName(creator, { color: 'var(--text-primary)', fontWeight: 600 })}
                        <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>ID: {creator.id}</div>
                      </div>
                    </div>
                  </td>
                  <td style={{ padding: '12px' }}><Badge variant={creator.typeVariant}>{creator.type}</Badge></td>
                  <td style={{ padding: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>{creator.followers}</td>
                  <td style={{ padding: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>{creator.quote}</td>
                  <td style={{ padding: '12px' }}>
                    <span style={{ fontWeight: 700, fontSize: 15, color: getScoreColor(creator.baseScore) }}>{creator.baseScore}</span>
                    <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>
                      基础 {creator.baseOnlyScore || 0} + 加成 {creator.bonusScore || 0} · 完整度 {creator.informationCompletenessLabel}
                    </span>
                  </td>
                  <td style={{ padding: '12px' }}>
                    {(() => {
                      const tier = getScoreTier(creator.baseScore);
                      return <Badge variant={tier.variant}>{tier.label} · {tier.text}</Badge>;
                    })()}
                    {creator.detailCollectionPriority && <Badge variant="default">{creator.detailCollectionPriority}</Badge>}
                  </td>
                  <td style={{ padding: '12px' }}>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {(creator.risk || []).map((t, i) => <span key={i} className="tag" style={{ fontSize: 10, color: t.includes('无') || t.includes('低') || t.includes('过多') || t.includes('低') ? '#EF4444' : '#F59E0B' }}>{t}</span>)}
                    </div>
                  </td>
                  <td style={{ padding: '12px' }}><Badge variant={getReviewVariant(creator.review)}>{creator.review}</Badge></td>
                  <td style={{ padding: '12px', maxWidth: 140 }}>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{creator.reason || '-'}</div>
                    {creator.reviewer && <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{creator.reviewer} · {creator.reviewedAt}</div>}
                  </td>
                  <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                    <div style={{ display: 'flex', gap: 4, justifyContent: 'center' }}>
                      {creator.review === '待审核' ? (
                        <>
                          <button className="btn btn-sm btn-ghost" style={{ color: '#10B981' }} onClick={(e) => { e.stopPropagation(); setReviewModal({ creator, action: 'pass' }); }} title="通过"><UserCheck size={15} /></button>
                          <button className="btn btn-sm btn-ghost" style={{ color: '#EF4444' }} onClick={(e) => { e.stopPropagation(); setReviewModal({ creator, action: 'reject' }); }} title="驳回"><UserX size={15} /></button>
                          <button className="btn btn-sm btn-ghost" style={{ color: '#F59E0B' }} onClick={(e) => { e.stopPropagation(); setReviewModal({ creator, action: 'backup' }); }} title="备选"><Bookmark size={15} /></button>
                        </>
                      ) : (
                        <button className="btn btn-sm btn-ghost" style={{ color: 'var(--text-secondary)' }} onClick={(e) => { e.stopPropagation(); setReviewModal({ creator, action: 'reset' }); }} title="重置"><RotateCcw size={15} /></button>
                      )}
                      <button
                        className="btn btn-sm btn-secondary"
                        onClick={(e) => { e.stopPropagation(); setDetailModalCreator(creator); }}
                        title="查看详情"
                      >
                        详情
                      </button>
                      <button
                        className="btn btn-sm btn-secondary"
                        onClick={(e) => { e.stopPropagation(); openInviteModal([creator], '初筛找博主单个邀约'); }}
                        disabled={!onPgyInvite}
                        title="通过蒲公英邀约该达人"
                      >
                        邀约
                      </button>
                      <button className="btn btn-sm btn-ghost" onClick={(e) => { e.stopPropagation(); setExpandedId(expandedId === creator.id ? null : creator.id); }} title="展开评分">
                        <ChevronDown size={15} style={{ transform: expandedId === creator.id ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
                      </button>
                    </div>
                  </td>
                </tr>
                {expandedId === creator.id && (
                  <tr style={{ background: 'var(--bg-raised)' }}>
                    <td colSpan={11} style={{ padding: '16px 24px', borderBottom: '1px solid var(--border-primary)' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
                        {/* 评分维度 */}
                        <div>
                          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12, fontWeight: 600 }}>评分维度明细</div>
                          {creator.scores && Object.entries(creator.scores).map(([key, val]) => (
                            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                              <span style={{ fontSize: 12, color: 'var(--text-secondary)', width: 70, flexShrink: 0 }}>{scoreDimLabels[key] || key}</span>
                              <div style={{ flex: 1, height: 6, background: 'var(--bg-elevated)', borderRadius: 3, overflow: 'hidden' }}>
                                <div style={{ width: `${val}%`, height: '100%', background: getScoreColor(val), borderRadius: 3, transition: 'width 0.3s' }} />
                              </div>
                              <span style={{ fontSize: 12, fontWeight: 600, color: getScoreColor(val), width: 28, textAlign: 'right' }}>{val}</span>
                            </div>
                          ))}
                        </div>
                        {/* AI 推荐理由 */}
                        <div>
                          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12, fontWeight: 600 }}>AI 推荐理由</div>
                          <div style={{ padding: 12, background: 'var(--bg-secondary)', borderRadius: 8, borderLeft: '3px solid #8B5CF6' }}>
                            <p style={{ margin: 0, color: 'var(--text-primary)', fontSize: 13, lineHeight: 1.7 }}>{creator.aiReason || '暂无 AI 评估'}</p>
                          </div>
                          {(creator.risk || []).length > 0 && (
                            <div style={{ marginTop: 12 }}>
                              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>风险提示</div>
                              {(creator.risk || []).map((r, i) => (
                                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                                  <AlertTriangle size={12} style={{ color: '#F59E0B', flexShrink: 0 }} />
                                  <span style={{ fontSize: 12, color: 'var(--text-primary)' }}>{r}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-secondary)' }}>
            <Users size={32} style={{ marginBottom: 8 }} />
            <div>暂无匹配达人</div>
          </div>
        )}
        <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border-primary)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12, color: 'var(--text-secondary)' }}>
          <span>共 {filtered.length} 位达人，已勾选 {selectedIds.length} 位</span>
          <span>筛选自 {screeningCandidates.length} 位待筛候选，已入池 {stats.passed} 位</span>
        </div>
      </div>

      {/* 审核确认弹窗 */}
      {batchModal && (
        <div className="modal-overlay" onClick={() => setBatchModal(null)}>
          <div className="modal" style={{ maxWidth: 680 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>
                {batchModal.action === 'pass' ? '确认批量通过' : '确认批量淘汰'}
              </h3>
              <button className="btn btn-ghost btn-sm modal-close" onClick={() => setBatchModal(null)}><X size={16} /></button>
            </div>
            <div className="modal-body">
              <div style={{ marginBottom: 12, color: 'var(--text-secondary)', fontSize: 13 }}>
                本次将处理 {batchModal.creators.length} 位已勾选达人，确认后会从筛选工作台移出，并进入
                {batchModal.action === 'pass' ? '「项目达人池」' : '「观察暂缓」'}。
              </div>
              <div className="batch-review-list">
                {batchModal.creators.map(creator => {
                  const tier = getScoreTier(creator.baseScore);
                  return (
                    <div key={creator.id} className="batch-review-item">
                      <div className="batch-review-avatar">{getCreatorAvatarUrl(creator) ? <img src={getCreatorAvatarUrl(creator)} alt={creator.name} /> : creator.name[0]}</div>
                      <div className="batch-review-main">
                        {renderCreatorName(creator, { color: 'var(--text-primary)', fontWeight: 700 })}
                        <span>{creator.type} · {creator.followers} · {creator.quote}</span>
                      </div>
                      <Badge variant={tier.variant}>{tier.label}</Badge>
                      <span style={{ color: getScoreColor(creator.baseScore), fontWeight: 700 }}>{creator.baseScore}</span>
                    </div>
                  );
                })}
              </div>
              <div style={{ marginTop: 16 }}>
                <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>批量处理备注</label>
                <textarea className="input-field" rows={3} value={reviewComment} onChange={e => setReviewComment(e.target.value)} placeholder="请输入批量处理意见..." style={{ resize: 'none' }} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setBatchModal(null)}>取消</button>
              <button className={`btn ${batchModal.action === 'pass' ? 'btn-primary' : 'btn-danger'}`} onClick={batchModal.action === 'pass' ? handleBatchPass : handleBatchReject}>
                {batchModal.action === 'pass' ? '确认通过并移入达人池' : '确认淘汰并移入观察暂缓'}
              </button>
            </div>
          </div>
        </div>
      )}

      {reviewModal && (
        <div className="modal-overlay" onClick={() => setReviewModal(null)}>
          <div className="modal" style={{ maxWidth: 420 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>
                {reviewModal.action === 'pass' && '确认通过'}
                {reviewModal.action === 'reject' && '确认驳回'}
                {reviewModal.action === 'backup' && '加入备选'}
                {reviewModal.action === 'reset' && '重置审核'}
              </h3>
              <button className="btn btn-ghost btn-sm modal-close" onClick={() => setReviewModal(null)}><X size={16} /></button>
            </div>
            <div className="modal-body">
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, padding: 12, background: 'var(--bg-elevated)', borderRadius: 8 }}>
                {renderCreatorAvatar(reviewModal.creator, 40)}
                <div>
                  {renderCreatorName(reviewModal.creator, { color: 'var(--text-primary)', fontWeight: 500 })}
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{reviewModal.creator.type} · {reviewModal.creator.followers} · 初筛总分 {reviewModal.creator.baseScore}</div>
                </div>
              </div>
              <div>
                <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>审核备注</label>
                <textarea className="input-field" rows={3} value={reviewComment} onChange={e => setReviewComment(e.target.value)} placeholder="请输入审核意见..." style={{ resize: 'none' }} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setReviewModal(null)}>取消</button>
              {reviewModal.action === 'reset' ? (
                <button className="btn btn-primary" onClick={() => {
                  const newStatus = { ...screeningStatus };
                  if (newStatus[project.id]) delete newStatus[project.id][reviewModal.creator.id];
                  setScreeningStatus(newStatus);
                  setReviewModal(null);
                }}>确认重置</button>
              ) : (
                <button className={`btn ${reviewModal.action === 'pass' ? 'btn-primary' : reviewModal.action === 'reject' ? 'btn-danger' : 'btn-secondary'}`}
                  onClick={() => handleReview(reviewModal.creator, reviewModal.action)}>
                  {reviewModal.action === 'pass' ? '确认通过' : reviewModal.action === 'reject' ? '确认驳回' : '确认备选'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
      {detailModalCreator && (
        <CreatorDetailModal
          creator={detailModalCreator}
          project={project}
          onClose={() => setDetailModalCreator(null)}
          onCollectDetails={onCollectDetails}
          onInvite={(creator) => openInviteModal([creator], '达人详情邀约')}
        />
      )}
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
