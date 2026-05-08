import React from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';

const colorMap = {
  blue: 'stat-card-icon-blue',
  green: 'stat-card-icon-green',
  amber: 'stat-card-icon-amber',
  red: 'stat-card-icon-red',
  purple: 'stat-card-icon-purple',
  cyan: 'stat-card-icon-cyan',
  pink: 'stat-card-icon-pink',
};

function StatCard({ title, value, change, changeLabel, icon: Icon, color = 'blue', subtitle }) {
  const isPositive = change >= 0;

  return (
    <div className="stat-card">
      <div className="stat-card-header">
        <div className={`stat-card-icon ${colorMap[color] || colorMap.blue}`}>
          {Icon && <Icon size={20} />}
        </div>
        {change !== undefined && (
          <div className={`stat-card-change ${isPositive ? 'stat-card-change-up' : 'stat-card-change-down'}`}>
            {isPositive ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
            <span>{isPositive ? '+' : ''}{change}%</span>
            {changeLabel && <span className="stat-card-change-label">{changeLabel}</span>}
          </div>
        )}
      </div>
      <div className="stat-card-value">{value}</div>
      <div className="stat-card-footer">
        <div className="stat-card-title">{title}</div>
        {subtitle && <div className="stat-card-subtitle">{subtitle}</div>}
      </div>
    </div>
  );
}

export default StatCard;
