#!/usr/bin/env python3
"""Comprehensive test that demonstrates auto-improvement in action."""
import json
import sys
import asyncio
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.classification_pipeline import ClassificationPipeline
from src.hitl_feedback import HITLFeedbackSystem
from src.prompt_refinement import PromptRefinementSystem
from src.auto_improvement import AutoImprovementSystem, AutoImprovementConfig
from config import settings


class ImprovementTester:
    """Test system that demonstrates auto-improvement."""
    
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
        self.hitl_system = HITLFeedbackSystem()
        self.refinement_system = PromptRefinementSystem(self.hitl_system, self.pipeline.prompt_library)
        self.auto_improvement = AutoImprovementSystem(
            hitl_system=self.hitl_system,
            refinement_system=self.refinement_system,
            config=AutoImprovementConfig(
                feedback_threshold=5,  # Lower for testing
                min_feedback_for_analysis=3,
                min_improvement_confidence=0.7  # Lower threshold for testing
            )
        )
    
    def test_dataset_sample(self, sample_size: int = 20) -> Dict:
        """Test accuracy on a sample of dataset examples."""
        print(f"\n{'='*80}")
        print(f"TESTING ON {sample_size} DATASET EXAMPLES")
        print(f"{'='*80}")
        
        # Load dataset
        with open("document_safety_dataset.json", 'r') as f:
            dataset = json.load(f)
        
        import random
        test_set = random.sample(dataset, min(sample_size, len(dataset)))
        
        results = {
            "total": len(test_set),
            "correct": 0,
            "incorrect": 0,
            "by_classification": defaultdict(lambda: {"correct": 0, "total": 0}),
            "errors": []
        }
        
        for i, example in enumerate(test_set, 1):
            if i % 5 == 0:
                print(f"  Processing {i}/{len(test_set)}...")
            
            text = example.get("text", "")
            expected = example.get("correct_classification", "Public")
            
            try:
                result = self.pipeline.classify_text_direct(text)
                predicted = result.get("classification", "Public")
                
                is_correct = predicted == expected
                results["by_classification"][expected]["total"] += 1
                
                if is_correct:
                    results["correct"] += 1
                    results["by_classification"][expected]["correct"] += 1
                else:
                    results["incorrect"] += 1
                    results["errors"].append({
                        "text": text[:100] + "..." if len(text) > 100 else text,
                        "expected": expected,
                        "predicted": predicted,
                        "document_id": result.get("document_id")
                    })
            except Exception as e:
                print(f"  Error on example {i}: {e}")
                results["incorrect"] += 1
        
        results["accuracy"] = results["correct"] / results["total"] if results["total"] > 0 else 0
        
        for classification in results["by_classification"]:
            total = results["by_classification"][classification]["total"]
            correct = results["by_classification"][classification]["correct"]
            if total > 0:
                results["by_classification"][classification]["accuracy"] = correct / total
        
        return results
    
    def submit_feedback_for_errors(self, errors: List[Dict]):
        """Submit feedback for classification errors to trigger improvement."""
        print(f"\n{'='*80}")
        print(f"SUBMITTING FEEDBACK FOR {len(errors)} ERRORS")
        print(f"{'='*80}")
        
        submitted = 0
        for error in errors[:10]:  # Limit to 10 to avoid too many API calls
            try:
                # Get the prompt_used from the classification result
                # For now, we'll use base_classification as default
                prompt_used = "base_classification"
                
                error_text = error.get('text', '')
                error_text_short = error_text[:100] if len(error_text) > 100 else error_text
                self.hitl_system.add_feedback(
                    document_id=error.get("document_id", ""),
                    original_classification=error.get("predicted"),
                    corrected_classification=error.get("expected"),
                    feedback_type="correction",
                    feedback_text=f"Dataset example: {error_text_short}",
                    prompt_used=prompt_used
                )
                submitted += 1
            except Exception as e:
                print(f"  Error submitting feedback: {e}")
        
        print(f"  ✅ Submitted {submitted} feedback records")
        return submitted
    
    async def trigger_improvement(self):
        """Trigger auto-improvement analysis."""
        print(f"\n{'='*80}")
        print("TRIGGERING AUTO-IMPROVEMENT")
        print(f"{'='*80}")
        
        result = await self.auto_improvement.analyze_and_improve_automatically()
        
        print(f"  Status: {result.get('status')}")
        
        if result.get('status') == 'analyzed':
            print(f"  Prompt analyzed: {result.get('prompt_name')}")
            print(f"  Confidence: {result.get('improvement_confidence', 0):.2%}")
            print(f"  Auto-applied: {result.get('auto_applied', False)}")
            if result.get('auto_applied'):
                print("  ✅ PROMPT WAS AUTO-APPLIED!")
                return True
        elif result.get('status') == 'no_suggestion':
            print(f"  Reason: {result.get('reason')}")
        elif result.get('status') == 'skipped':
            print(f"  Reason: {result.get('reason')}")
            print(f"  Current feedback count: {result.get('current_feedback_count', 0)}")
        
        return False
    
    def test_pdf_files(self) -> Dict:
        """Test classification of PDF files."""
        print(f"\n{'='*80}")
        print("TESTING PDF FILES")
        print(f"{'='*80}")
        
        test_cases = [
            {
                "filename": "TC1_Sample_Public_Marketing_Document.pdf",
                "expected": "Public",
                "path": "uploads/TC1_Sample_Public_Marketing_Document.pdf"
            },
            {
                "filename": "TC2_Filled_In_Employement_Application.pdf",
                "expected": "Highly Sensitive",
                "path": "uploads/TC2_Filled_In_Employement_Application.pdf"
            },
            {
                "filename": "TC3_Sample_Internal_Memo.pdf",
                "expected": "Confidential",
                "path": "uploads/TC3_Sample_Internal_Memo.pdf"
            },
            {
                "filename": "TC4_ Stealth_Fighter_With_Part_Names.pdf",
                "expected": "Confidential",
                "path": "uploads/TC4_ Stealth_Fighter_With_Part_Names.pdf"
            }
        ]
        
        results = {
            "total": 0,
            "correct": 0,
            "incorrect": 0,
            "details": []
        }
        
        for test_case in test_cases:
            file_path = test_case["path"]
            if not Path(file_path).exists():
                print(f"  ⚠️  File not found: {file_path}")
                continue
            
            print(f"\n  Testing: {test_case['filename']}")
            print(f"    Expected: {test_case['expected']}")
            
            try:
                result = self.pipeline.classify_document(file_path)
                predicted = result.get("classification", "Unknown")
                confidence = result.get("confidence", 0.0)
                
                is_correct = predicted == test_case["expected"]
                results["total"] += 1
                
                if is_correct:
                    results["correct"] += 1
                    print(f"    ✅ CORRECT: {predicted} (confidence: {confidence:.2%})")
                else:
                    results["incorrect"] += 1
                    print(f"    ❌ INCORRECT: Expected {test_case['expected']}, got {predicted} (confidence: {confidence:.2%})")
                
                results["details"].append({
                    "filename": test_case["filename"],
                    "expected": test_case["expected"],
                    "predicted": predicted,
                    "correct": is_correct,
                    "confidence": confidence
                })
            except Exception as e:
                print(f"    ❌ ERROR: {e}")
                results["incorrect"] += 1
        
        if results["total"] > 0:
            results["accuracy"] = results["correct"] / results["total"]
        else:
            results["accuracy"] = 0
        
        return results
    
    def print_summary(self, before_results: Dict, after_results: Dict, pdf_results: Dict):
        """Print comprehensive test summary."""
        print(f"\n{'='*80}")
        print("COMPREHENSIVE TEST SUMMARY")
        print(f"{'='*80}")
        
        print(f"\n📊 Dataset Test Results:")
        print(f"   Before Improvement: {before_results['accuracy']:.2%} ({before_results['correct']}/{before_results['total']})")
        if after_results:
            print(f"   After Improvement:  {after_results['accuracy']:.2%} ({after_results['correct']}/{after_results['total']})")
            improvement = after_results['accuracy'] - before_results['accuracy']
            if improvement > 0:
                print(f"   ✅ Improvement: +{improvement:.2%}")
            elif improvement < 0:
                print(f"   ⚠️  Change: {improvement:.2%}")
            else:
                print(f"   ➡️  No change")
        
        print(f"\n📊 PDF Test Results:")
        print(f"   Accuracy: {pdf_results['accuracy']:.2%} ({pdf_results['correct']}/{pdf_results['total']})")
        print(f"\n   Details:")
        for detail in pdf_results.get("details", []):
            status = "✅" if detail["correct"] else "❌"
            print(f"     {status} {detail['filename']}: {detail['predicted']} (expected: {detail['expected']})")
        
        print(f"\n{'='*80}")


