#!/usr/bin/env python3
"""Test script to classify all TC (Test Case) documents.

Expected Classifications:
- TC1: Public
- TC2: Highly Sensitive
- TC3: Confidential
- TC4: Confidential
"""
import requests
import os
import sys

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

test_cases = [
    {
        "filename": "TC1_Sample_Public_Marketing_Document",
        "expected": "Public",
        "description": "Public marketing document"
    },
    {
        "filename": "TC2_Filled_In_Employement_Application",
        "expected": "Highly Sensitive",
        "description": "Employment application with PII"
    },
    {
        "filename": "TC3_Sample_Internal_Memo",
        "expected": "Confidential",
        "description": "Internal memo"
    },
    {
        "filename": "TC4_ Stealth_Fighter_With_Part_Names",
        "expected": "Confidential",
        "description": "Stealth fighter technical document"
    }
]

def test_classification(test_case):
    """Test classification of a document."""
    filename_base = test_case["filename"]
    expected = test_case["expected"]
    description = test_case["description"]
    
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
    
    print(f"\n{'='*70}")
    print(f"Testing: {filename_base}")
    print(f"Description: {description}")
    print(f"Expected: {expected}")
    print(f"File: {file_path}")
    print(f"{'='*70}")
    
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
            reasoning = result.get('reasoning', 'N/A')
            
            print(f"\n✅ Classification successful")
            print(f"   Classification: {classification}")
            print(f"   Confidence: {confidence:.2%}")
            print(f"   Safety Check: {safety_check}")
            
            # Check if correct
            if classification == expected:
                print(f"   ✅ CORRECT: Classified as {expected}")
                return True
            else:
                print(f"   ❌ INCORRECT: Expected '{expected}', got '{classification}'")
                print(f"\n   Reasoning (first 300 chars):")
                print(f"   {reasoning[:300]}...")
                
                # Show detection summary if available
                detection_summary = result.get('detection_summary', {})
                if detection_summary:
                    print(f"\n   Detection Summary:")
                    print(f"   - PII Count: {detection_summary.get('pii_count', 0)}")
                    print(f"   - Keyword Count: {detection_summary.get('keyword_count', 0)}")
                    print(f"   - Unsafe Pages: {detection_summary.get('unsafe_pages', [])}")
                
                return False
        else:
            print(f"❌ Error: HTTP {response.status_code}")
            print(response.text)
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error: Could not connect to {API_BASE}")
        print("   Make sure the server is running: python3 main.py")
        return False
    except requests.exceptions.Timeout:
        print("❌ Timeout: The request took too long")
        print("   This might happen if the server is processing many items")
        return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("="*70)
    print("Testing All TC Documents")
    print("="*70)
    print(f"\nAPI Base URL: {API_BASE}")
    print("\nExpected Classifications:")
    for tc in test_cases:
        print(f"  - {tc['filename']}: {tc['expected']} ({tc['description']})")
    print()
    
    results = []
    for test_case in test_cases:
        success = test_classification(test_case)
        results.append((test_case['filename'], success, test_case['expected']))
    
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    
    passed = 0
    failed = 0
    
    for filename, success, expected in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {filename} (Expected: {expected})")
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\n{'='*70}")
    print(f"Results: {passed}/{len(results)} passed, {failed}/{len(results)} failed")
    print(f"{'='*70}")
    
    if failed == 0:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print(f"\n❌ {failed} test(s) failed")
        sys.exit(1)


