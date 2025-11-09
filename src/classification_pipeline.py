"""Main classification pipeline that orchestrates all components."""
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import uuid
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from .preprocessing import DocumentPreprocessor
from .pii_detection import PIIDetector
from .safety_detection import SafetyDetector
from .prompt_library import PromptLibrary
from .llm_integration import LLMIntegration


class ClassificationPipeline:
    """Orchestrates the complete document classification pipeline."""
    
    def __init__(
        self,
        gemini_api_key: str,
        mistral_api_key: str,
        openai_api_key: str,
        legibility_threshold: float = 0.6,
        enable_dual_validation: bool = True,
        prompts_file: Optional[str] = None,
        tree_file: Optional[str] = None,
        dataset_file: Optional[str] = None,
        enable_few_shot: bool = True
    ):
        """Initialize the classification pipeline.
        
        Args:
            gemini_api_key: Gemini API key
            mistral_api_key: Mistral API key
            openai_api_key: OpenAI API key
            legibility_threshold: OCR legibility threshold
            enable_dual_validation: Whether to use dual LLM validation
            prompts_file: Optional path to custom prompts file
            tree_file: Optional path to decision tree configuration file
            dataset_file: Optional path to dataset JSON file for few-shot learning
            enable_few_shot: Whether to enable few-shot learning (default: True)
        """
        self.preprocessor = DocumentPreprocessor(legibility_threshold=legibility_threshold)
        self.pii_detector = PIIDetector()
        self.safety_detector = SafetyDetector(openai_api_key=openai_api_key)
        self.prompt_library = PromptLibrary(
            prompts_file=prompts_file,
            tree_file=tree_file,
            dataset_file=dataset_file,
            enable_few_shot=enable_few_shot
        )
        self.llm = LLMIntegration(
            gemini_api_key=gemini_api_key,
            mistral_api_key=mistral_api_key
        )
        self.enable_dual_validation = enable_dual_validation
        # Number of parallel workers for page processing
        self.max_workers = 4  # Adjust based on system capabilities
    
    def classify_document(
        self,
        file_path: str,
        document_id: Optional[str] = None
    ) -> Dict:
        """Classify a complete document.
        
        Args:
            file_path: Path to document file
            document_id: Optional document ID (generated if not provided)
            
        Returns:
            Complete classification result
        """
        if document_id is None:
            document_id = str(uuid.uuid4())
        
        # Step 1: Preprocessing
        preprocessed = self.preprocessor.process_document(file_path)
        
        # Step 2: Rule-based extraction (parallel processing)
        pii_detections = []
        keyword_detections = []
        safety_issues = []
        
        # Prepare page data for parallel processing
        page_texts = [(page_data["text"], page_data["page_number"]) for page_data in preprocessed["pages"]]
        
        # Process pages in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            futures = []
            for page_text, page_num in page_texts:
                # Submit PII and keyword detection (CPU-bound, can run in parallel)
                pii_future = executor.submit(self.pii_detector.detect_all, page_text, page_num)
                keyword_future = executor.submit(self.pii_detector.detect_sensitive_keywords, page_text, page_num)
                futures.append((page_num, pii_future, keyword_future))
            
            # Collect results in page order
            results_by_page = {}
            for page_num, pii_future, keyword_future in futures:
                pii_result = pii_future.result()
                keyword_result = keyword_future.result()
                results_by_page[page_num] = {
                    "pii": pii_result,
                    "keyword": keyword_result
                }
        
        # Sort by page number and extract
        for page_num in sorted(results_by_page.keys()):
            pii_detections.append(results_by_page[page_num]["pii"])
            keyword_detections.append(results_by_page[page_num]["keyword"])
        
        # Batch safety detection (single API call for all pages)
        safety_issues = self.safety_detector.detect_unsafe_content_batch(page_texts)
        
        # Early exit optimization: Check if document is clearly Public
        total_pii = sum(p.get("count", 0) for p in pii_detections)
        total_keywords = sum(k.get("count", 0) for k in keyword_detections)
        is_unsafe = any(issue.get("is_unsafe", False) for issue in safety_issues)
        
        # If no PII, no keywords, safe, and legible, might be clearly Public
        # But we still need LLM to confirm, so we'll continue processing
        # (Early exit could be added here if needed, but LLM validation is still valuable)
        
        # Step 3: Prepare evidence for LLM
        detections = {
            "pii_detections": pii_detections,
            "keyword_detections": keyword_detections,
            "safety_issues": safety_issues,
            "image_count": preprocessed["total_images"]
        }
        
        # Step 4: Select and format prompt
        prompt_name = self.prompt_library.select_prompt(detections)
        evidence = self.prompt_library.format_evidence(detections)
        
        # Combine all page text
        full_text_parts = [
            f"\n\n--- Page {page_data['page_number']} ---\n{page_data['text']}"
            for page_data in preprocessed["pages"]
        ]
        full_text = "\n".join(full_text_parts)
        
        # Generate prompt
        prompt = self.prompt_library.get_prompt(
            prompt_name,
            total_pages=preprocessed["total_pages"],
            total_images=preprocessed["total_images"],
            is_legible=preprocessed["is_legible"],
            text=full_text[:8000],  # Limit text length
            pii_evidence=evidence["pii_evidence"],
            keyword_evidence=evidence["keyword_evidence"],
            safety_evidence=evidence["safety_evidence"],
            image_descriptions="Embedded images detected" if preprocessed["total_images"] > 0 else "No embedded images"
        )
        
        # Step 5: LLM Classification
        llm_result = self.llm.classify_with_dual_validation(
            prompt=prompt,
            document_text=full_text,
            enable_secondary=self.enable_dual_validation
        )
        
        # Step 6: Aggregate and format final result
        from .llm_integration import normalize_classification
        final_classification = normalize_classification(llm_result.get("final_classification", "Public"))
        final_confidence = llm_result.get("final_confidence", 0.5)
        
        # Determine if unsafe (safety check - separate from classification)
        is_unsafe = any(issue.get("is_unsafe", False) for issue in safety_issues)
        # Note: is_unsafe is a safety flag, NOT a classification
        # Classification remains Public/Confidential/Highly Sensitive
        # Safety status is separate: Safe or Unsafe
        
        # Build citations
        citations = []
        if llm_result.get("primary"):
            primary_citations = llm_result["primary"].get("citations", [])
            citations.extend(primary_citations)
        
        # Add PII citations
        for pii_page in pii_detections:
            if pii_page.get("count", 0) > 0:
                for match in pii_page.get("matches", []):
                    citations.append({
                        "page": pii_page["page"],
                        "snippet": match["text"],
                        "type": "PII"
                    })
        
        # Add safety citations
        for safety_page in safety_issues:
            if safety_page.get("is_unsafe", False):
                concerns = safety_page.get("primary_concerns", [])
                citations.append({
                    "page": safety_page["page"],
                    "snippet": f"Unsafe content: {', '.join(concerns)}",
                    "type": "Safety"
                })
        
        # Build final result
        result = {
            "document_id": document_id,
            "document_name": Path(file_path).name,
            "pages": preprocessed["total_pages"],
            "images": preprocessed["total_images"],
            "classification": final_classification,
            "confidence": final_confidence,
            "reasons": llm_result.get("primary", {}).get("reasons", []),
            "citations": citations,
            "safety_check": "Unsafe" if is_unsafe else "Safe",
            "is_legible": preprocessed["is_legible"],
            "average_confidence_ocr": preprocessed["average_confidence"],
            "extraction_method": preprocessed.get("extraction_method", "unknown"),
            "needs_review": llm_result.get("needs_review", False) or not llm_result.get("consensus", True),
            "models_used": {
                "primary": self.llm.primary_model_name,
                "secondary": self.llm.secondary_model_name if self.enable_dual_validation else None
            },
            "consensus": llm_result.get("consensus", True),
            "reasoning": llm_result.get("primary", {}).get("reasoning", ""),
            "detection_summary": {
                "pii_count": sum(p.get("count", 0) for p in pii_detections),
                "keyword_count": sum(k.get("count", 0) for k in keyword_detections),
                "unsafe_pages": [s["page"] for s in safety_issues if s.get("is_unsafe", False)]
            },
            "timestamp": datetime.utcnow().isoformat(),
            "prompt_used": prompt_name
        }
        
        return result
    
    def classify_document_bytes(
        self,
        pdf_bytes: bytes,
        document_id: Optional[str] = None,
        filename: Optional[str] = None
    ) -> Dict:
        """Classify a document from bytes.
        
        Args:
            pdf_bytes: PDF file as bytes
            document_id: Optional document ID
            filename: Optional filename for reference
            
        Returns:
            Complete classification result
        """
        # Save to temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(pdf_bytes)
            tmp_path = tmp_file.name
        
        try:
            result = self.classify_document(tmp_path, document_id)
            if filename:
                result["document_name"] = filename
            return result
        finally:
            # Clean up
            Path(tmp_path).unlink(missing_ok=True)
    
    def classify_text_direct(self, text: str, document_id: Optional[str] = None) -> Dict:
        """Classify text directly without file processing.
        
        Args:
            text: Text content to classify
            document_id: Optional document ID
            
        Returns:
            Complete classification result
        """
        if document_id is None:
            document_id = str(uuid.uuid4())
        
        # Create a mock preprocessed structure for text input
        # Treat text as a single page
        preprocessed = {
            "total_pages": 1,
            "total_images": 0,
            "average_confidence": 1.0,  # High confidence for direct text
            "is_legible": True,
            "pages": [{
                "page_number": 1,
                "text": text,
                "bounding_boxes": [],
                "confidence_scores": [],
                "average_confidence": 1.0,
                "is_legible": True,
                "extraction_method": "direct_text"
            }],
            "embedded_images": [],
            "extraction_method": "direct_text"
        }
        
        # Step 2: Rule-based extraction
        page_texts = [(text, 1)]
        
        # PII and keyword detection
        pii_result = self.pii_detector.detect_all(text, 1)
        keyword_result = self.pii_detector.detect_sensitive_keywords(text, 1)
        
        # Safety detection
        safety_issues = self.safety_detector.detect_unsafe_content_batch(page_texts)
        
        # Step 3: Prepare evidence for LLM
        detections = {
            "pii_detections": [pii_result],
            "keyword_detections": [keyword_result],
            "safety_issues": safety_issues,
            "image_count": 0
        }
        
        # Step 4: Select and format prompt
        prompt_name = self.prompt_library.select_prompt(detections)
        evidence = self.prompt_library.format_evidence(detections)
        
        # Generate prompt
        prompt = self.prompt_library.get_prompt(
            prompt_name,
            total_pages=1,
            total_images=0,
            is_legible=True,
            text=text[:8000],  # Limit text length
            pii_evidence=evidence["pii_evidence"],
            keyword_evidence=evidence["keyword_evidence"],
            safety_evidence=evidence["safety_evidence"],
            image_descriptions="No embedded images"
        )
        
        # Step 5: LLM Classification
        llm_result = self.llm.classify_with_dual_validation(
            prompt=prompt,
            document_text=text,
            enable_secondary=self.enable_dual_validation
        )
        
        # Step 6: Aggregate and format final result (same as classify_document)
        from .llm_integration import normalize_classification
        final_classification = normalize_classification(llm_result.get("final_classification", "Public"))
        final_confidence = llm_result.get("final_confidence", 0.5)
        
        # Determine if unsafe (safety check - separate from classification)
        is_unsafe = any(issue.get("is_unsafe", False) for issue in safety_issues)
        # Note: is_unsafe is a safety flag, NOT a classification
        # Classification remains Public/Confidential/Highly Sensitive
        # Safety status is separate: Safe or Unsafe
        
        # Build citations
        citations = []
        if llm_result.get("primary"):
            primary_citations = llm_result["primary"].get("citations", [])
            citations.extend(primary_citations)
        
        # Add PII citations
        if pii_result.get("count", 0) > 0:
            for match in pii_result.get("matches", []):
                citations.append({
                    "page": 1,
                    "snippet": match["text"],
                    "type": "PII"
                })
        
        # Add safety citations
        for safety_page in safety_issues:
            if safety_page.get("is_unsafe", False):
                concerns = safety_page.get("primary_concerns", [])
                citations.append({
                    "page": 1,
                    "snippet": f"Unsafe content: {', '.join(concerns)}",
                    "type": "Safety"
                })
        
        # Build final result
        result = {
            "document_id": document_id,
            "document_name": "text_input.txt",
            "pages": 1,
            "images": 0,
            "classification": final_classification,
            "confidence": final_confidence,
            "reasons": llm_result.get("primary", {}).get("reasons", []),
            "citations": citations,
            "safety_check": "Unsafe" if is_unsafe else "Safe",
            "is_legible": True,
            "average_confidence_ocr": 1.0,
            "extraction_method": "direct_text",
            "needs_review": llm_result.get("needs_review", False) or not llm_result.get("consensus", True),
            "models_used": {
                "primary": self.llm.primary_model_name,
                "secondary": self.llm.secondary_model_name if self.enable_dual_validation else None
            },
            "consensus": llm_result.get("consensus", True),
            "reasoning": llm_result.get("primary", {}).get("reasoning", ""),
            "detection_summary": {
                "pii_count": pii_result.get("count", 0),
                "keyword_count": keyword_result.get("count", 0),
                "unsafe_pages": [1] if is_unsafe else []
            },
            "timestamp": datetime.utcnow().isoformat(),
            "prompt_used": prompt_name
        }
        
        return result

