"""Audit trail system for tracking all system events and user actions."""
import json
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func

Base = declarative_base()


class AuditRecord(Base):
    """Database model for audit trail."""
    __tablename__ = "audit_records"
    
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, index=True)  # "classification", "feedback", "user_action", "system_event"
    action = Column(String, index=True)  # "upload", "classify", "submit_feedback", "model_change", etc.
    user_id = Column(String, index=True, nullable=True)
    document_id = Column(String, index=True, nullable=True)
    details = Column(JSON)  # Flexible JSON field for event-specific data
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)


class AuditTrailSystem:
    """Manages audit trail for compliance and tracking."""
    
    def __init__(self, db_path: str = "audit_trail.db"):
        """Initialize audit trail system.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def log_event(
        self,
        event_type: str,
        action: str,
        user_id: Optional[str] = None,
        document_id: Optional[str] = None,
        details: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> int:
        """Log an audit event.
        
        Args:
            event_type: Type of event (classification, feedback, user_action, system_event)
            action: Specific action taken
            user_id: User identifier (if available)
            document_id: Document identifier (if applicable)
            details: Additional event details as dictionary
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            Audit record ID
        """
        db: Session = self.SessionLocal()
        try:
            record = AuditRecord(
                event_type=event_type,
                action=action,
                user_id=user_id,
                document_id=document_id,
                details=details or {},
                ip_address=ip_address,
                user_agent=user_agent,
                timestamp=datetime.utcnow()
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return record.id
        finally:
            db.close()
    
    def get_audit_history(
        self,
        event_type: Optional[str] = None,
        action: Optional[str] = None,
        user_id: Optional[str] = None,
        document_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """Get audit history with filters.
        
        Args:
            event_type: Filter by event type
            action: Filter by action
            user_id: Filter by user ID
            document_id: Filter by document ID
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum number of records
            offset: Offset for pagination
            
        Returns:
            List of audit records
        """
        db: Session = self.SessionLocal()
        try:
            query = db.query(AuditRecord)
            
            if event_type:
                query = query.filter(AuditRecord.event_type == event_type)
            if action:
                query = query.filter(AuditRecord.action == action)
            if user_id:
                query = query.filter(AuditRecord.user_id == user_id)
            if document_id:
                query = query.filter(AuditRecord.document_id == document_id)
            if start_date:
                query = query.filter(AuditRecord.timestamp >= start_date)
            if end_date:
                query = query.filter(AuditRecord.timestamp <= end_date)
            
            records = query.order_by(AuditRecord.timestamp.desc()).limit(limit).offset(offset).all()
            
            return [
                {
                    "id": record.id,
                    "event_type": record.event_type,
                    "action": record.action,
                    "user_id": record.user_id,
                    "document_id": record.document_id,
                    "details": record.details,
                    "timestamp": record.timestamp.isoformat(),
                    "ip_address": record.ip_address,
                    "user_agent": record.user_agent
                }
                for record in records
            ]
        finally:
            db.close()
    
    def get_audit_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """Get audit statistics.
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Statistics dictionary
        """
        db: Session = self.SessionLocal()
        try:
            query = db.query(AuditRecord)
            
            if start_date:
                query = query.filter(AuditRecord.timestamp >= start_date)
            if end_date:
                query = query.filter(AuditRecord.timestamp <= end_date)
            
            total_events = query.count()
            
            # Count by event type
            event_types = db.query(
                AuditRecord.event_type,
                func.count(AuditRecord.id).label('count')
            )
            if start_date:
                event_types = event_types.filter(AuditRecord.timestamp >= start_date)
            if end_date:
                event_types = event_types.filter(AuditRecord.timestamp <= end_date)
            event_types = event_types.group_by(AuditRecord.event_type).all()
            
            # Count by action
            actions = db.query(
                AuditRecord.action,
                func.count(AuditRecord.id).label('count')
            )
            if start_date:
                actions = actions.filter(AuditRecord.timestamp >= start_date)
            if end_date:
                actions = actions.filter(AuditRecord.timestamp <= end_date)
            actions = actions.group_by(AuditRecord.action).all()
            
            return {
                "total_events": total_events,
                "by_event_type": {et[0]: et[1] for et in event_types},
                "by_action": {act[0]: act[1] for act in actions},
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None
            }
        finally:
            db.close()
    
    def get_document_history(self, document_id: str) -> List[Dict]:
        """Get complete history for a specific document.
        
        Args:
            document_id: Document identifier
            
        Returns:
            List of audit records for the document
        """
        return self.get_audit_history(document_id=document_id, limit=1000)
    
    def get_user_history(self, user_id: str) -> List[Dict]:
        """Get complete history for a specific user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of audit records for the user
        """
        return self.get_audit_history(user_id=user_id, limit=1000)

