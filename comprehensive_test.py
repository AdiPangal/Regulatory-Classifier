#!/usr/bin/env python3
"""Comprehensive test suite for classification accuracy."""
import json
import sys
from pathlib import Path
from typing import Dict, List
from collections import defaultdict, Counter

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.classification_pipeline import ClassificationPipeline
from config import settings


class ComprehensiveTester:
    """Comprehensive testing suite for classification system."""
    
    def __init__(self):
        """Initialize tester."""
        self.pipeline = ClassificationPipeline(
            gemini_api_key=settings.gemini_api_key,
            mistral_api_key=settings.mistral_api_key,
            openai_api_key=settings.openai_api_key,
            legibility_threshold=settings.legibility_threshold,
            enable_dual_validation=settings.enable_dual_llm_validation,
            dataset_file="document_safety_dataset.json",
            enable_few_shot=True
        )
    
    def test_dataset_accuracy(self, sample_size: int = 100) -> Dict:
        """Test accuracy on dataset examples."""
        print("\n" + "="*80)
        print("DATASET ACCURACY TEST")
        print("="*80)
        
        # Load dataset
        with open("document_safety_dataset.json", 'r') as f:
            dataset = json.load(f)
        
        if sample_size:
            import random
            dataset = random.sample(dataset, min(sample_size, len(dataset)))
        
        results = {
            "total": len(dataset),
            "correct": 0,
            "incorrect": 0,
            "by_classification": defaultdict(lambda: {"correct": 0, "total": 0}),
            "by_safety": defaultdict(lambda: {"correct": 0, "total": 0}),
            "confusion_matrix": defaultdict(lambda: defaultdict(int)),
            "errors": []
        }
        
        print(f"Testing on {len(dataset)} examples...\n")
        
        for i, example in enumerate(dataset, 1):
            if i % 10 == 0:
                print(f"  Progress: {i}/{len(dataset)}...")
            
            text = example.get("text", "")
            expected_classification = example.get("correct_classification", "Public")
            expected_safety = example.get("safety_status", "Safe")
            
            try:
                result = self.pipeline.classify_text_direct(text)
                
                predicted_classification = result.get("classification", "Public")
                predicted_safety = result.get("safety_check", "Safe")
                
                classification_correct = predicted_classification == expected_classification
                safety_correct = predicted_safety == expected_safety
                
                results["by_classification"][expected_classification]["total"] += 1
                results["by_safety"][expected_safety]["total"] += 1
                
                if classification_correct:
                    results["correct"] += 1
                    results["by_classification"][expected_classification]["correct"] += 1
                else:
                    results["incorrect"] += 1
                    results["errors"].append({
                        "text": text[:150] + "..." if len(text) > 150 else text,
                        "expected": expected_classification,
                        "predicted": predicted_classification,
                        "expected_safety": expected_safety,
                        "predicted_safety": predicted_safety,
                        "confidence": result.get("confidence", 0.0),
                        "reasoning": result.get("reasoning", "")[:200]
                    })
                
                if safety_correct:
                    results["by_safety"][expected_safety]["correct"] += 1
                
                results["confusion_matrix"][expected_classification][predicted_classification] += 1
                
            except Exception as e:
                print(f"  Error on example {i}: {e}")
                results["incorrect"] += 1
        
        results["accuracy"] = results["correct"] / results["total"] if results["total"] > 0 else 0
        
        for classification in results["by_classification"]:
            total = results["by_classification"][classification]["total"]
            correct = results["by_classification"][classification]["correct"]
            if total > 0:
                results["by_classification"][classification]["accuracy"] = correct / total
        
        for safety in results["by_safety"]:
            total = results["by_safety"][safety]["total"]
            correct = results["by_safety"][safety]["correct"]
            if total > 0:
                results["by_safety"][safety]["accuracy"] = correct / total
        
        return results
    
    def test_edge_cases(self) -> Dict:
        """Test edge cases and boundary conditions."""
        print("\n" + "="*80)
        print("EDGE CASE TEST")
        print("="*80)
        
        edge_cases = [
            {
                "text": "Marketing brochure: Buy our new product! Contact us at info@company.com. This document is proprietary and confidential.",
                "expected": "Public",
                "reason": "Marketing material with boilerplate legal text"
            },
            {
                "text": "Employment Application Form\nName: John Doe\nAddress: 123 Main St\nSSN: 123-45-6789",
                "expected": "Highly Sensitive",
                "reason": "Employment application with SSN"
            },
            {
                "text": "Internal memo: Q4 results show $2.5M revenue. Keep confidential.",
                "expected": "Confidential",
                "reason": "Internal business memo"
            },
            {
                "text": "Patient record: Jane Smith, DOB 01/01/1980, diagnosed with condition X.",
                "expected": "Highly Sensitive",
                "reason": "Medical record with patient information"
            },
            {
                "text": "Public blog post about gardening tips and techniques.",
                "expected": "Public",
                "reason": "Public educational content"
            },
            {
                "text": "Technical specification document for stealth fighter aircraft with part numbers and schematics.",
                "expected": "Confidential",
                "reason": "Technical defense documentation"
            }
        ]
        
        results = {
            "total": len(edge_cases),
            "correct": 0,
            "incorrect": 0,
            "details": []
        }
        
        for i, case in enumerate(edge_cases, 1):
            print(f"\n  Test {i}: {case['reason']}")
            print(f"    Text: {case['text'][:80]}...")
            
            try:
                result = self.pipeline.classify_text_direct(case["text"])
                predicted = result.get("classification", "Unknown")
                expected = case["expected"]
                
                is_correct = predicted == expected
                if is_correct:
                    results["correct"] += 1
                    print(f"    ✅ CORRECT: {predicted}")
                else:
                    results["incorrect"] += 1
                    print(f"    ❌ INCORRECT: Expected {expected}, got {predicted}")
                    print(f"    Confidence: {result.get('confidence', 0):.2%}")
                
                results["details"].append({
                    "case": case["reason"],
                    "expected": expected,
                    "predicted": predicted,
                    "correct": is_correct,
                    "confidence": result.get("confidence", 0.0)
                })
            except Exception as e:
                print(f"    ❌ ERROR: {e}")
                results["incorrect"] += 1
        
        results["accuracy"] = results["correct"] / results["total"] if results["total"] > 0 else 0
        return results
    
    def analyze_error_patterns(self, errors: List[Dict]) -> Dict:
        """Analyze patterns in classification errors."""
        print("\n" + "="*80)
        print("ERROR PATTERN ANALYSIS")
        print("="*80)
        
        if not errors:
            print("  No errors to analyze!")
            return {}
        
        # Count error types
        error_types = Counter()
        for error in errors:
            error_type = f"{error['expected']} -> {error['predicted']}"
            error_types[error_type] += 1
        
        print("\n  Most Common Error Types:")
        for error_type, count in error_types.most_common(5):
            print(f"    {error_type}: {count}")
        
        # Analyze confidence scores
        incorrect_confidences = [e.get("confidence", 0) for e in errors]
        if incorrect_confidences:
            avg_confidence = sum(incorrect_confidences) / len(incorrect_confidences)
            print(f"\n  Average confidence on incorrect predictions: {avg_confidence:.2%}")
        
        return {
            "error_types": dict(error_types),
            "avg_confidence_on_errors": avg_confidence if incorrect_confidences else 0
        }
    
    def print_summary(self, dataset_results: Dict, edge_case_results: Dict):
        """Print comprehensive test summary."""
        print("\n" + "="*80)
        print("COMPREHENSIVE TEST SUMMARY")
        print("="*80)
        
        print(f"\n📊 Dataset Accuracy: {dataset_results['accuracy']:.2%}")
        print(f"   Correct: {dataset_results['correct']}/{dataset_results['total']}")
        print(f"   Incorrect: {dataset_results['incorrect']}/{dataset_results['total']}")
        
        print(f"\n📊 Edge Case Accuracy: {edge_case_results['accuracy']:.2%}")
        print(f"   Correct: {edge_case_results['correct']}/{edge_case_results['total']}")
        print(f"   Incorrect: {edge_case_results['incorrect']}/{edge_case_results['total']}")
        
        print("\n📊 Per-Classification Accuracy (Dataset):")
        for classification in ["Public", "Confidential", "Highly Sensitive"]:
            if classification in dataset_results["by_classification"]:
                stats = dataset_results["by_classification"][classification]
                accuracy = stats.get("accuracy", 0)
                print(f"   {classification}: {accuracy:.2%} ({stats['correct']}/{stats['total']})")
        
        print("\n📊 Per-Safety Accuracy (Dataset):")
        for safety in ["Safe", "Unsafe"]:
            if safety in dataset_results["by_safety"]:
                stats = dataset_results["by_safety"][safety]
                accuracy = stats.get("accuracy", 0)
                print(f"   {safety}: {accuracy:.2%} ({stats['correct']}/{stats['total']})")
        
        print("\n📊 Confusion Matrix (Dataset):")
        print("   Expected -> Predicted")
        for expected in ["Public", "Confidential", "Highly Sensitive"]:
            row = []
            for predicted in ["Public", "Confidential", "Highly Sensitive"]:
                count = dataset_results["confusion_matrix"][expected][predicted]
                row.append(f"{count:4d}")
            print(f"   {expected:20s} -> {' | '.join(row)}")
        
        if dataset_results["errors"]:
            self.analyze_error_patterns(dataset_results["errors"])


if __name__ == "__main__":
    print("="*80)
    print("COMPREHENSIVE CLASSIFICATION TEST SUITE")
    print("="*80)
    
    tester = ComprehensiveTester()
    
    # Test dataset accuracy
    dataset_results = tester.test_dataset_accuracy(sample_size=100)
    
    # Test edge cases
    edge_case_results = tester.test_edge_cases()
    
    # Print summary
    tester.print_summary(dataset_results, edge_case_results)
    
    # Save results
    results = {
        "dataset_results": dataset_results,
        "edge_case_results": edge_case_results,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat()
    }
    
    with open("comprehensive_test_results.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to comprehensive_test_results.json")
    print("="*80)

