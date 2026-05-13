import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  LayoutDashboard, Users, BarChart3, FolderPlus, ScrollText, FolderOpen, ExternalLink,
} from 'lucide-react';
import TabBar from '../../components/TabBar';
import PageHeader from '../../components/PageHeader';
import { api } from './api/screeningApi';
import { initialProjects, initialScreeningStatus } from './constants/projectConstants';
import { mapBackendProject } from './utils/projectMappers';
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
  { key: 'project-setup', label: '立项 + 标准 + 飞书绑定', icon: <FolderPlus size={14} /> },
  { key: 'audit-log', label: '操作日志', icon: <ScrollText size={14} /> },
  { key: 'legacy', label: '高级配置', icon: <ExternalLink size={14} /> },
];

function getProjectKey(project = {}) {
  return project.id || project.project_id;
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
    setShowCreateModal(false);
  };

  const projectId = currentProject?.id || currentProject?.project_id;

  const updateCurrentProject = (patch) => {
    if (!currentProject) return;
    const normalizedPatch = {
      ...patch,
      ...(patch.project_name ? { name: patch.project_name, project_name: patch.project_name } : {}),
      ...(patch.target_qualified_creator_count ? { creatorCount: patch.target_qualified_creator_count } : {}),
      ...(patch.period_start ? { periodStart: patch.period_start } : {}),
      ...(patch.period_end ? { periodEnd: patch.period_end } : {}),
      ...(patch.brief ? { description: patch.brief, brief: { ...(currentProject.brief || {}), description: patch.brief } } : {}),
      ...(patch.screening_plan ? { screeningPlan: patch.screening_plan } : {}),
    };
    setProjects((prev) => prev.map((item) => (item.id === currentProject.id ? { ...item, ...normalizedPatch } : item)));
    setCurrentProject((prev) => (prev ? { ...prev, ...normalizedPatch } : prev));
  };

  const safeApi = async (url, options = {}) => {
    try {
      return await api(url, options);
    } catch (error) {
      console.warn('[ScreeningDashboard]', error.message || error);
      return { ok: false, error: error.message || '请求失败' };
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
      updateCurrentProject({
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

  const handleCollect = async (plan) => {
    if (plan) updateCurrentProject({ screening_plan: plan });
    return safeApi('/api/pgy/collect/list', { method: 'POST' });
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
    const payload = projectId ? await safeApi(`/api/projects/${projectId}`) : null;
    if (payload?.project) {
      setProjectList((prev) => {
        const exists = prev.some((item) => item.project_id === payload.project.project_id);
        return exists ? prev.map((item) => (item.project_id === payload.project.project_id ? payload.project : item)) : [...prev, payload.project];
      });
    }
    return payload;
  };

  const handleSaveFeishu = async (form = {}) => safeApi('/api/projects/feishu/connection', {
    method: 'POST',
    body: JSON.stringify({ ...form, project_id: projectId }),
  });

  const handleTestFeishu = async (form = {}) => safeApi('/api/projects/feishu/test', {
    method: 'POST',
    body: JSON.stringify({ ...form, project_id: projectId }),
    allowBusinessError: true,
  });

  const handleLoadTables = async () => safeApi(`/api/projects/feishu/tables?project_id=${projectId || ''}`);

  const handleLoadFields = async (tableId = '') => safeApi(`/api/projects/feishu/fields?project_id=${projectId || ''}${tableId ? `&table_id=${encodeURIComponent(tableId)}` : ''}`);

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

    if (!currentProject) {
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
        return <OverviewTab project={currentProject} onCollect={handleCollect} onSavePlan={handleSaveScreeningPlan} onTabChange={handleTabChange} />;
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
        return (
          <ProjectSetupTab
            project={currentProject}
            onSaveProject={handleSaveProject}
            onSaveScreeningPlan={handleSaveScreeningPlan}
            onSaveFeishu={handleSaveFeishu}
            onTestFeishu={handleTestFeishu}
            onLoadTables={handleLoadTables}
            onLoadFields={handleLoadFields}
            onWriteBack={handleWriteBack}
          />
        );
      case 'audit-log':
        return <AuditLogTab project={currentProject} />;
      case 'legacy':
        return <AdvancedConfigTab />;
      default:
        return <OverviewTab project={currentProject} onCollect={handleCollect} onSavePlan={handleSaveScreeningPlan} onTabChange={handleTabChange} />;
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
