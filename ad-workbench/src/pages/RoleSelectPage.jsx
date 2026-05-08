import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Lightbulb, Zap, Radio, BarChart3, Shield, ArrowRight } from 'lucide-react';

const roles = [
  {
    key: 'planner',
    name: '策划',
    icon: Lightbulb,
    description: '舆情洞察、Brief 解析、创意策略',
    color: '#8B5CF6',
    subtleBg: 'rgba(139, 92, 246, 0.12)',
  },
  {
    key: 'executor',
    name: '执行',
    icon: Zap,
    description: '需求接入、Agent 编排、任务跟进',
    color: '#06B6D4',
    subtleBg: 'rgba(6, 182, 212, 0.12)',
  },
  {
    key: 'media',
    name: '媒介',
    icon: Radio,
    description: '达人建联、投放追踪、预算优化',
    color: '#EC4899',
    subtleBg: 'rgba(236, 72, 153, 0.12)',
  },
  {
    key: 'manager',
    name: '管理层',
    icon: BarChart3,
    description: '全局总览、KPI 监控、风险分布',
    color: '#3B82F6',
    subtleBg: 'rgba(59, 130, 246, 0.12)',
  },
  {
    key: 'admin',
    name: '超级管理员',
    icon: Shield,
    description: '账号权限、Agent 编排、审计日志',
    color: '#F59E0B',
    subtleBg: 'rgba(245, 158, 11, 0.12)',
  },
];

export default function RoleSelectPage() {
  const navigate = useNavigate();

  const handleSelect = (roleKey) => {
    navigate(`/workbench/${roleKey}`);
  };

  return (
    <div className="role-select-page">
      {/* 标题区域 */}
      <h2>选择你的工作台</h2>
      <p className="role-subtitle">
        不同岗位看到不同视图，但共享同一份项目数据
      </p>

      {/* 角色卡片网格：前 3 个一行，后 2 个居中 */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 'var(--space-5)',
          maxWidth: 960,
          width: '100%',
          position: 'relative',
          zIndex: 1,
        }}
      >
        {/* 第一行：3 列 */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 'var(--space-5)',
            width: '100%',
          }}
        >
          {roles.slice(0, 3).map((role) => {
            const IconComponent = role.icon;
            return (
              <div
                key={role.key}
                className="role-card"
                onClick={() => handleSelect(role.key)}
                style={{ borderColor: 'var(--border-primary)' }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = role.color;
                  e.currentTarget.style.boxShadow = `0 8px 32px ${role.color}25`;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--border-primary)';
                  e.currentTarget.style.boxShadow = 'none';
                }}
              >
                {/* 角色图标 */}
                <div
                  className="role-icon"
                  style={{
                    backgroundColor: role.subtleBg,
                    color: role.color,
                  }}
                >
                  <IconComponent size={28} />
                </div>

                {/* 角色名称 */}
                <div className="role-name">{role.name}</div>

                {/* 角色描述 */}
                <div className="role-desc">{role.description}</div>

                {/* 进入按钮 */}
                <button
                  className="btn btn-sm"
                  style={{
                    marginTop: 'var(--space-5)',
                    backgroundColor: role.subtleBg,
                    color: role.color,
                    border: `1px solid transparent`,
                    borderRadius: 'var(--radius-md)',
                    fontSize: 'var(--text-sm)',
                    fontWeight: 500,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 'var(--space-1)',
                    transition: 'all 0.2s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = role.color;
                    e.currentTarget.style.color = '#ffffff';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = role.subtleBg;
                    e.currentTarget.style.color = role.color;
                  }}
                >
                  进入
                  <ArrowRight size={14} />
                </button>
              </div>
            );
          })}
        </div>

        {/* 第二行：2 列居中 */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: 'var(--space-5)',
            width: '66.67%',
          }}
        >
          {roles.slice(3, 5).map((role) => {
            const IconComponent = role.icon;
            return (
              <div
                key={role.key}
                className="role-card"
                onClick={() => handleSelect(role.key)}
                style={{ borderColor: 'var(--border-primary)' }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = role.color;
                  e.currentTarget.style.boxShadow = `0 8px 32px ${role.color}25`;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--border-primary)';
                  e.currentTarget.style.boxShadow = 'none';
                }}
              >
                {/* 角色图标 */}
                <div
                  className="role-icon"
                  style={{
                    backgroundColor: role.subtleBg,
                    color: role.color,
                  }}
                >
                  <IconComponent size={28} />
                </div>

                {/* 角色名称 */}
                <div className="role-name">{role.name}</div>

                {/* 角色描述 */}
                <div className="role-desc">{role.description}</div>

                {/* 进入按钮 */}
                <button
                  className="btn btn-sm"
                  style={{
                    marginTop: 'var(--space-5)',
                    backgroundColor: role.subtleBg,
                    color: role.color,
                    border: '1px solid transparent',
                    borderRadius: 'var(--radius-md)',
                    fontSize: 'var(--text-sm)',
                    fontWeight: 500,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 'var(--space-1)',
                    transition: 'all 0.2s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = role.color;
                    e.currentTarget.style.color = '#ffffff';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = role.subtleBg;
                    e.currentTarget.style.color = role.color;
                  }}
                >
                  进入
                  <ArrowRight size={14} />
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
