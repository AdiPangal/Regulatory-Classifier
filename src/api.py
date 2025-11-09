"""FastAPI endpoints for the Regulatory Classifier."""
import os
import uuid
import logging
from typing import List, Optional, Dict
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form, WebSocket, WebSocketDisconnect, Request, Query, Body
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import asyncio
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from io import BytesIO

from .classification_pipeline import ClassificationPipeline
from .hitl_feedback import HITLFeedbackSystem
from .audit_trail import AuditTrailSystem
from .prompt_refinement import PromptRefinementSystem
from .auto_improvement import AutoImprovementSystem, AutoImprovementConfig
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize FastAPI app
app = FastAPI(
    title="Regulatory Document Classifier",
    description="AI-powered document classification system for regulatory compliance",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
# Try to find dataset file in common locations
dataset_file = None
possible_dataset_paths = [
    Path("document_safety_dataset.json"),
    Path(__file__).parent.parent / "document_safety_dataset.json",
]
for path in possible_dataset_paths:
    if path.exists():
        dataset_file = str(path)
        logger.info(f"Found dataset file: {dataset_file}")
        break

pipeline = ClassificationPipeline(
    gemini_api_key=settings.gemini_api_key,
    mistral_api_key=settings.mistral_api_key,
    openai_api_key=settings.openai_api_key,
    legibility_threshold=settings.legibility_threshold,
    enable_dual_validation=settings.enable_dual_llm_validation,
    dataset_file=dataset_file,
    enable_few_shot=True
)

hitl_system = HITLFeedbackSystem()
audit_system = AuditTrailSystem()

# Initialize prompt refinement system (after pipeline is created)
refinement_system = PromptRefinementSystem(hitl_system, pipeline.prompt_library)

# Initialize automatic improvement system
# Get config from environment or use defaults
auto_improvement_config = AutoImprovementConfig(
    feedback_threshold=int(os.getenv("AUTO_IMPROVEMENT_FEEDBACK_THRESHOLD", "10")),
    min_improvement_confidence=float(os.getenv("AUTO_IMPROVEMENT_MIN_CONFIDENCE", "0.75")),
    auto_apply_enabled=os.getenv("AUTO_IMPROVEMENT_ENABLED", "true").lower() == "true",
    min_feedback_for_analysis=int(os.getenv("AUTO_IMPROVEMENT_MIN_FEEDBACK", "5")),
    check_interval_seconds=int(os.getenv("AUTO_IMPROVEMENT_CHECK_INTERVAL", "300"))
)
auto_improvement_system = AutoImprovementSystem(
    hitl_system=hitl_system,
    refinement_system=refinement_system,
    config=auto_improvement_config
)

# Start background improvement loop
improvement_task = None

# In-memory storage for batch processing status
batch_status = {}

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.batch_connections: Dict[str, List[WebSocket]] = {}  # batch_id -> connections
    
    async def connect(self, websocket: WebSocket, batch_id: Optional[str] = None):
        await websocket.accept()
        self.active_connections.append(websocket)
        if batch_id:
            if batch_id not in self.batch_connections:
                self.batch_connections[batch_id] = []
            self.batch_connections[batch_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, batch_id: Optional[str] = None):
        self.active_connections.remove(websocket)
        if batch_id and batch_id in self.batch_connections:
            self.batch_connections[batch_id].remove(websocket)
            if not self.batch_connections[batch_id]:
                del self.batch_connections[batch_id]
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
    
    async def broadcast_to_batch(self, batch_id: str, message: dict):
        if batch_id in self.batch_connections:
            disconnected = []
            for connection in self.batch_connections[batch_id]:
                try:
                    await connection.send_json(message)
                except:
                    disconnected.append(connection)
            for conn in disconnected:
                self.disconnect(conn, batch_id)

manager = ConnectionManager()


# Pydantic models
class ClassificationResponse(BaseModel):
    """Response model for classification."""
    document_id: str
    document_name: str
    pages: int
    images: int
    classification: str
    confidence: float
    reasons: List[str]
    citations: List[Dict]
    safety_check: str
    is_legible: bool
    average_confidence_ocr: float
    needs_review: bool
    models_used: Dict
    consensus: bool
    reasoning: str
    detection_summary: Dict
    timestamp: str
    prompt_used: str


class TextClassificationRequest(BaseModel):
    """Request model for text classification."""
    text: str
    document_id: Optional[str] = None


class FeedbackRequest(BaseModel):
    """Request model for HITL feedback."""
    document_id: str
    original_classification: str
    corrected_classification: Optional[str] = None
    feedback_type: str = "correction"
    feedback_text: Optional[str] = None
    reviewer_id: Optional[str] = None
    confidence: Optional[float] = None
    prompt_used: Optional[str] = None
    detection_summary: Optional[Dict] = None


class BulkFeedbackItem(BaseModel):
    """Single item in bulk feedback request."""
    text: str
    correct_classification: str  # "Public", "Confidential", or "Highly Sensitive" (Note: "Unsafe" is a safety flag, not a classification)
    document_name: Optional[str] = None  # Optional name for the text sample


class BulkFeedbackRequest(BaseModel):
    """Request model for bulk feedback submission."""
    items: List[BulkFeedbackItem]
    reviewer_id: Optional[str] = None
    auto_trigger_improvement: bool = True  # Whether to trigger improvement after submission


class BatchRequest(BaseModel):
    """Request model for batch processing."""
    document_ids: List[str]


# Helper function to save uploaded file
def save_uploaded_file(file: UploadFile) -> str:
    """Save uploaded file to disk.
    
    Args:
        file: Uploaded file
        
    Returns:
        Path to saved file
    """
    # Create upload directory if it doesn't exist
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    file_id = str(uuid.uuid4())
    file_extension = Path(file.filename).suffix if file.filename else ".pdf"
    file_path = upload_dir / f"{file_id}{file_extension}"
    
    # Save file
    with open(file_path, "wb") as f:
        content = file.file.read()
        f.write(content)
    
    return str(file_path)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Regulatory Document Classifier API",
        "version": "1.0.0",
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/preprocess")
async def preprocess_document(
    file: UploadFile = File(...),
    request: Request = None
):
    """Preprocess document and return legibility, page count, and image count.
    
    This endpoint returns preprocessing information quickly before full classification.
    
    Args:
        file: Uploaded document file
        request: FastAPI request object
        
    Returns:
        Preprocessing information (legibility, pages, images)
    """
    try:
        # Validate file type
        if not file.filename or not file.filename.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg')):
            raise HTTPException(status_code=400, detail="Only PDF and image files are supported")
        
        # Save uploaded file
        file_path = save_uploaded_file(file)
        
        try:
            # Only do preprocessing (fast)
            preprocessed = pipeline.preprocessor.process_document(file_path)
            
            # Clean up file
            Path(file_path).unlink(missing_ok=True)
            
            return {
                "pages": preprocessed["total_pages"],
                "images": preprocessed["total_images"],
                "is_legible": preprocessed["is_legible"],
                "average_confidence": preprocessed["average_confidence"],
                "extraction_method": preprocessed.get("extraction_method", "unknown")
            }
        except Exception as e:
            Path(file_path).unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail=f"Preprocessing failed: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.post("/preprocess/text")
async def preprocess_text(request_body: TextClassificationRequest):
    """Preprocess text and return basic information.
    
    Args:
        request_body: Text classification request
        
    Returns:
        Preprocessing information for text
    """
    try:
        if not request_body.text or not request_body.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        # For text, preprocessing is simple
        return {
            "pages": 1,
            "images": 0,
            "is_legible": True,
            "average_confidence": 1.0,
            "extraction_method": "direct_text",
            "text_length": len(request_body.text)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.post("/classify", response_model=ClassificationResponse)
async def classify_document(
    file: UploadFile = File(...),
    document_id: Optional[str] = Form(None),
    request: Request = None
):
    """Classify a single document.
    
    Args:
        file: Uploaded document file
        document_id: Optional document ID (can be provided as form field)
        request: FastAPI request object for audit logging
        
    Returns:
        Classification result
    """
    try:
        # Validate file type
        if not file.filename or not file.filename.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg')):
            raise HTTPException(status_code=400, detail="Only PDF and image files are supported")
        
        # Save uploaded file
        file_path = save_uploaded_file(file)
        
        try:
            # Classify document - generate ID if not provided
            if not document_id or document_id.strip() == "":
                document_id = str(uuid.uuid4())
            
            # Log audit event
            client_ip = request.client.host if request else None
            user_agent = request.headers.get("user-agent") if request else None
            audit_system.log_event(
                event_type="classification",
                action="upload_and_classify",
                document_id=document_id,
                details={"filename": file.filename, "file_size": file.size},
                ip_address=client_ip,
                user_agent=user_agent
            )
            
            result = pipeline.classify_document(file_path, document_id)
            
            # Log classification result
            audit_system.log_event(
                event_type="classification",
                action="classification_complete",
                document_id=document_id,
                details={
                    "classification": result.get("classification"),
                    "confidence": result.get("confidence"),
                    "pages": result.get("pages"),
                    "is_legible": result.get("is_legible")
                },
                ip_address=client_ip,
                user_agent=user_agent
            )
            
            # Clean up file after processing
            Path(file_path).unlink(missing_ok=True)
            
            return ClassificationResponse(**result)
            
        except RuntimeError as e:
            # Clean up file on error
            Path(file_path).unlink(missing_ok=True)
            # Check if it's a Poppler error
            error_msg = str(e)
            if "poppler" in error_msg.lower() or "pdftoppm" in error_msg.lower():
                raise HTTPException(
                    status_code=500,
                    detail=f"PDF processing failed: Poppler is not installed or not accessible. "
                           f"Please install Poppler (see SETUP.md for instructions). "
                           f"Error details: {error_msg}"
                )
            raise HTTPException(status_code=500, detail=f"Processing failed: {error_msg}")
        except Exception as e:
            # Clean up file on error
            Path(file_path).unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.post("/classify/text", response_model=ClassificationResponse)
async def classify_text(
    request_body: TextClassificationRequest,
    http_request: Request = None
):
    """Classify text directly without file upload.
    
    Args:
        request_body: Text classification request with text and optional document_id
        http_request: FastAPI request object for audit logging
        
    Returns:
        Classification result
    """
    try:
        if not request_body.text or not request_body.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        # Generate document ID if not provided
        document_id = request_body.document_id if request_body.document_id else str(uuid.uuid4())
        
        # Log audit event
        client_ip = http_request.client.host if http_request else None
        user_agent = http_request.headers.get("user-agent") if http_request else None
        audit_system.log_event(
            event_type="classification",
            action="text_classify",
            document_id=document_id,
            details={"text_length": len(request_body.text)},
            ip_address=client_ip,
            user_agent=user_agent
        )
        
        result = pipeline.classify_text_direct(request_body.text, document_id)
        
        # Log classification result
        audit_system.log_event(
            event_type="classification",
            action="classification_complete",
            document_id=document_id,
            details={
                "classification": result.get("classification"),
                "confidence": result.get("confidence"),
                "pages": result.get("pages"),
                "is_legible": result.get("is_legible")
            },
            ip_address=client_ip,
            user_agent=user_agent
        )
        
        return ClassificationResponse(**result)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.post("/classify/batch")
async def classify_batch(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Classify multiple documents in batch.
    
    Args:
        files: List of uploaded files
        background_tasks: FastAPI background tasks
        
    Returns:
        Batch job ID and status
    """
    try:
        batch_id = str(uuid.uuid4())
        batch_status[batch_id] = {
            "status": "processing",
            "total": len(files),
            "completed": 0,
            "results": [],
            "errors": []
        }
        
        # Process files in background with WebSocket updates
        async def process_batch():
            for idx, file in enumerate(files):
                try:
                    file_path = save_uploaded_file(file)
                    document_id = str(uuid.uuid4())
                    
                    # Send preprocessing update (backend does this as part of classification)
                    # Note: preprocessing happens inside classify_document, but we send update before it starts
                    await manager.broadcast_to_batch(batch_id, {
                        "type": "preprocessing",
                        "batch_id": batch_id,
                        "current_file": file.filename,
                        "file_index": idx,
                        "total": len(files),
                        "status": "preprocessing"
                    })
                    
                    # Classify document (this includes preprocessing internally)
                    result = pipeline.classify_document(file_path, document_id)
                    
                    # Send progress update after preprocessing is done (classification in progress)
                    await manager.broadcast_to_batch(batch_id, {
                        "type": "progress",
                        "batch_id": batch_id,
                        "completed": idx,
                        "total": len(files),
                        "current_file": file.filename,
                        "status": "processing"
                    })
                    
                    # Extract preprocessing info from result
                    preprocessing_info = {
                        "filename": file.filename,
                        "pages": result.get("pages", 0),
                        "images": result.get("images", 0),
                        "is_legible": result.get("is_legible", False),
                        "average_confidence": result.get("average_confidence", 0.0)
                    }
                    
                    batch_status[batch_id]["results"].append(result)
                    batch_status[batch_id]["completed"] += 1
                    
                    # Send result update with preprocessing info
                    await manager.broadcast_to_batch(batch_id, {
                        "type": "result",
                        "batch_id": batch_id,
                        "document_id": document_id,
                        "result": result,
                        "preprocessing": preprocessing_info
                    })
                    
                    # Clean up
                    Path(file_path).unlink(missing_ok=True)
                    
                except Exception as e:
                    batch_status[batch_id]["errors"].append({
                        "filename": file.filename,
                        "error": str(e)
                    })
                    batch_status[batch_id]["completed"] += 1
                    
                    # Send error update
                    await manager.broadcast_to_batch(batch_id, {
                        "type": "error",
                        "batch_id": batch_id,
                        "filename": file.filename,
                        "error": str(e)
                    })
            
            batch_status[batch_id]["status"] = "completed"
            
            # Send completion update
            await manager.broadcast_to_batch(batch_id, {
                "type": "complete",
                "batch_id": batch_id,
                "total": len(files),
                "completed": batch_status[batch_id]["completed"],
                "errors": len(batch_status[batch_id]["errors"])
            })
        
        background_tasks.add_task(process_batch)
        
        return {
            "batch_id": batch_id,
            "status": "processing",
            "total": len(files),
            "message": "Batch processing started"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {str(e)}")


@app.get("/batch/{batch_id}/status")
async def get_batch_status(batch_id: str):
    """Get status of batch processing job.
    
    Args:
        batch_id: Batch job ID
        
    Returns:
        Batch processing status
    """
    if batch_id not in batch_status:
        raise HTTPException(status_code=404, detail="Batch job not found")
    
    return batch_status[batch_id]


@app.post("/feedback")
async def submit_feedback(feedback: FeedbackRequest, request: Request = None):
    """Submit HITL feedback.
    
    Args:
        feedback: Feedback data
        request: FastAPI request object for audit logging
        
    Returns:
        Feedback record ID
    """
    try:
        # Get prompt_used from feedback (should be provided by frontend)
        prompt_used = feedback.prompt_used
        if not prompt_used:
            # Try to get from audit trail - look for recent classification event
            try:
                recent_events = audit_system.get_audit_history(
                    event_type="classification",
                    document_id=feedback.document_id,
                    limit=1
                )
                if recent_events:
                    # Try to extract prompt_used from event details
                    details = recent_events[0].get("details", {})
                    if isinstance(details, str):
                        # If details is a JSON string, parse it
                        try:
                            details = json.loads(details)
                        except:
                            details = {}
                    prompt_used = details.get("prompt_used")
                
                # If still not found, try getting from classification result directly
                if not prompt_used:
                    # Query the classification result from the database/cache if available
                    # For now, default to base_classification if we can't find it
                    prompt_used = "base_classification"
                    logger.warning(f"Could not determine prompt_used for document {feedback.document_id}, defaulting to base_classification")
            except Exception as e:
                logger.warning(f"Error retrieving prompt_used from audit trail: {e}")
                prompt_used = "base_classification"  # Default fallback
        
        feedback_id = hitl_system.add_feedback(
            document_id=feedback.document_id,
            original_classification=feedback.original_classification,
            corrected_classification=feedback.corrected_classification,
            feedback_type=feedback.feedback_type,
            feedback_text=feedback.feedback_text,
            reviewer_id=feedback.reviewer_id,
            confidence=feedback.confidence,
            prompt_used=prompt_used,
            detection_summary=feedback.detection_summary
        )
        
        # Log audit event
        client_ip = request.client.host if request else None
        user_agent = request.headers.get("user-agent") if request else None
        audit_system.log_event(
            event_type="feedback",
            action="submit_feedback",
            user_id=feedback.reviewer_id,
            document_id=feedback.document_id,
            details={
                "feedback_id": feedback_id,
                "feedback_type": feedback.feedback_type,
                "original_classification": feedback.original_classification,
                "corrected_classification": feedback.corrected_classification
            },
            ip_address=client_ip,
            user_agent=user_agent
        )
        
        # Trigger automatic improvement check (non-blocking)
        # Note: The background loop will handle this, but we can also trigger immediately
        try:
            if auto_improvement_system and auto_improvement_system.should_analyze():
                # Schedule background task for analysis (non-blocking)
                asyncio.create_task(auto_improvement_system.analyze_and_improve_automatically())
        except Exception as e:
            # Don't fail feedback submission if auto-improvement fails
            logger.error(f"Auto-improvement trigger failed: {e}")
        
        return {
            "feedback_id": feedback_id,
            "message": "Feedback submitted successfully"
        }
    except Exception as e:
        logger.error(f"Failed to submit feedback: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")


@app.post("/feedback/bulk")
async def submit_bulk_feedback(bulk_request: BulkFeedbackRequest, request: Request = None):
    """Submit bulk feedback for multiple text samples with correct classifications.
    
    This endpoint allows you to provide a list of text samples with their correct
    classifications. The system will:
    1. Classify each text sample
    2. Compare with the correct classification
    3. Submit feedback automatically
    4. Optionally trigger prompt improvement
    
    Args:
        bulk_request: Bulk feedback data with list of (text, correct_classification) pairs
        request: FastAPI request object for audit logging
        
    Returns:
        Summary of bulk feedback submission
    """
    try:
        results = []
        errors = []
        
        for idx, item in enumerate(bulk_request.items):
            try:
                # Classify the text
                classification_result = pipeline.classify_text_direct(
                    text=item.text,
                    document_id=f"bulk_{idx}_{hash(item.text) % 10000}"
                )
                
                original_classification = classification_result.get("classification")
                correct_classification = item.correct_classification
                prompt_used = classification_result.get("prompt_used", "base_classification")
                
                # Determine feedback type
                if original_classification == correct_classification:
                    feedback_type = "confirmation"
                    corrected_classification = None
                else:
                    feedback_type = "correction"
                    corrected_classification = correct_classification
                
                # Submit feedback
                feedback_id = hitl_system.add_feedback(
                    document_id=classification_result.get("document_id"),
                    original_classification=original_classification,
                    corrected_classification=corrected_classification,
                    feedback_type=feedback_type,
                    feedback_text=f"Bulk feedback for: {item.document_name or 'Text sample'}",
                    reviewer_id=bulk_request.reviewer_id or "bulk_feedback",
                    confidence=classification_result.get("confidence", 0.0),
                    prompt_used=prompt_used
                )
                
                # Log audit event
                if audit_system:
                    audit_system.log_event(
                        event_type="feedback",
                        action="submit_bulk_feedback",
                        document_id=classification_result.get("document_id"),
                        details={
                            "feedback_id": feedback_id,
                            "original": original_classification,
                            "correct": correct_classification,
                            "type": feedback_type,
                            "bulk_index": idx
                        },
                        ip_address=request.client.host if request else None,
                        user_agent=request.headers.get("user-agent") if request else None
                    )
                
                results.append({
                    "index": idx,
                    "feedback_id": feedback_id,
                    "original_classification": original_classification,
                    "correct_classification": correct_classification,
                    "match": original_classification == correct_classification,
                    "document_name": item.document_name
                })
                
            except Exception as e:
                errors.append({
                    "index": idx,
                    "error": str(e),
                    "text_preview": item.text[:50] + "..." if len(item.text) > 50 else item.text
                })
                logger.error(f"Error processing bulk feedback item {idx}: {e}")
        
        # Calculate statistics
        total = len(bulk_request.items)
        successful = len(results)
        corrections = sum(1 for r in results if not r["match"])
        confirmations = sum(1 for r in results if r["match"])
        
        # Trigger automatic improvement if requested and threshold is met
        improvement_triggered = False
        if bulk_request.auto_trigger_improvement and auto_improvement_system:
            try:
                if auto_improvement_system.should_analyze():
                    asyncio.create_task(auto_improvement_system.analyze_and_improve_automatically())
                    improvement_triggered = True
            except Exception as e:
                logger.error(f"Failed to trigger auto-improvement: {e}")
        
        return {
            "message": f"Bulk feedback submitted: {successful}/{total} successful",
            "total": total,
            "successful": successful,
            "errors": len(errors),
            "corrections": corrections,
            "confirmations": confirmations,
            "results": results,
            "error_details": errors,
            "improvement_triggered": improvement_triggered
        }
        
    except Exception as e:
        logger.error(f"Bulk feedback submission failed: {e}")
        raise HTTPException(status_code=500, detail=f"Bulk feedback failed: {str(e)}")


@app.get("/feedback/{document_id}")
async def get_feedback(document_id: str):
    """Get feedback for a document.
    
    Args:
        document_id: Document ID
        
    Returns:
        List of feedback records
    """
    try:
        feedback = hitl_system.get_feedback(document_id)
        return {"document_id": document_id, "feedback": feedback}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get feedback: {str(e)}")


@app.get("/feedback/pending")
async def get_pending_reviews(limit: int = 100):
    """Get documents pending review.
    
    Args:
        limit: Maximum number of records to return
        
    Returns:
        List of pending review records
    """
    try:
        pending = hitl_system.get_pending_reviews(limit=limit)
        return {"pending_reviews": pending}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get pending reviews: {str(e)}")


@app.get("/feedback/stats")
async def get_feedback_stats():
    """Get classification accuracy statistics.
    
    Returns:
        Accuracy statistics
    """
    try:
        stats = hitl_system.get_classification_accuracy_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@app.get("/feedback/prompt-performance")
async def get_prompt_performance():
    """Get performance statistics by prompt template.
    
    Returns:
        Prompt performance metrics
    """
    try:
        performance = hitl_system.get_prompt_performance()
        return {"prompt_performance": performance}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get prompt performance: {str(e)}")


@app.post("/feedback/{feedback_id}/resolve")
async def resolve_feedback(feedback_id: int):
    """Mark feedback as resolved.
    
    Args:
        feedback_id: Feedback record ID
        
    Returns:
        Success message
    """
    try:
        hitl_system.mark_resolved(feedback_id)
        return {"message": "Feedback marked as resolved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve feedback: {str(e)}")


@app.post("/refinement/analyze")
async def analyze_and_suggest_improvements(
    prompt_name: Optional[str] = Query(None),
    min_feedback_count: int = Query(3)
):
    """Analyze feedback and get LLM-generated prompt improvement suggestions.
    
    Args:
        prompt_name: Specific prompt to analyze (optional, as query param)
        min_feedback_count: Minimum feedback count required (as query param)
        
    Returns:
        Analysis results with suggested improvements
    """
    try:
        if not refinement_system:
            raise HTTPException(status_code=500, detail="Refinement system not initialized")
        
        result = refinement_system.analyze_feedback_and_suggest_improvements(
            prompt_name=prompt_name,
            min_feedback_count=min_feedback_count
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/refinement/apply")
async def apply_prompt_improvement(
    prompt_name: str,
    improved_prompt: str,
    reason: str,
    auto_apply: bool = False
):
    """Apply a prompt improvement suggestion.
    
    Args:
        prompt_name: Name of prompt to update
        improved_prompt: The improved prompt text
        reason: Reason for the change
        auto_apply: Whether to apply immediately (default: False, requires approval)
        
    Returns:
        Status of the application
    """
    try:
        if not refinement_system:
            raise HTTPException(status_code=500, detail="Refinement system not initialized")
        
        prompt_name = request_body.get("prompt_name")
        improved_prompt = request_body.get("improved_prompt")
        reason = request_body.get("reason")
        auto_apply = request_body.get("auto_apply", False)
        
        result = refinement_system.apply_prompt_improvement(
            prompt_name=prompt_name,
            improved_prompt=improved_prompt,
            reason=reason,
            auto_apply=auto_apply
        )
        
        # Log audit event
        audit_system.log_event(
            event_type="system",
            action="prompt_refinement",
            details={
                "prompt_name": prompt_name,
                "auto_applied": auto_apply,
                "reason": reason
            }
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply improvement: {str(e)}")


@app.get("/refinement/history")
async def get_refinement_history(prompt_name: Optional[str] = None):
    """Get refinement history.
    
    Args:
        prompt_name: Filter by prompt name (optional)
        
    Returns:
        List of refinement records
    """
    try:
        if not refinement_system:
            raise HTTPException(status_code=500, detail="Refinement system not initialized")
        
        history = refinement_system.get_refinement_history(prompt_name=prompt_name)
        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


@app.get("/refinement/suggestions")
async def get_pending_suggestions():
    """Get pending (not yet applied) prompt improvement suggestions.
    
    Returns:
        List of pending suggestions
    """
    try:
        if not refinement_system:
            raise HTTPException(status_code=500, detail="Refinement system not initialized")
        
        suggestions = refinement_system.get_pending_suggestions()
        return {"suggestions": suggestions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get suggestions: {str(e)}")


@app.get("/auto-improvement/status")
async def get_auto_improvement_status():
    """Get status of automatic improvement system.
    
    Returns:
        Status information
    """
    try:
        if not auto_improvement_system:
            raise HTTPException(status_code=500, detail="Auto-improvement system not initialized")
        
        status = auto_improvement_system.get_status()
        
        # Get accuracy trend
        accuracy_tracker = auto_improvement_system.accuracy_tracker
        trend = accuracy_tracker.get_accuracy_trend(days=30)
        latest = accuracy_tracker.get_latest_accuracy()
        
        status["accuracy_trend"] = trend[-10:] if len(trend) > 10 else trend  # Last 10 snapshots
        status["latest_accuracy"] = latest
        
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@app.post("/auto-improvement/trigger")
async def trigger_auto_improvement():
    """Manually trigger automatic improvement analysis.
    
    Returns:
        Analysis and improvement results
    """
    try:
        if not auto_improvement_system:
            raise HTTPException(status_code=500, detail="Auto-improvement system not initialized")
        
        result = await auto_improvement_system.analyze_and_improve_automatically()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger improvement: {str(e)}")


@app.get("/auto-improvement/accuracy-trend")
async def get_accuracy_trend(prompt_name: Optional[str] = None, days: int = 30):
    """Get accuracy trend over time.
    
    Args:
        prompt_name: Optional prompt name to filter
        days: Number of days to look back
        
    Returns:
        Accuracy trend data
    """
    try:
        if not auto_improvement_system:
            raise HTTPException(status_code=500, detail="Auto-improvement system not initialized")
        
        trend = auto_improvement_system.accuracy_tracker.get_accuracy_trend(
            prompt_name=prompt_name,
            days=days
        )
        
        return {
            "trend": trend,
            "prompt_name": prompt_name,
            "days": days
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get trend: {str(e)}")


@app.on_event("startup")
async def startup_event():
    """Start background tasks on server startup."""
    global improvement_task
    try:
        # Start continuous improvement loop
        improvement_task = asyncio.create_task(
            auto_improvement_system.run_continuous_improvement_loop()
        )
        logger.info("Started automatic improvement background task")
    except Exception as e:
        logger.error(f"Failed to start improvement task: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on server shutdown."""
    global improvement_task
    try:
        if auto_improvement_system:
            auto_improvement_system.stop()
        if improvement_task:
            improvement_task.cancel()
        logger.info("Stopped automatic improvement background task")
    except Exception as e:
        logger.error(f"Error shutting down improvement task: {e}")


@app.get("/models")
async def get_models_info():
    """Get information about models used.
    
    Returns:
        Model information
    """
    return {
        "primary_model": settings.primary_llm_model,
        "secondary_model": settings.secondary_llm_model,
        "dual_validation_enabled": settings.enable_dual_llm_validation,
        "moderation_model": settings.openai_moderation_model
    }


# WebSocket endpoint for real-time updates
@app.websocket("/ws/batch/{batch_id}")
async def websocket_batch_updates(websocket: WebSocket, batch_id: str):
    """WebSocket endpoint for real-time batch processing updates.
    
    Args:
        websocket: WebSocket connection
        batch_id: Batch job ID
    """
    await manager.connect(websocket, batch_id)
    try:
        while True:
            # Keep connection alive and wait for messages
            data = await websocket.receive_text()
            # Echo back or handle client messages if needed
            await manager.send_personal_message(f"Echo: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket, batch_id)


# Audit Trail Endpoints
@app.get("/audit/history")
async def get_audit_history(
    event_type: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    document_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """Get audit history with filters.
    
    Returns:
        List of audit records
    """
    try:
        start = datetime.fromisoformat(start_date) if start_date else None
        end = datetime.fromisoformat(end_date) if end_date else None
        
        records = audit_system.get_audit_history(
            event_type=event_type,
            action=action,
            user_id=user_id,
            document_id=document_id,
            start_date=start,
            end_date=end,
            limit=limit,
            offset=offset
        )
        return {"records": records, "total": len(records)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audit history: {str(e)}")


@app.get("/audit/stats")
async def get_audit_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get audit statistics.
    
    Returns:
        Audit statistics
    """
    try:
        start = datetime.fromisoformat(start_date) if start_date else None
        end = datetime.fromisoformat(end_date) if end_date else None
        
        stats = audit_system.get_audit_stats(start_date=start, end_date=end)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audit stats: {str(e)}")


@app.get("/audit/document/{document_id}")
async def get_document_audit_history(document_id: str):
    """Get complete audit history for a document.
    
    Returns:
        List of audit records for the document
    """
    try:
        records = audit_system.get_document_history(document_id)
        return {"document_id": document_id, "records": records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get document history: {str(e)}")


# Statistics endpoints for visualizations
@app.get("/stats/classification-distribution")
async def get_classification_distribution(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get classification distribution for charts.
    
    Returns:
        Classification distribution data
    """
    try:
        start = datetime.fromisoformat(start_date) if start_date else None
        end = datetime.fromisoformat(end_date) if end_date else None
        
        # Get all classification events
        records = audit_system.get_audit_history(
            event_type="classification",
            action="classification_complete",
            start_date=start,
            end_date=end,
            limit=10000
        )
        
        # Count classifications
        distribution = {
            "Public": 0,
            "Confidential": 0,
            "Highly Sensitive": 0,
            "Unsafe": 0
        }
        
        for record in records:
            classification = record.get("details", {}).get("classification", "")
            if classification in distribution:
                distribution[classification] += 1
        
        return {
            "distribution": distribution,
            "total": sum(distribution.values()),
            "start_date": start_date,
            "end_date": end_date
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get classification distribution: {str(e)}")


@app.get("/stats/hitl-feedback")
async def get_hitl_feedback_stats():
    """Get HITL feedback statistics for charts.
    
    Returns:
        HITL feedback statistics
    """
    try:
        stats = hitl_system.get_classification_accuracy_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get HITL stats: {str(e)}")


# PDF Report Generation
@app.post("/report/pdf")
async def generate_pdf_report_from_data(result: ClassificationResponse):
    """Generate PDF report from classification result data.
    
    Args:
        result: Classification result data
        
    Returns:
        PDF file stream
    """
    try:
        document_id = result.document_id
        details = {
            "classification": result.classification,
            "confidence": result.confidence,
            "pages": result.pages,
            "is_legible": result.is_legible,
            "timestamp": result.timestamp
        }
        
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        story = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#3b82f6'),
            spaceAfter=12
        )
        
        # Title
        story.append(Paragraph("Classification Report", title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Document Info
        story.append(Paragraph("Document Information", heading_style))
        info_data = [
            ["Document ID:", document_id],
            ["Document Name:", result.document_name],
            ["Classification:", details.get("classification", "N/A")],
            ["Confidence:", f"{details.get('confidence', 0):.1%}"],
            ["Pages:", str(details.get("pages", 0))],
            ["Images:", str(result.images)],
            ["Legible:", "Yes" if details.get("is_legible") else "No"],
            ["Safety Check:", result.safety_check],
            ["Timestamp:", details.get("timestamp", "N/A")]
        ]
        info_table = Table(info_data, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        story.append(info_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Reasons
        if result.reasons:
            story.append(Paragraph("Classification Reasons", heading_style))
            for reason in result.reasons:
                story.append(Paragraph(f"• {reason}", styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
            story.append(Spacer(1, 0.2*inch))
        
        # Detection Summary
        if result.detection_summary:
            story.append(Paragraph("Detection Summary", heading_style))
            detection_data = [
                ["PII Count:", str(result.detection_summary.get("pii_count", 0))],
                ["Keyword Count:", str(result.detection_summary.get("keyword_count", 0))],
            ]
            if result.detection_summary.get("unsafe_pages"):
                detection_data.append(["Unsafe Pages:", ", ".join(map(str, result.detection_summary["unsafe_pages"]))])
            detection_table = Table(detection_data, colWidths=[2*inch, 4*inch])
            detection_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey)
            ]))
            story.append(detection_table)
            story.append(Spacer(1, 0.3*inch))
        
        # Citations
        if result.citations and len(result.citations) > 0:
            story.append(Paragraph("Citations", heading_style))
            citation_data = [["Page", "Type", "Snippet"]]
            for citation in result.citations[:20]:  # Limit to 20 citations
                citation_data.append([
                    str(citation.get("page", "N/A")),
                    citation.get("type", "N/A"),
                    citation.get("snippet", "")[:100]  # Truncate long snippets
                ])
            citation_table = Table(citation_data, colWidths=[0.8*inch, 1.2*inch, 4*inch])
            citation_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
            ]))
            story.append(citation_table)
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=classification_report_{document_id}.pdf"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")


@app.get("/report/{document_id}/pdf")
async def generate_pdf_report(document_id: str):
    """Generate PDF report for a classification result (legacy endpoint using audit trail).
    
    Args:
        document_id: Document ID
        
    Returns:
        PDF file stream
    """
    try:
        # Get audit records for this document
        records = audit_system.get_document_history(document_id)
        
        # Find the classification result
        classification_record = None
        for record in records:
            if record.get("action") == "classification_complete":
                classification_record = record
                break
        
        if not classification_record:
            raise HTTPException(status_code=404, detail="Classification result not found")
        
        details = classification_record.get("details", {})
        
        # Create PDF directly with available data
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        story = []
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#3b82f6'),
            spaceAfter=12
        )
        
        story.append(Paragraph("Classification Report", title_style))
        story.append(Spacer(1, 0.2*inch))
        
        story.append(Paragraph("Document Information", heading_style))
        info_data = [
            ["Document ID:", document_id],
            ["Classification:", details.get("classification", "N/A")],
            ["Confidence:", f"{details.get('confidence', 0):.1%}"],
            ["Pages:", str(details.get("pages", 0))],
            ["Legible:", "Yes" if details.get("is_legible") else "No"],
            ["Timestamp:", classification_record.get("timestamp", "N/A")]
        ]
        info_table = Table(info_data, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        story.append(info_table)
        
        doc.build(story)
        buffer.seek(0)
        
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=classification_report_{document_id}.pdf"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")

