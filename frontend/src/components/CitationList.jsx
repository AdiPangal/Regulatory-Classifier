import '../styles/results.css';

const CitationList = ({ citations = [] }) => {
  if (citations.length === 0) {
    return (
      <div className="citations-container">
        <h3 className="citations-title">Citations</h3>
        <p className="no-citations">No citations found.</p>
      </div>
    );
  }

  const getCitationTypeColor = (type) => {
    switch (type?.toLowerCase()) {
      case 'pii':
        return 'citation-pii';
      case 'safety':
        return 'citation-safety';
      case 'keyword':
        return 'citation-keyword';
      default:
        return 'citation-default';
    }
  };

  return (
    <div className="citations-container">
      <h3 className="citations-title">Citations ({citations.length})</h3>
      <div className="citations-list">
        {citations.map((citation, index) => (
          <div key={index} className={`citation-item ${getCitationTypeColor(citation.type)}`}>
            <div className="citation-header">
              <span className="citation-type">{citation.type || 'General'}</span>
              {citation.page && (
                <span className="citation-page">Page {citation.page}</span>
              )}
            </div>
            {citation.snippet && (
              <p className="citation-snippet">{citation.snippet}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default CitationList;

