"""Few-shot learning example generator for prompt enhancement."""
import json
import random
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from collections import defaultdict


class FewShotGenerator:
    """Generates diverse few-shot examples from a labeled dataset."""
    
    def __init__(self, dataset_path: str):
        """Initialize the few-shot generator.
        
        Args:
            dataset_path: Path to JSON dataset file
        """
        self.dataset_path = Path(dataset_path)
        self.dataset = self._load_dataset()
        self._index_dataset()
    
    def _load_dataset(self) -> List[Dict]:
        """Load the dataset from JSON file."""
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {self.dataset_path}")
        
        with open(self.dataset_path, 'r') as f:
            return json.load(f)
    
    def _index_dataset(self):
        """Index dataset by classification and safety status for efficient sampling."""
        self.by_classification = defaultdict(list)
        self.by_safety = defaultdict(list)
        self.by_combination = defaultdict(list)
        
        for idx, example in enumerate(self.dataset):
            classification = example.get("correct_classification", "Public")
            safety = example.get("safety_status", "Safe")
            combination = f"{classification}_{safety}"
            
            self.by_classification[classification].append(idx)
            self.by_safety[safety].append(idx)
            self.by_combination[combination].append(idx)
    
    def sample_diverse_examples(
        self,
        n_per_class: int = 5,
        include_safety_variants: bool = True,
        max_text_length: int = 500
    ) -> List[Dict]:
        """Sample diverse examples ensuring representation from all classes.
        
        Args:
            n_per_class: Number of examples per classification category
            include_safety_variants: Whether to include both Safe and Unsafe examples
            max_text_length: Maximum text length for examples (to keep prompts manageable)
            
        Returns:
            List of example dictionaries
        """
        examples = []
        
        # Sample from each classification category
        for classification in ["Public", "Confidential", "Highly Sensitive"]:
            available_indices = self.by_classification[classification]
            
            if include_safety_variants:
                # Try to get both Safe and Unsafe examples
                safe_indices = [idx for idx in available_indices 
                               if self.dataset[idx].get("safety_status") == "Safe"]
                unsafe_indices = [idx for idx in available_indices 
                                 if self.dataset[idx].get("safety_status") == "Unsafe"]
                
                # Sample from both
                n_safe = max(1, n_per_class // 2)
                n_unsafe = n_per_class - n_safe
                
                sampled_safe = self._sample_with_length_filter(safe_indices, n_safe, max_text_length)
                sampled_unsafe = self._sample_with_length_filter(unsafe_indices, n_unsafe, max_text_length)
                
                examples.extend([self.dataset[idx] for idx in sampled_safe])
                examples.extend([self.dataset[idx] for idx in sampled_unsafe])
            else:
                # Just sample from the category
                sampled = self._sample_with_length_filter(available_indices, n_per_class, max_text_length)
                examples.extend([self.dataset[idx] for idx in sampled])
        
        # Shuffle to avoid bias
        random.shuffle(examples)
        return examples
    
    def _sample_with_length_filter(
        self,
        indices: List[int],
        n: int,
        max_length: int
    ) -> List[int]:
        """Sample indices with text length filtering.
        
        Args:
            indices: List of dataset indices
            n: Number to sample
            max_length: Maximum text length
            
        Returns:
            List of sampled indices
        """
        # Filter by length
        valid_indices = [
            idx for idx in indices
            if len(self.dataset[idx].get("text", "")) <= max_length
        ]
        
        # If not enough valid, use all available
        if len(valid_indices) < n:
            valid_indices = indices
        
        # Sample
        return random.sample(valid_indices, min(n, len(valid_indices)))
    
    def format_examples_for_prompt(self, examples: List[Dict]) -> str:
        """Format examples as a string for inclusion in prompts.
        
        Args:
            examples: List of example dictionaries
            
        Returns:
            Formatted string with examples
        """
        if not examples:
            return ""
        
        formatted = "\n**FEW-SHOT EXAMPLES:**\n\n"
        
        for i, example in enumerate(examples, 1):
            text = example.get("text", "")
            classification = example.get("correct_classification", "Public")
            safety = example.get("safety_status", "Safe")
            
            # Truncate text if too long
            if len(text) > 400:
                text = text[:397] + "..."
            
            formatted += f"""Example {i}:
Text: "{text}"
Correct Classification: {classification}
Safety Status: {safety}
Reasoning: This is classified as {classification} because {self._generate_reasoning(example)}
---
"""
        
        return formatted
    
    def _generate_reasoning(self, example: Dict) -> str:
        """Generate a brief reasoning explanation for an example.
        
        Args:
            example: Example dictionary
            
        Returns:
            Reasoning string
        """
        text = example.get("text", "").lower()
        classification = example.get("correct_classification", "Public")
        
        if classification == "Public":
            if any(word in text for word in ["marketing", "product", "brochure", "catalog", "announcement", "press release"]):
                return "it is public-facing marketing or promotional material"
            elif any(word in text for word in ["blog", "article", "educational", "how-to", "guide"]):
                return "it is educational or informational content intended for public consumption"
            else:
                return "it contains general information suitable for public distribution"
        
        elif classification == "Highly Sensitive":
            if any(word in text for word in ["ssn", "social security", "credit card", "bank account", "routing"]):
                return "it contains financial/identity PII such as SSNs, credit cards, or bank account numbers"
            elif any(word in text for word in ["employment", "job application", "application form"]):
                return "it is an employment application form that typically collects highly sensitive personal information"
            elif any(word in text for word in ["patient record", "medical", "passport", "encryption key"]):
                return "it contains highly sensitive personal or security information"
            else:
                return "it contains highly sensitive personal or financial information"
        
        else:  # Confidential
            if any(word in text for word in ["internal", "memo", "confidential", "proprietary"]):
                return "it is an internal business document marked as confidential or proprietary"
            elif any(word in text for word in ["technical", "schematic", "defense", "operational"]):
                return "it contains technical or operational information that should remain internal"
            elif any(word in text for word in ["strategy", "pricing", "acquisition", "board briefing"]):
                return "it contains internal business strategy or planning information"
            else:
                return "it contains internal or proprietary information not intended for public distribution"
    
    def get_examples_by_classification(
        self,
        classification: str,
        n: int = 10,
        max_text_length: int = 500
    ) -> List[Dict]:
        """Get examples for a specific classification.
        
        Args:
            classification: Target classification (Public, Confidential, Highly Sensitive)
            n: Number of examples to return
            max_text_length: Maximum text length
            
        Returns:
            List of example dictionaries
        """
        indices = self.by_classification.get(classification, [])
        valid_indices = [
            idx for idx in indices
            if len(self.dataset[idx].get("text", "")) <= max_text_length
        ]
        
        if len(valid_indices) < n:
            valid_indices = indices
        
        sampled = random.sample(valid_indices, min(n, len(valid_indices)))
        return [self.dataset[idx] for idx in sampled]

