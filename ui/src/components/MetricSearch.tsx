import React, { useState, useMemo } from 'react';
import { Plus, Search } from 'lucide-react';
import './MetricSearch.css';

interface Metric {
  key: string;
  name: string;
}

interface MetricSearchProps {
  availableMetrics: Metric[];
  selectedMetrics: string[];
  onAddMetric: (metricKey: string) => void;
}

const MetricSearch: React.FC<MetricSearchProps> = ({ availableMetrics, selectedMetrics, onAddMetric }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [isFocused, setIsFocused] = useState(false);

  const filteredMetrics = useMemo(() => {
    const search = searchTerm.toLowerCase();
    if (!search && isFocused) {
      return availableMetrics.filter(metric => !selectedMetrics.includes(metric.key)).slice(0, 5);
    }
    if (!searchTerm) return [];
    return availableMetrics
      .filter(
        (metric) =>
          (metric.name.toLowerCase().includes(search) || metric.key.toLowerCase().includes(search)) &&
          !selectedMetrics.includes(metric.key)
      )
      .slice(0, 5);
  }, [searchTerm, availableMetrics, selectedMetrics, isFocused]);

  const handleAdd = (metricKey: string) => {
    onAddMetric(metricKey);
    setSearchTerm('');
  };

  return (
    <div className="metric-search">
      <div className="search-bar">
        <Search size={14} className="search-icon" />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setTimeout(() => setIsFocused(false), 200)}
          placeholder="Search for a metric..."
          className="metric-input"
        />
        {searchTerm && (
          <button className="add-manual-btn" onClick={() => handleAdd(searchTerm)}>
            <Plus size={14} />
          </button>
        )}
      </div>
      {filteredMetrics.length > 0 && (
        <div className="metric-dropdown">
          {filteredMetrics.map((metric) => (
            <button key={metric.key} className="dropdown-item" onClick={() => handleAdd(metric.key)}>
              <span className="item-key">{metric.key}</span>
              <span className="item-name">{metric.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default MetricSearch;
