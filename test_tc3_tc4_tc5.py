#!/usr/bin/env python3
"""Test script to classify TC3, TC4, and TC5 documents.

These should all be classified as Confidential, not Highly Sensitive.
"""
import requests
import os
import sys

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

test_files = [
    "TC3_Sample_Internal_Memo",
    "TC4_ Stealth_Fighter_With_Part_Names",
    "TC5_Testing_Multiple_Non_Compliance_Categorization"
]

def test_classification(filename_base):
    """Test classification of a document."""
    # Try to find the file
    possible_paths = [
        f"uploads/{filename_base}.pdf",
        f"{filename_base}.pdf",
        f"uploads/{filename_base}",
        filename_base
    ]
    
    file_path = None
    for path in possible_paths:
        if os.path.exists(path):
            file_path = path
            break
    
    if not file_path:
        print(f"❌ Could not find {filename_base}.pdf")
        return False
    
    print(f"\n{'='*60}")
    print(f"Testing: {filename_base}")
    print(f"File: {file_path}")
    print(f"{'='*60}")
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/pdf')}
            response = requests.post(
                f"{API_BASE}/classify",
                files=files,
                timeout=120
            )
        
        if response.status_code == 200:
            result = response.json()
            classification = result.get('classification', 'Unknown')
            confidence = result.get('confidence', 0.0)
            safety_check = result.get('safety_check', 'Unknown')
            
            print(f"\n✅ Classification successful")
            print(f"   Classification: {classification}")
            print(f"   Confidence: {confidence:.2%}")
            print(f"   Safety Check: {safety_check}")
            
            # Check if correct
            if classification == "Confidential":
                print(f"   ✅ CORRECT: Classified as Confidential")
                return True
            else:
                print(f"   ❌ INCORRECT: Expected 'Confidential', got '{classification}'")
                print(f"   Reasoning: {result.get('reasoning', 'N/A')[:200]}...")
                return False
        else:
            print(f"❌ Error: HTTP {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing TC3, TC4, and TC5 classifications")
    print("Expected: All should be 'Confidential'")
    print(f"API Base: {API_BASE}\n")
    
    results = []
    for filename in test_files:
        success = test_classification(filename)
        results.append((filename, success))
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for filename, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {filename}")
    
    all_passed = all(success for _, success in results)
    if all_passed:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed")
    
    sys.exit(0 if all_passed else 1)

