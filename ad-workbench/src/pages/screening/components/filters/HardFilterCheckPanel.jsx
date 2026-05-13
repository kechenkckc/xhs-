import React, { useMemo } from 'react';
import { X } from 'lucide-react';
import { hardFilterKey, hardFilterLabel } from '../../constants/screeningConstants';
import { normalizeHardFilterItem } from '../../utils/screeningPlan';

const hardFilterIdentityKey = (item = {}) => item.pgyField || item.feishuField || item.field || hardFilterKey(item);

const defaultGroups = [
  { section: '预算与画像', fields: ['合作报价', '粉丝年龄'] },
  { section: '效率指标', fields: ['预估阅读单价', '预估互动单价'] },
  { section: '入库与风控', fields: ['蒲公英链接', '限流风险'] },
];

export function HardFilterCheckPanel({ filters = [], options = [], onChange, groups = defaultGroups, emptyText = '暂无筛选条件' }) {
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

  const toggleOption = (option = {}) => {
    const key = hardFilterIdentityKey(option);
    if (selectedIdentitySet.has(key)) {
      onChange?.(selectedFilters.filter(item => hardFilterIdentityKey(item) !== key));
      return;
    }
    onChange?.([...selectedFilters, normalizeHardFilterItem(option)]);
  };

  const renderOptionToken = (option) => {
    if (!option) return null;
    const active = selectedIdentitySet.has(hardFilterIdentityKey(option));
    return (
      <button
        key={hardFilterIdentityKey(option)}
        type="button"
        className={`pgy-find-filter-token ${active ? 'is-active' : ''}`}
        onClick={() => toggleOption(option)}
        title={hardFilterLabel(option)}
      >
        <span>{option.label || hardFilterLabel(option)}</span>
      </button>
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
