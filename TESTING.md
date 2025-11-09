# Testing Guide for Regulatory Classifier Backend

## Quick Start

### 1. Start the Server

First, make sure your `.env` file is configured with your API keys:

```bash
# Make sure you have your API keys in .env
GEMINI_API_KEY=your_key_here
MISTRAL_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
```

Then start the server:

```bash
python main.py
```

Or using uvicorn directly:

```bash
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

The server will be available at `http://localhost:8000`

### 2. Test Using the Interactive API Documentation

The easiest way to test is using the built-in Swagger UI:

1. Open your browser and go to: `http://localhost:8000/docs`
2. You'll see an interactive API documentation
3. Click on `POST /classify` endpoint
4. Click "Try it out"
5. Click "Choose File" and select a PDF file
6. Click "Execute"
7. View the response with classification results

### 3. Test Using cURL

#### Single Document Classification

```bash
curl -X POST "http://localhost:8000/classify" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/document.pdf"
```

#### With Optional Document ID

```bash
curl -X POST "http://localhost:8000/classify" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/document.pdf" \
  -F "document_id=my-custom-id-123"
```

### 4. Test Using Python Script

Use the provided test script:

```bash
# Install requests if not already installed
pip install requests

# Run the test script with a PDF file
python test_backend.py /path/to/your/document.pdf
```

Or use Python requests directly:

```python
import requests

url = "http://localhost:8000/classify"
file_path = "/path/to/your/document.pdf"

with open(file_path, "rb") as f:
    files = {"file": (file_path, f, "application/pdf")}
    response = requests.post(url, files=files)

print(response.json())
```

### 5. Test Batch Processing

#### Using cURL

```bash
curl -X POST "http://localhost:8000/classify/batch" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@/path/to/doc1.pdf" \
  -F "files=@/path/to/doc2.pdf" \
  -F "files=@/path/to/doc3.pdf"
```

This will return a `batch_id`. Check status with:

```bash
curl -X GET "http://localhost:8000/batch/{batch_id}/status"
```

#### Using Python

```python
import requests
import time

url = "http://localhost:8000/classify/batch"
files = [
    ("files", ("doc1.pdf", open("doc1.pdf", "rb"), "application/pdf")),
    ("files", ("doc2.pdf", open("doc2.pdf", "rb"), "application/pdf")),
]

response = requests.post(url, files=files)
batch_id = response.json()["batch_id"]

# Check status
while True:
    status = requests.get(f"http://localhost:8000/batch/{batch_id}/status").json()
    print(f"Progress: {status['completed']}/{status['total']}")
    if status["status"] == "completed":
        print("Results:", status["results"])
        break
    time.sleep(2)
```

## API Endpoints

### Main Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Root endpoint - API info |
| `/health` | GET | Health check |
| `/classify` | POST | Classify a single document |
| `/classify/batch` | POST | Classify multiple documents |
| `/batch/{batch_id}/status` | GET | Get batch processing status |

### HITL Feedback Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/feedback` | POST | Submit feedback |
| `/feedback/{document_id}` | GET | Get feedback for a document |
| `/feedback/pending` | GET | Get pending reviews |
| `/feedback/stats` | GET | Get accuracy statistics |
| `/feedback/prompt-performance` | GET | Get prompt performance metrics |

### Example Response

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "document_name": "test_document.pdf",
  "pages": 3,
  "images": 2,
  "classification": "Highly Sensitive",
  "confidence": 0.92,
  "reasons": [
    "Detected SSN pattern on page 2",
    "Contains address and bank details"
  ],
  "citations": [
    {
      "page": 2,
      "snippet": "SSN: 123-45-6789",
      "type": "PII"
    }
  ],
  "safety_check": "Safe",
  "is_legible": true,
  "average_confidence_ocr": 0.95,
  "needs_review": false,
  "models_used": {
    "primary": "gemini-1.5-flash",
    "secondary": "mistral-small"
  },
  "consensus": true,
  "reasoning": "The document contains personally identifiable information...",
  "detection_summary": {
    "pii_count": 3,
    "keyword_count": 0,
    "unsafe_pages": []
  },
  "timestamp": "2024-01-15T10:30:00.000000",
  "prompt_used": "pii_focused"
}
```

## Testing Different Document Types

### Test Case 1: Public Marketing Document
```bash
python test_backend.py test_cases/TC1_public_marketing.pdf
```

### Test Case 2: Employment Application (PII)
```bash
python test_backend.py test_cases/TC2_employment_application.pdf
```

### Test Case 3: Internal Memo
```bash
python test_backend.py test_cases/TC3_internal_memo.pdf
```

### Test Case 4: Stealth Fighter Image
```bash
python test_backend.py test_cases/TC4_stealth_fighter.jpg
```

### Test Case 5: Multiple Non-compliance
```bash
python test_backend.py test_cases/TC5_mixed_content.pdf
```

## Submitting HITL Feedback

After classifying a document, you can submit feedback to improve the system:

```python
import requests

feedback_data = {
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "original_classification": "Confidential",
    "corrected_classification": "Highly Sensitive",
    "feedback_type": "correction",
    "feedback_text": "This should be Highly Sensitive due to SSN",
    "reviewer_id": "reviewer_001"
}

response = requests.post("http://localhost:8000/feedback", json=feedback_data)
print(response.json())
```

## Troubleshooting

### Server won't start
- Check that all dependencies are installed: `pip install -r requirements.txt`
- Verify your `.env` file has all required API keys
- Check if port 8000 is already in use

### Classification fails
- Verify API keys are valid and have sufficient credits
- Check that the PDF file is not corrupted
- Ensure the file is not too large (default max: 50MB)

### PaddleOCR errors
- Make sure PaddleOCR models are downloaded (first run will download automatically)
- Check that you have sufficient disk space for model files

### Import errors
- Make sure you're running from the project root directory
- Verify virtual environment is activated
- Try: `pip install -r requirements.txt --upgrade`

## Performance Tips

1. **First Run**: The first classification will be slower as PaddleOCR downloads models
2. **Batch Processing**: Use batch endpoints for multiple documents
3. **Caching**: Models are cached after first use, subsequent runs are faster
4. **API Limits**: Be aware of rate limits on Gemini, Mistral, and OpenAI APIs

## Next Steps

1. Test with your own documents
2. Review classification results
3. Submit HITL feedback for incorrect classifications
4. Monitor feedback statistics to track accuracy improvements
5. Adjust prompts based on feedback performance metrics

