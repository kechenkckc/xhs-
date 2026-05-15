import React from 'react';
import {
  getHardFilterOptionMeta,
  normalizeHardFilterValue,
  splitHardFilterValue,
} from '../../utils/pgyFilters';

const numberPattern = /-?\d+(?:\.\d+)?/g;
const escapeRegExp = (value = '') => String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

function conditionSymbol(condition = '<=') {
  const map = { '<=': '≤', '>=': '≥', '>': '>', '<': '<', '=': '=' };
  return map[condition] || condition || '≤';
}

function getNumberText(value = '') {
  const matches = String(value || '').match(numberPattern);
  return matches?.length ? matches[matches.length - 1] : '';
}

function formatNumberValue(filter = {}, option = {}, rawValue = '') {
  const numberValue = String(rawValue || '').trim();
  if (!numberValue) return '';
  const label = option.subField || filter.subField || filter.field || option.field || '';
  return `${label}${conditionSymbol(filter.condition || option.condition || '<=')}${numberValue}`;
}

function trimSubFieldPrefix(value = '', subField = '') {
  if (!subField) return value;
  return String(value || '').replace(new RegExp(`^${escapeRegExp(subField)}[：:]?`), '');
}

function getRangeParts(value = '', subField = '') {
  const cleanValue = trimSubFieldPrefix(value, subField);
  const matches = cleanValue.match(numberPattern) || [];
  return {
    min: matches[0] || '',
    max: matches[1] || '',
    preset: cleanValue,
  };
}

function formatRangeValue(option = {}, min = '', max = '') {
  const values = [String(min || '').trim(), String(max || '').trim()];
  const range = values[0] && values[1] ? `${values[0]}～${values[1]}` : (values[1] ? `${values[1]}以下` : values[0] ? `${values[0]}以上` : '');
  if (!range) return '';
  return option.subField ? `${option.subField}：${range}` : range;
}

function isSelectedPreset(value = '', option = {}) {
  const subField = option.subField || '';
  const cleanValue = trimSubFieldPrefix(value, subField);
  return option.presets?.includes(cleanValue);
}

function withoutPresetValue(value = '', option = {}) {
  return isSelectedPreset(value, option) ? '' : value;
}

function valueHint(filter = {}, option = {}) {
  if (filter.valueControl === 'number' || option.valueControl === 'number') {
    return `${option.subField || filter.subField || filter.field || '数值'}不高于多少`;
  }
  if (filter.valueControl === 'range' || option.valueControl === 'range') {
    return `${option.subField || filter.subField || filter.field || '区间'}范围`;
  }
  return '填写筛选内容';
}

