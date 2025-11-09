import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import ClassificationCard from '../components/ClassificationCard';
import DetectionSummary from '../components/DetectionSummary';
import CitationList from '../components/CitationList';
import FeedbackForm from '../components/FeedbackForm';
import { downloadPDFReport } from '../services/api';
import '../styles/results.css';

const ResultsPage = () => {
  const { documentId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [result, setResult] = useState(location.state?.result || null);
  const [loading, setLoading] = useState(!result);
  const batchId = location.state?.batchId; // Check if we came from batch

  useEffect(() => {
    // If no result in state, we'd normally fetch it here
    // For now, if we have it in state, we're good
    if (!result && documentId) {
      // In a real app, you'd fetch the result by documentId
      // For now, redirect to input if no result
      setTimeout(() => {
        navigate('/', { replace: true });
      }, 1000);
    }
  }, [documentId, result, navigate]);

  if (loading) {
    return (
      <div className="results-page">
        <div className="loading-state">Loading results...</div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="results-page">
        <div className="error-state">No results found. Redirecting...</div>
      </div>
    );
  }

  return (
    <div className="results-page">
      <div className="results-container">
        <div className="results-header">
          <h1 className="results-title">Classification Results</h1>
          <div className="header-actions">
            {batchId && (
              <button 
                className="back-to-batch-button" 
                onClick={() => navigate(`/batch/${batchId}`)}
              >
                ← Back to Batch Results
              </button>
            )}
            <button 
              className="download-pdf-button" 
              onClick={async () => {
                try {
                  const blob = await downloadPDFReport(result.document_id, result);
                  const url = window.URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `classification_report_${result.document_id}.pdf`;
                  document.body.appendChild(a);
                  a.click();
                  window.URL.revokeObjectURL(url);
                  document.body.removeChild(a);
                } catch (error) {
                  alert('Failed to download PDF: ' + (error.response?.data?.detail || error.message));
                }
              }}
            >
              Download PDF Report
            </button>
            <button className="new-classification-button" onClick={() => navigate('/')}>
              New Classification
            </button>
          </div>
        </div>

        <ClassificationCard
          classification={result.classification}
          confidence={result.confidence}
        />

        {/* Reasoning section - moved to second position */}
        {result.reasoning && (
          <div className="reasoning-section-top">
            <h3 className="reasoning-title">Detailed Reasoning</h3>
            <p className="reasoning-text">{result.reasoning}</p>
          </div>
        )}

        <div className="results-content">
          <div className="results-left">
            <DetectionSummary
              detectionSummary={result.detection_summary}
              safetyCheck={result.safety_check}
              isLegible={result.is_legible}
            />

            <div className="document-metadata">
              <h3 className="metadata-title">Document Information</h3>
              <div className="metadata-grid">
                <div className="metadata-item">
                  <span className="metadata-label">Document ID:</span>
                  <span className="metadata-value">{result.document_id}</span>
                </div>
                <div className="metadata-item">
                  <span className="metadata-label">Pages:</span>
                  <span className="metadata-value">{result.pages}</span>
                </div>
                <div className="metadata-item">
                  <span className="metadata-label">Images:</span>
                  <span className="metadata-value">{result.images}</span>
                </div>
                <div className="metadata-item">
                  <span className="metadata-label">Extraction Method:</span>
                  <span className="metadata-value">{result.extraction_method || 'unknown'}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="results-right">
            <CitationList citations={result.citations} />

            {result.reasons && result.reasons.length > 0 && (
              <div className="reasons-section">
                <h3 className="reasons-title">Classification Reasons</h3>
                <ul className="reasons-list">
                  {result.reasons.map((reason, index) => (
                    <li key={index} className="reason-item">{reason}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>

        <FeedbackForm
          documentId={result.document_id}
          originalClassification={result.classification}
          confidence={result.confidence}
          promptUsed={result.prompt_used}
        />
      </div>
    </div>
  );
};

export default ResultsPage;

