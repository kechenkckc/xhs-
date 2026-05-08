import React from 'react';

const colorMap = {
  blue: 'kpi-card-blue',
  green: 'kpi-card-green',
  amber: 'kpi-card-amber',
  red: 'kpi-card-red',
  purple: 'kpi-card-purple',
  cyan: 'kpi-card-cyan',
  pink: 'kpi-card-pink',
};

function buildPolylinePoints(trend) {
  if (!trend || trend.length < 2) return '';

  const values = trend.map((d) => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const width = 120;
  const height = 40;
  const padding = 2;

  return trend
    .map((d, i) => {
      const x = padding + (i / (trend.length - 1)) * (width - padding * 2);
      const y = height - padding - ((d.value - min) / range) * (height - padding * 2);
      return `${x},${y}`;
    })
    .join(' ');
}

function KpiCard({ title, value, unit, target, current, trend = [], color = 'blue' }) {
  const achievementRate = target ? Math.round((current / target) * 100) : 0;
  const polylinePoints = buildPolylinePoints(trend);

  return (
    <div className={`kpi-card ${colorMap[color] || colorMap.blue}`}>
      <div className="kpi-card-header">
        <span className="kpi-card-title">{title}</span>
        {unit && <span className="kpi-card-unit">{unit}</span>}
      </div>
      <div className="kpi-card-value">{value}</div>
      {target !== undefined && current !== undefined && (
        <div className="kpi-card-achievement">
          <span className="kpi-card-achievement-label">达成率</span>
          <span className="kpi-card-achievement-value">{achievementRate}%</span>
        </div>
      )}
      {trend.length >= 2 && (
        <div className="kpi-card-trend">
          <svg width="120" height="40" viewBox="0 0 120 40" preserveAspectRatio="none">
            <polyline
              points={polylinePoints}
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      )}
    </div>
  );
}

export default KpiCard;
