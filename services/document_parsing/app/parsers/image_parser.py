"""
Image Parser for Document Parsing Service
"""

import pytesseract
from PIL import Image
from io import BytesIO
from typing import Dict, Any, Tuple

from common.observability import get_logger
from common.exceptions import DocumentParsingError, ErrorCode

from .base_parser import DocumentParser

logger = get_logger(__name__)


class ImageParser(DocumentParser):
    """Parse image files with OCR"""

    async def parse(self, file_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
        """Extract text from image using OCR"""
        try:
            image = Image.open(BytesIO(file_bytes))
            text = pytesseract.image_to_string(image)

            metadata = {
                "width": image.width,
                "height": image.height,
                "format": image.format,
                "mode": image.mode,
                "extracted_via_ocr": True,
            }

            return text, metadata
        except Exception as e:
            logger.error(f"Image parsing failed: {str(e)}")
            raise DocumentParsingError(
                ErrorCode.OCR_FAILED,
                "Failed to parse image",
                {"original_error": str(e)},
                e,
            )