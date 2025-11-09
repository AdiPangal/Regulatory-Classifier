"""Test script for the Regulatory Classifier API."""
import requests
import json
from pathlib import Path


# API base URL
BASE_URL = "http://localhost:8000"


def test_health_check():
    """Test the health check endpoint."""
    print("Testing health check...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")
    return response.status_code == 200


def test_classify_document(file_path: str):
    """Test document classification endpoint.
    
    Args:
        file_path: Path to the PDF or image file to classify
    """
    print(f"Testing document classification with: {file_path}")
    
    if not Path(file_path).exists():
        print(f"Error: File not found: {file_path}\n")
        return None
    
    # Upload and classify the document
    with open(file_path, "rb") as f:
        files = {"file": (Path(file_path).name, f, "application/pdf")}
        response = requests.post(f"{BASE_URL}/classify", files=files)
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print("\n=== Classification Result ===")
        print(f"Document ID: {result.get('document_id')}")
        print(f"Document Name: {result.get('document_name')}")
        print(f"Pages: {result.get('pages')}")
        print(f"Images: {result.get('images')}")
        print(f"Classification: {result.get('classification')}")
        print(f"Confidence: {result.get('confidence')}")
        print(f"Safety Check: {result.get('safety_check')}")
        print(f"Is Legible: {result.get('is_legible')}")
        print(f"Needs Review: {result.get('needs_review')}")
        print(f"\nReasons: {result.get('reasons', [])}")
        print(f"\nCitations: {json.dumps(result.get('citations', []), indent=2)}")
        print(f"\nReasoning: {result.get('reasoning', '')[:500]}...")
        print("=" * 50)
        return result
    else:
        print(f"Error: {response.text}\n")
        return None


def test_batch_classify(file_paths: list):
    """Test batch classification endpoint.
    
    Args:
        file_paths: List of paths to PDF or image files
    """
    print(f"Testing batch classification with {len(file_paths)} files...")
    
    # Prepare files
    files = []
    for file_path in file_paths:
        if Path(file_path).exists():
            files.append(("files", (Path(file_path).name, open(file_path, "rb"), "application/pdf")))
        else:
            print(f"Warning: File not found: {file_path}")
    
    if not files:
        print("Error: No valid files to upload\n")
        return None
    
    # Upload files
    response = requests.post(f"{BASE_URL}/classify/batch", files=files)
    
    # Close file handles
    for _, (_, file_handle, _) in files:
        file_handle.close()
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        batch_id = result.get("batch_id")
        print(f"Batch ID: {batch_id}")
        print(f"Status: {result.get('status')}")
        print(f"Total: {result.get('total')}")
        print("\nChecking batch status...")
        
        # Poll for completion
        import time
        max_wait = 300  # 5 minutes max
        wait_time = 0
        while wait_time < max_wait:
            time.sleep(2)
            status_response = requests.get(f"{BASE_URL}/batch/{batch_id}/status")
            if status_response.status_code == 200:
                status = status_response.json()
                print(f"Progress: {status.get('completed')}/{status.get('total')}")
                if status.get("status") == "completed":
                    print("\n=== Batch Results ===")
                    for i, res in enumerate(status.get("results", []), 1):
                        print(f"\nDocument {i}:")
                        print(f"  Name: {res.get('document_name')}")
                        print(f"  Classification: {res.get('classification')}")
                        print(f"  Confidence: {res.get('confidence')}")
                    if status.get("errors"):
                        print(f"\nErrors: {status.get('errors')}")
                    print("=" * 50)
                    return status
            wait_time += 2
        
        print("Timeout waiting for batch completion\n")
        return None
    else:
        print(f"Error: {response.text}\n")
        return None


def test_feedback(document_id: str, original_classification: str, corrected_classification: str = None):
    """Test submitting HITL feedback.
    
    Args:
        document_id: Document ID from classification
        original_classification: Original classification from system
        corrected_classification: Corrected classification (if correction)
    """
    print("Testing HITL feedback submission...")
    
    feedback_data = {
        "document_id": document_id,
        "original_classification": original_classification,
        "corrected_classification": corrected_classification,
        "feedback_type": "correction" if corrected_classification else "confirmation",
        "feedback_text": "Test feedback from automated test"
    }
    
    response = requests.post(
        f"{BASE_URL}/feedback",
        json=feedback_data
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Feedback ID: {result.get('feedback_id')}")
        print(f"Message: {result.get('message')}\n")
        return result
    else:
        print(f"Error: {response.text}\n")
        return None


def test_get_feedback_stats():
    """Test getting feedback statistics."""
    print("Testing feedback statistics...")
    response = requests.get(f"{BASE_URL}/feedback/stats")
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        stats = response.json()
        print("\n=== Feedback Statistics ===")
        print(json.dumps(stats, indent=2))
        print("=" * 50)
        return stats
    else:
        print(f"Error: {response.text}\n")
        return None


def main():
    """Main test function."""
    print("=" * 50)
    print("Regulatory Classifier API Test Suite")
    print("=" * 50)
    print()
    
    # Test 1: Health check
    if not test_health_check():
        print("Health check failed. Is the server running?")
        return
    
    # Test 2: Classify a document (if file provided)
    import sys
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        result = test_classify_document(file_path)
        
        if result:
            # Test 3: Submit feedback
            doc_id = result.get("document_id")
            classification = result.get("classification")
            test_feedback(doc_id, classification)
            
            # Test 4: Get feedback for document
            print(f"Getting feedback for document {doc_id}...")
            response = requests.get(f"{BASE_URL}/feedback/{doc_id}")
            if response.status_code == 200:
                feedback = response.json()
                print(f"Feedback records: {len(feedback.get('feedback', []))}\n")
    else:
        print("Usage: python test_backend.py <path_to_pdf_file>")
        print("\nExample:")
        print("  python test_backend.py test_document.pdf")
        print("\nOr test with multiple files for batch processing:")
        print("  python test_backend.py file1.pdf file2.pdf file3.pdf")
    
    # Test 5: Get overall stats
    test_get_feedback_stats()
    
    print("\nTest suite completed!")


if __name__ == "__main__":
    main()

