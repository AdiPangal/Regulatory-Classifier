import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { classifyBatch } from '../services/api';
import '../styles/input.css';

const InputPage = () => {
  const [inputMode, setInputMode] = useState('file'); // 'file' or 'text'
  const [files, setFiles] = useState([]);
  const [textInputs, setTextInputs] = useState(['']); // Array of text inputs
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();

  // File handling
  const handleFileSelect = (e) => {
    const selectedFiles = Array.from(e.target.files);
    const validFiles = selectedFiles.filter(file => {
      const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
      const acceptedTypes = ['.pdf', '.png', '.jpg', '.jpeg'];
      if (!acceptedTypes.includes(fileExtension)) {
        alert(`Invalid file type: ${file.name}. Accepted types: PDF, PNG, JPG, JPEG`);
        return false;
      }
      const maxSize = 50 * 1024 * 1024; // 50MB
      if (file.size > maxSize) {
        alert(`File ${file.name} exceeds 50MB limit`);
        return false;
      }
      return true;
    });
    setFiles([...files, ...validFiles]);
  };

  const handleRemoveFile = (index) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const droppedFiles = Array.from(e.dataTransfer.files);
    const validFiles = droppedFiles.filter(file => {
      const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
      const acceptedTypes = ['.pdf', '.png', '.jpg', '.jpeg'];
      if (!acceptedTypes.includes(fileExtension)) {
        return false;
      }
      const maxSize = 50 * 1024 * 1024;
      return file.size <= maxSize;
    });
    setFiles([...files, ...validFiles]);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  // Text input handling
  const handleTextChange = (index, value) => {
    const newTextInputs = [...textInputs];
    newTextInputs[index] = value;
    setTextInputs(newTextInputs);
  };

  const handleAddTextInput = () => {
    setTextInputs([...textInputs, '']);
  };

  const handleRemoveTextInput = (index) => {
    if (textInputs.length > 1) {
      setTextInputs(textInputs.filter((_, i) => i !== index));
    }
  };

  // Submission handling
  const handleSubmit = async () => {
    if (inputMode === 'file') {
      if (files.length === 0) {
        alert('Please select at least one file');
        return;
      }

      setIsSubmitting(true);
      try {
        if (files.length === 1) {
          // Single file - use regular classify flow
          navigate('/loading', { 
            state: { 
              mode: 'file',
              file: files[0]
            } 
          });
        } else {
          // Multiple files - use batch flow (skip frontend preprocessing, backend handles it)
          const response = await classifyBatch(files);
          const batchId = response.batch_id;
          // Go directly to batch progress page - backend handles preprocessing as part of classification
          navigate(`/batch/${batchId}`, { 
            state: { 
              batchId, 
              total: files.length
            } 
          });
        }
      } catch (error) {
        alert(`Error: ${error.response?.data?.detail || error.message}`);
        setIsSubmitting(false);
      }
    } else {
      // Text mode
      const validTexts = textInputs.filter(text => text.trim().length > 0);
      if (validTexts.length === 0) {
        alert('Please enter at least one text input');
        return;
      }

      setIsSubmitting(true);
      try {
        if (validTexts.length === 1) {
          // Single text - use regular classify flow
          navigate('/loading', { 
            state: { 
              mode: 'text',
              text: validTexts[0]
            } 
          });
        } else {
          // Multiple texts - convert to files or use batch API
          // For now, we'll process them one by one or you can implement a text batch endpoint
          alert('Multiple text inputs not yet supported in batch mode. Processing first text input...');
          navigate('/loading', { 
            state: { 
              mode: 'text',
              text: validTexts[0]
            } 
          });
        }
      } catch (error) {
        alert(`Error: ${error.response?.data?.detail || error.message}`);
        setIsSubmitting(false);
      }
    }
  };

  return (
    <div className="input-page">
      <div className="input-container">
        <h1 className="page-title">Regulatory Document Classifier</h1>
        <p className="page-subtitle">
          Upload document(s) or enter text to classify sensitivity level
        </p>

        <div className="input-mode-selector">
          <button
            className={`mode-button ${inputMode === 'file' ? 'active' : ''}`}
            onClick={() => setInputMode('file')}
          >
            Upload File(s)
          </button>
          <button
            className={`mode-button ${inputMode === 'text' ? 'active' : ''}`}
            onClick={() => setInputMode('text')}
          >
            Enter Text
          </button>
        </div>

        <div className="input-content">
          {inputMode === 'file' ? (
            <div className="file-input-section">
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
                    Supported formats: PDF, PNG, JPG, JPEG (max 50MB per file)
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
                    className="submit-button"
                    onClick={handleSubmit}
                    disabled={isSubmitting}
                  >
                    {isSubmitting 
                      ? 'Processing...' 
                      : files.length === 1 
                        ? 'Classify Document' 
                        : `Process ${files.length} Documents`}
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="text-input-section">
              <div className="text-inputs-container">
                {textInputs.map((text, index) => (
                  <div key={index} className="text-input-wrapper">
                    {textInputs.length > 1 && (
                      <div className="text-input-header">
                        <span className="text-input-label">Text Input {index + 1}</span>
                        <button
                          className="remove-text-button"
                          onClick={() => handleRemoveTextInput(index)}
                          disabled={textInputs.length === 1}
                        >
                          Remove
                        </button>
                      </div>
                    )}
                    <textarea
                      className="text-input-area"
                      value={text}
                      onChange={(e) => handleTextChange(index, e.target.value)}
                      placeholder="Enter text to classify..."
                      rows={8}
                    />
                  </div>
                ))}
                <div className="text-input-actions">
                  <button
                    className="add-text-button"
                    onClick={handleAddTextInput}
                  >
                    + Add Another Text Input
                  </button>
                  <button
                    className="submit-button"
                    onClick={handleSubmit}
                    disabled={isSubmitting || textInputs.every(t => !t.trim())}
                  >
                    {isSubmitting 
                      ? 'Processing...' 
                      : textInputs.filter(t => t.trim()).length === 1
                        ? 'Classify Text'
                        : `Classify ${textInputs.filter(t => t.trim()).length} Texts`}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default InputPage;
