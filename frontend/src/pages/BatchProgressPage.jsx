import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { getBatchStatus, createBatchWebSocket } from '../services/api';
import ProgressBar from '../components/ProgressBar';
import '../styles/batch.css';

const BatchProgressPage = () => {
  const { batchId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [batchStatus, setBatchStatus] = useState({
    status: 'processing',
    total: location.state?.total || 0,
    completed: 0,
    results: [],
    errors: []
  });
  const [documentStatuses, setDocumentStatuses] = useState({});
  const [currentFile, setCurrentFile] = useState('');
  const [preprocessingResults, setPreprocessingResults] = useState([]);
  const [currentPhase, setCurrentPhase] = useState('preprocessing'); // 'preprocessing' or 'classifying'

  useEffect(() => {
    if (!batchId) {
      navigate('/batch', { replace: true });
      return;
    }

    // Initial status fetch
    getBatchStatus(batchId)
      .then((status) => {
        setBatchStatus(status);
        // Initialize document statuses
        const statuses = {};
        status.results?.forEach((result) => {
          statuses[result.document_id] = 'completed';
        });
        status.errors?.forEach((error) => {
          statuses[error.filename] = 'error';
        });
        setDocumentStatuses(statuses);
      })
      .catch((error) => {
        console.error('Failed to fetch batch status:', error);
      });

    // Connect to WebSocket for real-time updates
    const ws = createBatchWebSocket(batchId, (message) => {
      if (message.type === 'preprocessing') {
        // Preprocessing phase - show preprocessing info
        setCurrentPhase('preprocessing');
        setCurrentFile(message.current_file || '');
      } else if (message.type === 'progress') {
        // Classification phase
        setCurrentPhase('classifying');
        setBatchStatus((prev) => ({
          ...prev,
          completed: message.completed || prev.completed,
          status: 'processing'
        }));
        setCurrentFile(message.current_file || '');
        
        // Update document status
        if (message.document_id) {
          setDocumentStatuses((prev) => ({
            ...prev,
            [message.document_id]: 'processing'
          }));
        }
      } else if (message.type === 'result') {
        setCurrentPhase('classifying');
        setBatchStatus((prev) => ({
          ...prev,
          results: [...(prev.results || []), message.result],
          completed: prev.completed + 1
        }));
        setDocumentStatuses((prev) => ({
          ...prev,
          [message.document_id]: 'completed'
        }));
        
        // Add preprocessing info if available
        if (message.preprocessing) {
          setPreprocessingResults((prev) => [...prev, message.preprocessing]);
        }
      } else if (message.type === 'error') {
        setCurrentPhase('classifying');
        setBatchStatus((prev) => ({
          ...prev,
          errors: [...(prev.errors || []), {
            filename: message.filename,
            error: message.error
          }],
          completed: prev.completed + 1
        }));
        setDocumentStatuses((prev) => ({
          ...prev,
          [message.filename]: 'error'
        }));
      } else if (message.type === 'complete') {
        setCurrentPhase('classifying');
        setBatchStatus((prev) => ({
          ...prev,
          status: 'completed',
          completed: message.completed,
          total: message.total
        }));
      }
    });

    return () => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [batchId, navigate]);

  // Calculate progress - account for preprocessing phase
  const progress = batchStatus.total > 0 
    ? (currentPhase === 'preprocessing' 
        ? (preprocessingResults.length / batchStatus.total) * 50  // Preprocessing is first 50%
        : 50 + ((batchStatus.completed / batchStatus.total) * 50))  // Classification is second 50%
    : 0;

  const handleViewResult = (documentId) => {
    const result = batchStatus.results?.find(r => r.document_id === documentId);
    if (result) {
      navigate(`/results/${documentId}`, { 
        state: { 
          result,
          batchId: batchId // Pass batchId so ResultsPage can show back button
        } 
      });
    }
  };

  const handleBackToBatch = () => {
    navigate('/batch');
  };

  return (
    <div className="batch-progress-page">
      <div className="batch-progress-container">
        <div className="batch-progress-header">
          <h1 className="page-title">Batch Processing</h1>
          <button className="back-button" onClick={handleBackToBatch}>
            ← Back to Batch Upload
          </button>
        </div>

        <div className="batch-status-card">
          <div className="status-header">
            <span className="batch-id">Batch ID: {batchId}</span>
            <span className={`status-badge status-${batchStatus.status}`}>
              {batchStatus.status}
            </span>
          </div>

          <div className="progress-section">
            <div className="progress-info">
              <span className="progress-text">
                {currentPhase === 'preprocessing' 
                  ? 'Preprocessing documents...'
                  : `${batchStatus.completed} of ${batchStatus.total} documents processed`}
              </span>
              <span className="progress-percentage">{Math.round(progress)}%</span>
            </div>
            <ProgressBar progress={progress} />
            {currentFile && (
              <p className="current-file">
                {currentPhase === 'preprocessing' ? 'Preprocessing' : 'Processing'}: {currentFile}
              </p>
            )}
          </div>
        </div>

        {preprocessingResults && preprocessingResults.length > 0 && (
          <div className="preprocessing-summary-card">
            <h3 className="section-title">Preprocessing Summary</h3>
            <div className="preprocessing-summary-grid">
              {preprocessingResults.map((preprocess, index) => (
                <div key={index} className="preprocessing-summary-item">
                  <span className="preprocessing-summary-filename">{preprocess.filename}</span>
                  {!preprocess.error && (
                    <div className="preprocessing-summary-details">
                      <span>Pages: {preprocess.pages || 0}</span>
                      <span>Images: {preprocess.images || 0}</span>
                      <span>Legible: {preprocess.is_legible ? 'Yes' : 'No'}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="batch-results-section">
          <h2 className="results-title">Classification Results</h2>
          
          {batchStatus.results && batchStatus.results.length > 0 && (
            <div className="results-list">
              <h3 className="section-title">Completed ({batchStatus.results.length})</h3>
              {batchStatus.results.map((result, index) => (
                <div key={result.document_id || index} className="result-item completed">
                  <div className="result-info">
                    <span className="result-classification">
                      {result.classification}
                    </span>
                    <span className="result-confidence">
                      {(result.confidence * 100).toFixed(1)}% confidence
                    </span>
                    <span className="result-id">ID: {result.document_id}</span>
                  </div>
                  <button
                    className="view-result-button"
                    onClick={() => handleViewResult(result.document_id)}
                  >
                    View Details
                  </button>
                </div>
              ))}
            </div>
          )}

          {batchStatus.errors && batchStatus.errors.length > 0 && (
            <div className="errors-list">
              <h3 className="section-title">Errors ({batchStatus.errors.length})</h3>
              {batchStatus.errors.map((error, index) => (
                <div key={index} className="result-item error">
                  <div className="result-info">
                    <span className="error-filename">{error.filename}</span>
                    <span className="error-message">{error.error}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {batchStatus.status === 'completed' && (
            <div className="batch-complete">
              <p className="complete-message">
                ✓ Batch processing completed successfully!
              </p>
              <button
                className="new-batch-button"
                onClick={handleBackToBatch}
              >
                Process Another Batch
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default BatchProgressPage;

