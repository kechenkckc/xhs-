import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
  ToggleLeft, ToggleRight, Square
} from 'lucide-react';
import StatCard from '../../../../components/StatCard';
import DataTable from '../../../../components/DataTable';
import Badge from '../../../../components/Badge';
import ProgressBar from '../../../../components/ProgressBar';
import {
  pgyFilterLabel,
} from '../../constants/screeningConstants';
import { getProjectCreators, getProjectStats } from '../../utils/projectMappers';
import { getScoreColor, getScoreTier } from '../../utils/creatorScoring';
import {
  mergeOptionItems,
  pgyFilterKey,
} from '../../utils/pgyFilters';
import { getSchemeAdditionalFilters, getSchemeRequiredFilters, normalizeWorkbenchPlan, syncScreeningCriteria } from '../../utils/screeningPlan';
import { SelectedChips } from '../filters/SelectedChips';
import { PgyFindBloggerFilterPanel } from '../filters/PgyFindBloggerFilterPanel';

const REQUIRED_SCHEME_FIELDS = new Set(['博主类目', '粉丝量', '粉丝年龄', '合作报价']);
const SCHEME_LABELS = ['方案一', '方案二', '方案三', '方案四', '方案五', '方案六'];

const schemeKey = (scheme = {}, index = 0) => String(scheme.scheme_id || scheme.id || scheme.name || `scheme_${index + 1}`);
const schemeDisplayName = (scheme = {}, index = 0) => SCHEME_LABELS[index] || `方案${index + 1}`;

const resultCountText = (result = {}) => {
  const text = result.estimated_count_text || result.preflight?.actual_count_text;
  const count = result.estimated_count ?? result.preflight?.actual_recommend_count;
  if (text) return text;
  if (count !== undefined && count !== null) return `推荐 ${count} 位博主`;
  return '待预估';
};

const enabledSchemeIdsFor = (pgyPlan = {}) => {
  const schemes = Array.isArray(pgyPlan.schemes) ? pgyPlan.schemes : [];
  const allIds = schemes.map((scheme, index) => schemeKey(scheme, index));
  const savedIds = Array.isArray(pgyPlan.enabled_scheme_ids) ? pgyPlan.enabled_scheme_ids.map(String).filter(Boolean) : [];
  return savedIds.length ? savedIds.filter(id => allIds.includes(id)) : allIds;
};

const batchSchemes = (batch = {}) => {
  if (Array.isArray(batch.scheme_results) && batch.scheme_results.length) return batch.scheme_results;
  if (Array.isArray(batch.collection_plan?.schemes) && batch.collection_plan.schemes.length) return batch.collection_plan.schemes;
  return [];
};

