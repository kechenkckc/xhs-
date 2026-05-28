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
import { getCreatorAvatarUrl, getCreatorDetailStatus, getCreatorDisplayId, getCreatorRealNoteCases, getPgyUrl, normalizeScoreTierKey } from '../../utils/creatorMappers';
import { getCreatorAdRecommendation, getCreatorDisplayTier, getCreatorLightProfile } from '../../utils/creatorScoring';
import { SelectedChips } from '../filters/SelectedChips';
import { HardFilterCheckPanel } from '../filters/HardFilterCheckPanel';
import { CreatorDetailModal } from './CreatorDetailModal';
import { PgyInviteModal } from '../pgy-invite/PgyInviteModal';
import { api } from '../../api/screeningApi';

function getInitialTier(creator) {
  if (creator.scorePending) return { key: '未评分', label: '未评分', variant: 'default', text: '待完成评分', color: '#64748B' };
  return getCreatorDisplayTier(creator);
}

function verdictVariant(value) {
  if (['强推荐', '推荐'].includes(value)) return value === '强推荐' ? 'green' : 'blue';
  if (['备选', '待人工确认'].includes(value)) return 'amber';
  if (['不推荐', 'Pass'].includes(value)) return 'red';
  return 'default';
}

function percentText(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return '待补';
  return `${Math.round(number * 100)}%`;
}

const REVIEW_DONE_STATUSES = ['已通过', '已写回飞书', '已驳回', '默认淘汰', '已废弃', '备选'];

