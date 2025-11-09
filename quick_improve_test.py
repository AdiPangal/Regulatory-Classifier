"""Quick test to verify improvement system works with a small sample."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from improve_with_dataset import DatasetImprover

async def main():
    print("="*80)
    print("QUICK TEST - 20 examples, 1 iteration")
    print("="*80)
    print("\nThis will:")
    print("1. Test 20 examples from the dataset")
    print("2. Submit feedback for errors")
    print("3. Trigger auto-improvement")
    print("4. Show accuracy before/after\n")
    
    improver = DatasetImprover("document_safety_dataset.json")
    
    try:
        results = await improver.run_improvement_cycle(
            sample_size=20,
            batch_size=10,
            max_iterations=1
        )
        
        print("\n" + "="*80)
        print("RESULTS")
        print("="*80)
        print(f"Initial: {results['initial_accuracy']:.1%}")
        print(f"Final:   {results['final_accuracy']:.1%}")
        print(f"Change:  {results['improvement']:+.1%}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

