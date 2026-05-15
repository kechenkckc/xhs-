import React, { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
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
import {
  getPgySelectedItems,
  makePgyFilterItem,
} from '../../utils/pgyFilters';
import { PGY_SINGLE_VALUE_CONTROLS } from '../../constants/pgyConstants';
import { CONTROL_TYPE_LABELS } from '../../constants/screeningConstants';

const POPOVER_MARGIN = 12;

export function PgyFilterPopover({ meta, filters = [], anchorEl, initialSubField = '', onApply, onClear, onClose }) {
  const popoverRef = useRef(null);
  const [popoverStyle, setPopoverStyle] = useState(null);
  const selectedItems = useMemo(() => getPgySelectedItems(filters, meta.field)
    .filter(item => !initialSubField || [item.goal, item.parent_value, item.parentValue, item.sub_field, item.subField].includes(initialSubField)), [filters, meta.field, initialSubField]);
  const defaultSubField = initialSubField || selectedItems[0]?.sub_field || meta.sub_fields?.[0] || '';
  const [subField, setSubField] = useState(defaultSubField);
  const optionGroups = meta.option_groups || meta.optionGroups || [];
  const [activeGroup, setActiveGroup] = useState(() => (
    initialSubField || selectedItems[0]?.sub_field || optionGroups[0]?.label || ''
  ));
  const [draftItems, setDraftItems] = useState(() => selectedItems.map(item => {
    const itemSubField = item.sub_field || item.subField || item.goal || item.parent_value || item.parentValue || '';
    const prefix = itemSubField ? `${itemSubField}：` : '';
    const value = prefix && String(item.value).startsWith(prefix) ? String(item.value).slice(prefix.length) : item.value;
    return { value, subField: itemSubField };
  }));
  const [customMin, setCustomMin] = useState('');
  const [customMax, setCustomMax] = useState('');
  const [inputText, setInputText] = useState('');
  const isSingle = PGY_SINGLE_VALUE_CONTROLS.has(meta.control_type);
  const isRange = /(range|percent|cpm|单价|报价|订单数)/i.test(`${meta.control_type} ${meta.field}`);
  const isSearchable = ['brand_search_recommendation', 'searchable_multi_select_with_exclude'].includes(meta.control_type);
  const isRegionCascade = ['地域', '粉丝地域'].includes(meta.field) && meta.control_type === 'three_level_cascade_checkbox_popover';
  const hasOptionGroups = optionGroups.length > 0;
  const [activeRegionCountry, setActiveRegionCountry] = useState(() => {
    const firstSelected = selectedItems[0]?.sub_field || selectedItems[0]?.subField || selectedItems[0]?.country || '';
    return firstSelected || optionGroups[0]?.label || '中国';
  });
  const [activeRegionProvince, setActiveRegionProvince] = useState(() => {
    const firstSelected = selectedItems[0]?.province || selectedItems[0]?.sub_field || selectedItems[0]?.subField || '';
    return firstSelected;
  });
  const activeCountryGroup = optionGroups.find(group => group.label === activeRegionCountry) || optionGroups[0] || {};
  const activeProvinceGroups = activeCountryGroup.options || [];
  const activeProvinceGroup = activeProvinceGroups.find(group => group.label === activeRegionProvince) || activeProvinceGroups[0] || {};
  const activeGroupOptions = optionGroups.find(group => group.label === activeGroup)?.options || optionGroups[0]?.options || [];
  const currentDraftValues = draftItems
    .filter(item => (item.subField || '') === ((hasOptionGroups ? activeGroup : subField) || ''))
    .map(item => item.value);
  const draftKey = (item) => `${item.subField || ''}|${item.value || ''}`;
  const canApply = draftItems.some(item => item.value && item.value !== '不限');

  const currentSubField = () => (hasOptionGroups ? activeGroup : subField);
  const replaceCurrentSubFieldItems = (items, nextItem) => {
    const nextKey = draftKey(nextItem);
    const nextSubField = currentSubField() || '';
    const otherItems = (items || []).filter(item => (item.subField || '') !== nextSubField);
    return [...otherItems, nextItem].filter((item, index, all) => all.findIndex(next => draftKey(next) === draftKey(item)) === index);
  };

  const toggleDraftValue = (value) => {
    if (!value || value === '不限') {
      setDraftItems(old => old.filter(item => (item.subField || '') !== (currentSubField() || '')));
      return;
    }
    setDraftItems(old => {
      const nextItem = { value, subField: currentSubField() };
      const nextKey = draftKey(nextItem);
      const exists = old.some(item => draftKey(item) === nextKey);
      if (isSingle) {
        return exists
          ? old.filter(item => (item.subField || '') !== (currentSubField() || ''))
          : replaceCurrentSubFieldItems(old, nextItem);
      }
      return exists ? old.filter(item => draftKey(item) !== nextKey) : [...old, nextItem];
    });
  };

  const addInputValue = () => {
    const value = inputText.trim();
    if (!value) return;
    setDraftItems(old => {
      const nextItem = { value, subField: currentSubField() };
      return old.some(item => draftKey(item) === draftKey(nextItem)) ? old : [...old, nextItem];
    });
    setInputText('');
  };

  const addRegionDraft = (value, path = {}) => {
    if (!value) return;
    setDraftItems(old => {
      const nextItem = { value, subField: path.country || '', ...path };
      return old.some(item => draftKey(item) === draftKey(nextItem)) ? old : [...old, nextItem];
    });
  };

  const removeRegionDraft = (value, path = {}) => {
    setDraftItems(old => old.filter(item => !(item.value === value && (!path.country || item.country === path.country))));
  };

  const toggleRegionCountry = (country) => {
    setActiveRegionCountry(country);
    const group = optionGroups.find(item => item.label === country);
    const firstProvince = group?.options?.[0]?.label || '';
    setActiveRegionProvince(firstProvince);
    if (!group?.options?.length) {
      const exists = draftItems.some(item => item.value === country && item.country === country);
      if (exists) removeRegionDraft(country, { country });
      else addRegionDraft(country, { country, level: 'country' });
    }
  };

  const toggleRegionProvince = (province) => {
    setActiveRegionProvince(province);
    const exists = draftItems.some(item => item.value === province && item.country === activeRegionCountry);
    if (exists) removeRegionDraft(province, { country: activeRegionCountry });
    else addRegionDraft(province, { country: activeRegionCountry, province, level: 'province' });
  };

  const toggleRegionCity = (city) => {
    const exists = draftItems.some(item => item.value === city && item.country === activeRegionCountry);
    if (exists) removeRegionDraft(city, { country: activeRegionCountry });
    else addRegionDraft(city, { country: activeRegionCountry, province: activeProvinceGroup.label, city, level: 'city' });
  };

  const addCustomRange = () => {
    const left = customMin.trim();
    const right = customMax.trim();
    if (!left && !right) return;
    const value = left && right ? `${left}～${right}` : left ? `${left}以上` : `${right}以下`;
    setDraftItems(old => {
      const nextItem = { value, subField: currentSubField() };
      const nextKey = draftKey(nextItem);
      if (isSingle) return replaceCurrentSubFieldItems(old, nextItem);
      return old.some(item => draftKey(item) === nextKey) ? old : [...old, nextItem];
    });
    setCustomMin('');
    setCustomMax('');
  };

  const buildAppliedItems = (items = draftItems) => items
      .filter(item => item.value && item.value !== '不限')
      .map(item => ({
        ...makePgyFilterItem(meta, item.value, item.subField),
        ...(isRegionCascade ? {
          country: item.country || item.subField || '',
          province: item.province || '',
          city: item.city || '',
          level: item.level || '',
        } : {}),
      }));

  const applyItems = (items = draftItems) => {
    const nextItems = buildAppliedItems(items);
    if (!nextItems.length) return;
    onApply?.(nextItems);
    onClose?.();
  };

  const addRangeOrApplyDraft = () => {
    const left = customMin.trim();
    const right = customMax.trim();
    if (!left && !right) {
      applyItems();
      return;
    }

    const value = left && right ? `${left}～${right}` : left ? `${left}以上` : `${right}以下`;
    const nextItem = { value, subField: currentSubField() };
    const nextItems = isSingle
      ? replaceCurrentSubFieldItems(draftItems, nextItem)
      : [...draftItems.filter(item => draftKey(item) !== draftKey(nextItem)), nextItem];
    setDraftItems(nextItems);
    setCustomMin('');
    setCustomMax('');
    applyItems(nextItems);
  };

  useLayoutEffect(() => {
    if (!anchorEl) return undefined;

    const updatePosition = () => {
      const anchorRect = anchorEl.getBoundingClientRect();
      const popoverRect = popoverRef.current?.getBoundingClientRect();
      const popoverWidth = popoverRect?.width || Math.min(380, window.innerWidth * 0.78);
      const popoverHeight = popoverRect?.height || Math.min(520, window.innerHeight - 150);
      const maxLeft = Math.max(POPOVER_MARGIN, window.innerWidth - popoverWidth - POPOVER_MARGIN);
      const preferredLeft = Math.min(anchorRect.left, maxLeft);
      const nextLeft = Math.max(POPOVER_MARGIN, preferredLeft);
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
  }, [anchorEl, meta.field, draftItems.length, hasOptionGroups, activeGroup, subField, isRegionCascade, activeRegionCountry, activeRegionProvince]);

  if (!anchorEl) return null;

  return createPortal(
    <div ref={popoverRef} className="pgy-find-filter-popover" style={popoverStyle || undefined}>
      <div className="pgy-find-filter-popover-head">
        <strong>{meta.field}</strong>
        <span>{CONTROL_TYPE_LABELS[meta.control_type] || meta.control_type}</span>
      </div>
      {meta.sub_fields?.length ? (
        <div className="pgy-find-subfield-tabs">
          {meta.sub_fields.map(item => (
            <button
              key={item}
              type="button"
              className={subField === item ? 'is-active' : ''}
              onClick={() => setSubField(item)}
            >
              {item}
            </button>
          ))}
        </div>
      ) : null}
      {isRegionCascade && (
        <div className="pgy-find-region-cascade">
          <div className="pgy-find-region-column">
            <div className="pgy-find-region-column-head">国家/地区</div>
            {optionGroups.map(group => {
              const selected = draftItems.some(item => item.country === group.label || item.value === group.label);
              return (
                <button
                  key={group.label}
                  type="button"
                  className={`${activeRegionCountry === group.label ? 'is-active' : ''} ${selected ? 'has-selected' : ''}`}
                  onClick={() => toggleRegionCountry(group.label)}
                >
                  <span>{group.label}</span>
                  {group.options?.length ? <ChevronRight size={14} /> : null}
                </button>
              );
            })}
          </div>
          <div className="pgy-find-region-column">
            <div className="pgy-find-region-column-head">省/市</div>
            {activeProvinceGroups.length ? activeProvinceGroups.map(group => {
              const selected = draftItems.some(item => item.country === activeRegionCountry && item.value === group.label);
              return (
                <label key={group.label} className={`pgy-find-filter-choice ${selected || activeRegionProvince === group.label ? 'is-active' : ''}`}>
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => toggleRegionProvince(group.label)}
                  />
                  <button type="button" onClick={() => setActiveRegionProvince(group.label)}>
                    <span>{group.label}</span>
                    {group.options?.length ? <ChevronRight size={14} /> : null}
                  </button>
                </label>
              );
            }) : (
              <div className="pgy-find-region-empty">该国家/地区无需二级选择</div>
            )}
          </div>
          <div className="pgy-find-region-column">
            <div className="pgy-find-region-column-head">市/区</div>
            {activeProvinceGroup.options?.length ? activeProvinceGroup.options.map(city => {
              const selected = draftItems.some(item => item.country === activeRegionCountry && item.value === city);
              return (
                <label key={city} className={`pgy-find-filter-choice ${selected ? 'is-active' : ''}`}>
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => toggleRegionCity(city)}
                  />
                  <span>{city}</span>
                </label>
              );
            }) : (
              <div className="pgy-find-region-empty">选择省/市后显示城市或区县</div>
            )}
          </div>
        </div>
      )}
      {!isRegionCascade && hasOptionGroups && (
        <div className="pgy-find-cascade-options">
          <div className="pgy-find-cascade-groups">
            {optionGroups.map(group => {
              const groupSelected = draftItems.some(item => item.subField === group.label);
              return (
                <button
                  key={group.label}
                  type="button"
                  className={`${activeGroup === group.label ? 'is-active' : ''} ${groupSelected ? 'has-selected' : ''}`}
                  onClick={() => setActiveGroup(group.label)}
                >
                  <span>{group.label}</span>
                  <ChevronRight size={14} />
                </button>
              );
            })}
          </div>
          <div className="pgy-find-cascade-values">
            {activeGroupOptions.map(value => {
              const checked = currentDraftValues.includes(value);
              return (
                <label key={`${activeGroup}-${value}`} className={`pgy-find-filter-choice ${checked ? 'is-active' : ''}`}>
                  <input
                    type={isSingle ? 'radio' : 'checkbox'}
                    checked={checked}
                    onChange={() => toggleDraftValue(value)}
                  />
                  <span>{value}</span>
                </label>
              );
            })}
          </div>
        </div>
      )}
      {isSearchable && (
        <div className="pgy-find-search-row">
          <input
            className="input-field"
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') {
                e.preventDefault();
                addInputValue();
              }
            }}
            placeholder={meta.field === '按博主粉丝推荐' ? '输入合作品牌或竞品品牌' : '输入品牌名称'}
          />
          <button type="button" className="btn btn-sm btn-secondary" onClick={addInputValue}>添加</button>
        </div>
      )}
      {!isRegionCascade && !hasOptionGroups && (
      <div className="pgy-find-filter-popover-options">
        {(meta.options || ['待选择']).map(value => {
          const checked = currentDraftValues.includes(value);
          return (
            <label key={value} className={`pgy-find-filter-choice ${checked ? 'is-active' : ''}`}>
              <input
                type={isSingle ? 'radio' : 'checkbox'}
                checked={checked}
                onChange={() => toggleDraftValue(value)}
              />
              <span>{value}</span>
            </label>
          );
        })}
      </div>
      )}
      {isRange && (
        <div className="pgy-find-custom-range">
          <input className="input-field" value={customMin} onChange={e => setCustomMin(e.target.value)} placeholder="最小值" />
          <span>至</span>
          <input className="input-field" value={customMax} onChange={e => setCustomMax(e.target.value)} placeholder="最大值" />
          <button type="button" className="btn btn-sm btn-secondary" disabled={!customMin.trim() && !customMax.trim() && !canApply} onClick={addRangeOrApplyDraft}>加入</button>
        </div>
      )}
      {draftItems.length > 0 && (
        <div className="pgy-find-draft-values">
          {draftItems.map(item => (
            <button key={draftKey(item)} type="button" onClick={() => setDraftItems(old => old.filter(next => draftKey(next) !== draftKey(item)))}>
              {isRegionCascade && item.country && item.country !== item.value ? `${item.country}：` : item.subField ? `${item.subField}：` : ''}{item.value}
              <X size={12} />
            </button>
          ))}
        </div>
      )}
      <div className="pgy-find-filter-popover-actions">
        <button type="button" onClick={() => { onClear?.(); onClose?.(); }}>重置</button>
        <button type="button" onClick={onClose}>取消</button>
        <button type="button" className="is-primary" disabled={!canApply} onClick={() => applyItems()}>添加条件</button>
      </div>
    </div>,
    document.body
  );
}