export function ScreeningReviewTab({ project, screeningStatus, setScreeningStatus, onReview, onRefresh, onScore, onImport, onCollect, onCollectDetails, onPgyInvite, onSavePlan, onTabChange }) {
  const pageSize = 50;
  const creators = useMemo(() => getProjectCreators(project).map(c => ({
    ...getDefaultCreatorStatus(), ...c, ...(getCreatorStatus(project.id, c.id, screeningStatus) || {})
  })), [project, screeningStatus]);
  const screeningCandidates = useMemo(
    () => creators.filter(c => !REVIEW_DONE_STATUSES.includes(c.review)),
    [creators]
  );

  const [statusFilter, setStatusFilter] = useState('全部');
  const [tierFilter, setTierFilter] = useState('全部');
  const [typeFilter, setTypeFilter] = useState('全部');
  const [recommendFilter, setRecommendFilter] = useState('全部');
  const [stagePriorityFilter, setStagePriorityFilter] = useState('全部');
  const [searchTerm, setSearchTerm] = useState('');
  const [sortField, setSortField] = useState('baseScore');
  const [sortDir, setSortDir] = useState('desc');
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState([]);
  const [expandedId, setExpandedId] = useState(null);
  const [detailModalCreator, setDetailModalCreator] = useState(null);
  const [detailLoadStatus, setDetailLoadStatus] = useState('');
  const [reviewModal, setReviewModal] = useState(null); // { creator, action }
  const [batchModal, setBatchModal] = useState(null); // { action, creators }
  const [inviteModal, setInviteModal] = useState(null); // { creators, source }
  const [reviewComment, setReviewComment] = useState('');
  const [planDraft, setPlanDraft] = useState(() => normalizeWorkbenchPlan(project.screeningPlan || {}));
  const [planExpanded, setPlanExpanded] = useState(false);
  const [planStatus, setPlanStatus] = useState('');
  const [scoreRun, setScoreRun] = useState({ status: 'idle', message: '' });

  useEffect(() => {
    setPlanDraft(normalizeWorkbenchPlan(project.screeningPlan || {}));
    setPlanStatus('');
  }, [project.id, project.screeningPlan]);

  useEffect(() => {
    setSelectedIds([]);
    setPage(1);
  }, [statusFilter, tierFilter, typeFilter, recommendFilter, stagePriorityFilter, searchTerm]);

  const filtered = useMemo(() => {
    let list = [...screeningCandidates];
    if (statusFilter !== '全部') list = list.filter(c => c.review === statusFilter);
    if (tierFilter !== '全部') list = list.filter(c => getInitialTier(c).key === tierFilter);
    if (typeFilter !== '全部') list = list.filter(c => c.type === typeFilter);
    if (recommendFilter !== '全部') {
      list = list.filter(c => (c.finalRecommendLevel || c.projectMatchStatus || c.raw?.final_recommend_level || c.raw?.project_match_status || '') === recommendFilter);
    }
    if (stagePriorityFilter !== '全部') {
      list = list.filter(c => (c.stage1Priority || c.raw?.stage1_priority || '') === stagePriorityFilter);
    }
    if (searchTerm) list = list.filter(c => `${c.name} ${getCreatorDisplayId(c)} ${c.id}`.includes(searchTerm));
    list.sort((a, b) => {
      const av = sortField === 'baseScore' ? a.baseScore : a[sortField];
      const bv = sortField === 'baseScore' ? b.baseScore : b[sortField];
      if (typeof av === 'number' && typeof bv === 'number') return sortDir === 'desc' ? bv - av : av - bv;
      return sortDir === 'desc' ? String(bv).localeCompare(String(av)) : String(av).localeCompare(String(bv));
    });
    return list;
  }, [screeningCandidates, statusFilter, tierFilter, typeFilter, recommendFilter, stagePriorityFilter, searchTerm, sortField, sortDir]);

  const stats = useMemo(() => {
    if (project.stats?.tiers) {
      return {
        total: project.stats.total || 0,
        passed: project.stats.passed || 0,
        rejected: project.stats.rejected || 0,
        discarded: project.stats.discarded || 0,
        backup: project.stats.backup || 0,
        review: project.stats.review || 0,
        pending: project.stats.pending || 0,
      };
    }
    const s = {
      total: screeningCandidates.length,
      passed: creators.filter(c => ['已通过', '已写回飞书'].includes(c.review)).length,
      rejected: creators.filter(c => ['已驳回', '默认淘汰'].includes(c.review)).length,
      discarded: creators.filter(c => c.review === '已废弃').length,
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
  }, [creators.length, project.stats, screeningCandidates]);

  const tierStats = useMemo(() => {
    const tiers = {
      S: { label: 'S档', desc: '95分以上，最高优先级', count: 0, variant: 'green', color: '#10B981' },
      A: { label: 'A档', desc: '80-94分，高优先级', count: 0, variant: 'blue', color: '#3B82F6' },
      'B+': { label: 'B+档', desc: '75-79分，中高优先级', count: 0, variant: 'amber', color: '#F59E0B' },
      B: { label: 'B档', desc: '70-74分，中优先级', count: 0, variant: 'amber', color: '#D97706' },
      C: { label: 'C档', desc: '70分以下，低优先级', count: 0, variant: 'red', color: '#EF4444' },
      未评分: { label: '未评分', desc: '待完成评分，不计入低优先级', count: 0, variant: 'default', color: '#64748B' },
    };
    if (screeningCandidates.length || creators.length) {
      screeningCandidates.forEach(creator => {
        const tier = getInitialTier(creator).key;
        tiers[tier].count += 1;
      });
    } else if (project.stats?.tiers) {
      Object.entries(project.stats.tiers).forEach(([key, count]) => {
        const tierKey = normalizeScoreTierKey(key);
        if (tiers[tierKey]) tiers[tierKey].count = Number(count || 0);
      });
    }
    return tiers;
  }, [creators.length, project.stats, screeningCandidates]);
  const activeTier = tierFilter === '全部' ? null : tierStats[tierFilter] || null;
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

  const openCreatorDetail = async (creator) => {
    setDetailModalCreator(creator);
    setDetailLoadStatus('loading');
    try {
      const payload = await api(`/api/projects/${encodeURIComponent(project.id)}/creators/${encodeURIComponent(creator.id)}`);
      if (payload.creator) {
        setDetailModalCreator({
          ...creator,
          raw: payload.creator,
        });
      }
      setDetailLoadStatus('');
    } catch (error) {
      console.warn('[ScreeningReviewTab] load creator detail failed', error);
      setDetailLoadStatus('error');
    }
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
    const selectedCreators = batchModal?.creators || filtered.filter(c => selectedIds.includes(c.id));
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
    const selectedCreators = batchModal?.creators || filtered.filter(c => selectedIds.includes(c.id));
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

  const handleBatchDiscard = async () => {
    const selectedCreators = batchModal?.creators || filtered.filter(c => selectedIds.includes(c.id));
    if (!selectedCreators.length) return;
    const reason = reviewComment || `清空${activeTier?.label || '当前筛选'}，移入废弃达人池`;
    applyLocalReviewStatus(selectedCreators, '已废弃', 'red', reason);
    if (onReview) {
      await onReview(selectedCreators.map(c => c.id), '已废弃', reason);
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
    const selectedCreators = selectedIds.length
      ? filtered.filter(c => selectedIds.includes(c.id))
      : filtered;
    if (!selectedCreators.length) return;
    setBatchModal({ action, creators: selectedCreators });
    setReviewComment(
      action === 'pass'
        ? '批量通过，进入项目达人池'
        : action === 'discard'
          ? `清空${activeTier?.label || '当前筛选'}，移入废弃达人池`
          : '批量淘汰，进入观察暂缓池'
    );
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

  const handleCollectCurrentTierDetails = async () => {
    if (!filtered.length || !onCollectDetails) return;
    const segmentLabel = activeTier?.label || '全部档位';
    const detailTargets = filtered.filter(creator => {
      const url = getPgyUrl(creator);
      return url && url.includes('/blogger-detail/');
    });
    if (!detailTargets.length) {
      setPlanStatus(`${segmentLabel}暂无可打开蒲公英详情页的达人`);
      return;
    }
    setPlanStatus(`正在完善${segmentLabel} ${detailTargets.length} 位达人详情...`);
    const result = await onCollectDetails({
      creatorIds: detailTargets.map(creator => creator.id),
      segment: tierFilter,
      segmentLabel,
    });
    setPlanStatus(result?.message || `已完成${segmentLabel}详情完善`);
    await onRefresh?.();
  };

  const runAiScore = async (source = 'toolbar') => {
    if (!onScore) {
      setScoreRun({ status: 'error', message: '当前项目未接入 AI 评分接口' });
      return null;
    }
    const scopedCreators = filtered.length ? filtered : screeningCandidates;
    const selectedTargetCreators = scopedCreators.filter(creator => selectedIds.includes(creator.id));
    const targetCreators = selectedTargetCreators;
    const targetIds = targetCreators.map(creator => creator.id).filter(Boolean);
    if (!targetIds.length) {
      setScoreRun({ status: 'idle', message: 'AI评分需要先勾选具体达人；自动/全量评分请使用规则评分。' });
      return null;
    }
    const confirmed = window.confirm(`确认对已勾选的 ${targetIds.length} 位达人发起大模型评分？未确认时系统只会使用规则评分。`);
    if (!confirmed) {
      setScoreRun({ status: 'idle', message: `已取消本次 AI 评分；未调用大模型。` });
      return null;
    }
    const confirmLargeLlmScore = true;
    const segmentLabel = activeTier?.label || '当前筛选';
    const startedAt = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    setScoreRun({
      status: 'running',
      message: `AI 评分进行中：正在核算${segmentLabel} ${targetIds.length} 位达人投流效果、合作笔记、人设优势和风险...`,
    });
    try {
      const result = await onScore({ source, creatorIds: targetIds, segment: tierFilter, segmentLabel, confirmLargeLlmScore });
      if (result?.ok === false) {
        throw new Error(result.message || result.error || 'AI 评分失败');
      }
      const scored = result?.scored ?? targetIds.length;
      setScoreRun({
        status: 'success',
        message: `AI 评分完成：${segmentLabel} ${scored} 位达人已更新评分和推荐理由 · ${startedAt}`,
      });
      return result;
    } catch (error) {
      setScoreRun({ status: 'error', message: error.message || 'AI 评分失败，请稍后重试' });
      return null;
    }
  };

  const saveScoringPlan = async (runScore = false) => {
    setPlanStatus(runScore ? '正在保存评分筛选条件并进行 AI 评分...' : '正在保存评分筛选条件...');
    try {
      const nextPlan = syncScreeningCriteria(planDraft);
      await onSavePlan?.(nextPlan);
      setPlanDraft(normalizeWorkbenchPlan(nextPlan));
      if (runScore) {
        const result = await runAiScore('save_plan_ai');
        setPlanStatus(result ? '评分筛选条件已保存，AI 评分已完成' : '评分筛选条件已保存，但 AI 评分未完成');
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
  const selectedFilteredCreators = filtered.filter(creator => selectedIds.includes(creator.id));
  const batchTargetCreators = selectedFilteredCreators.length ? selectedFilteredCreators : filtered;
  const batchTargetCount = batchTargetCreators.length;
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const visibleCreators = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const visibleIds = visibleCreators.map(creator => creator.id);
  const allFilteredSelected = filteredIds.length > 0 && filteredIds.every(id => selectedIds.includes(id));
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every(id => selectedIds.includes(id));
  const canDiscardBatch = Boolean(batchTargetCount && (selectedFilteredCreators.length || activeTier));

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const toggleSelectVisible = () => {
    setSelectedIds(ids => {
      if (allVisibleSelected) return ids.filter(id => !visibleIds.includes(id));
      return Array.from(new Set([...ids, ...visibleIds]));
    });
  };

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

  const batchActionTitle = (action) => {
    if (action === 'pass') return '确认批量通过';
    if (action === 'discard') return '清空当前档位达人';
    return '确认批量淘汰';
  };

  const batchActionDestination = (action) => {
    if (action === 'pass') return '「项目达人池」';
    if (action === 'discard') return '「废弃达人池」';
    return '「观察暂缓」';
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
  const scoreBusy = scoreRun.status === 'running';

  const renderKocScoreSummary = (creator) => {
    const verdict = creator.finalRecommendLevel || creator.projectMatchStatus || '';
    const hasKocProfile = Boolean(
      verdict
      || creator.stage1Priority
      || creator.targetContentRatio !== null && creator.targetContentRatio !== undefined && creator.targetContentRatio !== ''
      || creator.productSceneRatio !== null && creator.productSceneRatio !== undefined && creator.productSceneRatio !== ''
    );
    if (!hasKocProfile) return <span className="screening-koc-empty">未启用</span>;
    return (
      <div className="screening-koc-summary">
        <div>
          <Badge variant={verdictVariant(verdict)}>{verdict || '待二阶段'}</Badge>
          {creator.stage1Priority && <Badge variant="default">一阶段 {creator.stage1Priority}</Badge>}
        </div>
        <small>{creator.recommendedFormat || creator.stage1Reason || '推荐形态待补'}</small>
        <span>学习 {percentText(creator.targetContentRatio)} · 场景 {percentText(creator.productSceneRatio)}</span>
      </div>
    );
  };

  const renderLightProfileSummary = (creator) => {
    const profile = getCreatorLightProfile(creator, project);
    return (
      <div className="creator-light-profile">
        <div className="creator-light-profile-score">
          <strong>{profile.contentValueScore}</strong>
          <span>内容价值</span>
          <Badge variant={profile.hasDeepProfile ? 'green' : 'default'}>{profile.hasDeepProfile ? '深档案' : '轻档案'}</Badge>
        </div>
        <div className="creator-light-profile-text">
          <div>{profile.mainStrengths.slice(0, 2).join('、')}</div>
          <small>{profile.mainRisks[0]} · {profile.nextAction}</small>
        </div>
      </div>
    );
  };

  const renderAdRecommendation = (creator) => {
    const recommendation = getCreatorAdRecommendation(creator, getCreatorRealNoteCases(creator), project);
    return (
      <div className="screening-ai-reason-card">
        <div className="screening-ai-reason-head">
          <div>
            <span>大模型意见 · {recommendation.productName}</span>
            <strong>{recommendation.verdict}</strong>
            <small>{recommendation.standardEvidence}</small>
          </div>
          <Badge variant={(creator.risk || []).includes(recommendation.verdict) ? 'amber' : 'green'}>
            {recommendation.action}
          </Badge>
        </div>

        <div className="screening-ai-metric-strip">
          {recommendation.costMetrics.map(item => (
            <div className={`screening-ai-metric is-${item.tone}`} key={item.label}>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
              <small>{item.status}</small>
            </div>
          ))}
        </div>

        <div className="screening-ai-note-metrics">
          <div className="screening-ai-section-title">合作笔记数据</div>
          <div className="screening-ai-note-grid">
            {recommendation.noteMetrics.map(item => (
              <span key={item.label}><strong>{item.value}</strong>{item.label}</span>
            ))}
          </div>
          <p>{recommendation.noteSummary}</p>
        </div>

        <div className="screening-ai-pros-cons">
          <div>
            <div className="screening-ai-section-title">优势</div>
            {recommendation.strengths.map(item => <p key={item}>{item}</p>)}
          </div>
          <div>
            <div className="screening-ai-section-title">短板/风险</div>
            {recommendation.weaknesses.map(item => <p key={item}>{item}</p>)}
          </div>
        </div>

        {recommendation.manualReviewItems?.length ? (
          <div className="screening-ai-note-metrics">
            <div className="screening-ai-section-title">待人工复核</div>
            {recommendation.manualReviewItems.map(item => <p key={item}>{item}</p>)}
          </div>
        ) : null}
      </div>
    );
  };

  const renderReviewComment = (creator) => {
    const recommendation = getCreatorAdRecommendation(creator, getCreatorRealNoteCases(creator), project);
    return (
      <div className="screening-review-comment-card">
        <strong>{recommendation.verdict}</strong>
        <span>{recommendation.standardEvidence}</span>
        <small>{recommendation.productName} · {recommendation.action}</small>
      </div>
    );
  };

  return (
    <div>
      <div className="screening-workbench-hero" style={{ marginBottom: 20 }}>
        <div>
          <div className="screening-workbench-eyebrow">Scoring & Human Review</div>
          <h3>筛选工作台</h3>
          <p>展示找博主数据层级结果，按预算效果、近30天表现和T级基准分层，只让高分/高潜达人进入详情页完善。</p>
        </div>
        <button className="btn btn-primary" onClick={() => onTabChange?.('score-preview')}>
          <Users size={14} />查看项目达人池
        </button>
      </div>

      <div className={`screening-action-status is-${scoreRun.status}`}>
        <div>
          {scoreBusy ? <RefreshCw size={15} className="is-spinning" /> : <Sparkles size={15} />}
          <span>{scoreRun.message || 'AI 评分会按投流效果、合作笔记数据、达人优势和短板重新生成分数与推荐理由。'}</span>
        </div>
        {scoreRun.status === 'success' && <button type="button" onClick={() => setScoreRun({ status: 'idle', message: '' })}>收起</button>}
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
          <span className={planStatus.includes('失败') ? 'is-error' : ''}>{planStatus || '平时折叠；修改后保存，AI 评分会使用当前条件。'}</span>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button className="btn btn-secondary" onClick={() => saveScoringPlan(false)} disabled={!planDirty && planStatus.includes('已保存')}>
              <Save size={14} style={{ marginRight: 4 }} />保存条件
            </button>
            <button className="btn btn-primary" onClick={() => saveScoringPlan(true)} disabled={scoreBusy}>
              {scoreBusy ? <RefreshCw size={14} className="is-spinning" style={{ marginRight: 4 }} /> : <Sparkles size={14} style={{ marginRight: 4 }} />}
              {scoreBusy ? 'AI 评分中' : '保存并 AI 评分'}
            </button>
          </div>
        </div>
      </div>

      {/* 工具栏 */}
      <div className="card screening-review-toolbar" style={{ marginBottom: 16 }}>
        <div className="screening-review-toolbar-group">
          <div className="search-box screening-review-search">
            <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input className="search-input" placeholder="搜索达人..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)} />
          </div>
          <select className="select-field screening-review-select" style={{ width: 120 }} value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
            <option value="全部">全部状态</option>
            <option value="待审核">待审核</option>
            <option value="已通过">已通过</option>
            <option value="已驳回">已驳回</option>
            <option value="备选">备选</option>
            <option value="人工复核">人工复核</option>
          </select>
          <select className="select-field screening-review-select" style={{ width: 110 }} value={tierFilter} onChange={e => setTierFilter(e.target.value)}>
            <option value="全部">全部档位</option>
            <option value="S">S档</option>
            <option value="A">A档</option>
            <option value="B+">B+档</option>
            <option value="B">B档</option>
            <option value="C">C档</option>
            <option value="未评分">未评分</option>
          </select>
          <select className="select-field screening-review-select" style={{ width: 100 }} value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
            <option value="全部">全部类型</option>
            <option value="KOL">KOL</option>
            <option value="KOC">KOC</option>
          </select>
          <select className="select-field screening-review-select" style={{ width: 132 }} value={recommendFilter} onChange={e => setRecommendFilter(e.target.value)}>
            <option value="全部">全部推荐级别</option>
            <option value="强推荐">强推荐</option>
            <option value="推荐">推荐</option>
            <option value="备选">备选</option>
            <option value="待人工确认">待人工确认</option>
            <option value="不推荐">不推荐</option>
            <option value="Pass">Pass</option>
          </select>
          <select className="select-field screening-review-select" style={{ width: 108 }} value={stagePriorityFilter} onChange={e => setStagePriorityFilter(e.target.value)}>
            <option value="全部">全部P级</option>
            <option value="P0">P0</option>
            <option value="P1">P1</option>
            <option value="P2">P2</option>
            <option value="P3">P3</option>
            <option value="不入库">不入库</option>
          </select>
        </div>
        <div className="screening-review-toolbar-actions">
          <button className="btn btn-sm btn-secondary" onClick={onImport}><Upload size={14} style={{ marginRight: 4 }} />导入模板</button>
          <button className="btn btn-sm btn-secondary" onClick={() => onCollect?.()}><Bot size={14} style={{ marginRight: 4 }} />蒲公英采集</button>
          <button
            className="btn btn-sm btn-secondary"
            onClick={() => runAiScore('toolbar_ai')}
            disabled={scoreBusy || !screeningCandidates.length}
            title="重新核算投流效果、合作笔记数据、达人优势和短板"
          >
            {scoreBusy ? <RefreshCw size={14} className="is-spinning" style={{ marginRight: 4 }} /> : <Sparkles size={14} style={{ marginRight: 4 }} />}
            {scoreBusy ? '评分中' : 'AI评分'}
          </button>
          <button
            className="btn btn-sm btn-primary"
            onClick={() => openInviteModal(batchTargetCreators, '初筛找博主批量邀约')}
            disabled={!batchTargetCount || !onPgyInvite}
            title="通过蒲公英邀约通道批量发起合作"
          >
            <Send size={14} style={{ marginRight: 4 }} />批量邀约{batchTargetCount ? ` ${batchTargetCount}` : ''}
          </button>
          <button
            className="btn btn-sm btn-primary"
            onClick={handleCollectCurrentTierDetails}
            disabled={!filtered.length}
            title={`批量完善当前${activeTier?.label || '全部档位'}分段的达人详情页`}
          >
            <FileText size={14} style={{ marginRight: 4 }} />完善{activeTier?.label || '全部档位'}{filtered.length ? ` ${filtered.length}` : ''}
          </button>
          <button className="btn btn-sm btn-ghost" onClick={onRefresh}><RefreshCw size={14} /></button>
          <button className="btn btn-sm btn-secondary" onClick={() => openBatchModal('pass')} disabled={!batchTargetCount} title="批量通过当前筛选达人"><UserCheck size={14} style={{ marginRight: 4 }} />批量通过{batchTargetCount ? ` ${batchTargetCount}` : ''}</button>
          <button className="btn btn-sm btn-danger" onClick={() => openBatchModal('reject')} disabled={!batchTargetCount} title="批量淘汰当前筛选达人"><UserX size={14} style={{ marginRight: 4 }} />批量淘汰{batchTargetCount ? ` ${batchTargetCount}` : ''}</button>
          <button
            className="btn btn-sm btn-danger"
            onClick={() => openBatchModal('discard')}
            disabled={!canDiscardBatch}
            title={activeTier || selectedFilteredCreators.length ? '清空当前档位或已勾选达人，移入废弃达人池' : '请先选择一个档位，或勾选要废弃的达人'}
          >
            <Trash2 size={14} style={{ marginRight: 4 }} />清空{activeTier?.label || '所选'}{batchTargetCount ? ` ${batchTargetCount}` : ''}
          </button>
        </div>
      </div>

      {/* 达人列表 */}
      <div className="card screening-review-table-card">
        <div className="screening-review-table-scroll">
          <table className="screening-review-table">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-primary)' }}>
                <th className="screening-review-col-checkbox" style={{ padding: '12px 8px 12px 16px', textAlign: 'center' }}>
                  <input
                    type="checkbox"
                    checked={allFilteredSelected}
                    disabled={!filtered.length}
                    onChange={toggleSelectFiltered}
                    aria-label="选择全部筛选结果达人"
                    title="选择全部筛选结果达人"
                  />
                </th>
                <th className="screening-review-col-creator" style={{ padding: '12px 16px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>达人</th>
                <th className="screening-review-col-type" style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>类型</th>
                <th className="screening-review-col-followers" style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12, cursor: 'pointer' }} onClick={() => toggleSort('followersNum')}>粉丝数 <SortIcon field="followersNum" /></th>
                <th className="screening-review-col-quote" style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12, cursor: 'pointer' }} onClick={() => toggleSort('quoteNum')}>报价 <SortIcon field="quoteNum" /></th>
                <th className="screening-review-col-score" style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12, cursor: 'pointer' }} onClick={() => toggleSort('baseScore')}>推荐分 <SortIcon field="baseScore" /></th>
                <th className="screening-review-col-koc" style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>KOC结论</th>
                <th className="screening-review-col-model" style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>内容建模</th>
                <th className="screening-review-col-tier" style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>档位</th>
                <th className="screening-review-col-risk" style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>优势项</th>
                <th className="screening-review-col-status" style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>审核状态</th>
                <th className="screening-review-col-comment" style={{ padding: '12px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>审核意见</th>
                <th className="screening-review-col-actions" style={{ padding: '12px 16px', textAlign: 'center', color: 'var(--text-secondary)', fontWeight: 600, fontSize: 12 }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {visibleCreators.map(creator => (
                <React.Fragment key={creator.id}>
                  <tr style={{ borderBottom: '1px solid var(--border-primary)', cursor: 'pointer', transition: 'background 0.15s' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                    <td className="screening-review-col-checkbox" style={{ padding: '12px 8px 12px 16px', textAlign: 'center' }}>
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(creator.id)}
                        onChange={() => toggleSelectCreator(creator.id)}
                        onClick={e => e.stopPropagation()}
                        aria-label={`选择${creator.name}`}
                      />
                    </td>
                    <td className="screening-review-col-creator" style={{ padding: '12px 16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        {renderCreatorAvatar(creator)}
                        <div>
                          {renderCreatorName(creator, { color: 'var(--text-primary)', fontWeight: 600 })}
                          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{getCreatorDisplayId(creator)}</div>
                        </div>
                      </div>
                    </td>
                    <td className="screening-review-col-type" style={{ padding: '12px' }}><Badge variant={creator.typeVariant}>{creator.type}</Badge></td>
                    <td className="screening-review-col-followers" style={{ padding: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>{creator.followers}</td>
                    <td className="screening-review-col-quote" style={{ padding: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>{creator.quote}</td>
                    <td className="screening-review-col-score screening-review-cell-score" style={{ padding: '12px' }}>
                      <span style={{ fontWeight: 700, fontSize: 15, color: getScoreColor(creator.baseScore) }}>
                        {creator.scorePending ? '待评分' : (creator.baseScore ?? '-')}
                      </span>
                      <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>
                        规则初筛 {creator.ruleGroupScore ?? '-'} · 完整度 {creator.informationCompletenessLabel}
                      </span>
                    </td>
                    <td className="screening-review-col-koc screening-review-cell-koc" style={{ padding: '12px' }}>
                      {renderKocScoreSummary(creator)}
                    </td>
                    <td className="screening-review-col-model screening-review-cell-model" style={{ padding: '12px' }}>
                      {renderLightProfileSummary(creator)}
                    </td>
                    <td className="screening-review-col-tier" style={{ padding: '12px' }}>
                      {(() => {
                        const tier = getInitialTier(creator);
                        return <Badge variant={tier.variant}>{tier.label} · {tier.text}</Badge>;
                      })()}
                      {creator.detailCollectionPriority && <Badge variant="default">{creator.detailCollectionPriority}</Badge>}
                      {(() => {
                        const detailStatus = getCreatorDetailStatus(creator);
                        return <Badge variant={detailStatus.variant}>{detailStatus.label}</Badge>;
                      })()}
                    </td>
                    <td className="screening-review-col-risk screening-review-cell-risk" style={{ padding: '12px' }}>
                      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        {(creator.risk || []).map((t, i) => <span key={i} className="tag" style={{ fontSize: 10, color: '#0F766E' }}>{t}</span>)}
                      </div>
                    </td>
                    <td className="screening-review-col-status" style={{ padding: '12px' }}><Badge variant={getReviewVariant(creator.review)}>{creator.review}</Badge></td>
                    <td className="screening-review-col-comment screening-review-cell-comment" style={{ padding: '12px' }}>
                      {renderReviewComment(creator)}
                      {creator.reviewer && <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>{creator.reviewer} · {creator.reviewedAt}</div>}
                    </td>
                    <td className="screening-review-col-actions" style={{ padding: '12px 16px', textAlign: 'center' }}>
                      <div className="screening-review-action-row">
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
                          onClick={(e) => { e.stopPropagation(); openCreatorDetail(creator); }}
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
                    <tr className="screening-review-expanded-row" style={{ background: 'var(--bg-raised)' }}>
                      <td colSpan={13} style={{ padding: '16px 24px', borderBottom: '1px solid var(--border-primary)' }}>
                        <div className="screening-review-expanded-grid">
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
                            {renderAdRecommendation(creator)}
                            {(creator.risk || []).length > 0 && (
                              <div className="screening-ai-risk-list">
                                <div>风险提示</div>
                                {(creator.risk || []).map((r, i) => (
                                  <div key={i}>
                                    <AlertTriangle size={12} />
                                    <span>{r}</span>
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
            <span>共 {filtered.length} 位达人，当前显示 {visibleCreators.length} 位，已勾选 {selectedIds.length} 位</span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <button className="btn btn-sm btn-secondary" disabled={!filteredIds.length} onClick={toggleSelectFiltered}>
                {allFilteredSelected ? '取消全部筛选结果' : `选择全部筛选结果 ${filteredIds.length}`}
              </button>
              <button className="btn btn-sm btn-secondary" disabled={currentPage <= 1} onClick={() => setPage(value => Math.max(1, value - 1))}>上一页</button>
              第 {currentPage} / {totalPages} 页
              <button className="btn btn-sm btn-secondary" disabled={currentPage >= totalPages} onClick={() => setPage(value => Math.min(totalPages, value + 1))}>下一页</button>
              筛选自 {screeningCandidates.length} 位待筛候选，已入池 {stats.passed} 位
            </span>
          </div>
        </div>
      </div>

      {/* 审核确认弹窗 */}
      {batchModal && (
        <div className="modal-overlay" onClick={() => setBatchModal(null)}>
          <div className="modal" style={{ maxWidth: 680 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>
                {batchActionTitle(batchModal.action)}
              </h3>
              <button className="btn btn-ghost btn-sm modal-close" onClick={() => setBatchModal(null)}><X size={16} /></button>
            </div>
            <div className="modal-body">
              <div style={{ marginBottom: 12, color: 'var(--text-secondary)', fontSize: 13 }}>
                本次将处理 {batchModal.creators.length} 位{selectedFilteredCreators.length ? '已勾选' : '当前筛选'}达人，确认后会从筛选工作台移出，并进入
                {batchActionDestination(batchModal.action)}。
              </div>
              <div className="batch-review-list">
                {batchModal.creators.map(creator => {
                  const tier = getCreatorDisplayTier(creator);
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
              <button
                className={`btn ${batchModal.action === 'pass' ? 'btn-primary' : 'btn-danger'}`}
                onClick={batchModal.action === 'pass' ? handleBatchPass : batchModal.action === 'discard' ? handleBatchDiscard : handleBatchReject}
              >
                {batchModal.action === 'pass' ? '确认通过并移入达人池' : batchModal.action === 'discard' ? '确认清空并移入废弃达人池' : '确认淘汰并移入观察暂缓'}
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
          loadStatus={detailLoadStatus}
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
