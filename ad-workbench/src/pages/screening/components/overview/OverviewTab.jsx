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
import {
  DEFAULT_SCORING_HARD_FILTER_FIELDS,
  hardFilterKey,
  hardFilterLabel,
} from '../../constants/screeningConstants';
import { getProjectCreators, getProjectStats } from '../../utils/projectMappers';
import { getScoreColor, getScoreTier } from '../../utils/creatorScoring';
import {
  collectionHardFiltersToPgyFilters,
  markManualPgyFilters,
  mergeOptionItems,
  pgyFilterKey,
  syncCollectionHardFiltersFromPgyFilters,
} from '../../utils/pgyFilters';
import { getSchemeAdditionalFilters, getSchemeRequiredFilters, normalizeWorkbenchPlan, syncScreeningCriteria } from '../../utils/screeningPlan';
import { SelectedChips } from '../filters/SelectedChips';
import { PgyFindBloggerFilterPanel } from '../filters/PgyFindBloggerFilterPanel';

export function OverviewTab({ project, onCollect, onLatestBatch, onSavePlan, onTabChange }) {
  const creators = useMemo(() => getProjectCreators(project), [project]);
  const stats = getProjectStats(project);
  const [planDraft, setPlanDraft] = useState(() => normalizeWorkbenchPlan(project.screeningPlan || {}));
  const [planStatus, setPlanStatus] = useState('');
  const [planExpanded, setPlanExpanded] = useState(false);
  const [collectLimit, setCollectLimit] = useState(1000);
  const [collectStatus, setCollectStatus] = useState('');
  const [collecting, setCollecting] = useState(false);
  const [collectProgress, setCollectProgress] = useState(null);

  useEffect(() => {
    setPlanDraft(normalizeWorkbenchPlan(project.screeningPlan || {}));
    setPlanStatus('');
  }, [project.id, project.screeningPlan]);

  const savedPlan = useMemo(() => normalizeWorkbenchPlan(project.screeningPlan || {}), [project.screeningPlan]);
  const planDirty = JSON.stringify(planDraft) !== JSON.stringify(savedPlan);
  const pgyPlan = planDraft.pgyCollectionPlan || {};
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
      subtitle: '达人已入本项目',
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
      title: '需补采',
      value: expectedShortage,
      subtitle: '按通过率推算',
      icon: AlertTriangle,
      color: expectedShortage > 0 ? 'amber' : 'green',
    },
  ];
  const collectionTaskResults = [
    ['已采集入库', collectionResult.collected, '去重达人'],
    ['已完成初评', collectionResult.scored, 'ABC 分档'],
    ['初筛可用', collectionResult.passedFilters, '>=90 或高潜'],
    ['需人工判断', collectionResult.needsManual, '风险或低分'],
  ];

  const planSummary = `${planDraft.collectionHardFilters?.length || 0} 个采集前条件 · ${pgyPlan.filters?.length || 0} 个蒲公英条件 · ${pgyPlan.display_metrics?.length || 0} 个展示指标`;
  const activePgyFilters = useMemo(
    () => mergeOptionItems(
      collectionHardFiltersToPgyFilters(planDraft.collectionHardFilters || []),
      pgyPlan.filters || [],
      pgyFilterKey
    ),
    [planDraft.collectionHardFilters, pgyPlan.filters]
  );

  const updatePgyFilters = (filters = []) => {
    const normalizedFilters = markManualPgyFilters(filters);
    setPlanDraft(old => ({
      ...old,
      collectionHardFilters: syncCollectionHardFiltersFromPgyFilters(normalizedFilters, old.collectionHardFilters || []),
      pgyCollectionPlan: {
        ...(old.pgyCollectionPlan || {}),
        filters: normalizedFilters,
        hard_filters: syncCollectionHardFiltersFromPgyFilters(normalizedFilters, old.collectionHardFilters || []),
      },
    }));
  };

  const updateWeight = (key, value) => {
    const number = Math.max(0, Number(value || 0));
    setPlanDraft(old => ({ ...old, scoringWeights: { ...(old.scoringWeights || {}), [key]: number } }));
  };

  const updateSchemeFilters = (schemeIndex, updater) => {
    setPlanDraft(old => {
      const schemes = [...(old.pgyCollectionPlan?.schemes || [])];
      const current = schemes[schemeIndex];
      if (!current) return old;
      schemes[schemeIndex] = updater({ ...current });
      return {
        ...old,
        pgyCollectionPlan: {
          ...(old.pgyCollectionPlan || {}),
          schemes,
        },
      };
    });
  };

  const updateSchemeFilterValue = (schemeIndex, group, filterIndex, value) => {
    updateSchemeFilters(schemeIndex, (scheme) => {
      const key = group === 'required' ? 'required_filters' : 'additional_filters';
      const legacyKey = group === 'required' ? 'base_filters' : 'extra_filters';
      const filters = [...(group === 'required' ? getSchemeRequiredFilters(scheme) : getSchemeAdditionalFilters(scheme))];
      if (!filters[filterIndex]) return scheme;
      filters[filterIndex] = { ...filters[filterIndex], value };
      return { ...scheme, [key]: filters, [legacyKey]: filters, filters: [] };
    });
  };

  const moveSchemeAdditionalFilter = (schemeIndex, filterIndex, direction) => {
    updateSchemeFilters(schemeIndex, (scheme) => {
      const filters = [...getSchemeAdditionalFilters(scheme)];
      const nextIndex = filterIndex + direction;
      if (nextIndex < 0 || nextIndex >= filters.length) return scheme;
      [filters[filterIndex], filters[nextIndex]] = [filters[nextIndex], filters[filterIndex]];
      return { ...scheme, additional_filters: filters, extra_filters: filters, filters: [] };
    });
  };

  const savePlan = async () => {
    setPlanStatus('正在保存筛选计划...');
    try {
      const nextPlan = syncScreeningCriteria(planDraft);
      await onSavePlan?.(nextPlan);
      setPlanDraft(nextPlan);
      setPlanStatus('采集筛选计划已保存，并同步到项目配置');
    } catch (error) {
      setPlanStatus(error.message || '筛选计划保存失败');
    }
  };

  const runCollect = async () => {
    if (collecting) return;
    setCollecting(true);
    setCollectStatus(`正在采集，目标上限 ${collectLimit} 个...`);
    setCollectProgress({ status: 'running', total_count: 0, success_count: 0, progress_stage: 'starting', progress_message: '正在启动采集任务' });
    let stopped = false;
    const pollProgress = async () => {
      if (stopped || !onLatestBatch) return;
      try {
        const batch = await onLatestBatch();
        if (batch?.batch_id) {
          setCollectProgress(batch);
          const stageText = batch.progress_message || batch.status || '采集中';
          setCollectStatus(`${stageText} · 已采集 ${batch.total_count || 0} · 已入库 ${batch.success_count || 0}`);
        }
      } catch {
        // Ignore transient polling failures; the final collect response still settles the UI.
      }
    };
    const progressTimer = window.setInterval(pollProgress, 2000);
    pollProgress();
    try {
      const result = await onCollect(syncScreeningCriteria(planDraft), { limit: collectLimit });
      stopped = true;
      window.clearInterval(progressTimer);
      if (result?.ok) {
        const count = result.batch?.success_count ?? result.creators?.length ?? 0;
        setCollectProgress(result.batch || null);
        setCollectStatus(`采集完成，已入库 ${count} 个达人`);
      } else {
        setCollectProgress(result?.batch || null);
        setCollectStatus(result?.message || result?.error || '采集未完成');
      }
    } catch (error) {
      stopped = true;
      window.clearInterval(progressTimer);
      setCollectStatus(error.message || '采集失败');
    } finally {
      stopped = true;
      window.clearInterval(progressTimer);
      setCollecting(false);
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
          <span>基于当前项目达人池与初筛通过率自动推算</span>
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
                    setCollectLimit(Math.max(1, Math.min(1000, nextValue)));
                  }}
                />
              </label>
              <button className="btn btn-primary collector-action collector-action-primary" onClick={runCollect} disabled={collecting}>
                <Download size={16} />{collecting ? '采集中...' : '一键采集'}
              </button>
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
                <span>入库</span>
                <strong>{collectProgress.success_count || 0}</strong>
                <small>已写入达人池</small>
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
            <button type="button" className="collection-plan-collapse-button" onClick={() => setPlanExpanded(value => !value)}>
              <Filter size={16} />
              <span>采集筛选计划</span>
              <small>{planSummary}</small>
              <ChevronDown size={16} className={planExpanded ? 'is-open' : ''} />
            </button>
            <div className="collection-plan-header-badges">
              <Badge variant={planDraft.briefType === 'complex' ? 'amber' : 'blue'}>{planDraft.briefType === 'complex' ? '复杂需求' : '标准需求'}</Badge>
              {planDirty && <Badge variant="purple">未应用</Badge>}
            </div>
          </div>
          {!planExpanded ? (
            <div className="collection-plan-compact">
              <SelectedChips
                items={(planDraft.collectionHardFilters || []).slice(0, 4)}
                getKey={hardFilterKey}
                getLabel={hardFilterLabel}
                onRemove={(item) => setPlanDraft(old => ({ ...old, collectionHardFilters: (old.collectionHardFilters || []).filter(next => hardFilterKey(next) !== hardFilterKey(item)) }))}
                emptyText="暂无采集前条件"
              />
              {(planDraft.collectionHardFilters || []).length > 4 && <span className="collection-compact-more">+{(planDraft.collectionHardFilters || []).length - 4}</span>}
            </div>
          ) : (
            <>
          <div className="collection-plan-block">
            <div className="collection-plan-title-row">
              <div>
                <div className="collection-plan-title">采集前筛选条件</div>
                <div className="collection-plan-subtitle">按蒲公英「找博主」筛选区组织，选中项会写入采集计划。</div>
              </div>
            </div>
            <PgyFindBloggerFilterPanel
              filters={activePgyFilters}
              onChange={updatePgyFilters}
            />
            {(pgyPlan.schemes || []).length > 0 && (
              <div className="collection-plan-block" style={{ marginTop: 16 }}>
                <div className="collection-plan-title-row">
                  <div>
                    <div className="collection-plan-title">方案筛选条件</div>
                    <div className="collection-plan-subtitle">必备筛选先执行；附加筛选按顺序叠加。</div>
                  </div>
                </div>
                <div style={{ display: 'grid', gap: 12 }}>
                  {(pgyPlan.schemes || []).map((scheme, schemeIndex) => {
                    const requiredFilters = getSchemeRequiredFilters(scheme);
                    const additionalFilters = getSchemeAdditionalFilters(scheme);
                    const schemeKey = scheme.scheme_id || scheme.id || scheme.name || schemeIndex;
                    return (
                      <div key={schemeKey} className="collection-selected-card" style={{ alignItems: 'stretch' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
                          <strong style={{ color: 'var(--text-primary)' }}>{scheme.name || schemeKey}</strong>
                          <Badge variant="blue">{scheme.target_count_range || pgyPlan.target_count_range || '50-2000'}</Badge>
                        </div>
                        <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
                          <div style={{ color: 'var(--text-secondary)', fontSize: 13 }}>必备筛选条件</div>
                          {requiredFilters.map((filter, filterIndex) => (
                            <div key={`${filter.field}-${filterIndex}`} className="collection-filter-row">
                              <span>{filter.field}</span>
                              <input
                                value={filter.value || ''}
                                onChange={(event) => updateSchemeFilterValue(schemeIndex, 'required', filterIndex, event.target.value)}
                              />
                            </div>
                          ))}
                        </div>
                        <div style={{ display: 'grid', gap: 8, marginTop: 12 }}>
                          <div style={{ color: 'var(--text-secondary)', fontSize: 13 }}>附加筛选条件</div>
                          {additionalFilters.length === 0 && <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>暂无附加筛选条件</span>}
                          {additionalFilters.map((filter, filterIndex) => (
                            <div key={`${filter.field}-${filterIndex}`} className="collection-filter-row">
                              <span>{filter.field}</span>
                              <input
                                value={filter.value || ''}
                                onChange={(event) => updateSchemeFilterValue(schemeIndex, 'additional', filterIndex, event.target.value)}
                              />
                              <button
                                type="button"
                                className="btn btn-ghost btn-icon btn-sm"
                                title="上移"
                                disabled={filterIndex === 0}
                                onClick={() => moveSchemeAdditionalFilter(schemeIndex, filterIndex, -1)}
                              >
                                <ChevronUp size={14} />
                              </button>
                              <button
                                type="button"
                                className="btn btn-ghost btn-icon btn-sm"
                                title="下移"
                                disabled={filterIndex === additionalFilters.length - 1}
                                onClick={() => moveSchemeAdditionalFilter(schemeIndex, filterIndex, 1)}
                              >
                                <ChevronDown size={14} />
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
            </>
          )}
          <div className="collection-plan-actions">
            <span className={planStatus.includes('失败') ? 'is-error' : ''}>{planStatus || '修改后点击保存，采集会使用当前筛选计划。'}</span>
            <button className="btn btn-primary" onClick={savePlan} disabled={!planDirty && planStatus.includes('已保存')}>
              <Save size={14} style={{ marginRight: 4 }} />保存计划
            </button>
          </div>
        </div>
      </div>

      {/* 达人池预览 */}
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
