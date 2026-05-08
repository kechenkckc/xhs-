import React from 'react';

const colorMap = {
  blue: 'progress-fill-blue',
  green: 'progress-fill-green',
  amber: 'progress-fill-amber',
  red: 'progress-fill-red',
  purple: 'progress-fill-purple',
  cyan: 'progress-fill-cyan',
  pink: 'progress-fill-pink',
};

function ProgressBar({ value = 0, color = 'blue', size = 'md', showLabel = false }) {
  const clampedValue = Math.min(100, Math.max(0, value));

  return (
    <div className={`progress-bar progress-bar-${size}`}>
      <div
        className={`progress-fill ${colorMap[color] || colorMap.blue}`}
        style={{ width: `${clampedValue}%` }}
      />
      {showLabel && (
        <span className="progress-label">{Math.round(clampedValue)}%</span>
      )}
    </div>
  );
}

export default ProgressBar;
