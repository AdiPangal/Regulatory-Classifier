import '../styles/loading.css';

const PreprocessingInfo = ({ preprocessing }) => {
  if (!preprocessing) return null;

  return (
    <div className="preprocessing-info">
      <h3 className="preprocessing-title">Pre-processing Results</h3>
      <div className="preprocessing-grid">
        <div className="preprocessing-item">
          <span className="preprocessing-label">Pages:</span>
          <span className="preprocessing-value">{preprocessing.pages || 0}</span>
        </div>
        <div className="preprocessing-item">
          <span className="preprocessing-label">Images:</span>
          <span className="preprocessing-value">{preprocessing.images || 0}</span>
        </div>
        <div className="preprocessing-item">
          <span className="preprocessing-label">Legible:</span>
          <span className={`preprocessing-value legible-${preprocessing.is_legible ? 'yes' : 'no'}`}>
            {preprocessing.is_legible ? 'Yes' : 'No'}
          </span>
        </div>
        {preprocessing.extraction_method && (
          <div className="preprocessing-item">
            <span className="preprocessing-label">Method:</span>
            <span className="preprocessing-value">{preprocessing.extraction_method}</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default PreprocessingInfo;

