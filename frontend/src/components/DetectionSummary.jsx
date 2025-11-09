import '../styles/results.css';

const DetectionSummary = ({ detectionSummary, safetyCheck, isLegible }) => {
  return (
    <div className="detection-summary">
      <h3 className="summary-title">Detection Summary</h3>
      <div className="summary-grid">
        <div className="summary-item">
          <span className="summary-label">PII Detected:</span>
          <span className="summary-value">{detectionSummary?.pii_count || 0}</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">Sensitive Keywords:</span>
          <span className="summary-value">{detectionSummary?.keyword_count || 0}</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">Safety Check:</span>
          <span className={`summary-value safety-${safetyCheck?.toLowerCase() || 'safe'}`}>
            {safetyCheck || 'Safe'}
          </span>
        </div>
        <div className="summary-item">
          <span className="summary-label">Document Legible:</span>
          <span className={`summary-value legible-${isLegible ? 'yes' : 'no'}`}>
            {isLegible ? 'Yes' : 'No'}
          </span>
        </div>
        {detectionSummary?.unsafe_pages && detectionSummary.unsafe_pages.length > 0 && (
          <div className="summary-item full-width">
            <span className="summary-label">Unsafe Pages:</span>
            <span className="summary-value">
              {detectionSummary.unsafe_pages.join(', ')}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

export default DetectionSummary;

