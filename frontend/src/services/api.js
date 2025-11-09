import axios from 'axios';

// Get API base URL from environment variable
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000, // 5 minutes for large files
});

/**
 * Classify a document file (PDF or image)
 * @param {File} file - The file to classify
 * @param {string} documentId - Optional document ID
 * @returns {Promise} Classification result
 */
export const classifyDocument = async (file, documentId = null) => {
  const formData = new FormData();
  formData.append('file', file);
  if (documentId) {
    formData.append('document_id', documentId);
  }
  
  const response = await api.post('/classify', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  
  return response.data;
};

/**
 * Preprocess document (get legibility, page count, image count)
 * @param {File} file - The file to preprocess
 * @returns {Promise} Preprocessing information
 */
export const preprocessDocument = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await api.post('/preprocess', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  
  return response.data;
};

/**
 * Preprocess text
 * @param {string} text - Text to preprocess
 * @returns {Promise} Preprocessing information
 */
export const preprocessText = async (text) => {
  const response = await api.post('/preprocess/text', {
    text,
  });
  
  return response.data;
};

/**
 * Classify text directly
 * @param {string} text - Text to classify
 * @param {string} documentId - Optional document ID
 * @returns {Promise} Classification result
 */
export const classifyText = async (text, documentId = null) => {
  const response = await api.post('/classify/text', {
    text,
    document_id: documentId,
  });
  
  return response.data;
};

/**
 * Classify multiple documents in batch
 * @param {File[]} files - Array of files to classify
 * @returns {Promise} Batch job ID and status
 */
export const classifyBatch = async (files) => {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });
  
  const response = await api.post('/classify/batch', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  
  return response.data;
};

/**
 * Get batch processing status
 * @param {string} batchId - Batch job ID
 * @returns {Promise} Batch status
 */
export const getBatchStatus = async (batchId) => {
  const response = await api.get(`/batch/${batchId}/status`);
  return response.data;
};

/**
 * Submit HITL feedback
 * @param {Object} feedbackData - Feedback data
 * @returns {Promise} Feedback response
 */
export const submitFeedback = async (feedbackData) => {
  const response = await api.post('/feedback', feedbackData);
  return response.data;
};

/**
 * Get feedback for a document
 * @param {string} documentId - Document ID
 * @returns {Promise} Feedback records
 */
export const getFeedback = async (documentId) => {
  const response = await api.get(`/feedback/${documentId}`);
  return response.data;
};

/**
 * Health check
 * @returns {Promise} Health status
 */
export const healthCheck = async () => {
  const response = await api.get('/health');
  return response.data;
};

/**
 * Get audit history
 * @param {Object} filters - Filter parameters
 * @returns {Promise} Audit records
 */
export const getAuditHistory = async (filters = {}) => {
  const response = await api.get('/audit/history', { params: filters });
  return response.data;
};

/**
 * Get audit statistics
 * @param {string} startDate - Start date (ISO format)
 * @param {string} endDate - End date (ISO format)
 * @returns {Promise} Audit statistics
 */
export const getAuditStats = async (startDate = null, endDate = null) => {
  const params = {};
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;
  const response = await api.get('/audit/stats', { params });
  return response.data;
};

/**
 * Get document audit history
 * @param {string} documentId - Document ID
 * @returns {Promise} Document audit records
 */
export const getDocumentAuditHistory = async (documentId) => {
  const response = await api.get(`/audit/document/${documentId}`);
  return response.data;
};

/**
 * Get classification distribution for charts
 * @param {string} startDate - Start date (ISO format)
 * @param {string} endDate - End date (ISO format)
 * @returns {Promise} Classification distribution
 */
export const getClassificationDistribution = async (startDate = null, endDate = null) => {
  const params = {};
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;
  const response = await api.get('/stats/classification-distribution', { params });
  return response.data;
};

/**
 * Get HITL feedback statistics
 * @returns {Promise} HITL feedback stats
 */
export const getHITLFeedbackStats = async () => {
  const response = await api.get('/stats/hitl-feedback');
  return response.data;
};

/**
 * Download PDF report
 * @param {string} documentId - Document ID
 * @param {Object} resultData - Optional classification result data (for better PDF)
 * @returns {Promise} PDF blob
 */
export const downloadPDFReport = async (documentId, resultData = null) => {
  if (resultData) {
    // Use POST endpoint with full result data for better PDF
    const response = await api.post('/report/pdf', resultData, {
      responseType: 'blob'
    });
    return response.data;
  } else {
    // Fallback to GET endpoint using audit trail
    const response = await api.get(`/report/${documentId}/pdf`, {
      responseType: 'blob'
    });
    return response.data;
  }
};

/**
 * Create WebSocket connection for batch updates
 * @param {string} batchId - Batch job ID
 * @param {Function} onMessage - Callback for messages
 * @returns {WebSocket} WebSocket connection
 */
export const createBatchWebSocket = (batchId, onMessage) => {
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsHost = import.meta.env.VITE_API_BASE_URL?.replace(/^https?:\/\//, '') || 'localhost:8000';
  const wsUrl = `${wsProtocol}//${wsHost}/ws/batch/${batchId}`;
  
  const ws = new WebSocket(wsUrl);
  
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (e) {
      console.error('Failed to parse WebSocket message:', e);
    }
  };
  
  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
  };
  
  ws.onclose = () => {
    console.log('WebSocket connection closed');
  };
  
  return ws;
};

/**
 * Analyze feedback and get prompt improvement suggestions
 * @param {string} promptName - Optional prompt name to analyze
 * @param {number} minFeedbackCount - Minimum feedback count required
 * @returns {Promise} Analysis results
 */
export const analyzePromptRefinement = async (promptName = null, minFeedbackCount = 3) => {
  const response = await api.post('/refinement/analyze', null, {
    params: {
      prompt_name: promptName,
      min_feedback_count: minFeedbackCount
    }
  });
  return response.data;
};

/**
 * Apply a prompt improvement
 * @param {string} promptName - Prompt name
 * @param {string} improvedPrompt - Improved prompt text
 * @param {string} reason - Reason for change
 * @param {boolean} autoApply - Whether to apply immediately
 * @returns {Promise} Application result
 */
export const applyPromptImprovement = async (promptName, improvedPrompt, reason, autoApply = false) => {
  const response = await api.post('/refinement/apply', {
    prompt_name: promptName,
    improved_prompt: improvedPrompt,
    reason: reason,
    auto_apply: autoApply
  });
  return response.data;
};

/**
 * Get refinement history
 * @param {string} promptName - Optional prompt name filter
 * @returns {Promise} Refinement history
 */
export const getRefinementHistory = async (promptName = null) => {
  const response = await api.get('/refinement/history', {
    params: {
      prompt_name: promptName
    }
  });
  return response.data;
};

/**
 * Get pending suggestions
 * @returns {Promise} Pending suggestions
 */
export const getPendingSuggestions = async () => {
  const response = await api.get('/refinement/suggestions');
  return response.data;
};

export default api;

