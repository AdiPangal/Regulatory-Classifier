#!/usr/bin/env python3
"""Test script for bulk feedback endpoint.

This script demonstrates how to use the bulk feedback endpoint to automatically
improve the model by providing a list of text samples with their correct classifications.
"""
import requests
import json
import os

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# Example bulk feedback data
# You can modify this list with your own text samples and correct classifications
bulk_data = {
    "items": [
        {
            "text": "This is a public marketing brochure for our new product line. It contains general information about features and benefits that we want to share with potential customers.",
            "correct_classification": "Public",
            "document_name": "Marketing Brochure"
        },
        {
            "text": "Internal memo: Q4 financial results show revenue of $2.5M. Please keep this confidential until public announcement next week.",
            "correct_classification": "Confidential",
            "document_name": "Internal Financial Memo"
        },
        {
            "text": "Customer record: John Doe, SSN: 123-45-6789, Credit Card: 4532-1234-5678-9010, Address: 123 Main St, City: Anytown.",
            "correct_classification": "Highly Sensitive",
            "document_name": "Customer PII Record"
        },
        {
            "text": "This document contains proprietary schematics for our next-generation defense equipment. Top secret design specifications.",
            "correct_classification": "Highly Sensitive",
            "document_name": "Defense Equipment Schematics"
        },
        {
            "text": "Product announcement: We're excited to launch our new smartphone with advanced features. Pre-order now!",
            "correct_classification": "Public",
            "document_name": "Product Announcement"
        }
    ],
    "reviewer_id": "test_user",
    "auto_trigger_improvement": True
}

def test_bulk_feedback():
    """Test the bulk feedback endpoint."""
    print("=" * 60)
    print("Testing Bulk Feedback Endpoint")
    print("=" * 60)
    print(f"\nSubmitting {len(bulk_data['items'])} text samples...")
    print(f"API Base URL: {API_BASE}\n")
    
    try:
        response = requests.post(
            f"{API_BASE}/feedback/bulk",
            json=bulk_data,
            headers={"Content-Type": "application/json"},
            timeout=120  # Allow time for classification
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Bulk feedback submitted successfully!")
            print("\n" + "=" * 60)
            print("SUMMARY")
            print("=" * 60)
            print(f"   Total items: {result['total']}")
            print(f"   Successful: {result['successful']}")
            print(f"   Errors: {result['errors']}")
            print(f"   Corrections: {result['corrections']}")
            print(f"   Confirmations: {result['confirmations']}")
            print(f"   Improvement triggered: {result['improvement_triggered']}")
            
            print("\n" + "=" * 60)
            print("DETAILED RESULTS")
            print("=" * 60)
            for r in result['results']:
                match_icon = "✅" if r['match'] else "❌"
                status = "CORRECT" if r['match'] else "INCORRECT"
                print(f"\n{match_icon} [{status}] {r['document_name']}")
                print(f"   Original: {r['original_classification']}")
                print(f"   Expected: {r['correct_classification']}")
                if not r['match']:
                    print(f"   ⚠️  Classification mismatch - feedback submitted")
            
            if result['error_details']:
                print("\n" + "=" * 60)
                print("ERRORS")
                print("=" * 60)
                for e in result['error_details']:
                    print(f"\n   Index {e['index']}: {e['error']}")
                    print(f"   Text preview: {e['text_preview']}")
            
            print("\n" + "=" * 60)
            print("NEXT STEPS")
            print("=" * 60)
            print("1. Check the auto-improvement status:")
            print(f"   GET {API_BASE}/auto-improvement/status")
            print("\n2. View refinement history:")
            print(f"   GET {API_BASE}/refinement/history")
            print("\n3. View pending suggestions:")
            print(f"   GET {API_BASE}/refinement/suggestions")
            
            return True
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
    success = test_bulk_feedback()
    exit(0 if success else 1)
