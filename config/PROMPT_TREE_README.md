# Configurable Prompt Decision Tree

This document describes the configurable decision tree system for dynamic prompt selection in the Regulatory Classifier.

## Overview

The decision tree allows you to configure how prompts are selected based on document characteristics (PII, keywords, safety issues, images, etc.) without modifying code. The tree is defined in JSON format and evaluated at runtime.

## Tree Structure

The decision tree consists of **nodes** and **leaves**:

- **Node**: An internal decision point that evaluates a condition and branches based on the result
- **Leaf**: A terminal point that returns a prompt name

## Configuration File Format

The tree configuration is a JSON file with the following structure:

```json
{
  "version": "1.0",
  "description": "Configurable decision tree for dynamic prompt selection",
  "tree": {
    "type": "node",
    "priority": 1,
    "condition": { ... },
    "if_true": { ... },
    "if_false": { ... }
  }
}
```

## Node Types

### Leaf Node
A leaf node represents a final decision and returns a prompt name:

```json
{
  "type": "leaf",
  "prompt": "base_classification"
}
```

### Internal Node
An internal node evaluates a condition and branches:

```json
{
  "type": "node",
  "priority": 1,
  "condition": { ... },
  "if_true": { ... },
  "if_false": { ... }
}
```

## Condition Types

### 1. Safety Check (`check_safety`)
Checks for unsafe content:

```json
{
  "type": "check_safety",
  "operator": "has_unsafe_pages"
}
```

**Operators:**
- `has_unsafe_pages`: Returns true if any pages are flagged as unsafe

### 2. PII Check (`check_pii`)
Checks for high-risk PII:

```json
{
  "type": "check_pii",
  "operator": "has_high_risk_pii",
  "pii_types": ["SSN", "CREDIT_CARD", "BANK_ACCOUNT"],
  "exclude_types": ["DRIVER_LICENSE"]
}
```

**Operators:**
- `has_high_risk_pii`: Returns true if high-risk PII types are detected

**Parameters:**
- `pii_types`: List of PII types that trigger the condition
- `exclude_types`: List of PII types to exclude from consideration

### 3. Keyword Check (`check_keywords`)
Checks for sensitive keywords:

```json
{
  "type": "check_keywords",
  "operator": "has_keywords"
}
```

**Operators:**
- `has_keywords`: Returns true if any sensitive keywords are detected

### 4. Count Check (`check_count`)
Checks numeric values:

```json
{
  "type": "check_count",
  "field": "image_count",
  "operator": "greater_than",
  "value": 0
}
```

**Operators:**
- `greater_than`
- `greater_than_or_equal`
- `less_than`
- `less_than_or_equal`
- `equals`
- `not_equals`

**Fields:**
- `image_count`: Number of images in the document
- Any numeric field from detections

### 5. Logical Operators (`check_images_and_keywords`)
Combines multiple conditions with logical operators:

```json
{
  "type": "check_images_and_keywords",
  "operator": "and",
  "conditions": [
    {
      "type": "check_count",
      "field": "image_count",
      "operator": "greater_than",
      "value": 0
    },
    {
      "type": "check_keywords",
      "operator": "has_keywords"
    }
  ]
}
```

**Operators:**
- `and`: All conditions must be true
- `or`: At least one condition must be true
- `not`: Negates the first condition

## Example Tree

Here's a complete example that mirrors the default hardcoded logic:

```json
{
  "version": "1.0",
  "description": "Default decision tree for prompt selection",
  "tree": {
    "type": "node",
    "priority": 1,
    "condition": {
      "type": "check_safety",
      "operator": "has_unsafe_pages"
    },
    "if_true": {
      "type": "leaf",
      "prompt": "safety_focused"
    },
    "if_false": {
      "type": "node",
      "priority": 2,
      "condition": {
        "type": "check_pii",
        "operator": "has_high_risk_pii",
        "pii_types": ["SSN", "CREDIT_CARD", "CREDIT_CARD_NUMBER", "US_BANK_ACCOUNT", "US_ROUTING_NUMBER", "BANK_ACCOUNT"],
        "exclude_types": ["DRIVER_LICENSE", "DRIVER"]
      },
      "if_true": {
        "type": "leaf",
        "prompt": "pii_focused"
      },
      "if_false": {
        "type": "node",
        "priority": 3,
        "condition": {
          "type": "check_images_and_keywords",
          "operator": "and",
          "conditions": [
            {
              "type": "check_count",
              "field": "image_count",
              "operator": "greater_than",
              "value": 0
            },
            {
              "type": "check_keywords",
              "operator": "has_keywords"
            }
          ]
        },
        "if_true": {
          "type": "leaf",
          "prompt": "image_focused"
        },
        "if_false": {
          "type": "leaf",
          "prompt": "base_classification"
        }
      }
    }
  }
}
```

## Usage

### Default Location
The system automatically looks for `config/prompt_tree.json` in the project root.

### Custom Location
You can specify a custom tree file when initializing the pipeline:

```python
pipeline = ClassificationPipeline(
    gemini_api_key=...,
    mistral_api_key=...,
    openai_api_key=...,
    tree_file="path/to/custom_tree.json"
)
```

### Fallback Behavior
If the tree file is not found or contains errors, the system falls back to the hardcoded logic for backward compatibility.

## Extending the Tree

To add new condition types:

1. Add the condition evaluation logic in `PromptLibrary._evaluate_condition()`
2. Update this documentation with the new condition type
3. Use the new condition in your tree configuration

## Benefits

1. **No Code Changes**: Modify prompt selection logic without touching code
2. **Easy Testing**: Test different decision paths by editing JSON
3. **Version Control**: Track changes to decision logic in version control
4. **Flexibility**: Support complex branching logic with nested conditions
5. **Maintainability**: Clear separation between logic and configuration

## Priority System

The `priority` field in nodes determines evaluation order (lower numbers = higher priority). This ensures conditions are checked in the correct sequence, matching the original hardcoded logic.

