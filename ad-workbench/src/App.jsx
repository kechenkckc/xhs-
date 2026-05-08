import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

const LoginPage = lazy(() => import('./pages/LoginPage'));
const RoleSelectPage = lazy(() => import('./pages/RoleSelectPage'));
const WorkbenchLayout = lazy(() => import('./pages/WorkbenchLayout'));

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        background: '#0B0E11',
        color: '#8B95A5',
        fontSize: '14px',
        fontFamily: "'DM Sans', sans-serif"
      }}>加载中...</div>}>
        <Routes>
          <Route path="/" element={<LoginPage />} />
          <Route path="/select-role" element={<RoleSelectPage />} />
          <Route path="/workbench/screening" element={<Navigate to="/workbench/screening/projects" replace />} />
          <Route path="/workbench/:role" element={<WorkbenchLayout />} />
          <Route path="/workbench/:role/:tab" element={<WorkbenchLayout />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

export default App;
