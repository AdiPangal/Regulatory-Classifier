import { useState, useEffect } from 'react';
import { getAuditHistory } from '../services/api';
import '../styles/audit.css';

const AuditTrailPage = () => {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    event_type: '',
    action: '',
    document_id: '',
    limit: 100
  });

  useEffect(() => {
    loadAuditHistory();
  }, [filters]);

  const loadAuditHistory = async () => {
    setLoading(true);
    try {
      const data = await getAuditHistory(filters);
      setRecords(data.records || []);
    } catch (error) {
      console.error('Failed to load audit history:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters({ ...filters, [key]: value });
  };

  return (
    <div className="audit-page">
      <div className="audit-container">
        <h1 className="audit-title">Audit Trail</h1>
        
        <div className="audit-filters">
          <input
            type="text"
            placeholder="Event Type"
            value={filters.event_type}
            onChange={(e) => handleFilterChange('event_type', e.target.value)}
          />
          <input
            type="text"
            placeholder="Action"
            value={filters.action}
            onChange={(e) => handleFilterChange('action', e.target.value)}
          />
          <input
            type="text"
            placeholder="Document ID"
            value={filters.document_id}
            onChange={(e) => handleFilterChange('document_id', e.target.value)}
          />
          <button onClick={loadAuditHistory}>Refresh</button>
        </div>

        {loading ? (
          <div className="loading-state">Loading audit records...</div>
        ) : (
          <div className="audit-table-container">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Event Type</th>
                  <th>Action</th>
                  <th>Document ID</th>
                  <th>User ID</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {records.map((record) => (
                  <tr key={record.id}>
                    <td>{new Date(record.timestamp).toLocaleString()}</td>
                    <td>{record.event_type}</td>
                    <td>{record.action}</td>
                    <td className="document-id-cell">{record.document_id || 'N/A'}</td>
                    <td>{record.user_id || 'N/A'}</td>
                    <td className="details-cell">
                      <pre>{JSON.stringify(record.details, null, 2)}</pre>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {records.length === 0 && (
              <p className="no-records">No audit records found.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default AuditTrailPage;

