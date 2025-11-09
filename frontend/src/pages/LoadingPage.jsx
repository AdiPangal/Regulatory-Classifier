import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import PreprocessingInfo from '../components/PreprocessingInfo';
import { classifyDocument, classifyText, preprocessDocument, preprocessText } from '../services/api';
import '../styles/loading.css';

const LoadingPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { mode, file, text, documentId, result } = location.state || {};
  const [statusMessage, setStatusMessage] = useState('Processing your document...');
  const [preprocessing, setPreprocessing] = useState(null);
  const [showPreprocessing, setShowPreprocessing] = useState(false);

  useEffect(() => {
    // If result is already available, go directly to results
    if (result && documentId) {
      navigate(`/results/${documentId}`, { state: { result }, replace: true });
      return;
    }

    // If we have mode and data, perform preprocessing first, then classification
    if (mode === 'text' && text) {
      setStatusMessage('Preprocessing text...');
      // Preprocess first (fast)
      preprocessText(text)
        .then((preprocessResult) => {
          setPreprocessing(preprocessResult);
          setShowPreprocessing(true);
          setStatusMessage('Analyzing text content...');
          // Then do full classification
          return classifyText(text);
        })
        .then((result) => {
          // Show preprocessing info for a moment, then navigate
          setTimeout(() => {
            navigate(`/results/${result.document_id}`, { state: { result }, replace: true });
          }, 1500);
        })
        .catch((error) => {
          alert(`Error: ${error.response?.data?.detail || error.message}`);
          navigate('/', { replace: true });
        });
    } else if (mode === 'file' && file) {
      setStatusMessage('Preprocessing document...');
      // Preprocess first (fast)
      preprocessDocument(file)
        .then((preprocessResult) => {
          setPreprocessing(preprocessResult);
          setShowPreprocessing(true);
          setStatusMessage('Analyzing document content...');
          // Then do full classification
          return classifyDocument(file);
        })
        .then((result) => {
          // Show preprocessing info for a moment, then navigate
          setTimeout(() => {
            navigate(`/results/${result.document_id}`, { state: { result }, replace: true });
          }, 1500);
        })
        .catch((error) => {
          alert(`Error: ${error.response?.data?.detail || error.message}`);
          navigate('/', { replace: true });
        });
    } else if (documentId) {
      // Legacy: If we have a document ID but no result, redirect
      setStatusMessage('Loading results...');
      const timer = setTimeout(() => {
        navigate(`/results/${documentId}`);
      }, 2000);
      return () => clearTimeout(timer);
    } else {
      // No data, redirect to input
      navigate('/', { replace: true });
    }
  }, [mode, file, text, documentId, result, navigate]);

  return (
    <div className="loading-page">
      <LoadingSpinner message={statusMessage} />
      {showPreprocessing && preprocessing && (
        <PreprocessingInfo preprocessing={preprocessing} />
      )}
    </div>
  );
};

export default LoadingPage;

