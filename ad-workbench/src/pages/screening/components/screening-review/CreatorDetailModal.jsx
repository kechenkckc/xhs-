import React, { useMemo } from 'react';
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
import { formatCompleteness } from '../../utils/formatters';
import {
  getCreatorAvatarUrl,
  getCreatorLocation,
  getCreatorRealNoteCases,
  getPgyUrl,
  parseStructuredList,
} from '../../utils/creatorMappers';
import { getCreatorAdRecommendation, getCreatorDeepAuditReason, getCreatorMatchProfile, getCreatorModelProfile, getScoreColor } from '../../utils/creatorScoring';
import { CreatorRecentNotesPanel } from './CreatorRecentNotesPanel';

function verdictVariant(value) {
  if (['强推荐', '推荐'].includes(value)) return value === '强推荐' ? 'green' : 'blue';
  if (['备选', '待人工确认'].includes(value)) return 'amber';
  if (['不推荐', 'Pass'].includes(value)) return 'red';
  return 'default';
}

function percentText(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return '待补';
  return `${Math.round(number * 100)}%`;
}

function listText(value, fallback = '暂无') {
  const items = parseStructuredList(value);
  return items.length ? items.join('、') : fallback;
}

export function CreatorDetailModal({ creator, project, onClose, onCollectDetails, onInvite, loadStatus = '' }) {
  const realNotes = useMemo(() => getCreatorRealNoteCases(creator), [creator]);
  const match = useMemo(() => getCreatorMatchProfile(creator, project), [creator, project]);
  const reasonDetail = useMemo(() => getCreatorDeepAuditReason(creator, realNotes), [creator, realNotes]);
  const modelProfile = useMemo(() => getCreatorModelProfile(creator, project), [creator, project]);
  const recommendation = useMemo(() => getCreatorAdRecommendation(creator, realNotes, project), [creator, realNotes, project]);
  const noteSourceText = realNotes.length ? '来自蒲公英详情页采集' : '未采集到真实近期笔记';
  const pgyUrl = getPgyUrl(creator);
  const scoreDimLabels = { budget: '执行确定性', fans: '目标人群匹配', cpe: '成本效率', engagement: '真实流量质量', persona: '产品场景匹配', content: '内容证据加成' };
  const lightProfile = modelProfile.lightProfile;
  const contentModel = modelProfile.contentValueModel;
  const projectFitConfig = project?.screeningPlan?.projectFitConfig || {};
  const projectSceneTags = parseStructuredList(projectFitConfig.preferred_content_scenes).slice(0, 5);
  const projectStyleTags = parseStructuredList(projectFitConfig.preferred_presentation_styles).slice(0, 4);
  const projectGradeTags = parseStructuredList(projectFitConfig.target_grade_keywords).slice(0, 5);
  const projectNegativeTags = parseStructuredList(projectFitConfig.discouraged_keywords).slice(0, 4);
  const evidenceRules = projectFitConfig.evidence_rules || {};
  const llmManualReviewItems = creator.llmManualReviewItems?.length
    ? creator.llmManualReviewItems
    : parseStructuredList(creator.raw?.manual_review_items);
  const llmEvidenceQuotes = creator.llmEvidenceQuotes?.length
    ? creator.llmEvidenceQuotes
    : parseStructuredList(creator.raw?.evidence_quotes);
  const llmConfidence = Number(creator.llmConfidence ?? creator.raw?.llm_confidence);
  const confidenceLabel = Number.isFinite(llmConfidence) ? `${Math.round(llmConfidence * 100)}%` : '待生成';
  const kocVerdict = creator.finalRecommendLevel || creator.projectMatchStatus || '';
  const riskControl = creator.riskControlResult && typeof creator.riskControlResult === 'object' ? creator.riskControlResult : {};
  const riskHardItems = Array.isArray(riskControl.hard) ? riskControl.hard : [];
  const riskMissingItems = Array.isArray(riskControl.missing) ? riskControl.missing : [];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal creator-detail-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header creator-detail-modal-header">
          <div className="creator-detail-profile">
            {getCreatorAvatarUrl(creator) ? (
              <img src={getCreatorAvatarUrl(creator)} alt={creator.name} />
            ) : (
              <div>{creator.name?.[0] || '达'}</div>
            )}
            <div>
              <h3>{creator.name}</h3>
              <p>{creator.type} · {creator.followers} · {creator.quote} · {getCreatorLocation(creator)}</p>
            </div>
          </div>
          <button className="btn btn-ghost btn-sm modal-close" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="modal-body creator-detail-modal-body">
          {loadStatus === 'loading' && (
            <div className="creator-detail-section" style={{ marginTop: 0 }}>
              <div className="creator-detail-empty">正在加载完整达人证据...</div>
            </div>
          )}
          {loadStatus === 'error' && (
            <div className="creator-detail-section" style={{ marginTop: 0 }}>
              <div className="creator-detail-empty">完整达人证据加载失败，当前展示列表摘要。</div>
            </div>
          )}
          {onInvite && (
            <div className="creator-detail-section" style={{ marginTop: 0 }}>
              <div className="creator-detail-section-head">
                <h4>蒲公英邀约通道</h4>
                <button className="btn btn-primary btn-sm" onClick={() => onInvite(creator)}>
                  <Send size={14} />发起邀约
                </button>
              </div>
            </div>
          )}

          <div className="creator-detail-summary">
            <div>
              <span>初筛总分</span>
              <strong style={{ color: getScoreColor(creator.baseScore) }}>{creator.baseScore || 0}</strong>
            </div>
            <div>
              <span>匹配判断</span>
              <strong>{match.tier}</strong>
            </div>
            <div>
              <span>详情完整度</span>
              <strong>{creator.informationCompletenessLabel || formatCompleteness(creator.informationCompleteness)}</strong>
            </div>
            <div>
              <span>近期笔记</span>
              <strong>{realNotes.length}</strong>
            </div>
            <div>
              <span>KOC结论</span>
              <strong>{kocVerdict || '待生成'}</strong>
            </div>
          </div>

          {(kocVerdict || creator.stage1Priority || creator.targetContentRatio !== undefined || creator.productSceneRatio !== undefined) && (
            <section className="creator-detail-section">
              <div className="creator-detail-section-head">
                <h4>KOC二阶段评分</h4>
                <Badge variant={verdictVariant(kocVerdict)}>{kocVerdict || '待二阶段'}</Badge>
              </div>
              <div className="creator-koc-score-grid">
                <div>
                  <span>一阶段优先级</span>
                  <strong>{creator.stage1Priority || '待补'}</strong>
                  <p>{creator.stage1Reason || '入库/补详情优先级待生成'}</p>
                </div>
                <div>
                  <span>项目匹配置信度</span>
                  <strong>{percentText(creator.projectMatchConfidence)}</strong>
                  <p>{creator.projectMatchStatus || '二阶段结论待生成'}</p>
                </div>
                <div>
                  <span>目标内容占比</span>
                  <strong>{percentText(creator.targetContentRatio)}</strong>
                  <p>{listText(creator.targetContentEvidence, '学习/留学内容证据待补')}</p>
                </div>
                <div>
                  <span>产品场景占比</span>
                  <strong>{percentText(creator.productSceneRatio)}</strong>
                  <p>{listText(creator.productSceneEvidence, '听课/笔记/复盘场景证据待补')}</p>
                </div>
                <div>
                  <span>冲突内容占比</span>
                  <strong>{percentText(creator.conflictContentRatio)}</strong>
                  <p>{listText(creator.conflictContentCategories, '暂无明显冲突类目')}</p>
                </div>
                <div>
                  <span>推荐形态</span>
                  <strong>{creator.recommendedFormat || '待补'}</strong>
                  <p>{riskHardItems.length ? `硬风险：${riskHardItems.join('、')}` : riskMissingItems.length ? `待补：${riskMissingItems.join('、')}` : '无明显硬风险'}</p>
                </div>
              </div>
            </section>
          )}

          <section className="creator-detail-section">
            <div className="creator-detail-section-head">
              <h4>综合建模档案</h4>
              <Badge variant={lightProfile.hasDeepProfile ? 'green' : 'default'}>{lightProfile.hasDeepProfile ? '高潜深档案' : '轻量档案'}</Badge>
            </div>
            <div className="creator-model-grid">
              <div className="creator-model-verdict">
                <span>当前结论</span>
                <strong>{lightProfile.decision}</strong>
                <p>{modelProfile.actionRecommendation.nextAction} · 证据完整度 {Math.round(lightProfile.evidenceCompleteness * 100)}%</p>
              </div>
              <div>
                <span>身份模型</span>
                <strong>{modelProfile.identityModel.positioning || '待识别'}</strong>
                <p>{modelProfile.identityModel.persona.length ? modelProfile.identityModel.persona.join('、') : '人设证据待补'}</p>
              </div>
              <div>
                <span>受众模型</span>
                <strong>{modelProfile.audienceModel.parentAudienceFit === 'high' ? '家长人群匹配' : '受众待复核'}</strong>
                <p>{modelProfile.audienceModel.ageFit} · {modelProfile.audienceModel.geoFit}</p>
              </div>
              <div>
                <span>风险模型</span>
                <strong>{modelProfile.riskModel.riskLevel === 'high' ? '高风险' : modelProfile.riskModel.riskLevel === 'medium' ? '中风险' : '低风险'}</strong>
                <p>{modelProfile.riskModel.risks.length ? modelProfile.riskModel.risks.slice(0, 2).join('、') : modelProfile.riskModel.mitigation}</p>
              </div>
            </div>
          </section>

          <section className="creator-detail-section">
            <div className="creator-detail-section-head">
              <h4>项目评分口径</h4>
              <Badge variant={projectFitConfig.product_name ? 'blue' : 'default'}>{projectFitConfig.product_name || '按当前 Brief'}</Badge>
            </div>
            <div className="creator-project-fit">
              <div className="creator-project-fit-main">
                <span>本轮产品适配</span>
                <strong>{projectFitConfig.product_category || '项目化评分配置'}</strong>
                <p>{projectFitConfig.target_audience_summary || projectFitConfig.summary || '围绕 Brief 判断达人是否匹配目标人群、产品场景、内容调性和证据充分度。'}</p>
              </div>
              <div className="creator-project-fit-rule">
                <span>高分证据门槛</span>
                <strong>{evidenceRules.require_scene_evidence_for_a_tier ? '需产品场景证据' : '按通用证据'}</strong>
                <p>场景弱相关最高 {evidenceRules.weak_scene_match_max_score || 79} 分；证据不足最高 {evidenceRules.insufficient_evidence_max_score || 84} 分。</p>
              </div>
            </div>
            <div className="creator-project-fit-tags">
              <div>
                <span>优先场景</span>
                <div>{projectSceneTags.length ? projectSceneTags.map(item => <em key={item}>{item}</em>) : <small>待配置</small>}</div>
              </div>
              <div>
                <span>内容调性</span>
                <div>{projectStyleTags.length ? projectStyleTags.map(item => <em key={item}>{item}</em>) : <small>待配置</small>}</div>
              </div>
              <div>
                <span>目标学段</span>
                <div>{projectGradeTags.length ? projectGradeTags.map(item => <em key={item}>{item}</em>) : <small>待配置</small>}</div>
              </div>
              <div>
                <span>降权内容</span>
                <div>{projectNegativeTags.length ? projectNegativeTags.map(item => <em key={item}>{item}</em>) : <small>无明确降权项</small>}</div>
              </div>
            </div>
          </section>

          <section className="creator-detail-section">
            <div className="creator-detail-section-head">
              <h4>内容价值模型</h4>
              <Badge variant={contentModel.contentValueScore >= 85 ? 'green' : contentModel.contentValueScore >= 70 ? 'blue' : 'amber'}>{contentModel.contentValueScore} 分</Badge>
            </div>
            <div className="creator-content-model">
              <div className="creator-content-radar">
                <div>
                  <span>主题深度</span>
                  <strong>{contentModel.topicDepth}</strong>
                </div>
                <div>
                  <span>场景真实</span>
                  <strong>{contentModel.scenarioAuthenticity}</strong>
                </div>
                <div>
                  <span>表达能力</span>
                  <strong>{contentModel.storytellingAbility}</strong>
                </div>
                <div>
                  <span>种草适配</span>
                  <strong>{contentModel.productSeedingFit}</strong>
                </div>
              </div>
              <div className="creator-content-columns">
                <div>
                  <strong>擅长内容</strong>
                  <p>{contentModel.contentStrengths.join('、')}</p>
                </div>
                <div>
                  <strong>适合角度</strong>
                  <p>{contentModel.bestContentAngles.length ? contentModel.bestContentAngles.join('；') : '需补充笔记正文后判断'}</p>
                </div>
                <div>
                  <strong>不建议角度</strong>
                  <p>{contentModel.weakContentAngles.join('；')}</p>
                </div>
              </div>
            </div>
          </section>

          <section className="creator-detail-section">
            <div className="creator-detail-section-head">
              <h4>代表笔记分析</h4>
              <span>{contentModel.noteAnalysis.length ? `${contentModel.noteAnalysis.length} 篇代表样本` : '待补内容样本'}</span>
            </div>
            {contentModel.noteAnalysis.length ? (
              <div className="creator-note-analysis-grid">
                {contentModel.noteAnalysis.map(note => (
                  <article className="creator-note-analysis-card" key={`${note.noteTitle}-${note.noteValueScore}`}>
                    <div>
                      <strong>{note.noteTitle}</strong>
                      <Badge variant={note.noteValueScore >= 85 ? 'green' : note.noteValueScore >= 70 ? 'blue' : 'amber'}>{note.noteValueScore}</Badge>
                    </div>
                    <p>{note.mainTopic} · {note.scene} · {note.expressionStyle}</p>
                    <small>{note.audienceValue}</small>
                    <small>{note.brandFit}</small>
                    <div>
                      {note.evidence.map(item => <span className="tag creator-pool-tag-content" key={item}>{item}</span>)}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="creator-detail-empty">
                <FileText size={28} />
                <strong>代表笔记分析待生成</strong>
                <p>补采近期笔记标题、正文和互动数据后，可判断擅长内容、种草方式和内容价值分。</p>
              </div>
            )}
          </section>

          <section className="creator-detail-section">
            <div className="creator-detail-section-head">
              <h4>推荐理由</h4>
              <Badge variant={match.matchScore >= 85 ? 'green' : match.matchScore >= 70 ? 'blue' : 'amber'}>{match.matchScore} 分匹配</Badge>
            </div>
            <div className="creator-audit-deep-reason">
              {reasonDetail.sections.map(item => (
                <div key={item.title}>
                  <strong>{item.title}</strong>
                  <p>{item.text}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="creator-detail-section">
            <div className="creator-detail-section-head">
              <h4>待人工复核</h4>
              <Badge variant={recommendation.manualReviewItems?.length ? 'amber' : 'green'}>
                {recommendation.manualReviewItems?.length ? '需复核' : '已清晰'}
              </Badge>
            </div>
            <div className="creator-audit-deep-reason">
              {((llmManualReviewItems.length ? llmManualReviewItems : recommendation.manualReviewItems)?.length ? (llmManualReviewItems.length ? llmManualReviewItems : recommendation.manualReviewItems) : ['当前无额外人工复核项']).map(item => (
                <div key={item}>
                  <strong>{item.split('：')[0] || '复核项'}</strong>
                  <p>{item}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="creator-detail-section">
            <div className="creator-detail-section-head">
              <h4>模型结构化输出</h4>
              <Badge variant={Number.isFinite(llmConfidence) && llmConfidence >= 0.8 ? 'green' : Number.isFinite(llmConfidence) ? 'amber' : 'default'}>
                置信度 {confidenceLabel}
              </Badge>
            </div>
            <div className="creator-llm-output">
              <div>
                <strong>证据摘要</strong>
                {llmEvidenceQuotes.length ? (
                  <ul>{llmEvidenceQuotes.map(item => <li key={item}>{item}</li>)}</ul>
                ) : (
                  <p>当前还没有结构化证据摘要，下一次大模型评分后会自动落库。</p>
                )}
              </div>
              <div>
                <strong>协议版本</strong>
                <p>{creator.llmPromptVersion || creator.raw?.llm_prompt_version || 'prompt 待记录'} · {creator.llmSchemaVersion || creator.raw?.llm_schema_version || 'schema 待记录'}</p>
              </div>
            </div>
          </section>

          <section className="creator-detail-section">
            <div className="creator-detail-section-head">
              <h4>近期笔记详情</h4>
              <span>{noteSourceText}</span>
            </div>
            {realNotes.length ? (
              <CreatorRecentNotesPanel notes={realNotes} />
            ) : (
              <div className="creator-detail-empty">
                <FileText size={28} />
                <strong>未采集到真实近期笔记详情</strong>
                <p>需要完善达人详情页证据，系统才会展示真实笔记标题、阅读、点赞、收藏等数据。</p>
                {onCollectDetails && (
                  <button className="btn btn-primary btn-sm" onClick={() => onCollectDetails({ creatorIds: [creator.id], segment: 'detail-modal', segmentLabel: '详情弹窗完善' })}>
                    完善该达人详情
                  </button>
                )}
              </div>
            )}
          </section>

          <section className="creator-detail-section">
            <div className="creator-detail-section-head">
              <h4>关键数据与风险</h4>
              {pgyUrl && <a href={pgyUrl} target="_blank" rel="noreferrer">蒲公英详情 <ExternalLink size={12} /></a>}
            </div>
            <div className="creator-detail-metrics">
              {creator.scores && Object.entries(creator.scores).map(([key, val]) => (
                <div className="creator-audit-dim" key={key}>
                  <span>{scoreDimLabels[key] || key}</span>
                  <div><i style={{ width: `${Math.min(100, Number(val || 0))}%`, background: getScoreColor(val) }} /></div>
                  <strong>{val}</strong>
                </div>
              ))}
            </div>
            <div className="creator-audit-chip-list">
              {match.matchedSignals.map(item => <span className="tag creator-pool-tag-metric" key={item}>{item}</span>)}
              {match.riskSignals.map(item => <span className="tag creator-audit-risk" key={item}>{item}</span>)}
            </div>
          </section>

          <section className="creator-detail-section">
            <div className="creator-detail-section-head">
              <h4>证据链与行动建议</h4>
              <span>{modelProfile.evidenceChain.length} 条核心判断</span>
            </div>
            <div className="creator-evidence-chain">
              {modelProfile.evidenceChain.map(item => (
                <div key={item.claim}>
                  <div>
                    <strong>{item.claim}</strong>
                    <Badge variant={item.confidence === 'high' ? 'green' : item.confidence === 'medium' ? 'blue' : 'default'}>{item.confidence}</Badge>
                  </div>
                  <p>{item.evidence.length ? item.evidence.map(evidence => evidence.value).join('；') : '证据待补'}</p>
                  {item.missingEvidence.length > 0 && <small>缺失：{item.missingEvidence.join('、')}</small>}
                </div>
              ))}
            </div>
            <div className="creator-action-brief">
              <strong>{modelProfile.actionRecommendation.cooperationAngle}</strong>
              <p>复核重点：{modelProfile.actionRecommendation.reviewFocus.join('、')}；避免：{modelProfile.actionRecommendation.avoidAngle}</p>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