export function HardFilterValueControl({ filter, onChange, presentation = 'editor' }) {
  const option = getHardFilterOptionMeta(filter) || {};
  const control = filter.valueControl || option.valueControl || '';
  const isPgyPresentation = presentation === 'pgy';
  if (control === 'none') {
    return <span className="standard-hard-filter-static">{isPgyPresentation ? '选中后生效，无需填写' : '无需填写'}</span>;
  }
  if (control === 'multi' && option.options?.length) {
    const selected = splitHardFilterValue(filter.value);
    return (
      <div className={isPgyPresentation ? 'pgy-find-filter-popover-options hard-filter-choice-grid' : 'standard-hard-filter-multi'}>
        {option.options.map(value => {
          const checked = selected.includes(value);
          return (
            <label key={value} className={isPgyPresentation ? `pgy-find-filter-choice ${checked ? 'is-active' : ''}` : ''}>
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
    const subField = option.subField || filter.subField || '';
    const rangeParts = getRangeParts(value, subField);
    const presetValue = option.presets?.includes(trimSubFieldPrefix(value, subField)) ? trimSubFieldPrefix(value, subField) : '';
    if (isPgyPresentation) {
      return (
        <div className="hard-filter-pgy-control">
          {option.presets?.length ? (
            <div className="hard-filter-control-block">
              <div className="hard-filter-control-title">选择网页档位</div>
              <div className="pgy-find-filter-popover-options hard-filter-choice-grid">
                {option.presets.map(item => {
                  const checked = presetValue === item;
                  return (
                    <label key={item} className={`pgy-find-filter-choice ${checked ? 'is-active' : ''}`}>
                      <input
                        type="radio"
                        checked={checked}
                        onChange={() => onChange({ value: option.subField ? `${option.subField}：${item}` : item })}
                      />
                      <span>{item}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          ) : null}
          <div className="hard-filter-control-block">
            <div className="hard-filter-control-title">自定义区间</div>
            <div className="pgy-find-custom-range hard-filter-inline-range">
              <input
                className="input-field"
                type="number"
                value={rangeParts.min}
                onChange={e => onChange({ value: formatRangeValue(option, e.target.value, rangeParts.max) })}
                placeholder="最小值"
              />
              <span>至</span>
              <input
                className="input-field"
                type="number"
                value={rangeParts.max}
                onChange={e => onChange({ value: formatRangeValue(option, rangeParts.min, e.target.value) })}
                placeholder="最大值"
              />
            </div>
            {withoutPresetValue(value, option) && <div className="hard-filter-current-value">当前：{value}</div>}
          </div>
        </div>
      );
    }
    return (
      <div className="standard-hard-filter-range">
        <select
          className="select-field"
          value={presetValue}
          onChange={e => onChange({ value: option.subField ? `${option.subField}：${e.target.value}` : e.target.value })}
        >
          <option value="">选择网页档位</option>
          {(option.presets || []).map(item => <option key={item} value={item}>{item}</option>)}
        </select>
        <div className="standard-hard-filter-number-pair">
          <input
            className="input-field"
            type="number"
            value={rangeParts.min}
            onChange={e => onChange({ value: formatRangeValue(option, e.target.value, rangeParts.max) })}
            placeholder="最小"
          />
          <span>至</span>
          <input
            className="input-field"
            type="number"
            value={rangeParts.max}
            onChange={e => onChange({ value: formatRangeValue(option, rangeParts.min, e.target.value) })}
            placeholder="最大"
          />
        </div>
      </div>
    );
  }
  if (control === 'number') {
    const numberText = getNumberText(filter.value);
    if (isPgyPresentation) {
      return (
        <div className="hard-filter-pgy-control">
          {option.presets?.length ? (
            <div className="hard-filter-control-block">
              <div className="hard-filter-control-title">选择网页档位</div>
              <div className="pgy-find-filter-popover-options hard-filter-choice-grid">
                {option.presets.map(item => {
                  const itemNumber = getNumberText(item);
                  const checked = numberText === itemNumber;
                  return (
                    <label key={item} className={`pgy-find-filter-choice ${checked ? 'is-active' : ''}`}>
                      <input
                        type="radio"
                        checked={checked}
                        onChange={() => onChange({ value: formatNumberValue(filter, option, itemNumber) })}
                      />
                      <span>{item}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          ) : null}
          <div className="hard-filter-control-block">
            <div className="hard-filter-control-title">自定义上限</div>
            <label className="hard-filter-single-number">
              <span>{valueHint(filter, option)}</span>
              <input
                className="input-field"
                type="number"
                value={numberText}
                onChange={e => onChange({ value: formatNumberValue(filter, option, e.target.value) })}
                placeholder={`输入数值${option.unit ? `（${option.unit}）` : ''}`}
              />
            </label>
            {filter.value && <div className="hard-filter-current-value">当前：{filter.value}</div>}
          </div>
        </div>
      );
    }
    return (
      <div className="standard-hard-filter-range">
        {option.presets?.length ? (
          <select
            className="select-field"
            value=""
            onChange={e => e.target.value && onChange({ value: formatNumberValue(filter, option, getNumberText(e.target.value)) })}
          >
            <option value="">网页档位</option>
            {option.presets.map(item => <option key={item} value={item}>{item}</option>)}
          </select>
        ) : null}
        <label className="standard-hard-filter-number-input">
          <span>{option.subField || filter.subField || filter.field}</span>
          <input
            className="input-field"
            type="number"
            value={numberText}
            onChange={e => onChange({ value: formatNumberValue(filter, option, e.target.value) })}
            placeholder={`数值${option.unit ? `（${option.unit}）` : ''}`}
          />
        </label>
      </div>
    );
  }
  if (isPgyPresentation) {
    return (
      <div className="hard-filter-control-block">
        <div className="hard-filter-control-title">填写条件</div>
        <input className="input-field" value={filter.value || ''} onChange={e => onChange({ value: e.target.value })} placeholder={valueHint(filter, option)} />
      </div>
    );
  }
  return <input className="input-field" value={filter.value || ''} onChange={e => onChange({ value: e.target.value })} placeholder="阈值或规则" />;
}
