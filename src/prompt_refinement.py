"""Automated prompt refinement system using LLM to analyze feedback and suggest improvements."""
import json
import re
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
from google import genai
from google.genai import types
import os
from config import Settings

settings = Settings()


class PromptRefinementSystem:
    """Automatically analyzes feedback and suggests prompt improvements using LLM."""
    
    def __init__(self, hitl_system, prompt_library):
        """Initialize prompt refinement system.
        
        Args:
            hitl_system: HITLFeedbackSystem instance
            prompt_library: PromptLibrary instance
        """
        self.hitl_system = hitl_system
        self.prompt_library = prompt_library
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.refinement_history_file = "prompt_refinement_history.json"
        self.refinement_history = self._load_history()
    
    def _load_history(self) -> List[Dict]:
        """Load refinement history from file."""
        if Path(self.refinement_history_file).exists():
            try:
                with open(self.refinement_history_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_history(self):
        """Save refinement history to file."""
        with open(self.refinement_history_file, 'w') as f:
            json.dump(self.refinement_history, f, indent=2)
    
    def analyze_feedback_and_suggest_improvements(
        self,
        prompt_name: Optional[str] = None,
        min_feedback_count: int = 3
    ) -> Dict:
        """Analyze feedback patterns and use LLM to suggest prompt improvements.
        
        Args:
            prompt_name: Specific prompt to analyze (None for all prompts)
            min_feedback_count: Minimum feedback count to analyze
            
        Returns:
            Dictionary with analysis results and suggestions
        """
        # Get feedback data
        if prompt_name:
            # Get feedback for specific prompt
            feedback_records = self._get_feedback_for_prompt(prompt_name)
        else:
            # Get all feedback
            feedback_records = self._get_all_feedback()
        
        if len(feedback_records) < min_feedback_count:
            return {
                "status": "insufficient_feedback",
                "message": f"Need at least {min_feedback_count} feedback records to analyze",
                "current_count": len(feedback_records)
            }
        
        # Analyze patterns
        patterns = self._analyze_patterns(feedback_records)
        
        # Get current prompt
        if prompt_name:
            current_prompt = self.prompt_library.prompts.get(prompt_name, "")
        else:
            # Analyze most problematic prompt
            prompt_performance = self.hitl_system.get_prompt_performance()
            if not prompt_performance:
                return {"status": "error", "message": "No prompt performance data available"}
            
            # Find prompt with lowest accuracy
            worst_prompt = min(prompt_performance.items(), key=lambda x: x[1].get("accuracy", 100))
            prompt_name = worst_prompt[0]
            current_prompt = self.prompt_library.prompts.get(prompt_name, "")
        
        if not current_prompt:
            return {"status": "error", "message": f"Prompt '{prompt_name}' not found"}
        
        # Use LLM to suggest improvements
        suggestions = self._get_llm_suggestions(
            prompt_name=prompt_name,
            current_prompt=current_prompt,
            patterns=patterns,
            feedback_records=feedback_records
        )
        
        # If LLM failed and we got fallback, merge fallback into main suggestions
        if "error" in suggestions and "fallback_suggestions" in suggestions:
            fallback = suggestions.pop("fallback_suggestions")
            # Merge fallback into main suggestions, prioritizing fallback's improved_prompt
            if fallback.get("improved_prompt"):
                suggestions["improved_prompt"] = fallback["improved_prompt"]
            if fallback.get("issues"):
                suggestions.setdefault("issues", []).extend(fallback["issues"])
            if fallback.get("suggestions"):
                suggestions.setdefault("suggestions", []).extend(fallback["suggestions"])
            if fallback.get("reasoning"):
                suggestions["reasoning"] = fallback["reasoning"]
        
        return {
            "status": "success",
            "prompt_name": prompt_name,
            "current_prompt": current_prompt,
            "patterns": patterns,
            "suggestions": suggestions,
            "feedback_count": len(feedback_records)
        }
    
    def _get_feedback_for_prompt(self, prompt_name: str) -> List[Dict]:
        """Get feedback records for a specific prompt."""
        db = self.hitl_system.SessionLocal()
        try:
            from src.hitl_feedback import FeedbackRecord
            records = db.query(FeedbackRecord).filter(
                FeedbackRecord.prompt_used == prompt_name
            ).all()
            return [self.hitl_system._record_to_dict(r) for r in records]
        finally:
            db.close()
    
    def _get_all_feedback(self) -> List[Dict]:
        """Get all feedback records."""
        db = self.hitl_system.SessionLocal()
        try:
            from src.hitl_feedback import FeedbackRecord
            records = db.query(FeedbackRecord).all()
            return [self.hitl_system._record_to_dict(r) for r in records]
        finally:
            db.close()
    
    def _analyze_patterns(self, feedback_records: List[Dict]) -> Dict:
        """Analyze feedback to identify patterns."""
        patterns = {
            "common_misclassifications": {},
            "low_confidence_errors": [],
            "frequent_corrections": {},
            "feedback_themes": []
        }
        
        corrections = [f for f in feedback_records if f.get("feedback_type") == "correction"]
        
        # Common misclassifications
        for feedback in corrections:
            original = feedback.get("original_classification")
            corrected = feedback.get("corrected_classification")
            if original and corrected:
                key = f"{original} -> {corrected}"
                patterns["common_misclassifications"][key] = \
                    patterns["common_misclassifications"].get(key, 0) + 1
        
        # Low confidence errors
        for feedback in corrections:
            confidence = feedback.get("confidence")
            if confidence is not None and confidence < 0.7:
                patterns["low_confidence_errors"].append({
                    "document_id": feedback.get("document_id"),
                    "original": feedback.get("original_classification"),
                    "corrected": feedback.get("corrected_classification"),
                    "confidence": confidence
                })
        
        # Frequent corrections
        for feedback in corrections:
            original = feedback.get("original_classification")
            if original:
                patterns["frequent_corrections"][original] = \
                    patterns["frequent_corrections"].get(original, 0) + 1
        
        # Extract themes from feedback text
        feedback_texts = [f.get("feedback_text", "") for f in feedback_records if f.get("feedback_text")]
        if feedback_texts:
            # Simple keyword extraction (can be enhanced)
            all_text = " ".join(feedback_texts).lower()
            themes = []
            if "pii" in all_text or "personal" in all_text:
                themes.append("PII detection issues")
            if "keyword" in all_text or "sensitive" in all_text:
                themes.append("Keyword detection issues")
            if "safety" in all_text or "unsafe" in all_text:
                themes.append("Safety detection issues")
            if "ambiguous" in all_text or "unclear" in all_text:
                themes.append("Ambiguity in classification")
            patterns["feedback_themes"] = themes
        
        return patterns
    
    def _get_llm_suggestions(
        self,
        prompt_name: str,
        current_prompt: str,
        patterns: Dict,
        feedback_records: List[Dict]
    ) -> Dict:
        """Use LLM to generate prompt improvement suggestions."""
        
        # Prepare feedback summary
        corrections = [f for f in feedback_records if f.get("feedback_type") == "correction"]
        feedback_summary = f"""
Common Misclassifications:
{json.dumps(patterns.get("common_misclassifications", {}), indent=2)}

Frequent Corrections:
{json.dumps(patterns.get("frequent_corrections", {}), indent=2)}

Feedback Themes:
{', '.join(patterns.get("feedback_themes", []))}

Sample Feedback (last 5 corrections):
{json.dumps(corrections[:5], indent=2, default=str)}
"""
        
        analysis_prompt = f"""You are an expert in prompt engineering for document classification systems.

Current Prompt Template ("{prompt_name}"):
{current_prompt}

Feedback Analysis:
{feedback_summary}

Based on this feedback, analyze the prompt and provide:
1. **Issues Identified**: What problems does the feedback reveal about the current prompt?
2. **Suggested Improvements**: Specific, actionable improvements to the prompt
3. **Improved Prompt**: A complete revised version of the prompt that addresses the issues

Return your response as JSON:
{{
    "issues": ["issue1", "issue2"],
    "suggestions": ["suggestion1", "suggestion2"],
    "improved_prompt": "the complete improved prompt text here",
    "reasoning": "explanation of why these changes will help"
}}"""
        
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=8000  # Increased for longer prompts (prompts can be 2000+ chars)
                ),
                contents=analysis_prompt
            )
            
            # Check if response is valid
            if not response:
                raise ValueError("LLM returned None response")
            
            # Extract text from response - handle different response formats
            if hasattr(response, 'text') and response.text:
                response_text = response.text.strip()
            elif hasattr(response, 'candidates') and response.candidates:
                # Try to get text from candidates
                if response.candidates[0].content and response.candidates[0].content.parts:
                    response_text = response.candidates[0].content.parts[0].text.strip()
                else:
                    raise ValueError("No text found in response candidates")
            else:
                raise ValueError(f"Unexpected response format: {type(response)}")
            
            if not response_text:
                raise ValueError("Response text is empty")
            
            # Try to extract JSON if wrapped in markdown
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # Try to find JSON in the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group()
            
            # Try to parse JSON - handle partial/incomplete JSON
            try:
                suggestions = json.loads(response_text)
            except json.JSONDecodeError as json_err:
                # Try to extract what we can from partial JSON
                # Look for improved_prompt field even if JSON is incomplete
                improved_prompt_match = re.search(
                    r'"improved_prompt"\s*:\s*"([^"]*(?:\\.[^"]*)*)"',
                    response_text,
                    re.DOTALL
                )
                if improved_prompt_match:
                    # We found improved_prompt, try to construct minimal valid JSON
                    improved_prompt = improved_prompt_match.group(1).replace('\\"', '"')
                    # Extract other fields if possible
                    issues_match = re.search(r'"issues"\s*:\s*\[(.*?)\]', response_text, re.DOTALL)
                    suggestions_match = re.search(r'"suggestions"\s*:\s*\[(.*?)\]', response_text, re.DOTALL)
                    
                    suggestions = {
                        "improved_prompt": improved_prompt,
                        "issues": [],
                        "suggestions": [],
                        "reasoning": "LLM response was partially parsed due to JSON truncation"
                    }
                    
                    if issues_match:
                        # Try to extract issues (simplified)
                        issues_text = issues_match.group(1)
                        # Extract quoted strings
                        issues = re.findall(r'"([^"]+)"', issues_text)
                        suggestions["issues"] = issues
                    
                    if suggestions_match:
                        suggestions_text = suggestions_match.group(1)
                        suggestions_list = re.findall(r'"([^"]+)"', suggestions_text)
                        suggestions["suggestions"] = suggestions_list
                else:
                    # Can't extract improved_prompt, raise error to trigger fallback
                    raise json_err
            
            # Validate that improved_prompt exists
            if not suggestions.get("improved_prompt"):
                raise ValueError("LLM response missing 'improved_prompt' field")
            
            return suggestions
            
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Response text (first 500 chars): {response_text[:500] if 'response_text' in locals() else 'N/A'}")
            # Try fallback
            return self._get_fallback_suggestions(patterns, current_prompt, prompt_name)
        except Exception as e:
            print(f"LLM suggestion error: {e}")
            import traceback
            traceback.print_exc()
            # Try fallback
            return self._get_fallback_suggestions(patterns, current_prompt, prompt_name)
    
    def _get_fallback_suggestions(self, patterns: Dict, current_prompt: str = "", prompt_name: str = "") -> Dict:
        """Generate fallback suggestions if LLM fails - actually generates improved prompt."""
        suggestions = {
            "issues": [],
            "suggestions": [],
            "improved_prompt": current_prompt,  # Start with current prompt
            "reasoning": "LLM analysis failed, using rule-based improvements"
        }
        
        # Get current prompt if not provided
        if not current_prompt and prompt_name:
            current_prompt = self.prompt_library.prompts.get(prompt_name, "")
            suggestions["improved_prompt"] = current_prompt
        
        improved_prompt = current_prompt
        
        # Rule-based improvements based on patterns
        common_misclassifications = patterns.get("common_misclassifications", {})
        frequent_corrections = patterns.get("frequent_corrections", {})
        
        if common_misclassifications:
            suggestions["issues"].append("Frequent misclassifications detected")
            suggestions["suggestions"].append(
                "Add more explicit examples for common misclassification cases"
            )
            
            # Generate improvement based on most common misclassification
            most_common = max(common_misclassifications.items(), key=lambda x: x[1], default=(None, 0))
            if most_common[0]:
                misclass_pattern = most_common[0]  # e.g., "Confidential -> Public"
                parts = misclass_pattern.split(" -> ")
                if len(parts) == 2:
                    wrong_class, correct_class = parts
                    # Add a note to the prompt about this specific misclassification
                    improvement_note = f"\n\n**IMPORTANT: Common Error to Avoid**\n"
                    improvement_note += f"Documents are frequently incorrectly classified as '{wrong_class}' when they should be '{correct_class}'. "
                    improvement_note += f"Pay special attention to distinguishing between these categories.\n"
                    
                    # Insert before the document information section
                    if "Document Information:" in improved_prompt:
                        improved_prompt = improved_prompt.replace(
                            "Document Information:",
                            improvement_note + "\nDocument Information:"
                        )
                    else:
                        improved_prompt += improvement_note
        
        if patterns.get("low_confidence_errors"):
            suggestions["issues"].append("High error rate with low confidence scores")
            suggestions["suggestions"].append(
                "Strengthen instructions for handling ambiguous cases"
            )
            
            # Add instruction about confidence
            if "confidence" not in improved_prompt.lower():
                confidence_note = "\n\n**Confidence Guidelines:**\n"
                confidence_note += "If you are uncertain about the classification, use a lower confidence score (< 0.7). "
                confidence_note += "Only use high confidence (>= 0.8) when you are very certain based on clear evidence.\n"
                
                if "Document Information:" in improved_prompt:
                    improved_prompt = improved_prompt.replace(
                        "Document Information:",
                        confidence_note + "\nDocument Information:"
                    )
                else:
                    improved_prompt += confidence_note
        
        # If we have frequent corrections, add emphasis
        if frequent_corrections:
            most_frequent = max(frequent_corrections.items(), key=lambda x: x[1], default=(None, 0))
            if most_frequent[0] and most_frequent[1] >= 3:
                wrong_class = most_frequent[0]
                suggestions["issues"].append(f"Frequent over-classification as '{wrong_class}'")
                suggestions["suggestions"].append(
                    f"Add explicit guidance to avoid over-classifying as '{wrong_class}'"
                )
                
                # Add warning about over-classification
                warning = f"\n\n**Warning: Avoid Over-Classification**\n"
                warning += f"Documents are frequently over-classified as '{wrong_class}'. "
                warning += f"Only classify as '{wrong_class}' when there is clear, unambiguous evidence. "
                warning += f"When in doubt, consider other classification options first.\n"
                
                if "Document Information:" in improved_prompt:
                    improved_prompt = improved_prompt.replace(
                        "Document Information:",
                        warning + "\nDocument Information:"
                    )
                else:
                    improved_prompt += warning
        
        suggestions["improved_prompt"] = improved_prompt
        
        return suggestions
    
    def apply_prompt_improvement(
        self,
        prompt_name: str,
        improved_prompt: str,
        reason: str,
        auto_apply: bool = False
    ) -> Dict:
        """Apply an improved prompt (with or without approval).
        
        Args:
            prompt_name: Name of prompt to update
            improved_prompt: The improved prompt text
            reason: Reason for the change
            auto_apply: If True, apply immediately. If False, save as suggestion.
            
        Returns:
            Dictionary with status
        """
        if prompt_name not in self.prompt_library.prompts:
            return {"status": "error", "message": f"Prompt '{prompt_name}' not found"}
        
        # Save old prompt
        old_prompt = self.prompt_library.prompts[prompt_name]
        
        # Record in history
        refinement_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "prompt_name": prompt_name,
            "old_prompt": old_prompt,
            "new_prompt": improved_prompt,
            "reason": reason,
            "auto_applied": auto_apply
        }
        self.refinement_history.append(refinement_record)
        self._save_history()
        
        if auto_apply:
            # Apply immediately
            self.prompt_library.prompts[prompt_name] = improved_prompt
            
            # Save to file if prompts_file is set
            if self.prompt_library.prompts_file:
                self.prompt_library.save_prompts(self.prompt_library.prompts_file)
            
            return {
                "status": "applied",
                "message": f"Prompt '{prompt_name}' has been updated",
                "refinement_id": len(self.refinement_history) - 1
            }
        else:
            # Save as suggestion
            return {
                "status": "suggested",
                "message": f"Improvement suggestion saved for '{prompt_name}'",
                "refinement_id": len(self.refinement_history) - 1,
                "suggestion": {
                    "prompt_name": prompt_name,
                    "improved_prompt": improved_prompt,
                    "reason": reason
                }
            }
    
    def get_refinement_history(self, prompt_name: Optional[str] = None) -> List[Dict]:
        """Get refinement history.
        
        Args:
            prompt_name: Filter by prompt name (optional)
            
        Returns:
            List of refinement records
        """
        if prompt_name:
            return [r for r in self.refinement_history if r.get("prompt_name") == prompt_name]
        return self.refinement_history
    
    def get_pending_suggestions(self) -> List[Dict]:
        """Get pending (not yet applied) suggestions."""
        return [
            r for r in self.refinement_history
            if not r.get("auto_applied", False) and "new_prompt" in r
        ]

