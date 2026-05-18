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
} from '../../utils/creatorMappers';
import { getCreatorDeepAuditReason, getCreatorMatchProfile, getCreatorModelProfile, getScoreColor } from '../../utils/creatorScoring';
import { CreatorRecentNotesPanel } from './CreatorRecentNotesPanel';

export function CreatorDetailModal({ creator, project, onClose, onCollectDetails, onInvite }) {
  const realNotes = useMemo(() => getCreatorRealNoteCases(creator), [creator]);
  const match = useMemo(() => getCreatorMatchProfile(creator, project), [creator, project]);
  const reasonDetail = useMemo(() => getCreatorDeepAuditReason(creator, realNotes), [creator, realNotes]);
  const modelProfile = useMemo(() => getCreatorModelProfile(creator, project), [creator, project]);
  const noteSourceText = realNotes.length ? '来自蒲公英详情页采集' : '未采集到真实近期笔记';
  const pgyUrl = getPgyUrl(creator);
  const scoreDimLabels = { budget: '预算匹配', fans: '粉丝量级', cpe: 'CPE效率', engagement: '互动质量', persona: '人设匹配', content: '内容风格' };
  const lightProfile = modelProfile.lightProfile;
  const contentModel = modelProfile.contentValueModel;

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
          </div>

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
