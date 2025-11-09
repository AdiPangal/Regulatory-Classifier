"""Automatic continuous improvement system for prompts."""
import asyncio
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
import logging

logger = logging.getLogger(__name__)


class AutoImprovementConfig:
    """Configuration for automatic improvement."""
    
    def __init__(
        self,
        feedback_threshold: int = 10,  # Analyze after N feedback submissions
        min_improvement_confidence: float = 0.8,  # Auto-apply if confidence > this
        auto_apply_enabled: bool = True,  # Enable automatic application
        min_feedback_for_analysis: int = 5,  # Minimum feedback needed for analysis
        check_interval_seconds: int = 300  # Check every 5 minutes
    ):
        self.feedback_threshold = feedback_threshold
        self.min_improvement_confidence = min_improvement_confidence
        self.auto_apply_enabled = auto_apply_enabled
        self.min_feedback_for_analysis = min_feedback_for_analysis
        self.check_interval_seconds = check_interval_seconds


class AccuracyTracker:
    """Tracks accuracy improvements over time."""
    
    def __init__(self, db_path: str = "accuracy_tracking.json"):
        self.db_path = db_path
        self.lock = Lock()
        self._load_data()
    
    def _load_data(self):
        """Load tracking data from file."""
        if Path(self.db_path).exists():
            try:
                with open(self.db_path, 'r') as f:
                    self.data = json.load(f)
            except:
                self.data = {
                    "prompt_versions": {},  # prompt_name -> list of versions
                    "accuracy_history": [],  # List of accuracy snapshots
                    "improvements": []  # List of applied improvements
                }
        else:
            self.data = {
                "prompt_versions": {},
                "accuracy_history": [],
                "improvements": []
            }
    
    def _save_data(self):
        """Save tracking data to file."""
        with self.lock:
            with open(self.db_path, 'w') as f:
                json.dump(self.data, f, indent=2)
    
    def record_prompt_version(
        self,
        prompt_name: str,
        prompt_text: str,
        version_number: int,
        reason: str
    ):
        """Record a new prompt version."""
        if prompt_name not in self.data["prompt_versions"]:
            self.data["prompt_versions"][prompt_name] = []
        
        self.data["prompt_versions"][prompt_name].append({
            "version": version_number,
            "prompt_text": prompt_text,
            "timestamp": datetime.utcnow().isoformat(),
            "reason": reason
        })
        self._save_data()
    
    def record_accuracy_snapshot(
        self,
        prompt_name: str,
        accuracy: float,
        total_feedback: int,
        corrections: int,
        confirmations: int
    ):
        """Record an accuracy snapshot."""
        snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "prompt_name": prompt_name,
            "accuracy": accuracy,
            "total_feedback": total_feedback,
            "corrections": corrections,
            "confirmations": confirmations
        }
        self.data["accuracy_history"].append(snapshot)
        self._save_data()
        return snapshot
    
    def record_improvement(
        self,
        prompt_name: str,
        old_accuracy: float,
        new_accuracy: float,
        improvement_id: str
    ):
        """Record an improvement application."""
        improvement = {
            "timestamp": datetime.utcnow().isoformat(),
            "prompt_name": prompt_name,
            "old_accuracy": old_accuracy,
            "new_accuracy": new_accuracy,
            "improvement": new_accuracy - old_accuracy,
            "improvement_id": improvement_id
        }
        self.data["improvements"].append(improvement)
        self._save_data()
        return improvement
    
    def get_accuracy_trend(self, prompt_name: Optional[str] = None, days: int = 30) -> List[Dict]:
        """Get accuracy trend over time."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        cutoff_str = cutoff_date.isoformat()
        
        history = self.data["accuracy_history"]
        if prompt_name:
            history = [h for h in history if h.get("prompt_name") == prompt_name]
        
        return [h for h in history if h.get("timestamp", "") >= cutoff_str]
    
    def get_latest_accuracy(self, prompt_name: Optional[str] = None) -> Optional[Dict]:
        """Get the latest accuracy snapshot."""
        history = self.data["accuracy_history"]
        if prompt_name:
            history = [h for h in history if h.get("prompt_name") == prompt_name]
        
        if not history:
            return None
        
        return max(history, key=lambda x: x.get("timestamp", ""))


class AutoImprovementSystem:
    """Manages automatic continuous improvement of prompts."""
    
    def __init__(
        self,
        hitl_system,
        refinement_system,
        config: Optional[AutoImprovementConfig] = None
    ):
        """Initialize automatic improvement system.
        
        Args:
            hitl_system: HITLFeedbackSystem instance
            refinement_system: PromptRefinementSystem instance
            config: AutoImprovementConfig instance
        """
        self.hitl_system = hitl_system
        self.refinement_system = refinement_system
        self.config = config or AutoImprovementConfig()
        self.accuracy_tracker = AccuracyTracker()
        self.last_feedback_count = 0
        self.last_analysis_time = None
        self.is_running = False
        self.lock = Lock()
    
    def get_feedback_count_since_last_analysis(self) -> int:
        """Get number of feedback submissions since last analysis."""
        db = self.hitl_system.SessionLocal()
        try:
            from src.hitl_feedback import FeedbackRecord
            if self.last_analysis_time:
                count = db.query(FeedbackRecord).filter(
                    FeedbackRecord.timestamp >= self.last_analysis_time
                ).count()
            else:
                count = db.query(FeedbackRecord).count()
            return count
        finally:
            db.close()
    
    def should_analyze(self) -> bool:
        """Check if it's time to analyze feedback."""
        feedback_count = self.get_feedback_count_since_last_analysis()
        return feedback_count >= self.config.feedback_threshold
    
    async def analyze_and_improve_automatically(self) -> Dict:
        """Automatically analyze feedback and apply improvements if confident.
        
        Returns:
            Dictionary with analysis and application results
        """
        if not self.should_analyze():
            return {
                "status": "skipped",
                "reason": "Feedback threshold not reached",
                "current_feedback_count": self.get_feedback_count_since_last_analysis()
            }
        
        try:
            # Get current accuracy baseline
            stats = self.hitl_system.get_classification_accuracy_stats()
            current_accuracy = stats.get("overall_accuracy", 0.0)
            
            # Analyze feedback (find worst-performing prompt)
            analysis_result = self.refinement_system.analyze_feedback_and_suggest_improvements(
                prompt_name=None,  # Auto-select worst prompt
                min_feedback_count=self.config.min_feedback_for_analysis
            )
            
            if analysis_result.get("status") != "success":
                return {
                    "status": "analysis_failed",
                    "reason": analysis_result.get("message", "Unknown error"),
                    "analysis_result": analysis_result
                }
            
            prompt_name = analysis_result.get("prompt_name")
            suggestions = analysis_result.get("suggestions", {})
            
            # Check for improved_prompt in suggestions or fallback_suggestions
            improved_prompt = suggestions.get("improved_prompt")
            if not improved_prompt and "fallback_suggestions" in suggestions:
                improved_prompt = suggestions["fallback_suggestions"].get("improved_prompt")
            
            if not improved_prompt:
                logger.warning(f"No improved_prompt found in suggestions. Keys: {list(suggestions.keys())}")
                if "error" in suggestions:
                    logger.warning(f"LLM error: {suggestions.get('error')}")
                return {
                    "status": "no_suggestion",
                    "reason": "LLM did not generate improved prompt and fallback also failed",
                    "analysis_result": analysis_result,
                    "suggestions_keys": list(suggestions.keys())
                }
            
            # Evaluate confidence in improvement
            # For now, we'll use a simple heuristic:
            # - High confidence if feedback count is high and patterns are clear
            feedback_count = analysis_result.get("feedback_count", 0)
            patterns = analysis_result.get("patterns", {})
            
            # Calculate confidence score
            confidence = self._calculate_improvement_confidence(
                feedback_count=feedback_count,
                patterns=patterns,
                suggestions=suggestions
            )
            
            result = {
                "status": "analyzed",
                "prompt_name": prompt_name,
                "current_accuracy": current_accuracy,
                "improvement_confidence": confidence,
                "feedback_count": feedback_count,
                "auto_applied": False
            }
            
            # Auto-apply if confidence is high enough
            if (self.config.auto_apply_enabled and 
                confidence >= self.config.min_improvement_confidence and
                improved_prompt):
                
                # Record accuracy before improvement
                prompt_stats = self.hitl_system.get_prompt_performance()
                prompt_accuracy = prompt_stats.get(prompt_name, {}).get("accuracy", current_accuracy)
                
                # Apply improvement
                apply_result = self.refinement_system.apply_prompt_improvement(
                    prompt_name=prompt_name,
                    improved_prompt=improved_prompt,
                    reason=f"Auto-applied: {suggestions.get('reasoning', 'High confidence improvement')}",
                    auto_apply=True
                )
                
                if apply_result.get("status") == "applied":
                    result["auto_applied"] = True
                    result["apply_result"] = apply_result
                    
                    # Record improvement
                    self.accuracy_tracker.record_improvement(
                        prompt_name=prompt_name,
                        old_accuracy=prompt_accuracy,
                        new_accuracy=prompt_accuracy,  # Will be updated after more feedback
                        improvement_id=str(apply_result.get("refinement_id", ""))
                    )
                    
                    logger.info(f"Auto-applied improvement to prompt '{prompt_name}' with confidence {confidence:.2f}")
                else:
                    result["apply_error"] = apply_result.get("message", "Unknown error")
            else:
                # Save as suggestion for manual review
                self.refinement_system.apply_prompt_improvement(
                    prompt_name=prompt_name,
                    improved_prompt=improved_prompt,
                    reason=f"Auto-suggested: Confidence {confidence:.2f} (threshold: {self.config.min_improvement_confidence})",
                    auto_apply=False
                )
                result["saved_as_suggestion"] = True
            
            # Update last analysis time
            self.last_analysis_time = datetime.utcnow()
            
            # Record accuracy snapshot
            self.accuracy_tracker.record_accuracy_snapshot(
                prompt_name=prompt_name,
                accuracy=current_accuracy,
                total_feedback=stats.get("total_feedback", 0),
                corrections=stats.get("corrections", 0),
                confirmations=stats.get("confirmations", 0)
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Automatic improvement failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _calculate_improvement_confidence(
        self,
        feedback_count: int,
        patterns: Dict,
        suggestions: Dict
    ) -> float:
        """Calculate confidence score for an improvement.
        
        Args:
            feedback_count: Number of feedback records analyzed
            patterns: Analysis patterns
            suggestions: LLM suggestions
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        confidence = 0.5  # Base confidence
        
        # More feedback = higher confidence
        if feedback_count >= 20:
            confidence += 0.2
        elif feedback_count >= 10:
            confidence += 0.1
        
        # Clear patterns = higher confidence
        if patterns.get("common_misclassifications"):
            misclass_count = sum(patterns["common_misclassifications"].values())
            if misclass_count >= 5:
                confidence += 0.15
        
        # Detailed suggestions = higher confidence
        if suggestions.get("issues") and len(suggestions["issues"]) >= 2:
            confidence += 0.1
        
        if suggestions.get("suggestions") and len(suggestions["suggestions"]) >= 2:
            confidence += 0.05
        
        # Cap at 1.0
        return min(confidence, 1.0)
    
    async def run_continuous_improvement_loop(self):
        """Run continuous improvement in background."""
        self.is_running = True
        logger.info("Starting continuous improvement loop")
        
        while self.is_running:
            try:
                if self.should_analyze():
                    logger.info("Triggering automatic analysis and improvement")
                    result = await self.analyze_and_improve_automatically()
                    logger.info(f"Auto-improvement result: {result.get('status')}")
                
                await asyncio.sleep(self.config.check_interval_seconds)
            except Exception as e:
                logger.error(f"Error in improvement loop: {e}", exc_info=True)
                await asyncio.sleep(self.config.check_interval_seconds)
    
    def stop(self):
        """Stop the continuous improvement loop."""
        self.is_running = False
        logger.info("Stopped continuous improvement loop")
    
    def get_status(self) -> Dict:
        """Get current status of auto-improvement system."""
        feedback_count = self.get_feedback_count_since_last_analysis()
        return {
            "is_running": self.is_running,
            "feedback_count_since_last_analysis": feedback_count,
            "feedback_threshold": self.config.feedback_threshold,
            "should_analyze": self.should_analyze(),
            "last_analysis_time": self.last_analysis_time.isoformat() if self.last_analysis_time else None,
            "auto_apply_enabled": self.config.auto_apply_enabled,
            "min_improvement_confidence": self.config.min_improvement_confidence
        }