export function OverviewTab({ project, onCollect, onStopCollect, onLatestBatch, onRunningBatch, onRefresh, onSavePlan, onTabChange }) {
  const creators = useMemo(() => getProjectCreators(project), [project]);
  const stats = getProjectStats(project);
  const projectKey = project.id || project.project_id;
  const [planDraft, setPlanDraft] = useState(() => normalizeWorkbenchPlan(project.screeningPlan || {}));
  const [planStatus, setPlanStatus] = useState('');
  const [planExpanded, setPlanExpanded] = useState(false);
  const [selectedSchemeIds, setSelectedSchemeIds] = useState([]);
  const [expandedSchemeId, setExpandedSchemeId] = useState('');
  const [collectSchemeResults, setCollectSchemeResults] = useState([]);
  const [schemeSaveStatus, setSchemeSaveStatus] = useState({});
  const [collectLimit, setCollectLimit] = useState(5000);
  const [collectStatus, setCollectStatus] = useState('');
  const [collecting, setCollecting] = useState(false);
  const [stoppingCollect, setStoppingCollect] = useState(false);
  const [collectProgress, setCollectProgress] = useState(null);
  const editingPlanRef = useRef(false);
  const lastProjectKeyRef = useRef(projectKey);
  const activeBatchIdRef = useRef('');
  const lastLoadedBatchIdRef = useRef('');
  const pollingTimerRef = useRef(null);

  const stopProgressPolling = useCallback(() => {
    if (pollingTimerRef.current) {
      window.clearInterval(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }
  }, []);

  const applyBatchProgress = useCallback((batch, { resume = false } = {}) => {
    if (!batch?.batch_id) return false;
    if (activeBatchIdRef.current && batch.batch_id !== activeBatchIdRef.current) {
      return false;
    }
    if (!activeBatchIdRef.current) {
      activeBatchIdRef.current = batch.batch_id;
    }
    setCollectProgress(batch);
    const schemes = batchSchemes(batch);
    if (schemes.length) setCollectSchemeResults(schemes);
    if (batch.status === 'running') {
      const stageText = batch.progress_message || '采集中';
      setCollecting(true);
      setCollectStatus(`${resume ? '已续连后台采集：' : ''}${stageText} · 已采集 ${batch.total_count || 0} · 已进筛选 ${batch.success_count || 0}`);
      return true;
    }
    setCollecting(false);
    setStoppingCollect(false);
    activeBatchIdRef.current = '';
    if (batch.status === 'success') {
      setCollectStatus(`采集完成，已进入筛选工作台 ${batch.success_count || 0} 个达人`);
    } else if (batch.status === 'stopped') {
      setCollectStatus(batch.progress_message || batch.error_message || '采集已停止');
    } else if (batch.status === 'failed') {
      setCollectStatus(batch.error_message || batch.progress_message || '采集失败');
    } else {
      setCollectStatus(batch.progress_message || batch.status || '采集状态已更新');
    }
    return false;
  }, []);

  const startProgressPolling = useCallback((initialBatchId = '') => {
    if (!onLatestBatch) return;
    if (initialBatchId) activeBatchIdRef.current = initialBatchId;
    stopProgressPolling();
    const poll = async () => {
      if (!activeBatchIdRef.current) {
        stopProgressPolling();
        return;
      }
      try {
        const batch = await onLatestBatch();
        if (!batch?.batch_id) return;
        const stillRunning = applyBatchProgress(batch);
        if (!stillRunning) {
          stopProgressPolling();
          await onRefresh?.();
        }
      } catch {
        // 页面可暂时失去连接，下一轮继续尝试。
      }
    };
    pollingTimerRef.current = window.setInterval(poll, 2000);
    poll();
  }, [applyBatchProgress, onLatestBatch, onRefresh, stopProgressPolling]);

  useEffect(() => {
    const sameProject = lastProjectKeyRef.current === projectKey;
    if (sameProject && editingPlanRef.current) {
      return;
    }
    stopProgressPolling();
    activeBatchIdRef.current = '';
    const nextPlan = normalizeWorkbenchPlan(project.screeningPlan || {});
    const nextSchemes = nextPlan.pgyCollectionPlan?.schemes || [];
    const nextIds = enabledSchemeIdsFor(nextPlan.pgyCollectionPlan || {});
    lastProjectKeyRef.current = projectKey;
    editingPlanRef.current = false;
    setPlanDraft(nextPlan);
    setSelectedSchemeIds(nextIds);
    setExpandedSchemeId(nextIds[0] || (nextSchemes[0] ? schemeKey(nextSchemes[0], 0) : ''));
    setCollectSchemeResults([]);
    setSchemeSaveStatus({});
    setPlanStatus('');
    lastLoadedBatchIdRef.current = '';
  }, [projectKey, project.screeningPlan, stopProgressPolling]);

  useEffect(() => () => stopProgressPolling(), [stopProgressPolling]);

  const savedPlan = useMemo(() => normalizeWorkbenchPlan(project.screeningPlan || {}), [project.screeningPlan]);
  const planDirty = JSON.stringify(planDraft) !== JSON.stringify(savedPlan);
  const pgyPlan = planDraft.pgyCollectionPlan || {};
  const schemes = Array.isArray(pgyPlan.schemes) ? pgyPlan.schemes : [];
  const schemeResultById = useMemo(() => {
    const map = new Map();
    collectSchemeResults.forEach(item => map.set(String(item.scheme_id || item.id || item.name || ''), item));
    return map;
  }, [collectSchemeResults]);
  const collectionResult = {
    collected: creators.length,
    scored: creators.filter(item => Number(item.baseScore || 0) > 0).length,
    passedFilters: creators.filter(item => item.baseScore >= 90 && !item.risk?.includes('无蒲公英')).length,
    needsManual: creators.filter(item => item.baseScore < 90 || item.risk?.length).length,
  };
  const targetCount = Number(project.creatorCount || 0);
  const passRate = collectionResult.collected > 0 ? collectionResult.passedFilters / collectionResult.collected : 0;
  const qualifiedGap = Math.max(0, targetCount - collectionResult.passedFilters);
  const expectedShortage = qualifiedGap === 0 ? 0 : passRate > 0 ? Math.ceil(qualifiedGap / passRate) : qualifiedGap;
  const passRateLabel = collectionResult.collected > 0 ? `${Math.round(passRate * 100)}%` : '待采集';
  const collectionMetrics = [
    {
      title: '累计采集',
      value: collectionResult.collected,
      subtitle: '待评分匹配',
      icon: Database,
      color: 'blue',
    },
    {
      title: '通过率',
      value: passRateLabel,
      subtitle: `${collectionResult.passedFilters} 位通过初筛`,
      icon: TrendingUp,
      color: 'green',
    },
    {
      title: '目标合格',
      value: targetCount,
      subtitle: `缺口 ${qualifiedGap} 位`,
      icon: Target,
      color: 'purple',
    },
    {
      title: '需完善',
      value: expectedShortage,
      subtitle: '按通过率推算',
      icon: AlertTriangle,
      color: expectedShortage > 0 ? 'amber' : 'green',
    },
  ];
  const collectionTaskResults = [
    ['已采集候选', collectionResult.collected, '待评分匹配'],
    ['已完成初评', collectionResult.scored, 'ABC 分档'],
    ['初筛可用', collectionResult.passedFilters, '>=90 或高潜'],
    ['需人工判断', collectionResult.needsManual, '风险或低分'],
  ];

  const planSummary = `${selectedSchemeIds.length || schemes.length} 套采集方案 · ${pgyPlan.display_metrics?.length || 0} 个展示指标`;
  const selectedSchemes = schemes.filter((scheme, index) => selectedSchemeIds.includes(schemeKey(scheme, index)));

  const updatePlanDraft = (updater) => {
    editingPlanRef.current = true;
    setPlanStatus('正在自动保存筛选条件...');
    setPlanDraft(updater);
  };

  useEffect(() => {
    if (!editingPlanRef.current || !planDirty) return;
    const timer = window.setTimeout(async () => {
      try {
        const nextPlan = syncScreeningCriteria({
          ...planDraft,
          pgyCollectionPlan: {
            ...(planDraft.pgyCollectionPlan || {}),
            enabled_scheme_ids: selectedSchemeIds,
          },
        });
        await onSavePlan?.(nextPlan);
        editingPlanRef.current = false;
        setPlanDraft(normalizeWorkbenchPlan(nextPlan));
        setPlanStatus('筛选条件已自动保存，刷新后会保留');
      } catch (error) {
        setPlanStatus(error.message || '自动保存筛选条件失败，请点击保存计划重试');
      }
    }, 700);
    return () => window.clearTimeout(timer);
  }, [onSavePlan, planDirty, planDraft, selectedSchemeIds]);

  useEffect(() => {
    let alive = true;
    const loadLatestBatch = async () => {
      if (!onLatestBatch) return;
      try {
        const runningBatch = await onRunningBatch?.();
        if (alive && runningBatch?.batch_id) {
          lastLoadedBatchIdRef.current = runningBatch.batch_id;
          applyBatchProgress(runningBatch, { resume: true });
          startProgressPolling(runningBatch.batch_id);
          return;
        }
        const batch = await onLatestBatch();
        if (!alive || !batch?.batch_id || batch.batch_id === lastLoadedBatchIdRef.current) return;
        lastLoadedBatchIdRef.current = batch.batch_id;
        const schemes = batchSchemes(batch);
        if (schemes.length) setCollectSchemeResults(schemes);
        if (batch.status) setCollectProgress(batch);
      } catch {
        // 历史批次读取失败不影响页面编辑。
      }
    };
    loadLatestBatch();
    return () => {
      alive = false;
    };
  }, [applyBatchProgress, onLatestBatch, onRunningBatch, projectKey, startProgressPolling]);

  const updateWeight = (key, value) => {
    const number = Math.max(0, Number(value || 0));
    updatePlanDraft(old => ({ ...old, scoringWeights: { ...(old.scoringWeights || {}), [key]: number } }));
  };

  const patchScheme = (targetIndex, patcher) => {
    updatePlanDraft(old => {
      const oldPlan = old.pgyCollectionPlan || {};
      const nextSchemes = (oldPlan.schemes || []).map((scheme, index) => (
        index === targetIndex ? patcher(scheme) : scheme
      ));
      return {
        ...old,
        pgyCollectionPlan: {
          ...oldPlan,
          schemes: nextSchemes,
        },
      };
    });
  };

  const updateSchemeActiveFilters = (targetIndex, filters = []) => {
    const requiredFilters = filters.filter(item => REQUIRED_SCHEME_FIELDS.has(item.field));
    const enabledAdditionalFilters = filters.filter(item => !REQUIRED_SCHEME_FIELDS.has(item.field));
    patchScheme(targetIndex, scheme => {
      const additionalFilters = mergeOptionItems(getSchemeAdditionalFilters(scheme), enabledAdditionalFilters, pgyFilterKey);
      return {
        ...scheme,
        required_filters: requiredFilters,
        base_filters: requiredFilters,
        additional_filters: additionalFilters,
        extra_filters: additionalFilters,
        enabled_additional_filters: enabledAdditionalFilters,
        enabled_extra_filters: enabledAdditionalFilters,
      };
    });
  };

  const toggleSchemeAdditionalFilter = (targetIndex, filter) => {
    patchScheme(targetIndex, scheme => {
      const enabled = scheme.enabled_additional_filters || scheme.enabled_extra_filters || [];
      const exists = enabled.some(item => pgyFilterKey(item) === pgyFilterKey(filter));
      const nextEnabled = exists ? enabled.filter(item => pgyFilterKey(item) !== pgyFilterKey(filter)) : [...enabled, filter];
      return {
        ...scheme,
        enabled_additional_filters: nextEnabled,
        enabled_extra_filters: nextEnabled,
      };
    });
  };

  const toggleScheme = (id) => {
    setSelectedSchemeIds(old => {
      const nextIds = old.includes(id) ? old.filter(item => item !== id) : [...old, id];
      editingPlanRef.current = true;
      setPlanStatus('正在自动保存筛选条件...');
      setPlanDraft(plan => ({
        ...plan,
        pgyCollectionPlan: {
          ...(plan.pgyCollectionPlan || {}),
          enabled_scheme_ids: nextIds,
        },
      }));
      return nextIds;
    });
  };

  const savePlan = async () => {
    setPlanStatus('正在保存筛选计划...');
    try {
      const nextPlan = syncScreeningCriteria({
        ...planDraft,
        pgyCollectionPlan: {
          ...(planDraft.pgyCollectionPlan || {}),
          enabled_scheme_ids: selectedSchemeIds,
        },
      });
      await onSavePlan?.(nextPlan);
      editingPlanRef.current = false;
      setPlanDraft(normalizeWorkbenchPlan(nextPlan));
      setPlanStatus('采集筛选计划已保存，并同步到项目配置');
    } catch (error) {
      setPlanStatus(error.message || '筛选计划保存失败');
    }
  };

  const saveSchemeConfig = async (id) => {
    setSchemeSaveStatus(old => ({ ...old, [id]: '正在保存本方案...' }));
    try {
      const nextPlan = syncScreeningCriteria({
        ...planDraft,
        pgyCollectionPlan: {
          ...(planDraft.pgyCollectionPlan || {}),
          enabled_scheme_ids: selectedSchemeIds,
        },
      });
      await onSavePlan?.(nextPlan);
      editingPlanRef.current = false;
      setPlanDraft(normalizeWorkbenchPlan(nextPlan));
      setSchemeSaveStatus(old => ({ ...old, [id]: '本方案已保存，采集会使用当前配置' }));
      setPlanStatus('方案配置已保存，并同步到项目配置');
    } catch (error) {
      setSchemeSaveStatus(old => ({ ...old, [id]: error.message || '本方案保存失败' }));
    }
  };

  const runCollect = async () => {
    if (collecting) return;
    if (schemes.length && selectedSchemeIds.length === 0) {
      setCollectStatus('请先勾选至少一个采集方案');
      return;
    }
    setCollecting(true);
    setStoppingCollect(false);
    activeBatchIdRef.current = '';
    setCollectStatus(`正在采集，目标上限 ${collectLimit} 个，已选 ${selectedSchemeIds.length || 1} 套方案...`);
    setCollectProgress({ status: 'running', total_count: 0, success_count: 0, progress_stage: 'starting', progress_message: '正在启动采集任务' });
    setCollectSchemeResults([]);
    let keepPollingAfterStart = false;
    stopProgressPolling();
    try {
      const result = await onCollect(syncScreeningCriteria(planDraft), {
        limit: collectLimit,
        schemeIds: selectedSchemeIds,
        multiScheme: true,
        preflight: true,
        asyncCollect: true,
      });
      activeBatchIdRef.current = result?.batch?.batch_id || activeBatchIdRef.current;
      if (result?.accepted) {
        keepPollingAfterStart = true;
        setCollectProgress(result.batch || null);
        setCollectStatus(result.message || '采集已在后台启动，正在刷新进度...');
        startProgressPolling(activeBatchIdRef.current);
        return;
      }
      const schemes = batchSchemes(result);
      if (schemes.length) setCollectSchemeResults(schemes);
      if (result?.ok) {
        const count = result.batch?.success_count ?? result.creators?.length ?? 0;
        setCollectProgress(result.batch || null);
        setCollectStatus(`采集完成，已进入筛选工作台 ${count} 个达人`);
      } else if (result?.stopped || result?.batch?.status === 'stopped') {
        setCollectProgress(result.batch || null);
        setCollectStatus('采集已停止');
      } else {
        setCollectProgress(result?.batch || null);
        setCollectStatus(result?.message || result?.error || '采集未完成');
      }
    } catch (error) {
      setCollectStatus(error.message || '采集失败');
    } finally {
      if (!keepPollingAfterStart) {
        stopProgressPolling();
        setCollecting(false);
        setStoppingCollect(false);
        activeBatchIdRef.current = '';
      }
    }
  };

  const stopCollect = async () => {
    if (!collecting || stoppingCollect) return;
    setStoppingCollect(true);
    setCollectStatus('正在请求停止采集...');
    try {
      const result = await onStopCollect?.();
      activeBatchIdRef.current = result?.batch?.batch_id || activeBatchIdRef.current;
      if (result?.batch) setCollectProgress(result.batch);
      setCollectStatus(result?.message || '已发送停止请求，当前步骤结束后会停止');
    } catch (error) {
      setCollectStatus(error.message || '停止采集失败');
      setStoppingCollect(false);
    }
  };

  return (
    <div>
      {/* 项目概览 */}
      <div className="card screening-section-card screening-project-summary" style={{ marginBottom: 24 }}>
        <div className="collection-overview-hero">
          <div>
            <div className="screening-workbench-eyebrow">Collection & Intake</div>
            <h3>{project.name}</h3>
            <p>{project.product} · {project.period} · <Badge variant={project.poolType === 'shared' ? 'blue' : 'purple'} style={{ marginLeft: 4 }}>{project.poolType === 'shared' ? '共享池' : '独立池'}</Badge></p>
          </div>
          <Badge variant={project.status === '进行中' ? 'blue' : project.status === '已完成' ? 'green' : 'amber'} style={{ fontSize: 13 }}>{project.status}</Badge>
        </div>
        <div className="collection-section-heading">
          <h4><Activity size={16} /> 指标预览</h4>
          <span>基于筛选工作台候选与初筛通过率自动推算</span>
        </div>
        <div className="collection-metric-preview-grid">
          {collectionMetrics.map(metric => {
            const Icon = metric.icon;
            return (
              <div key={metric.title} className={`collection-metric-card collection-metric-card-${metric.color}`}>
                <div className="collection-metric-title" title={metric.title}>{metric.title}</div>
                <div className="collection-metric-main">
                  <div className="collection-metric-icon">
                    <Icon size={22} />
                  </div>
                  <strong>{metric.value}</strong>
                </div>
                <div className="collection-metric-subtitle">{metric.subtitle}</div>
              </div>
            );
          })}
        </div>
        <div className="collector-inline-panel">
          <div className="collector-inline-header">
            <h4><Bot size={16} /> 蒲公英采集执行</h4>
            <div className="collector-action-row">
              <label className="collector-limit-control">
                <span>采集上限</span>
                <input
                  type="number"
                  min="1"
                  max="1000"
                  step="50"
                  value={collectLimit}
                  onChange={(event) => {
                    const nextValue = Number(event.target.value || 1);
                    setCollectLimit(Math.max(1, Math.min(5000, nextValue)));
                  }}
                />
              </label>
              <button className="btn btn-primary collector-action collector-action-primary" onClick={runCollect} disabled={collecting}>
                <Download size={16} />{collecting ? '采集中...' : '一键采集'}
              </button>
              {collecting && (
                <button className="btn btn-secondary collector-action collector-action-stop" onClick={stopCollect} disabled={stoppingCollect}>
                  <Square size={15} />{stoppingCollect ? '停止中...' : '停止采集'}
                </button>
              )}
            </div>
          </div>
          {collectStatus && (
            <div className={`collector-status-line ${collectStatus.includes('失败') || collectStatus.includes('未完成') || collectStatus.includes('运行') ? 'is-error' : ''}`}>
              {collectStatus}
            </div>
          )}
          {collectProgress && (
            <div className="collector-progress-panel">
              <div className="collector-progress-row">
                <span>采集</span>
                <strong>{collectProgress.total_count || 0}</strong>
                <small>候选达人</small>
              </div>
              <div className="collector-progress-row">
                <span>筛选</span>
                <strong>{collectProgress.success_count || 0}</strong>
                <small>已进工作台</small>
              </div>
              <div className="collector-progress-row">
                <span>阶段</span>
                <strong>{collectProgress.progress_stage || collectProgress.status || '-'}</strong>
                <small>{collectProgress.progress_message || collectProgress.error_message || '等待更新'}</small>
              </div>
            </div>
          )}
          <div className="collector-result-strip">
            {collectionTaskResults.map(([label, value, desc]) => (
              <div key={label} className="collector-result-item">
                <span>{label}</span>
                <strong>{value}</strong>
                <small>{desc}</small>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 当前筛选计划 */}
      <div className="collection-workbench-grid" style={{ marginBottom: 24 }}>
        <div className="card screening-section-card collection-plan-panel">
          <div className="collection-plan-collapsible-header">
            <button
              type="button"
              className={`collection-plan-collapse-button ${planExpanded ? 'is-expanded' : ''}`}
              onClick={() => setPlanExpanded(value => !value)}
              aria-expanded={planExpanded}
            >
              <span className="collection-plan-collapse-main">
                <span className="collection-plan-collapse-icon">
                  <Filter size={15} />
                </span>
                <span className="collection-plan-collapse-copy">
                  <strong>采集筛选计划</strong>
                  <small>{planSummary}</small>
                </span>
              </span>
              <span className="collection-plan-collapse-action">
                <span className="collection-plan-toggle-text">{planExpanded ? '收起计划' : '展开计划'}</span>
                <ChevronDown size={16} className={planExpanded ? 'is-open' : ''} />
              </span>
            </button>
            <div className="collection-plan-header-badges">
              <Badge variant={planDraft.briefType === 'complex' ? 'amber' : 'blue'}>{planDraft.briefType === 'complex' ? '复杂需求' : '标准需求'}</Badge>
              {planDirty && <Badge variant="purple">未应用</Badge>}
            </div>
          </div>
          {planExpanded ? (
            <>
              {schemes.length > 0 && (
                <div className="collection-scheme-card-grid">
                  {schemes.map((scheme, index) => {
                    const id = schemeKey(scheme, index);
                    const selected = selectedSchemeIds.includes(id);
                    const expanded = expandedSchemeId === id;
                    const requiredFilters = getSchemeRequiredFilters(scheme);
                    const additionalFilters = getSchemeAdditionalFilters(scheme);
                    const enabledAdditionalFilters = scheme.enabled_additional_filters || scheme.enabled_extra_filters || [];
                    const editableFilters = mergeOptionItems(requiredFilters, enabledAdditionalFilters, pgyFilterKey);
                    const result = schemeResultById.get(id) || {};
                    return (
                      <div key={id} className={`collection-scheme-card ${selected ? 'is-selected' : ''}`}>
                        <div className="collection-scheme-card-head">
                          <label className="collection-scheme-check">
                            <input
                              type="checkbox"
                              checked={selected}
                              onChange={() => toggleScheme(id)}
                            />
                            <span>
                              <strong>{schemeDisplayName(scheme, index)}</strong>
                              <small>{scheme.name || id}</small>
                            </span>
                          </label>
                          <button type="button" className="collection-scheme-config-button" onClick={() => setExpandedSchemeId(expanded ? '' : id)}>
                            <Settings size={14} />配置
                            <ChevronDown size={14} className={expanded ? 'is-open' : ''} />
                          </button>
                        </div>
                        <div className="collection-scheme-goal">{scheme.goal || '按该方案独立应用蒲公英筛选并采集'}</div>
                        <div className="collection-scheme-chip-row">
                          {editableFilters.slice(0, 5).map(item => (
                            <span key={pgyFilterKey(item)}>{pgyFilterLabel(item)}</span>
                          ))}
                          {editableFilters.length > 5 && <span>+{editableFilters.length - 5}</span>}
                        </div>
                        <div className="collection-scheme-stats">
                          <div>
                            <span>蒲公英预估</span>
                            <strong>{resultCountText(result)}</strong>
                          </div>
                          <div>
                            <span>真实入库</span>
                            <strong>{result.ingested_count ?? result.collected_count ?? '-'}</strong>
                          </div>
                        </div>
                        <div className="collection-scheme-save-row">
                          <span className={String(schemeSaveStatus[id] || '').includes('失败') ? 'is-error' : ''}>
                            {schemeSaveStatus[id] || (selected ? '已勾选，保存后纳入采集' : '未勾选，保存后不纳入采集')}
                          </span>
                          <button type="button" className="btn btn-primary btn-sm" onClick={() => saveSchemeConfig(id)}>
                            <Save size={14} />保存本方案
                          </button>
                        </div>
                        {expanded && (
                          <div className="collection-scheme-config">
                            <div className="collection-scheme-config-title">
                              <span>已应用条件</span>
                              <small>修改后先保存计划，再启动采集</small>
                            </div>
                            <PgyFindBloggerFilterPanel
                              filters={editableFilters}
                              onChange={(nextFilters) => updateSchemeActiveFilters(index, nextFilters)}
                            />
                            {additionalFilters.length > 0 && (
                              <div className="collection-scheme-extra-list">
                                <span>可选附加条件</span>
                                <div>
                                  {additionalFilters.map(item => {
                                    const active = enabledAdditionalFilters.some(next => pgyFilterKey(next) === pgyFilterKey(item));
                                    return (
                                      <button
                                        key={pgyFilterKey(item)}
                                        type="button"
                                        className={active ? 'is-active' : ''}
                                        onClick={() => toggleSchemeAdditionalFilter(index, item)}
                                      >
                                        {active ? <CheckCircle2 size={13} /> : <Plus size={13} />}
                                        {pgyFilterLabel(item)}
                                      </button>
                                    );
                                  })}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
              <div className="collection-plan-actions">
                <span className={planStatus.includes('失败') ? 'is-error' : ''}>{planStatus || '修改后点击保存，采集会使用当前筛选计划。'}</span>
                <button className="btn btn-primary" onClick={savePlan} disabled={!planDirty && planStatus.includes('已保存')}>
                  <Save size={14} style={{ marginRight: 4 }} />保存计划
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="collection-plan-collapsed-body">
                <div className="collection-plan-compact">
                  <SelectedChips
                    items={selectedSchemes.slice(0, 4)}
                    getKey={schemeKey}
                    getLabel={(scheme) => scheme.name || scheme.scheme_id || scheme.id || '未命名方案'}
                    emptyText="暂无已勾选方案"
                  />
                  {selectedSchemes.length > 4 && <span className="collection-compact-more">+{selectedSchemes.length - 4}</span>}
                </div>
              </div>
              <div className="collection-plan-actions">
                <span className={planStatus.includes('失败') ? 'is-error' : ''}>{planStatus || '已收起，展开后可继续编辑筛选计划。'}</span>
                <button className="btn btn-primary" onClick={() => setPlanExpanded(true)}>
                  <ChevronDown size={14} className="is-open" />展开
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* 筛选工作台候选预览 */}
      <div className="card screening-section-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h4 style={{ margin: 0, color: 'var(--text-primary)' }}>采集结果预览 <span style={{ color: 'var(--text-secondary)', fontWeight: 400, fontSize: 14 }}>（{creators.length}人）</span></h4>
          <button className="btn btn-sm btn-secondary" onClick={() => onTabChange('screening-review')}>人工筛选 <ArrowRight size={14} /></button>
        </div>
        <DataTable
          columns={[
            { key: 'name', label: '达人昵称', render: (v, row) => (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--border-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600 }}>{v[0]}</div>
                <span style={{ color: 'var(--text-primary)' }}>{v}</span>
              </div>
            )},
            { key: 'type', label: '类型', render: (v, row) => <Badge variant={row.typeVariant}>{v}</Badge> },
            { key: 'followers', label: '粉丝数' },
            { key: 'quote', label: '报价' },
            { key: 'baseScore', label: '初筛总分', render: v => {
              const tier = getScoreTier(v);
              return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><span style={{ fontWeight: 700, color: getScoreColor(v) }}>{v}</span><Badge variant={tier.variant}>{tier.label}</Badge></span>;
            } },
            { key: 'risk', label: '风险', render: v => v?.length > 0 ? v.map((t, i) => <span key={i} className="tag" style={{ marginRight: 4, fontSize: 11 }}>{t}</span>) : <span style={{ color: 'var(--text-muted)' }}>-</span> },
          ]}
          data={creators.slice(0, 5)}
        />
        {creators.length > 5 && (
          <div style={{ textAlign: 'center', padding: '12px 0 0', borderTop: '1px solid var(--border-primary)' }}>
            <button className="btn btn-sm btn-ghost" onClick={() => onTabChange('screening-review')}>还有 {creators.length - 5} 位达人，进入人工筛选 <ArrowRight size={14} /></button>
          </div>
        )}
      </div>
    </div>
  );
}
