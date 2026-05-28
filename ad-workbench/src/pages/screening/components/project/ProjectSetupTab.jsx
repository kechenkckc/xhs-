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
import Badge from '../../../../components/Badge';
import ProgressBar from '../../../../components/ProgressBar';
import { api } from '../../api/screeningApi';
import {
  DEFAULT_SCORING_HARD_FILTER_FIELDS,
  hardFilterKey,
  pgyFilterLabel,
} from '../../constants/screeningConstants';
import {
  mergeOptionItems,
  pgyFilterKey,
} from '../../utils/pgyFilters';
import { getSchemeAdditionalFilters, getSchemeRequiredFilters, hardFilterOptionsFor, normalizeWorkbenchPlan, syncScreeningCriteria } from '../../utils/screeningPlan';
import { PgyFindBloggerFilterPanel } from '../filters/PgyFindBloggerFilterPanel';
import { HardFilterCheckPanel } from '../filters/HardFilterCheckPanel';

const URL_PATTERN = /https?:\/\/[^\s"'<>）)]+/g;
const FEISHU_PERMISSION_HOSTS = new Set(['open.feishu.cn', 'open.larksuite.com']);
const REQUIRED_SCHEME_FIELDS = new Set(['博主类目', '粉丝量', '粉丝年龄', '合作报价']);
const SCHEME_LABELS = ['方案一', '方案二', '方案三', '方案四', '方案五', '方案六'];

const schemeKey = (scheme = {}, index = 0) => String(scheme.scheme_id || scheme.id || scheme.name || `scheme_${index + 1}`);
const schemeDisplayName = (scheme = {}, index = 0) => SCHEME_LABELS[index] || `方案${index + 1}`;

function enabledSchemeIdsFor(pgyPlan = {}) {
  const schemes = Array.isArray(pgyPlan.schemes) ? pgyPlan.schemes : [];
  const allIds = schemes.map((scheme, index) => schemeKey(scheme, index));
  const savedIds = Array.isArray(pgyPlan.enabled_scheme_ids) ? pgyPlan.enabled_scheme_ids.map(String).filter(Boolean) : [];
  return savedIds.length ? savedIds.filter(id => allIds.includes(id)) : allIds;
}

function uniqueItems(items = []) {
  return Array.from(new Set(items.filter(Boolean)));
}

function collectNested(value, predicate) {
  const result = [];
  const walk = (item) => {
    if (!item) return;
    if (predicate(item)) result.push(item);
    if (typeof item === 'string') return;
    if (Array.isArray(item)) {
      item.forEach(walk);
      return;
    }
    if (typeof item === 'object') Object.values(item).forEach(walk);
  };
  walk(value);
  return result;
}

function collectUrls(value) {
  const urls = [];
  const walk = (item, key = '') => {
    if (!item) return;
    if (typeof item === 'string') {
      if (['console_url', 'permission_url', 'auth_url', 'open_url'].includes(key) || item.includes('open.feishu.cn')) {
        urls.push(item);
      }
      urls.push(...(item.match(URL_PATTERN) || []));
      return;
    }
    if (Array.isArray(item)) {
      item.forEach(walk);
      return;
    }
    if (typeof item === 'object') Object.entries(item).forEach(([nextKey, nextValue]) => walk(nextValue, nextKey));
  };
  walk(value);
  return uniqueItems(urls).filter((url) => {
    try {
      return FEISHU_PERMISSION_HOSTS.has(new URL(url).hostname);
    } catch {
      return false;
    }
  });
}

function normalizeFeishuTestResult(result) {
  if (!result) return null;
  const detail = result.detail && typeof result.detail === 'object' ? result.detail : result;
  const error = detail.error && typeof detail.error === 'object' ? detail.error : {};
  const failedStep = detail.failed_step || error.failed_step || '';
  const failedStepMessage = (detail.steps || []).find(step => step.key === failedStep)?.message;
  const permissionViolations = [
    ...(detail.permission_violations || []),
    ...(error.permission_violations || []),
    ...collectNested(detail, item => item && typeof item === 'object' && (item.scope || item.permission)),
  ];
  return {
    ...detail,
    error,
    title: detail.title || (detail.ok ? '飞书连接测试通过' : '飞书连接测试未通过'),
    failedReason: detail.failed_reason || detail.message || failedStepMessage || error.message || error.msg || '飞书返回了失败结果，请按下方步骤定位。',
    permissionUrls: collectUrls(detail),
    requiredScope: detail.required_scope || error.required_scope,
    permissionViolations,
    fixActions: detail.fix_actions || error.fix_actions || [],
  };
}

export function ProjectSetupTab({
  project,
  projects = [],
  onSelectProject,
  onCreateProject,
  feishuConfig,
  feishuFields,
  feishuTables,
  onSaveProject,
  onSaveScreeningPlan,
  onSaveFeishu,
  onTestFeishu,
  onLoadTables,
  onLoadFields,
  onWriteBack,
}) {
  const [activeSection, setActiveSection] = useState('info');
  const [screeningPlan, setScreeningPlan] = useState(project.screeningPlan || {});
  const [standardStatus, setStandardStatus] = useState('');
  const [collectionFilterStatus, setCollectionFilterStatus] = useState('');
  const [scoringFilterStatus, setScoringFilterStatus] = useState('');
  const [selectedSchemeIds, setSelectedSchemeIds] = useState([]);
  const [expandedSchemeId, setExpandedSchemeId] = useState('');
  const [schemeSaveStatus, setSchemeSaveStatus] = useState({});
  const [feishuStatus, setFeishuStatus] = useState('');
  const [feishuSaved, setFeishuSaved] = useState(false);
  const [feishuTestResult, setFeishuTestResult] = useState(null);
  const [writebackBusy, setWritebackBusy] = useState(false);
  const [optimizingStandard, setOptimizingStandard] = useState(false);
  const [form, setForm] = useState({
    name: project.name, product: project.product, budget: project.budget,
    singleBudget: project.singleBudget || '', creatorCount: project.creatorCount,
    periodStart: project.periodStart || '', periodEnd: project.periodEnd || '',
    cooperationType: project.cooperationType || '合作笔记', description: project.description,
  });
  const [saved, setSaved] = useState(false);
  const [savingStandard, setSavingStandard] = useState(false);
  const [feishuForm, setFeishuForm] = useState({
    feishu_url: feishuConfig?.feishu_url || project.feishuBinding?.tableUrl || '',
    app_id: feishuConfig?.app_id || '',
    app_secret: '',
    table_id: project.feishuBinding?.tableId || '',
  });

  const hasProjectInfo = Boolean((project.id || project.project_id) && (form.name || project.name) && (form.product || project.product));
  const projectInfoCompleted = saved || hasProjectInfo;
  const feishuCompleted = Boolean(feishuSaved || project.feishuBinding?.linked || feishuConfig?.feishu_url);
  const canUseFeishuStep = projectInfoCompleted;
  const canUseStandardStep = projectInfoCompleted && feishuCompleted;

  useEffect(() => {
    const nextPlan = normalizeWorkbenchPlan(project.screeningPlan || {});
    const nextSchemes = nextPlan.pgyCollectionPlan?.schemes || [];
    const nextIds = enabledSchemeIdsFor(nextPlan.pgyCollectionPlan || {});
    setScreeningPlan(nextPlan);
    setSelectedSchemeIds(nextIds);
    setExpandedSchemeId(nextIds[0] || (nextSchemes[0] ? schemeKey(nextSchemes[0], 0) : ''));
    setSchemeSaveStatus({});
  }, [project.screeningPlan]);

  useEffect(() => {
    const nextPlan = normalizeWorkbenchPlan(project.screeningPlan || {});
    const nextSchemes = nextPlan.pgyCollectionPlan?.schemes || [];
    const nextIds = enabledSchemeIdsFor(nextPlan.pgyCollectionPlan || {});
    setScreeningPlan(nextPlan);
    setSelectedSchemeIds(nextIds);
    setExpandedSchemeId(nextIds[0] || (nextSchemes[0] ? schemeKey(nextSchemes[0], 0) : ''));
    setSchemeSaveStatus({});
    setSaved(false);
    setFeishuSaved(false);
    setFeishuStatus('');
    setStandardStatus('');
    setCollectionFilterStatus('');
    setScoringFilterStatus('');
    setFeishuForm(old => ({
      ...old,
      feishu_url: feishuConfig?.feishu_url || project.feishuBinding?.tableUrl || '',
      app_id: feishuConfig?.app_id || old.app_id || '',
      table_id: project.feishuBinding?.tableId || old.table_id || '',
    }));
  }, [feishuConfig, project.id, project.feishuBinding?.tableId, project.feishuBinding?.tableUrl]);

  useEffect(() => {
    setForm({
      name: project.name,
      product: project.product,
      budget: project.budget,
      singleBudget: project.singleBudget || '',
      creatorCount: project.creatorCount,
      periodStart: project.periodStart || '',
      periodEnd: project.periodEnd || '',
      cooperationType: project.cooperationType || '合作笔记',
      description: project.brief?.description || project.description || '',
    });
  }, [
    project.id,
    project.name,
    project.product,
    project.budget,
    project.singleBudget,
    project.creatorCount,
    project.periodStart,
    project.periodEnd,
    project.cooperationType,
    project.description,
    project.brief?.description,
  ]);

  const sections = [
    { key: 'info', label: '立项信息', icon: <FileText size={14} />, step: '01', done: projectInfoCompleted },
    { key: 'feishu', label: '飞书绑定', icon: <Link2 size={14} />, step: '02', done: feishuCompleted, disabled: !canUseFeishuStep },
    { key: 'standard', label: 'Brief 解析', icon: <Target size={14} />, step: '03', done: Boolean(screeningPlan?.briefType), disabled: !canUseStandardStep },
  ];

  const labelStyle = { fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 };
  const feishuFailure = useMemo(() => normalizeFeishuTestResult(feishuTestResult), [feishuTestResult]);

  const runFeishuTest = async () => {
    if (!onTestFeishu) return;
    setFeishuTestResult(null);
    try {
      const result = await onTestFeishu(feishuForm);
      setFeishuTestResult(result);
    } catch (error) {
      setFeishuTestResult(error.detail || { ok: false, message: error.message || '飞书连接测试未通过' });
    }
  };

  const runWriteBack = async () => {
    if (!onWriteBack) return;
    setWritebackBusy(true);
    setFeishuStatus('正在写回飞书，请稍等...');
    try {
      const result = await onWriteBack(feishuForm.table_id);
      if (result?.ok === false) {
        setFeishuStatus(result.message || result.error || '写回飞书失败，请检查飞书权限或字段映射');
        return result;
      }
      setFeishuStatus(`写回完成：${result?.written_count || 0} 位达人`);
      return result;
    } catch (error) {
      setFeishuStatus(error.message || '写回飞书失败，请检查飞书权限或网络');
      return null;
    } finally {
      setWritebackBusy(false);
    }
  };

  const runAiFieldMapping = async () => {
    if (!onLoadFields) return;
    setFeishuStatus('正在使用大模型分析飞书字段映射...');
    try {
      const result = await onLoadFields(feishuForm.table_id, true);
      setFeishuStatus(result?.message || '大模型字段映射分析完成');
      return result;
    } catch (error) {
      setFeishuStatus(error.message || '大模型字段映射失败，请检查模型配置或飞书权限');
      return null;
    }
  };

  const goToSection = (section) => {
    if (section.disabled) return;
    setActiveSection(section.key);
  };

  const saveProjectInfo = async () => {
    if (onSaveProject) await onSaveProject({
      project_name: form.name,
      product: form.product,
      budget: Number(form.budget || 0),
      singleBudget: Number(form.singleBudget || 0),
      poolType: project.poolType,
      sharedPoolId: project.sharedPoolId,
      cooperationType: form.cooperationType,
      target_qualified_creator_count: Number(form.creatorCount || 10),
      period_start: form.periodStart,
      period_end: form.periodEnd,
      brief: form.description,
    });
    setSaved(true);
    setActiveSection('feishu');
  };

  const saveFeishuBinding = async () => {
    setFeishuStatus('正在保存飞书绑定...');
    try {
      const result = await onSaveFeishu?.(feishuForm);
      setFeishuStatus(result?.ok === false ? (result.message || result.error || '飞书绑定保存失败') : '飞书绑定已保存');
      if (result?.ok !== false) {
        setFeishuSaved(true);
      }
      return result;
    } catch (error) {
      setFeishuStatus(error.message || '飞书绑定保存失败');
      return null;
    }
  };

  const optimizeStandard = async () => {
    if (!canUseStandardStep) {
      setStandardStatus('请先完成立项信息和飞书绑定，再解析 Brief');
      return;
    }
    setOptimizingStandard(true);
    setStandardStatus('正在保存 Brief，并读取飞书字段生成量化标准...');
    try {
      if (onSaveProject) {
        await onSaveProject({
          project_name: form.name,
          product: form.product,
          budget: Number(form.budget || 0),
          singleBudget: Number(form.singleBudget || 0),
          poolType: project.poolType,
          sharedPoolId: project.sharedPoolId,
          cooperationType: form.cooperationType,
          target_qualified_creator_count: Number(form.creatorCount || 10),
          period_start: form.periodStart,
          period_end: form.periodEnd,
          brief: form.description,
        });
      }
      let fields = feishuFields || [];
      if ((!fields || fields.length === 0) && onLoadFields) {
        await onLoadFields(feishuForm.table_id);
        const data = await api(`/api/projects/feishu/fields?project_id=${project.id}${feishuForm.table_id ? `&table_id=${feishuForm.table_id}` : ''}`);
        fields = data.fields || [];
      }
      const result = await api(`/api/projects/${project.id}/screening-standard/optimize`, {
        method: 'POST',
        body: JSON.stringify({
          project_id: project.id,
          brief: form.description,
          project: {
            name: form.name,
            product: form.product,
            budget: form.budget,
            singleBudget: form.singleBudget,
            creatorCount: form.creatorCount,
            periodStart: form.periodStart,
            periodEnd: form.periodEnd,
          },
          feishu_fields: fields,
        }),
      });
      const nextPlan = normalizeWorkbenchPlan(syncScreeningCriteria(result.screeningPlan || {}));
      const nextSchemes = nextPlan.pgyCollectionPlan?.schemes || [];
      const nextIds = enabledSchemeIdsFor(nextPlan.pgyCollectionPlan || {});
      setScreeningPlan(nextPlan);
      setSelectedSchemeIds(nextIds);
      setExpandedSchemeId(nextIds[0] || (nextSchemes[0] ? schemeKey(nextSchemes[0], 0) : ''));
      setStandardStatus(result.source === 'llm' ? '已调用大模型，并结合飞书字段完成优化' : result.message || '测试阶段已生成量化标准');
    } catch (error) {
      setStandardStatus(error.message || error.message_cn || error.detail?.message || '优化量化标准失败，请检查大模型配置和飞书绑定');
    } finally {
      setOptimizingStandard(false);
    }
  };

  const saveStandard = async () => {
    if (!onSaveScreeningPlan || !screeningPlan?.briefType) return;
    setSavingStandard(true);
    setStandardStatus('正在保存量化标准...');
    try {
      const nextPlan = syncScreeningCriteria({
        ...screeningPlan,
        pgyCollectionPlan: {
          ...(screeningPlan.pgyCollectionPlan || {}),
          enabled_scheme_ids: selectedSchemeIds,
        },
      });
      await onSaveScreeningPlan(nextPlan, {
        project_name: form.name,
        product: form.product,
        budget: Number(form.budget || 0),
        singleBudget: Number(form.singleBudget || 0),
        poolType: project.poolType,
        sharedPoolId: project.sharedPoolId,
        cooperationType: form.cooperationType,
        target_qualified_creator_count: Number(form.creatorCount || 10),
        period_start: form.periodStart,
        period_end: form.periodEnd,
        brief: form.description,
      });
      setScreeningPlan(normalizeWorkbenchPlan(nextPlan));
      setStandardStatus('量化标准已保存，刷新后会自动恢复');
    } catch (error) {
      setStandardStatus(error.message || error.message_cn || error.detail?.message || '保存量化标准失败');
    } finally {
      setSavingStandard(false);
    }
  };

  const updateHardFilterGroup = (key, filters) => {
    setScreeningPlan(old => syncScreeningCriteria({
      ...old,
      [key]: filters,
    }));
  };

  const scoringHardFilterOptions = useMemo(
    () => mergeOptionItems(screeningPlan.scoringHardFilters || [], hardFilterOptionsFor(DEFAULT_SCORING_HARD_FILTER_FIELDS), hardFilterKey),
    [screeningPlan.scoringHardFilters]
  );

  const pgyPlan = screeningPlan.pgyCollectionPlan || {};
  const schemes = Array.isArray(pgyPlan.schemes) ? pgyPlan.schemes : [];

  const patchScheme = (targetIndex, patcher) => {
    setCollectionFilterStatus('');
    setScreeningPlan(old => {
      const oldPlan = old.pgyCollectionPlan || {};
      const nextSchemes = (oldPlan.schemes || []).map((scheme, index) => (
        index === targetIndex ? patcher(scheme) : scheme
      ));
      return syncScreeningCriteria({
        ...old,
        pgyCollectionPlan: {
          ...oldPlan,
          schemes: nextSchemes,
        },
      });
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
      setCollectionFilterStatus('');
      setScreeningPlan(plan => syncScreeningCriteria({
        ...plan,
        pgyCollectionPlan: {
          ...(plan.pgyCollectionPlan || {}),
          enabled_scheme_ids: nextIds,
        },
      }));
      return nextIds;
    });
  };

  const saveScreeningPlanPart = async (part) => {
    const setStatus = part === 'collection' ? setCollectionFilterStatus : setScoringFilterStatus;
    setStatus('正在保存...');
    try {
      const nextPlan = syncScreeningCriteria({
        ...screeningPlan,
        pgyCollectionPlan: {
          ...(screeningPlan.pgyCollectionPlan || {}),
          enabled_scheme_ids: selectedSchemeIds,
        },
      });
      await onSaveScreeningPlan?.(nextPlan, {
        project_name: form.name,
        product: form.product,
        budget: Number(form.budget || 0),
        singleBudget: Number(form.singleBudget || 0),
        poolType: project.poolType,
        sharedPoolId: project.sharedPoolId,
        cooperationType: form.cooperationType,
        target_qualified_creator_count: Number(form.creatorCount || 10),
        period_start: form.periodStart,
        period_end: form.periodEnd,
        brief: form.description,
      });
      setScreeningPlan(normalizeWorkbenchPlan(nextPlan));
      setStatus(part === 'collection' ? '方案采集条件已保存，并同步到采集工作台' : '评分筛选条件已保存，并同步到初筛评分工作台');
    } catch (error) {
      setStatus(error.message || '保存失败');
    }
  };

  const saveSchemeConfig = async (id) => {
    setSchemeSaveStatus(old => ({ ...old, [id]: '正在保存本方案...' }));
    try {
      const nextPlan = syncScreeningCriteria({
        ...screeningPlan,
        pgyCollectionPlan: {
          ...(screeningPlan.pgyCollectionPlan || {}),
          enabled_scheme_ids: selectedSchemeIds,
        },
      });
      await onSaveScreeningPlan?.(nextPlan, {
        project_name: form.name,
        product: form.product,
        budget: Number(form.budget || 0),
        singleBudget: Number(form.singleBudget || 0),
        poolType: project.poolType,
        sharedPoolId: project.sharedPoolId,
        cooperationType: form.cooperationType,
        target_qualified_creator_count: Number(form.creatorCount || 10),
        period_start: form.periodStart,
        period_end: form.periodEnd,
        brief: form.description,
      });
      setScreeningPlan(normalizeWorkbenchPlan(nextPlan));
      setSchemeSaveStatus(old => ({ ...old, [id]: '本方案已保存，采集工作台会使用当前配置' }));
      setCollectionFilterStatus('方案配置已保存，并同步到采集工作台');
    } catch (error) {
      setSchemeSaveStatus(old => ({ ...old, [id]: error.message || '本方案保存失败' }));
    }
  };

  return (
    <div className="project-setup-workbench">
      <div className="project-config-header card">
        <div>
          <div className="screening-workbench-eyebrow">Project Config</div>
          <h3>项目配置</h3>
          <p>选择已有项目或新建项目后，按立项信息、飞书绑定、Brief 解析顺序完成配置。</p>
        </div>
        <div className="project-config-actions">
          <select
            className="select-field"
            value={project.id || project.project_id || ''}
            onChange={(event) => {
              const next = projects.find(item => (item.id || item.project_id) === event.target.value);
              if (next) onSelectProject?.(next);
            }}
          >
            {projects.map(item => {
              const id = item.id || item.project_id;
              return <option key={id} value={id}>{item.name || item.project_name || id}</option>;
            })}
          </select>
          <button type="button" className="btn btn-primary" onClick={onCreateProject}>
            <Plus size={14} />新建项目
          </button>
        </div>
      </div>

      {/* 分段 Tab */}
      <div className="project-setup-tabs">
        {sections.map(s => (
          <button
            key={s.key}
            type="button"
            onClick={() => goToSection(s)}
            disabled={s.disabled}
            title={s.disabled ? (s.key === 'feishu' ? '请先保存立项信息' : '请先完成立项和飞书绑定') : s.label}
            className={`project-setup-tab ${activeSection === s.key ? 'is-active' : ''} ${s.done ? 'is-done' : ''}`}
          >
            <span className="project-setup-step-index">{s.done ? <CheckCircle2 size={13} /> : s.step}</span>
            {s.icon} {s.label}
          </button>
        ))}
      </div>

      {/* 立项信息 */}
      {activeSection === 'info' && (
        <div className="card project-setup-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <h4 style={{ margin: 0, color: 'var(--text-primary)' }}>项目立项信息</h4>
            <Badge variant={project.status === '进行中' ? 'blue' : project.status === '已完成' ? 'green' : 'amber'}>{project.status}</Badge>
          </div>
          <div className="project-setup-form-grid" style={{ marginBottom: 16 }}>
            <div><label style={labelStyle}>项目 ID</label><input className="input-field" value={project.id} disabled /></div>
            <div><label style={labelStyle}>项目名称 *</label><input className="input-field" value={form.name} onChange={e => setForm({...form, name: e.target.value})} /></div>
            <div><label style={labelStyle}>产品名称 *</label><input className="input-field" value={form.product} onChange={e => setForm({...form, product: e.target.value})} /></div>
            <div><label style={labelStyle}>达人池类型</label>
              <select className="select-field" value={project.poolType} disabled>
                <option value="shared">共享池</option><option value="isolated">独立池</option>
              </select>
            </div>
            <div><label style={labelStyle}>总预算（元）</label><input className="input-field" type="number" value={form.budget} onChange={e => setForm({...form, budget: e.target.value})} /></div>
            <div><label style={labelStyle}>单达人预算上限（元）</label><input className="input-field" type="number" value={form.singleBudget} onChange={e => setForm({...form, singleBudget: e.target.value})} /></div>
            <div><label style={labelStyle}>目标达人数量</label><input className="input-field" type="number" value={form.creatorCount} onChange={e => setForm({...form, creatorCount: e.target.value})} /></div>
            <div><label style={labelStyle}>合作形式</label>
              <select className="select-field" value={form.cooperationType} onChange={e => setForm({...form, cooperationType: e.target.value})}>
                <option value="合作笔记">合作笔记</option><option value="视频+图文">视频+图文</option><option value="报备">报备</option><option value="直播带货">直播带货</option>
              </select>
            </div>
            <div><label style={labelStyle}>开始日期</label><input className="input-field" type="date" value={form.periodStart} onChange={e => setForm({...form, periodStart: e.target.value})} /></div>
            <div><label style={labelStyle}>结束日期</label><input className="input-field" type="date" value={form.periodEnd} onChange={e => setForm({...form, periodEnd: e.target.value})} /></div>
          </div>
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>项目描述</label>
            <textarea className="input-field" rows={3} value={form.description} onChange={e => setForm({...form, description: e.target.value})} style={{ resize: 'none' }} />
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <button className="btn btn-primary" onClick={saveProjectInfo}><Save size={14} style={{ marginRight: 4 }} />保存并进入飞书绑定</button>
            {saved && <span style={{ fontSize: 12, color: '#10B981' }}>✓ 已保存</span>}
          </div>
        </div>
      )}

      {/* 量化标准 */}
      {activeSection === 'standard' && (
        <div>
          <div className="card project-setup-card" style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <h4 style={{ margin: 0, color: 'var(--text-primary)' }}>Brief 解析与标准生成</h4>
              <Badge variant={screeningPlan?.briefType === 'complex' ? 'amber' : 'blue'}>
                {screeningPlan?.briefType === 'complex' ? '复杂需求' : '简单需求'}
              </Badge>
            </div>
            <div style={{ marginBottom: 20 }}>
              <label style={labelStyle}>客户 Brief（用于生成量化标准）</label>
              <textarea
                className="input-field"
                rows={4}
                value={form.description}
                onChange={e => setForm({ ...form, description: e.target.value })}
                placeholder="请输入客户需求、目标人群、达人画像、预算限制等，用于生成量化筛选标准"
                style={{ resize: 'vertical', minHeight: 92 }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginTop: 10, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 12, color: standardStatus.includes('失败') ? '#FCA5A5' : 'var(--text-secondary)' }}>{standardStatus || '会结合当前 Brief、项目预算和飞书字段优化量化标准'}</span>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  <button className="btn btn-secondary" onClick={optimizeStandard} disabled={optimizingStandard || !form.description?.trim() || !canUseStandardStep}>
                    <Sparkles size={14} style={{ marginRight: 4 }} />{optimizingStandard ? '解析中...' : '解析 Brief 生成标准'}
                  </button>
                  <button className="btn btn-primary" onClick={saveStandard} disabled={savingStandard || !screeningPlan?.briefType}>
                    <Save size={14} style={{ marginRight: 4 }} />{savingStandard ? '保存中...' : '保存标准'}
                  </button>
                </div>
              </div>
            </div>
            {screeningPlan?.briefType ? (
              <div>
                {/* 硬性条件 */}
                <div style={{ marginBottom: 20 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                      <Shield size={14} style={{ color: '#EF4444' }} /> 硬性筛选条件
                    </span>
                    <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>采集条件按方案维护，评分条件用于采后初筛</span>
                  </div>
                  <div className="standard-hard-filter-group">
                    <div className="standard-hard-filter-group-title">
                      <span><Download size={14} />方案采集条件</span>
                      <small>地域、报价、粉丝量等采集约束在各方案内维护，勾选的方案会同步到采集工作台</small>
                    </div>
                    {schemes.length > 0 ? (
                      <div className="collection-scheme-card-grid">
                        {schemes.map((scheme, index) => {
                          const id = schemeKey(scheme, index);
                          const selected = selectedSchemeIds.includes(id);
                          const expanded = expandedSchemeId === id;
                          const requiredFilters = getSchemeRequiredFilters(scheme);
                          const additionalFilters = getSchemeAdditionalFilters(scheme);
                          const enabledAdditionalFilters = scheme.enabled_additional_filters || scheme.enabled_extra_filters || [];
                          const editableFilters = mergeOptionItems(requiredFilters, enabledAdditionalFilters, pgyFilterKey);
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
                                <button
                                  type="button"
                                  className={`collection-plan-collapse-button ${expanded ? 'is-expanded' : ''}`}
                                  onClick={() => setExpandedSchemeId(expanded ? '' : id)}
                                  aria-expanded={expanded}
                                >
                                  <span className="collection-plan-collapse-main">
                                    <span className="collection-plan-collapse-icon">
                                      <Settings size={14} />
                                    </span>
                                    <span className="collection-plan-collapse-copy">
                                      <strong>配置方案</strong>
                                      <small>{expanded ? '收起后回到方案概览' : '展开查看可编辑条件'}</small>
                                    </span>
                                  </span>
                                  <span className="collection-plan-collapse-action">
                                    <span className="collection-plan-toggle-text">{expanded ? '收起' : '展开'}</span>
                                    <ChevronDown size={14} className={expanded ? 'is-open' : ''} />
                                  </span>
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
                                  <strong>采集时读取</strong>
                                </div>
                                <div>
                                  <span>方案状态</span>
                                  <strong>{selected ? '纳入采集' : '不采集'}</strong>
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
                                    <small>这里修改后保存，采集工作台会沿用同一方案</small>
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
                    ) : (
                      <div className="collection-empty-text">暂无采集方案，请先解析 Brief 生成标准。</div>
                    )}
                    <div className="standard-filter-save-row">
                      <span className={collectionFilterStatus.includes('失败') ? 'is-error' : ''}>{collectionFilterStatus || '保存后采集工作台会同步使用各方案条件。'}</span>
                      <button type="button" className="btn btn-primary btn-sm" onClick={() => saveScreeningPlanPart('collection')}>
                        <Save size={14} />保存方案采集条件
                      </button>
                    </div>
                  </div>
                  <div className="standard-hard-filter-group">
                    <div className="standard-hard-filter-group-title">
                      <span><Sparkles size={14} />评分筛选条件</span>
                      <small>按已勾选筛选条件展示，保存后初筛评分工作台同步使用</small>
                    </div>
                    <HardFilterCheckPanel
                      filters={screeningPlan.scoringHardFilters || []}
                      options={scoringHardFilterOptions}
                      onChange={(filters) => {
                        setScoringFilterStatus('');
                        updateHardFilterGroup('scoringHardFilters', filters);
                      }}
                      emptyText="暂无评分筛选条件，可从可选项添加或手工新增"
                    />
                    <div className="standard-filter-save-row">
                      <span className={scoringFilterStatus.includes('失败') ? 'is-error' : ''}>{scoringFilterStatus || '保存后评分工作台会同步使用当前条件。'}</span>
                      <button type="button" className="btn btn-primary btn-sm" onClick={() => saveScreeningPlanPart('scoring')}>
                        <Save size={14} />保存评分条件
                      </button>
                    </div>
                  </div>
                </div>

                {/* 评分权重 */}
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Activity size={14} style={{ color: '#3B82F6' }} /> 评分维度权重
                  </div>
                  {Object.keys(screeningPlan.scoringWeights || {}).length > 0 ? (
                    <div className="project-setup-weight-grid">
                      {Object.entries(screeningPlan.scoringWeights || {}).map(([key, weight]) => {
                        const labels = { budget: '预算匹配', fans: '粉丝量级', cpe: 'CPE效率', engagement: '互动质量', persona: '人设匹配', content: '内容风格' };
                        return (
                          <div key={key} className="project-setup-weight-card">
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{labels[key] || key}</span>
                              <span style={{ fontSize: 16, fontWeight: 700, color: '#3B82F6' }}>{weight}%</span>
                            </div>
                            <ProgressBar value={weight} size="sm" color="blue" />
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div style={{ padding: 16, background: 'var(--bg-elevated)', borderRadius: 6, textAlign: 'center', color: 'var(--text-muted)' }}>
                      暂未生成评分标准
                    </div>
                  )}
                </div>
                {(screeningPlan.fieldMappings || []).length > 0 && (
                  <div style={{ marginTop: 20 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <FileSpreadsheet size={14} style={{ color: '#10B981' }} /> 飞书字段匹配
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      {(screeningPlan.fieldMappings || []).map((item, i) => (
                        <span key={i} className="tag" style={{ fontSize: 12 }}>
                          {item.standard} → {item.feishu || '未匹配'}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {screeningPlan.pgyCollectionPlan && (
                  <div style={{ marginTop: 20 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Bot size={14} style={{ color: '#3B82F6' }} /> 蒲公英采集计划
                    </div>
                    <div className="project-setup-preview-grid">
                      <div className="project-setup-preview-card">
                        <div style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 8 }}>方案映射</div>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          {schemes.length > 0 ? schemes.map((scheme, i) => {
                            const id = schemeKey(scheme, i);
                            return (
                              <span key={id} className="tag">
                                {schemeDisplayName(scheme, i)}：{scheme.name || id}{selectedSchemeIds.includes(id) ? '' : '（未勾选）'}
                              </span>
                            );
                          }) : (screeningPlan.pgyCollectionPlan.filters || []).map((item, i) => (
                            <span key={`${item.field}-${item.value}-${i}`} className="tag">{pgyFilterLabel(item)}</span>
                          ))}
                        </div>
                      </div>
                      <div className="project-setup-preview-card">
                        <div style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 8 }}>展示指标</div>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          {(screeningPlan.pgyCollectionPlan.display_metrics || []).map(item => <span key={item} className="tag">{item}</span>)}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: 32 }}>
                <Bot size={32} style={{ color: 'var(--text-muted)', marginBottom: 12 }} />
                <p style={{ color: 'var(--text-secondary)', marginBottom: 16 }}>尚未解析 Brief，请先完成立项信息和飞书绑定</p>
                <button className="btn btn-primary" onClick={optimizeStandard} disabled={optimizingStandard || !form.description?.trim() || !canUseStandardStep}>
                  <Sparkles size={14} style={{ marginRight: 4 }} />{optimizingStandard ? '解析中...' : '解析 Brief 生成标准'}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 飞书绑定 */}
      {activeSection === 'feishu' && (
        <div>
          <div className="card project-setup-card" style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <h4 style={{ margin: 0, color: 'var(--text-primary)' }}>飞书表格绑定</h4>
              <Badge variant={project.feishuBinding?.linked ? 'green' : 'default'}>
                {project.feishuBinding?.linked ? '已绑定' : '未绑定'}
              </Badge>
            </div>

            <div>
              <div className="project-setup-feishu-grid" style={{ marginBottom: 20 }}>
                <div><label style={labelStyle}>飞书链接</label><input className="input-field" value={feishuForm.feishu_url} onChange={e => setFeishuForm({ ...feishuForm, feishu_url: e.target.value })} placeholder="粘贴电子表格或多维表格链接" /></div>
                <div><label style={labelStyle}>App ID</label><input className="input-field" value={feishuForm.app_id} onChange={e => setFeishuForm({ ...feishuForm, app_id: e.target.value })} placeholder="cli_xxx" /></div>
                <div><label style={labelStyle}>App Secret</label><input className="input-field" type="password" value={feishuForm.app_secret} onChange={e => setFeishuForm({ ...feishuForm, app_secret: e.target.value })} placeholder={feishuConfig?.app_secret_configured ? '已配置，留空沿用' : '请输入'} /></div>
              </div>

              <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
                <button className="btn btn-primary" onClick={saveFeishuBinding}><Save size={14} style={{ marginRight: 4 }} />保存绑定</button>
                <button className="btn btn-secondary" onClick={runFeishuTest}><CheckCircle2 size={14} style={{ marginRight: 4 }} />测试连接</button>
                <button className="btn btn-secondary" onClick={onLoadTables}><Database size={14} style={{ marginRight: 4 }} />读取子表</button>
                <button className="btn btn-primary" onClick={runWriteBack} disabled={writebackBusy}>
                  <Send size={14} style={{ marginRight: 4 }} />{writebackBusy ? '写回中...' : '写回飞书'}
                </button>
              </div>
              {feishuStatus && (
                <div style={{ marginBottom: 16, color: feishuStatus.includes('失败') ? '#FCA5A5' : 'var(--text-secondary)', fontSize: 12 }}>
                  {feishuStatus}
                </div>
              )}

              {feishuFailure && (
                <div style={{ marginBottom: 20, padding: 14, border: `1px solid ${feishuFailure.ok ? '#10B98155' : '#F59E0B55'}`, background: feishuFailure.ok ? 'rgba(16, 185, 129, 0.08)' : 'rgba(245, 158, 11, 0.08)', borderRadius: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', marginBottom: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-primary)', fontWeight: 600 }}>
                      {feishuFailure.ok ? <CheckCircle2 size={16} style={{ color: '#10B981' }} /> : <AlertTriangle size={16} style={{ color: '#F59E0B' }} />}
                      {feishuFailure.title}
                    </div>
                    {feishuFailure.failed_step && <Badge variant="amber">卡在：{feishuFailure.failed_step}</Badge>}
                  </div>
                  {!feishuFailure.ok && (
                    <div style={{ marginBottom: 12, padding: 12, border: '1px solid rgba(245, 158, 11, 0.28)', background: 'rgba(255, 255, 255, 0.62)', borderRadius: 8, display: 'grid', gap: 8 }}>
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                        <Info size={14} style={{ color: '#D97706', marginTop: 2, flexShrink: 0 }} />
                        <div>
                          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 2 }}>未通过原因</div>
                          <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 600 }}>{feishuFailure.failedReason}</div>
                        </div>
                      </div>
                      {feishuFailure.permissionUrls.length > 0 && (
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          {feishuFailure.permissionUrls.map((url, index) => (
                            <a key={url} className="btn btn-sm btn-primary" href={url} target="_blank" rel="noreferrer">
                              <ExternalLink size={13} /> 打开飞书权限配置{feishuFailure.permissionUrls.length > 1 ? ` ${index + 1}` : ''}
                            </a>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  <div style={{ display: 'grid', gap: 8 }}>
                    {(feishuFailure.steps || []).map(step => (
                      <div key={step.key} style={{ display: 'grid', gridTemplateColumns: '20px 160px 1fr', gap: 8, alignItems: 'start', fontSize: 12 }}>
                        <span style={{ color: step.status === 'success' ? '#10B981' : step.status === 'failed' ? '#EF4444' : 'var(--text-muted)' }}>
                          {step.status === 'success' ? '✓' : step.status === 'failed' ? '!' : '·'}
                        </span>
                        <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{step.label || step.key}</span>
                        <span style={{ color: 'var(--text-secondary)' }}>{step.message || step.status}</span>
                      </div>
                    ))}
                  </div>
                  {!feishuFailure.ok && (feishuFailure.requiredScope || feishuFailure.permissionViolations.length > 0 || feishuFailure.fixActions.length > 0 || feishuFailure.permissionUrls.length > 0) && (
                    <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border-subtle)', display: 'grid', gap: 8 }}>
                      {feishuFailure.requiredScope && <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>需要权限：<code>{feishuFailure.requiredScope}</code></div>}
                      {feishuFailure.permissionViolations.length > 0 && <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>飞书返回缺失权限：{feishuFailure.permissionViolations.map(item => item.scope || item.permission || JSON.stringify(item)).join('、')}</div>}
                      {feishuFailure.fixActions.map((item, index) => <div key={index} style={{ fontSize: 12, color: 'var(--text-secondary)' }}>处理方式：{item}</div>)}
                    </div>
                  )}
                </div>
              )}

              {(feishuTables || []).length > 0 && (
                <div style={{ marginBottom: 20 }}>
                  <label style={labelStyle}>选择子表</label>
                  <select className="select-field" value={feishuForm.table_id} onChange={e => {
                    const tableId = e.target.value;
                    setFeishuForm({ ...feishuForm, table_id: tableId });
                    onLoadFields?.(tableId);
                  }}>
                    <option value="">请选择子表</option>
                    {feishuTables.map(table => {
                      const id = table.table_id || table.sheet_id || table.id;
                      return <option key={id} value={id}>{table.name || table.title || id}</option>;
                    })}
                  </select>
                  <div style={{ marginTop: 10, display: 'flex', gap: 8, alignItems: 'center' }}>
                    <button type="button" className="btn btn-sm btn-secondary" onClick={runAiFieldMapping} title="使用大模型重新分析字段映射">
                      AI 分析字段映射
                    </button>
                  </div>
                </div>
              )}

                {/* 字段映射 */}
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>字段映射关系</div>
                  {(project.feishuBinding.fieldMapping || []).length > 0 ? (
                    <table className="project-setup-mapping-table">
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border-primary)' }}>
                          <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 500, fontSize: 12 }}>标准字段</th>
                          <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 500, fontSize: 12 }}>飞书字段</th>
                          <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 500, fontSize: 12 }}>类型</th>
                          <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-secondary)', fontWeight: 500, fontSize: 12 }}>可写</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(project.feishuBinding.fieldMapping || []).map((fm, i) => {
                          const matched = (feishuFields || []).find(field => [field.field_name, field.name].includes(fm.standard) || [field.field_name, field.name].includes(fm.feishu));
                          return (
                          <tr key={i} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                            <td style={{ padding: '8px 12px', color: 'var(--text-primary)' }}>{fm.standard}</td>
                            <td style={{ padding: '8px 12px', color: 'var(--text-secondary)' }}>{matched?.field_name || matched?.name || fm.feishu}</td>
                            <td style={{ padding: '8px 12px' }}><Badge variant="default">{fm.type}</Badge></td>
                            <td style={{ padding: '8px 12px' }}>
                              <Badge variant={matched ? 'green' : 'amber'}>{matched ? '可写' : '待匹配'}</Badge>
                            </td>
                          </tr>
                        )})}
                      </tbody>
                    </table>
                  ) : (
                    <div style={{ padding: 16, background: 'var(--bg-elevated)', borderRadius: 6, textAlign: 'center', color: 'var(--text-muted)' }}>暂无字段映射</div>
                  )}
                </div>

              </div>
            </div>

          {/* 写回校验清单 */}
          {project.feishuBinding?.linked && (
            <div className="card project-setup-card">
              <h4 style={{ margin: '0 0 16px', color: 'var(--text-primary)' }}>写回前校验清单</h4>
              {[
                { label: '字段映射已确认', done: true },
                { label: '写回字段均为可写字段', done: true },
                { label: '达人记录已通过审核', done: false },
                { label: '已按蒲公英链接或达人 ID 去重', done: true },
                { label: '必填字段不为空', done: false },
                { label: '项目 ID 和采集批次完整', done: true },
              ].map((item, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: i < 5 ? '1px solid var(--border-subtle)' : 'none' }}>
                  <div style={{ width: 20, height: 20, borderRadius: '50%', border: item.done ? 'none' : '2px solid var(--text-muted)', background: item.done ? '#10B981' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {item.done && <CheckCircle2 size={12} color="#fff" />}
                  </div>
                  <span style={{ color: item.done ? 'var(--text-secondary)' : 'var(--text-secondary)', fontSize: 13, textDecoration: item.done ? 'line-through' : 'none' }}>{item.label}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
