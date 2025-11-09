"""Preprocessing module for document extraction and OCR."""
import io
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
from PIL import Image
import PyPDF2
from pdf2image import convert_from_path, convert_from_bytes
from paddleocr import PaddleOCR
import numpy as np
import shutil


class DocumentPreprocessor:
    """Handles PDF extraction, OCR, and page/image analysis."""
    
    def __init__(self, legibility_threshold: float = 0.6, ocr_dpi: int = 150, use_angle_cls: bool = False):
        """Initialize the preprocessor.
        
        Args:
            legibility_threshold: Minimum OCR confidence to consider text legible
            ocr_dpi: DPI for OCR (lower = faster, default 150)
            use_angle_cls: Whether to use angle classification (slower, default False)
        """
        self.legibility_threshold = legibility_threshold
        self.ocr_dpi = ocr_dpi
        # PaddleOCR 2.9+ doesn't support show_log parameter
        # Only initialize OCR if needed (lazy loading)
        self.ocr = None
        self._ocr_initialized = False
        self._use_angle_cls = use_angle_cls
        # Check if Poppler is installed
        self._check_poppler()
    
    def _initialize_ocr_if_needed(self):
        """Lazy initialization of OCR to avoid startup delay."""
        if not self._ocr_initialized:
            self.ocr = PaddleOCR(use_angle_cls=self._use_angle_cls, lang='en')
            self._ocr_initialized = True
    
    def _check_poppler(self):
        """Check if Poppler is installed and accessible.
        
        Raises:
            RuntimeError: If Poppler is not installed
        """
        # Check for pdftoppm command (part of Poppler)
        poppler_found = False
        
        # Try to find pdftoppm in common locations
        if shutil.which("pdftoppm"):
            poppler_found = True
        else:
            # Try common installation paths
            common_paths = [
                "/usr/bin/pdftoppm",
                "/usr/local/bin/pdftoppm",
                "/opt/homebrew/bin/pdftoppm",  # macOS Homebrew
            ]
            for path in common_paths:
                if Path(path).exists():
                    poppler_found = True
                    break
        
        if not poppler_found:
            raise RuntimeError(
                "Poppler is not installed. pdf2image requires Poppler to convert PDFs to images.\n"
                "Installation instructions:\n"
                "  Ubuntu/Debian: sudo apt-get install poppler-utils\n"
                "  CentOS/RHEL: sudo yum install poppler-utils\n"
                "  macOS: brew install poppler\n"
                "  Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases\n"
                "           and add to PATH, or use: conda install -c conda-forge poppler\n"
            )
    
    def extract_pages_from_pdf(self, file_path: str, dpi: Optional[int] = None) -> List[Image.Image]:
        """Extract pages from PDF as images.
        
        Args:
            file_path: Path to PDF file
            dpi: DPI for conversion (defaults to self.ocr_dpi)
            
        Returns:
            List of PIL Images, one per page
            
        Raises:
            RuntimeError: If Poppler is not installed or PDF conversion fails
        """
        try:
            # Use lower DPI for faster processing (default 150 instead of 200)
            dpi = dpi or self.ocr_dpi
            # Try to convert PDF to images
            images = convert_from_path(file_path, dpi=dpi)
            return images
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check for Poppler-related errors
            if "poppler" in error_msg or "pdftoppm" in error_msg or "pdftocairo" in error_msg:
                raise RuntimeError(
                    f"Poppler is required but not found or not accessible.\n"
                    f"Error: {str(e)}\n\n"
                    f"Installation instructions:\n"
                    f"  Ubuntu/Debian: sudo apt-get install poppler-utils\n"
                    f"  CentOS/RHEL: sudo yum install poppler-utils\n"
                    f"  macOS: brew install poppler\n"
                    f"  Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases\n"
                    f"           and add to PATH, or use: conda install -c conda-forge poppler\n"
                )
            
            # Fallback: try with bytes if file_path is actually bytes
            if isinstance(file_path, bytes):
                try:
                    dpi = dpi or self.ocr_dpi
                    images = convert_from_bytes(file_path, dpi=dpi)
                    return images
                except Exception as e2:
                    raise RuntimeError(f"Failed to extract pages from PDF: {str(e2)}")
            
            raise RuntimeError(f"Failed to extract pages from PDF: {str(e)}")
    
    def extract_pages_from_pdf_bytes(self, pdf_bytes: bytes, dpi: Optional[int] = None) -> List[Image.Image]:
        """Extract pages from PDF bytes.
        
        Args:
            pdf_bytes: PDF file as bytes
            dpi: DPI for conversion (defaults to self.ocr_dpi)
            
        Returns:
            List of PIL Images, one per page
            
        Raises:
            RuntimeError: If Poppler is not installed or PDF conversion fails
        """
        try:
            dpi = dpi or self.ocr_dpi
            images = convert_from_bytes(pdf_bytes, dpi=dpi)
            return images
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check for Poppler-related errors
            if "poppler" in error_msg or "pdftoppm" in error_msg or "pdftocairo" in error_msg:
                raise RuntimeError(
                    f"Poppler is required but not found or not accessible.\n"
                    f"Error: {str(e)}\n\n"
                    f"Installation instructions:\n"
                    f"  Ubuntu/Debian: sudo apt-get install poppler-utils\n"
                    f"  CentOS/RHEL: sudo yum install poppler-utils\n"
                    f"  macOS: brew install poppler\n"
                    f"  Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases\n"
                    f"           and add to PATH, or use: conda install -c conda-forge poppler\n"
                )
            
            raise RuntimeError(f"Failed to extract pages from PDF bytes: {str(e)}")
    
    def perform_ocr(self, image: Image.Image) -> Dict:
        """Perform OCR on a single image.
        
        Args:
            image: PIL Image to process
            
        Returns:
            Dictionary with text, bounding boxes, and confidence scores
        """
        # Lazy initialize OCR if needed
        self._initialize_ocr_if_needed()
        
        # Convert PIL Image to numpy array
        img_array = np.array(image)
        
        # Perform OCR (cls parameter removed in PaddleOCR 2.9+)
        # Angle classification is controlled by use_angle_cls during initialization
        result = self.ocr.ocr(img_array)
        
        if not result or not result[0]:
            return {
                "text": "",
                "full_text": "",
                "bounding_boxes": [],
                "confidence_scores": [],
                "average_confidence": 0.0
            }
        
        # Extract text and metadata
        # PaddleOCR result structure: [[[box_coords], (text, confidence)], ...]
        lines = result[0] if result else []
        full_text_parts = []
        bounding_boxes = []
        confidence_scores = []
        
        for line in lines:
            if line and len(line) >= 2:
                try:
                    # Handle different PaddleOCR result structures
                    if isinstance(line[0], (list, tuple)) and len(line[0]) >= 4:
                        # Standard structure: [box_coords, (text, confidence)]
                        box = line[0]
                        if isinstance(line[1], (list, tuple)) and len(line[1]) >= 2:
                            text, confidence = line[1][0], line[1][1]
                        else:
                            # Fallback: line[1] might be just text
                            text = str(line[1]) if len(line) > 1 else ""
                            confidence = 1.0
                    else:
                        # Alternative structure: try to extract from available data
                        box = line[0] if isinstance(line[0], (list, tuple)) else []
                        text = str(line[1]) if len(line) > 1 else ""
                        confidence = float(line[2]) if len(line) > 2 else 1.0
                    
                    full_text_parts.append(text)
                    bounding_boxes.append(box)
                    confidence_scores.append(confidence)
                except (ValueError, IndexError, TypeError) as e:
                    # Skip malformed lines
                    continue
        
        full_text = "\n".join(full_text_parts)
        avg_confidence = np.mean(confidence_scores) if confidence_scores else 0.0
        
        return {
            "text": full_text,
            "full_text": full_text,
            "bounding_boxes": bounding_boxes,
            "confidence_scores": confidence_scores,
            "average_confidence": float(avg_confidence)
        }
    
    def extract_embedded_images(self, pdf_path: str) -> List[Dict]:
        """Extract embedded images from PDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of dictionaries with image data and metadata
        """
        embedded_images = []
        
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num, page in enumerate(pdf_reader.pages):
                    if '/XObject' in page.get('/Resources', {}):
                        xobjects = page['/Resources']['/XObject'].get_object()
                        
                        for obj_name in xobjects:
                            obj = xobjects[obj_name]
                            if obj.get('/Subtype') == '/Image':
                                embedded_images.append({
                                    "page": page_num + 1,
                                    "name": obj_name,
                                    "width": obj.get('/Width'),
                                    "height": obj.get('/Height'),
                                    "filter": obj.get('/Filter')
                                })
        except Exception as e:
            # If extraction fails, return empty list
            pass
        
        return embedded_images
    
    def extract_text_from_pdf(self, file_path: str) -> Dict[str, Any]:
        """Extract text directly from PDF using PyPDF2 (fast, for text-based PDFs).
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Dictionary with page texts and metadata
        """
        page_texts = []
        total_text_length = 0
        
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                num_pages = len(pdf_reader.pages)
                
                for page_num, page in enumerate(pdf_reader.pages, start=1):
                    try:
                        text = page.extract_text()
                        text_length = len(text.strip())
                        total_text_length += text_length
                        
                        page_texts.append({
                            "page_number": page_num,
                            "text": text,
                            "text_length": text_length,
                            "extraction_method": "direct"
                        })
                    except Exception as e:
                        # If extraction fails for a page, add empty entry
                        page_texts.append({
                            "page_number": page_num,
                            "text": "",
                            "text_length": 0,
                            "extraction_method": "direct_error",
                            "error": str(e)
                        })
                
                # Calculate average text per page (for quality check)
                avg_text_per_page = total_text_length / num_pages if num_pages > 0 else 0
                
                return {
                    "success": True,
                    "pages": page_texts,
                    "total_pages": num_pages,
                    "total_text_length": total_text_length,
                    "average_text_per_page": avg_text_per_page,
                    "extraction_method": "direct"
                }
        except Exception as e:
            return {
                "success": False,
                "pages": [],
                "total_pages": 0,
                "total_text_length": 0,
                "average_text_per_page": 0,
                "extraction_method": "direct",
                "error": str(e)
            }
    
    def process_document(self, file_path: str, force_ocr: bool = False) -> Dict:
        """Process a complete document: try direct text extraction first, OCR fallback.
        
        Args:
            file_path: Path to PDF file
            force_ocr: Force OCR even if text extraction succeeds
            
        Returns:
            Dictionary with processed document data
        """
        # Step 1: Try direct text extraction first (fast for text-based PDFs)
        text_extraction_result = self.extract_text_from_pdf(file_path)
        
        # Determine if we need OCR
        needs_ocr = force_ocr
        if not needs_ocr:
            # Use OCR if:
            # - Text extraction failed
            # - Average text per page is very low (< 50 chars/page suggests scanned/image-based)
            # - Total text is very low (< 10% of expected for document type)
            if not text_extraction_result.get("success"):
                needs_ocr = True
            elif text_extraction_result.get("average_text_per_page", 0) < 50:
                # Very low text suggests scanned document
                needs_ocr = True
            elif text_extraction_result.get("total_text_length", 0) < 100:
                # Very little text overall
                needs_ocr = True
        
        processed_pages = []
        total_confidence = 0.0
        extraction_method = "hybrid"
        
        if needs_ocr:
            # Use OCR path
            extraction_method = "ocr"
            page_images = self.extract_pages_from_pdf(file_path)
            
            for page_num, page_image in enumerate(page_images, start=1):
                # Perform OCR
                ocr_result = self.perform_ocr(page_image)
                
                page_data = {
                    "page_number": page_num,
                    "text": ocr_result["full_text"],
                    "bounding_boxes": ocr_result["bounding_boxes"],
                    "confidence_scores": ocr_result["confidence_scores"],
                    "average_confidence": ocr_result["average_confidence"],
                    "is_legible": ocr_result["average_confidence"] >= self.legibility_threshold,
                    "extraction_method": "ocr"
                }
                
                processed_pages.append(page_data)
                total_confidence += ocr_result["average_confidence"]
        else:
            # Use direct text extraction (much faster)
            extraction_method = "direct"
            for page_data in text_extraction_result.get("pages", []):
                # Convert to standard format with high confidence for direct extraction
                processed_pages.append({
                    "page_number": page_data["page_number"],
                    "text": page_data["text"],
                    "bounding_boxes": [],
                    "confidence_scores": [],
                    "average_confidence": 0.95 if page_data["text_length"] > 0 else 0.0,  # High confidence for direct extraction
                    "is_legible": page_data["text_length"] > 0,
                    "extraction_method": "direct"
                })
                total_confidence += 0.95 if page_data["text_length"] > 0 else 0.0
        
        # Extract embedded images
        embedded_images = self.extract_embedded_images(file_path)
        image_count = len(embedded_images)
        
        # Calculate overall legibility
        avg_confidence = total_confidence / len(processed_pages) if processed_pages else 0.0
        is_legible = avg_confidence >= self.legibility_threshold
        
        return {
            "total_pages": len(processed_pages),
            "total_images": image_count,
            "average_confidence": avg_confidence,
            "is_legible": is_legible,
            "pages": processed_pages,
            "embedded_images": embedded_images,
            "extraction_method": extraction_method
        }
    
    def process_document_bytes(self, pdf_bytes: bytes) -> Dict:
        """Process a document from bytes.
        
        Args:
            pdf_bytes: PDF file as bytes
            
        Returns:
            Dictionary with processed document data
        """
        # Save to temporary file for processing
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(pdf_bytes)
            tmp_path = tmp_file.name
        
        try:
            result = self.process_document(tmp_path)
            return result
        finally:
            # Clean up temporary file
            Path(tmp_path).unlink(missing_ok=True)