async def main():
    """Run comprehensive test with improvement demonstration."""
    print("="*80)
    print("COMPREHENSIVE TEST WITH AUTO-IMPROVEMENT")
    print("="*80)
    
    tester = ImprovementTester()
    
    # Step 1: Test current accuracy
    print("\n🔍 STEP 1: Testing current accuracy...")
    before_results = tester.test_dataset_sample(sample_size=20)
    print(f"\n   Current Accuracy: {before_results['accuracy']:.2%}")
    print(f"   Errors: {len(before_results['errors'])}")
    
    # Step 2: Submit feedback for errors
    if before_results['errors']:
        print("\n📝 STEP 2: Submitting feedback to trigger improvement...")
        tester.submit_feedback_for_errors(before_results['errors'])
        
        # Step 3: Trigger improvement
        print("\n🔄 STEP 3: Triggering auto-improvement...")
        improved = await tester.trigger_improvement()
        
        if improved:
            # Step 4: Test accuracy after improvement
            print("\n🔍 STEP 4: Testing accuracy after improvement...")
            # Reinitialize pipeline to get updated prompts
            tester.pipeline = ClassificationPipeline(
                gemini_api_key=settings.gemini_api_key,
                mistral_api_key=settings.mistral_api_key,
                openai_api_key=settings.openai_api_key,
                legibility_threshold=settings.legibility_threshold,
                enable_dual_validation=settings.enable_dual_llm_validation,
                dataset_file="document_safety_dataset.json",
                enable_few_shot=True
            )
            after_results = tester.test_dataset_sample(sample_size=20)
        else:
            after_results = None
            print("\n   ⚠️  Improvement was not auto-applied (may need more feedback or higher confidence)")
    else:
        after_results = None
        print("\n   ✅ No errors found - accuracy is perfect!")
    
    # Step 5: Test PDF files
    print("\n📄 STEP 5: Testing PDF files...")
    pdf_results = tester.test_pdf_files()
    
    # Print summary
    tester.print_summary(before_results, after_results, pdf_results)
    
    # Save results
    results = {
        "before_improvement": before_results,
        "after_improvement": after_results,
        "pdf_results": pdf_results,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat()
    }
    
    with open("improvement_test_results.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to improvement_test_results.json")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())

