import React from 'react';

function DataTable({ columns = [], data = [], onRowClick, emptyText = '暂无数据' }) {
  if (!data.length) {
    return (
      <div className="data-table">
        <div className="empty-state">
          <div className="empty-state-text">{emptyText}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="data-table">
      <div className="data-table-wrapper">
        <table className="data-table-inner">
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  style={col.width ? { width: col.width } : undefined}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, rowIndex) => (
              <tr
                key={row.id ?? rowIndex}
                className="data-table-row"
                onClick={() => onRowClick && onRowClick(row, rowIndex)}
                style={onRowClick ? { cursor: 'pointer' } : undefined}
              >
                {columns.map((col) => (
                  <td key={col.key}>
                    {col.render ? col.render(row[col.key], row, rowIndex) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default DataTable;
