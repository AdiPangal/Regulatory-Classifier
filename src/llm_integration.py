"""LLM integration for Gemini 2.5 Flash and Mistral 7B."""
import json
import re
from typing import Dict, Optional, List
from google import genai
from google.genai import types
from mistralai import Mistral


def normalize_classification(classification: str) -> str:
    """Normalize classification to one of the three valid categories.
    
    Valid categories: Public, Confidential, Highly Sensitive
    Note: "Unsafe" is NOT a classification - it's a separate safety flag.
    All documents have a classification (Public/Confidential/Highly Sensitive)
    AND a safety status (Safe/Unsafe for child safety).
    
    Args:
        classification: Raw classification string from LLM
        
    Returns:
        Normalized classification string (Public, Confidential, or Highly Sensitive)
    """
    if not classification:
        return "Public"
    
    classification_lower = classification.lower().strip()
    
    # Map variations to standard categories (exclude "unsafe" - that's a safety flag, not a classification)
    if "highly sensitive" in classification_lower or "highly-sensitive" in classification_lower:
        return "Highly Sensitive"
    elif "confidential" in classification_lower:
        return "Confidential"
    elif "public" in classification_lower or "not highly sensitive" in classification_lower or "not highly-sensitive" in classification_lower:
        return "Public"
    else:
        # Default to Public if unclear
        return "Public"


