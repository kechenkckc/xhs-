import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  LayoutDashboard, Users, BarChart3, FolderPlus, ScrollText, FolderOpen, ExternalLink,
} from 'lucide-react';
import TabBar from '../../components/TabBar';
import PageHeader from '../../components/PageHeader';
import { api } from './api/screeningApi';
import { initialProjects, initialScreeningStatus } from './constants/projectConstants';
import { mapBackendProject, parseStoredScreeningPlan } from './utils/projectMappers';
import { mapBackendCreator } from './utils/creatorMappers';
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

  const updateCurrentProject = (patch) => {
    if (!currentProject) return;
    const currentId = getProjectKey(currentProject);
    const normalizedPatch = patchProject(currentProject, patch);
    setProjects((prev) => prev.map((item) => (getProjectKey(item) === currentId ? patchProject(item, patch) : item)));
    setProjectList((prev) => prev.map((item) => (getProjectKey(item) === currentId ? { ...item, ...patch } : item)));
    setCurrentProject((prev) => (prev ? patchProject(prev, patch) : prev));
  };

  const refreshProjectData = async () => {
    if (!projectId) return { ok: false, error: '未选择项目' };
    const [projectPayload, creatorsPayload] = await Promise.all([
      safeApi(`/api/projects/${projectId}`),
      safeApi(`/api/projects/${projectId}/creators`),
    ]);
    const mappedCreators = (creatorsPayload.creators || []).map(mapBackendCreator);
    if (projectPayload?.project) {
      const mappedProject = mapBackendProject(projectPayload.project, mappedCreators, feishuConfig);
      setProjectList((prev) => {
        const exists = prev.some((item) => item.project_id === projectPayload.project.project_id);
        return exists ? prev.map((item) => (item.project_id === projectPayload.project.project_id ? projectPayload.project : item)) : [...prev, projectPayload.project];
      });
      setCurrentProject(mappedProject);
      setProjects((prev) => {
        const exists = prev.some((item) => getProjectKey(item) === getProjectKey(mappedProject));
        return exists ? prev.map((item) => (getProjectKey(item) === getProjectKey(mappedProject) ? mappedProject : item)) : prev;
      });
    } else if (mappedCreators.length) {
      updateCurrentProject({ creators: mappedCreators });
    }
    return { ok: true, project: projectPayload?.project, creators: creatorsPayload.creators || [] };
  };

  const safeApi = async (url, options = {}) => {
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
  };

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

  const handleCollect = async (plan, options = {}) => {
    if (plan) updateCurrentProject({ screening_plan: plan });
    if (!projectId) return { ok: false, error: '未选择项目' };
    const limit = Math.max(1, Math.min(1000, Number(options.limit || 1000)));
    const result = await safeApi('/api/pgy/collect/batch', {
      method: 'POST',
      body: JSON.stringify({
        project_id: projectId,
        screening_plan: plan || currentProject?.screeningPlan || {},
        apply_filters: true,
        include_details: false,
        collect_profile_urls: true,
        export_metrics: true,
        limit,
      }),
    });
    if (result.ok) {
      await refreshProjectData();
    }
    return result;
  };

  const handleCollectDetails = async ({ creatorIds = [], segment = '', segmentLabel = '' } = {}) => {
    if (!projectId) return { ok: false, error: '未选择项目' };
    return safeApi('/api/pgy/collect/detail', {
      method: 'POST',
      body: JSON.stringify({
        project_id: projectId,
        creator_ids: creatorIds.map(String),
        segment,
        manual: true,
      }),
    });
  };

  const handleScore = async () => {
    if (!projectId) return { ok: false, error: '未选择项目' };
    return safeApi(`/api/projects/${projectId}/creators/score`, { method: 'POST' });
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
        return <OverviewTab project={currentProject} onCollect={handleCollect} onLatestBatch={getLatestCollectBatch} onSavePlan={handleSaveScreeningPlan} onTabChange={handleTabChange} />;
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
        return <OverviewTab project={currentProject} onCollect={handleCollect} onLatestBatch={getLatestCollectBatch} onSavePlan={handleSaveScreeningPlan} onTabChange={handleTabChange} />;
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <div>
        {renderTabContent()}
      </div>

      <CreateProjectModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreate={createProject}
      />
    </div>
  );
}
