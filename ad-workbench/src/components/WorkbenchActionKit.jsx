import React, { useRef, useState } from 'react';
import { CheckCircle2, RefreshCw, Send, X } from 'lucide-react';
import Modal from './Modal';
import Badge from './Badge';

export function useWorkbenchActions() {
  const [modal, setModal] = useState(null);
  const [toast, setToast] = useState('');
  const toastTimerRef = useRef(null);

  const notify = (message) => {
    setToast(message);
    window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = window.setTimeout(() => setToast(''), 2400);
  };

  const openDetail = (title, payload = {}) => {
    setModal({ type: 'detail', title, payload });
  };

  const openForm = (title, fields = ['操作对象', '负责人', '期望完成时间', '备注'], payload = {}) => {
    setModal({ type: 'form', title, fields, payload });
  };

  const closeModal = () => setModal(null);

  const toastNode = (
    <WorkbenchToast message={toast} onClose={() => setToast('')} />
  );

  const modalNode = (
    <WorkbenchModal
      modal={modal}
      onClose={closeModal}
      onSubmit={() => {
        notify(`${modal?.title || '测试操作'}已提交`);
        closeModal();
      }}
    />
  );

  return { openDetail, openForm, notify, toastNode, modalNode };
}

export function WorkbenchToast({ message, onClose }) {
  if (!message) return null;

  return (
    <div className="workbench-toast" role="status">
      <CheckCircle2 size={16} />
      <span>{message}</span>
      <button type="button" className="workbench-icon-button" onClick={onClose} aria-label="关闭提示">
        <X size={14} />
      </button>
    </div>
  );
}

export function WorkbenchInfoGrid({ items = [] }) {
  return (
    <div className="workbench-info-grid">
      {items.map((item) => (
        <div key={item.label} className="workbench-info-cell">
          <span>{item.label}</span>
          <strong>{item.value ?? '-'}</strong>
          {item.meta && <em>{item.meta}</em>}
        </div>
      ))}
    </div>
  );
}

export function WorkbenchTestForm({ title, fields = [], onSubmit }) {
  const [formData, setFormData] = useState(() => (
    fields.reduce((acc, field) => ({ ...acc, [field]: '' }), {})
  ));

  const reset = () => setFormData(fields.reduce((acc, field) => ({ ...acc, [field]: '' }), {}));

  return (
    <div className="workbench-test-form">
      <div className="workbench-test-form-head">
        <div>
          <div className="section-title" style={{ marginBottom: 4 }}>{title}</div>
          <p>临时测试界面，可先完成前端填写、重置和提交反馈。</p>
        </div>
        <Badge variant="blue">测试界面</Badge>
      </div>
      <div className="workbench-form-grid">
        {fields.map((field, index) => (
          <label key={field} className="workbench-field">
            <span>{field}</span>
            {index === fields.length - 1 ? (
              <textarea
                rows={3}
                value={formData[field]}
                onChange={(event) => setFormData({ ...formData, [field]: event.target.value })}
                placeholder={`填写${field}`}
              />
            ) : (
              <input
                value={formData[field]}
                onChange={(event) => setFormData({ ...formData, [field]: event.target.value })}
                placeholder={`输入${field}`}
              />
            )}
          </label>
        ))}
      </div>
      <div className="workbench-test-actions">
        <button type="button" className="btn btn-secondary" onClick={reset}>
          <RefreshCw size={14} />
          重置
        </button>
        <button type="button" className="btn btn-primary" onClick={onSubmit}>
          <Send size={14} />
          提交测试
        </button>
      </div>
    </div>
  );
}

export function WorkbenchModal({ modal, onClose, onSubmit }) {
  if (!modal) return null;
  const payload = modal.payload || {};
  const items = payload.items || Object.entries(payload)
    .filter(([key, value]) => !['items', 'fields'].includes(key) && value !== undefined && value !== null && typeof value !== 'object')
    .slice(0, 8)
    .map(([key, value]) => ({ label: key, value: String(value) }));

  return (
    <Modal
      isOpen={Boolean(modal)}
      onClose={onClose}
      title={modal.title || '测试界面'}
      size="lg"
      footer={(
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose}>关闭</button>
          <button type="button" className="btn btn-primary" onClick={onSubmit}>保存测试</button>
        </>
      )}
    >
      <div className="workbench-modal-stack">
        {items.length > 0 && <WorkbenchInfoGrid items={items} />}
        <WorkbenchTestForm
          title={modal.type === 'form' ? modal.title : '补充操作'}
          fields={modal.fields || payload.fields || ['处理动作', '负责人', '下一步时间', '备注']}
          onSubmit={onSubmit}
        />
      </div>
    </Modal>
  );
}

export function ClickSurface({ children, onClick, className = '', ariaLabel, as = 'button', ...rest }) {
  if (as === 'div') {
    return (
      <div
        className={`workbench-click-surface ${className}`}
        onClick={onClick}
        role="button"
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') onClick?.(event);
        }}
        aria-label={ariaLabel}
        {...rest}
      >
        {children}
      </div>
    );
  }

  return (
    <button type="button" className={`workbench-click-surface ${className}`} onClick={onClick} aria-label={ariaLabel} {...rest}>
      {children}
    </button>
  );
}
