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
import { getCreatorDeepAuditReason, getCreatorMatchProfile, getScoreColor } from '../../utils/creatorScoring';
import { CreatorRecentNotesPanel } from './CreatorRecentNotesPanel';

export function CreatorDetailModal({ creator, project, onClose, onCollectDetails, onInvite }) {
  const realNotes = useMemo(() => getCreatorRealNoteCases(creator), [creator]);
  const match = useMemo(() => getCreatorMatchProfile(creator, project), [creator, project]);
  const reasonDetail = useMemo(() => getCreatorDeepAuditReason(creator, realNotes), [creator, realNotes]);
  const noteSourceText = realNotes.length ? '来自蒲公英详情页采集' : '未采集到真实近期笔记';
  const pgyUrl = getPgyUrl(creator);
  const scoreDimLabels = { budget: '预算匹配', fans: '粉丝量级', cpe: 'CPE效率', engagement: '互动质量', persona: '人设匹配', content: '内容风格' };

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
                <p>需要先补采蒲公英详情页，系统才会展示真实笔记标题、阅读、点赞、收藏等数据。</p>
                {onCollectDetails && (
                  <button className="btn btn-primary btn-sm" onClick={() => onCollectDetails({ creatorIds: [creator.id], segment: 'detail-modal', segmentLabel: '详情弹窗补采' })}>
                    补采该达人详情
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
        </div>
      </div>
    </div>
  );
}
