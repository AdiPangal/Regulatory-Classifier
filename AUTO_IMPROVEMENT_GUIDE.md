# Automatic Continuous Improvement Guide

## Overview

The system now includes **fully automatic continuous improvement**! As you process documents and submit feedback, the system will:

1. ✅ **Automatically analyze** feedback after every 10 submissions (configurable)
2. ✅ **Automatically apply** improvements if confidence is high enough (≥75% by default)
3. ✅ **Track accuracy** improvements over time
4. ✅ **Run in background** - no manual intervention needed!

## How It Works

### Automatic Cycle

```
Process 100 PDFs → Submit Feedback → System Analyzes (after 10 feedbacks) 
→ LLM Generates Better Prompts → Auto-Applies if Confident → Next 100 PDFs Use Better Prompts
→ Accuracy Improves → Cycle Continues
```

### Configuration

You can configure the system via environment variables in your `.env` file:

```bash
# Number of feedback submissions before triggering analysis
AUTO_IMPROVEMENT_FEEDBACK_THRESHOLD=10

# Minimum confidence (0.0-1.0) required to auto-apply improvements
AUTO_IMPROVEMENT_MIN_CONFIDENCE=0.75

# Enable/disable automatic application (true/false)
AUTO_IMPROVEMENT_ENABLED=true

# Minimum feedback needed for analysis
AUTO_IMPROVEMENT_MIN_FEEDBACK=5

# How often to check for improvements (seconds)
AUTO_IMPROVEMENT_CHECK_INTERVAL=300  # 5 minutes
```

### Default Settings

- **Feedback Threshold**: 10 submissions
- **Min Confidence**: 75% (0.75)
- **Auto-Apply**: Enabled
- **Check Interval**: Every 5 minutes

## What Gets Improved

1. **Prompts**: The instructions given to the LLM get better over time
2. **Classification Accuracy**: Better prompts = better classifications
3. **Pattern Recognition**: System learns from feedback patterns

## Monitoring

### API Endpoints

1. **GET `/auto-improvement/status`**
   - Current status of the system
   - Feedback count since last analysis
   - Latest accuracy metrics
   - Accuracy trend

2. **POST `/auto-improvement/trigger`**
   - Manually trigger analysis (useful for testing)

3. **GET `/auto-improvement/accuracy-trend`**
   - View accuracy improvements over time
   - Filter by prompt name
   - Specify number of days to look back

### Example Status Response

```json
{
  "is_running": true,
  "feedback_count_since_last_analysis": 8,
  "feedback_threshold": 10,
  "should_analyze": false,
  "last_analysis_time": "2024-01-15T10:30:00",
  "auto_apply_enabled": true,
  "min_improvement_confidence": 0.75,
  "accuracy_trend": [...],
  "latest_accuracy": {
    "timestamp": "2024-01-15T10:30:00",
    "accuracy": 85.5,
    "total_feedback": 50
  }
}
```

## How to Use

### 1. Start the Server

The automatic improvement system starts automatically when you start the server:

```bash
python3 main.py
```

### 2. Process Documents and Submit Feedback

Just use the system normally:
- Classify documents
- Submit feedback when classifications are wrong
- The system handles the rest automatically!

### 3. Monitor Improvements

Check the status endpoint to see improvements:

```bash
curl http://localhost:8000/auto-improvement/status
```

### 4. View Accuracy Trends

See how accuracy improves over time:

```bash
curl http://localhost:8000/auto-improvement/accuracy-trend?days=30
```

## Improvement Confidence Calculation

The system calculates confidence based on:

- **Feedback Count**: More feedback = higher confidence
- **Clear Patterns**: Strong misclassification patterns = higher confidence
- **Detailed Suggestions**: LLM provides detailed improvements = higher confidence

Confidence thresholds:
- **≥75%**: Auto-apply immediately
- **<75%**: Save as suggestion for manual review

## Safety Features

1. **Confidence Threshold**: Only auto-applies if confidence is high
2. **Manual Override**: You can always review and manually apply suggestions
3. **History Tracking**: All improvements are logged
4. **Rollback Capability**: Old prompts are saved in history

## Example Workflow

1. **Day 1**: Process 50 documents, submit 10 feedback corrections
   - System automatically analyzes after 10th feedback
   - LLM generates improved prompt
   - Confidence: 82% → **Auto-applied!**

2. **Day 2**: Process 50 more documents with improved prompt
   - Accuracy improves from 70% to 78%
   - System tracks improvement

3. **Day 3**: Process 50 more documents, submit 10 more feedbacks
   - System analyzes again
   - Generates further improvements
   - Accuracy improves to 85%

4. **Week 1**: Accuracy has improved from 70% → 85% automatically!

## Troubleshooting

### System Not Improving

1. Check if auto-improvement is enabled:
   ```bash
   curl http://localhost:8000/auto-improvement/status
   ```

2. Check feedback count:
   - Need at least 10 feedback submissions (configurable)
   - Need at least 5 feedbacks for analysis (configurable)

3. Check confidence:
   - If confidence < threshold, improvements are saved as suggestions
   - Review them manually in the Prompt Refinement page

### Manual Trigger

If you want to trigger analysis immediately:

```bash
curl -X POST http://localhost:8000/auto-improvement/trigger
```

## Best Practices

1. **Submit Feedback Consistently**: The more feedback, the better the improvements
2. **Be Specific**: Detailed feedback comments help the LLM generate better prompts
3. **Monitor Trends**: Check accuracy trends regularly to see improvements
4. **Review Suggestions**: Even if auto-applied, review the improvement history

## Files Created

- `accuracy_tracking.json`: Tracks accuracy over time
- `prompt_refinement_history.json`: History of all prompt improvements

These files are automatically created and updated by the system.

