"""Script to integrate dataset examples with prompt refinement system."""
import json
import sys
from pathlib import Path
from typing import List, Dict
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.hitl_feedback import HITLFeedbackSystem
from src.classification_pipeline import ClassificationPipeline
from config import settings


def convert_dataset_to_feedback(
    dataset_path: str,
    sample_size: int = 100,
    dry_run: bool = True
) -> List[Dict]:
    """Convert dataset examples to feedback format for refinement system.
    
    Args:
        dataset_path: Path to dataset JSON file
        sample_size: Number of examples to convert (for testing)
        dry_run: If True, don't actually submit feedback, just return the format
        
    Returns:
        List of feedback dictionaries
    """
    # Load dataset
    with open(dataset_path, 'r') as f:
        dataset = json.load(f)
    
    # Sample if needed
    if sample_size and sample_size < len(dataset):
        import random
        dataset = random.sample(dataset, sample_size)
    
    # Initialize pipeline for classification
    pipeline = ClassificationPipeline(
        gemini_api_key=settings.gemini_api_key,
        mistral_api_key=settings.mistral_api_key,
        openai_api_key=settings.openai_api_key,
        legibility_threshold=settings.legibility_threshold,
        enable_dual_validation=settings.enable_dual_llm_validation,
        dataset_file=dataset_path,  # Use dataset for few-shot
        enable_few_shot=True
    )
    
    feedback_records = []
    
    print(f"Processing {len(dataset)} examples...")
    
    for i, example in enumerate(dataset, 1):
        if i % 10 == 0:
            print(f"  Processed {i}/{len(dataset)}...")
        
        text = example.get("text", "")
        expected_classification = example.get("correct_classification", "Public")
        expected_safety = example.get("safety_status", "Safe")
        
        try:
            # Classify using pipeline
            result = pipeline.classify_text_direct(text)
            
            predicted_classification = result.get("classification", "Public")
            predicted_safety = result.get("safety_check", "Safe")
            document_id = result.get("document_id", "")
            prompt_used = result.get("prompt_used", "base_classification")
            
            # Only create feedback if prediction is wrong
            if predicted_classification != expected_classification or predicted_safety != expected_safety:
                feedback = {
                    "document_id": document_id,
                    "original_classification": predicted_classification,
                    "correct_classification": expected_classification,
                    "original_safety": predicted_safety,
                    "correct_safety": expected_safety,
                    "feedback_type": "correction",
                    "user_notes": f"Dataset example: {text[:100]}...",
                    "prompt_used": prompt_used,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                feedback_records.append(feedback)
                
                # Submit feedback if not dry run
                if not dry_run:
                    hitl_system = HITLFeedbackSystem()
                    try:
                        hitl_system.submit_feedback(
                            document_id=document_id,
                            original_classification=predicted_classification,
                            correct_classification=expected_classification,
                            feedback_type="correction",
                            user_notes=feedback["user_notes"],
                            prompt_used=prompt_used
                        )
                    except Exception as e:
                        print(f"  Error submitting feedback for example {i}: {e}")
        
        except Exception as e:
            print(f"  Error processing example {i}: {e}")
    
    return feedback_records


def analyze_dataset_patterns(dataset_path: str) -> Dict:
    """Analyze patterns in the dataset to inform prompt improvements.
    
    Args:
        dataset_path: Path to dataset JSON file
        
    Returns:
        Dictionary with analysis results
    """
    with open(dataset_path, 'r') as f:
        dataset = json.load(f)
    
    from collections import Counter, defaultdict
    
    # Count classifications
    classifications = Counter([d.get("correct_classification", "Public") for d in dataset])
    safety = Counter([d.get("safety_status", "Safe") for d in dataset])
    
    # Analyze text patterns
    public_keywords = defaultdict(int)
    confidential_keywords = defaultdict(int)
    highly_sensitive_keywords = defaultdict(int)
    
    keywords_to_check = [
        "marketing", "brochure", "product", "public", "announcement",
        "internal", "memo", "confidential", "proprietary", "strategy",
        "ssn", "credit card", "bank account", "employment", "application",
        "patient", "medical", "passport", "encryption"
    ]
    
    for example in dataset:
        text_lower = example.get("text", "").lower()
        classification = example.get("correct_classification", "Public")
        
        for keyword in keywords_to_check:
            if keyword in text_lower:
                if classification == "Public":
                    public_keywords[keyword] += 1
                elif classification == "Confidential":
                    confidential_keywords[keyword] += 1
                elif classification == "Highly Sensitive":
                    highly_sensitive_keywords[keyword] += 1
    
    return {
        "total_examples": len(dataset),
        "classifications": dict(classifications),
        "safety": dict(safety),
        "public_keywords": dict(public_keywords),
        "confidential_keywords": dict(confidential_keywords),
        "highly_sensitive_keywords": dict(highly_sensitive_keywords)
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Integrate dataset with prompt refinement")
    parser.add_argument("--dataset", default="document_safety_dataset.json", help="Path to dataset")
    parser.add_argument("--sample", type=int, help="Sample size (default: all)")
    parser.add_argument("--submit", action="store_true", help="Actually submit feedback (default: dry run)")
    parser.add_argument("--analyze", action="store_true", help="Analyze dataset patterns only")
    
    args = parser.parse_args()
    
    if args.analyze:
        print("Analyzing dataset patterns...")
        analysis = analyze_dataset_patterns(args.dataset)
        print("\nDataset Analysis:")
        print(f"  Total examples: {analysis['total_examples']}")
        print(f"  Classifications: {analysis['classifications']}")
        print(f"  Safety: {analysis['safety']}")
        print("\n  Top Public keywords:")
        for kw, count in sorted(analysis['public_keywords'].items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"    {kw}: {count}")
        print("\n  Top Confidential keywords:")
        for kw, count in sorted(analysis['confidential_keywords'].items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"    {kw}: {count}")
        print("\n  Top Highly Sensitive keywords:")
        for kw, count in sorted(analysis['highly_sensitive_keywords'].items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"    {kw}: {count}")
    else:
        print(f"Converting dataset to feedback format...")
        print(f"  Dataset: {args.dataset}")
        print(f"  Sample size: {args.sample or 'all'}")
        print(f"  Mode: {'SUBMIT' if args.submit else 'DRY RUN'}")
        print()
        
        feedback_records = convert_dataset_to_feedback(
            args.dataset,
            sample_size=args.sample,
            dry_run=not args.submit
        )
        
        print(f"\nGenerated {len(feedback_records)} feedback records")
        
        if not args.submit:
            print("\nThis was a dry run. Use --submit to actually submit feedback.")
            print("\nSample feedback records:")
            for i, feedback in enumerate(feedback_records[:5], 1):
                print(f"\n  {i}. {feedback['original_classification']} -> {feedback['correct_classification']}")
                print(f"     Prompt: {feedback['prompt_used']}")
        
        # Save to file
        output_file = "dataset_feedback_records.json"
        with open(output_file, 'w') as f:
            json.dump(feedback_records, f, indent=2)
        print(f"\nFeedback records saved to {output_file}")

