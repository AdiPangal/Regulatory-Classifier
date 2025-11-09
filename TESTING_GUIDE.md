# Automated Testing Guide

This guide explains how to use the automated test script to test the API repeatedly without manual intervention.

## Quick Start

### 1. Create a Test PDF (Optional)

If you don't have a test PDF, create one:

```bash
python create_test_pdf.py
```

This will create a `test.pdf` file in the current directory.

### 2. Start the Server

In one terminal, start the server:

```bash
python main.py
```

Keep this running.

### 3. Run Tests

In another terminal, run the test script:

```bash
# Test with a specific PDF
python run_tests.py /path/to/your/document.pdf

# Or if you created test.pdf
python run_tests.py test.pdf
```

## How It Works

The `run_tests.py` script:

1. **Checks server health** - Verifies the server is running
2. **Tests classification** - Uploads a PDF and tests the classification endpoint
3. **Shows results** - Displays formatted results with colors
4. **Retries on failure** - Automatically retries up to 3 times if there are errors
5. **Shows detailed errors** - Provides clear error messages to help debug issues

## Features

- ✅ Automatic retry logic
- ✅ Color-coded output (green=success, red=error, yellow=warning, blue=info)
- ✅ Detailed error reporting
- ✅ Server health checking
- ✅ Formatted result display

## Example Output

```
============================================================
Regulatory Classifier API Test Suite
============================================================

ℹ Server is running and healthy
✓ Server is running and healthy

ℹ Attempt 1/3
ℹ Testing classification with: test.pdf
ℹ Sending request to /classify endpoint...
ℹ Response status: 200
✓ Classification successful!

============================================================
Classification Results:
============================================================
Document ID: 550e8400-e29b-41d4-a716-446655440000
Document Name: test.pdf
Pages: 1
Images: 0
Classification: Public
Confidence: 0.85
Safety Check: Safe
Is Legible: True
Needs Review: False

Reasons:
  - Document contains only public marketing content
  - No PII detected

Citations: 0 found
============================================================

✓ All tests passed!
```

## Troubleshooting

### "Cannot connect to server"
- Make sure the server is running: `python main.py`
- Check that the server is on `http://localhost:8000`
- Verify the BASE_URL in `run_tests.py` matches your server

### "Request timed out"
- The document might be too large
- Processing might be slow (first run downloads models)
- Try with a smaller PDF file

### "Classification failed"
- Check the error message for details
- Common issues:
  - Poppler not installed (see INSTALL_POPPLER.md)
  - API keys missing or invalid
  - PDF file corrupted

## Continuous Testing

You can run the test script in a loop to test repeatedly:

```bash
# Test 10 times
for i in {1..10}; do
    echo "Test run $i"
    python run_tests.py test.pdf
    sleep 5
done
```

Or use watch (Linux/macOS):

```bash
watch -n 10 python run_tests.py test.pdf
```

This will run the test every 10 seconds.

## Integration with Development

The test script is designed to be run repeatedly during development:

1. Make code changes
2. Restart server (if needed)
3. Run `python run_tests.py test.pdf`
4. Check results
5. Fix any errors
6. Repeat

This workflow allows you to quickly iterate and fix issues without manually testing each time.

