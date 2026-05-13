import {
  initialProjects,
  initialScreeningStatus,
  sharedPoolEducationMom,
  sharedPoolBabyCare,
  isolatedPoolLuxury,
} from '../constants/projectConstants';

export function normalizeProjectBrief(item, base) {
  const savedBrief = typeof item.brief === 'string' ? item.brief.trim() : '';
  const baseBrief = base.brief && typeof base.brief === 'object' ? base.brief : {};
  return {
    ...baseBrief,
    projectId: item.project_id,
    projectName: item.project_name,
    template: baseBrief.template || '自定义',
    description: savedBrief || baseBrief.description || base.description || '',
  };
}

export function mapBackendProject(item, creators = [], feishuConfig = null) {
  const base = initialProjects[0];
  const linked = Boolean(feishuConfig?.feishu_url);
  const normalizedBrief = normalizeProjectBrief(item, base);
  return {
    ...base,
    id: item.project_id,
    name: item.project_name,
    product: '有道答疑笔Pro',
    creatorCount: item.target_qualified_creator_count || 10,
    periodStart: item.period_start || base.periodStart,
    periodEnd: item.period_end || base.periodEnd,
    period: `${item.period_start || '2026-05-07'} 至 ${item.period_end || '2026-05-19'}`,
    createdAt: item.created_at || '',
    updatedAt: item.updated_at || '',
    archivedAt: item.archived_at || '',
    status: item.archived_at ? '已归档' : base.status,
    description: normalizedBrief.description || base.description,
    brief: normalizedBrief,
    currentStep: linked ? 6 : 4,
    creators,
    feishuBinding: {
      linked,
      tableUrl: feishuConfig?.feishu_url || '',
      tableName: linked ? '有道答疑笔达人池' : '',
      baseToken: feishuConfig?.target?.token || '',
      tableId: feishuConfig?.target?.table_id || '',
      viewId: '',
      fieldMapping: base.feishuBinding.fieldMapping,
    },
    stats: {
      total: item.creator_pool_count || creators.length,
      passed: item.qualified_creator_count || 0,
      ratio: item.qualified_ratio || 0,
    },
    screeningPlan: parseStoredScreeningPlan(item.screening_plan, base.screeningPlan),
  };
}

export function parseStoredScreeningPlan(value, fallback = {}) {
  if (!value) return fallback || {};
  if (typeof value === 'object') return value;
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === 'object' && Object.keys(parsed).length ? parsed : fallback || {};
  } catch {
    return fallback || {};
  }
}

export function getProjectCreators(project) {
  if (!project) return [];
  if (project.creators) return project.creators;
  if (project.poolType === 'isolated') {
    if (project.id === 'luxury_skincare') return isolatedPoolLuxury;
    return project.creators || [];
  } else {
    if (project.sharedPoolId === 'education_mom') return sharedPoolEducationMom;
    if (project.sharedPoolId === 'baby_care') return sharedPoolBabyCare;
    return [];
  }
}

export function getCreatorStatus(projectId, creatorId, statusMap) {
  const map = statusMap || initialScreeningStatus;
  return map[projectId]?.[creatorId] || null;
}

export function getDefaultCreatorStatus() {
  return {
    review: '待审核', reviewVariant: 'default', finalScore: null, reason: '', reviewer: null, reviewedAt: null, risk: [],
  };
}

export function getProjectStats(project, statusMap) {
  const creators = getProjectCreators(project);
  if (project.stats) {
    const backup = creators.filter(c => c.review === '备选').length;
    const rejected = creators.filter(c => c.review === '已驳回').length;
    const review = creators.filter(c => c.review === '待审核').length;
    const pending = creators.filter(c => c.review === '待补数据').length;
    return { total: project.stats.total, passed: project.stats.passed, rejected, backup, review, pending };
  }
  const sm = (statusMap || initialScreeningStatus)[project.id] || {};
  const passed = Object.values(sm).filter(s => s.review === '已通过').length;
  const rejected = Object.values(sm).filter(s => s.review === '已驳回' || s.review === '默认淘汰').length;
  const backup = Object.values(sm).filter(s => s.review === '备选').length;
  const review = Object.values(sm).filter(s => s.review === '人工复核').length;
  const pending = creators.length - passed - rejected - backup - review;
  return { total: creators.length, passed, rejected, backup, review, pending };
}

