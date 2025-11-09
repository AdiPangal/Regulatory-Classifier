import '../styles/results.css';

const ClassificationCard = ({ classification, confidence }) => {
  const normalizeClassification = (classification) => {
    if (!classification) return 'Public';
    const lower = classification.toLowerCase().trim();
    // Note: "Unsafe" is NOT a classification - it's a separate safety flag
    // Only normalize to: Public, Confidential, or Highly Sensitive
    if (lower.includes('highly sensitive') || lower.includes('highly-sensitive')) return 'Highly Sensitive';
    if (lower.includes('confidential')) return 'Confidential';
    if (lower.includes('public') || lower.includes('not highly sensitive') || lower.includes('not highly-sensitive')) return 'Public';
    return 'Public'; // Default
  };

  const getClassificationColor = (classification) => {
    const normalized = normalizeClassification(classification);
    switch (normalized?.toLowerCase()) {
      case 'public':
        return 'classification-public';
      case 'confidential':
        return 'classification-confidential';
      case 'highly sensitive':
        return 'classification-highly-sensitive';
      default:
        return 'classification-default';
    }
  };

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.8) return 'confidence-high';
    if (confidence >= 0.5) return 'confidence-medium';
    return 'confidence-low';
  };

  return (
    <div className={`classification-card ${getClassificationColor(classification)}`}>
      <div className="classification-header">
        <h2 className="classification-title">Classification</h2>
        <span className={`classification-badge ${getClassificationColor(classification)}`}>
          {normalizeClassification(classification) || 'Unknown'}
        </span>
      </div>
      <div className="confidence-section">
        <span className="confidence-label">Confidence:</span>
        <div className="confidence-bar-container">
          <div 
            className={`confidence-bar ${getConfidenceColor(confidence)}`}
            style={{ width: `${(confidence || 0) * 100}%` }}
          ></div>
        </div>
        <span className="confidence-value">{(confidence * 100).toFixed(1)}%</span>
      </div>
    </div>
  );
};

export default ClassificationCard;

