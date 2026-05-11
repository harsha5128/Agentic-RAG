# Evaluation Service

This service evaluates the quality and performance of query responses and system metrics.

## Development Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the service:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

## API Endpoints

- `POST /evaluate`: Evaluate a query response
- `GET /metrics`: Get evaluation metrics
- `GET /health`: Health check

## Features

- Response quality metrics
- Performance tracking
- User feedback integration