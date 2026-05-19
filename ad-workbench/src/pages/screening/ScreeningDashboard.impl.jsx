import React, { useCallback, useEffect, useMemo, useState } from 'react';
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
  return project.id || project.project_id;
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

function ResultSummaryModal({ summary, onClose }) {
  if (!summary) return null;
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal result-summary-modal" onClick={event => event.stopPropagation()}>
        <div className="modal-header result-summary-header">
          <div>
            <span className={`result-summary-pill is-${summary.type || 'success'}`}>{summary.type === 'error' ? '需要关注' : '已完成'}</span>
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

export default function ScreeningDashboard() {
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
    if (!currentProject && mergedProjects.length > 0) {
      setCurrentProject(mergedProjects[0]);
    }
  }, [currentProject, mergedProjects]);

  const selectProject = (project) => {
    setCurrentProject(project);
    setActiveTab('overview');
    navigate('/workbench/screening/overview');
  };

  const createProject = (newProject) => {
    setProjects((prev) => [...prev, newProject]);
    setCurrentProject(newProject);
    setActiveTab('project-setup');
    setShowCreateModal(false);
    navigate('/workbench/screening/project-setup');
  };

  const projectId = currentProject?.id || currentProject?.project_id;

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

  const refreshProjectData = useCallback(async (options = {}) => {
    if (!projectId) return { ok: false, error: '未选择项目' };
    const [projectPayload, creatorsPayload] = await Promise.all([
      safeApi(`/api/projects/${projectId}`),
      safeApi(`/api/projects/${projectId}/creators`),
    ]);
    const mappedCreators = (creatorsPayload.creators || []).map(mapBackendCreator);
    if (projectPayload?.project) {
      const mappedProject = mapBackendProject(projectPayload.project, mappedCreators, feishuConfig);
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
    setLoadedCreatorProjectIds((prev) => ({ ...prev, [projectId]: true }));
    return { ok: true, project: projectPayload?.project, creators: creatorsPayload.creators || [] };
  }, [feishuConfig, projectId, safeApi, updateCurrentProject]);

  useEffect(() => {
    if (!projectId || currentProject?.creators?.length) return;
    if (loadedCreatorProjectIds[projectId]) return;
    if (!['overview', 'screening-review', 'creator-audit', 'score-preview'].includes(activeTab)) return;
    refreshProjectData();
  }, [activeTab, currentProject?.creators?.length, loadedCreatorProjectIds, projectId, refreshProjectData]);

  const handleSaveProject = async (payload = {}) => {
    updateCurrentProject(payload);
    if (!projectId) return { ok: false, error: '未选择项目' };
    const result = await safeApi(`/api/projects/${projectId}`, {
      method: 'POST',
      body: JSON.stringify(payload),
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
    const payload = { ...projectPatch, screening_plan: screeningPlan };
    updateCurrentProject(payload);
    return handleSaveProject(payload);
  };

  const getLatestCollectBatch = async () => {
    if (!projectId) return {};
    const payload = await safeApi(`/api/projects/${projectId}/batches`);
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
      }),
    });
    if (result.ok) {
      await refreshProjectData({ screeningPlan: activePlan });
    }
    setResultModal(buildCollectResultSummary(result));
    return result;
  };

  const handleCollectDetails = async ({ creatorIds = [], segment = '', segmentLabel = '' } = {}) => {
    if (!projectId) return { ok: false, error: '未选择项目' };
    const result = await safeApi('/api/pgy/collect/detail', {
      method: 'POST',
      body: JSON.stringify({
        project_id: projectId,
        creator_ids: creatorIds.map(String),
        segment,
        manual: true,
      }),
    });
    setResultModal(buildDetailResultSummary(result, creatorIds.length, segmentLabel));
    return result;
  };

  const handleScore = async () => {
    if (!projectId) return { ok: false, error: '未选择项目' };
    const result = await safeApi(`/api/projects/${projectId}/creators/score`, { method: 'POST' });
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

  const handleWriteBack = async (tableId = '') => safeApi('/api/projects/feishu/writeback', {
    method: 'POST',
    body: JSON.stringify({ project_id: projectId, table_id: tableId, quality_only: true, rows: [] }),
  });

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
        return <OverviewTab project={currentProject} onCollect={handleCollect} onStopCollect={handleStopCollect} onLatestBatch={getLatestCollectBatch} onSavePlan={handleSaveScreeningPlan} onTabChange={handleTabChange} />;
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
            onSelectProject={setCurrentProject}
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
        return <OverviewTab project={currentProject} onCollect={handleCollect} onStopCollect={handleStopCollect} onLatestBatch={getLatestCollectBatch} onSavePlan={handleSaveScreeningPlan} onTabChange={handleTabChange} />;
    }
  };

  return (
    <div style={{ padding: 24 }}>
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
