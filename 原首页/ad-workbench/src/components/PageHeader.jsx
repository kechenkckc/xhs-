import React from 'react';
import { ChevronRight } from 'lucide-react';

function PageHeader({ title, subtitle, breadcrumbs = [], actions }) {
  return (
    <div className="page-header">
      <div className="page-header-left">
        {breadcrumbs.length > 0 && (
          <nav className="page-header-breadcrumbs">
            {breadcrumbs.map((item, index) => (
              <React.Fragment key={item.path ?? index}>
                {index > 0 && <ChevronRight size={14} className="breadcrumb-separator" />}
                <span
                  className={`breadcrumb-item ${index === breadcrumbs.length - 1 ? 'breadcrumb-item-active' : ''}`}
                >
                  {item.label}
                </span>
              </React.Fragment>
            ))}
          </nav>
        )}
        <h1 className="page-header-title">{title}</h1>
        {subtitle && <p className="page-header-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="page-header-actions">{actions}</div>}
    </div>
  );
}

export default PageHeader;
