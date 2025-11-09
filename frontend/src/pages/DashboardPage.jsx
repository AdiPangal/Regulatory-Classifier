import { useState, useEffect } from 'react';
import ClassificationChart from '../components/ClassificationChart';
import HITLStatsChart from '../components/HITLStatsChart';
import { getClassificationDistribution, getHITLFeedbackStats } from '../services/api';
import '../styles/dashboard.css';

const DashboardPage = () => {
  const [classificationData, setClassificationData] = useState(null);
  const [hitlData, setHITLData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dateRange, setDateRange] = useState({ start: null, end: null });

  useEffect(() => {
    loadData();
  }, [dateRange]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [classificationDist, hitlStats] = await Promise.all([
        getClassificationDistribution(dateRange.start, dateRange.end),
        getHITLFeedbackStats()
      ]);
      setClassificationData(classificationDist);
      setHITLData(hitlStats);
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="dashboard-page">
        <div className="loading-state">Loading dashboard...</div>
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      <div className="dashboard-container">
        <h1 className="dashboard-title">Dashboard & Statistics</h1>
        
        <div className="date-filter">
          <label>
            Start Date:
            <input
              type="date"
              value={dateRange.start || ''}
              onChange={(e) => setDateRange({ ...dateRange, start: e.target.value })}
            />
          </label>
          <label>
            End Date:
            <input
              type="date"
              value={dateRange.end || ''}
              onChange={(e) => setDateRange({ ...dateRange, end: e.target.value })}
            />
          </label>
          <button onClick={() => setDateRange({ start: null, end: null })}>
            Clear Filters
          </button>
        </div>

        <div className="charts-grid">
          <div className="chart-card">
            {classificationData && <ClassificationChart data={classificationData} />}
          </div>
          <div className="chart-card">
            {hitlData && <HITLStatsChart data={hitlData} />}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;

