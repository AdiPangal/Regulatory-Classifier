"""Configurable prompt library for dynamic prompt generation."""
import json
import re
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

# Import few-shot generator if available
try:
    from .few_shot_generator import FewShotGenerator
    FEW_SHOT_AVAILABLE = True
except ImportError:
    FEW_SHOT_AVAILABLE = False


class PromptLibrary:
    """Manages configurable prompts for document classification."""
    
    def __init__(
        self,
        prompts_file: Optional[str] = None,
        tree_file: Optional[str] = None,
        dataset_file: Optional[str] = None,
        enable_few_shot: bool = True,
        few_shot_examples_per_class: int = 5
    ):
        """Initialize prompt library.
        
        Args:
            prompts_file: Path to JSON file with prompt templates (optional)
            tree_file: Path to JSON file with decision tree configuration (optional)
            dataset_file: Path to JSON dataset file for few-shot learning (optional)
            enable_few_shot: Whether to enable few-shot learning (default: True)
            few_shot_examples_per_class: Number of examples per class for few-shot (default: 5)
        """
        self.prompts_file = prompts_file
        self.tree_file = tree_file
        self.dataset_file = dataset_file
        self.enable_few_shot = enable_few_shot and FEW_SHOT_AVAILABLE
        self.few_shot_examples_per_class = few_shot_examples_per_class
        self.few_shot_generator = None
        self.few_shot_examples = None
        
        # Initialize few-shot generator if dataset provided
        if self.enable_few_shot and dataset_file and FEW_SHOT_AVAILABLE:
            try:
                dataset_path = Path(dataset_file)
                if dataset_path.exists():
                    self.few_shot_generator = FewShotGenerator(str(dataset_path))  # type: ignore
                    # Pre-generate examples for efficiency
                    self.few_shot_examples = self.few_shot_generator.sample_diverse_examples(
                        n_per_class=self.few_shot_examples_per_class
                    )
                else:
                    print(f"Warning: Dataset file not found: {dataset_path}, few-shot learning disabled")
                    self.enable_few_shot = False
            except Exception as e:
                print(f"Warning: Could not initialize few-shot generator: {e}")
                self.enable_few_shot = False
        
        self.prompts = self._load_default_prompts()
        self.decision_tree = None
        
        # Load improvements from refinement history (persist across restarts)
        # NOTE: History loading can be disabled by setting environment variable DISABLE_PROMPT_HISTORY=1
        # This allows testing with simplified default prompts
        import os
        if not os.getenv("DISABLE_PROMPT_HISTORY"):
            self._load_improvements_from_history()
        
        # Load custom prompts if file provided
        if prompts_file and Path(prompts_file).exists():
            self._load_custom_prompts(prompts_file)
        
        # Load decision tree configuration
        if tree_file and Path(tree_file).exists():
            self._load_decision_tree(tree_file)
        else:
            # Try default location
            default_tree = Path(__file__).parent.parent / "config" / "prompt_tree.json"
            if default_tree.exists():
                self._load_decision_tree(str(default_tree))
            else:
                # Fall back to hardcoded logic if no tree file
                self.decision_tree = None
    
    def _load_default_prompts(self) -> Dict:
        """Load default prompt templates."""
        return {
            "base_classification": """You are a compliance classifier. You MUST follow the classification steps in EXACT ORDER. Do NOT skip steps.

**CRITICAL: EVALUATE IN THIS EXACT ORDER - STOP AT FIRST MATCH:**

**STEP 1: Is this PUBLIC marketing material? (CHECK THIS FIRST - DO NOT SKIP)**
- Look at the document content and structure, NOT just keywords.
- If the document is a marketing brochure, product catalog, promotional material, advertisement, or public-facing content, classify as **Public** IMMEDIATELY.
- **IGNORE keywords like "proprietary", "nda", "confidential" if this is marketing material - these are boilerplate legal text.**
- Marketing materials are Public EVEN IF they contain:
  - "PROPRIETARY - nda" keywords (these are legal disclaimers, not classification markers)
  - Names, addresses, phone numbers (common in marketing for contact info)
  - Product images or descriptions
- Indicators: product descriptions, pricing, "contact us", "order now", promotional language, marketing copy.
- **IF THIS IS MARKETING MATERIAL, CLASSIFY AS PUBLIC AND STOP. DO NOT PROCEED TO STEP 2.**

**STEP 2: Is this HIGHLY SENSITIVE? (ONLY CHECK IF NOT MARKETING)**
- Classify as **Highly Sensitive** ONLY if:
  - Document contains actual SSNs (XXX-XX-XXXX format), credit card numbers (16 digits), bank account numbers, OR routing numbers
  - OR document is clearly an employment application, job application form, or resume (these are always Highly Sensitive regardless of PII detected)
- **Note: Names, addresses, phone numbers, email addresses, or driver's license numbers alone are NOT Highly Sensitive - they are Confidential.**

**STEP 3: Is this CONFIDENTIAL? (ONLY IF NOT MARKETING AND NOT HIGHLY SENSITIVE)**
- Classify as **Confidential** if:
  - Internal memo, business document, or technical documentation
  - Contains names, addresses, phone numbers, emails, or driver's license numbers (but NOT SSNs/credit cards)
  - Marked "internal", "confidential", "proprietary", "not for public distribution"
  - Technical specs, schematics, defense equipment details

**ABSOLUTE RULES:**
1. Marketing material = Public (even with "proprietary" keywords - IGNORE those keywords for marketing)
2. SSN/Credit Card/Bank Account OR Employment Application = Highly Sensitive
3. Everything else with PII or internal markers = Confidential

IMPORTANT: All documents are also evaluated for child safety separately. A document can be Public and Safe, Public and Unsafe, Confidential and Safe, Confidential and Unsafe, Highly Sensitive and Safe, or Highly Sensitive and Unsafe. The classification (Public/Confidential/Highly Sensitive) and safety status (Safe/Unsafe) are independent.

Document Information:
- Total Pages: {total_pages}
- Total Images: {total_images}
- Document Legibility: {is_legible}

Extracted Text:
{text}

Detected PII:
{pii_evidence}

Detected Sensitive Keywords:
{keyword_evidence}

Safety Check Results:
{safety_evidence}

Provide your classification in the following JSON format:
{{
    "classification": "Public|Confidential|Highly Sensitive",
    "confidence": 0.0-1.0,
    "reasons": ["reason1", "reason2"],
    "evidence_pages": [1, 2],
    "citations": [
        {{"page": 1, "snippet": "relevant text", "type": "PII|Keyword|Safety|Content"}}
    ],
    "reasoning": "Detailed explanation of why this classification was chosen"
}}""",
            
            "pii_focused": """You are a compliance classifier. This document contains detected PII (Personally Identifiable Information).

**CRITICAL: EVALUATE IN THIS EXACT ORDER - STOP AT FIRST MATCH:**

**STEP 1: Is this PUBLIC marketing material? (CHECK FIRST)**
- If marketing brochure, product catalog, or public-facing material, classify as **Public** IMMEDIATELY.
- **IGNORE keywords like "proprietary", "nda" if this is marketing - these are boilerplate legal text.**
- Marketing materials are Public EVEN IF they contain PII (names, addresses, phone numbers are common in marketing).

**STEP 2: Is this HIGHLY SENSITIVE? (ONLY IF NOT MARKETING)**
- Classify as **Highly Sensitive** ONLY if:
  - Contains actual SSNs (XXX-XX-XXXX format), credit card numbers (16 digits), bank account numbers, OR routing numbers
  - OR is clearly an employment application, job application, or resume (always Highly Sensitive)
- **Note: Names, addresses, phone numbers, emails, or driver's license numbers alone are NOT Highly Sensitive - they are Confidential.**

**STEP 3: Other PII = CONFIDENTIAL (ONLY IF NOT MARKETING AND NOT HIGHLY SENSITIVE)**
- If document contains only names, addresses, phone numbers, emails, driver's license numbers, or technical info, classify as **Confidential**.
- Driver's license numbers alone = Confidential, NOT Highly Sensitive.

Detected PII:
{pii_evidence}

Document Text:
{text}

Provide specific citations of where PII was found.

Return JSON:
{{
    "classification": "Highly Sensitive",
    "confidence": 0.0-1.0,
    "reasons": ["SSN found on page X", "Credit card number detected"],
    "evidence_pages": [X],
    "citations": [{{"page": X, "snippet": "SSN: XXX-XX-XXXX", "type": "PII"}}],
    "reasoning": "Explanation"
}}""",
            
            "safety_focused": """You are a safety compliance classifier. This document may contain unsafe content.

Safety Check Results:
{safety_evidence}

Document Text:
{text}

Note: Child safety is evaluated separately from classification. A document can be Public/Confidential/Highly Sensitive AND Safe or Unsafe. The safety check is independent of the classification.

Return JSON:
{{
    "classification": "Public|Confidential|Highly Sensitive",
    "confidence": 0.0-1.0,
    "reasons": ["Reason 1", "Reason 2"],
    "evidence_pages": [X],
    "citations": [{{"page": X, "snippet": "problematic text", "type": "Safety"}}],
    "reasoning": "Explanation"
}}""",
            
            "image_focused": """You are a compliance classifier analyzing images and visual content.

Document Information:
- Total Pages: {total_pages}
- Total Images: {total_images}
- Image Descriptions: {image_descriptions}

Detected Sensitive Keywords:
{keyword_evidence}

Classify this document. Technical documents with schematics, part names, or defense equipment details should be classified as **Confidential**. Only classify as **Highly Sensitive** if the document contains actual financial/identity PII (SSNs, credit card numbers, bank account numbers) in addition to technical content.

Return JSON:
{{
    "classification": "Confidential",
    "confidence": 0.0-1.0,
    "reasons": ["Stealth fighter image with serial numbers", "Proprietary design visible"],
    "evidence_pages": [X],
    "citations": [{{"page": X, "snippet": "Image region with serial number", "type": "Image"}}],
    "reasoning": "Explanation"
}}""",
            
            "secondary_validation": """You are a secondary validator reviewing a classification decision.

Primary Classification Result:
{primary_classification}

Document Text:
{text}

Detected Evidence:
{pii_evidence}
{keyword_evidence}
{safety_evidence}

Review the primary classification and either:
1. **Agree** - Confirm the classification is correct
2. **Disagree** - Suggest a different classification with reasoning

Return JSON:
{{
    "agreement": true|false,
    "agreed_classification": "Public|Confidential|Highly Sensitive",
    "confidence": 0.0-1.0,
    "reasoning": "Why you agree or disagree",
    "suggested_classification": "Public|Confidential|Highly Sensitive" (if disagreeing)
}}"""
        }
    
    def _load_custom_prompts(self, file_path: str):
        """Load custom prompts from JSON file.
        
        Args:
            file_path: Path to JSON file with prompt templates
        """
        try:
            with open(file_path, 'r') as f:
                custom_prompts = json.load(f)
                self.prompts.update(custom_prompts)
        except Exception as e:
            print(f"Warning: Could not load custom prompts from {file_path}: {e}")
    
    def get_prompt(self, prompt_name: str, **kwargs) -> str:
        """Get a formatted prompt by name.
        
        Args:
            prompt_name: Name of the prompt template
            **kwargs: Variables to format into the prompt
            
        Returns:
            Formatted prompt string
        """
        if prompt_name not in self.prompts:
            raise ValueError(f"Prompt '{prompt_name}' not found in library")
        
        template = self.prompts[prompt_name]
        
        # Inject few-shot examples if enabled
        if self.enable_few_shot and self.few_shot_examples and self.few_shot_generator:
            # Add few-shot examples before the document information
            few_shot_text = self.few_shot_generator.format_examples_for_prompt(self.few_shot_examples)
            
            # Insert few-shot examples after the rules but before document info
            # Find a good insertion point (after the IMPORTANT note, before Document Information)
            if "IMPORTANT: All documents" in template:
                # Insert after the IMPORTANT section
                parts = template.split("IMPORTANT: All documents are also evaluated for child safety separately.")
                if len(parts) == 2:
                    template = parts[0] + "IMPORTANT: All documents are also evaluated for child safety separately.\n\n" + few_shot_text + "\n" + parts[1]
                else:
                    # Fallback: insert before Document Information
                    template = template.replace("Document Information:", few_shot_text + "\n\nDocument Information:")
            else:
                # Fallback: insert before Document Information
                template = template.replace("Document Information:", few_shot_text + "\n\nDocument Information:")
        
        return template.format(**kwargs)
    
    def _load_decision_tree(self, file_path: str):
        """Load decision tree configuration from JSON file.
        
        Args:
            file_path: Path to JSON file with tree configuration
        """
        try:
            with open(file_path, 'r') as f:
                tree_config = json.load(f)
                self.decision_tree = tree_config.get("tree")
                if not self.decision_tree:
                    print(f"Warning: No 'tree' key found in {file_path}, using hardcoded logic")
                    self.decision_tree = None
        except Exception as e:
            print(f"Warning: Could not load decision tree from {file_path}: {e}")
            self.decision_tree = None
    
    def _evaluate_condition(self, condition: Dict, detections: Dict) -> bool:
        """Evaluate a condition node against detections.
        
        Args:
            condition: Condition configuration dictionary
            detections: Detection results dictionary
            
        Returns:
            True if condition is met, False otherwise
        """
        condition_type = condition.get("type")
        operator = condition.get("operator")
        
        if condition_type == "check_safety":
            if operator == "has_unsafe_pages":
                safety_issues = detections.get("safety_issues", [])
                unsafe_pages = [d for d in safety_issues if d.get("is_unsafe", False)]
                return len(unsafe_pages) > 0
        
        elif condition_type == "check_pii":
            if operator == "has_high_risk_pii":
                pii_detections = detections.get("pii_detections", [])
                pii_pages = [d for d in pii_detections if d.get("count", 0) > 0]
                if not pii_pages:
                    return False
                
                # Get allowed and excluded PII types
                allowed_types = condition.get("pii_types", [])
                exclude_types = condition.get("exclude_types", [])
                
                for pii_page in pii_pages:
                    matches = pii_page.get("matches", [])
                    for match in matches:
                        pii_type = match.get("type", "").upper()
                        
                        # Check exclusions first
                        if any(exclude_type.upper() in pii_type for exclude_type in exclude_types):
                            continue
                        
                        # Check if it's a high-risk type
                        if any(allowed_type.upper() in pii_type for allowed_type in allowed_types):
                            # Also check the actual text for SSN patterns
                            text = match.get("text", "")
                            if "SSN" in pii_type or re.search(r'\b\d{3}-\d{2}-\d{4}\b', text) or re.search(r'\b\d{3}\s\d{2}\s\d{4}\b', text):
                                return True
                            elif "CREDIT_CARD" in pii_type or "BANK_ACCOUNT" in pii_type or "ROUTING" in pii_type:
                                return True
                return False
        
        elif condition_type == "check_keywords":
            if operator == "has_keywords":
                keyword_detections = detections.get("keyword_detections", [])
                keyword_pages = [d for d in keyword_detections if d.get("count", 0) > 0]
                return len(keyword_pages) > 0
        
        elif condition_type == "check_count":
            field = condition.get("field")
            value = condition.get("value")
            field_value = detections.get(field, 0)
            
            if operator == "greater_than":
                return field_value > value
            elif operator == "greater_than_or_equal":
                return field_value >= value
            elif operator == "less_than":
                return field_value < value
            elif operator == "less_than_or_equal":
                return field_value <= value
            elif operator == "equals":
                return field_value == value
            elif operator == "not_equals":
                return field_value != value
        
        elif condition_type == "check_images_and_keywords":
            # Handle logical operators (AND, OR, NOT)
            logical_op = condition.get("operator", "and")
            sub_conditions = condition.get("conditions", [])
            
            if logical_op == "and":
                return all(self._evaluate_condition(sub_cond, detections) for sub_cond in sub_conditions)
            elif logical_op == "or":
                return any(self._evaluate_condition(sub_cond, detections) for sub_cond in sub_conditions)
            elif logical_op == "not":
                if sub_conditions:
                    return not self._evaluate_condition(sub_conditions[0], detections)
        
        # Default: condition not recognized, return False
        return False
    
    def _evaluate_tree_node(self, node: Dict, detections: Dict) -> Optional[str]:
        """Recursively evaluate a tree node.
        
        Args:
            node: Tree node configuration
            detections: Detection results dictionary
            
        Returns:
            Prompt name if leaf node is reached, None otherwise
        """
        node_type = node.get("type")
        
        if node_type == "leaf":
            # Leaf node: return the prompt name
            return node.get("prompt")
        
        elif node_type == "node":
            # Internal node: evaluate condition
            condition = node.get("condition")
            if not condition:
                return None
            
            condition_result = self._evaluate_condition(condition, detections)
            
            # Navigate based on condition result
            if condition_result:
                next_node = node.get("if_true")
            else:
                next_node = node.get("if_false")
            
            if next_node:
                return self._evaluate_tree_node(next_node, detections)
        
        return None
    
    def select_prompt(self, detections: Dict) -> str:
        """Dynamically select prompt based on detected features.
        
        Uses configurable decision tree if available, otherwise falls back to hardcoded logic.
        
        Args:
            detections: Dictionary with detection results (PII, keywords, safety)
            
        Returns:
            Name of the selected prompt
        """
        # Use configurable tree if available
        if self.decision_tree:
            try:
                result = self._evaluate_tree_node(self.decision_tree, detections)
                if result:
                    return result
            except Exception as e:
                print(f"Warning: Error evaluating decision tree: {e}, falling back to hardcoded logic")
        
        # Fallback to hardcoded logic (backward compatibility)
        return self._select_prompt_hardcoded(detections)
    
    def _select_prompt_hardcoded(self, detections: Dict) -> str:
        """Hardcoded prompt selection logic (fallback).
        
        Args:
            detections: Dictionary with detection results
            
        Returns:
            Name of the selected prompt
        """
        # Check for unsafe content first (highest priority)
        if detections.get("safety_issues", []):
            unsafe_pages = [d for d in detections["safety_issues"] if d.get("is_unsafe", False)]
            if unsafe_pages:
                return "safety_focused"
        
        # Check for actual financial/identity PII (high priority for Highly Sensitive)
        # Only trigger pii_focused if we detect SSN, credit card, or bank account numbers
        if detections.get("pii_detections", []):
            pii_pages = [d for d in detections["pii_detections"] if d.get("count", 0) > 0]
            if pii_pages:
                # Check if PII includes high-risk financial/identity data
                # Only SSN, credit card, and bank account numbers trigger Highly Sensitive
                # Driver's license, names, addresses, phone numbers, emails are Confidential, not Highly Sensitive
                high_risk_pii_types = ["SSN", "CREDIT_CARD", "CREDIT_CARD_NUMBER", "US_BANK_ACCOUNT", "US_ROUTING_NUMBER", "BANK_ACCOUNT"]
                has_high_risk_pii = False
                for pii_page in pii_pages:
                    matches = pii_page.get("matches", [])
                    for match in matches:
                        pii_type = match.get("type", "").upper()
                        # Explicitly exclude driver's license from high-risk
                        if "DRIVER_LICENSE" in pii_type or "DRIVER" in pii_type:
                            continue  # Skip driver's license - it's Confidential, not Highly Sensitive
                        # Check for exact matches or key substrings
                        if any(risk_type in pii_type for risk_type in high_risk_pii_types):
                            # Also check the actual text for SSN patterns
                            text = match.get("text", "")
                            if "SSN" in pii_type or re.search(r'\b\d{3}-\d{2}-\d{4}\b', text) or re.search(r'\b\d{3}\s\d{2}\s\d{4}\b', text):
                                has_high_risk_pii = True
                                break
                            elif "CREDIT_CARD" in pii_type or "BANK_ACCOUNT" in pii_type or "ROUTING" in pii_type:
                                has_high_risk_pii = True
                                break
                    if has_high_risk_pii:
                        break
                if has_high_risk_pii:
                    return "pii_focused"
                # If only names, addresses, phone numbers, emails, driver's licenses - these are Confidential, not Highly Sensitive
        
        # Check for images with sensitive keywords
        if detections.get("image_count", 0) > 0 and detections.get("keyword_detections", []):
            keyword_pages = [d for d in detections["keyword_detections"] if d.get("count", 0) > 0]
            if keyword_pages:
                return "image_focused"
        
        # Default to base classification
        return "base_classification"
    
    def format_evidence(self, detections: Dict) -> Dict:
        """Format detection evidence for prompt insertion.
        
        Args:
            detections: Dictionary with all detection results
            
        Returns:
            Dictionary with formatted evidence strings
        """
        # Format PII evidence
        pii_evidence = "None detected"
        if detections.get("pii_detections"):
            pii_list = []
            for pii_page in detections["pii_detections"]:
                if pii_page.get("count", 0) > 0:
                    matches = pii_page.get("matches", [])
                    for match in matches:
                        pii_list.append(f"Page {pii_page['page']}: {match['type']} - {match['text']}")
            if pii_list:
                pii_evidence = "\n".join(pii_list)
        
        # Format keyword evidence
        keyword_evidence = "None detected"
        if detections.get("keyword_detections"):
            keyword_list = []
            for kw_page in detections["keyword_detections"]:
                if kw_page.get("count", 0) > 0:
                    matches = kw_page.get("matches", [])
                    for match in matches:
                        keyword_list.append(f"Page {kw_page['page']}: {match['type']} - {match['keyword']}")
            if keyword_list:
                keyword_evidence = "\n".join(keyword_list)
        
        # Format safety evidence
        safety_evidence = "No safety concerns detected"
        if detections.get("safety_issues"):
            safety_list = []
            for safety_page in detections["safety_issues"]:
                if safety_page.get("is_unsafe", False):
                    concerns = safety_page.get("primary_concerns", [])
                    safety_list.append(f"Page {safety_page['page']}: UNSAFE - {', '.join(concerns)}")
            if safety_list:
                safety_evidence = "\n".join(safety_list)
        
        return {
            "pii_evidence": pii_evidence,
            "keyword_evidence": keyword_evidence,
            "safety_evidence": safety_evidence
        }
    
    def _load_improvements_from_history(self):
        """Load auto-applied prompt improvements from refinement history.
        
        This ensures that improvements persist across server restarts.
        Only loads improvements that were auto-applied (auto_applied=True).
        """
        history_file = Path("prompt_refinement_history.json")
        if not history_file.exists():
            return
        
        try:
            with open(history_file, 'r') as f:
                history = json.load(f)
            
            # Group by prompt_name and get the latest auto-applied improvement for each
            prompt_improvements = {}
            for record in history:
                prompt_name = record.get("prompt_name")
                auto_applied = record.get("auto_applied", False)
                new_prompt = record.get("new_prompt")
                
                if prompt_name and auto_applied and new_prompt:
                    # Keep only the latest improvement for each prompt (history is chronological)
                    if prompt_name not in prompt_improvements:
                        prompt_improvements[prompt_name] = new_prompt
                    else:
                        # If we already have one, check timestamp to get the latest
                        # Since history is typically in chronological order, we'll just update
                        # But to be safe, we could compare timestamps - for now, just take the last one
                        prompt_improvements[prompt_name] = new_prompt
            
            # Apply improvements to prompts
            for prompt_name, improved_prompt in prompt_improvements.items():
                if prompt_name in self.prompts:
                    self.prompts[prompt_name] = improved_prompt
                    print(f"Loaded persisted improvement for prompt '{prompt_name}' from history")
                else:
                    print(f"Warning: Prompt '{prompt_name}' in history not found in prompt library")
                    
        except Exception as e:
            print(f"Warning: Could not load improvements from history: {e}")
    
    def save_prompts(self, file_path: str):
        """Save current prompts to JSON file.
        
        Args:
            file_path: Path to save prompts
        """
        with open(file_path, 'w') as f:
            json.dump(self.prompts, f, indent=2)

