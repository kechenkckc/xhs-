import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  LayoutDashboard, Users, BarChart3, FolderPlus, ScrollText, FolderOpen, ExternalLink,
  X,
} from 'lucide-react';
import TabBar from '../../components/TabBar';
import PageHeader from '../../components/PageHeader';
import { api } from './api/screeningApi';
import { initialProjects, initialScreeningStatus } from './constants/projectConstants';
import { mapBackendProject, parseStoredScreeningPlan } from './utils/projectMappers';
import { mapBackendCreator } from './utils/creatorMappers';
import { getScoreTier } from './utils/creatorScoring';
import { ProjectsPreview } from './components/project/ProjectsPreview';
import { CreateProjectModal } from './components/project/CreateProjectModal';
import { OverviewTab } from './components/overview/OverviewTab';
import { ScreeningReviewTab } from './components/screening-review/ScreeningReviewTab';
import { ScorePreviewTab } from './components/creator-pool/ScorePreviewTab';
import { ProjectSetupTab } from './components/project/ProjectSetupTab';
import { AuditLogTab } from './components/logs/AuditLogTab';
import { CreatorAuditTab } from './components/creator-audit/CreatorAuditTab';
import { AdvancedConfigTab } from './components/config/AdvancedConfigTab';

const tabs = [
  { key: 'projects', label: '项目预览', icon: <FolderOpen size={14} /> },
  { key: 'overview', label: '流程工作台', icon: <LayoutDashboard size={14} /> },
  { key: 'screening-review', label: '初筛评分 + 人工筛选', icon: <Users size={14} /> },
  { key: 'creator-audit', label: '审号工作台', icon: <BarChart3 size={14} /> },
  { key: 'score-preview', label: '候选评分预览', icon: <BarChart3 size={14} /> },
  { key: 'project-setup', label: '项目配置', icon: <FolderPlus size={14} /> },
  { key: 'audit-log', label: '操作日志', icon: <ScrollText size={14} /> },
  { key: 'legacy', label: '高级配置', icon: <ExternalLink size={14} /> },
];

function getProjectKey(project = {}) {
  return project?.id || project?.project_id || '';
}

function tierDistribution(creators = []) {
  const total = creators.length || 0;
  const groups = {};
  creators.forEach((creator) => {
    const tier = getScoreTier(Number(creator.baseScore || creator.total_score || 0));
    const label = tier.label || tier.key || '未分档';
    groups[label] = (groups[label] || 0) + 1;
  });
  return Object.entries(groups).map(([label, count]) => ({
    label,
    count,
    ratio: total ? Math.round((count / total) * 100) : 0,
  }));
}

