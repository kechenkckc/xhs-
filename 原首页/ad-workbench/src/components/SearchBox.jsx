import React from 'react';
import { Search } from 'lucide-react';

function SearchBox({ placeholder = '搜索...', value, onChange, onSearch }) {
  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      onSearch && onSearch(value);
    }
  };

  const handleChange = (e) => {
    onChange && onChange(e.target.value);
  };

  return (
    <div className="search-box">
      <Search size={16} className="search-box-icon" />
      <input
        type="text"
        className="search-box-input"
        placeholder={placeholder}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
      />
    </div>
  );
}

export default SearchBox;
