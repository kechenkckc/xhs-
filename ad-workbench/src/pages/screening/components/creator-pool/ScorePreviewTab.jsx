import React, { useCallback, useEffect, useMemo, useState } from 'react';
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
import { api, formatApiErrorMessage } from '../../api/screeningApi';
import { compactNumber, formatDateLabel, formatDateTime, formatPercentValue, getDateKey } from '../../utils/formatters';
import { getCreatorStatus, getProjectCreators } from '../../utils/projectMappers';
import {
  creatorHasTag,
  getCreatorAvatarUrl,
  getCreatorCategory,
  getCreatorCollectedAt,
  getCreatorDetailStatus,
  getCreatorDisplayTier,
  getCreatorFollowupInfo,
  getCreatorIntro,
  getCreatorLocation,
  getCreatorRecommendation,
  getCreatorTagGroups,
  getCreatorPrioritySignals,
  getCreatorTags,
  getCreatorUpdateLog,
  getCreatorXhsId,
  getPgyUrl,
  mapBackendCreator,
  pickCreatorValue,
  uniqueCompactItems,
} from '../../utils/creatorMappers';
import { getPoolStage, getReviewVariant, getScoreColor } from '../../utils/creatorScoring';
import { PgyInviteModal } from '../pgy-invite/PgyInviteModal';

