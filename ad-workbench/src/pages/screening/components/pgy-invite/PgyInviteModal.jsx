import React, { useMemo, useState } from 'react';
import { Calendar, Search, Send, X } from 'lucide-react';
import Badge from '../../../../components/Badge';
import { getCreatorAvatarUrl } from '../../utils/creatorMappers';

const initialForm = {
  brandName: '',
  cooperationType: '图文笔记一口价',
  productName: '',
  expectedStartDate: '',
  expectedEndDate: '',
  contentIntro: '',
  contactType: '微信',
  contactInfo: '',
};

export function PgyInviteModal({ isOpen, creators = [], project, source = '批量邀约', onClose, onSubmit }) {
  const [form, setForm] = useState(() => ({
    ...initialForm,
    brandName: project?.brandName || project?.brief?.product || project?.name || '',
    productName: project?.product || project?.brief?.product || '',
    expectedStartDate: project?.periodStart || project?.period_start || '',
    expectedEndDate: project?.periodEnd || project?.period_end || '',
  }));
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState('');

  const quota = project?.pgyInviteQuota || project?.pgy_invite_quota || 528;
  const creatorPreview = useMemo(() => creators.slice(0, 6), [creators]);
  const isValid = form.brandName.trim()
    && form.productName.trim()
    && form.expectedStartDate
    && form.expectedEndDate
    && form.contentIntro.trim()
    && form.contactInfo.trim()
    && creators.length > 0;

  if (!isOpen) return null;

  const update = (key, value) => {
    if (key === 'productName' && value.length > 20) return;
    if (key === 'contentIntro' && value.length > 200) return;
    setForm(prev => ({ ...prev, [key]: value }));
  };

  const submit = async () => {
    if (!isValid || submitting) return;
    setSubmitting(true);
    setMessage('正在通过蒲公英邀约通道提交...');
    try {
      const payload = await onSubmit?.({ ...form, source });
      setMessage(payload?.message || `已提交 ${creators.length} 位达人邀约`);
      onClose?.(payload);
    } catch (error) {
      setMessage(error.message || '蒲公英邀约提交失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay pgy-invite-overlay" onClick={() => onClose?.()}>
      <div className="modal pgy-invite-modal" onClick={event => event.stopPropagation()}>
        <div className="pgy-invite-header">
          <div>
            <h3>蒲公英批量邀约</h3>
            <p>当前蒲公英账号剩余邀约次数 <strong>{quota}</strong> 次，本次选择达人 <strong>{creators.length}</strong> 位。</p>
          </div>
          <button className="btn btn-ghost btn-sm modal-close" onClick={() => onClose?.()}><X size={16} /></button>
        </div>

        <div className="pgy-invite-body">
          <div className="pgy-invite-targets">
            <span>{source}</span>
            <div>
              {creatorPreview.map(creator => {
                const avatarUrl = getCreatorAvatarUrl(creator);
                return (
                  <Badge key={creator.id} variant="neutral">
                    {avatarUrl && <img src={avatarUrl} alt="" />}
                    {creator.name}
                  </Badge>
                );
              })}
              {creators.length > creatorPreview.length && <Badge variant="blue">+{creators.length - creatorPreview.length}</Badge>}
            </div>
          </div>

          <label className="pgy-invite-row is-required">
            <span>品牌名</span>
            <div className="pgy-invite-search-field">
              <input className="input-field" value={form.brandName} onChange={event => update('brandName', event.target.value)} placeholder="请选择报名品牌" />
              <Search size={16} />
            </div>
          </label>

          <div className="pgy-invite-row is-required">
            <span>合作类型</span>
            <div className="pgy-invite-radio-group">
              {['图文笔记一口价', '视频笔记一口价'].map(type => (
                <label key={type}>
                  <input type="radio" checked={form.cooperationType === type} onChange={() => update('cooperationType', type)} />
                  <span>{type}</span>
                </label>
              ))}
            </div>
          </div>

          <label className="pgy-invite-row is-required">
            <span>产品名称</span>
            <div className="pgy-invite-count-field">
              <input className="input-field" value={form.productName} onChange={event => update('productName', event.target.value)} placeholder="请输入产品名称" />
              <em>{form.productName.length} / 20</em>
            </div>
          </label>

          <div className="pgy-invite-row is-required">
            <span>期望发布时间</span>
            <div className="pgy-invite-date-range">
              <input className="input-field" type="date" value={form.expectedStartDate} onChange={event => update('expectedStartDate', event.target.value)} />
              <i>→</i>
              <input className="input-field" type="date" value={form.expectedEndDate} onChange={event => update('expectedEndDate', event.target.value)} />
              <Calendar size={16} />
            </div>
          </div>

          <label className="pgy-invite-row is-required pgy-invite-textarea-row">
            <span>合作内容介绍</span>
            <div className="pgy-invite-count-field">
              <textarea className="input-field" rows={5} value={form.contentIntro} onChange={event => update('contentIntro', event.target.value)} placeholder="请填写合作内容、核心卖点、内容方向和注意事项" />
              <em>{form.contentIntro.length} / 200</em>
            </div>
          </label>

          <div className="pgy-invite-row">
            <span>联系方式</span>
            <div className="pgy-invite-radio-group">
              {['微信', '手机号'].map(type => (
                <label key={type}>
                  <input type="radio" checked={form.contactType === type} onChange={() => update('contactType', type)} />
                  <span>{type}</span>
                </label>
              ))}
            </div>
          </div>

          <label className="pgy-invite-row is-required">
            <span>联系信息</span>
            <input className="input-field" value={form.contactInfo} onChange={event => update('contactInfo', event.target.value)} placeholder={`请输入${form.contactType}`} />
          </label>
        </div>

        <div className="pgy-invite-footer">
          <span className={message.includes('失败') ? 'is-error' : ''}>{message || '确认后会标记为已邀约，并记录蒲公英邀约参数。'}</span>
          <div>
            <button className="btn btn-secondary" onClick={() => onClose?.()} disabled={submitting}>取消</button>
            <button className="btn btn-primary" onClick={submit} disabled={!isValid || submitting}>
              <Send size={14} />确认
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
