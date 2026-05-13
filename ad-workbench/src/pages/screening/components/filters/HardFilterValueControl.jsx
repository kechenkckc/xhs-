import React from 'react';
import {
  getHardFilterOptionMeta,
  normalizeHardFilterValue,
  splitHardFilterValue,
} from '../../utils/pgyFilters';

export function HardFilterValueControl({ filter, onChange }) {
  const option = getHardFilterOptionMeta(filter) || {};
  const control = filter.valueControl || option.valueControl || '';
  if (control === 'none') {
    return <span className="standard-hard-filter-static">无需填写</span>;
  }
  if (control === 'multi' && option.options?.length) {
    const selected = splitHardFilterValue(filter.value);
    return (
      <div className="standard-hard-filter-multi">
        {option.options.map(value => {
          const checked = selected.includes(value);
          return (
            <label key={value}>
              <input
                type="checkbox"
                checked={checked}
                onChange={e => {
                  const next = e.target.checked
                    ? [...selected, value]
                    : selected.filter(item => item !== value);
                  onChange({ value: normalizeHardFilterValue(option, next) });
                }}
              />
              <span>{value}</span>
            </label>
          );
        })}
      </div>
    );
  }
  if (control === 'range') {
    const value = filter.value || '';
    return (
      <div className="standard-hard-filter-range">
        <select
          className="select-field"
          value={option.presets?.includes(value.replace(`${option.subField || ''}：`, '')) ? value.replace(`${option.subField || ''}：`, '') : ''}
          onChange={e => onChange({ value: option.subField ? `${option.subField}：${e.target.value}` : e.target.value })}
        >
          <option value="">选择网页档位</option>
          {(option.presets || []).map(item => <option key={item} value={item}>{item}</option>)}
        </select>
        <input className="input-field" value={value} onChange={e => onChange({ value: e.target.value })} placeholder="或填写自定义区间" />
      </div>
    );
  }
  if (control === 'number') {
    return (
      <div className="standard-hard-filter-range">
        {option.presets?.length ? (
          <select className="select-field" value="" onChange={e => e.target.value && onChange({ value: `${option.subField || filter.field}≤${e.target.value.replace('以下', '').replace('以上', '')}` })}>
            <option value="">网页档位</option>
            {option.presets.map(item => <option key={item} value={item}>{item}</option>)}
          </select>
        ) : null}
        <input className="input-field" value={filter.value || ''} onChange={e => onChange({ value: e.target.value })} placeholder={`填写数值${option.unit ? `（${option.unit}）` : ''}`} />
      </div>
    );
  }
  return <input className="input-field" value={filter.value || ''} onChange={e => onChange({ value: e.target.value })} placeholder="阈值或规则" />;
}
