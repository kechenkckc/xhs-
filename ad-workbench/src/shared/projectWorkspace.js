import { useCallback, useEffect, useMemo, useState } from 'react';

const STORAGE_KEY = 'adflow-selected-project';

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload?.detail?.message || payload?.message || '请求失败';
    throw new Error(message);
  }
  return payload;
}

export function getProjectDisplayName(project) {
  return project?.project_name || project?.name || project?.project_id || '未选择项目';
}

export function getProjectBrand(project) {
  const brief = project?.brief || '';
  if (brief.includes('有道')) return '有道';
  return project?.brand || '未标注品牌';
}

export function formatProjectPeriod(project) {
  return `${project?.period_start || '待定'} 至 ${project?.period_end || '待定'}`;
}

export function healthLabel(score) {
  if (score >= 80) return '健康';
  if (score >= 60) return '关注';
  return '预警';
}

export function healthColor(score) {
  if (score >= 80) return 'green';
  if (score >= 60) return 'amber';
  return 'red';
}

export const projectWorkspaceApi = {
  async listProjects() {
    const payload = await requestJson('/api/projects?include_archived=true');
    return payload.projects || [];
  },
  async getProject(projectId) {
    const payload = await requestJson(`/api/projects/${projectId}`);
    return payload.project;
  },
  async saveProject(projectId, payload) {
    const result = await requestJson(`/api/projects/${projectId}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return result.project;
  },
  async listLogs(projectId) {
    const payload = await requestJson(`/api/projects/${projectId}/logs`);
    return payload.logs || [];
  },
  async listHandoffs(projectId, params = {}) {
    const query = new URLSearchParams(params);
    const suffix = query.toString() ? `?${query}` : '';
    const payload = await requestJson(`/api/projects/${projectId}/handoffs${suffix}`);
    return payload.handoffs || [];
  },
  async createHandoff(projectId, payload) {
    const result = await requestJson(`/api/projects/${projectId}/handoffs`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return result.handoff;
  },
  async acceptHandoff(projectId, handoffId, operator = '用户') {
    const result = await requestJson(`/api/projects/${projectId}/handoffs/${handoffId}/accept`, {
      method: 'POST',
      body: JSON.stringify({ operator }),
    });
    return result.handoff;
  },
  async returnHandoff(projectId, handoffId, returnReason, operator = '用户') {
    const result = await requestJson(`/api/projects/${projectId}/handoffs/${handoffId}/return`, {
      method: 'POST',
      body: JSON.stringify({ operator, return_reason: returnReason }),
    });
    return result.handoff;
  },
  async listTasks(projectId, params = {}) {
    const query = new URLSearchParams(params);
    const suffix = query.toString() ? `?${query}` : '';
    const payload = await requestJson(`/api/projects/${projectId}/tasks${suffix}`);
    return payload.tasks || [];
  },
  async createTask(projectId, payload) {
    const result = await requestJson(`/api/projects/${projectId}/tasks`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return result.task;
  },
  async updateTask(projectId, taskId, payload) {
    const result = await requestJson(`/api/projects/${projectId}/tasks/${taskId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
    return result.task;
  },
  async createTasksFromHandoff(projectId, handoffId, operator = '用户') {
    const result = await requestJson(`/api/projects/${projectId}/tasks/from-handoff/${handoffId}`, {
      method: 'POST',
      body: JSON.stringify({ operator }),
    });
    return result.tasks || [];
  },
  async listAssets(projectId, assetType) {
    const suffix = assetType ? `?asset_type=${encodeURIComponent(assetType)}` : '';
    const payload = await requestJson(`/api/projects/${projectId}/assets${suffix}`);
    return payload.assets || [];
  },
  async createAsset(projectId, payload) {
    const result = await requestJson(`/api/projects/${projectId}/assets`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return result.asset;
  },
  async getMetrics(projectId) {
    return requestJson(`/api/projects/${projectId}/metrics`);
  },
  async getManagementOverview() {
    return requestJson('/api/management/overview');
  },
  async aiBrief(projectId, payload) {
    return requestJson(`/api/projects/${projectId}/ai/brief`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  async aiStrategy(projectId, payload) {
    return requestJson(`/api/projects/${projectId}/ai/strategy`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  async aiHandoff(projectId, payload) {
    return requestJson(`/api/projects/${projectId}/ai/handoff`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  async aiTasks(projectId, payload) {
    return requestJson(`/api/projects/${projectId}/ai/tasks`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  async aiManagementAdvice(projectId, payload) {
    return requestJson(`/api/projects/${projectId}/ai/management-advice`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
};

export function useProjectWorkspace(selectedProjectId, onSelectedProjectIdChange) {
  const [projects, setProjects] = useState([]);
  const [currentProject, setCurrentProject] = useState(null);
  const [logs, setLogs] = useState([]);
  const [handoffs, setHandoffs] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [assets, setAssets] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [localProjectId, setLocalProjectId] = useState(() => {
    try {
      return window.localStorage.getItem(STORAGE_KEY) || selectedProjectId || '';
    } catch {
      return selectedProjectId || '';
    }
  });

  const projectId = selectedProjectId || localProjectId || projects[0]?.project_id || '';

  const selectProject = useCallback((nextProjectId) => {
    setLocalProjectId(nextProjectId);
    onSelectedProjectIdChange?.(nextProjectId);
    try {
      window.localStorage.setItem(STORAGE_KEY, nextProjectId);
    } catch {
      // Persistence is optional.
    }
  }, [onSelectedProjectIdChange]);

  const reloadProjects = useCallback(async () => {
    const nextProjects = await projectWorkspaceApi.listProjects();
    setProjects(nextProjects);
    if (!projectId && nextProjects[0]?.project_id) {
      selectProject(nextProjects[0].project_id);
    }
    return nextProjects;
  }, [projectId, selectProject]);

  const reloadCurrentProject = useCallback(async (nextProjectId = projectId) => {
    if (!nextProjectId) return;
    setLoading(true);
    setError('');
    try {
      const [project, nextLogs, nextHandoffs, nextTasks, nextAssets, nextMetrics] = await Promise.all([
        projectWorkspaceApi.getProject(nextProjectId),
        projectWorkspaceApi.listLogs(nextProjectId),
        projectWorkspaceApi.listHandoffs(nextProjectId),
        projectWorkspaceApi.listTasks(nextProjectId),
        projectWorkspaceApi.listAssets(nextProjectId),
        projectWorkspaceApi.getMetrics(nextProjectId),
      ]);
      setCurrentProject(project);
      setLogs(nextLogs);
      setHandoffs(nextHandoffs);
      setTasks(nextTasks);
      setAssets(nextAssets);
      setMetrics(nextMetrics);
    } catch (nextError) {
      setError(nextError.message || '项目数据加载失败');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    reloadProjects().catch((nextError) => {
      setError(nextError.message || '项目列表加载失败');
      setLoading(false);
    });
  }, [reloadProjects]);

  useEffect(() => {
    if (!projectId) return;
    reloadCurrentProject(projectId);
  }, [projectId, reloadCurrentProject]);

  const value = useMemo(() => ({
    projectId,
    projects,
    currentProject,
    logs,
    handoffs,
    tasks,
    assets,
    metrics,
    loading,
    error,
    selectProject,
    reloadProjects,
    reloadCurrentProject,
  }), [projectId, projects, currentProject, logs, handoffs, tasks, assets, metrics, loading, error, selectProject, reloadProjects, reloadCurrentProject]);

  return value;
}
