"""
Document Processing Tool
========================
OCR, PDF parsing, image analysis for claim document intake.
"""
import io
import base64
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import uuid

from loguru import logger

# PDF processing
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

# Image processing
try:
    from PIL import Image
    import pytesseract
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

# OpenCV for image quality
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


class DocumentProcessor:
    """
    Process various document types for claim intake.
    Handles PDFs, images, and text extraction with OCR.
    """
    
    def __init__(self, ocr_min_confidence: float = 85.0):
        self.ocr_min_confidence = ocr_min_confidence
        self.logger = logger.bind(module="document_processor")
        
        # Configure Tesseract if available
        if PILLOW_AVAILABLE and not OPENCV_AVAILABLE:
            self.logger.warning("OpenCV not available - image quality checks disabled")
    
    def process_document(
        self,
        file_path: str = None,
        file_bytes: bytes = None,
        file_name: str = None,
        document_type: str = "unknown"
    ) -> Dict[str, Any]:
        """
        Process a document and extract text/content.
        
        Args:
            file_path: Path to the document file
            file_bytes: Raw bytes of the document
            file_name: Original file name
            document_type: Type of document (claim_form, photo, etc.)
            
        Returns:
            Dictionary with extracted text, metadata, and quality scores
        """
        result = {
            "document_id": str(uuid.uuid4()),
            "document_type": document_type,
            "file_name": file_name or "unknown",
            "processed_at": datetime.utcnow().isoformat(),
            "text_content": "",
            "ocr_confidence": 0.0,
            "quality_score": "unknown",
            "metadata": {},
            "tables": [],
            "images_count": 0,
            "pages_count": 0,
            "errors": []
        }
        
        try:
            # Determine file format
            file_format = self._detect_format(file_path, file_bytes, file_name)
            result["file_format"] = file_format
            
            # Process based on format
            if file_format in ["PDF"]:
                result.update(self._process_pdf(file_path, file_bytes))
            elif file_format in ["JPG", "JPEG", "PNG", "BMP", "TIFF"]:
                result.update(self._process_image(file_path, file_bytes))
            elif file_format in ["TXT", "TEXT"]:
                result.update(self._process_text(file_path, file_bytes))
            elif file_format in ["EMAIL"]:
                result.update(self._process_email(file_path, file_bytes))
            else:
                result["errors"].append(f"Unsupported file format: {file_format}")
            
            # Calculate quality score
            result["quality_score"] = self._calculate_quality_score(result)
            
            self.logger.info(
                f"Document processed: {result['file_name']}",
                format=file_format,
                quality=result["quality_score"],
                ocr_confidence=result.get("ocr_confidence", 0)
            )
            
        except Exception as e:
            self.logger.error(f"Error processing document: {str(e)}")
            result["errors"].append(str(e))
        
        return result
    
    def _detect_format(
        self,
        file_path: str = None,
        file_bytes: bytes = None,
        file_name: str = None
    ) -> str:
        """Detect file format from extension or magic bytes."""
        if file_name:
            ext = Path(file_name).suffix.lower()
            if ext == ".pdf":
                return "PDF"
            elif ext in [".jpg", ".jpeg"]:
                return "JPG"
            elif ext == ".png":
                return "PNG"
            elif ext in [".bmp", ".tiff", ".tif"]:
                return "IMAGE"
            elif ext in [".txt", ".text"]:
                return "TXT"
            elif ext in [".eml", ".msg"]:
                return "EMAIL"
        
        # Try magic bytes detection
        if file_bytes:
            if file_bytes[:4] == b'%PDF':
                return "PDF"
            elif file_bytes[:2] == b'\xff\xd8':
                return "JPG"
            elif file_bytes[:8] == b'\x89PNG\r\n\x1a\n':
                return "PNG"
        
        if file_path:
            try:
                with open(file_path, 'rb') as f:
                    header = f.read(8)
                    if header[:4] == b'%PDF':
                        return "PDF"
            except:
                pass
        
        return "UNKNOWN"
    
    def _process_pdf(
        self,
        file_path: str = None,
        file_bytes: bytes = None
    ) -> Dict[str, Any]:
        """Process PDF document."""
        result = {
            "text_content": "",
            "pages_count": 0,
            "images_count": 0,
            "tables": [],
            "ocr_confidence": 100.0,  # Native PDF text has 100% confidence
            "ocr_completed": False
        }
        
        # Try PyMuPDF first (faster)
        if PYMUPDF_AVAILABLE:
            try:
                if file_bytes:
                    doc = fitz.open(stream=file_bytes, filetype="pdf")
                else:
                    doc = fitz.open(file_path)
                
                result["pages_count"] = len(doc)
                
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    text = page.get_text()
                    result["text_content"] += f"\n--- Page {page_num + 1} ---\n{text}"
                    
                    # Count images
                    images = page.get_images()
                    result["images_count"] += len(images)
                
                doc.close()
                result["ocr_completed"] = False  # Native text extraction, not OCR
                
            except Exception as e:
                result["tables"].append({"error": f"PyMuPDF error: {str(e)}"})
        
        # Fallback to pdfplumber
        if not result["text_content"] and PDFPLUMBER_AVAILABLE:
            try:
                if file_bytes:
                    pdf = pdfplumber.open(io.BytesIO(file_bytes))
                else:
                    pdf = pdfplumber.open(file_path)
                
                result["pages_count"] = len(pdf.pages)
                
                for page_num, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    result["text_content"] += f"\n--- Page {page_num + 1} ---\n{text}"
                    
                    # Extract tables
                    tables = page.extract_tables()
                    for table in tables:
                        result["tables"].append({
                            "page": page_num + 1,
                            "data": table
                        })
                
                pdf.close()
                
            except Exception as e:
                pass
        
        # If still no text, might be scanned PDF - run OCR
        if not result["text_content"].strip() and PILLOW_AVAILABLE:
            self.logger.info("PDF appears to be scanned - running OCR")
            ocr_result = self._ocr_pdf(file_path, file_bytes)
            result["text_content"] = ocr_result.get("text_content", "")
            result["ocr_confidence"] = ocr_result.get("ocr_confidence", 0)
            result["ocr_completed"] = True
        
        return result
    
    def _ocr_pdf(self, file_path: str = None, file_bytes: bytes = None) -> Dict[str, Any]:
        """Run OCR on scanned PDF."""
        result = {"text_content": "", "ocr_confidence": 0.0}
        
        if not PILLOW_AVAILABLE:
            return result
        
        try:
            if file_bytes:
                doc = fitz.open(stream=file_bytes, filetype="pdf")
            else:
                doc = fitz.open(file_path)
            
            all_text = []
            confidences = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
                img_data = pix.tobytes("png")
                
                # Run OCR
                img = Image.open(io.BytesIO(img_data))
                ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                
                # Extract text and confidence
                page_text = []
                page_confidences = []
                for i, text in enumerate(ocr_data['text']):
                    if text.strip():
                        page_text.append(text)
                        conf = ocr_data['conf'][i]
                        if conf > 0:
                            page_confidences.append(conf)
                
                all_text.append(f"\n--- Page {page_num + 1} ---\n" + " ".join(page_text))
                if page_confidences:
                    confidences.extend(page_confidences)
            
            doc.close()
            
            result["text_content"] = "".join(all_text)
            result["ocr_confidence"] = sum(confidences) / len(confidences) if confidences else 0
            
        except Exception as e:
            self.logger.error(f"OCR error: {str(e)}")
        
        return result
    
    def _process_image(
        self,
        file_path: str = None,
        file_bytes: bytes = None
    ) -> Dict[str, Any]:
        """Process image file with OCR."""
        result = {
            "text_content": "",
            "ocr_confidence": 0.0,
            "ocr_completed": True,
            "images_count": 1,
            "pages_count": 1,
            "metadata": {}
        }
        
        if not PILLOW_AVAILABLE:
            result["errors"] = ["PIL/Pillow not available for image processing"]
            return result
        
        try:
            # Load image
            if file_bytes:
                img = Image.open(io.BytesIO(file_bytes))
            else:
                img = Image.open(file_path)
            
            # Extract EXIF metadata
            if hasattr(img, '_getexif'):
                exif = img._getexif()
                if exif:
                    result["metadata"]["exif"] = dict(exif)
            
            # Check image quality (if OpenCV available)
            if OPENCV_AVAILABLE:
                if file_bytes:
                    img_array = np.frombuffer(file_bytes, np.uint8)
                    img_cv = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                else:
                    img_cv = cv2.imread(file_path)
                
                # Blur detection
                gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                variance = cv2.Laplacian(gray, cv2.CV_64F).var()
                result["metadata"]["blur_score"] = float(variance)
                result["metadata"]["is_blurry"] = variance < 100
            
            # Run OCR
            if file_bytes:
                img = Image.open(io.BytesIO(file_bytes))
            
            ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            
            # Extract text and confidence
            text_parts = []
            confidences = []
            for i, text in enumerate(ocr_data['text']):
                if text.strip():
                    text_parts.append(text)
                    conf = ocr_data['conf'][i]
                    if conf > 0:
                        confidences.append(conf)
            
            result["text_content"] = " ".join(text_parts)
            result["ocr_confidence"] = sum(confidences) / len(confidences) if confidences else 0
            
        except Exception as e:
            result["errors"].append(str(e))
        
        return result
    
    def _process_text(
        self,
        file_path: str = None,
        file_bytes: bytes = None
    ) -> Dict[str, Any]:
        """Process plain text file."""
        result = {
            "text_content": "",
            "ocr_confidence": 100.0,
            "ocr_completed": False,
            "images_count": 0,
            "pages_count": 1
        }
        
        try:
            if file_bytes:
                result["text_content"] = file_bytes.decode('utf-8')
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    result["text_content"] = f.read()
        except Exception as e:
            result["errors"].append(str(e))
        
        return result
    
    def _process_email(
        self,
        file_path: str = None,
        file_bytes: bytes = None
    ) -> Dict[str, Any]:
        """Process email file (.eml)."""
        result = {
            "text_content": "",
            "ocr_confidence": 100.0,
            "ocr_completed": False,
            "images_count": 0,
            "pages_count": 1,
            "metadata": {}
        }
        
        try:
            import email
            from email import policy
            
            if file_bytes:
                msg = email.message_from_bytes(file_bytes, policy=policy.default)
            else:
                with open(file_path, 'rb') as f:
                    msg = email.message_from_bytes(f.read(), policy=policy.default)
            
            # Extract headers
            result["metadata"]["subject"] = msg.get('Subject', '')
            result["metadata"]["from"] = msg.get('From', '')
            result["metadata"]["to"] = msg.get('To', '')
            result["metadata"]["date"] = msg.get('Date', '')
            
            # Extract body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get_content_disposition())
                    
                    if content_type == "text/plain" and "attachment" not in content_disposition:
                        try:
                            body += part.get_content()
                        except:
                            pass
                    elif content_type.startswith("image/"):
                        result["images_count"] += 1
            else:
                body = msg.get_content()
            
            result["text_content"] = f"""
Subject: {result['metadata']['subject']}
From: {result['metadata']['from']}
To: {result['metadata']['to']}
Date: {result['metadata']['date']}

{body}
"""
            
        except Exception as e:
            result["errors"].append(str(e))
        
        return result
    
    def _calculate_quality_score(self, result: Dict[str, Any]) -> str:
        """Calculate overall document quality score."""
        errors = result.get("errors", [])
        ocr_confidence = result.get("ocr_confidence", 100)
        blur_score = result.get("metadata", {}).get("blur_score", float('inf'))
        is_blurry = result.get("metadata", {}).get("is_blurry", False)
        
        # Critical issues
        if errors:
            return "poor"
        
        # OCR confidence check
        if ocr_confidence < self.ocr_min_confidence:
            return "poor"
        
        # Blur check
        if is_blurry:
            return "poor"
        
        # Good quality
        if ocr_confidence >= 95 and not is_blurry:
            return "good"
        
        return "fair"
    
    def extract_claim_fields(self, text: str) -> Dict[str, Any]:
        """
        Extract common claim fields from text using pattern matching.
        For more advanced extraction, use LLM-based extraction.
        """
        import re
        
        extracted = {
            "policy_number": None,
            "claim_amount": None,
            "date_of_loss": None,
            "phone_numbers": [],
            "emails": [],
            "addresses": []
        }
        
        # Policy number patterns (common formats)
        policy_patterns = [
            r'Policy\s*#?\s*:?\s*([A-Z0-9-]{8,20})',
            r'Policy\s+Number\s*:?\s*([A-Z0-9-]{8,20})',
            r'([A-Z]{2,3}-\d{6,10})',
        ]
        for pattern in policy_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted["policy_number"] = match.group(1)
                break
        
        # Dollar amounts
        amount_patterns = [
            r'\$([\d,]+(?:\.\d{2})?)',
            r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*dollars?',
        ]
        for pattern in amount_patterns:
            matches = re.findall(pattern, text)
            if matches:
                amounts = []
                for m in matches:
                    try:
                        amounts.append(float(m.replace(',', '')))
                    except:
                        pass
                if amounts:
                    extracted["claim_amount"] = max(amounts)
        
        # Phone numbers
        phone_pattern = r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})'
        extracted["phone_numbers"] = re.findall(phone_pattern, text)
        
        # Emails
        email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        extracted["emails"] = re.findall(email_pattern, text)
        
        return extracted


# Singleton instance
_document_processor = None

def get_document_processor() -> DocumentProcessor:
    """Get or create document processor singleton."""
    global _document_processor
    if _document_processor is None:
        _document_processor = DocumentProcessor()
    return _document_processor
