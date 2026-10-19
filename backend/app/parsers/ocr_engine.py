import os
import shutil
from typing import Optional, List

try:
    import pytesseract
    from PIL import Image
    from pdf2image import convert_from_path
    OCR_PACKAGES_INSTALLED = True
except ImportError:
    OCR_PACKAGES_INSTALLED = False

def is_ocr_available() -> bool:
    """Check if Tesseract binary and required libraries are installed."""
    if not OCR_PACKAGES_INSTALLED:
        return False
    # Check if tesseract is in PATH or known location
    tesseract_cmd = shutil.which("tesseract") or shutil.which("tesseract.exe")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        return True
    
    # Common Windows paths
    common_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe")
    ]
    for p in common_paths:
        if os.path.isfile(p):
            pytesseract.pytesseract.tesseract_cmd = p
            return True
            
    return False

def ocr_pdf_to_text(pdf_path: str) -> str:
    """
    Fallback OCR engine for scanned PDFs.
    Returns concatenated text from all pages.
    """
    if not is_ocr_available():
        raise RuntimeError("Tesseract OCR binary is not installed on the system.")
        
    try:
        images = convert_from_path(pdf_path)
        extracted = []
        for img in images:
            text = pytesseract.image_to_string(img)
            extracted.append(text)
        return "\n--- PAGE BREAK ---\n".join(extracted)
    except Exception as e:
        raise RuntimeError(f"OCR execution failed: {str(e)}")
