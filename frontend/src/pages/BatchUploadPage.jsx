import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { classifyBatch, createBatchWebSocket } from '../services/api';
import '../styles/batch.css';

const BatchUploadPage = () => {
  const [files, setFiles] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const navigate = useNavigate();

  const handleFileSelect = (e) => {
    const selectedFiles = Array.from(e.target.files);
    setFiles([...files, ...selectedFiles]);
  };

  const handleRemoveFile = (index) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const droppedFiles = Array.from(e.dataTransfer.files);
    setFiles([...files, ...droppedFiles]);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleSubmit = async () => {
    if (files.length === 0) {
      alert('Please select at least one file');
      return;
    }

    setIsUploading(true);
    try {
      const response = await classifyBatch(files);
      const batchId = response.batch_id;
      
      // Navigate to batch progress page
      navigate(`/batch/${batchId}`, { state: { batchId, total: files.length } });
    } catch (error) {
      alert(`Error: ${error.response?.data?.detail || error.message}`);
      setIsUploading(false);
    }
  };

  return (
    <div className="batch-upload-page">
      <div className="batch-upload-container">
        <h1 className="page-title">Batch Document Classification</h1>
        <p className="page-subtitle">
          Upload multiple documents to classify them in batch
        </p>

        <div
          className="file-drop-zone"
          onDrop={handleDrop}
          onDragOver={handleDragOver}
        >
          <div className="drop-zone-content">
            <svg className="upload-icon" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="17 8 12 3 7 8"></polyline>
              <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
            <p className="drop-zone-text">
              Drag and drop files here, or{' '}
              <label className="file-input-label">
                <input
                  type="file"
                  multiple
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={handleFileSelect}
                  className="file-input-hidden"
                />
                <span className="file-input-link">browse</span>
              </label>
            </p>
            <p className="drop-zone-hint">
              Supported formats: PDF, PNG, JPG, JPEG
            </p>
          </div>
        </div>

        {files.length > 0 && (
          <div className="selected-files">
            <h3 className="files-title">Selected Files ({files.length})</h3>
            <div className="files-list">
              {files.map((file, index) => (
                <div key={index} className="file-item">
                  <span className="file-name">{file.name}</span>
                  <span className="file-size">
                    {(file.size / 1024).toFixed(2)} KB
                  </span>
                  <button
                    className="remove-file-button"
                    onClick={() => handleRemoveFile(index)}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
            <button
              className="submit-batch-button"
              onClick={handleSubmit}
              disabled={isUploading}
            >
              {isUploading ? 'Uploading...' : `Process ${files.length} Document${files.length > 1 ? 's' : ''}`}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default BatchUploadPage;

