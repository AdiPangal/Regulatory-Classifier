# Setup Instructions

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- **Poppler** (required for PDF processing) - See installation instructions below

## Installation Steps

### 1. Clone or navigate to the project directory

```bash
cd RegulatoryClassifier
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

**Note:** Some dependencies may require additional system libraries:

### System Dependencies

#### Poppler (REQUIRED for PDF processing)

Poppler is required for `pdf2image` to convert PDFs to images. Install it based on your OS:

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install poppler-utils
```

**CentOS/RHEL/Fedora:**
```bash
sudo yum install poppler-utils
# or for newer versions:
sudo dnf install poppler-utils
```

**macOS:**
```bash
brew install poppler
```

**Windows:**
- Download from: https://github.com/oschwartz10612/poppler-windows/releases
- Extract and add the `bin` folder to your system PATH
- Or use conda: `conda install -c conda-forge poppler`

**Verify installation:**
```bash
pdftoppm -v  # Should show version information
```

#### Other Dependencies

- **PaddleOCR**: You may need to install system dependencies. See [PaddleOCR installation guide](https://github.com/PaddlePaddle/PaddleOCR/blob/release/2.7/doc/doc_en/installation_en.md)
- **Presidio**: You may need to download spaCy models:
  ```bash
  python -m spacy download en_core_web_sm
  ```

### 4. Set up environment variables

Create a `.env` file in the project root (copy from `.env.example`):

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```env
GEMINI_API_KEY=your_gemini_api_key_here
MISTRAL_API_KEY=your_mistral_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

**Where to get API keys:**
- **Gemini API Key**: Get from [Google AI Studio](https://makersuite.google.com/app/apikey)
- **Mistral API Key**: Get from [Mistral AI Platform](https://console.mistral.ai/)
- **OpenAI API Key**: Get from [OpenAI Platform](https://platform.openai.com/api-keys)

### 5. Create necessary directories

```bash
mkdir -p uploads
```

## Running the Application

### Start the server

```bash
python main.py
```

Or using uvicorn directly:

```bash
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- **API Base URL**: `http://localhost:8000`
- **API Documentation**: `http://localhost:8000/docs` (Swagger UI)
- **Alternative Docs**: `http://localhost:8000/redoc` (ReDoc)

## API Endpoints

### Main Endpoints

- `POST /classify` - Classify a single document
- `POST /classify/batch` - Classify multiple documents (batch processing)
- `GET /batch/{batch_id}/status` - Get batch processing status

### HITL Feedback Endpoints

- `POST /feedback` - Submit feedback
- `GET /feedback/{document_id}` - Get feedback for a document
- `GET /feedback/pending` - Get pending reviews
- `GET /feedback/stats` - Get accuracy statistics
- `GET /feedback/prompt-performance` - Get prompt performance metrics
- `POST /feedback/{feedback_id}/resolve` - Mark feedback as resolved

### Utility Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /models` - Get model information

## Testing the API

### Using curl

```bash
# Classify a document
curl -X POST "http://localhost:8000/classify" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test_document.pdf"
```

### Using Python requests

```python
import requests

url = "http://localhost:8000/classify"
files = {"file": open("test_document.pdf", "rb")}
response = requests.post(url, files=files)
print(response.json())
```

## Troubleshooting

### Common Issues

1. **PaddleOCR installation issues**
   - Make sure you have the required system dependencies
   - On Linux: `sudo apt-get install libgl1-mesa-glx libglib2.0-0`
   - See PaddleOCR documentation for more details

2. **Presidio/spaCy model not found**
   - Run: `python -m spacy download en_core_web_sm`

3. **API key errors**
   - Make sure your `.env` file is in the project root
   - Verify API keys are correct and have proper permissions

4. **Port already in use**
   - Change the port in `.env` file or use a different port:
     ```bash
     uvicorn src.api:app --port 8001
     ```

## Project Structure

```
RegulatoryClassifier/
├── src/
│   ├── __init__.py
│   ├── api.py                 # FastAPI endpoints
│   ├── classification_pipeline.py  # Main pipeline
│   ├── preprocessing.py       # PDF/OCR processing
│   ├── pii_detection.py       # PII detection
│   ├── safety_detection.py    # Safety/content moderation
│   ├── prompt_library.py      # Prompt management
│   ├── llm_integration.py     # LLM API calls
│   └── hitl_feedback.py       # HITL feedback system
├── config.py                  # Configuration
├── main.py                    # Application entry point
├── requirements.txt           # Python dependencies
├── .env                       # Environment variables (create from .env.example)
└── README.md                  # Project documentation
```

## Next Steps

1. Test with sample documents
2. Review classification results
3. Submit HITL feedback to improve accuracy
4. Monitor prompt performance metrics
5. Adjust prompts based on feedback

