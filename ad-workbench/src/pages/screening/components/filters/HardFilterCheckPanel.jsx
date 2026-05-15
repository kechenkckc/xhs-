import React, { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, X } from 'lucide-react';
import { hardFilterKey, hardFilterLabel } from '../../constants/screeningConstants';
import {
  defaultHardFilterCondition,
  hardFilterConditionsFor,
  normalizeHardFilterItem,
} from '../../utils/screeningPlan';
import { HardFilterValueControl } from './HardFilterValueControl';

const hardFilterIdentityKey = (item = {}) => item.pgyField || item.feishuField || item.field || hardFilterKey(item);
const POPOVER_MARGIN = 12;

const defaultGroups = [
  { section: '预算与画像', fields: ['合作报价', '粉丝年龄'] },
  { section: '效率指标', fields: ['预估阅读单价', '预估互动单价'] },
  { section: '入库与风控', fields: ['蒲公英链接', '限流风险'] },
];

function HardFilterPopover({ item, anchorEl, onChange, onRemove, onClose }) {
  const popoverRef = useRef(null);
  const [popoverStyle, setPopoverStyle] = useState(null);

  useLayoutEffect(() => {
    if (!anchorEl) return undefined;

    const updatePosition = () => {
      const anchorRect = anchorEl.getBoundingClientRect();
      const popoverRect = popoverRef.current?.getBoundingClientRect();
      const popoverWidth = popoverRect?.width || Math.min(420, window.innerWidth * 0.82);
      const popoverHeight = popoverRect?.height || 280;
      const maxLeft = Math.max(POPOVER_MARGIN, window.innerWidth - popoverWidth - POPOVER_MARGIN);
      const nextLeft = Math.max(POPOVER_MARGIN, Math.min(anchorRect.left, maxLeft));
      const roomBelow = window.innerHeight - anchorRect.bottom - POPOVER_MARGIN;
      const roomAbove = anchorRect.top - POPOVER_MARGIN;
      const openAbove = roomBelow < Math.min(popoverHeight, 260) && roomAbove > roomBelow;
      const nextTop = openAbove
        ? Math.max(POPOVER_MARGIN, anchorRect.top - popoverHeight - 8)
        : Math.min(anchorRect.bottom + 8, window.innerHeight - POPOVER_MARGIN);

      setPopoverStyle({
        left: `${nextLeft}px`,
        top: `${nextTop}px`,
        maxHeight: `${Math.max(220, openAbove ? roomAbove - 8 : roomBelow - 8)}px`,
      });
    };

    updatePosition();
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);
    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [anchorEl, item]);

  if (!anchorEl) return null;

  return createPortal(
    <div ref={popoverRef} className="pgy-find-filter-popover hard-filter-popover" style={popoverStyle || undefined}>
      <div className="pgy-find-filter-popover-head">
        <strong>{item.field || item.pgyField || '评分条件'}</strong>
        <span>{item.feishuField ? `依据 ${item.feishuField}` : '评分筛选'}</span>
      </div>
      <div className="hard-filter-popover-body">
        <div className="hard-filter-popover-control">
          <HardFilterValueControl filter={item} onChange={onChange} presentation="pgy" />
        </div>
        <label className="standard-hard-filter-required hard-filter-popover-required">
          <input
            type="checkbox"
            checked={item.required !== false}
            onChange={event => onChange?.({ required: event.target.checked })}
          />
          <span>不满足时直接淘汰</span>
        </label>
      </div>
      <div className="pgy-find-filter-popover-actions">
        <button type="button" onClick={onRemove}>移除</button>
        <button type="button" className="is-primary" onClick={onClose}>完成</button>
      </div>
    </div>,
    document.body
  );
}

