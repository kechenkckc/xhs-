import React from 'react';

function TabBar({ tabs = [], activeTab, onChange }) {
  return (
    <div className="tab-bar">
      {tabs.map((tab) => (
        <div
          key={tab.key}
          className={`tab-item ${activeTab === tab.key ? 'tab-item-active' : ''}`}
          onClick={() => onChange && onChange(tab.key)}
        >
          {tab.icon && <span className="tab-item-icon">{tab.icon}</span>}
          <span className="tab-item-label">{tab.label}</span>
          {tab.count !== undefined && (
            <span className="tab-item-count">{tab.count}</span>
          )}
        </div>
      ))}
    </div>
  );
}

export default TabBar;