class LLMIntegration:
    """Handles LLM API calls for classification."""
    
    def __init__(
        self,
        gemini_api_key: str,
        mistral_api_key: str,
        primary_model: str = "gemini-2.5-flash",
        secondary_model: str = "mistral-small-2503"  # Updated from deprecated mistral-small (Mistral Small 3.1)
    ):
        """Initialize LLM integration.
        
        Args:
            gemini_api_key: Google Gemini API key
            mistral_api_key: Mistral AI API key
            primary_model: Primary LLM model name
            secondary_model: Secondary LLM model name
        """
        # Initialize Gemini with new Client API
        try:
            self.client = genai.Client(api_key=gemini_api_key)
            self.primary_model_name = primary_model
        except Exception as e:
            raise ValueError(f"Could not initialize Gemini client: {str(e)}")
        
        # Initialize Mistral (v1.9.x+ uses api_key parameter)
        self.mistral_client = Mistral(api_key=mistral_api_key)
        self.secondary_model_name = secondary_model
    
    def classify_with_gemini(self, prompt: str) -> Dict:
        """Classify document using Gemini 2.5 Flash.
        
        Args:
            prompt: Classification prompt
            
        Returns:
            Dictionary with classification results
        """
        try:
            # Generate response using new Client API
            try:
                response = self.client.models.generate_content(
                    model=self.primary_model_name,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        top_p=0.95,
                        top_k=40,
                    ),
                    contents=prompt
                )
            except Exception as model_error:
                # If model fails, try alternative model names
                error_str = str(model_error).lower()
                error_type = type(model_error).__name__
                
                # Log the actual error for debugging
                print(f"DEBUG: Model error type: {error_type}, message: {str(model_error)[:200]}")
                
                if "not found" in error_str or "not supported" in error_str or "404" in error_str:
                    # Try alternative model names (skip the one that just failed)
                    alternative_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
                    # Remove the current model from alternatives if it's already in the list
                    if self.primary_model_name in alternative_models:
                        alternative_models.remove(self.primary_model_name)
                    
                    for alt_model in alternative_models:
                        try:
                            print(f"DEBUG: Trying fallback model: {alt_model}")
                            response = self.client.models.generate_content(
                                model=alt_model,
                                config=types.GenerateContentConfig(
                                    temperature=0.1,
                                    top_p=0.95,
                                    top_k=40,
                                ),
                                contents=prompt
                            )
                            # Update the primary model name for future use
                            self.primary_model_name = alt_model
                            print(f"DEBUG: Successfully used fallback model: {alt_model}")
                            break
                        except Exception as fallback_error:
                            print(f"DEBUG: Fallback model {alt_model} also failed: {str(fallback_error)[:200]}")
                            continue
                    else:
                        # If all models fail, raise the original error
                        raise model_error
                else:
                    raise model_error
            
            # Extract text
            response_text = response.text
            
            # Try to parse JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
            else:
                # Fallback: try to extract classification from text
                result = self._parse_classification_from_text(response_text)
            
            # Ensure required fields and normalize classification
            if "classification" not in result:
                result["classification"] = "Public"  # Default
            else:
                # Normalize classification to ensure consistency
                result["classification"] = normalize_classification(result["classification"])
            if "confidence" not in result:
                result["confidence"] = 0.5
            if "reasons" not in result:
                result["reasons"] = []
            if "evidence_pages" not in result:
                result["evidence_pages"] = []
            if "citations" not in result:
                result["citations"] = []
            if "reasoning" not in result:
                result["reasoning"] = response_text[:500]  # Use first 500 chars as reasoning
            
            result["model"] = self.primary_model_name
            result["raw_response"] = response_text
            
            return result
            
        except Exception as e:
            # Check if it's an API key or model configuration issue
            error_str = str(e).lower()
            if "api key" in error_str or "not found" in error_str or "not supported" in error_str:
                error_msg = (
                    "LLM API configuration error. Please check:\n"
                    "1. GEMINI_API_KEY is set in .env file\n"
                    "2. API key is valid and has access to the model\n"
                    "3. Model name is correct (tried: gemini-2.5-flash, gemini-1.5-flash, gemini-pro, etc.)\n"
                    f"Original error: {str(e)}"
                )
            else:
                error_msg = str(e)
            
            # Return error result with clear message
            return {
                "classification": "Public",  # Default to Public on error
                "confidence": 0.0,
                "reasons": [f"LLM Error: {error_msg}"],
                "evidence_pages": [],
                "citations": [],
                "reasoning": f"Classification failed due to LLM error. {error_msg}",
                "model": self.primary_model_name,
                "error": error_msg,
                "needs_review": True  # Flag for manual review
            }
    
    def validate_with_mistral(self, primary_result: Dict, prompt: str, document_text: str) -> Dict:
        """Validate classification using Mistral 7B.
        
        Args:
            primary_result: Result from primary LLM
            prompt: Original classification prompt
            document_text: Document text for context
            
        Returns:
            Dictionary with validation results
        """
        try:
            # Create validation prompt
            validation_prompt = f"""You are a secondary validator reviewing a classification decision.

Primary Classification Result:
{json.dumps(primary_result, indent=2)}

Document Text (first 2000 chars):
{document_text[:2000]}

Review the primary classification and either:
1. **Agree** - Confirm the classification is correct
2. **Disagree** - Suggest a different classification with reasoning

Return JSON:
{{
    "agreement": true|false,
    "agreed_classification": "Public|Confidential|Highly Sensitive|Unsafe",
    "confidence": 0.0-1.0,
    "reasoning": "Why you agree or disagree",
    "suggested_classification": "Public|Confidential|Highly Sensitive|Unsafe" (if disagreeing)
}}"""
            
            # Call Mistral API (v1.9.x+ uses chat.complete method)
            messages = [
                {
                    "role": "user",
                    "content": validation_prompt
                }
            ]
            
            # Use the standard Mistral API v1.9.x+ method
            response = self.mistral_client.chat.complete(
                model=self.secondary_model_name,
                messages=messages,
                temperature=0.1
            )
            
            # Extract response content
            response_text = response.choices[0].message.content
            
            # Parse JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
            else:
                # Fallback parsing
                result = {
                    "agreement": "agree" in response_text.lower(),
                    "agreed_classification": normalize_classification(primary_result.get("classification", "Public")),
                    "confidence": 0.5,
                    "reasoning": response_text[:500]
                }
            
            result["model"] = self.secondary_model_name
            result["raw_response"] = response_text
            
            return result
            
        except Exception as e:
            # Return agreement by default if validation fails
            return {
                "agreement": True,
                "agreed_classification": normalize_classification(primary_result.get("classification", "Public")),
                "confidence": 0.5,
                "reasoning": f"Validation failed: {str(e)}",
                "model": self.secondary_model_name,
                "error": str(e)
            }
    
    def _parse_classification_from_text(self, text: str) -> Dict:
        """Parse classification from unstructured text response.
        
        Args:
            text: LLM response text
            
        Returns:
            Dictionary with parsed classification
        """
        # Try to extract classification
        classification = "Public"
        for cat in ["Highly Sensitive", "Unsafe", "Confidential", "Public", "Not Highly Sensitive"]:
            if cat.lower() in text.lower():
                classification = cat
                break
        
        # Normalize the classification
        classification = normalize_classification(classification)
        
        # Try to extract confidence
        confidence_match = re.search(r'confidence[:\s]+([0-9.]+)', text, re.IGNORECASE)
        confidence = float(confidence_match.group(1)) if confidence_match else 0.5
        
        # Extract reasons (look for bullet points or numbered lists)
        reasons = []
        reason_patterns = [
            r'[-•]\s*(.+?)(?:\n|$)',
            r'\d+[\.\)]\s*(.+?)(?:\n|$)',
            r'reason[:\s]+(.+?)(?:\n|$)'
        ]
        for pattern in reason_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            reasons.extend(matches[:3])  # Limit to 3 reasons
        
        return {
            "classification": classification,
            "confidence": confidence,
            "reasons": reasons if reasons else [text[:200]],
            "evidence_pages": [],
            "citations": [],
            "reasoning": text
        }
    
    def classify_with_dual_validation(
        self,
        prompt: str,
        document_text: str,
        enable_secondary: bool = True,
        confidence_threshold: float = 0.9
    ) -> Dict:
        """Classify document with primary LLM and optional secondary validation.
        
        Args:
            prompt: Classification prompt
            document_text: Document text for context
            enable_secondary: Whether to use secondary validation
            confidence_threshold: Skip secondary if primary confidence > threshold (default 0.9)
            
        Returns:
            Dictionary with combined classification results
        """
        # Primary classification
        primary_result = self.classify_with_gemini(prompt)
        
        # Get primary confidence
        primary_confidence = primary_result.get("confidence", 0.5)
        
        # Conditional dual validation: skip secondary if primary confidence is high
        if not enable_secondary:
            return {
                "primary": primary_result,
                "secondary": None,
                "final_classification": normalize_classification(primary_result.get("classification", "Public")),
                "final_confidence": primary_confidence,
                "consensus": True,
                "secondary_skipped": False
            }
        
        # Skip secondary validation if primary confidence is high
        if primary_confidence > confidence_threshold:
            return {
                "primary": primary_result,
                "secondary": None,
                "final_classification": normalize_classification(primary_result.get("classification", "Public")),
                "final_confidence": primary_confidence,
                "consensus": True,
                "secondary_skipped": True,
                "skip_reason": f"Primary confidence {primary_confidence:.2f} > threshold {confidence_threshold}"
            }
        
        # Secondary validation (only for uncertain cases)
        secondary_result = self.validate_with_mistral(primary_result, prompt, document_text)
        
        # Determine consensus
        primary_class = normalize_classification(primary_result.get("classification", "Public"))
        secondary_class = normalize_classification(secondary_result.get("agreed_classification", primary_class))
        agreement = secondary_result.get("agreement", True)
        
        consensus = (primary_class == secondary_class) and agreement
        
        # Use primary classification, but adjust confidence based on consensus
        final_classification = primary_class
        final_confidence = primary_result.get("confidence", 0.5)
        
        if not consensus:
            # Lower confidence if models disagree
            final_confidence = min(final_confidence, 0.6)
        
        return {
            "primary": primary_result,
            "secondary": secondary_result,
            "final_classification": final_classification,
            "final_confidence": final_confidence,
            "consensus": consensus,
            "needs_review": not consensus,
            "secondary_skipped": False
        }

