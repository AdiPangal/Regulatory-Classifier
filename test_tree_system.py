#!/usr/bin/env python3
"""Test script for the configurable decision tree system."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.prompt_library import PromptLibrary

def test_tree_evaluation():
    """Test the decision tree evaluation with various scenarios."""
    
    print("="*70)
    print("Testing Configurable Decision Tree System")
    print("="*70)
    
    # Initialize prompt library (should auto-load tree from config/prompt_tree.json)
    library = PromptLibrary()
    
    # Test Case 1: Safety issues (should return "safety_focused")
    print("\n1. Testing safety-focused scenario...")
    detections_1 = {
        "safety_issues": [
            {"page": 1, "is_unsafe": True, "primary_concerns": ["child_safety_concern"]}
        ],
        "pii_detections": [],
        "keyword_detections": [],
        "image_count": 0
    }
    result_1 = library.select_prompt(detections_1)
    print(f"   Result: {result_1}")
    assert result_1 == "safety_focused", f"Expected 'safety_focused', got '{result_1}'"
    print("   ✅ PASS")
    
    # Test Case 2: High-risk PII (should return "pii_focused")
    print("\n2. Testing high-risk PII scenario...")
    detections_2 = {
        "safety_issues": [],
        "pii_detections": [
            {
                "page": 1,
                "count": 1,
                "matches": [
                    {"type": "US_SSN", "text": "123-45-6789"}
                ]
            }
        ],
        "keyword_detections": [],
        "image_count": 0
    }
    result_2 = library.select_prompt(detections_2)
    print(f"   Result: {result_2}")
    assert result_2 == "pii_focused", f"Expected 'pii_focused', got '{result_2}'"
    print("   ✅ PASS")
    
    # Test Case 3: Images + keywords (should return "image_focused")
    print("\n3. Testing images + keywords scenario...")
    detections_3 = {
        "safety_issues": [],
        "pii_detections": [],
        "keyword_detections": [
            {
                "page": 1,
                "count": 1,
                "matches": [
                    {"type": "DEFENSE", "keyword": "stealth fighter"}
                ]
            }
        ],
        "image_count": 5
    }
    result_3 = library.select_prompt(detections_3)
    print(f"   Result: {result_3}")
    assert result_3 == "image_focused", f"Expected 'image_focused', got '{result_3}'"
    print("   ✅ PASS")
    
    # Test Case 4: Driver's license (should NOT trigger pii_focused, should go to base)
    print("\n4. Testing driver's license exclusion...")
    detections_4 = {
        "safety_issues": [],
        "pii_detections": [
            {
                "page": 1,
                "count": 1,
                "matches": [
                    {"type": "US_DRIVER_LICENSE", "text": "D1234567"}
                ]
            }
        ],
        "keyword_detections": [],
        "image_count": 0
    }
    result_4 = library.select_prompt(detections_4)
    print(f"   Result: {result_4}")
    assert result_4 == "base_classification", f"Expected 'base_classification', got '{result_4}'"
    print("   ✅ PASS")
    
    # Test Case 5: Default case (should return "base_classification")
    print("\n5. Testing default scenario...")
    detections_5 = {
        "safety_issues": [],
        "pii_detections": [],
        "keyword_detections": [],
        "image_count": 0
    }
    result_5 = library.select_prompt(detections_5)
    print(f"   Result: {result_5}")
    assert result_5 == "base_classification", f"Expected 'base_classification', got '{result_5}'"
    print("   ✅ PASS")
    
    print("\n" + "="*70)
    print("All tests passed! ✅")
    print("="*70)
    
    # Check if tree was loaded
    if library.decision_tree:
        print("\n✅ Decision tree loaded successfully from config")
    else:
        print("\n⚠️  Decision tree not loaded, using hardcoded fallback")

if __name__ == "__main__":
    try:
        test_tree_evaluation()
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

