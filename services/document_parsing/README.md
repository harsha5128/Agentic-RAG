# Document Parsing Service

This service parses various document formats and extracts text content and metadata.

## Supported Formats

- PDF documents
- DOCX files
- Excel spreadsheets (XLSX)
- Images (with OCR)
- CSV files

## Development Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. For OCR functionality, ensure Tesseract is installed on your system.

3. Set environment variables (see common/config/settings.py)

4. Run the service:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

## API Endpoints

- `POST /parse`: Parse a document and return extracted text and metadata
- `GET /health`: Health check

## Key Features

- Multi-parser fallback system
- Table extraction from PDFs and spreadsheets
- OCR for image-based documents
- Semantic chunking support