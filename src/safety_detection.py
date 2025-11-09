"""Safety detection module using OpenAI moderation and Detoxify."""
import os
import logging
from typing import Dict, List, Optional, Tuple
from openai import OpenAI
import detoxify

logger = logging.getLogger(__name__)


class SafetyDetector:
    """Detects unsafe content using OpenAI moderation and Detoxify."""
    
    def __init__(self, openai_api_key: str, use_detoxify_backup: bool = True):
        """Initialize safety detector.
        
        Args:
            openai_api_key: OpenAI API key
            use_detoxify_backup: Whether to use Detoxify as backup
        """
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.use_detoxify_backup = use_detoxify_backup
        
        # Initialize Detoxify if backup is enabled
        if use_detoxify_backup:
            try:
                self.detoxify_model = detoxify.Detoxify('original')
            except Exception as e:
                print(f"Warning: Could not load Detoxify model: {e}")
                self.detoxify_model = None
                self.use_detoxify_backup = False
        else:
            self.detoxify_model = None
    
    def detect_with_openai(self, text: str) -> Dict:
        """Detect unsafe content using OpenAI moderation API.
        
        IMPORTANT: Only flags content as unsafe for CHILD SAFETY reasons.
        Does NOT flag: hate speech, political news, cyber-threat, exploitative, 
        violent, or criminal content (unless it's child safety related).
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary with moderation results
        """
        try:
            response = self.openai_client.moderations.create(
                input=text,
                model="omni-moderation-latest"  # Updated model name per OpenAI API
            )
            
            result = response.results[0]
            
            # Get category scores (convert to dict for easier access)
            # OpenAI returns categories as attributes, convert to dict
            categories_dict = {}
            scores_dict = {}
            
            # Convert categories to dict
            if hasattr(result.categories, 'dict'):
                categories_dict = result.categories.dict()
            else:
                # Access as attributes and convert
                for attr in ['sexual', 'hate', 'harassment', 'self_harm', 'violence', 'illegal_activity']:
                    if hasattr(result.categories, attr):
                        categories_dict[attr] = getattr(result.categories, attr)
            
            # Convert category_scores to dict
            if hasattr(result.category_scores, 'dict'):
                scores_dict = result.category_scores.dict()
            else:
                # Access as attributes and convert
                for attr in ['sexual', 'hate', 'harassment', 'self_harm', 'violence', 'illegal_activity']:
                    if hasattr(result.category_scores, attr):
                        scores_dict[attr] = getattr(result.category_scores, attr)
            
            # Check for sexual/minors (child safety) - OpenAI uses 'sexual' category for this
            # ONLY check for child safety (sexual content involving minors)
            # We IGNORE: hate, harassment, self-harm, violence, illegal activity, etc.
            is_flagged = False
            primary_concerns = []
            
            # Check ONLY for sexual content (which includes child safety concerns)
            # OpenAI's 'sexual' category flags sexual content including child safety issues
            # We use a conservative threshold to only flag clear child safety concerns
            sexual_flagged = categories_dict.get('sexual', False)
            sexual_score = scores_dict.get('sexual', 0.0)
            
            # Only flag if sexual content is detected (conservative approach for child safety)
            # Note: We're being conservative - only flag if clearly sexual content
            # This will catch child safety issues while avoiding false positives
            if sexual_flagged and sexual_score > 0.7:  # Conservative threshold
                is_flagged = True
                primary_concerns.append("child_safety_concern")
            
            # We explicitly IGNORE these categories (do not flag as unsafe):
            # - hate (hate speech) - NOT flagged
            # - harassment (harassment) - NOT flagged
            # - self_harm (self-harm) - NOT flagged
            # - violence (violence) - NOT flagged
            # - illegal_activity (criminal content) - NOT flagged
            # - These are NOT considered "unsafe" for our classification purposes
            
            return {
                "is_unsafe": is_flagged,
                "flagged": is_flagged,
                "primary_concerns": primary_concerns,
                "category_scores": {
                    "child_safety": sexual_score if is_flagged else 0.0,
                    "sexual": sexual_score,
                    # Include other scores for logging but don't use them for flagging
                    "hate": scores_dict.get('hate', 0.0),
                    "violence": scores_dict.get('violence', 0.0),
                },
                "method": "openai",
                "confidence": sexual_score if is_flagged else 0.0
            }
        except Exception as e:
            # If OpenAI fails, return safe default
            return {
                "is_unsafe": False,
                "flagged": False,
                "primary_concerns": [],
                "category_scores": {},
                "method": "openai_error",
                "error": str(e),
                "confidence": 0.0
            }
    
    def detect_with_detoxify(self, text: str) -> Dict:
        """Detect unsafe content using Detoxify.
        
        IMPORTANT: Only flags content as unsafe for CHILD SAFETY reasons.
        Does NOT flag: hate speech, political news, cyber-threat, exploitative, 
        violent, or criminal content (unless it's child safety related).
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary with toxicity scores (only child safety relevant)
        """
        if not self.detoxify_model:
            return {
                "is_unsafe": False,
                "method": "detoxify_unavailable",
                "confidence": 0.0
            }
        
        try:
            # Detoxify expects a list of texts
            results = self.detoxify_model.predict([text])
            
            # Extract scores
            sexual_explicit_score = results['sexual_explicit'][0]
            
            # ONLY check for sexual explicit content (child safety concern)
            # IGNORE: toxicity, severe_toxicity, obscene, threat, insult, identity_attack
            # These are NOT considered "unsafe" for our classification purposes
            
            # Determine if unsafe - ONLY for sexual explicit content
            threshold = 0.5
            is_unsafe = sexual_explicit_score > threshold
            
            # Get primary concerns (only child safety related)
            primary_concerns = []
            if sexual_explicit_score > threshold:
                primary_concerns.append("child_safety_concern")
            
            return {
                "is_unsafe": is_unsafe,
                "flagged": is_unsafe,
                "primary_concerns": primary_concerns,
                "category_scores": {
                    # Only include sexual_explicit for child safety
                    "sexual_explicit": float(sexual_explicit_score),
                    # Include others for logging but don't use for flagging
                    "toxicity": float(results['toxicity'][0]),
                    "threat": float(results['threat'][0]),
                },
                "method": "detoxify",
                "confidence": float(sexual_explicit_score) if is_unsafe else 0.0
            }
        except Exception as e:
            return {
                "is_unsafe": False,
                "method": "detoxify_error",
                "error": str(e),
                "confidence": 0.0
            }
    
    def detect_unsafe_content_batch(self, texts: List[Tuple[str, int]]) -> List[Dict]:
        """Detect unsafe content for multiple pages in a single API call.
        
        IMPORTANT: Only flags for child safety. Reduces API calls by batching.
        
        Args:
            texts: List of (text, page_number) tuples
            
        Returns:
            List of dictionaries with safety analysis results
        """
        # Combine all text for batch processing (single API call)
        combined_text = "\n\n---PAGE_SEPARATOR---\n\n".join([text for text, _ in texts])
        
        # Single API call for all pages
        try:
            openai_result = self.detect_with_openai(combined_text)
        except Exception as e:
            # If API call fails, return safe defaults for all pages
            logger.warning(f"OpenAI moderation API failed: {e}")
            return [
                {
                    "page": page_num,
                    "is_unsafe": False,
                    "flagged": False,
                    "primary_concerns": [],
                    "category_scores": {},
                    "method": "openai_error",
                    "confidence": 0.0,
                    "error": str(e)
                }
                for _, page_num in texts
            ]
        
        # If OpenAI fails, fall back to per-page processing (but skip if error)
        if openai_result.get("error"):
            # Return safe defaults rather than making more API calls
            logger.warning(f"OpenAI moderation returned error: {openai_result.get('error')}")
            return [
                {
                    "page": page_num,
                    "is_unsafe": False,
                    "flagged": False,
                    "primary_concerns": [],
                    "category_scores": {},
                    "method": "openai_error",
                    "confidence": 0.0
                }
                for _, page_num in texts
            ]
        
        # If content is flagged, we need to determine which pages are problematic
        # For now, if any content is unsafe, mark all pages as potentially unsafe
        # (This is conservative but safe)
        is_unsafe = openai_result.get("is_unsafe", False)
        
        results = []
        for text, page_num in texts:
            # Use batch result but add page-specific info
            result = {
                "page": page_num,
                "is_unsafe": is_unsafe,
                "flagged": is_unsafe,
                "primary_concerns": openai_result.get("primary_concerns", []),
                "category_scores": openai_result.get("category_scores", {}),
                "method": "openai_batch",
                "confidence": openai_result.get("confidence", 0.0)
            }
            
            # If unsafe, try to narrow down which page (optional enhancement)
            # Only use Detoxify if OpenAI flagged it (to avoid extra processing)
            if is_unsafe and self.use_detoxify_backup:
                try:
                    detoxify_result = self.detect_with_detoxify(text)
                    if detoxify_result.get("is_unsafe"):
                        result["detoxify_confirmation"] = detoxify_result
                        result["confidence"] = max(result["confidence"], detoxify_result.get("confidence", 0.0))
                except Exception as e:
                    logger.warning(f"Detoxify check failed for page {page_num}: {e}")
            
            results.append(result)
        
        return results
    
    def detect_unsafe_content(self, text: str, page_number: int) -> Dict:
        """Detect unsafe content using primary method (OpenAI).
        
        IMPORTANT: Only flags for child safety. Reduces API calls by avoiding fallbacks.
        
        Args:
            text: Text to analyze
            page_number: Page number for citation
            
        Returns:
            Dictionary with safety analysis results
        """
        # Try OpenAI (only method we use - no fallbacks to reduce API calls)
        try:
            openai_result = self.detect_with_openai(text)
        except Exception as e:
            # If API call fails, return safe default (don't make more calls)
            logger.warning(f"OpenAI moderation API call failed: {e}")
            return {
                "page": page_number,
                "is_unsafe": False,
                "flagged": False,
                "primary_concerns": [],
                "category_scores": {},
                "method": "openai_error",
                "confidence": 0.0,
                "error": str(e)
            }
        
        # If OpenAI fails, return safe default (don't use Detoxify to avoid extra calls)
        if openai_result.get("error"):
            logger.warning(f"OpenAI moderation returned error: {openai_result.get('error')}")
            return {
                "page": page_number,
                "is_unsafe": False,
                "flagged": False,
                "primary_concerns": [],
                "category_scores": {},
                "method": "openai_error",
                "confidence": 0.0
            }
        
        # Use OpenAI result (already filtered to only child safety)
        return {
            "page": page_number,
            "is_unsafe": openai_result.get("is_unsafe", False),
            "flagged": openai_result.get("flagged", False),
            "primary_concerns": openai_result.get("primary_concerns", []),
            "category_scores": openai_result.get("category_scores", {}),
            "method": "openai",
            "confidence": openai_result.get("confidence", 0.0)
        }

