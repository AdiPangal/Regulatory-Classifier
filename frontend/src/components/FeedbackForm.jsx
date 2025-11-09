import { useState } from 'react';
import { submitFeedback } from '../services/api';
import '../styles/feedback.css';

const FeedbackForm = ({ documentId, originalClassification, confidence, promptUsed, onFeedbackSubmitted }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [feedbackType, setFeedbackType] = useState('correction');
  const [correctedClassification, setCorrectedClassification] = useState('');
  const [feedbackText, setFeedbackText] = useState('');
  const [reviewerId, setReviewerId] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      await submitFeedback({
        document_id: documentId,
        original_classification: originalClassification,
        corrected_classification: feedbackType === 'correction' ? correctedClassification : null,
        feedback_type: feedbackType,
        feedback_text: feedbackText,
        reviewer_id: reviewerId || 'anonymous',
        confidence: confidence,
        prompt_used: promptUsed || null
      });

      alert('Feedback submitted successfully!');
      setIsOpen(false);
      setFeedbackText('');
      setCorrectedClassification('');
      if (onFeedbackSubmitted) {
        onFeedbackSubmitted();
      }
    } catch (error) {
      alert(`Error submitting feedback: ${error.response?.data?.detail || error.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) {
    return (
      <button className="feedback-toggle-button" onClick={() => setIsOpen(true)}>
        Provide Feedback
      </button>
    );
  }

  return (
    <div className="feedback-form-container">
      <div className="feedback-form-header">
        <h3 className="feedback-form-title">HITL Feedback</h3>
        <button className="close-button" onClick={() => setIsOpen(false)}>×</button>
      </div>

      <form onSubmit={handleSubmit} className="feedback-form">
        <div className="form-group">
          <label className="form-label">Feedback Type</label>
          <select
            className="form-select"
            value={feedbackType}
            onChange={(e) => setFeedbackType(e.target.value)}
          >
            <option value="correction">Correction (Classification was wrong)</option>
            <option value="confirmation">Confirmation (Classification was correct)</option>
            <option value="prompt_suggestion">Prompt Suggestion</option>
          </select>
        </div>

        {feedbackType === 'correction' && (
          <div className="form-group">
            <label className="form-label">Correct Classification</label>
            <select
              className="form-select"
              value={correctedClassification}
              onChange={(e) => setCorrectedClassification(e.target.value)}
              required
            >
              <option value="">Select correct classification</option>
              <option value="Public">Public</option>
              <option value="Confidential">Confidential</option>
              <option value="Highly Sensitive">Highly Sensitive</option>
              {/* Note: "Unsafe" is a safety flag, not a classification. Safety is evaluated separately. */}
            </select>
          </div>
        )}

        <div className="form-group">
          <label className="form-label">Reviewer ID (optional)</label>
          <input
            type="text"
            className="form-input"
            value={reviewerId}
            onChange={(e) => setReviewerId(e.target.value)}
            placeholder="Your name or ID"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Comments</label>
          <textarea
            className="form-textarea"
            value={feedbackText}
            onChange={(e) => setFeedbackText(e.target.value)}
            placeholder="Please provide details about why the classification was incorrect or any suggestions..."
            rows={4}
          />
        </div>

        <div className="form-actions">
          <button
            type="button"
            className="cancel-button"
            onClick={() => setIsOpen(false)}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="submit-button"
            disabled={isSubmitting || (feedbackType === 'correction' && !correctedClassification)}
          >
            {isSubmitting ? 'Submitting...' : 'Submit Feedback'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default FeedbackForm;

