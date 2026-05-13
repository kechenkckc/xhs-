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
import { api } from '../../api/screeningApi';
import {
  DEFAULT_COLLECTION_HARD_FILTER_FIELDS,
  DEFAULT_SCORING_HARD_FILTER_FIELDS,
  hardFilterKey,
  hardFilterLabel,
  WEIGHT_LABELS,
} from '../../constants/screeningConstants';
import { DEFAULT_PGY_DISPLAY_METRICS, PGY_FILTER_OPTIONS } from '../../constants/pgyConstants';
import { briefTextFromProject } from '../../utils/projectMappers';
import { mergeOptionItems, markManualPgyFilters } from '../../utils/pgyFilters';
import { hardFilterOptionsFor, normalizeWorkbenchPlan, syncScreeningCriteria } from '../../utils/screeningPlan';
import { SelectedChips } from '../filters/SelectedChips';
import { PgyFilterCards } from '../filters/PgyFilterCards';
import { PgyFindBloggerFilterPanel } from '../filters/PgyFindBloggerFilterPanel';
import { HardFilterEditor } from '../filters/HardFilterEditor';

export function ProjectSetupTab({ project, feishuConfig, feishuFields, feishuTables, onSaveProject, onSaveScreeningPlan, onSaveFeishu, onTestFeishu, onLoadTables, onLoadFields, onWriteBack }) {
  const [activeSection, setActiveSection] = useState('info');
  const [screeningPlan, setScreeningPlan] = useState(project.screeningPlan || {});
  const [standardStatus, setStandardStatus] = useState('');
  const [feishuTestResult, setFeishuTestResult] = useState(null);
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

  useEffect(() => {
    setScreeningPlan(normalizeWorkbenchPlan(project.screeningPlan || {}));
    setFeishuForm(old => ({
      ...old,
      feishu_url: feishuConfig?.feishu_url || project.feishuBinding?.tableUrl || '',
      app_id: feishuConfig?.app_id || old.app_id || '',
      table_id: project.feishuBinding?.tableId || old.table_id || '',
    }));
  }, [feishuConfig, project.feishuBinding?.tableId, project.feishuBinding?.tableUrl, project.screeningPlan]);

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
    { key: 'info', label: '立项信息', icon: <FileText size={14} /> },
    { key: 'standard', label: '量化标准', icon: <Target size={14} /> },
    { key: 'feishu', label: '飞书绑定', icon: <Link2 size={14} /> },
  ];

  const labelStyle = { fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 };

  const runFeishuTest = async () => {
    if (!onTestFeishu) return;
    try {
      const result = await onTestFeishu(feishuForm);
      setFeishuTestResult(result);
    } catch (error) {
      setFeishuTestResult(error.detail || { ok: false, message: error.message });
    }
  };

  const optimizeStandard = async () => {
    setOptimizingStandard(true);
    setStandardStatus('正在保存 Brief，并读取飞书字段生成量化标准...');
    try {
      if (onSaveProject) {
        await onSaveProject({
          project_name: form.name,
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
      setScreeningPlan(normalizeWorkbenchPlan(syncScreeningCriteria(result.screeningPlan || {})));
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
      const nextPlan = syncScreeningCriteria(screeningPlan);
      await onSaveScreeningPlan(nextPlan, {
        project_name: form.name,
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

  return (
    <div className="project-setup-workbench">
      {/* 分段 Tab */}
      <div className="project-setup-tabs">
        {sections.map(s => (
          <button key={s.key} onClick={() => setActiveSection(s.key)}
            className={`project-setup-tab ${activeSection === s.key ? 'is-active' : ''}`}>
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
            <button className="btn btn-primary" onClick={async () => {
              if (onSaveProject) await onSaveProject({
                project_name: form.name,
                target_qualified_creator_count: Number(form.creatorCount || 10),
                period_start: form.periodStart,
                period_end: form.periodEnd,
                brief: form.description,
              });
              setSaved(true);
            }}><Save size={14} style={{ marginRight: 4 }} />保存立项信息</button>
            {saved && <span style={{ fontSize: 12, color: '#10B981' }}>✓ 已保存</span>}
          </div>
        </div>
      )}

      {/* 量化标准 */}
      {activeSection === 'standard' && (
        <div>
          <div className="card project-setup-card" style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <h4 style={{ margin: 0, color: 'var(--text-primary)' }}>Brief 量化标准</h4>
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
                  <button className="btn btn-secondary" onClick={optimizeStandard} disabled={optimizingStandard || !form.description?.trim()}>
                    <Sparkles size={14} style={{ marginRight: 4 }} />{optimizingStandard ? '优化中...' : 'AI 优化量化标准'}
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
                    <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>已拆分为采集前筛选条件与评分筛选条件，保存后分别应用到采集/评分</span>
                  </div>
                  <div className="standard-hard-filter-group">
                    <div className="standard-hard-filter-group-title">
                      <span><Download size={14} />采集前筛选条件</span>
                      <small>采集工作台展示并编辑，采集入库前使用</small>
                    </div>
                    <HardFilterEditor
                      filters={screeningPlan.collectionHardFilters || []}
                      options={mergeOptionItems(screeningPlan.collectionHardFilters || [], hardFilterOptionsFor(DEFAULT_COLLECTION_HARD_FILTER_FIELDS), hardFilterKey)}
                      onChange={(filters) => updateHardFilterGroup('collectionHardFilters', filters)}
                      emptyText="暂无采集前筛选条件，可从可选项添加或手工新增"
                      fieldHeader="采集筛选项"
                      evidenceHeader="蒲公英/入库字段"
                      evidencePlaceholder="关联蒲公英或入库字段"
                    />
                  </div>
                  <div className="standard-hard-filter-group">
                    <div className="standard-hard-filter-group-title">
                      <span><Sparkles size={14} />评分筛选条件</span>
                      <small>筛选工作台展示并编辑，重新评分时使用</small>
                    </div>
                    <HardFilterEditor
                      filters={screeningPlan.scoringHardFilters || []}
                      options={mergeOptionItems(screeningPlan.scoringHardFilters || [], hardFilterOptionsFor(DEFAULT_SCORING_HARD_FILTER_FIELDS), hardFilterKey)}
                      onChange={(filters) => updateHardFilterGroup('scoringHardFilters', filters)}
                      emptyText="暂无评分筛选条件，可从可选项添加或手工新增"
                      fieldHeader="评分筛选项"
                      evidenceHeader="评分依据字段"
                      evidencePlaceholder="关联评分/飞书字段"
                    />
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
                        <div style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 8 }}>页面筛选条件</div>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          {(screeningPlan.pgyCollectionPlan.filters || []).map((item, i) => (
                            <span key={`${item.field}-${item.value}-${i}`} className="tag">{item.field}：{item.value}</span>
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
                <p style={{ color: 'var(--text-secondary)', marginBottom: 16 }}>尚未生成量化标准，请先在 Brief 中描述需求</p>
                <button className="btn btn-primary" onClick={optimizeStandard} disabled={optimizingStandard || !form.description?.trim()}>
                  <Sparkles size={14} style={{ marginRight: 4 }} />{optimizingStandard ? '生成中...' : 'AI 生成筛选标准'}
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
                <button className="btn btn-primary" onClick={() => onSaveFeishu?.(feishuForm)}><Save size={14} style={{ marginRight: 4 }} />保存绑定</button>
                <button className="btn btn-secondary" onClick={runFeishuTest}><CheckCircle2 size={14} style={{ marginRight: 4 }} />测试连接</button>
                <button className="btn btn-secondary" onClick={onLoadTables}><Database size={14} style={{ marginRight: 4 }} />读取子表</button>
                <button className="btn btn-primary" onClick={() => onWriteBack?.(feishuForm.table_id)}><Send size={14} style={{ marginRight: 4 }} />写回飞书</button>
              </div>

              {feishuTestResult && (
                <div style={{ marginBottom: 20, padding: 14, border: `1px solid ${feishuTestResult.ok ? '#10B98155' : '#F59E0B55'}`, background: 'var(--bg-elevated)', borderRadius: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', marginBottom: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-primary)', fontWeight: 600 }}>
                      {feishuTestResult.ok ? <CheckCircle2 size={16} style={{ color: '#10B981' }} /> : <AlertTriangle size={16} style={{ color: '#F59E0B' }} />}
                      {feishuTestResult.message || (feishuTestResult.ok ? '飞书连接测试通过' : '飞书连接测试未通过')}
                    </div>
                    {feishuTestResult.failed_step && <Badge variant="amber">卡在：{feishuTestResult.failed_step}</Badge>}
                  </div>
                  <div style={{ display: 'grid', gap: 8 }}>
                    {(feishuTestResult.steps || []).map(step => (
                      <div key={step.key} style={{ display: 'grid', gridTemplateColumns: '20px 160px 1fr', gap: 8, alignItems: 'start', fontSize: 12 }}>
                        <span style={{ color: step.status === 'success' ? '#10B981' : step.status === 'failed' ? '#EF4444' : 'var(--text-muted)' }}>
                          {step.status === 'success' ? '✓' : step.status === 'failed' ? '!' : '·'}
                        </span>
                        <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{step.label || step.key}</span>
                        <span style={{ color: 'var(--text-secondary)' }}>{step.message || step.status}</span>
                      </div>
                    ))}
                  </div>
                  {(feishuTestResult.error || feishuTestResult.write_error) && (
                    <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border-subtle)', display: 'grid', gap: 8 }}>
                      {(() => {
                        const error = feishuTestResult.error || feishuTestResult.write_error || {};
                        const urls = error.permission_urls || (error.console_url ? [error.console_url] : []);
                        return (
                          <>
                            {error.required_scope && <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>需要权限：<code>{error.required_scope}</code></div>}
                            {(error.permission_violations || []).length > 0 && <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>飞书返回缺失权限：{error.permission_violations.map(item => item.scope || item.permission || JSON.stringify(item)).join('、')}</div>}
                            {(error.fix_actions || []).map((item, index) => <div key={index} style={{ fontSize: 12, color: 'var(--text-secondary)' }}>处理方式：{item}</div>)}
                            {urls.length > 0 && (
                              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                {urls.map((url, index) => (
                                  <a key={url} className="btn btn-sm btn-primary" href={url} target="_blank" rel="noreferrer">
                                    <ExternalLink size={13} /> 打开飞书权限配置{urls.length > 1 ? ` ${index + 1}` : ''}
                                  </a>
                                ))}
                              </div>
                            )}
                          </>
                        );
                      })()}
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
