"""
Spreadsheet Parser for Document Parsing Service
"""

import pandas as pd
from io import BytesIO
from typing import Dict, Any, Tuple

from common.observability import get_logger
from common.exceptions import DocumentParsingError, ErrorCode

from .base_parser import DocumentParser

logger = get_logger(__name__)


class SpreadsheetParser(DocumentParser):
    """
    Parse XLSX and CSV files as table-aware text.

    Pandas/openpyxl are the production path here because they preserve sheet,
    row, column, and null-count metadata. The output is markdown-ish table text
    so downstream chunking and embedding keep table structure better than a raw
    string dump.
    """

    async def parse(self, file_bytes: bytes, file_type: str = "xlsx") -> Tuple[str, Dict[str, Any]]:
        """Extract text and metadata from spreadsheet"""
        try:
            if file_type == "xlsx":
                df = pd.read_excel(BytesIO(file_bytes), sheet_name=None)
            else:
                df = pd.read_csv(BytesIO(file_bytes))
                df = {"Sheet1": df}

            text = ""
            metadata = {
                "parser_stack": ["pandas", "openpyxl" if file_type == "xlsx" else "csv"],
                "sheets": len(df) if isinstance(df, dict) else 1,
                "total_rows": 0,
                "total_columns": 0,
                "tables": [],
            }

            sheet_data = []
            for sheet_name, sheet_df in (df.items() if isinstance(df, dict) else [("Sheet1", df)]):
                text += f"\n=== Sheet: {sheet_name} ===\n"
                text += self._dataframe_to_text(sheet_df) + "\n"

                sheet_data.append({
                    "name": sheet_name,
                    "rows": len(sheet_df),
                    "columns": len(sheet_df.columns),
                    "column_names": list(sheet_df.columns),
                    "null_cells": int(sheet_df.isna().sum().sum()),
                })
                metadata["tables"].append({
                    "source": "spreadsheet",
                    "sheet": sheet_name,
                    "rows": len(sheet_df),
                    "columns": len(sheet_df.columns),
                })

                metadata["total_rows"] += len(sheet_df)
                metadata["total_columns"] = max(metadata["total_columns"], len(sheet_df.columns))

            metadata["sheets_info"] = sheet_data
            return text, metadata
        except Exception as e:
            logger.error(f"Spreadsheet parsing failed: {str(e)}")
            raise DocumentParsingError(
                ErrorCode.PARSE_FAILED,
                "Failed to parse spreadsheet",
                {"original_error": str(e)},
                e,
            )

    def _dataframe_to_text(self, df: pd.DataFrame) -> str:
        """Prefer markdown tables, fall back to plain text if tabulate is absent."""
        try:
            return df.to_markdown(index=False)
        except Exception:
            return df.to_string(index=False)
