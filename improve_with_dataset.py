"""Script to improve classification using the dataset by submitting feedback and triggering auto-improvement."""
import json
import sys
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.classification_pipeline import ClassificationPipeline
from src.hitl_feedback import HITLFeedbackSystem
from src.prompt_refinement import PromptRefinementSystem
from src.auto_improvement import AutoImprovementSystem, AutoImprovementConfig
from config import settings


class DatasetImprover:
    """Uses dataset to improve classification through feedback and auto-improvement."""
    
    def __init__(self, dataset_path: str):
        """Initialize improver.
        
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
            enable_dual_validation=settings.enable_dual_llm_validation,
            dataset_file=str(self.dataset_path),
            enable_few_shot=True
        )
        self.hitl_system = HITLFeedbackSystem()
        self.refinement_system = PromptRefinementSystem(
            self.hitl_system,
            self.pipeline.prompt_library
        )
        self.auto_improvement = AutoImprovementSystem(
            hitl_system=self.hitl_system,
            refinement_system=self.refinement_system,
            config=AutoImprovementConfig(
                feedback_threshold=50,  # Trigger after 50 feedbacks
                min_feedback_for_analysis=10,
                min_improvement_confidence=0.7,  # 70% confidence to auto-apply
                auto_apply_enabled=True
            )
        )
    
    def _load_dataset(self) -> List[Dict]:
        """Load the dataset."""
        with open(self.dataset_path, 'r') as f:
            return json.load(f)
    
    async def run_improvement_cycle(
        self,
        sample_size: Optional[int] = None,
        batch_size: int = 50,
        max_iterations: int = 3
    ) -> Dict:
        """Run improvement cycle: validate -> submit feedback -> improve -> re-validate.
        
        Args:
            sample_size: Number of examples to use (None for all)
            batch_size: Number of feedbacks to submit before triggering improvement
            max_iterations: Maximum number of improvement iterations
            
        Returns:
            Dictionary with improvement results
        """
        # Sample if needed
        test_set = self.dataset
        if sample_size and sample_size < len(self.dataset):
            import random
            test_set = random.sample(self.dataset, sample_size)
        
        print(f"Using {len(test_set)} examples from dataset")
        print(f"Batch size: {batch_size}, Max iterations: {max_iterations}\n")
        
        all_results = []
        
        # Initial validation
        print("="*80)
        print("INITIAL VALIDATION")
        print("="*80)
        initial_results = await self._validate_and_submit_feedback(
            test_set, 
            submit_feedback=True,
            batch_size=batch_size
        )
        all_results.append({
            "iteration": 0,
            "type": "initial",
            "results": initial_results
        })
        
        # Improvement iterations
        for iteration in range(1, max_iterations + 1):
            print(f"\n{'='*80}")
            print(f"IMPROVEMENT ITERATION {iteration}")
            print("="*80)
            
            # Trigger auto-improvement
            print("\nTriggering auto-improvement analysis...")
            improvement_result = await self.auto_improvement.analyze_and_improve_automatically()
            
            if improvement_result.get("status") == "applied":
                print(f"✅ Improvement applied: {improvement_result.get('prompt_name')}")
                print(f"   Confidence: {improvement_result.get('confidence', 0):.1%}")
            elif improvement_result.get("status") == "suggested":
                print(f"⚠️  Improvement suggested but not auto-applied")
                print(f"   Confidence: {improvement_result.get('confidence', 0):.1%}")
                print(f"   Reason: {improvement_result.get('reason', 'Unknown')}")
            else:
                print(f"ℹ️  No improvement: {improvement_result.get('reason', 'Unknown')}")
            
            # Re-validate with improved prompts
            print(f"\nRe-validating with improved prompts...")
            new_results = await self._validate_and_submit_feedback(
                test_set,
                submit_feedback=True,
                batch_size=batch_size
            )
            
            all_results.append({
                "iteration": iteration,
                "type": "improved",
                "improvement_result": improvement_result,
                "results": new_results
            })
            
            # Check if accuracy improved
            initial_acc = initial_results["accuracy"]
            new_acc = new_results["accuracy"]
            improvement = new_acc - initial_acc
            
            print(f"\n📊 Accuracy: {initial_acc:.2%} → {new_acc:.2%} ({improvement:+.2%})")
            
            # Stop if no significant improvement
            if improvement < 0.01:  # Less than 1% improvement
                print(f"\nStopping: Improvement < 1%")
                break
        
        return {
            "initial_accuracy": initial_results["accuracy"],
            "final_accuracy": all_results[-1]["results"]["accuracy"],
            "improvement": all_results[-1]["results"]["accuracy"] - initial_results["accuracy"],
            "iterations": len(all_results) - 1,
            "all_results": all_results
        }
    
    async def _validate_and_submit_feedback(
        self,
        test_set: List[Dict],
        submit_feedback: bool = True,
        batch_size: int = 50
    ) -> Dict:
        """Validate and optionally submit feedback for errors.
        
        Args:
            test_set: List of test examples
            submit_feedback: Whether to submit feedback for errors
            batch_size: Submit feedback in batches of this size
            
        Returns:
            Validation results dictionary
        """
        results = {
            "total": len(test_set),
            "correct": 0,
            "incorrect": 0,
            "by_classification": defaultdict(lambda: {"correct": 0, "total": 0}),
            "confusion_matrix": defaultdict(lambda: defaultdict(int)),
            "errors": []
        }
        
        feedback_submitted = 0
        
        for i, example in enumerate(test_set, 1):
            if i % 10 == 0:
                print(f"  Processing {i}/{len(test_set)}... (Feedback submitted: {feedback_submitted})", flush=True)
            
            text = example.get("text", "")
            expected_classification = example.get("correct_classification", "Public")
            expected_safety = example.get("safety_status", "Safe")
            
            try:
                # Classify
                result = self.pipeline.classify_text_direct(text)
                
                predicted_classification = result.get("classification", "Public")
                predicted_safety = result.get("safety_check", "Safe")
                
                # Check accuracy
                classification_correct = predicted_classification == expected_classification
                safety_correct = predicted_safety == expected_safety
                
                # Update results
                results["by_classification"][expected_classification]["total"] += 1
                
                if classification_correct:
                    results["correct"] += 1
                    results["by_classification"][expected_classification]["correct"] += 1
                else:
                    results["incorrect"] += 1
                    error_info = {
                        "text": text[:200] + "..." if len(text) > 200 else text,
                        "expected": expected_classification,
                        "predicted": predicted_classification,
                        "expected_safety": expected_safety,
                        "predicted_safety": predicted_safety,
                        "confidence": result.get("confidence", 0.0),
                    }
                    results["errors"].append(error_info)
                    
                    # Submit feedback for misclassifications
                    if submit_feedback:
                        try:
                            self.hitl_system.add_feedback(
                                document_id=f"dataset_{i}",
                                original_classification=predicted_classification,
                                corrected_classification=expected_classification,
                                feedback_type="correction",
                                feedback_text=f"Dataset example {i}: Expected {expected_classification}, got {predicted_classification}",
                                reviewer_id="dataset_improver",
                                prompt_used=result.get("prompt_used", "base_classification")
                            )
                            feedback_submitted += 1
                            
                            # Trigger improvement after batch_size feedbacks
                            if feedback_submitted % batch_size == 0:
                                print(f"\n  → Triggering auto-improvement after {feedback_submitted} feedbacks...")
                                await self.auto_improvement.analyze_and_improve_automatically()
                        except Exception as e:
                            print(f"  ⚠️  Error submitting feedback: {e}")
                
                # Confusion matrix
                results["confusion_matrix"][expected_classification][predicted_classification] += 1
                
            except Exception as e:
                print(f"Error processing example {i}: {e}")
                results["incorrect"] += 1
        
        # Calculate accuracy
        results["accuracy"] = results["correct"] / results["total"] if results["total"] > 0 else 0
        
        # Calculate per-class accuracy
        for classification in results["by_classification"]:
            total = results["by_classification"][classification]["total"]
            correct = results["by_classification"][classification]["correct"]
            if total > 0:
                results["by_classification"][classification]["accuracy"] = correct / total
        
        # Print summary
        print(f"\n📊 Results: {results['accuracy']:.2%} accuracy ({results['correct']}/{results['total']})")
        print(f"   Feedback submitted: {feedback_submitted}")
        
        for classification in ["Public", "Confidential", "Highly Sensitive"]:
            if classification in results["by_classification"]:
                stats = results["by_classification"][classification]
                acc = stats.get("accuracy", 0)
                print(f"   {classification}: {acc:.2%} ({stats['correct']}/{stats['total']})")
        
        return results


async def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Improve classification using dataset feedback and auto-improvement"
    )
    parser.add_argument(
        "--dataset",
        default="document_safety_dataset.json",
        help="Path to dataset JSON file"
    )
    parser.add_argument(
        "--sample",
        type=int,
        help="Sample size (default: all, use smaller for testing)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of feedbacks before triggering improvement (default: 50)"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Maximum improvement iterations (default: 3)"
    )
    
    args = parser.parse_args()
    
    print("="*80)
    print("DATASET-BASED CLASSIFICATION IMPROVEMENT")
    print("="*80)
    print(f"\nDataset: {args.dataset}")
    if args.sample:
        print(f"Sample size: {args.sample}")
    else:
        print("Using full dataset")
    print(f"Batch size: {args.batch_size}")
    print(f"Max iterations: {args.iterations}\n")
    
    improver = DatasetImprover(args.dataset)
    
    try:
        results = await improver.run_improvement_cycle(
            sample_size=args.sample,
            batch_size=args.batch_size,
            max_iterations=args.iterations
        )
        
        print("\n" + "="*80)
        print("FINAL RESULTS")
        print("="*80)
        print(f"\nInitial Accuracy: {results['initial_accuracy']:.2%}")
        print(f"Final Accuracy:   {results['final_accuracy']:.2%}")
        print(f"Improvement:      {results['improvement']:+.2%}")
        print(f"Iterations:       {results['iterations']}")
        
        # Save results
        output_file = "improvement_results.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n✅ Results saved to {output_file}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