export function HardFilterCheckPanel({ filters = [], options = [], onChange, groups = defaultGroups, emptyText = '暂无筛选条件' }) {
  const [openKey, setOpenKey] = useState(null);
  const [openAnchor, setOpenAnchor] = useState(null);
  const selectedFilters = filters || [];
  const selectedIdentitySet = useMemo(
    () => new Set(selectedFilters.map(hardFilterIdentityKey).filter(Boolean)),
    [selectedFilters]
  );
  const optionByField = useMemo(
    () => new Map((options || []).map(option => [option.field, option])),
    [options]
  );
  const groupedOptionKeys = useMemo(
    () => new Set((groups || []).flatMap(group => group.fields || [])),
    [groups]
  );
  const extraSelected = selectedFilters.filter(item => !groupedOptionKeys.has(item.field));

  const removeByIdentity = (item) => {
    const key = hardFilterIdentityKey(item);
    onChange?.(selectedFilters.filter(next => hardFilterIdentityKey(next) !== key));
  };

  const updateByIdentity = (item, patch) => {
    const key = hardFilterIdentityKey(item);
    onChange?.(selectedFilters.map(next => {
      if (hardFilterIdentityKey(next) !== key) return next;
      const updated = { ...next, ...patch };
      const conditions = hardFilterConditionsFor(updated);
      if (!conditions.includes(updated.condition)) {
        updated.condition = defaultHardFilterCondition(updated);
      }
      return updated;
    }));
  };

  const toggleOption = (option = {}) => {
    const key = hardFilterIdentityKey(option);
    if (selectedIdentitySet.has(key)) {
      onChange?.(selectedFilters.filter(item => hardFilterIdentityKey(item) !== key));
      if (openKey === key) {
        setOpenKey(null);
        setOpenAnchor(null);
      }
      return;
    }
    onChange?.([...selectedFilters, normalizeHardFilterItem(option)]);
  };

  const openOption = (event, option = {}) => {
    const key = hardFilterIdentityKey(option);
    if (!selectedIdentitySet.has(key)) {
      onChange?.([...selectedFilters, normalizeHardFilterItem(option)]);
    }
    setOpenKey(openKey === key ? null : key);
    setOpenAnchor(openKey === key ? null : event.currentTarget);
  };

  const selectedByOption = (option = {}) => selectedFilters.find(item => hardFilterIdentityKey(item) === hardFilterIdentityKey(option));

  const renderOptionToken = (option) => {
    if (!option) return null;
    const selectedItem = selectedByOption(option);
    const active = Boolean(selectedItem);
    const key = hardFilterIdentityKey(option);
    const displayLabel = active
      ? `${selectedItem.field || option.field}${selectedItem.value ? `：${selectedItem.value}` : selectedItem.condition ? `：${selectedItem.condition}` : ''}`
      : (option.label || hardFilterLabel(option));
    return (
      <span key={key} className="pgy-find-filter-popover-wrap">
        <button
          type="button"
          className={`pgy-find-filter-token has-chevron ${active ? 'is-active' : ''}`}
          onClick={(event) => openOption(event, option)}
          title={active ? hardFilterLabel(selectedItem) : hardFilterLabel(option)}
        >
          <span>{displayLabel}</span>
          <ChevronDown size={14} className={openKey === key ? 'is-open' : ''} />
        </button>
        {openKey === key && (
          <HardFilterPopover
            item={selectedItem || normalizeHardFilterItem(option)}
            anchorEl={openAnchor}
            onChange={patch => updateByIdentity(selectedItem || option, patch)}
            onRemove={() => {
              removeByIdentity(selectedItem || option);
              setOpenKey(null);
              setOpenAnchor(null);
            }}
            onClose={() => {
              setOpenKey(null);
              setOpenAnchor(null);
            }}
          />
        )}
      </span>
    );
  };

  return (
    <div className="pgy-find-filter-panel hard-filter-check-panel">
      {selectedFilters.length > 0 ? (
        <div className="pgy-find-selected-bar">
          <span>已选条件</span>
          <div className="pgy-find-selected-list">
            {selectedFilters.map(item => (
              <button
                key={hardFilterKey(item)}
                type="button"
                onClick={() => removeByIdentity(item)}
                title={hardFilterLabel(item)}
              >
                {hardFilterLabel(item)}
                <X size={12} />
              </button>
            ))}
          </div>
          <button type="button" className="pgy-find-clear-all" onClick={() => onChange?.([])}>清空全部</button>
        </div>
      ) : (
        <div className="pgy-find-selected-bar">
          <span>已选条件</span>
          <div className="collection-empty-text">{emptyText}</div>
          <span />
        </div>
      )}
      {(groups || []).map(group => (
        <div className="pgy-find-filter-section" key={group.section}>
          <div className="pgy-find-filter-section-label">{group.section}</div>
          <div className="pgy-find-filter-section-body">
            <div className="pgy-find-filter-row">
              <div className="pgy-find-filter-row-label">筛选项</div>
              <div className="pgy-find-filter-row-options">
                {(group.fields || []).map(field => renderOptionToken(optionByField.get(field)))}
              </div>
            </div>
          </div>
        </div>
      ))}
      {extraSelected.length > 0 && (
        <div className="pgy-find-filter-section">
          <div className="pgy-find-filter-section-label">AI 生成</div>
          <div className="pgy-find-filter-section-body">
            <div className="pgy-find-filter-row">
              <div className="pgy-find-filter-row-label">补充条件</div>
              <div className="pgy-find-filter-row-options">
                {extraSelected.map(item => (
                  <button
                    key={hardFilterKey(item)}
                    type="button"
                    className="pgy-find-filter-token is-active"
                    onClick={() => removeByIdentity(item)}
                    title={hardFilterLabel(item)}
                  >
                    <span>{hardFilterLabel(item)}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
