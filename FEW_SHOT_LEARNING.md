# Few-Shot Learning Implementation

This document describes the few-shot learning implementation that uses your dataset to improve classification accuracy.

## Overview

The system now supports few-shot learning by automatically injecting diverse examples from your `document_safety_dataset.json` into the classification prompts. This helps the LLM learn patterns from your labeled data without requiring model fine-tuning.

## Components

### 1. Few-Shot Generator (`src/few_shot_generator.py`)

The `FewShotGenerator` class:
- Loads and indexes your dataset
- Samples diverse examples ensuring representation from all classes
- Formats examples for inclusion in prompts
- Filters examples by text length to keep prompts manageable

**Key Methods:**
- `sample_diverse_examples()`: Samples balanced examples from all classification categories
- `format_examples_for_prompt()`: Formats examples as a string for prompt injection
- `get_examples_by_classification()`: Gets examples for a specific classification

### 2. Enhanced Prompt Library (`src/prompt_library.py`)

The `PromptLibrary` class now:
- Accepts a `dataset_file` parameter
- Automatically initializes the few-shot generator
- Injects examples into prompts dynamically
- Maintains backward compatibility (works without dataset)

**New Parameters:**
- `dataset_file`: Path to your dataset JSON file
- `enable_few_shot`: Enable/disable few-shot learning (default: True)
- `few_shot_examples_per_class`: Number of examples per class (default: 5)

### 3. Validation Script (`validate_dataset.py`)

Test your classification accuracy against the dataset:

```bash
# Validate on all examples
python3 validate_dataset.py

# Validate on a sample
python3 validate_dataset.py --sample 100

# Quiet mode (no progress output)
python3 validate_dataset.py --quiet
```

**Output:**
- Overall accuracy
- Per-classification accuracy (Public, Confidential, Highly Sensitive)
- Per-safety accuracy (Safe, Unsafe)
- Confusion matrix
- Sample errors
- Results saved to `validation_results.json`

### 4. Dataset Integration Script (`integrate_dataset_with_refinement.py`)

Integrate your dataset with the prompt refinement system:

```bash
# Analyze dataset patterns
python3 integrate_dataset_with_refinement.py --analyze

# Convert dataset to feedback format (dry run)
python3 integrate_dataset_with_refinement.py --sample 50

# Actually submit feedback
python3 integrate_dataset_with_refinement.py --sample 50 --submit
```

**Features:**
- Analyzes dataset patterns and keyword distributions
- Converts misclassified examples to feedback records
- Submits feedback to the HITL system for prompt refinement
- Helps the auto-improvement system learn from your dataset

## Usage

### Automatic Integration

The system automatically detects and uses your dataset if it's in one of these locations:
- `document_safety_dataset.json` (project root)
- `src/../document_safety_dataset.json`

The API initialization in `src/api.py` automatically searches for and loads the dataset.

### Manual Configuration

You can also manually specify the dataset when creating a pipeline:

```python
from src.classification_pipeline import ClassificationPipeline

pipeline = ClassificationPipeline(
    gemini_api_key="...",
    mistral_api_key="...",
    openai_api_key="...",
    dataset_file="path/to/your/dataset.json",
    enable_few_shot=True,
    few_shot_examples_per_class=5
)
```

## How It Works

1. **Dataset Loading**: On initialization, the system loads your dataset and indexes it by classification and safety status.

2. **Example Sampling**: For each classification request, the system:
   - Samples diverse examples (default: 5 per class = 15 total)
   - Ensures representation from all categories
   - Includes both Safe and Unsafe examples
   - Filters by text length to keep prompts manageable

3. **Prompt Injection**: Examples are formatted and injected into prompts:
   - Inserted after the classification rules
   - Before the document information
   - Includes reasoning explanations

4. **LLM Learning**: The LLM sees these examples and learns:
   - Pattern recognition from similar documents
   - Edge case handling
   - Classification boundaries

## Example Output

When few-shot learning is enabled, prompts include sections like:

```
**FEW-SHOT EXAMPLES:**

Example 1:
Text: "This is a public marketing brochure for our new product line..."
Correct Classification: Public
Safety Status: Safe
Reasoning: This is classified as Public because it is public-facing marketing or promotional material
---

Example 2:
Text: "Customer record: John Doe, SSN: 123-45-6789..."
Correct Classification: Highly Sensitive
Safety Status: Safe
Reasoning: This is classified as Highly Sensitive because it contains financial/identity PII such as SSNs, credit cards, or bank account numbers
---
...
```

## Benefits

1. **Improved Accuracy**: LLM learns from your specific data patterns
2. **No Fine-Tuning Required**: Works with existing LLM APIs
3. **Fast Implementation**: No training time, immediate effect
4. **Easy Updates**: Just update your dataset and restart
5. **Validation**: Test accuracy improvements with validation script

## Dataset Format

Your dataset should be a JSON array with objects like:

```json
{
  "text": "Document text content...",
  "correct_classification": "Public|Confidential|Highly Sensitive",
  "safety_status": "Safe|Unsafe"
}
```

## Performance Considerations

- **Prompt Length**: Examples are filtered to max 500 characters to keep prompts manageable
- **Sampling**: Examples are pre-generated on initialization for efficiency
- **Caching**: Examples are cached and reused across requests
- **Optional**: System works fine without dataset (backward compatible)

## Next Steps

1. **Run Validation**: Test current accuracy
   ```bash
   python3 validate_dataset.py --sample 100
   ```

2. **Enable Few-Shot**: Ensure dataset is in the right location

3. **Re-validate**: Check accuracy improvement
   ```bash
   python3 validate_dataset.py --sample 100
   ```

4. **Integrate with Refinement**: Let the system learn from misclassifications
   ```bash
   python3 integrate_dataset_with_refinement.py --sample 50 --submit
   ```

5. **Monitor**: Check prompt refinement history and auto-improvement logs

## Troubleshooting

**Few-shot not working?**
- Check that `document_safety_dataset.json` exists
- Check logs for initialization warnings
- Verify dataset format is correct JSON

**Low accuracy?**
- Run validation to identify problem areas
- Check confusion matrix for patterns
- Review sample errors for common mistakes
- Consider increasing `few_shot_examples_per_class`

**Prompt too long?**
- Examples are filtered to max 500 chars
- Reduce `few_shot_examples_per_class` if needed
- Check LLM token limits

