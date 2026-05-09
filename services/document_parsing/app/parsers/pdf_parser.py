"""
PDF Parser for Document Parsing Service
"""

import os
import tempfile
import pytesseract
from PyPDF2 import PdfReader
from io import BytesIO
from typing import Dict, Any, Tuple, List

from common.config import settings
from common.observability import get_logger
from common.exceptions import DocumentParsingError, ErrorCode

from .base_parser import DocumentParser

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None

try:
    import camelot
except ImportError:  # pragma: no cover
    camelot = None

try:
    from unstructured.partition.pdf import partition_pdf
except ImportError:  # pragma: no cover
    partition_pdf = None

logger = get_logger(__name__)


class PDFParser(DocumentParser):
    """
    Parse PDF documents with production-first libraries.

    Preferred path:
    - unstructured for layout-aware elements
    - pdfplumber for text and tables
    - camelot for table extraction

    Fallback path:
    - PyPDF2 plus OCR for pages where normal extraction fails. Keeping this
      fallback is intentional: it documents how the extraction can be built
      manually if third-party layout/table libraries are unavailable.
    """

    async def parse(self, file_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
        """Extract text and metadata from PDF"""
        try:
            content_parts: List[str] = []
            metadata: Dict[str, Any] = {
                "parser_stack": [],
                "extracted_via_ocr": False,
                "tables": [],
                "page_contents": [],
            }

            unstructured_text = self._extract_with_unstructured(file_bytes, metadata)
            if unstructured_text:
                content_parts.append(unstructured_text)

            plumber_text = self._extract_with_pdfplumber(file_bytes, metadata)
            if plumber_text:
                content_parts.append(plumber_text)

            camelot_tables = self._extract_tables_with_camelot(file_bytes, metadata)
            if camelot_tables:
                content_parts.append(camelot_tables)

            if content_parts:
                return "\n\n".join(content_parts), metadata

            return self._parse_with_pypdf_fallback(file_bytes)
        except Exception as e:
            logger.error(f"PDF parsing failed: {str(e)}")
            raise DocumentParsingError(
                ErrorCode.PARSE_FAILED,
                "Failed to parse PDF",
                {"original_error": str(e)},
                e,
            )

    def _extract_with_unstructured(self, file_bytes: bytes, metadata: Dict[str, Any]) -> str:
        if not partition_pdf:
            return ""

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                temp_file.write(file_bytes)
                temp_path = temp_file.name

            elements = partition_pdf(filename=temp_path, strategy="auto")
            text = "\n".join(str(element) for element in elements if str(element).strip())
            if text:
                metadata["parser_stack"].append("unstructured.partition_pdf")
                metadata["unstructured_elements"] = len(elements)
            return text
        except Exception as e:
            logger.warning(f"Unstructured PDF extraction failed, continuing fallback chain: {str(e)}")
            return ""
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def _extract_with_pdfplumber(self, file_bytes: bytes, metadata: Dict[str, Any]) -> str:
        if not pdfplumber:
            return ""

        try:
            text_parts = []
            tables = []
            with pdfplumber.open(BytesIO(file_bytes)) as pdf:
                metadata["pages"] = len(pdf.pages)
                for page_idx, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        text_parts.append(f"\n--- Page {page_idx + 1} ---\n{page_text}")
                    page_tables = page.extract_tables() or []
                    for table_idx, table in enumerate(page_tables):
                        table_text = self._format_table(table)
                        text_parts.append(f"\n--- Page {page_idx + 1} Table {table_idx + 1} ---\n{table_text}")
                        tables.append({
                            "source": "pdfplumber",
                            "page": page_idx + 1,
                            "table_index": table_idx,
                            "rows": len(table),
                        })
                    metadata["page_contents"].append({
                        "page": page_idx + 1,
                        "has_content": bool(page_text.strip() or page_tables),
                    })

            if text_parts:
                metadata["parser_stack"].append("pdfplumber")
                metadata["tables"].extend(tables)
            return "\n".join(text_parts)
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed, continuing fallback chain: {str(e)}")
            return ""

    def _extract_tables_with_camelot(self, file_bytes: bytes, metadata: Dict[str, Any]) -> str:
        if not camelot:
            return ""

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                temp_file.write(file_bytes)
                temp_path = temp_file.name

            text_parts = []
            extracted_tables = []
            for flavor in ("lattice", "stream"):
                try:
                    tables = camelot.read_pdf(temp_path, pages="all", flavor=flavor)
                    for table_idx, table in enumerate(tables):
                        table_text = table.df.to_markdown(index=False)
                        text_parts.append(f"\n--- Camelot {flavor} Table {table_idx + 1} ---\n{table_text}")
                        extracted_tables.append({
                            "source": "camelot",
                            "flavor": flavor,
                            "table_index": table_idx,
                            "rows": len(table.df),
                            "columns": len(table.df.columns),
                            "accuracy": table.parsing_report.get("accuracy"),
                        })
                    if tables:
                        break
                except Exception as e:
                    logger.debug(f"Camelot {flavor} extraction skipped: {str(e)}")

            if text_parts:
                metadata["parser_stack"].append("camelot")
                metadata["tables"].extend(extracted_tables)
            return "\n".join(text_parts)
        except Exception as e:
            logger.warning(f"Camelot table extraction failed, continuing fallback chain: {str(e)}")
            return ""
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def _parse_with_pypdf_fallback(self, file_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
        try:
            pdf_reader = PdfReader(BytesIO(file_bytes))
            text = ""
            metadata = {
                "pages": len(pdf_reader.pages),
                "extracted_via_ocr": False,
                "page_contents": [],
                "parser_stack": ["pypdf_fallback"],
                "tables": [],
            }

            for page_num, page in enumerate(pdf_reader.pages):
                # Extract text
                page_text = page.extract_text() or ""
                text += f"\n--- Page {page_num + 1} ---\n" + page_text + "\n"

                # Apply OCR if text extraction failed
                if not page_text.strip() and settings.OCR_ENABLED:
                    try:
                        from pdf2image import convert_from_bytes
                        images = convert_from_bytes(file_bytes, first_page=page_num+1, last_page=page_num+1)
                        if images:
                            ocr_text = pytesseract.image_to_string(images[0])
                            text += ocr_text + "\n"
                            metadata["extracted_via_ocr"] = True
                    except Exception as e:
                        logger.warning(f"OCR failed for page {page_num}: {str(e)}")

                metadata["page_contents"].append({
                    "page": page_num + 1,
                    "has_content": len(page_text.strip()) > 0,
                })

            # Extract metadata
            if pdf_reader.metadata:
                metadata.update({
                    "title": pdf_reader.metadata.get("/Title", ""),
                    "author": pdf_reader.metadata.get("/Author", ""),
                    "subject": pdf_reader.metadata.get("/Subject", ""),
                })

            return text, metadata
        except Exception as e:
            logger.error(f"PyPDF fallback parsing failed: {str(e)}")
            raise DocumentParsingError(
                ErrorCode.PARSE_FAILED,
                "Failed to parse PDF",
                {"original_error": str(e)},
                e,
            )

    def _format_table(self, table: List[List[Any]]) -> str:
        if not table:
            return ""
        return "\n".join(
            " | ".join("" if cell is None else str(cell) for cell in row)
            for row in table
        )