function parseRawPayload(value) {
  if (!value) return {};
  if (typeof value === 'object') return value;
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function notesCountFromCreator(creator = {}) {
  const payload = parseRawPayload(creator.raw?.raw_payload || creator.rawPayload || creator.raw_payload);
  const lists = [payload.recent_notes, payload.note_cases, payload.cooperation_note_cases, payload.detail?.recent_notes, payload.detail?.note_cases];
  return lists.reduce((sum, list) => sum + (Array.isArray(list) ? list.length : 0), 0);
}

function durationBetween(startedAt, finishedAt) {
  if (!startedAt || !finishedAt) return '';
  const start = new Date(startedAt.replace(' ', 'T'));
  const end = new Date(finishedAt.replace(' ', 'T'));
  const diffSeconds = Math.max(0, Math.round((end - start) / 1000));
  if (!Number.isFinite(diffSeconds)) return '';
  if (diffSeconds < 60) return `${diffSeconds}秒`;
  const minutes = Math.floor(diffSeconds / 60);
  const seconds = diffSeconds % 60;
  return `${minutes}分${String(seconds).padStart(2, '0')}秒`;
}

function collectPerCreatorTiming(result = {}, limit = 5) {
  const updated = Array.isArray(result.updated) ? result.updated : [];
  const failed = Array.isArray(result.failed) ? result.failed : [];
  const successItems = updated
    .map((creator) => {
      const payload = parseRawPayload(creator.raw?.raw_payload || creator.rawPayload || creator.raw_payload);
      const timing = creator.detail_collection_timing || payload.detail_collection_timing || {};
      return {
        label: creator.nickname || creator.name || creator.creator_id || '达人',
        value: timing.duration_text || '-',
        note: timing.finished_at ? `完成于 ${timing.finished_at}` : '',
      };
    })
    .filter(item => item.value && item.value !== '-');
  const failedItems = failed
    .map((item) => {
      const timing = item?.detail_collection_timing || {};
      return {
        label: `${item.nickname || item.creator_id || '达人'}（失败）`,
        value: timing.duration_text || '-',
        note: item.message || '',
      };
    })
    .filter(item => item.value && item.value !== '-');
  return [...successItems, ...failedItems].slice(0, limit);
}

function buildCollectResultSummary(result = {}) {
  const creators = Array.isArray(result.creators) ? result.creators : [];
  const schemeResults = result.scheme_results || result.collection_plan?.schemes || [];
  const errors = [
    result.message && !result.ok ? result.message : '',
    ...(schemeResults || []).map(item => item?.message).filter(Boolean),
  ].filter(Boolean);
  return {
    type: result.ok ? 'success' : 'error',
    title: result.ok ? '采集完成' : (result.stopped ? '采集已停止' : '采集未完成'),
    subtitle: result.message || result.batch?.error_message || '',
    stats: [
      ['采集候选', result.batch?.total_count ?? creators.length ?? 0],
      ['进入工作台', result.batch?.success_count ?? creators.length ?? 0],
      ['失败/跳过', result.batch?.failed_count ?? 0],
      ['方案数', schemeResults.length || 0],
      ['开始时间', result.batch?.started_at || '-'],
      ['完成时间', result.batch?.finished_at || '-'],
      ['总耗时', durationBetween(result.batch?.started_at, result.batch?.finished_at) || '-'],
    ],
    tiers: tierDistribution(creators.map(mapBackendCreator)),
    schemes: (schemeResults || []).map(item => ({
      label: item.scheme_name || item.scheme_id || '方案',
      value: `${item.collected_count ?? 0} 采集 / ${item.ingested_count ?? 0} 入库`,
      note: item.estimated_count_text || item.message || '',
    })),
    errors,
  };
}

function buildDetailResultSummary(result = {}, requestedCount = 0, label = '') {
  const updated = Array.isArray(result.updated) ? result.updated : [];
  const failed = Array.isArray(result.failed) ? result.failed : [];
  const noteCount = updated.reduce((sum, creator) => sum + notesCountFromCreator(creator), 0);
  const timingSchemes = collectPerCreatorTiming(result);
  return {
    type: result.ok === false ? 'error' : 'success',
    title: result.ok === false ? '详情完善未完成' : '详情完善完成',
    subtitle: result.message || label || '',
    stats: [
      ['请求达人', requestedCount || updated.length + failed.length],
      ['成功完善', updated.length],
      ['失败', failed.length],
      ['采到笔记', noteCount],
      ['完成时间', result.finished_at || '-'],
      ['总耗时', result.duration_text || '-'],
      ['单个均耗时', result.average_duration_text || '-'],
    ],
    tiers: tierDistribution(updated.map(mapBackendCreator)),
    schemes: [
      ...(timingSchemes.length ? timingSchemes : []),
      ...(result.auto_writeback ? [{
        label: '飞书自动写回',
        value: `${result.auto_writeback.written_count || 0} 条`,
        note: result.auto_writeback.message || '',
      }] : []),
    ],
    errors: failed.map(item => `${item.nickname || item.creator_id || '未知达人'}：${item.message || '失败'}`),
  };
}

function detailProgressInfo(task = {}) {
  const total = Number(task.total_count || 0);
  const completed = Number(task.completed_count || 0);
  const failed = Number(task.failed_count || 0);
  const done = Math.min(total || completed + failed, completed + failed);
  const ratio = total ? Math.min(100, Math.round((done / total) * 100)) : 0;
  return {
    total,
    completed,
    failed,
    done,
    ratio,
    text: total ? `${done}/${total} 达人已完成` : `${done} 位达人已完成`,
  };
}

function buildScoreResultSummary(result = {}, refreshedCreators = []) {
  const mappedCreators = (refreshedCreators || []).map(mapBackendCreator);
  const sources = result.sources || {};
  const scored = result.scored ?? mappedCreators.length ?? 0;
  const sourceLabel = result.source === 'llm'
    ? '大模型评分'
    : result.source === 'generated'
      ? '测试生成评分'
      : '规则评分';
  const llmErrors = Array.isArray(result.llm_errors) ? result.llm_errors.filter(Boolean) : [];
  return {
    type: result.ok === false ? 'error' : 'success',
    title: result.ok === false ? 'AI 评分未完成' : 'AI 评分完成',
    subtitle: result.ok === false
      ? (result.message || result.error || '评分接口返回失败')
      : `批次 ${result.batch_id || '未记录'} · ${sourceLabel}`,
    stats: [
      ['评分达人', scored],
      ['大模型分析', sources.llm || 0],
      ['规则/兜底', (sources.generated || 0) + (sources.rule || 0)],
      ['触发来源', result.trigger_source || 'manual'],
    ],
    tiers: tierDistribution(mappedCreators),
    schemes: [
      { label: '评分来源', value: sourceLabel, note: result.source === 'llm' ? '已调用大模型生成推荐理由和维度分' : '当前使用规则或测试兜底，配置大模型后可重新评分' },
      { label: '后续动作', value: '已刷新筛选工作台', note: '可展开达人查看评分维度、推荐理由和风险提示' },
    ],
    errors: result.ok === false ? [result.message || result.error || '评分失败'] : llmErrors,
  };
}

function buildWritebackResultSummary(result = {}) {
  const syncStatus = result.sync_status || {};
  const selectedTable = result.selected_table || {};
  const imageResult = result.image_result || {};
  const target = result.target || {};
  const ok = result.ok !== false;
  const writtenCount = result.written_count ?? ((result.result?.created || []).length + (result.result?.updated || []).length);
  const errors = [
    !ok ? (result.message || result.error || '写回飞书失败') : '',
    imageResult?.ok === false ? (imageResult.message || imageResult.error || '粉丝画像图片写入失败') : '',
  ].filter(Boolean);

  return {
    type: ok ? 'success' : 'error',
    title: ok ? '写回飞书完成' : '写回飞书未完成',
    subtitle: ok ? (result.message || '已结束本次写回') : (result.message || result.error || '请检查飞书权限、字段映射或网络状态后重试'),
    stats: [
      ['写回达人', writtenCount ?? 0],
      ['成功标记', syncStatus.success ?? (ok ? writtenCount ?? 0 : 0)],
      ['失败', syncStatus.failed ?? (ok ? 0 : 1)],
      ['目标资源', target.resource_type || '-'],
      ['目标子表', selectedTable.name || selectedTable.title || selectedTable.sheet_id || selectedTable.table_id || '-'],
    ],
    schemes: [
      {
        label: '记录写入',
        value: ok ? '已返回结果' : '未完成',
        note: result.result?.message || result.error || '',
      },
      ...(imageResult.message ? [{
        label: '粉丝画像图片',
        value: imageResult.enabled === false ? '未启用' : (imageResult.ok === false ? '失败' : '已处理'),
        note: imageResult.message,
      }] : []),
    ],
    errors,
  };
}

function ResultSummaryModal({ summary, onClose }) {
  if (!summary) return null;
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal result-summary-modal" onClick={event => event.stopPropagation()}>
        <div className="modal-header result-summary-header">
          <div>
            <span className={`result-summary-pill is-${summary.type || 'success'}`}>{summary.type === 'error' ? '需要关注' : summary.type === 'progress' ? '进行中' : '已完成'}</span>
            <h3>{summary.title}</h3>
            {summary.subtitle && <p>{summary.subtitle}</p>}
          </div>
          <button className="btn btn-sm btn-ghost modal-close" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="modal-body">
          <div className="result-summary-stats">
            {(summary.stats || []).map(([label, value]) => (
              <div key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
          {!!summary.tiers?.length && (
            <div className="result-summary-section">
              <h4>档位占比</h4>
              <div className="result-summary-tier-list">
                {summary.tiers.map(item => (
                  <div key={item.label}>
                    <span>{item.label}</span>
                    <div><i style={{ width: `${item.ratio}%` }} /></div>
                    <em>{item.count} 位 · {item.ratio}%</em>
                  </div>
                ))}
              </div>
            </div>
          )}
          {!!summary.schemes?.length && (
            <div className="result-summary-section">
              <h4>执行明细</h4>
              <div className="result-summary-detail-list">
                {summary.schemes.map((item, index) => (
                  <div key={`${item.label}-${index}`}>
                    <strong>{item.label}</strong>
                    <span>{item.value}</span>
                    {item.note && <small>{item.note}</small>}
                  </div>
                ))}
              </div>
            </div>
          )}
          {!!summary.errors?.length && (
            <div className="result-summary-section">
              <h4>错误与跳过</h4>
              <div className="result-summary-error-list">
                {summary.errors.slice(0, 8).map((item, index) => <p key={index}>{item}</p>)}
                {summary.errors.length > 8 && <p>还有 {summary.errors.length - 8} 条未展示</p>}
              </div>
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn btn-primary" onClick={onClose}>知道了</button>
        </div>
      </div>
    </div>
  );
}

function DetailProgressBanner({ task, onDismiss }) {
  if (!task) return null;
  const progress = detailProgressInfo(task);
  return (
    <div className="detail-progress-banner">
      <div className="detail-progress-main">
        <div>
          <strong>详情完善中</strong>
          <span>{task.progress_message || progress.text}</span>
        </div>
        <small>{task.current_nickname || task.current_creator_id ? `当前：${task.current_nickname || task.current_creator_id}` : task.progress_stage || 'running'}</small>
      </div>
      <div className="detail-progress-track" aria-label={progress.text}>
        <i style={{ width: `${progress.ratio}%` }} />
      </div>
      <div className="detail-progress-meta">
        <span>{progress.text}</span>
        <span>成功 {progress.completed} · 失败 {progress.failed}</span>
      </div>
      <button className="btn btn-sm btn-ghost" onClick={onDismiss}>收起</button>
    </div>
  );
}
function patchProject(project = {}, patch = {}) {
  return {
    ...project,
    ...patch,
    ...(patch.project_id ? { id: patch.project_id, project_id: patch.project_id } : {}),
    ...(patch.project_name ? { name: patch.project_name, project_name: patch.project_name } : {}),
    ...(patch.target_qualified_creator_count ? { creatorCount: patch.target_qualified_creator_count } : {}),
    ...(patch.period_start ? { periodStart: patch.period_start } : {}),
    ...(patch.period_end ? { periodEnd: patch.period_end } : {}),
    ...(patch.brief ? { description: patch.brief, brief: { ...(project.brief || {}), description: patch.brief } } : {}),
    ...(patch.screening_plan ? { screeningPlan: parseStoredScreeningPlan(patch.screening_plan, project.screeningPlan || {}) } : {}),
  };
}

export default function ScreeningDashboard({ selectedProjectId = '', onSelectedProjectIdChange } = {}) {
  const navigate = useNavigate();
  const { tab } = useParams();
  const [activeTab, setActiveTab] = useState(tab || 'projects');
  const [projects, setProjects] = useState([]);
  const [currentProject, setCurrentProject] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [screeningStatus, setScreeningStatus] = useState(initialScreeningStatus);
  const [projectList, setProjectList] = useState([]);
  const [projectListLoadFailed, setProjectListLoadFailed] = useState(false);
  const [feishuConfig, setFeishuConfig] = useState(null);
  const [feishuTables, setFeishuTables] = useState([]);
  const [feishuFields, setFeishuFields] = useState([]);
  const [loadedCreatorProjectIds, setLoadedCreatorProjectIds] = useState({});
  const [resultModal, setResultModal] = useState(null);
  const [detailProgress, setDetailProgress] = useState(null);
  const currentProjectIdRef = useRef('');
  const detailCollectInFlightRef = useRef(new Set());
  const detailProgressTimerRef = useRef(null);
  const projectId = currentProject?.id || currentProject?.project_id;

  useEffect(() => {
    setActiveTab(tab || 'projects');
  }, [tab]);

  useEffect(() => {
    api('/api/projects?include_archived=true')
      .then((payload) => {
        setProjectList(payload.projects || []);
        setProjectListLoadFailed(false);
      })
      .catch(() => setProjectListLoadFailed(true));
  }, []);

  const mergedProjects = useMemo(() => {
    if (projectListLoadFailed) {
      return projects.length > 0 ? projects : initialProjects;
    }
    const templateMap = new Map(initialProjects.map((item) => [item.id, item]));
    const backendProjects = projectList.map((item) => {
      const mapped = mapBackendProject(item);
      const template = templateMap.get(item.project_id);
      return template ? { ...template, ...mapped } : mapped;
    });
    const backendIds = new Set(backendProjects.map(getProjectKey));
    const localOnlyProjects = projects.filter((item) => !backendIds.has(getProjectKey(item)));
    return [...backendProjects, ...localOnlyProjects];
  }, [projectList, projectListLoadFailed, projects]);

  useEffect(() => {
    currentProjectIdRef.current = projectId || '';
  }, [projectId]);

  useEffect(() => {
    if (!mergedProjects.length) return;
    const currentId = getProjectKey(currentProject);
    const next = selectedProjectId
      ? mergedProjects.find(item => getProjectKey(item) === selectedProjectId)
      : null;
    if (next && getProjectKey(next) !== currentId) {
      currentProjectIdRef.current = getProjectKey(next) || '';
      setCurrentProject(next);
      return;
    }
    if (!currentProject) {
      const fallback = next || mergedProjects[0];
      currentProjectIdRef.current = getProjectKey(fallback) || '';
      setCurrentProject(fallback);
      onSelectedProjectIdChange?.(getProjectKey(fallback));
    }
  }, [currentProject, mergedProjects, onSelectedProjectIdChange, selectedProjectId]);

  const selectProject = (project, options = {}) => {
    setCurrentProject(project);
    const nextId = getProjectKey(project);
    if (nextId) {
      currentProjectIdRef.current = nextId;
      onSelectedProjectIdChange?.(nextId);
      try {
        window.localStorage.setItem('adflow-selected-screening-project', nextId);
        window.localStorage.setItem('adflow-selected-project', nextId);
      } catch {
        // Project selection still works without local storage.
      }
    }
    if (options.navigateToOverview !== false) {
      setActiveTab('overview');
      navigate('/workbench/screening/overview');
    }
  };

  const createProject = (newProject) => {
    setProjects((prev) => [...prev, newProject]);
    setCurrentProject(newProject);
    onSelectedProjectIdChange?.(getProjectKey(newProject));
    setActiveTab('project-setup');
    setShowCreateModal(false);
    navigate('/workbench/screening/project-setup');
  };

  useEffect(() => {
    if (!projectId) {
      setFeishuConfig(null);
      setFeishuTables([]);
      setFeishuFields([]);
      return;
    }
    let cancelled = false;
    setFeishuTables([]);
    setFeishuFields([]);
    api(`/api/projects/feishu/connection?project_id=${encodeURIComponent(projectId)}`)
      .then((payload) => {
        if (cancelled) return;
        const config = payload.config || null;
        setFeishuConfig(config);
        if (config?.feishu_url) {
          updateCurrentProject({
            feishuBinding: {
              ...(currentProject?.feishuBinding || {}),
              linked: true,
              tableUrl: config.feishu_url,
              baseToken: config.target?.token || '',
              tableId: config.target?.table_id || '',
            },
          });
        }
      })
      .catch(() => {
        if (!cancelled) setFeishuConfig(null);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const updateCurrentProject = useCallback((patch) => {
    if (!currentProject) return;
    const currentId = getProjectKey(currentProject);
    const normalizedPatch = patchProject(currentProject, patch);
    setProjects((prev) => prev.map((item) => (getProjectKey(item) === currentId ? patchProject(item, patch) : item)));
    setProjectList((prev) => prev.map((item) => (getProjectKey(item) === currentId ? { ...item, ...patch } : item)));
    setCurrentProject((prev) => (prev ? patchProject(prev, patch) : prev));
  }, [currentProject]);

  const safeApi = useCallback(async (url, options = {}) => {
    try {
      return await api(url, options);
    } catch (error) {
      console.warn('[ScreeningDashboard]', error.message || error);
      return {
        ok: false,
        error: error.message || '请求失败',
        message: error.message || '请求失败',
        ...(error.detail && typeof error.detail === 'object' ? error.detail : {}),
      };
    }
  }, []);

  const applyProjectPayload = useCallback((projectPayload, mappedCreators, options = {}) => {
    const payloadProjectId = projectPayload?.project?.project_id;
    if (payloadProjectId && currentProjectIdRef.current && payloadProjectId !== currentProjectIdRef.current) {
      return;
    }
    if (projectPayload?.project) {
      const mappedProject = mapBackendProject(projectPayload.project, mappedCreators, feishuConfig, options.creatorStats);
      const nextProject = options.screeningPlan
        ? { ...mappedProject, screeningPlan: options.screeningPlan }
        : mappedProject;
      setProjectList((prev) => {
        const exists = prev.some((item) => item.project_id === projectPayload.project.project_id);
        return exists ? prev.map((item) => (item.project_id === projectPayload.project.project_id ? projectPayload.project : item)) : [...prev, projectPayload.project];
      });
      setCurrentProject(nextProject);
      setProjects((prev) => {
        const exists = prev.some((item) => getProjectKey(item) === getProjectKey(nextProject));
        return exists ? prev.map((item) => (getProjectKey(item) === getProjectKey(nextProject) ? nextProject : item)) : prev;
      });
    } else if (mappedCreators.length) {
      updateCurrentProject({ creators: mappedCreators });
    }
  }, [feishuConfig, updateCurrentProject]);

  const fetchCreatorsPaged = useCallback(async (targetProjectId, pageSize = 200, onFirstPage, options = {}) => {
    const firstPayload = await safeApi(`/api/projects/${targetProjectId}/creators?page=1&page_size=${pageSize}`);
    const firstCreators = firstPayload.creators || [];
    onFirstPage?.(firstPayload);
    const total = Number(firstPayload.total || firstCreators.length);
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    if (options.firstPageOnly) {
      return { ...firstPayload, creators: firstCreators, partial: totalPages > 1 };
    }
    if (totalPages <= 1) return { ...firstPayload, creators: firstCreators };
    const restPayloads = await Promise.all(
      Array.from({ length: totalPages - 1 }, (_, index) => (
        safeApi(`/api/projects/${targetProjectId}/creators?page=${index + 2}&page_size=${pageSize}`)
      )),
    );
    return {
      ...firstPayload,
      creators: [
        ...firstCreators,
        ...restPayloads.flatMap(payload => payload.creators || []),
      ],
      total,
      has_more: false,
    };
  }, [safeApi]);

  const refreshProjectData = useCallback(async (options = {}) => {
    if (!projectId) return { ok: false, error: '未选择项目' };
    const requestedProjectId = projectId;
    const background = Boolean(options.background);
    const firstPageOnly = Boolean(options.firstPageOnly);
    const [projectPayload, statsPayload] = await Promise.all([
      safeApi(`/api/projects/${requestedProjectId}`),
      safeApi(`/api/projects/${requestedProjectId}/creators/stats`),
    ]);
    const creatorStats = statsPayload?.tiers ? statsPayload : null;
    if (currentProjectIdRef.current && currentProjectIdRef.current !== requestedProjectId) {
      return { ok: false, stale: true, project: projectPayload?.project, creators: [] };
    }
    let firstPageApplied = false;
    const creatorsPayload = await fetchCreatorsPaged(requestedProjectId, 500, (firstPayload) => {
      if (currentProjectIdRef.current && currentProjectIdRef.current !== requestedProjectId) return;
      firstPageApplied = true;
      const firstMappedCreators = (firstPayload.creators || []).map(mapBackendCreator);
      applyProjectPayload(projectPayload, firstMappedCreators, { ...options, creatorStats });
    }, { firstPageOnly });
    if (currentProjectIdRef.current && currentProjectIdRef.current !== requestedProjectId) {
      return { ok: false, stale: true, project: projectPayload?.project, creators: [] };
    }
    const mappedCreators = (creatorsPayload.creators || []).map(mapBackendCreator);
    if (!firstPageOnly && (!firstPageApplied || mappedCreators.length !== (creatorsPayload.creators || []).length || mappedCreators.length > 50)) {
      applyProjectPayload(projectPayload, mappedCreators, { ...options, creatorStats });
    }
    if (!firstPageOnly || !creatorsPayload.partial) {
      setLoadedCreatorProjectIds((prev) => ({ ...prev, [requestedProjectId]: true }));
    } else if (!background) {
      refreshProjectData({ ...options, background: true, firstPageOnly: false });
    }
    return { ok: true, project: projectPayload?.project, creators: creatorsPayload.creators || [] };
  }, [applyProjectPayload, fetchCreatorsPaged, projectId, safeApi]);

  useEffect(() => {
    if (!projectId || currentProject?.creators?.length) return;
    if (loadedCreatorProjectIds[projectId]) return;
    if (!['screening-review', 'creator-audit'].includes(activeTab)) return;
    refreshProjectData({ firstPageOnly: true });
  }, [activeTab, currentProject?.creators?.length, loadedCreatorProjectIds, projectId, refreshProjectData]);

  const handleSaveProject = async (payload = {}) => {
    updateCurrentProject(payload);
    if (!projectId) return { ok: false, error: '未选择项目' };
    const basePlan = payload.screening_plan || currentProject?.screeningPlan || {};
    const payloadWithMeta = {
      ...payload,
      screening_plan: {
        ...(basePlan || {}),
        uiProject: {
          product: payload.product || currentProject?.product || '',
          poolType: payload.poolType || currentProject?.poolType || '',
          sharedPoolId: payload.sharedPoolId || currentProject?.sharedPoolId || '',
          budget: payload.budget ?? currentProject?.budget ?? 0,
          singleBudget: payload.singleBudget ?? currentProject?.singleBudget ?? '',
          cooperationType: payload.cooperationType || currentProject?.cooperationType || '',
        },
      },
    };
    const result = await safeApi(`/api/projects/${projectId}`, {
      method: 'POST',
      body: JSON.stringify(payloadWithMeta),
    });
    if (result.project) {
      setProjectList((prev) => {
        const exists = prev.some((item) => getProjectKey(item) === result.project.project_id);
        return exists ? prev.map((item) => (getProjectKey(item) === result.project.project_id ? result.project : item)) : [...prev, result.project];
      });
      updateCurrentProject({
        project_id: result.project.project_id,
        project_name: result.project.project_name,
        target_qualified_creator_count: result.project.target_qualified_creator_count,
        period_start: result.project.period_start,
        period_end: result.project.period_end,
        brief: result.project.brief,
        screening_plan: result.project.screening_plan,
      });
    }
    return result;
  };

  const handleSaveScreeningPlan = async (screeningPlan, projectPatch = {}) => {
    const payload = {
      ...projectPatch,
      screening_plan: {
        ...(screeningPlan || {}),
        uiProject: {
          product: projectPatch.product || currentProject?.product || '',
          poolType: projectPatch.poolType || currentProject?.poolType || '',
          sharedPoolId: projectPatch.sharedPoolId || currentProject?.sharedPoolId || '',
          budget: projectPatch.budget ?? currentProject?.budget ?? 0,
          singleBudget: projectPatch.singleBudget ?? currentProject?.singleBudget ?? '',
          cooperationType: projectPatch.cooperationType || currentProject?.cooperationType || '',
        },
      },
    };
    updateCurrentProject(payload);
    return handleSaveProject(payload);
  };

  const getLatestCollectBatch = async () => {
    if (!projectId) return {};
    const payload = await safeApi(`/api/projects/${projectId}/batches?limit=1`);
    return (payload.batches || [])[0] || {};
  };

  const getRunningCollectBatch = async () => {
    if (!projectId) return {};
    const payload = await safeApi(`/api/projects/${projectId}/batches?status=running&limit=1`);
    return (payload.batches || [])[0] || {};
  };

  const handleStopCollect = async () => {
    if (!projectId) return { ok: false, error: '未选择项目' };
    return safeApi('/api/pgy/collect/stop', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId }),
    });
  };

  const handleCollect = async (plan, options = {}) => {
    const activePlan = plan && typeof plan === 'object' && !plan.nativeEvent
      ? plan
      : currentProject?.screeningPlan || {};
    if (activePlan) updateCurrentProject({ screening_plan: activePlan });
    if (!projectId) return { ok: false, error: '未选择项目' };
    const limit = Math.max(1, Math.min(5000, Number(options.limit || 5000)));
    const schemeIds = Array.isArray(options.schemeIds) ? options.schemeIds.map(String).filter(Boolean) : [];
    if (activePlan && Object.keys(activePlan).length > 0) {
      const saveResult = await safeApi(`/api/projects/${projectId}`, {
        method: 'POST',
        body: JSON.stringify({ screening_plan: activePlan }),
      });
      if (saveResult?.ok === false) {
        return {
          ...saveResult,
          message: `保存筛选条件失败：${saveResult.message || saveResult.error || '请求失败'}`,
        };
      }
    }
    const result = await safeApi('/api/pgy/collect/batch', {
      method: 'POST',
      body: JSON.stringify({
        project_id: projectId,
        screening_plan: activePlan,
        apply_filters: true,
        include_details: false,
        collect_profile_urls: true,
        export_metrics: true,
        limit,
        scheme_ids: schemeIds,
        multi_scheme: options.multiScheme !== false,
        preflight: options.preflight !== false,
        async_collect: options.asyncCollect === true,
      }),
    });
    if (result.ok && !result.accepted) {
      await refreshProjectData({ screeningPlan: activePlan });
    }
    if (!result.accepted) {
      setResultModal(buildCollectResultSummary(result));
    }
    return result;
  };

  const handleCollectDetails = async ({ creatorIds = [], segment = '', segmentLabel = '' } = {}) => {
    if (!projectId) return { ok: false, error: '未选择项目' };
    const normalizedIds = [...new Set(creatorIds.map(String).filter(Boolean))].sort();
    const requestedCount = normalizedIds.length;
    const requestKey = `${projectId}:${normalizedIds.join(',') || 'auto'}:${segment || ''}`;
    if (detailCollectInFlightRef.current.has(requestKey)) {
      return {
        ok: false,
        error: 'detail_collection_already_running',
        message: '这批达人详情正在完善中，请稍等',
      };
    }
    detailCollectInFlightRef.current.add(requestKey);
    try {
      const result = await safeApi('/api/pgy/collect/detail', {
        method: 'POST',
        body: JSON.stringify({
          project_id: projectId,
          creator_ids: normalizedIds,
          segment,
          manual: true,
          limit: normalizedIds.length || 500,
          async_collect: true,
        }),
      });
      if (result?.accepted && result?.task?.task_id) {
        const taskId = result.task.task_id;
        setDetailProgress({ ...result.task, segmentLabel });
        const finalResult = await new Promise((resolve) => {
          let stopped = false;
          const poll = async () => {
            if (stopped) return;
            const payload = await safeApi(`/api/pgy/collect/detail/tasks/${taskId}`);
            const task = payload?.task;
            if (!task) {
              stopped = true;
              resolve(result);
              return;
            }
            if (task.status === 'running') {
              setDetailProgress({ ...task, segmentLabel });
              detailProgressTimerRef.current = window.setTimeout(poll, 1200);
              return;
            }
            stopped = true;
            setDetailProgress(null);
            const finalResult = task.result || { ok: task.status !== 'failed', message: task.progress_message || result.message };
            setResultModal(buildDetailResultSummary(finalResult, requestedCount, segmentLabel));
            if (finalResult.ok !== false) {
              await refreshProjectData();
            }
            resolve(finalResult);
          };
          detailProgressTimerRef.current = window.setTimeout(poll, 800);
        });
        return { ...result, finalResult };
      }
      setResultModal(buildDetailResultSummary(result, requestedCount, segmentLabel));
      return result;
    } finally {
      detailCollectInFlightRef.current.delete(requestKey);
    }
  };

  const handleScore = async ({ source = 'manual', creatorIds = [], segment = '', segmentLabel = '' } = {}) => {
    if (!projectId) return { ok: false, error: '未选择项目' };
    const result = await safeApi(`/api/projects/${projectId}/creators/score`, {
      method: 'POST',
      body: JSON.stringify({
        source,
        creator_ids: creatorIds.map(String),
        segment,
        segment_label: segmentLabel,
      }),
    });
    if (result?.ok === false) {
      setResultModal(buildScoreResultSummary(result, []));
      return result;
    }
    const refreshed = await refreshProjectData();
    setResultModal(buildScoreResultSummary(result, refreshed.creators || []));
    return { ...result, refreshed };
  };

  const handleImport = async () => ({ ok: true, message: '当前页面使用内置模板数据，无需额外导入。' });

  const handleReview = async (creatorIds = [], reviewStatus = '待审核', reviewReason = '') => {
    if (!projectId) return { ok: false, error: '未选择项目' };
    return safeApi(`/api/projects/${projectId}/creators/review`, {
      method: 'POST',
      body: JSON.stringify({
        creator_ids: creatorIds.map(String),
        review_status: reviewStatus,
        review_reason: reviewReason,
        reviewer: '当前用户',
      }),
    });
  };

  const handlePgyInvite = async (creatorIds = [], form = {}) => {
    if (!projectId) return { ok: false, error: '未选择项目' };
    return safeApi(`/api/projects/${projectId}/creators/invite`, {
      method: 'POST',
      body: JSON.stringify({
        creator_ids: creatorIds.map(String),
        brand_name: form.brandName,
        cooperation_type: form.cooperationType,
        product_name: form.productName,
        expected_start_date: form.expectedStartDate,
        expected_end_date: form.expectedEndDate,
        content_intro: form.contentIntro,
        contact_type: form.contactType,
        contact_info: form.contactInfo,
        source: form.source || '批量邀约',
        channel: 'pgy',
        operator: '当前用户',
      }),
    });
  };

  const handleRefresh = async () => {
    return refreshProjectData();
  };

  const handleSaveFeishu = async (form = {}) => {
    const result = await safeApi('/api/projects/feishu/connection', {
      method: 'POST',
      body: JSON.stringify({ ...form, project_id: projectId }),
    });
    if (result.config) {
      setFeishuConfig(result.config);
      updateCurrentProject({
        feishuBinding: {
          ...(currentProject?.feishuBinding || {}),
          linked: Boolean(result.config.feishu_url),
          tableUrl: result.config.feishu_url || '',
          baseToken: result.config.target?.token || '',
          tableId: result.config.target?.table_id || '',
        },
      });
    }
    return result;
  };

  const handleTestFeishu = async (form = {}) => safeApi('/api/projects/feishu/test', {
    method: 'POST',
    body: JSON.stringify({ ...form, project_id: projectId }),
    allowBusinessError: true,
  });

  const handleLoadTables = async () => {
    const result = await safeApi(`/api/projects/feishu/tables?project_id=${encodeURIComponent(projectId || '')}`);
    if (result.tables) setFeishuTables(result.tables);
    return result;
  };

  const handleLoadFields = async (tableId = '') => {
    const result = await safeApi(`/api/projects/feishu/fields?project_id=${encodeURIComponent(projectId || '')}${tableId ? `&table_id=${encodeURIComponent(tableId)}` : ''}`);
    if (result.fields) setFeishuFields(result.fields);
    return result;
  };

  const handleWriteBack = async (tableId = '') => {
    if (!projectId) {
      const result = { ok: false, message: '未选择项目，无法写回飞书' };
      setResultModal(buildWritebackResultSummary(result));
      return result;
    }
    const result = await safeApi('/api/projects/feishu/writeback', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId, table_id: tableId, quality_only: true, rows: [] }),
      timeoutMs: 90000,
      timeoutMessage: '写回飞书超过 90 秒未返回，已停止等待。请检查飞书权限、字段映射或网络后重试。',
    });
    setResultModal(buildWritebackResultSummary(result));
    if (result?.ok !== false) {
      await refreshProjectData();
    }
    return result;
  };

  const handleTabChange = (nextTab) => {
    setActiveTab(nextTab);
    navigate(`/workbench/screening/${nextTab}`);
  };

  const handleArchiveProject = async (project) => {
    const targetId = getProjectKey(project);
    if (!targetId) return;
    const archivedAt = new Date().toISOString();
    await api(`/api/projects/${targetId}/archive`, { method: 'POST' });
    setProjects((prev) => prev.map((item) => (getProjectKey(item) === targetId ? { ...item, archivedAt } : item)));
    setProjectList((prev) => prev.map((item) => (getProjectKey(item) === targetId ? { ...item, archived_at: archivedAt } : item)));
  };

  const handleRestoreProject = async (project) => {
    const targetId = getProjectKey(project);
    if (!targetId) return;
    await api(`/api/projects/${targetId}/restore`, { method: 'POST' });
    setProjects((prev) => prev.map((item) => (getProjectKey(item) === targetId ? { ...item, archivedAt: '' } : item)));
    setProjectList((prev) => prev.map((item) => (getProjectKey(item) === targetId ? { ...item, archived_at: null } : item)));
  };

  const handleDeleteProject = async (project) => {
    const targetId = getProjectKey(project);
    if (!targetId) return;
    const confirmed = window.confirm(`确认删除「${project.name || project.project_name || targetId}」？删除后会移除项目及相关采集/评分记录。`);
    if (!confirmed) return;
    try {
      await api(`/api/projects/${targetId}`, { method: 'DELETE' });
    } catch (error) {
      const message = error.message || '';
      if (!message.includes('项目不存在')) {
        window.alert(`删除失败：${message || '请求失败'}`);
        return;
      }
    }
    setProjects((prev) => prev.filter((item) => getProjectKey(item) !== targetId));
    setProjectList((prev) => prev.filter((item) => getProjectKey(item) !== targetId));
    if (getProjectKey(currentProject) === targetId) {
      setCurrentProject(null);
      navigate('/workbench/screening/projects');
    }
  };

  const renderTabContent = () => {
    if (activeTab === 'projects') {
      return (
        <ProjectsPreview
          projects={mergedProjects}
          onSelectProject={selectProject}
          onCreateProject={() => setShowCreateModal(true)}
          onArchiveProject={handleArchiveProject}
          onRestoreProject={handleRestoreProject}
          onDeleteProject={handleDeleteProject}
        />
      );
    }

    if (!currentProject && activeTab !== 'project-setup') {
      return (
        <div className="card" style={{ textAlign: 'center', padding: 48 }}>
          <FolderOpen size={48} style={{ color: '#5A6478', marginBottom: 16 }} />
          <h4 style={{ color: '#E8ECF1', marginBottom: 8 }}>请先选择项目</h4>
          <p style={{ color: '#8B95A5', marginBottom: 16 }}>进入「项目预览」选择一个项目开始工作</p>
          <button className="btn btn-primary" onClick={() => handleTabChange('projects')}>前往项目预览</button>
        </div>
      );
    }

    switch (activeTab) {
      case 'overview':
        return (
          <OverviewTab
            project={currentProject}
            onCollect={handleCollect}
            onStopCollect={handleStopCollect}
            onLatestBatch={getLatestCollectBatch}
            onRunningBatch={getRunningCollectBatch}
            onRefresh={handleRefresh}
            onSavePlan={handleSaveScreeningPlan}
            onTabChange={handleTabChange}
          />
        );
      case 'screening-review':
        return (
          <ScreeningReviewTab
            project={currentProject}
            screeningStatus={screeningStatus}
            setScreeningStatus={setScreeningStatus}
            onReview={handleReview}
            onRefresh={handleRefresh}
            onScore={handleScore}
            onImport={handleImport}
            onCollect={handleCollect}
            onCollectDetails={handleCollectDetails}
            onPgyInvite={handlePgyInvite}
            onSavePlan={handleSaveScreeningPlan}
            onTabChange={handleTabChange}
          />
        );
      case 'creator-audit':
        return (
          <CreatorAuditTab
            project={currentProject}
            screeningStatus={screeningStatus}
            setScreeningStatus={setScreeningStatus}
            onCollectDetails={handleCollectDetails}
            onPgyInvite={handlePgyInvite}
            onReview={handleReview}
            onRefresh={handleRefresh}
            onTabChange={handleTabChange}
          />
        );
      case 'score-preview':
        return <ScorePreviewTab project={currentProject} screeningStatus={screeningStatus} onCollectDetails={handleCollectDetails} onPgyInvite={handlePgyInvite} />;
      case 'project-setup':
        return currentProject ? (
          <ProjectSetupTab
            project={currentProject}
            projects={mergedProjects}
            onSelectProject={(project) => selectProject(project, { navigateToOverview: false })}
            onCreateProject={() => setShowCreateModal(true)}
            feishuConfig={feishuConfig}
            feishuFields={feishuFields}
            feishuTables={feishuTables}
            onSaveProject={handleSaveProject}
            onSaveScreeningPlan={handleSaveScreeningPlan}
            onSaveFeishu={handleSaveFeishu}
            onTestFeishu={handleTestFeishu}
            onLoadTables={handleLoadTables}
            onLoadFields={handleLoadFields}
            onWriteBack={handleWriteBack}
          />
        ) : (
          <div className="card" style={{ textAlign: 'center', padding: 48 }}>
            <FolderPlus size={44} style={{ color: 'var(--text-muted)', marginBottom: 16 }} />
            <h4 style={{ margin: '0 0 8px', color: 'var(--text-primary)' }}>项目配置</h4>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 16 }}>选择已有项目或新建项目后，按立项、飞书绑定、Brief 解析顺序完成配置。</p>
            <div style={{ display: 'inline-flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'center' }}>
              {mergedProjects.length > 0 && (
                <select
                  className="select-field"
                  defaultValue=""
                  style={{ minWidth: 260 }}
                  onChange={(event) => {
                    const next = mergedProjects.find(item => getProjectKey(item) === event.target.value);
                    if (next) setCurrentProject(next);
                  }}
                >
                  <option value="">选择已有项目</option>
                  {mergedProjects.map(item => {
                    const id = getProjectKey(item);
                    return <option key={id} value={id}>{item.name || item.project_name || id}</option>;
                  })}
                </select>
              )}
              <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
                <FolderPlus size={14} />新建项目
              </button>
            </div>
          </div>
        );
      case 'audit-log':
        return <AuditLogTab project={currentProject} />;
      case 'legacy':
        return <AdvancedConfigTab />;
      default:
        return (
          <OverviewTab
            project={currentProject}
            onCollect={handleCollect}
            onStopCollect={handleStopCollect}
            onLatestBatch={getLatestCollectBatch}
            onRunningBatch={getRunningCollectBatch}
            onRefresh={handleRefresh}
            onSavePlan={handleSaveScreeningPlan}
            onTabChange={handleTabChange}
          />
        );
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <DetailProgressBanner task={detailProgress} onDismiss={() => setDetailProgress(null)} />

      <div>
        {renderTabContent()}
      </div>

      <ResultSummaryModal summary={resultModal} onClose={() => setResultModal(null)} />

      <CreateProjectModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreate={createProject}
      />
    </div>
  );
}
