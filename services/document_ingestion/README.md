# Document Ingestion Service

This service handles the ingestion of documents from S3 buckets and prepares them for parsing.

## Responsibilities

- Listen for S3 object creation events
- Validate and deduplicate documents
- Extract basic metadata
- Queue documents for parsing via SQS

## Development Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set environment variables (see common/config/settings.py for required vars)

3. Run the service:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

## API Endpoints

- `POST /process-s3-event`: Process S3 event notifications
- `GET /health`: Health check endpoint

## Dependencies

- AWS S3 and SQS for event-driven ingestion
- MongoDB for document metadata storage
- Redis for caching (if needed)