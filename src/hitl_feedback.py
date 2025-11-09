"""Human-in-the-Loop (HITL) feedback system for prompt refinement."""
import json
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, Column, String, Integer, Float, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func

Base = declarative_base()


class FeedbackRecord(Base):
    """Database model for HITL feedback."""
    __tablename__ = "feedback_records"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String, index=True)
    original_classification = Column(String)
    corrected_classification = Column(String)
    confidence = Column(Float)
    feedback_type = Column(String)  # "correction", "confirmation", "prompt_suggestion"
    feedback_text = Column(Text)
    reviewer_id = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    is_resolved = Column(Boolean, default=False)
    prompt_used = Column(String)
    detection_summary = Column(Text)  # JSON string


class HITLFeedbackSystem:
    """Manages HITL feedback for improving classification accuracy."""
    
    def __init__(self, db_path: str = "hitl_feedback.db"):
        """Initialize HITL feedback system.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def add_feedback(
        self,
        document_id: str,
        original_classification: str,
        corrected_classification: Optional[str] = None,
        feedback_type: str = "correction",
        feedback_text: Optional[str] = None,
        reviewer_id: Optional[str] = None,
        confidence: Optional[float] = None,
        prompt_used: Optional[str] = None,
        detection_summary: Optional[Dict] = None
    ) -> int:
        """Add feedback record.
        
        Args:
            document_id: Document ID
            original_classification: Original classification from system
            corrected_classification: Corrected classification (if correction)
            feedback_type: Type of feedback ("correction", "confirmation", "prompt_suggestion")
            feedback_text: Additional feedback text
            reviewer_id: ID of reviewer
            confidence: Confidence score
            prompt_used: Prompt template used
            detection_summary: Summary of detections
            
        Returns:
            Feedback record ID
        """
        db: Session = self.SessionLocal()
        try:
            record = FeedbackRecord(
                document_id=document_id,
                original_classification=original_classification,
                corrected_classification=corrected_classification,
                feedback_type=feedback_type,
                feedback_text=feedback_text,
                reviewer_id=reviewer_id,
                confidence=confidence,
                prompt_used=prompt_used,
                detection_summary=json.dumps(detection_summary) if detection_summary else None
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return record.id
        finally:
            db.close()
    
    def get_feedback(self, document_id: str) -> List[Dict]:
        """Get feedback for a document.
        
        Args:
            document_id: Document ID
            
        Returns:
            List of feedback records
        """
        db: Session = self.SessionLocal()
        try:
            records = db.query(FeedbackRecord).filter(
                FeedbackRecord.document_id == document_id
            ).order_by(FeedbackRecord.timestamp.desc()).all()
            
            return [self._record_to_dict(record) for record in records]
        finally:
            db.close()
    
    def get_pending_reviews(self, limit: int = 100) -> List[Dict]:
        """Get documents pending review.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of pending review records
        """
        db: Session = self.SessionLocal()
        try:
            records = db.query(FeedbackRecord).filter(
                FeedbackRecord.is_resolved == False
            ).order_by(FeedbackRecord.timestamp.desc()).limit(limit).all()
            
            return [self._record_to_dict(record) for record in records]
        finally:
            db.close()
    
    def get_classification_accuracy_stats(self) -> Dict:
        """Get statistics on classification accuracy from feedback.
        
        Returns:
            Dictionary with accuracy statistics
        """
        db: Session = self.SessionLocal()
        try:
            total_feedback = db.query(FeedbackRecord).count()
            corrections = db.query(FeedbackRecord).filter(
                FeedbackRecord.feedback_type == "correction"
            ).count()
            confirmations = db.query(FeedbackRecord).filter(
                FeedbackRecord.feedback_type == "confirmation"
            ).count()
            
            accuracy = (confirmations / total_feedback * 100) if total_feedback > 0 else 0.0
            
            # Get accuracy by classification type
            by_classification = {}
            for classification in ["Public", "Confidential", "Highly Sensitive"]:  # Note: "Unsafe" is a safety flag, not a classification
                total = db.query(FeedbackRecord).filter(
                    FeedbackRecord.original_classification == classification
                ).count()
                correct = db.query(FeedbackRecord).filter(
                    FeedbackRecord.original_classification == classification,
                    FeedbackRecord.feedback_type == "confirmation"
                ).count()
                
                if total > 0:
                    by_classification[classification] = {
                        "total": total,
                        "correct": correct,
                        "accuracy": (correct / total * 100)
                    }
            
            return {
                "total_feedback": total_feedback,
                "corrections": corrections,
                "confirmations": confirmations,
                "overall_accuracy": accuracy,
                "by_classification": by_classification
            }
        finally:
            db.close()
    
    def mark_resolved(self, feedback_id: int):
        """Mark feedback record as resolved.
        
        Args:
            feedback_id: Feedback record ID
        """
        db: Session = self.SessionLocal()
        try:
            record = db.query(FeedbackRecord).filter(FeedbackRecord.id == feedback_id).first()
            if record:
                record.is_resolved = True
                db.commit()
        finally:
            db.close()
    
    def get_prompt_performance(self) -> Dict:
        """Get performance statistics by prompt template.
        
        Returns:
            Dictionary with prompt performance metrics
        """
        db: Session = self.SessionLocal()
        try:
            prompts = db.query(FeedbackRecord.prompt_used).distinct().all()
            prompt_stats = {}
            
            for (prompt_name,) in prompts:
                if not prompt_name:
                    continue
                
                total = db.query(FeedbackRecord).filter(
                    FeedbackRecord.prompt_used == prompt_name
                ).count()
                
                correct = db.query(FeedbackRecord).filter(
                    FeedbackRecord.prompt_used == prompt_name,
                    FeedbackRecord.feedback_type == "confirmation"
                ).count()
                
                accuracy = (correct / total * 100) if total > 0 else 0.0
                
                prompt_stats[prompt_name] = {
                    "total": total,
                    "correct": correct,
                    "accuracy": accuracy
                }
            
            return prompt_stats
        finally:
            db.close()
    
    def _record_to_dict(self, record: FeedbackRecord) -> Dict:
        """Convert database record to dictionary.
        
        Args:
            record: Database record
            
        Returns:
            Dictionary representation
        """
        return {
            "id": record.id,
            "document_id": record.document_id,
            "original_classification": record.original_classification,
            "corrected_classification": record.corrected_classification,
            "feedback_type": record.feedback_type,
            "feedback_text": record.feedback_text,
            "reviewer_id": record.reviewer_id,
            "timestamp": record.timestamp.isoformat() if record.timestamp else None,
            "is_resolved": record.is_resolved,
            "prompt_used": record.prompt_used,
            "detection_summary": json.loads(record.detection_summary) if record.detection_summary else None,
            "confidence": record.confidence
        }

