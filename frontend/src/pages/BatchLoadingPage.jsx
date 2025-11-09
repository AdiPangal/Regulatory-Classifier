import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { createBatchWebSocket, preprocessDocument } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import PreprocessingInfo from '../components/PreprocessingInfo';
import ProgressBar from '../components/ProgressBar';
import '../styles/batch.css';
import '../styles/loading.css';

const BatchLoadingPage = () => {
  const { batchId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { files } = location.state || {};
  
  const [phase, setPhase] = useState('preprocessing'); // 'preprocessing' or 'classifying'
  const [preprocessingResults, setPreprocessingResults] = useState([]);
  const [preprocessingProgress, setPreprocessingProgress] = useState(0);
  const [currentFile, setCurrentFile] = useState('');
  const [classificationProgress, setClassificationProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState('Preprocessing documents...');

  useEffect(() => {
    if (!batchId || !files || files.length === 0) {
      navigate('/', { replace: true });
      return;
    }

    // Phase 1: Preprocess all files
    const preprocessAllFiles = async () => {
      const results = [];
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        setCurrentFile(file.name);
        setPreprocessingProgress(((i + 1) / files.length) * 100);
        setStatusMessage(`Preprocessing ${i + 1} of ${files.length}: ${file.name}`);
        
        try {
          const preprocessResult = await preprocessDocument(file);
          results.push({
            filename: file.name,
            ...preprocessResult
          });
        } catch (error) {
          results.push({
            filename: file.name,
            error: error.response?.data?.detail || error.message
          });
        }
      }
      
      setPreprocessingResults(results);
      setPhase('classifying');
      setStatusMessage('Classification in progress...');
    };

    preprocessAllFiles();
  }, [batchId, files, navigate]);

  // Phase 2: Connect to WebSocket for classification updates when phase changes to classifying
  useEffect(() => {
    if (phase === 'classifying' && batchId) {
      const ws = createBatchWebSocket(batchId, (message) => {
        if (message.type === 'progress') {
          setCurrentFile(message.current_file || '');
          const progress = message.total > 0 
            ? (message.completed / message.total) * 100 
            : 0;
          setClassificationProgress(progress);
          setStatusMessage(`Processing ${message.completed + 1} of ${message.total}: ${message.current_file || ''}`);
        } else if (message.type === 'complete') {
          // Navigate to batch progress page when complete
          setTimeout(() => {
            navigate(`/batch/${batchId}`, { 
              state: { 
                batchId, 
                total: message.total,
                preprocessingResults 
              },
              replace: true 
            });
          }, 1000);
        }
      });
      
      return () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.close();
        }
      };
    }
  }, [phase, batchId, navigate, preprocessingResults]);

  const progress = phase === 'preprocessing' ? preprocessingProgress : classificationProgress;

  return (
    <div className="loading-page batch-loading-page">
      <div className="loading-container">
        <LoadingSpinner message={statusMessage} />
        
        <div className="progress-section">
          <ProgressBar progress={progress} />
          <p className="progress-text">
            {phase === 'preprocessing' 
              ? `Preprocessing: ${Math.round(preprocessingProgress)}%` 
              : `Classification: ${Math.round(classificationProgress)}%`}
          </p>
          {currentFile && (
            <p className="current-file">Current: {currentFile}</p>
          )}
        </div>

        {preprocessingResults.length > 0 && (
          <div className="preprocessing-results">
            <h3 className="preprocessing-title">
              Preprocessing Results ({preprocessingResults.length} of {files?.length || 0})
            </h3>
            <div className="preprocessing-list">
              {preprocessingResults.map((result, index) => (
                <div key={index} className="preprocessing-item">
                  <div className="preprocessing-item-header">
                    <span className="preprocessing-filename">{result.filename}</span>
                    {result.error ? (
                      <span className="preprocessing-error">Error</span>
                    ) : (
                      <span className="preprocessing-success">✓</span>
                    )}
                  </div>
                  {!result.error && (
                    <div className="preprocessing-item-details">
                      <span>Pages: {result.pages || 0}</span>
                      <span>Images: {result.images || 0}</span>
                      <span>Legible: {result.is_legible ? 'Yes' : 'No'}</span>
                    </div>
                  )}
                  {result.error && (
                    <div className="preprocessing-item-error">
                      {result.error}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default BatchLoadingPage;

