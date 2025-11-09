# Bulk Feedback Guide

This guide explains how to use the bulk feedback feature to automatically improve the model by providing a list of text samples with their correct classifications.

## Overview

The bulk feedback endpoint (`POST /feedback/bulk`) allows you to:
1. Submit multiple text samples with their correct classifications
2. Automatically classify each text sample
3. Compare classifications with correct answers
4. Submit feedback automatically (corrections or confirmations)
5. Optionally trigger prompt improvement

## API Endpoint

```
POST /feedback/bulk
```

## Request Format

```json
{
  "items": [
    {
      "text": "Your text sample here",
      "correct_classification": "Public",
      "document_name": "Optional name for this sample"
    },
    {
      "text": "Another text sample",
      "correct_classification": "Confidential",
      "document_name": "Another sample"
    }
  ],
  "reviewer_id": "optional_reviewer_id",
  "auto_trigger_improvement": true
}
```

### Fields

- **items** (required): List of text samples with correct classifications
  - **text** (required): The text to classify
  - **correct_classification** (required): One of "Public", "Confidential", "Highly Sensitive", or "Unsafe"
  - **document_name** (optional): A name/identifier for this sample
- **reviewer_id** (optional): Identifier for who is providing the feedback
- **auto_trigger_improvement** (optional, default: true): Whether to trigger prompt improvement after submission

## Response Format

```json
{
  "message": "Bulk feedback submitted: 5/5 successful",
  "total": 5,
  "successful": 5,
  "errors": 0,
  "corrections": 2,
  "confirmations": 3,
  "results": [
    {
      "index": 0,
      "feedback_id": "uuid",
      "original_classification": "Public",
      "correct_classification": "Public",
      "match": true,
      "document_name": "Marketing Brochure"
    }
  ],
  "error_details": [],
  "improvement_triggered": true
}
```

## Usage Examples

### Python Example

```python
import requests

API_BASE = "http://localhost:8000"

bulk_data = {
    "items": [
        {
            "text": "This is a public marketing document.",
            "correct_classification": "Public",
            "document_name": "Marketing Doc"
        },
        {
            "text": "Internal memo: Keep confidential.",
            "correct_classification": "Confidential",
            "document_name": "Internal Memo"
        },
        {
            "text": "SSN: 123-45-6789, Credit Card: 4532-1234-5678-9010",
            "correct_classification": "Highly Sensitive",
            "document_name": "PII Document"
        }
    ],
    "reviewer_id": "my_user_id",
    "auto_trigger_improvement": True
}

response = requests.post(
    f"{API_BASE}/feedback/bulk",
    json=bulk_data
)

result = response.json()
print(f"Submitted: {result['successful']}/{result['total']}")
print(f"Corrections: {result['corrections']}")
print(f"Confirmations: {result['confirmations']}")
```

### cURL Example

```bash
curl -X POST http://localhost:8000/feedback/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {
        "text": "This is a public document",
        "correct_classification": "Public",
        "document_name": "Test 1"
      },
      {
        "text": "Internal confidential memo",
        "correct_classification": "Confidential",
        "document_name": "Test 2"
      }
    ],
    "auto_trigger_improvement": true
  }'
```

### Using the Test Script

A test script is provided at `test_bulk_feedback.py`:

```bash
python3 test_bulk_feedback.py
```

You can modify the `bulk_data` dictionary in the script to include your own text samples.

## How It Works

1. **Classification**: Each text sample is classified using the current model
2. **Comparison**: The classification is compared with the correct classification
3. **Feedback Submission**: 
   - If they match → "confirmation" feedback is submitted
   - If they don't match → "correction" feedback is submitted
4. **Prompt Improvement**: If `auto_trigger_improvement` is true and the feedback threshold is met, the system automatically analyzes feedback and improves prompts

## Best Practices

1. **Provide diverse examples**: Include samples from all four categories
2. **Use clear text**: Make sure your text samples are representative of real documents
3. **Batch size**: Submit 10-50 samples at a time for best results
4. **Review results**: Check the response to see which classifications were correct/incorrect
5. **Monitor improvement**: Use `/auto-improvement/status` to track model improvements

## Checking Improvement Status

After submitting bulk feedback, you can check if improvements were applied:

```bash
# Get auto-improvement status
curl http://localhost:8000/auto-improvement/status

# Get refinement history
curl http://localhost:8000/refinement/history

# Get pending suggestions
curl http://localhost:8000/refinement/suggestions
```

## Tips

- Start with a small batch (5-10 samples) to test
- Focus on areas where the model is making mistakes
- Include edge cases and boundary examples
- Submit feedback regularly to continuously improve the model
- The system needs at least 10 feedback submissions before triggering automatic improvement (configurable via `AUTO_IMPROVEMENT_FEEDBACK_THRESHOLD`)

