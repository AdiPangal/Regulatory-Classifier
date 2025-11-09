"""Automated test script for the Regulatory Classifier API.
Run this script to test the API with a test PDF file.
The script will run tests repeatedly until all pass or show clear errors.
"""
import requests
import json
import time
import sys
from pathlib import Path
from typing import Optional, Dict, Any


# Configuration
BASE_URL = "http://localhost:8000"
TEST_PDF_PATH = None  # Will be set from command line or use default
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_success(msg: str):
    """Print success message."""
    print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")


def print_error(msg: str):
    """Print error message."""
    print(f"{Colors.RED}✗ {msg}{Colors.RESET}")


def print_warning(msg: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.RESET}")


def print_info(msg: str):
    """Print info message."""
    print(f"{Colors.BLUE}ℹ {msg}{Colors.RESET}")


def check_server_health() -> bool:
    """Check if the server is running and healthy."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print_success("Server is running and healthy")
            return True
        else:
            print_error(f"Server returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_error("Cannot connect to server. Is it running?")
        print_info(f"Start the server with: python main.py")
        return False
    except Exception as e:
        print_error(f"Health check failed: {str(e)}")
        return False


def test_classify_document(file_path: str, document_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Test the classify endpoint with a PDF file.
    
    Args:
        file_path: Path to the PDF file
        document_id: Optional document ID
        
    Returns:
        Classification result or None if failed
    """
    print_info(f"Testing classification with: {file_path}")
    
    if not Path(file_path).exists():
        print_error(f"File not found: {file_path}")
        return None
    
    try:
        # Prepare the request
        with open(file_path, "rb") as f:
            files = {"file": (Path(file_path).name, f, "application/pdf")}
            data = {}
            # Only include document_id in form data if provided
            if document_id and document_id.strip():
                data["document_id"] = document_id
            
            # Make the request
            print_info("Sending request to /classify endpoint...")
            # Use files parameter for file upload, data parameter for form fields
            if data:
                response = requests.post(
                    f"{BASE_URL}/classify",
                    files=files,
                    data=data,
                    timeout=120  # 2 minutes timeout for processing
                )
            else:
                # If no form data, just send the file
                response = requests.post(
                    f"{BASE_URL}/classify",
                    files=files,
                    timeout=120
                )
        
        print_info(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print_success("Classification successful!")
            print("\n" + "="*60)
            print(f"{Colors.BOLD}Classification Results:{Colors.RESET}")
            print("="*60)
            print(f"Document ID: {result.get('document_id')}")
            print(f"Document Name: {result.get('document_name')}")
            print(f"Pages: {result.get('pages')}")
            print(f"Images: {result.get('images')}")
            print(f"Classification: {Colors.BOLD}{result.get('classification')}{Colors.RESET}")
            print(f"Confidence: {result.get('confidence')}")
            print(f"Safety Check: {result.get('safety_check')}")
            print(f"Is Legible: {result.get('is_legible')}")
            print(f"Needs Review: {result.get('needs_review')}")
            print(f"\nReasons:")
            for reason in result.get('reasons', []):
                print(f"  - {reason}")
            print(f"\nCitations: {len(result.get('citations', []))} found")
            if result.get('citations'):
                for citation in result.get('citations', [])[:5]:  # Show first 5
                    print(f"  - Page {citation.get('page')}: {citation.get('type')} - {citation.get('snippet', '')[:50]}...")
            print("="*60 + "\n")
            return result
        else:
            print_error(f"Classification failed with status {response.status_code}")
            try:
                error_detail = response.json()
                print_error(f"Error details: {json.dumps(error_detail, indent=2)}")
            except:
                print_error(f"Error response: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print_error("Request timed out. The document might be too large or processing is slow.")
        return None
    except Exception as e:
        print_error(f"Request failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def run_tests(file_path: str, max_attempts: int = MAX_RETRIES):
    """Run tests with retry logic.
    
    Args:
        file_path: Path to test PDF file
        max_attempts: Maximum number of attempts
    """
    print(f"\n{Colors.BOLD}{'='*60}")
    print(f"Regulatory Classifier API Test Suite")
    print(f"{'='*60}{Colors.RESET}\n")
    
    # Check server health
    if not check_server_health():
        print_error("Server health check failed. Please start the server first.")
        return False
    
    print()
    
    # Test classification
    success = False
    for attempt in range(1, max_attempts + 1):
        print_info(f"Attempt {attempt}/{max_attempts}")
        result = test_classify_document(file_path)
        
        if result:
            success = True
            break
        else:
            if attempt < max_attempts:
                print_warning(f"Attempt {attempt} failed. Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                print_error("All attempts failed.")
    
    if success:
        print_success("All tests passed!")
        return True
    else:
        print_error("Tests failed. Please check the errors above.")
        return False


def main():
    """Main entry point."""
    global TEST_PDF_PATH
    
    # Get test file from command line or use default
    if len(sys.argv) > 1:
        TEST_PDF_PATH = sys.argv[1]
    else:
        # Try to find a test PDF in common locations
        test_locations = [
            "test.pdf",
            "test_document.pdf",
            "sample.pdf",
            "test_cases/TC1_public_marketing.pdf",
            "test_cases/TC2_employment_application.pdf",
        ]
        
        for loc in test_locations:
            if Path(loc).exists():
                TEST_PDF_PATH = loc
                break
    
    if not TEST_PDF_PATH:
        print_error("No test PDF file specified or found.")
        print_info("Usage: python run_tests.py <path_to_pdf_file>")
        print_info("Example: python run_tests.py test_document.pdf")
        sys.exit(1)
    
    if not Path(TEST_PDF_PATH).exists():
        print_error(f"Test file not found: {TEST_PDF_PATH}")
        sys.exit(1)
    
    # Run tests
    success = run_tests(TEST_PDF_PATH)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