export function briefTextFromProject(project) {
  const brief = project?.brief;
  const briefDescription = typeof brief === 'string'
    ? brief
    : [brief?.description, brief?.goal, brief?.requirement].filter(Boolean).join(' ');
  return [project?.description, briefDescription].filter(Boolean).join(' ');
}

export function extractFirstNumber(text, patterns = []) {
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) {
      return Number(match[1]);
    }
  }
  return null;
}

export function parseBriefTaskTargets(project) {
  const text = briefTextFromProject(project);
  const targetCreators = extractFirstNumber(text, [
    /(?:目标|需要|合作|筛选|招募)[^\d]{0,12}(\d+)\s*(?:位|个|名)?\s*达人/i,
    /(\d+)\s*(?:位|个|名)\s*(?:合格|合作|目标)?达人/i,
  ]);
  const roiMatch = text.match(/(?:ROI|roi|投产比|投入产出比)[^\d]*(\d+(?:\.\d+)?)(?:\s*[:：]\s*(\d+(?:\.\d+)?))?/);
  const cpe = extractFirstNumber(text, [
    /(?:CPE|cpe)[^\d]*(\d+(?:\.\d+)?)/,
    /互动成本[^\d]*(\d+(?:\.\d+)?)/,
  ]);
  const exposure = extractFirstNumber(text, [
    /(?:曝光|播放|阅读)[^\d]*(\d+(?:\.\d+)?)(?:\s*万)?/,
  ]);

  return {
    targetCreators: targetCreators || project.creatorCount || project.stats?.target || project.stats?.total || 0,
    targetRoi: roiMatch ? Number(roiMatch[2] || roiMatch[1]) : null,
    targetCpe: cpe,
    targetExposure: exposure,
    hasExplicitMetric: Boolean(roiMatch || cpe || exposure),
  };
}

export function getProjectTaskSummary(project, statusMap) {
  const creators = getProjectCreators(project);
  const stats = getProjectStats(project, statusMap);
  const targets = parseBriefTaskTargets(project);
  const statusById = (statusMap || initialScreeningStatus)[project.id] || {};
  const collaboratorStatuses = new Set(['已合作', '合作中', '已通过', '已写回飞书']);
  const rejectedStatuses = new Set(['已驳回', '默认淘汰', '不合作']);
  const creatorReview = (creator) => statusById[creator.id]?.review || creator.review || creator.raw?.status || '';

  const collaboratedFromCreators = creators.filter(creator => collaboratorStatuses.has(creatorReview(creator))).length;
  const rejectedFromCreators = creators.filter(creator => rejectedStatuses.has(creatorReview(creator))).length;
  const collaborated = project.stats?.passed ?? collaboratedFromCreators;
  const total = project.stats?.total ?? creators.length;
  const rejected = project.stats ? stats.rejected : rejectedFromCreators;
  const pendingScreening = Math.max(total - collaborated - rejected, 0);
  const targetCreators = Math.max(targets.targetCreators || collaborated || 1, 1);

  const actualRoi = Number(project.metrics?.roi || project.stats?.roi || project.roi || 0) || null;
  const collaboratorProgress = Math.min(collaborated / targetCreators, 1);
  const roiProgress = actualRoi && targets.targetRoi ? Math.min(actualRoi / targets.targetRoi, 1) : null;
  const progressRatio = roiProgress === null
    ? collaboratorProgress
    : collaboratorProgress * 0.7 + roiProgress * 0.3;

  const briefMetric = targets.targetRoi
    ? `ROI ${targets.targetRoi}x`
    : targets.targetCpe
      ? `CPE <= ${targets.targetCpe}`
      : targets.targetExposure
        ? `曝光 ${targets.targetExposure}万`
        : 'Brief未写明';

  return {
    total,
    pendingScreening,
    collaborated,
    targetCreators,
    progress: Math.round(progressRatio * 100),
    progressText: `${collaborated}/${targetCreators} · ${Math.round(progressRatio * 100)}%`,
    progressDetail: actualRoi && targets.targetRoi
      ? `合作达人 + ROI ${actualRoi}x/${targets.targetRoi}x`
      : `按已合作达人推进，指标：${briefMetric}`,
    briefMetric,
  };
}
