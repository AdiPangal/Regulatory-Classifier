"""Validation script to test classification accuracy against the dataset."""
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict, Counter

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.classification_pipeline import ClassificationPipeline
from config import settings


class DatasetValidator:
    """Validates classification accuracy against labeled dataset."""
    
    def __init__(self, dataset_path: str):
        """Initialize validator.
        
        Args:
            dataset_path: Path to JSON dataset file
        """
        self.dataset_path = Path(dataset_path)
        self.dataset = self._load_dataset()
        self.pipeline = ClassificationPipeline(
            gemini_api_key=settings.gemini_api_key,
            mistral_api_key=settings.mistral_api_key,
            openai_api_key=settings.openai_api_key,
            legibility_threshold=settings.legibility_threshold,
            enable_dual_validation=settings.enable_dual_llm_validation
        )
    
    def _load_dataset(self) -> List[Dict]:
        """Load the dataset."""
        with open(self.dataset_path, 'r') as f:
            return json.load(f)
    
    def validate(
        self,
        sample_size: Optional[int] = None,
        verbose: bool = True
    ) -> Dict:
        """Validate classification accuracy on dataset.
        
        Args:
            sample_size: Number of examples to test (None for all)
            verbose: Whether to print progress
            
        Returns:
            Dictionary with validation results
        """
        # Sample if needed
        test_set = self.dataset
        if sample_size and sample_size < len(self.dataset):
            import random
            test_set = random.sample(self.dataset, sample_size)
        
        results = {
            "total": len(test_set),
            "correct": 0,
            "incorrect": 0,
            "by_classification": defaultdict(lambda: {"correct": 0, "total": 0}),
            "by_safety": defaultdict(lambda: {"correct": 0, "total": 0}),
            "confusion_matrix": defaultdict(lambda: defaultdict(int)),
            "errors": []
        }
        
        print(f"Validating on {len(test_set)} examples...")
        
        for i, example in enumerate(test_set, 1):
            if verbose and i % 10 == 0:
                print(f"Processing {i}/{len(test_set)}...")
            
            text = example.get("text", "")
            expected_classification = example.get("correct_classification", "Public")
            expected_safety = example.get("safety_status", "Safe")
            
            try:
                # Classify using pipeline
                result = self.pipeline.classify_text_direct(text)
                
                predicted_classification = result.get("classification", "Public")
                predicted_safety = result.get("safety_check", "Safe")
                
                # Check classification accuracy
                classification_correct = predicted_classification == expected_classification
                safety_correct = predicted_safety == expected_safety
                
                # Update results
                results["by_classification"][expected_classification]["total"] += 1
                results["by_safety"][expected_safety]["total"] += 1
                
                if classification_correct:
                    results["correct"] += 1
                    results["by_classification"][expected_classification]["correct"] += 1
                else:
                    results["incorrect"] += 1
                    results["errors"].append({
                        "text": text[:200] + "..." if len(text) > 200 else text,
                        "expected": expected_classification,
                        "predicted": predicted_classification,
                        "expected_safety": expected_safety,
                        "predicted_safety": predicted_safety,
                        "confidence": result.get("confidence", 0.0),
                        "reasoning": result.get("reasoning", "")[:200]
                    })
                
                if safety_correct:
                    results["by_safety"][expected_safety]["correct"] += 1
                
                # Confusion matrix
                results["confusion_matrix"][expected_classification][predicted_classification] += 1
                
            except Exception as e:
                print(f"Error processing example {i}: {e}")
                results["errors"].append({
                    "text": text[:200] + "..." if len(text) > 200 else text,
                    "error": str(e)
                })
                results["incorrect"] += 1
        
        # Calculate accuracy
        results["accuracy"] = results["correct"] / results["total"] if results["total"] > 0 else 0
        
        # Calculate per-class accuracy
        for classification in results["by_classification"]:
            total = results["by_classification"][classification]["total"]
            correct = results["by_classification"][classification]["correct"]
            if total > 0:
                results["by_classification"][classification]["accuracy"] = correct / total
        
        # Calculate per-safety accuracy
        for safety in results["by_safety"]:
            total = results["by_safety"][safety]["total"]
            correct = results["by_safety"][safety]["correct"]
            if total > 0:
                results["by_safety"][safety]["accuracy"] = correct / total
        
        return results
    
    def print_results(self, results: Dict):
        """Print validation results in a readable format.
        
        Args:
            results: Results dictionary from validate()
        """
        print("\n" + "="*80)
        print("VALIDATION RESULTS")
        print("="*80)
        print(f"\nOverall Accuracy: {results['accuracy']:.2%} ({results['correct']}/{results['total']})")
        
        print("\n--- Per-Classification Accuracy ---")
        for classification in ["Public", "Confidential", "Highly Sensitive"]:
            if classification in results["by_classification"]:
                stats = results["by_classification"][classification]
                accuracy = stats.get("accuracy", 0)
                print(f"  {classification}: {accuracy:.2%} ({stats['correct']}/{stats['total']})")
        
        print("\n--- Per-Safety Accuracy ---")
        for safety in ["Safe", "Unsafe"]:
            if safety in results["by_safety"]:
                stats = results["by_safety"][safety]
                accuracy = stats.get("accuracy", 0)
                print(f"  {safety}: {accuracy:.2%} ({stats['correct']}/{stats['total']})")
        
        print("\n--- Confusion Matrix ---")
        print("Expected -> Predicted")
        for expected in ["Public", "Confidential", "Highly Sensitive"]:
            row = []
            for predicted in ["Public", "Confidential", "Highly Sensitive"]:
                count = results["confusion_matrix"][expected][predicted]
                row.append(f"{count:4d}")
            print(f"  {expected:20s} -> {' | '.join(row)}")
        
        if results["errors"]:
            print(f"\n--- Sample Errors ({min(10, len(results['errors']))} of {len(results['errors'])}) ---")
            for i, error in enumerate(results["errors"][:10], 1):
                print(f"\nError {i}:")
                print(f"  Expected: {error.get('expected', 'N/A')}")
                print(f"  Predicted: {error.get('predicted', 'N/A')}")
                print(f"  Confidence: {error.get('confidence', 0):.2f}")
                print(f"  Text: {error.get('text', 'N/A')[:150]}...")
        
        print("\n" + "="*80)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate classification accuracy on dataset")
    parser.add_argument("--dataset", default="document_safety_dataset.json", help="Path to dataset JSON file")
    parser.add_argument("--sample", type=int, help="Sample size (default: all)")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")
    
    args = parser.parse_args()
    
    validator = DatasetValidator(args.dataset)
    results = validator.validate(sample_size=args.sample, verbose=not args.quiet)
    validator.print_results(results)
    
    # Save results to file
    output_file = "validation_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_file}")

