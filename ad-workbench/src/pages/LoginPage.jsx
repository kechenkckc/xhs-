import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock, User, Eye, EyeOff, ArrowRight, CheckCircle2 } from 'lucide-react';

const principles = [
  '同项目同数据，不同岗位不同视图',
  '前台讲业务语言，不暴露技术概念',
  '优先做岗位闭环，不先堆大而全功能',
];

export default function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  const validate = () => {
    const newErrors = {};
    if (!username.trim()) {
      newErrors.username = '请输入用户名';
    }
    if (!password.trim()) {
      newErrors.password = '请输入密码';
    } else if (password.length < 6) {
      newErrors.password = '密码至少 6 位';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleLogin = (e) => {
    e.preventDefault();
    if (!validate()) return;
    setLoading(true);
    // 模拟登录延迟
    setTimeout(() => {
      setLoading(false);
      navigate('/select-role');
    }, 800);
  };

  return (
    <div className="login-page">
      {/* 左侧品牌展示区 60% */}
      <div
        style={{
          flex: '0 0 60%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          padding: 'var(--space-12)',
          position: 'relative',
          zIndex: 1,
          background:
            'linear-gradient(135deg, rgba(59,130,246,0.08) 0%, rgba(139,92,246,0.06) 50%, rgba(6,182,212,0.04) 100%)',
          borderRight: '1px solid var(--border-subtle)',
        }}
      >
        {/* 产品名 */}
        <h1
          style={{
            fontFamily: 'var(--font-sans)',
            fontSize: '28px',
            fontWeight: 700,
            color: 'var(--text-primary)',
            marginBottom: 'var(--space-3)',
            letterSpacing: 0,
          }}
        >
          AdFlow AI
        </h1>

        {/* 副标题 */}
        <p
          style={{
            fontSize: 'var(--text-md)',
            color: 'var(--text-secondary)',
            marginBottom: 'var(--space-12)',
            fontWeight: 400,
          }}
        >
          广告 AI 自动化工作台
        </p>

        {/* 3 条产品原则 */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-5)',
            maxWidth: 420,
          }}
        >
          {principles.map((text, index) => (
            <div
              key={index}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-4)',
              }}
            >
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 'var(--radius-full)',
                  backgroundColor: 'var(--accent-blue-subtle)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <CheckCircle2
                  size={18}
                  style={{ color: 'var(--accent-blue)' }}
                />
              </div>
              <span
                style={{
                  fontSize: 'var(--text-md)',
                  color: 'var(--text-secondary)',
                  lineHeight: 'var(--leading-relaxed)',
                }}
              >
                {text}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* 右侧登录表单 40% */}
      <div
        style={{
          flex: '0 0 40%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 'var(--space-8)',
          position: 'relative',
          zIndex: 1,
        }}
      >
        <div className="login-card">
          <div className="login-logo">
            <div className="logo-icon">A</div>
            <span className="logo-text">AdFlow AI</span>
          </div>

          <h2>登录账号</h2>
          <p className="login-subtitle">请输入你的账号信息以继续</p>

          <form onSubmit={handleLogin}>
            {/* 用户名 */}
            <div className="form-group">
              <label className="form-label" htmlFor="username">
                用户名
              </label>
              <div style={{ position: 'relative' }}>
                <User
                  size={16}
                  style={{
                    position: 'absolute',
                    left: 'var(--space-3)',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: 'var(--text-muted)',
                    pointerEvents: 'none',
                  }}
                />
                <input
                  id="username"
                  type="text"
                  className="input-field"
                  placeholder="请输入用户名"
                  value={username}
                  onChange={(e) => {
                    setUsername(e.target.value);
                    if (errors.username) {
                      setErrors((prev) => ({ ...prev, username: '' }));
                    }
                  }}
                  style={{ paddingLeft: 'var(--space-8)' }}
                />
              </div>
              {errors.username && (
                <span
                  style={{
                    fontSize: 'var(--text-xs)',
                    color: 'var(--accent-red)',
                    marginTop: 'var(--space-1)',
                    display: 'block',
                  }}
                >
                  {errors.username}
                </span>
              )}
            </div>

            {/* 密码 */}
            <div className="form-group">
              <label className="form-label" htmlFor="password">
                密码
              </label>
              <div style={{ position: 'relative' }}>
                <Lock
                  size={16}
                  style={{
                    position: 'absolute',
                    left: 'var(--space-3)',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: 'var(--text-muted)',
                    pointerEvents: 'none',
                  }}
                />
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  className="input-field"
                  placeholder="请输入密码"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (errors.password) {
                      setErrors((prev) => ({ ...prev, password: '' }));
                    }
                  }}
                  style={{
                    paddingLeft: 'var(--space-8)',
                    paddingRight: 'var(--space-8)',
                  }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{
                    position: 'absolute',
                    right: 'var(--space-3)',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    padding: 2,
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {errors.password && (
                <span
                  style={{
                    fontSize: 'var(--text-xs)',
                    color: 'var(--accent-red)',
                    marginTop: 'var(--space-1)',
                    display: 'block',
                  }}
                >
                  {errors.password}
                </span>
              )}
            </div>

            {/* 记住我 */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-2)',
                marginBottom: 'var(--space-4)',
              }}
            >
              <input
                type="checkbox"
                id="remember"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                style={{
                  width: 16,
                  height: 16,
                  accentColor: 'var(--accent-blue)',
                  cursor: 'pointer',
                }}
              />
              <label
                htmlFor="remember"
                style={{
                  fontSize: 'var(--text-sm)',
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                  userSelect: 'none',
                }}
              >
                记住我
              </label>
            </div>

            {/* 登录按钮 */}
            <button
              type="submit"
              className="btn btn-primary login-btn"
              disabled={loading}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 'var(--space-2)',
                padding: 'var(--space-3) var(--space-4)',
                width: '100%',
                fontSize: 'var(--text-md)',
                fontWeight: 600,
                borderRadius: 'var(--radius-md)',
                transition: 'all 0.2s ease',
              }}
              onMouseEnter={(e) => {
                if (!loading) {
                  e.currentTarget.style.backgroundColor = '#2563EB';
                  e.currentTarget.style.borderColor = '#2563EB';
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--accent-blue)';
                e.currentTarget.style.borderColor = 'var(--accent-blue)';
              }}
            >
              {loading ? (
                <span>登录中...</span>
              ) : (
                <>
                  <span>登录</span>
                  <ArrowRight size={18} />
                </>
              )}
            </button>
          </form>

          <div className="login-footer">
            <span>还没有账号？</span>{' '}
            <a href="#register" onClick={(e) => e.preventDefault()}>
              联系管理员
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
