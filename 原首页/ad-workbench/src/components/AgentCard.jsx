import React from 'react';
import { Bot, Clock } from 'lucide-react';

const statusConfig = {
  running: { className: 'agent-status-running', label: '运行中' },
  idle: { className: 'agent-status-idle', label: '空闲' },
  error: { className: 'agent-status-error', label: '异常' },
  completed: { className: 'agent-status-completed', label: '已完成' },
};

function AgentCard({ name, type, status = 'idle', description, lastRun, output, icon: Icon }) {
  const config = statusConfig[status] || statusConfig.idle;

  return (
    <div className="agent-card">
      <div className="agent-card-header">
        <div className="agent-card-info">
          <div className="agent-card-icon">
            {Icon ? <Icon size={20} /> : <Bot size={20} />}
          </div>
          <div>
            <div className="agent-card-name">{name}</div>
            {type && <div className="agent-card-type">{type}</div>}
          </div>
        </div>
        <div className={`agent-status ${config.className}`}>
          <span className="agent-status-dot" />
          <span className="agent-status-label">{config.label}</span>
        </div>
      </div>
      {description && <div className="agent-card-description">{description}</div>}
      {lastRun && (
        <div className="agent-card-meta">
          <Clock size={12} />
          <span>最后运行: {lastRun}</span>
        </div>
      )}
      {output && (
        <div className="agent-card-output">
          <span className="agent-card-output-label">输出摘要</span>
          <span className="agent-card-output-text">{output}</span>
        </div>
      )}
    </div>
  );
}

export default AgentCard;