export function ScorePreviewTab({ project, screeningStatus, onCollectDetails, onPgyInvite }) {
  const pageSize = 60;
  const [poolData, setPoolData] = useState(null);
  const [poolMessage, setPoolMessage] = useState('');
  const creators = useMemo(() => {
    if (poolData?.groups) {
      return Object.entries(poolData.groups)
        .filter(([stage]) => stage !== '筛选工作台')
        .flatMap(([, items]) => items || [])
        .map(mapBackendCreator);
    }
    return getProjectCreators(project).map((creator, index) => ({
      ...creator,
      ...(getCreatorStatus(project.id, creator.id, screeningStatus) || {}),
      poolStage: getPoolStage({ ...creator, ...(getCreatorStatus(project.id, creator.id, screeningStatus) || {}) }, index),
    })).filter(creator => getPoolStage(creator) !== '筛选工作台');
  }, [poolData, project, screeningStatus]);
  const [activeStage, setActiveStage] = useState('合格达人待合作');
  const [collectionDateFilter, setCollectionDateFilter] = useState('全部');
  const [activeTagFilter, setActiveTagFilter] = useState('');
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState(null);
  const [updateLogs, setUpdateLogs] = useState({});
  const [writebackSettings, setWritebackSettings] = useState({ auto_writeback_enabled: false });
  const [writebackBusy, setWritebackBusy] = useState(false);
  const [detailBusy, setDetailBusy] = useState(false);
  const [inviteModal, setInviteModal] = useState(null);

  const stageConfig = {
    '已合作跟进中': { variant: 'green', icon: <RefreshCw size={14} />, desc: '已确认合作，持续追踪近期数据变化' },
    '合格达人待合作': { variant: 'blue', icon: <UserCheck size={14} />, desc: '人工筛选合格，等待排期或商务推进' },
    '待建联达人': { variant: 'amber', icon: <MessageSquare size={14} />, desc: '需要媒介建联并确认档期报价' },
    '观察暂缓': { variant: 'neutral', icon: <Clock size={14} />, desc: '低分或风险项较多，暂不进入合作池' },
    '废弃达人池': { variant: 'red', icon: <Trash2 size={14} />, desc: '已从当前档位清空，仍保留本地记录用于追溯' },
  };

  const collectionDateOptions = useMemo(() => {
    const counts = new Map();
    creators.forEach(creator => {
      const key = getDateKey(getCreatorCollectedAt(creator));
      if (key) counts.set(key, (counts.get(key) || 0) + 1);
    });
    return Array.from(counts.entries()).sort((a, b) => b[0].localeCompare(a[0]));
  }, [creators]);

  const dateFilteredCreators = useMemo(() => {
    if (collectionDateFilter === '全部') return creators;
    return creators.filter(creator => getDateKey(getCreatorCollectedAt(creator)) === collectionDateFilter);
  }, [collectionDateFilter, creators]);

  const stageCreatorsForTagStats = useMemo(() => {
    const result = Object.fromEntries(Object.keys(stageConfig).map(stage => [stage, []]));
    if (poolData?.groups) {
      Object.entries(poolData.groups).forEach(([stage, items]) => {
        if (!stageConfig[stage]) return;
        result[stage] = (items || [])
          .map(mapBackendCreator)
          .filter(creator => collectionDateFilter === '全部' || getDateKey(getCreatorCollectedAt(creator)) === collectionDateFilter);
      });
      return result;
    }
    dateFilteredCreators.forEach((creator, index) => {
      const stage = getPoolStage(creator, index);
      if (!result[stage]) result[stage] = [];
      result[stage].push(creator);
    });
    return result;
  }, [collectionDateFilter, dateFilteredCreators, poolData]);

  const commonTagStatsByStage = useMemo(() => {
    return Object.fromEntries(Object.entries(stageCreatorsForTagStats).map(([stage, items]) => {
      const counts = new Map();
      items.forEach(creator => {
        getCreatorTags(creator).forEach(tag => {
          counts.set(tag, (counts.get(tag) || 0) + 1);
        });
      });
      return [stage, counts];
    }));
  }, [stageCreatorsForTagStats]);

  useEffect(() => {
    if (collectionDateFilter !== '全部' && !collectionDateOptions.some(([date]) => date === collectionDateFilter)) {
      setCollectionDateFilter('全部');
    }
  }, [collectionDateFilter, collectionDateOptions]);

  const grouped = useMemo(() => {
    const result = Object.fromEntries(Object.keys(stageConfig).map(stage => [stage, []]));
    if (poolData?.groups) {
      Object.entries(poolData.groups).forEach(([stage, items]) => {
        if (!stageConfig[stage]) return;
        result[stage] = (items || [])
          .map(mapBackendCreator)
          .filter(creator => collectionDateFilter === '全部' || getDateKey(getCreatorCollectedAt(creator)) === collectionDateFilter)
          .filter(creator => creatorHasTag(creator, activeTagFilter));
      });
      return result;
    }
    dateFilteredCreators.forEach((creator, index) => {
      if (!creatorHasTag(creator, activeTagFilter)) return;
      const stage = getPoolStage(creator, index);
      if (!result[stage]) result[stage] = [];
      result[stage].push(creator);
    });
    Object.values(result).forEach(list => list.sort((a, b) => b.baseScore - a.baseScore));
    return result;
  }, [activeTagFilter, collectionDateFilter, dateFilteredCreators, poolData]);

  const visibleStages = [activeStage];
  const activeStageCreators = grouped[activeStage] || [];
  const activeTagIsCommon = !activeTagFilter || (commonTagStatsByStage[activeStage]?.get(activeTagFilter) || 0) >= 2;
  const visibleLimit = page * pageSize;
  const visibleStageCreators = activeStageCreators.slice(0, visibleLimit);
  const hasMoreStageCreators = visibleStageCreators.length < activeStageCreators.length;
  const activePoolCreators = useMemo(
    () => creators.filter(creator => getPoolStage(creator) !== '废弃达人池'),
    [creators]
  );
  const activeStageTotal = useMemo(() => {
    if (poolData?.groups) {
      return (poolData.groups[activeStage] || [])
        .map(mapBackendCreator)
        .filter(creator => collectionDateFilter === '全部' || getDateKey(getCreatorCollectedAt(creator)) === collectionDateFilter)
        .length;
    }
    return dateFilteredCreators.filter(creator => getPoolStage(creator) === activeStage).length;
  }, [activeStage, collectionDateFilter, dateFilteredCreators, poolData]);
  const activePoolCount = activePoolCreators.length;
  const avgScore = activePoolCreators.length ? (activePoolCreators.reduce((sum, creator) => sum + Number(creator.baseScore || 0), 0) / activePoolCreators.length).toFixed(1) : '0.0';

  useEffect(() => {
    setPage(1);
    setExpandedId(null);
  }, [activeStage, activeTagFilter, collectionDateFilter]);

  useEffect(() => {
    if (!activeTagIsCommon) setActiveTagFilter('');
  }, [activeTagIsCommon]);

  useEffect(() => {
    if (!hasMoreStageCreators) return undefined;
    const handleScroll = () => {
      const scrollBottom = window.innerHeight + window.scrollY;
      const documentHeight = document.documentElement.scrollHeight;
      if (documentHeight - scrollBottom < 520) {
        setPage(value => value + 1);
      }
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, [hasMoreStageCreators]);

  const loadCreatorPool = useCallback(async () => {
    setPoolMessage('读取达人池中...');
    try {
      const payload = await api(`/api/projects/${project.id}/creator-pool`);
      setPoolData(payload);
      setPoolMessage('');
    } catch (error) {
      setPoolMessage(error.message || '读取达人池失败');
    }
  }, [project.id]);

  const loadWritebackSettings = useCallback(async () => {
    try {
      const payload = await api(`/api/projects/feishu/writeback-settings?project_id=${project.id}`);
      setWritebackSettings(payload.settings || { auto_writeback_enabled: false });
    } catch (error) {
      setPoolMessage(error.message || '读取写回设置失败');
    }
  }, [project.id]);

  useEffect(() => {
    loadCreatorPool();
    loadWritebackSettings();
  }, [loadCreatorPool, loadWritebackSettings]);

  const handleToggleAutoWriteback = async () => {
    const nextEnabled = !writebackSettings.auto_writeback_enabled;
    setWritebackBusy(true);
    try {
      const payload = await api('/api/projects/feishu/writeback-settings', {
        method: 'POST',
        body: JSON.stringify({ project_id: project.id, auto_writeback_enabled: nextEnabled }),
      });
      setWritebackSettings(payload.settings || { auto_writeback_enabled: nextEnabled });
      setPoolMessage(nextEnabled ? '已开启自动写回：合格达人完成详情完善后会写入飞书' : '已关闭自动写回：可手动批量写入合格达人');
    } catch (error) {
      setPoolMessage(error.message || '写回设置保存失败');
    } finally {
      setWritebackBusy(false);
    }
  };

  const handleManualWriteback = async () => {
    setWritebackBusy(true);
    setPoolMessage('正在批量写回合格达人...');
    try {
      const payload = await api('/api/projects/feishu/writeback', {
        method: 'POST',
        body: JSON.stringify({ project_id: project.id, quality_only: true, rows: [] }),
        timeoutMs: 90000,
        timeoutMessage: '写回飞书超过 90 秒未返回，已停止等待。请检查飞书权限、字段映射或网络后重试。',
      });
      await loadCreatorPool();
      setPoolMessage(`已写回 ${payload.written_count || 0} 位合格达人`);
    } catch (error) {
      setPoolMessage(error.message || '写回飞书失败');
    } finally {
      setWritebackBusy(false);
    }
  };

  const handleUpdateCreator = async (creator) => {
    const now = new Date().toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-');
    const nextFollowers = Math.max(0, Number(creator.followersNum || 0) + 320);
    try {
      await api(`/api/projects/${project.id}/creator-pool/${creator.id}/update-metrics`, {
        method: 'POST',
        body: JSON.stringify({ data: { followers_count: nextFollowers }, operator: '当前用户' }),
      });
      setUpdateLogs(prev => ({
        ...prev,
        [creator.id]: [
          { time: now, metrics: getCreatorUpdateLog({ ...creator, followersNum: nextFollowers }, (prev[creator.id] || []).length), operator: '当前用户' },
          ...(prev[creator.id] || []),
        ],
      }));
      await loadCreatorPool();
      setPoolMessage('数据已更新并写入历史快照');
    } catch (error) {
      setPoolMessage(error.message || '更新达人数据失败');
    } finally {
      setExpandedId(creator.id);
    }
  };

  const handleExportCsv = () => {
    window.open(`/api/projects/${project.id}/exports/creator-pool.csv`, '_blank');
  };

  const handleCollectPoolDetails = async (targetCreators, label) => {
    if (!targetCreators.length || !onCollectDetails) return;
    setDetailBusy(true);
    setPoolMessage(`正在完善${label}详情...`);
    try {
      const result = await onCollectDetails({
        creatorIds: targetCreators.map(creator => creator.id),
        segment: `pool:${label}`,
        segmentLabel: label,
      });
      await loadCreatorPool();
      setPoolMessage(result?.message || `已完成${label}详情页完善，共 ${targetCreators.length} 位达人`);
    } finally {
      setDetailBusy(false);
    }
  };

  const handleTagFilter = (tag) => {
    setActiveTagFilter(current => (current === tag ? '' : tag));
    setExpandedId(null);
  };

  const openInviteModal = (targetCreators, source = '项目达人池邀约') => {
    const validCreators = (targetCreators || []).filter(Boolean);
    if (!validCreators.length) return;
    setInviteModal({ creators: validCreators, source });
  };

  const submitInvite = async (form) => {
    const targetCreators = inviteModal?.creators || [];
    setPoolMessage(`正在通过蒲公英邀约 ${targetCreators.length} 位达人...`);
    const payload = await onPgyInvite?.(targetCreators.map(creator => creator.id), form);
    await loadCreatorPool();
    setPoolMessage(payload?.message || `已通过蒲公英邀约 ${targetCreators.length} 位达人`);
    return payload;
  };

  return (
    <div>
      <div className="creator-pool-hero" style={{ marginBottom: 20 }}>
        <div>
          <div className="creator-pool-eyebrow">Project Creator Pool</div>
          <h3>项目达人池</h3>
          <p>采集达人先在筛选工作台完成评分匹配，人工通过后再进入项目达人池分层管理。</p>
        </div>
        <div className="creator-pool-hero-stats">
          <div><strong>{activePoolCount}</strong><span>池内达人</span></div>
          <div><strong>{avgScore}</strong><span>平均评分</span></div>
          <div><strong>{grouped['已合作跟进中']?.length || 0}</strong><span>跟进中</span></div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>{poolMessage || `后端达人池已同步至 ${poolData?.updated_at || '当前页面'}`}</span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <select
            className="select-field"
            style={{ width: 168 }}
            value={collectionDateFilter}
            onChange={event => setCollectionDateFilter(event.target.value)}
          >
            <option value="全部">全部采集日期</option>
            {collectionDateOptions.map(([date, count]) => (
              <option key={date} value={date}>{formatDateLabel(date)} · {count}人</option>
            ))}
          </select>
          <button
            className={`creator-pool-writeback-toggle ${writebackSettings.auto_writeback_enabled ? 'is-on' : ''}`}
            onClick={handleToggleAutoWriteback}
            disabled={writebackBusy}
            title="开启后，详情完善完成且评分合格的真实达人会自动写入飞书"
          >
            {writebackSettings.auto_writeback_enabled ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
            <span>{writebackSettings.auto_writeback_enabled ? '自动写回已开' : '自动写回已关'}</span>
          </button>
          <button className="btn btn-sm btn-secondary" onClick={handleManualWriteback} disabled={writebackBusy}>
            <FileSpreadsheet size={14} />写回合格达人
          </button>
          <button
            className="btn btn-sm btn-primary"
            onClick={() => handleCollectPoolDetails(activeStageCreators, activeStage)}
            disabled={detailBusy || !activeStageCreators.length}
            title="手动完善当前分组内所有达人详情，不受自动详情完善优先级限制"
          >
            <FileText size={14} />完善当前分组{activeStageCreators.length ? ` ${activeStageCreators.length}` : ''}
          </button>
          <button
            className="btn btn-sm btn-primary"
            onClick={() => openInviteModal(activeStageCreators, `${activeStage}批量邀约`)}
            disabled={!onPgyInvite || !activeStageCreators.length}
            title="通过蒲公英邀约通道批量发起合作"
          >
            <Send size={14} />邀约当前分组{activeStageCreators.length ? ` ${activeStageCreators.length}` : ''}
          </button>
          <button className="btn btn-sm btn-secondary" onClick={loadCreatorPool}><RefreshCw size={14} />刷新</button>
          <button className="btn btn-sm btn-primary" onClick={handleExportCsv}><Download size={14} />导出 CSV</button>
        </div>
      </div>

      <div className="creator-pool-stage-tabs" style={{ marginBottom: 16 }}>
        {Object.keys(stageConfig).map(stage => (
          <button key={stage} className={activeStage === stage ? 'is-active' : ''} onClick={() => setActiveStage(stage)}>
            {stageConfig[stage].icon}
            <span>{stage}</span>
            <strong>{grouped[stage]?.length || 0}</strong>
          </button>
        ))}
      </div>

      <div className="creator-pool-board">
        {visibleStages.map(stage => {
          const cfg = stageConfig[stage];
          const stageCreators = grouped[stage] || [];
          const displayCreators = stage === activeStage ? visibleStageCreators : stageCreators.slice(0, pageSize);
          return (
            <section key={stage} className="creator-pool-section">
              <div className="creator-pool-section-head">
                <div>
                  <h4>{cfg.icon}{stage}<Badge variant={cfg.variant}>{stageCreators.length}人</Badge></h4>
                  <p>{cfg.desc}</p>
                </div>
              </div>
              {activeTagFilter && (
                <div className="creator-pool-filter-bar">
                  <span>已筛选标签</span>
                  <strong>{activeTagFilter}</strong>
                  <em>{stageCreators.length}/{activeStageTotal} 人</em>
                  <button type="button" onClick={() => setActiveTagFilter('')}>清除</button>
                </div>
              )}
              {stageCreators.length === 0 ? (
                <div className="creator-pool-empty">{activeTagFilter ? `暂无「${activeTagFilter}」标签达人` : '暂无达人'}</div>
              ) : (
                <>
                <div className="creator-pool-grid">
                  {displayCreators.map((creator, index) => {
                    const tier = getCreatorDisplayTier(creator);
                    const logs = updateLogs[creator.id] || (stage === '已合作跟进中' ? [{ time: '2026-05-09 10:00:00', metrics: getCreatorUpdateLog(creator, index), operator: '系统同步' }] : []);
                    const avatarUrl = getCreatorAvatarUrl(creator);
                    const location = getCreatorLocation(creator);
                    const category = getCreatorCategory(creator);
                    const xhsId = getCreatorXhsId(creator);
                    const intro = getCreatorIntro(creator);
                    const tagGroups = getCreatorTagGroups(creator);
                    const commonTagCounts = commonTagStatsByStage[stage] || new Map();
                    const commonTagGroups = Object.fromEntries(Object.entries(tagGroups).map(([group, items]) => [
                      group,
                      items.filter(item => (commonTagCounts.get(item) || 0) >= 2),
                    ]));
                    const hasCommonTags = Object.values(commonTagGroups).some(items => items.length);
                    const followup = getCreatorFollowupInfo(creator, stage);
                    const recommendation = getCreatorRecommendation(creator, stage);
                    const detailStatus = getCreatorDetailStatus(creator);
                    const prioritySignals = getCreatorPrioritySignals(creator);
                    const platformMark = String(creator.type || '达').replace(/[\/\s].*$/, '').slice(0, 2);
                    const pgyUrl = getPgyUrl(creator);
                    const collectedAt = getCreatorCollectedAt(creator);
                    const renderTag = (item, group) => (
                      <button
                        type="button"
                        className={`tag creator-pool-tag creator-pool-tag-${group} ${activeTagFilter === item ? 'is-active' : ''}`}
                        key={`${group}-${item}`}
                        onClick={() => handleTagFilter(item)}
                        title={`筛选${item}标签达人`}
                      >
                        {item}
                      </button>
                    );
                    return (
                      <article key={creator.id} className="creator-pool-card">
                        <div className="creator-pool-profile">
                          <div className="creator-pool-avatar-wrap">
                            {avatarUrl ? (
                              <img className="creator-pool-photo" src={avatarUrl} alt={creator.name} />
                            ) : (
                              <div className="creator-pool-photo creator-pool-photo-fallback">{creator.name[0]}</div>
                            )}
                            <span className="creator-pool-platform-mark">{platformMark}</span>
                          </div>
                          <div className="creator-pool-profile-main">
                            <div className="creator-pool-title-line">
                              <span className="creator-pool-name-hover">
                                {pgyUrl ? (
                                  <a className="creator-pool-name-link" href={pgyUrl} target="_blank" rel="noreferrer" onClick={event => event.stopPropagation()}>
                                    {creator.name}<ExternalLink size={13} />
                                  </a>
                                ) : (
                                  <span className="creator-pool-name-link creator-pool-name-link-disabled">
                                    {creator.name}
                                  </span>
                                )}
                                <span className="creator-pool-profile-popover" role="tooltip">
                                  <strong>{creator.name}</strong>
                                  <span>{intro}</span>
                                </span>
                              </span>
                              <span className="creator-pool-location">{location}</span>
                              <Badge variant="neutral">{category}</Badge>
                            </div>
                            <div className="creator-pool-identity-row">
                              <span>小红书号：<strong>{xhsId}</strong><Copy size={13} /></span>
                              <span>{creator.followers} 粉丝</span>
                              <span>{creator.quote} 报价</span>
                              <span>{formatDateLabel(collectedAt)} 采集</span>
                            </div>
                            <div className="creator-pool-intro">{intro}</div>
                          </div>
                          <div className="creator-pool-score-panel">
                            <div className="creator-pool-score" style={{ color: getScoreColor(creator.baseScore) }}>{creator.baseScore}</div>
                            <span>{tier.label}</span>
                            <strong>{recommendation}</strong>
                          </div>
                        </div>

                        <div className="creator-pool-card-meta">
                          <Badge variant={tier.variant}>{tier.label}</Badge>
                          {prioritySignals.map(signal => (
                            <span key={signal.label} className={`creator-pool-priority-signal creator-pool-priority-signal-${signal.tone}`}>{signal.label}</span>
                          ))}
                          <Badge variant={detailStatus.variant}>{detailStatus.label}</Badge>
                          <Badge variant={getReviewVariant(creator.review)}>{creator.review || '待审核'}</Badge>
                          <span className="creator-pool-followup-pill">{followup.status}</span>
                          <span className="creator-pool-followup-pill">负责人 {followup.owner}</span>
                          <span className="creator-pool-followup-pill">最近 {followup.lastAt}</span>
                        </div>

                        <div className="creator-pool-tag-groups">
                          <div>
                            <span>人设</span>
                            <div>{commonTagGroups.persona.length ? commonTagGroups.persona.map(item => renderTag(item, 'persona')) : <em>暂无共性标签</em>}</div>
                          </div>
                          <div>
                            <span>内容</span>
                            <div>{commonTagGroups.content.length ? commonTagGroups.content.map(item => renderTag(item, 'content')) : <em>暂无共性标签</em>}</div>
                          </div>
                          <div>
                            <span>数据</span>
                            <div>{commonTagGroups.metric.length ? commonTagGroups.metric.map(item => renderTag(item, 'metric')) : <em>暂无共性标签</em>}</div>
                          </div>
                          {(commonTagGroups.risk.length || !hasCommonTags) && (
                            <div className="creator-pool-risk-group">
                              <span>优势</span>
                              <div>{commonTagGroups.risk.length ? commonTagGroups.risk.map(item => renderTag(item, 'advantage')) : <em className="creator-pool-safe">暂无共性优势</em>}</div>
                            </div>
                          )}
                        </div>

                        <div className="creator-pool-actions">
                          <button
                            className="btn btn-sm btn-secondary"
                            onClick={() => handleCollectPoolDetails([creator], creator.name)}
                            disabled={detailBusy}
                            title="手动完善该达人详情，不受自动详情完善优先级限制"
                          >
                            <FileText size={13} />完善详情
                          </button>
                          {stage === '已合作跟进中' && (
                            <button className="btn btn-sm btn-primary" onClick={() => handleUpdateCreator(creator)}>
                              <RefreshCw size={13} />更新数据
                            </button>
                          )}
                          {stage === '合格达人待合作' && (
                            <button className="btn btn-sm btn-secondary"><Calendar size={13} />排期沟通</button>
                          )}
                          {stage === '待建联达人' && (
                            <button className="btn btn-sm btn-secondary"><MessageSquare size={13} />记录建联</button>
                          )}
                          <button
                            className="btn btn-sm btn-primary"
                            onClick={() => openInviteModal([creator], '项目达人池单个邀约')}
                            disabled={!onPgyInvite}
                          >
                            <Send size={13} />邀约
                          </button>
                          <button className="btn btn-sm btn-ghost" onClick={() => setExpandedId(expandedId === creator.id ? null : creator.id)}>
                            {expandedId === creator.id ? '收起' : '详情'}<ChevronDown size={13} style={{ transform: expandedId === creator.id ? 'rotate(180deg)' : 'none' }} />
                          </button>
                        </div>

                        {expandedId === creator.id && (
                          <div className="creator-pool-detail">
                            <div className="creator-pool-detail-title">近期数据记录</div>
                            {logs.length ? logs.map((log, logIndex) => (
                              <div className="creator-pool-log" key={`${creator.id}-${log.time}-${logIndex}`}>
                                <div className="creator-pool-log-head">
                                  <span>{log.time}</span>
                                  <strong>{log.operator}</strong>
                                </div>
                                <div className="creator-pool-log-metrics">
                                  {log.metrics.map(metric => (
                                    <div key={metric.label} className={metric.direction === 'up' ? 'is-up' : 'is-down'}>
                                      <span>{metric.label}</span>
                                      <strong>{metric.value}</strong>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )) : (
                              <div className="creator-pool-no-log">暂无更新记录，进入合作后可在此追踪数据变化。</div>
                            )}
                          </div>
                        )}
                      </article>
                    );
                  })}
                </div>
                <div style={{ padding: '12px 4px 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12, color: 'var(--text-secondary)' }}>
                  <span>当前显示 {displayCreators.length} / {stageCreators.length} 位达人</span>
                  {hasMoreStageCreators ? (
                    <button className="btn btn-sm btn-secondary" onClick={() => setPage(value => value + 1)}>加载更多 60</button>
                  ) : (
                    <span>已显示全部</span>
                  )}
                </div>
                </>
              )}
            </section>
          );
        })}
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
