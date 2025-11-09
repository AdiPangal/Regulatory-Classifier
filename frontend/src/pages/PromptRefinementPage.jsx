import { useState, useEffect } from 'react';
import { analyzePromptRefinement, applyPromptImprovement, getRefinementHistory, getPendingSuggestions } from '../services/api';
import '../styles/refinement.css';

const PromptRefinementPage = () => {
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [selectedPrompt, setSelectedPrompt] = useState('');
  const [applying, setApplying] = useState(false);
  const [history, setHistory] = useState([]);
  const [suggestions, setSuggestions] = useState([]);

  useEffect(() => {
    loadHistory();
    loadSuggestions();
  }, []);

  const loadHistory = async () => {
    try {
      const response = await getRefinementHistory();
      setHistory(response.history || []);
    } catch (error) {
      console.error('Failed to load history:', error);
    }
  };

  const loadSuggestions = async () => {
    try {
      const response = await getPendingSuggestions();
      setSuggestions(response.suggestions || []);
    } catch (error) {
      console.error('Failed to load suggestions:', error);
    }
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setAnalysisResult(null);
    try {
      const result = await analyzePromptRefinement(selectedPrompt || null, 3);
      setAnalysisResult(result);
    } catch (error) {
      alert(`Analysis failed: ${error.response?.data?.detail || error.message}`);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleApplySuggestion = async (suggestion, autoApply = false) => {
    if (!autoApply && !window.confirm('Apply this prompt improvement?')) {
      return;
    }

    setApplying(true);
    try {
      const result = await applyPromptImprovement(
        suggestion.prompt_name,
        suggestion.new_prompt || suggestion.improved_prompt,
        suggestion.reason || 'Applied from suggestion',
        autoApply
      );
      
      alert(result.message);
      loadHistory();
      loadSuggestions();
      if (analysisResult && analysisResult.prompt_name === suggestion.prompt_name) {
        setAnalysisResult(null);
      }
    } catch (error) {
      alert(`Failed to apply: ${error.response?.data?.detail || error.message}`);
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="refinement-page">
      <div className="refinement-container">
        <h1 className="page-title">Automated Prompt Refinement</h1>
        <p className="page-subtitle">
          Analyze feedback and automatically get LLM-generated prompt improvements
        </p>

        <div className="refinement-section">
          <h2 className="section-title">Analyze Feedback</h2>
          <div className="analyze-controls">
            <input
              type="text"
              className="prompt-input"
              placeholder="Prompt name (leave empty to analyze worst-performing prompt)"
              value={selectedPrompt}
              onChange={(e) => setSelectedPrompt(e.target.value)}
            />
            <button
              className="analyze-button"
              onClick={handleAnalyze}
              disabled={analyzing}
            >
              {analyzing ? 'Analyzing...' : 'Analyze Feedback & Get Suggestions'}
            </button>
          </div>

          {analysisResult && (
            <div className="analysis-result">
              {analysisResult.status === 'insufficient_feedback' ? (
                <div className="info-message">
                  <p>Need at least {analysisResult.current_count} feedback records.</p>
                  <p>Current: {analysisResult.current_count}</p>
                </div>
              ) : analysisResult.status === 'success' ? (
                <div className="suggestions-display">
                  <h3>Analysis for: {analysisResult.prompt_name}</h3>
                  <p className="feedback-count">
                    Analyzed {analysisResult.feedback_count} feedback records
                  </p>

                  {analysisResult.suggestions && (
                    <>
                      <div className="issues-section">
                        <h4>Issues Identified:</h4>
                        <ul>
                          {analysisResult.suggestions.issues?.map((issue, idx) => (
                            <li key={idx}>{issue}</li>
                          ))}
                        </ul>
                      </div>

                      <div className="suggestions-section">
                        <h4>Suggested Improvements:</h4>
                        <ul>
                          {analysisResult.suggestions.suggestions?.map((suggestion, idx) => (
                            <li key={idx}>{suggestion}</li>
                          ))}
                        </ul>
                      </div>

                      {analysisResult.suggestions.improved_prompt && (
                        <div className="improved-prompt-section">
                          <h4>Improved Prompt:</h4>
                          <div className="prompt-comparison">
                            <div className="prompt-box">
                              <h5>Current Prompt</h5>
                              <pre className="prompt-text">{analysisResult.current_prompt}</pre>
                            </div>
                            <div className="prompt-box">
                              <h5>Improved Prompt</h5>
                              <pre className="prompt-text">{analysisResult.suggestions.improved_prompt}</pre>
                            </div>
                          </div>
                          <div className="prompt-actions">
                            <button
                              className="apply-button"
                              onClick={() => handleApplySuggestion({
                                prompt_name: analysisResult.prompt_name,
                                new_prompt: analysisResult.suggestions.improved_prompt,
                                reason: analysisResult.suggestions.reasoning || 'LLM-generated improvement'
                              }, false)}
                              disabled={applying}
                            >
                              {applying ? 'Applying...' : 'Apply This Improvement'}
                            </button>
                            <button
                              className="auto-apply-button"
                              onClick={() => {
                                if (window.confirm('Auto-apply this improvement? It will be applied immediately.')) {
                                  handleApplySuggestion({
                                    prompt_name: analysisResult.prompt_name,
                                    new_prompt: analysisResult.suggestions.improved_prompt,
                                    reason: analysisResult.suggestions.reasoning || 'LLM-generated improvement'
                                  }, true);
                                }
                              }}
                              disabled={applying}
                            >
                              Auto-Apply (No Approval)
                            </button>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              ) : (
                <div className="error-message">
                  {analysisResult.message || 'Analysis failed'}
                </div>
              )}
            </div>
          )}
        </div>

        {suggestions.length > 0 && (
          <div className="refinement-section">
            <h2 className="section-title">Pending Suggestions</h2>
            <div className="suggestions-list">
              {suggestions.map((suggestion, idx) => (
                <div key={idx} className="suggestion-item">
                  <h4>{suggestion.prompt_name}</h4>
                  <p className="suggestion-reason">{suggestion.reason}</p>
                  <button
                    className="apply-button-small"
                    onClick={() => handleApplySuggestion(suggestion, false)}
                    disabled={applying}
                  >
                    Apply
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {history.length > 0 && (
          <div className="refinement-section">
            <h2 className="section-title">Refinement History</h2>
            <div className="history-list">
              {history.slice().reverse().map((record, idx) => (
                <div key={idx} className="history-item">
                  <div className="history-header">
                    <span className="history-prompt">{record.prompt_name}</span>
                    <span className={`history-status ${record.auto_applied ? 'applied' : 'suggested'}`}>
                      {record.auto_applied ? 'Applied' : 'Suggested'}
                    </span>
                    <span className="history-time">
                      {new Date(record.timestamp).toLocaleString()}
                    </span>
                  </div>
                  <p className="history-reason">{record.reason}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PromptRefinementPage;

